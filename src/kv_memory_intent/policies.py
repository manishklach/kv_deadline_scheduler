"""Placement policies for KV Deadline Scheduler.

Higher score = better eviction candidate. Negative contributions protect a block.
"""

from __future__ import annotations

from dataclasses import dataclass

from .schema import MemoryIntent, Phase, Priority, Tier


class PlacementPolicy:
    name = "base"

    def choose_victim(
        self,
        blocks: list[MemoryIntent],
        capacity_bytes: int,
        current_step: int,
    ) -> MemoryIntent | None:
        raise NotImplementedError

    def should_prefetch(self, block: MemoryIntent, current_step: int) -> bool:
        return False

    def explain_victim_choice(
        self,
        victim: MemoryIntent,
        candidates: list[MemoryIntent],
        current_step: int,
    ) -> str:
        del current_step
        return f"Selected {victim.object_id} for eviction under {self.name}."


class LRUPolicy(PlacementPolicy):
    name = "LRU"

    def choose_victim(
        self,
        blocks: list[MemoryIntent],
        capacity_bytes: int,
        current_step: int,
    ) -> MemoryIntent | None:
        del capacity_bytes, current_step
        if not blocks:
            return None
        return min(blocks, key=lambda block: (block.last_access_step, -block.size_bytes, block.object_id))


class HotColdPolicy(PlacementPolicy):
    name = "HotCold"

    def choose_victim(
        self,
        blocks: list[MemoryIntent],
        capacity_bytes: int,
        current_step: int,
    ) -> MemoryIntent | None:
        del capacity_bytes, current_step
        if not blocks:
            return None
        return min(
            blocks,
            key=lambda block: (block.recency_score, block.last_access_step, -block.size_bytes, block.object_id),
        )


class PredictiveHotnessPolicy(PlacementPolicy):
    name = "PredictiveHotness"

    def predicted_hotness(self, block: MemoryIntent) -> float:
        reuse_signal = 0.0
        if block.expected_reuse_window_tokens is not None:
            reuse_signal = max(0.0, 64.0 - float(block.expected_reuse_window_tokens)) / 64.0
        return (block.recency_score * 0.7) + (reuse_signal * 0.3)

    def choose_victim(
        self,
        blocks: list[MemoryIntent],
        capacity_bytes: int,
        current_step: int,
    ) -> MemoryIntent | None:
        del capacity_bytes, current_step
        if not blocks:
            return None
        return min(
            blocks,
            key=lambda block: (
                self.predicted_hotness(block),
                block.last_access_step,
                -block.size_bytes,
                block.object_id,
            ),
        )


@dataclass(slots=True)
class IntentAwarePolicy(PlacementPolicy):
    name: str = "IntentAware"

    def eviction_score(self, block: MemoryIntent, current_step: int) -> float:
        """Higher score means the block is a better eviction candidate."""
        score = 0.0
        priority_weight = {
            Priority.COLD: 110.0,
            Priority.WARM: 55.0,
            Priority.HOT: 15.0,
            Priority.DECODE_CRITICAL: -900.0,
        }
        score += priority_weight[block.priority]  # COLD=+110 makes it a preferred victim; DECODE_CRITICAL=-900 protects it strongly
        if block.pin_requested:
            score -= 900.0  # Explicit pinning nearly removes the block from consideration unless there are no alternatives
        if block.phase == Phase.DONE:
            score += 120.0  # DONE state is safe to displace aggressively because the request no longer needs it live
        elif block.phase == Phase.IDLE:
            score += 50.0  # IDLE state is less urgent than active decode or verify paths, so it drifts toward eviction
        score += float(100 - block.request_priority)  # Lower-priority requests add positive score so they yield capacity first
        if block.expected_reuse_window_tokens is not None:
            score += min(block.expected_reuse_window_tokens / 6.0, 120.0)  # Long reuse windows imply delayed need, so they bias toward eviction
        if block.recompute_ok:
            score += 30.0  # Recompute-friendly blocks can be sacrificed because recovery cost is acceptable
        if block.compression_ok:
            score += 20.0  # Compressible blocks are easier to demote because another space-saving path exists
        if block.is_draft and not block.is_committed:
            score += 45.0  # Uncommitted draft state is speculative, so it is intentionally easier to evict
        if block.recompute_cost_us is not None:
            score -= min(block.recompute_cost_us / 40.0, 180.0)  # Expensive recovery subtracts score to protect costly blocks
        score -= block.recency_score * 60.0  # Recently touched blocks lose score because fresh access suggests near-term reuse
        access_age = max(current_step - block.last_access_step, 0)
        score += min(access_age / 4.0, 35.0)  # Older untouched blocks slowly become more disposable over time
        score -= max(block.eviction_risk_score(current_step), 0.0) / 40.0  # Global eviction risk subtracts score to keep semantically important blocks safe
        return score

    def choose_victim(
        self,
        blocks: list[MemoryIntent],
        capacity_bytes: int,
        current_step: int,
    ) -> MemoryIntent | None:
        del capacity_bytes
        if not blocks:
            return None
        non_pinned = [block for block in blocks if not block.pin_requested]
        candidates = non_pinned if non_pinned else blocks
        return max(
            candidates,
            key=lambda block: (self.eviction_score(block, current_step), block.size_bytes, block.object_id),
        )

    def explain_victim_choice(
        self,
        victim: MemoryIntent,
        candidates: list[MemoryIntent],
        current_step: int,
    ) -> str:
        protected = [
            block.object_id
            for block in candidates
            if block.object_id != victim.object_id and block.eviction_risk_score(current_step) > 250.0
        ]
        reasons = []
        if victim.phase == Phase.DONE:
            reasons.append("DONE phase")
        if victim.priority == Priority.COLD:
            reasons.append("COLD")
        if victim.request_priority <= 25:
            reasons.append("low priority")
        if victim.recompute_ok:
            reasons.append("recompute-friendly")
        if victim.compression_ok:
            reasons.append("compressible")
        if victim.is_draft and not victim.is_committed:
            reasons.append("uncommitted draft")
        if victim.expected_reuse_window_tokens is not None and victim.expected_reuse_window_tokens >= 32:
            reasons.append("long reuse window")
        summary = ", ".join(reasons) if reasons else "lowest semantic protection score"
        if protected:
            return (
                f"Selected {victim.object_id} because it is {summary}. "
                f"Avoided {protected[0]} because it is more urgent or more expensive to evict."
            )
        return f"Selected {victim.object_id} because it is {summary}."


