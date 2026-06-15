"""Simulator and synthetic workload generation."""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

from .events import MemoryIntentEvent
from .metrics import percentile
from .policies import DeadlineAwarePolicy, IntentAwarePolicy, LRUPolicy, PlacementPolicy
from .schema import EventType, MemoryIntent, ObjectType, Phase, Priority, Tier


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
        self.spill_count = 0
        self.prefetch_count = 0
        self.miss_count = 0
        self.eviction_count = 0
        self.decode_critical_misses = 0
        self.decode_critical_evictions = 0
        self.peak_hbm_demand_bytes = 0
        self.actual_peak_hbm_used_bytes = 0

    def _used_bytes(self, ids: Iterable[str]) -> int:
        return sum(self.live_blocks[object_id].size_bytes for object_id in ids if object_id in self.live_blocks)

    def _hbm_used(self) -> int:
        return self._used_bytes(self.hbm_blocks)

    def _dram_used(self) -> int:
        return self._used_bytes(self.dram_blocks)

    def _record_usage(self) -> None:
        self.actual_peak_hbm_used_bytes = max(self.actual_peak_hbm_used_bytes, self._hbm_used())

    def _move_to_hbm(self, block: MemoryIntent, current_step: int) -> int:
        block.current_tier = Tier.HBM
        self.live_blocks[block.object_id] = block
        self.hbm_blocks.add(block.object_id)
        self.dram_blocks.discard(block.object_id)
        self._ensure_hbm_capacity(current_step)
        self._record_usage()
        return 0

    def _ensure_hbm_capacity(self, current_step: int) -> int:
        added_latency = 0
        while self._hbm_used() > self.hbm_capacity_bytes:
            victims = [self.live_blocks[object_id] for object_id in self.hbm_blocks if object_id in self.live_blocks]
            victim = self.policy.choose_victim(victims, self.hbm_capacity_bytes, current_step)
            if victim is None:
                break
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
            else:
                victim.current_tier = target_tier or Tier.NVME
                self.live_blocks[victim.object_id] = victim
                self.dram_blocks.discard(victim.object_id)
        self._record_usage()
        return added_latency

    def _merge_intent(self, existing: MemoryIntent, incoming: MemoryIntent) -> MemoryIntent:
        return existing.copy_with(
            request_id=incoming.request_id,
            block_id=incoming.block_id,
            object_type=incoming.object_type,
            phase=incoming.phase,
            priority=incoming.priority,
            allowed_tiers=set(incoming.allowed_tiers),
            current_tier=incoming.current_tier,
            size_bytes=incoming.size_bytes,
            request_priority=incoming.request_priority,
            recency_score=incoming.recency_score,
            deadline_us=incoming.deadline_us,
            expected_reuse_window_tokens=incoming.expected_reuse_window_tokens,
            recompute_cost_us=incoming.recompute_cost_us,
            spill_cost_us=incoming.spill_cost_us,
            compression_ok=incoming.compression_ok,
            recompute_ok=incoming.recompute_ok,
            prefetch_ok=incoming.prefetch_ok,
            pin_requested=incoming.pin_requested,
            is_draft=incoming.is_draft,
            is_committed=incoming.is_committed,
            created_step=incoming.created_step,
            last_access_step=incoming.last_access_step,
        )

    def run(self, events: list[MemoryIntentEvent]) -> SimulationResult:
        for event in events:
            latency = self.base_step_latency_us
            intent = event.intent.copy_with()
            existing = self.live_blocks.get(intent.object_id)
            if existing is not None:
                # Keep the latest semantic metadata without lossy enum serialization.
                intent = self._merge_intent(existing, intent)

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
                        expected_reuse_window_tokens=intent.expected_reuse_window_tokens,
                        request_priority=intent.request_priority,
                        recency_score=intent.recency_score,
                    )
            elif event.event_type == EventType.MARKED_COLD:
                if existing is not None:
                    self.live_blocks[intent.object_id] = existing.copy_with(
                        priority=Priority.COLD,
                        phase=intent.phase,
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
                    self.live_blocks[existing.object_id] = existing.copy_with(current_tier=Tier.DRAM)
                    self.spill_count += 1
                    latency += self.spill_latency_us
            elif event.event_type == EventType.PREFETCHED:
                if existing is not None and existing.object_id not in self.hbm_blocks:
                    should_prefetch = self.policy.should_prefetch(existing, event.step)
                    if should_prefetch:
                        self.prefetch_count += 1
                        latency += self.prefetch_latency_us
                        latency += self._move_to_hbm(existing, event.step)
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

            for object_id, block in list(self.live_blocks.items()):
                updated_score = max(block.recency_score - 0.03, 0.0)
                self.live_blocks[object_id] = block.copy_with(recency_score=updated_score)

            self.latencies.append(latency)

        total_latency = sum(self.latencies)
        return SimulationResult(
            policy_name=self.policy.name,
            total_blocks=len({event.intent.object_id for event in events}),
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
            decode_critical_evictions=self.decode_critical_evictions,
            final_hbm_used_bytes=self._hbm_used(),
            final_dram_used_bytes=self._dram_used(),
        )


def generate_synthetic_kv_workload(
    num_requests: int,
    blocks_per_request: int,
    block_size_bytes: int,
    decode_steps: int,
    long_context_fraction: float = 0.3,
    draft_fraction: float = 0.2,
    high_priority_fraction: float = 0.2,
    seed: int = 42,
) -> list[MemoryIntentEvent]:
    rng = random.Random(seed)
    events: list[MemoryIntentEvent] = []
    requests: list[dict[str, object]] = []
    step = 0

    for request_index in range(num_requests):
        request_id = f"req-{request_index:03d}"
        is_high = request_index < max(1, int(num_requests * high_priority_fraction))
        is_long = request_index < max(1, int(num_requests * long_context_fraction))
        request_priority = 90 if is_high else rng.randint(20, 60)
        block_count = blocks_per_request * (2 if is_long else 1)
        block_ids: list[str] = []
        hot_span = 3 if is_high else 2
        for block_id in range(block_count):
            priority = Priority.WARM if block_id < block_count - hot_span else Priority.HOT
            phase = Phase.PREFILL
            intent = MemoryIntent(
                object_id=f"{request_id}:block:{block_id}",
                request_id=request_id,
                block_id=block_id,
                object_type=ObjectType.KV_CACHE,
                phase=phase,
                priority=priority,
                allowed_tiers={Tier.HBM, Tier.DRAM},
                current_tier=Tier.HBM,
                size_bytes=block_size_bytes,
                request_priority=request_priority,
                recency_score=0.2 if priority == Priority.WARM else 0.6,
                deadline_us=800 if is_high and block_id >= block_count - hot_span else 9_000,
                expected_reuse_window_tokens=2 if block_id >= block_count - hot_span else 24 + block_id,
                recompute_cost_us=4_000 if block_id >= block_count - hot_span else 300,
                spill_cost_us=200,
                compression_ok=block_id < block_count - hot_span,
                recompute_ok=block_id < block_count - hot_span,
                prefetch_ok=block_id < block_count - hot_span,
                pin_requested=False,
                is_draft=block_id < max(1, int(block_count * draft_fraction)) and not is_high,
                is_committed=False,
                created_step=step,
                last_access_step=step,
            )
            events.append(
                MemoryIntentEvent(
                    step=step,
                    event_type=EventType.ALLOCATED,
                    intent=intent,
                    reason="initial kv allocation",
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
                deadline_us=800 if is_high else 2_500,
                expected_reuse_window_tokens=1 + offset,
                recompute_cost_us=5_000 if is_high else 2_000,
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
                request_priority=max(int(active["request_priority"]) - 20, 0),
                recency_score=0.0,
                deadline_us=None,
                expected_reuse_window_tokens=48,
                recompute_cost_us=100,
                spill_cost_us=100,
                compression_ok=True,
                recompute_ok=True,
                prefetch_ok=True,
                pin_requested=False,
                is_draft=not is_high and decode_step % 3 == 0,
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

            if stale_intent.is_draft and decode_step % 9 == 0:
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
                    expected_reuse_window_tokens=4,
                    deadline_us=4_000 if is_high else 7_000,
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
    if normalized == "intent":
        return IntentAwarePolicy()
    if normalized == "deadline":
        return DeadlineAwarePolicy()
    raise ValueError(f"Unknown policy: {name}")
