"""Import external request traces into approximate MemoryIntentEvent sequences."""

from __future__ import annotations

from math import ceil

from .events import MemoryIntentEvent
from .kv_estimator import ModelKVConfig, estimate_request_kv_bytes
from .request_trace import RequestTraceRecord
from .schema import EventType, MemoryIntent, ObjectType, Phase, Priority, Tier


def request_trace_to_intent_events(
    records: list[RequestTraceRecord],
    model_config: ModelKVConfig,
    block_size_bytes: int = 1 * 1024 * 1024,
    decode_block_tokens: int = 16,
    max_blocks_per_request: int | None = None,
) -> list[MemoryIntentEvent]:
    if block_size_bytes <= 0:
        raise ValueError("block_size_bytes must be > 0")
    if decode_block_tokens <= 0:
        raise ValueError("decode_block_tokens must be > 0")
    if max_blocks_per_request is not None and max_blocks_per_request <= 0:
        raise ValueError("max_blocks_per_request must be > 0 when provided")

    events: list[MemoryIntentEvent] = []
    current_step = 0

    for record in sorted(records, key=lambda item: (item.arrival_ms, item.request_id)):
        total_kv_bytes = estimate_request_kv_bytes(
            model_config,
            prompt_tokens=record.prompt_tokens,
            generated_tokens=record.generated_tokens,
        )
        num_blocks = max(1, ceil(total_kv_bytes / block_size_bytes))
        logical_block_size = block_size_bytes
        if max_blocks_per_request is not None and num_blocks > max_blocks_per_request:
            num_blocks = max_blocks_per_request
            logical_block_size = ceil(total_kv_bytes / num_blocks)

        decode_hot_blocks = min(max(1, ceil(max(record.generated_tokens, 1) / decode_block_tokens)), num_blocks)
        for block_id in range(num_blocks):
            is_hot_tail = block_id >= num_blocks - decode_hot_blocks
            age_fraction = block_id / max(num_blocks - 1, 1)
            priority = Priority.HOT if is_hot_tail else Priority.WARM if age_fraction > 0.5 else Priority.COLD
            phase = Phase.PREFILL
            deadline_us = record.deadline_ms * 1000 if record.deadline_ms is not None else None
            recompute_ok = not is_hot_tail
            compression_ok = not is_hot_tail
            expected_reuse = max(1, int((1.0 - age_fraction) * 512)) if not is_hot_tail else 2
            alloc_intent = MemoryIntent(
                object_id=f"{record.request_id}:import:{block_id}",
                request_id=record.request_id,
                block_id=block_id,
                object_type=ObjectType.KV_CACHE,
                phase=phase,
                priority=priority,
                allowed_tiers={Tier.HBM, Tier.DRAM},
                current_tier=Tier.HBM,
                size_bytes=logical_block_size,
                request_priority=record.request_priority if is_hot_tail else max(record.request_priority - 15, 0),
                recency_score=0.7 if is_hot_tail else max(0.0, 0.6 - age_fraction),
                deadline_us=deadline_us if is_hot_tail else None,
                slack_us=(deadline_us - 5000) if deadline_us is not None and is_hot_tail else None,
                arrival_step=record.arrival_ms,
                target_decode_step=(record.start_ms or record.arrival_ms) + block_id,
                expected_reuse_window_tokens=expected_reuse,
                recompute_cost_us=5000 if is_hot_tail else 200,
                spill_cost_us=200,
                compression_ok=compression_ok,
                recompute_ok=recompute_ok,
                prefetch_ok=not is_hot_tail,
                pin_requested=False,
                is_draft=False,
                is_committed=True,
                created_step=current_step,
                last_access_step=current_step,
            )
            events.append(
                MemoryIntentEvent(
                    step=current_step,
                    event_type=EventType.ALLOCATED,
                    intent=alloc_intent,
                    reason="approximate allocation imported from external request trace",
                )
            )
            current_step += 1

        for offset in range(decode_hot_blocks):
            block_id = num_blocks - decode_hot_blocks + offset
            deadline_us = record.deadline_ms * 1000 if record.deadline_ms is not None else None
            hot_intent = MemoryIntent(
                object_id=f"{record.request_id}:import:{block_id}",
                request_id=record.request_id,
                block_id=block_id,
                object_type=ObjectType.KV_CACHE,
                phase=Phase.DECODE,
                priority=Priority.DECODE_CRITICAL,
                allowed_tiers={Tier.HBM, Tier.DRAM},
                current_tier=Tier.HBM,
                size_bytes=logical_block_size,
                request_priority=record.request_priority,
                recency_score=max(0.8, 1.0 - (offset * 0.1)),
                deadline_us=deadline_us,
                slack_us=(deadline_us - (offset * 2000)) if deadline_us is not None else None,
                arrival_step=record.arrival_ms,
                target_decode_step=(record.start_ms or record.arrival_ms) + offset,
                expected_reuse_window_tokens=1 + offset,
                recompute_cost_us=6000,
                spill_cost_us=250,
                compression_ok=False,
                recompute_ok=False,
                prefetch_ok=True,
                pin_requested=True,
                is_draft=False,
                is_committed=True,
                created_step=current_step,
                last_access_step=current_step,
            )
            events.append(
                MemoryIntentEvent(
                    step=current_step,
                    event_type=EventType.MARKED_DECODE_CRITICAL,
                    intent=hot_intent,
                    reason="approximate decode-critical block reconstructed from external request trace",
                )
            )
            current_step += 1
            events.append(
                MemoryIntentEvent(
                    step=current_step,
                    event_type=EventType.ACCESSED,
                    intent=hot_intent.copy_with(last_access_step=current_step),
                    reason="approximate decode access reconstructed from external request trace",
                )
            )
            current_step += 1

        for block_id in range(max(0, num_blocks - decode_hot_blocks)):
            cold_intent = MemoryIntent(
                object_id=f"{record.request_id}:import:{block_id}",
                request_id=record.request_id,
                block_id=block_id,
                object_type=ObjectType.KV_CACHE,
                phase=Phase.IDLE,
                priority=Priority.COLD,
                allowed_tiers={Tier.HBM, Tier.DRAM},
                current_tier=Tier.HBM,
                size_bytes=logical_block_size,
                request_priority=max(record.request_priority - 20, 0),
                recency_score=0.0,
                deadline_us=None,
                slack_us=None,
                arrival_step=record.arrival_ms,
                target_decode_step=(record.end_ms or record.arrival_ms) + 1000,
                expected_reuse_window_tokens=256 + block_id,
                recompute_cost_us=100,
                spill_cost_us=100,
                compression_ok=True,
                recompute_ok=True,
                prefetch_ok=True,
                pin_requested=False,
                is_draft=False,
                is_committed=True,
                created_step=current_step,
                last_access_step=max(current_step - 5, 0),
            )
            events.append(
                MemoryIntentEvent(
                    step=current_step,
                    event_type=EventType.MARKED_COLD,
                    intent=cold_intent,
                    reason="approximate cold block reconstructed from external request trace",
                )
            )
            current_step += 1

        if record.status == "completed":
            for block_id in range(num_blocks):
                freed_intent = MemoryIntent(
                    object_id=f"{record.request_id}:import:{block_id}",
                    request_id=record.request_id,
                    block_id=block_id,
                    object_type=ObjectType.KV_CACHE,
                    phase=Phase.DONE,
                    priority=Priority.COLD,
                    allowed_tiers={Tier.HBM, Tier.DRAM},
                    current_tier=Tier.DRAM,
                    size_bytes=logical_block_size,
                    request_priority=record.request_priority,
                    recency_score=0.0,
                    deadline_us=None,
                    slack_us=None,
                    arrival_step=record.arrival_ms,
                    target_decode_step=None,
                    expected_reuse_window_tokens=None,
                    recompute_cost_us=0,
                    spill_cost_us=0,
                    compression_ok=True,
                    recompute_ok=False,
                    prefetch_ok=False,
                    pin_requested=False,
                    is_draft=False,
                    is_committed=True,
                    created_step=current_step,
                    last_access_step=current_step,
                )
                events.append(
                    MemoryIntentEvent(
                        step=current_step,
                        event_type=EventType.FREED,
                        intent=freed_intent,
                        reason="approximate free reconstructed from external request trace",
                    )
                )
                current_step += 1

    return events
