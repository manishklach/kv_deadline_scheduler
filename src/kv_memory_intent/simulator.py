"""Simulator and synthetic workload generation."""

from __future__ import annotations

import json
import random
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .events import MemoryIntentEvent
from .metrics import percentile
from .policies import (
    DeadlineAwarePolicy,
    HotColdPolicy,
    IntentAwarePolicy,
    LRUPolicy,
    PlacementPolicy,
    PredictiveHotnessPolicy,
)
from .schema import EventType, MemoryIntent, ObjectType, Phase, Priority, Tier

WorkloadProfile = Literal[
    "balanced",
    "deadline_pressure",
    "rag_mixed_priority",
    "speculative_decode",
    "long_context_extreme",
]


@dataclass(slots=True)
class SimulationResult:
    policy_name: str
    total_blocks: int
    total_steps: int
    hbm_capacity_bytes: int
    dram_capacity_bytes: int
    peak_hbm_demand_bytes: int
    actual_peak_hbm_used_bytes: int
    hbm_bytes_saved: int
    spill_count: int
    prefetch_count: int
    miss_count: int
    eviction_count: int
    total_latency_us: int
    p50_latency_us: float
    p95_latency_us: float
    p99_latency_us: float
    decode_critical_misses: int
    decode_critical_miss_rate: float
    decode_critical_evictions: int
    final_hbm_used_bytes: int
    final_dram_used_bytes: int

    def to_dict(self) -> dict[str, int | float | str]:
        return {
            "policy_name": self.policy_name,
            "total_blocks": self.total_blocks,
            "total_steps": self.total_steps,
            "hbm_capacity_bytes": self.hbm_capacity_bytes,
            "dram_capacity_bytes": self.dram_capacity_bytes,
            "peak_hbm_demand_bytes": self.peak_hbm_demand_bytes,
            "actual_peak_hbm_used_bytes": self.actual_peak_hbm_used_bytes,
            "hbm_bytes_saved": self.hbm_bytes_saved,
            "spill_count": self.spill_count,
            "prefetch_count": self.prefetch_count,
            "miss_count": self.miss_count,
            "eviction_count": self.eviction_count,
            "total_latency_us": self.total_latency_us,
            "p50_latency_us": self.p50_latency_us,
            "p95_latency_us": self.p95_latency_us,
            "p99_latency_us": self.p99_latency_us,
            "decode_critical_misses": self.decode_critical_misses,
            "decode_critical_miss_rate": self.decode_critical_miss_rate,
            "decode_critical_evictions": self.decode_critical_evictions,
            "final_hbm_used_bytes": self.final_hbm_used_bytes,
            "final_dram_used_bytes": self.final_dram_used_bytes,
        }


