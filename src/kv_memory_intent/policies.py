"""Placement policies for the simulator."""

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


class LRUPolicy(PlacementPolicy):
    name = "LRU"

    def choose_victim(
        self,
        blocks: list[MemoryIntent],
        capacity_bytes: int,
        current_step: int,
    ) -> MemoryIntent | None:
        if not blocks:
            return None
        return min(blocks, key=lambda block: (block.last_access_step, -block.size_bytes, block.object_id))


@dataclass(slots=True)
class IntentAwarePolicy(PlacementPolicy):
    name: str = "IntentAware"

    def eviction_score(self, block: MemoryIntent, current_step: int) -> float:
        score = 0.0
        priority_weight = {
            Priority.COLD: 100.0,
            Priority.WARM: 60.0,
            Priority.HOT: 20.0,
            Priority.DECODE_CRITICAL: -1000.0,
        }
        score += priority_weight[block.priority]
        if block.pin_requested:
            score -= 1000.0
        if block.phase == Phase.DONE:
            score += 100.0
        score += float(100 - block.request_priority)
        if block.expected_reuse_window_tokens is not None:
            score += block.expected_reuse_window_tokens / 10.0
        if block.recompute_ok:
            score += 25.0
        if block.compression_ok:
            score += 15.0
        if block.is_draft and not block.is_committed:
            score += 40.0
        if block.recompute_cost_us is not None:
            score -= block.recompute_cost_us / 200.0
        score -= block.recency_score * 50.0
        access_age = max(current_step - block.last_access_step, 0)
        score += min(access_age / 5.0, 30.0)
        return score

    def choose_victim(
        self,
        blocks: list[MemoryIntent],
        capacity_bytes: int,
        current_step: int,
    ) -> MemoryIntent | None:
        if not blocks:
            return None
        non_pinned = [block for block in blocks if not block.pin_requested]
        candidates = non_pinned if non_pinned else blocks
        return max(
            candidates,
            key=lambda block: (self.eviction_score(block, current_step), block.size_bytes, block.object_id),
        )


class DeadlineAwarePolicy(IntentAwarePolicy):
    def __init__(self) -> None:
        super().__init__(name="DeadlineAware")

    def eviction_score(self, block: MemoryIntent, current_step: int) -> float:
        score = super().eviction_score(block, current_step)
        if block.deadline_us is not None:
            if block.deadline_us <= 1_000:
                score -= 300.0
            elif block.deadline_us <= 5_000:
                score -= 120.0
            else:
                score -= 20.0
        elif block.priority == Priority.COLD:
            score += 25.0
        return score

    def should_prefetch(self, block: MemoryIntent, current_step: int) -> bool:
        if not block.prefetch_ok or block.current_tier == Tier.HBM:
            return False
        urgent_deadline = block.deadline_us is not None and block.deadline_us <= 5_000
        near_reuse = (
            block.expected_reuse_window_tokens is not None and block.expected_reuse_window_tokens <= 8
        )
        important = block.priority in {Priority.HOT, Priority.DECODE_CRITICAL}
        return important and (urgent_deadline or near_reuse)