class DeadlineAwarePolicy(IntentAwarePolicy):
    def __init__(self) -> None:
        super().__init__(name="KVDeadline")

    def eviction_score(self, block: MemoryIntent, current_step: int) -> float:
        """Higher score means the block is a better eviction candidate."""
        score = super().eviction_score(block, current_step)
        risk = block.eviction_risk_score(current_step)

        # Near-deadline blocks should be heavily protected.
        if block.deadline_us is not None:
            if block.deadline_us <= 1_000:
                score -= 320.0  # Extremely near deadlines get a large negative term so they almost never become victims
            elif block.deadline_us <= 5_000:
                score -= 140.0  # Moderately near deadlines still receive strong protection against eviction
            else:
                score -= 25.0  # Even relaxed deadlines shave score because time-bounded work should not look purely cold

        # Explicit slack is even stronger than raw deadline when available.
        if block.slack_us is not None:
            if block.slack_us <= 500:
                score -= 260.0  # Tiny slack means almost no room for miss recovery, so the block is heavily protected
            elif block.slack_us <= 2_000:
                score -= 120.0  # Narrow slack windows still need substantial protection, though less absolute than imminent misses

        if block.request_priority >= 80:
            score -= 90.0  # High-priority requests surrender score so background work gives way before interactive work
        if block.recompute_cost_us is not None and block.recompute_cost_us >= 4_000:
            score -= 80.0  # High recompute cost means eviction would be expensive, so subtract score to discourage it
        if block.phase == Phase.DECODE:
            score -= 110.0  # Decode-phase state is latency-sensitive, so it receives an extra protection term
        if block.priority == Priority.DECODE_CRITICAL:
            score -= 400.0  # Decode-critical priority gets a large negative term so it dominates over generic coldness signals

        # Low-risk blocks become the preferred victims.
        score -= risk / 18.0  # The aggregate risk score subtracts from eviction score to reflect deadline, priority, and recompute danger
        if block.phase == Phase.DONE:
            score += 40.0  # DONE blocks regain some positive score because post-request state should still drain out first
        if block.priority == Priority.COLD and block.deadline_us is None:
            score += 35.0  # Deadline-free cold blocks are intentionally nudged upward as preferred capacity relief
        return score

    def should_prefetch(self, block: MemoryIntent, current_step: int) -> bool:
        del current_step
        if not block.prefetch_ok or block.current_tier == Tier.HBM:
            return False
        urgent_deadline = block.deadline_us is not None and block.deadline_us <= 5_000
        urgent_slack = block.slack_us is not None and block.slack_us <= 2_000
        near_reuse = (
            block.expected_reuse_window_tokens is not None and block.expected_reuse_window_tokens <= 8
        )
        important = block.priority in {Priority.HOT, Priority.DECODE_CRITICAL} or block.phase == Phase.DECODE
        return important and (urgent_deadline or urgent_slack or near_reuse)

    def explain_victim_choice(
        self,
        victim: MemoryIntent,
        candidates: list[MemoryIntent],
        current_step: int,
    ) -> str:
        protected = [
            block
            for block in candidates
            if block.object_id != victim.object_id and block.eviction_risk_score(current_step) > 250.0
        ]
        reasons = []
        if victim.priority == Priority.COLD:
            reasons.append("COLD")
        if victim.phase == Phase.DONE:
            reasons.append("DONE phase")
        if victim.request_priority <= 25:
            reasons.append("low request priority")
        if victim.deadline_us is None:
            reasons.append("no deadline")
        if victim.slack_us is None:
            reasons.append("no slack protection")
        if victim.recompute_ok:
            reasons.append("recompute-friendly")
        if victim.compression_ok:
            reasons.append("spillable/compressible")
        if victim.expected_reuse_window_tokens is not None and victim.expected_reuse_window_tokens >= 32:
            reasons.append("long reuse window")
        reason_text = ", ".join(reasons) if reasons else "lowest deadline protection"
        if protected:
            avoided = protected[0]
            return (
                f"Selected {victim.object_id} because it is {reason_text}. "
                f"Avoided {avoided.object_id} because it is {avoided.priority}, "
                f"phase {avoided.phase}, and near a decode deadline."
            )
        return f"Selected {victim.object_id} because it is {reason_text}."