class KVMemorySimulator:
    def __init__(
        self,
        policy: PlacementPolicy,
        hbm_capacity_bytes: int,
        dram_capacity_bytes: int,
        miss_penalty_us: int = 5_000,
        spill_latency_us: int = 200,
        prefetch_latency_us: int = 100,
        base_step_latency_us: int = 50,
    ) -> None:
        self.policy = policy
        self.hbm_capacity_bytes = hbm_capacity_bytes
        self.dram_capacity_bytes = dram_capacity_bytes
        self.miss_penalty_us = miss_penalty_us
        self.spill_latency_us = spill_latency_us
        self.prefetch_latency_us = prefetch_latency_us
        self.base_step_latency_us = base_step_latency_us

        self.live_blocks: dict[str, MemoryIntent] = {}
        self.hbm_blocks: set[str] = set()
        self.dram_blocks: set[str] = set()
        self.latencies: list[int] = []
        self.decision_log: list[dict[str, object]] = []
        self.spill_count = 0
        self.prefetch_count = 0
        self.miss_count = 0
        self.eviction_count = 0
        self.decode_critical_misses = 0
        self.decode_critical_evictions = 0
        self.peak_hbm_demand_bytes = 0
        self.actual_peak_hbm_used_bytes = 0
        self._last_decay_step: int = -1

    def _used_bytes(self, ids: Iterable[str]) -> int:
        return sum(self.live_blocks[object_id].size_bytes for object_id in ids if object_id in self.live_blocks)

    def _hbm_used(self) -> int:
        return self._used_bytes(self.hbm_blocks)

    def _dram_used(self) -> int:
        return self._used_bytes(self.dram_blocks)

    def _record_usage(self) -> None:
        self.actual_peak_hbm_used_bytes = max(self.actual_peak_hbm_used_bytes, self._hbm_used())

    def _log_decision(
        self,
        step: int,
        action: str,
        victim: MemoryIntent,
        candidates: list[MemoryIntent],
        reason: str,
        avoided_decode_critical: bool,
    ) -> None:
        self.decision_log.append(
            {
                "step": step,
                "action": action,
                "policy": self.policy.name,
                "victim_object_id": victim.object_id,
                "victim_priority": victim.priority.value,
                "victim_phase": victim.phase.value,
                "victim_request_priority": victim.request_priority,
                "victim_deadline_us": victim.deadline_us,
                "reason": reason,
                "avoided_decode_critical": avoided_decode_critical,
            }
        )

    def write_decision_log(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as handle:
            for record in self.decision_log:
                handle.write(json.dumps(record, sort_keys=True) + "\n")

    def _move_to_hbm(self, block: MemoryIntent, current_step: int) -> int:
        block.current_tier = Tier.HBM
        self.live_blocks[block.object_id] = block
        self.hbm_blocks.add(block.object_id)
        self.dram_blocks.discard(block.object_id)
        added_latency = self._ensure_hbm_capacity(current_step)
        self._record_usage()
        return added_latency

    def _ensure_hbm_capacity(self, current_step: int) -> int:
        added_latency = 0
        while self._hbm_used() > self.hbm_capacity_bytes:
            candidates = [self.live_blocks[object_id] for object_id in self.hbm_blocks if object_id in self.live_blocks]
            victim = self.policy.choose_victim(candidates, self.hbm_capacity_bytes, current_step)
            if victim is None:
                break
            reason = self.policy.explain_victim_choice(victim, candidates, current_step)
            avoided_decode_critical = any(
                block.object_id != victim.object_id and block.is_decode_critical() for block in candidates
            )
            self.eviction_count += 1
            if victim.is_decode_critical():
                self.decode_critical_evictions += 1
            self.hbm_blocks.discard(victim.object_id)
            fallback_tiers = [tier for tier in victim.allowed_tiers if tier != Tier.HBM]
            target_tier = fallback_tiers[0] if fallback_tiers else None
            if target_tier == Tier.DRAM and self._dram_used() + victim.size_bytes <= self.dram_capacity_bytes:
                victim.current_tier = Tier.DRAM
                self.live_blocks[victim.object_id] = victim
                self.dram_blocks.add(victim.object_id)
                self.spill_count += 1
                added_latency += self.spill_latency_us
                self._log_decision(current_step, "spill", victim, candidates, reason, avoided_decode_critical)
            else:
                victim.current_tier = target_tier or Tier.NVME
                self.live_blocks[victim.object_id] = victim
                self.dram_blocks.discard(victim.object_id)
                self._log_decision(current_step, "evict", victim, candidates, reason, avoided_decode_critical)
        self._record_usage()
        return added_latency

    def _merge_intent(
        self,
        existing: MemoryIntent,
        incoming: MemoryIntent,
        fields: set[str] | None = None,
    ) -> MemoryIntent:
        if fields is None:
            fields = {
                "request_id",
                "block_id",
                "object_type",
                "phase",
                "priority",
                "allowed_tiers",
                "current_tier",
                "size_bytes",
                "request_priority",
                "recency_score",
                "deadline_us",
                "slack_us",
                "arrival_step",
                "target_decode_step",
                "expected_reuse_window_tokens",
                "recompute_cost_us",
                "spill_cost_us",
                "compression_ok",
                "recompute_ok",
                "prefetch_ok",
                "pin_requested",
                "is_draft",
                "is_committed",
                "created_step",
                "last_access_step",
            }
        updates: dict[str, object] = {}
        for field in fields:
            value = getattr(incoming, field)
            if field == "allowed_tiers":
                value = set(value)
            updates[field] = value
        return existing.copy_with(**updates)

    def run(self, events: list[MemoryIntentEvent]) -> SimulationResult:
        for event in events:
            latency = self.base_step_latency_us
            intent = event.intent.copy_with()
            existing = self.live_blocks.get(intent.object_id)
            if existing is not None:
                merge_fields = None
                if event.event_type == EventType.MARKED_DECODE_CRITICAL:
                    merge_fields = {
                        "priority",
                        "phase",
                        "pin_requested",
                        "deadline_us",
                        "slack_us",
                        "target_decode_step",
                        "expected_reuse_window_tokens",
                        "request_priority",
                        "recency_score",
                    }
                elif event.event_type == EventType.MARKED_COLD:
                    merge_fields = {
                        "priority",
                        "phase",
                        "deadline_us",
                        "slack_us",
                        "compression_ok",
                        "recompute_ok",
                        "prefetch_ok",
                        "recency_score",
                    }
                elif event.event_type == EventType.ACCESSED:
                    merge_fields = {
                        "last_access_step",
                        "recency_score",
                        "phase",
                        "priority",
                        "deadline_us",
                        "slack_us",
                        "target_decode_step",
                        "expected_reuse_window_tokens",
                        "pin_requested",
                        "prefetch_ok",
                    }
                elif event.event_type == EventType.COMMITTED:
                    merge_fields = {"is_committed", "is_draft"}
                intent = self._merge_intent(existing, intent, fields=merge_fields)

            if event.event_type == EventType.ALLOCATED:
                self.live_blocks[intent.object_id] = intent
                self.peak_hbm_demand_bytes = max(
                    self.peak_hbm_demand_bytes,
                    self._hbm_used() + (intent.size_bytes if intent.current_tier == Tier.HBM else 0),
                )
                if intent.current_tier == Tier.HBM:
                    self.hbm_blocks.add(intent.object_id)
                    latency += self._ensure_hbm_capacity(event.step)
                elif intent.current_tier == Tier.DRAM:
                    self.dram_blocks.add(intent.object_id)
                self._record_usage()
            elif event.event_type == EventType.ACCESSED:
                if intent.object_id not in self.live_blocks:
                    self.live_blocks[intent.object_id] = intent
                block = self.live_blocks[intent.object_id].copy_with(
                    last_access_step=event.step,
                    recency_score=max(intent.recency_score, 1.0),
                    phase=intent.phase,
                    priority=intent.priority,
                    deadline_us=intent.deadline_us,
                    slack_us=intent.slack_us,
                    target_decode_step=intent.target_decode_step,
                    expected_reuse_window_tokens=intent.expected_reuse_window_tokens,
                    pin_requested=intent.pin_requested,
                    prefetch_ok=intent.prefetch_ok,
                )
                self.live_blocks[intent.object_id] = block
                if block.object_id not in self.hbm_blocks:
                    self.miss_count += 1
                    latency += self.miss_penalty_us
                    if block.is_decode_critical():
                        self.decode_critical_misses += 1
                    latency += self._move_to_hbm(block, event.step)
                else:
                    self._record_usage()
            elif event.event_type == EventType.MARKED_DECODE_CRITICAL:
                if existing is None:
                    self.live_blocks[intent.object_id] = intent.copy_with(
                        priority=Priority.DECODE_CRITICAL,
                        pin_requested=True,
                    )
                else:
                    self.live_blocks[intent.object_id] = existing.copy_with(
                        priority=Priority.DECODE_CRITICAL,
                        phase=intent.phase,
                        pin_requested=True,
                        deadline_us=intent.deadline_us,
                        slack_us=intent.slack_us,
                        target_decode_step=intent.target_decode_step,
                        expected_reuse_window_tokens=intent.expected_reuse_window_tokens,
                        request_priority=intent.request_priority,
                        recency_score=intent.recency_score,
                    )
            elif event.event_type == EventType.MARKED_COLD:
                if existing is not None:
                    self.live_blocks[intent.object_id] = existing.copy_with(
                        priority=Priority.COLD,
                        phase=intent.phase,
                        deadline_us=intent.deadline_us,
                        slack_us=intent.slack_us,
                        compression_ok=intent.compression_ok,
                        recompute_ok=intent.recompute_ok,
                        prefetch_ok=intent.prefetch_ok,
                        recency_score=intent.recency_score,
                    )
            elif event.event_type == EventType.COMMITTED:
                if existing is not None:
                    self.live_blocks[intent.object_id] = existing.copy_with(is_committed=True, is_draft=False)
            elif event.event_type == EventType.SPILLED:
                if existing is not None and Tier.DRAM in existing.allowed_tiers:
                    self.hbm_blocks.discard(existing.object_id)
                    self.dram_blocks.add(existing.object_id)
                    updated = existing.copy_with(current_tier=Tier.DRAM)
                    self.live_blocks[existing.object_id] = updated
                    self.spill_count += 1
                    latency += self.spill_latency_us
            elif event.event_type == EventType.PREFETCHED:
                block = self.live_blocks.get(intent.object_id)
                if block is not None and block.object_id not in self.hbm_blocks:
                    block = self._merge_intent(block, intent)
                    self.live_blocks[block.object_id] = block
                    should_prefetch = self.policy.should_prefetch(block, event.step)
                    if should_prefetch:
                        self.prefetch_count += 1
                        latency += self.prefetch_latency_us
                        latency += self._move_to_hbm(block, event.step)
                        self._log_decision(
                            event.step,
                            "prefetch",
                            block,
                            [block],
                            f"Prefetched {block.object_id} because it is urgent and prefetchable under {self.policy.name}.",
                            avoided_decode_critical=False,
                        )
            elif event.event_type == EventType.EVICTED:
                if existing is not None:
                    self.hbm_blocks.discard(existing.object_id)
                    self.dram_blocks.discard(existing.object_id)
                    if existing.is_decode_critical():
                        self.decode_critical_evictions += 1
                    self.eviction_count += 1
            elif event.event_type == EventType.FREED:
                self.live_blocks.pop(intent.object_id, None)
                self.hbm_blocks.discard(intent.object_id)
                self.dram_blocks.discard(intent.object_id)

            if event.step != self._last_decay_step:
                for object_id, block in list(self.live_blocks.items()):
                    updated_score = max(block.recency_score - 0.03, 0.0)
                    self.live_blocks[object_id] = block.copy_with(recency_score=updated_score)
                self._last_decay_step = event.step

            self.latencies.append(latency)

        total_blocks = len({event.intent.object_id for event in events})
        total_latency = sum(self.latencies)
        decode_critical_miss_rate = min(self.decode_critical_misses / max(total_blocks, 1), 1.0)
        return SimulationResult(
            policy_name=self.policy.name,
            total_blocks=total_blocks,
            total_steps=max((event.step for event in events), default=0) + 1,
            hbm_capacity_bytes=self.hbm_capacity_bytes,
            dram_capacity_bytes=self.dram_capacity_bytes,
            peak_hbm_demand_bytes=self.peak_hbm_demand_bytes,
            actual_peak_hbm_used_bytes=self.actual_peak_hbm_used_bytes,
            hbm_bytes_saved=max(self.peak_hbm_demand_bytes - self.actual_peak_hbm_used_bytes, 0),
            spill_count=self.spill_count,
            prefetch_count=self.prefetch_count,
            miss_count=self.miss_count,
            eviction_count=self.eviction_count,
            total_latency_us=total_latency,
            p50_latency_us=percentile(self.latencies, 50),
            p95_latency_us=percentile(self.latencies, 95),
            p99_latency_us=percentile(self.latencies, 99),
            decode_critical_misses=self.decode_critical_misses,
            decode_critical_miss_rate=decode_critical_miss_rate,
            decode_critical_evictions=self.decode_critical_evictions,
            final_hbm_used_bytes=self._hbm_used(),
            final_dram_used_bytes=self._dram_used(),
        )


def _profile_settings(profile: WorkloadProfile) -> dict[str, float]:
    defaults: dict[str, float] = {
        "long_context_fraction": 0.3,
        "draft_fraction": 0.2,
        "high_priority_fraction": 0.2,
        "deadline_ratio": 0.25,
        "reuse_scale": 1.0,
    }
    if profile == "deadline_pressure":
        defaults.update(
            long_context_fraction=0.4,
            high_priority_fraction=0.45,
            deadline_ratio=0.65,
            reuse_scale=0.7,
        )
    elif profile == "rag_mixed_priority":
        defaults.update(
            long_context_fraction=0.5,
            high_priority_fraction=0.15,
            deadline_ratio=0.2,
            reuse_scale=1.6,
        )
    elif profile == "speculative_decode":
        defaults.update(
            draft_fraction=0.45,
            deadline_ratio=0.3,
            reuse_scale=0.9,
        )
    elif profile == "long_context_extreme":
        defaults.update(
            long_context_fraction=0.75,
            high_priority_fraction=0.1,
            deadline_ratio=0.15,
            reuse_scale=2.8,
        )
    return defaults


def generate_synthetic_kv_workload(
    num_requests: int,
    blocks_per_request: int,
    block_size_bytes: int,
    decode_steps: int,
    long_context_fraction: float = 0.3,
    draft_fraction: float = 0.2,
    high_priority_fraction: float = 0.2,
    seed: int = 42,
    profile: WorkloadProfile = "balanced",
) -> list[MemoryIntentEvent]:
    rng = random.Random(seed)
    settings = _profile_settings(profile)
    long_context_fraction = settings["long_context_fraction"]
    draft_fraction = settings["draft_fraction"]
    high_priority_fraction = settings["high_priority_fraction"]
    deadline_ratio = settings["deadline_ratio"]
    reuse_scale = settings["reuse_scale"]

    events: list[MemoryIntentEvent] = []
    requests: list[dict[str, object]] = []
    step = 0

    for request_index in range(num_requests):
        request_id = f"req-{request_index:03d}"
        is_high = request_index < max(1, int(num_requests * high_priority_fraction))
        is_long = request_index < max(1, int(num_requests * long_context_fraction))
        request_priority = 92 if is_high else rng.randint(10, 60)
        block_count = blocks_per_request * (3 if profile == "long_context_extreme" and is_long else 2 if is_long else 1)
        block_ids: list[str] = []
        hot_span = 3 if is_high or profile == "deadline_pressure" else 2

        for block_id in range(block_count):
            is_hot_tail = block_id >= block_count - hot_span
            priority = Priority.WARM if not is_hot_tail else Priority.HOT
            base_deadline = 900 if is_high and is_hot_tail else 10_000
            if profile == "deadline_pressure" and is_hot_tail:
                base_deadline = 700
            elif profile == "rag_mixed_priority" and not is_high:
                base_deadline = 15_000
            elif profile == "long_context_extreme" and not is_hot_tail:
                base_deadline = None  # type: ignore[assignment]
            reuse_window = 2 if is_hot_tail else int((24 + block_id) * reuse_scale)
            recompute_cost = 5_000 if is_hot_tail else 200
            is_draft = (
                block_id < max(1, int(block_count * draft_fraction))
                and profile in {"speculative_decode", "balanced"}
                and not is_high
            )
            intent = MemoryIntent(
                object_id=f"{request_id}:block:{block_id}",
                request_id=request_id,
                block_id=block_id,
                object_type=ObjectType.KV_CACHE,
                phase=Phase.PREFILL,
                priority=priority,
                allowed_tiers={Tier.HBM, Tier.DRAM},
                current_tier=Tier.HBM,
                size_bytes=block_size_bytes,
                request_priority=request_priority,
                recency_score=0.15 if priority == Priority.WARM else 0.7,
                deadline_us=base_deadline,
                slack_us=(base_deadline - 200) if isinstance(base_deadline, int) else None,
                arrival_step=step,
                target_decode_step=step + block_count + max(2, block_id // 2),
                expected_reuse_window_tokens=reuse_window,
                recompute_cost_us=recompute_cost,
                spill_cost_us=200,
                compression_ok=not is_hot_tail,
                recompute_ok=not is_hot_tail,
                prefetch_ok=not is_hot_tail,
                pin_requested=False,
                is_draft=is_draft,
                is_committed=False,
                created_step=step,
                last_access_step=step,
            )
            events.append(
                MemoryIntentEvent(
                    step=step,
                    event_type=EventType.ALLOCATED,
                    intent=intent,
                    reason=f"initial kv allocation ({profile})",
                )
            )
            block_ids.append(intent.object_id)
            step += 1

        requests.append(
            {
                "request_id": request_id,
                "block_ids": block_ids,
                "request_priority": request_priority,
                "is_high": is_high,
                "hot_span": hot_span,
            }
        )

    total_requests = len(requests)
    for decode_step in range(decode_steps):
        active = requests[decode_step % total_requests]
        block_ids = list(active["block_ids"])
        is_high = bool(active["is_high"])
        hot_span = int(active["hot_span"])
        current_hot = block_ids[-hot_span:]
        cold_candidates = block_ids[:-hot_span]

        for offset, object_id in enumerate(current_hot):
            deadline_us = 700 if (profile == "deadline_pressure" or is_high) else 2_500
            slack_us = 250 if profile == "deadline_pressure" else 1_500 if is_high else 3_500
            intent = MemoryIntent(
                object_id=object_id,
                request_id=str(active["request_id"]),
                block_id=int(object_id.rsplit(":", 1)[-1]),
                object_type=ObjectType.KV_CACHE,
                phase=Phase.DECODE,
                priority=Priority.DECODE_CRITICAL,
                allowed_tiers={Tier.HBM, Tier.DRAM},
                current_tier=Tier.HBM,
                size_bytes=block_size_bytes,
                request_priority=int(active["request_priority"]),
                recency_score=1.0 - (offset * 0.1),
                deadline_us=deadline_us,
                slack_us=slack_us,
                arrival_step=0,
                target_decode_step=step + offset,
                expected_reuse_window_tokens=1 + offset,
                recompute_cost_us=6_000 if is_high or profile == "deadline_pressure" else 2_000,
                spill_cost_us=250,
                prefetch_ok=False,
                pin_requested=True,
                is_draft=False,
                is_committed=True,
                created_step=0,
                last_access_step=step,
            )
            events.append(
                MemoryIntentEvent(
                    step=step,
                    event_type=EventType.MARKED_DECODE_CRITICAL,
                    intent=intent,
                    reason="decode hot set",
                )
            )
            step += 1
            events.append(
                MemoryIntentEvent(
                    step=step,
                    event_type=EventType.ACCESSED,
                    intent=intent,
                    reason="token decode access",
                )
            )
            step += 1

        if cold_candidates:
            stale_id = cold_candidates[decode_step % len(cold_candidates)]
            low_prio = max(int(active["request_priority"]) - (45 if profile == "rag_mixed_priority" else 20), 0)
            stale_intent = MemoryIntent(
                object_id=stale_id,
                request_id=str(active["request_id"]),
                block_id=int(stale_id.rsplit(":", 1)[-1]),
                object_type=ObjectType.KV_CACHE,
                phase=Phase.DONE if decode_step % 7 == 0 else Phase.VERIFY,
                priority=Priority.COLD,
                allowed_tiers={Tier.HBM, Tier.DRAM},
                current_tier=Tier.HBM,
                size_bytes=block_size_bytes,
                request_priority=low_prio,
                recency_score=0.0 if profile != "long_context_extreme" else 0.05,
                deadline_us=None if profile != "deadline_pressure" else int(6_000 / max(deadline_ratio, 0.1)),
                slack_us=None,
                arrival_step=0,
                target_decode_step=step + 512,
                expected_reuse_window_tokens=int(48 * reuse_scale),
                recompute_cost_us=80,
                spill_cost_us=100,
                compression_ok=True,
                recompute_ok=True,
                prefetch_ok=True,
                pin_requested=False,
                is_draft=profile == "speculative_decode" and decode_step % 2 == 0,
                is_committed=False,
                created_step=0,
                last_access_step=max(step - 20, 0),
            )
            events.append(
                MemoryIntentEvent(
                    step=step,
                    event_type=EventType.MARKED_COLD,
                    intent=stale_intent,
                    reason="aging old kv block",
                )
            )
            step += 1

            if stale_intent.is_draft and decode_step % 5 == 0:
                commit_intent = stale_intent.copy_with(is_committed=True, is_draft=False)
                events.append(
                    MemoryIntentEvent(
                        step=step,
                        event_type=EventType.COMMITTED,
                        intent=commit_intent,
                        reason="draft accepted",
                    )
                )
                step += 1

            if decode_step % 5 == 0:
                prefetch_target = stale_intent.copy_with(
                    current_tier=Tier.DRAM,
                    prefetch_ok=True,
                    priority=Priority.HOT if is_high else Priority.WARM,
                    deadline_us=4_000 if is_high else None,
                    slack_us=1_200 if is_high else None,
                    expected_reuse_window_tokens=4 if profile != "long_context_extreme" else 12,
                )
                events.append(
                    MemoryIntentEvent(
                        step=step,
                        event_type=EventType.PREFETCHED,
                        intent=prefetch_target,
                        reason="anticipated reuse",
                    )
                )
                step += 1

    return events


def policy_from_name(name: str) -> PlacementPolicy:
    normalized = name.strip().lower()
    if normalized == "lru":
        return LRUPolicy()
    if normalized == "hotcold":
        return HotColdPolicy()
    if normalized == "predictive":
        return PredictiveHotnessPolicy()
    if normalized == "intent":
        return IntentAwarePolicy()
    if normalized == "deadline":
        return DeadlineAwarePolicy()
    raise ValueError(f"Unknown policy: {name}")
