"""Prometheus GPU memory telemetry adapter."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from ..events import MemoryIntentEvent
from ..schema import EventType, MemoryIntent, ObjectType, Phase, Priority, Tier


def prometheus_samples_to_intent_events(
    samples: list[dict[str, object]],
    max_memory_bytes: int = 40 * 1024**3,
) -> list[MemoryIntentEvent]:
    if max_memory_bytes <= 0:
        raise ValueError("max_memory_bytes must be > 0")

    events: list[MemoryIntentEvent] = []
    sorted_samples = sorted(samples, key=lambda sample: float(sample["value"][0]))
    for step, sample in enumerate(sorted_samples):
        memory_used_bytes = int(float(sample["value"][1]))
        high_pressure = memory_used_bytes > (0.85 * max_memory_bytes)
        event_type = EventType.MARKED_DECODE_CRITICAL if high_pressure else EventType.MARKED_COLD
        intent = MemoryIntent(
            object_id="pressure-monitor:block:0",
            request_id="pressure-monitor",
            block_id=0,
            object_type=ObjectType.KV_CACHE,
            phase=Phase.DECODE if high_pressure else Phase.IDLE,
            priority=Priority.DECODE_CRITICAL if high_pressure else Priority.COLD,
            allowed_tiers={Tier.HBM, Tier.DRAM},
            current_tier=Tier.HBM,
            size_bytes=memory_used_bytes or 1,
            request_priority=100 if high_pressure else 10,
            recency_score=1.0 if high_pressure else 0.0,
            deadline_us=1000 if high_pressure else None,
            slack_us=300 if high_pressure else None,
            arrival_step=step,
            target_decode_step=step,
            expected_reuse_window_tokens=1 if high_pressure else 1024,
            recompute_cost_us=5000 if high_pressure else 100,
            spill_cost_us=250 if high_pressure else 100,
            compression_ok=not high_pressure,
            recompute_ok=not high_pressure,
            prefetch_ok=high_pressure,
            pin_requested=high_pressure,
            is_draft=False,
            is_committed=True,
            created_step=step,
            last_access_step=step,
        )
        events.append(
            MemoryIntentEvent(
                step=step,
                event_type=event_type,
                intent=intent,
                reason="synthetic pressure signal imported from Prometheus GPU memory telemetry",
            )
        )
    return events


def load_prometheus_samples(path: str | Path) -> list[dict[str, object]]:
    data = Path(path).read_text(encoding="utf-8").strip()
    if not data:
        return []
    if data.startswith("["):
        return list(json.loads(data))
    return [json.loads(line) for line in data.splitlines() if line.strip()]


def write_prometheus_samples(samples: Iterable[dict[str, object]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(list(samples), indent=2), encoding="utf-8")
