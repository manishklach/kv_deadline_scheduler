#!/usr/bin/env python3
"""Convert DAMON hotness output into MemoryIntentEvent JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from kv_memory_intent.events import MemoryIntentEvent
from kv_memory_intent.schema import EventType, MemoryIntent, ObjectType, Phase, Priority, Tier
from kv_memory_intent.trace import IntentTraceRecorder


def classify_priority(nr_accesses: int) -> Priority:
    if nr_accesses >= 10:
        return Priority.DECODE_CRITICAL
    if nr_accesses >= 3:
        return Priority.HOT
    if nr_accesses >= 1:
        return Priority.WARM
    return Priority.COLD


def build_event(index: int, region: dict[str, object]) -> MemoryIntentEvent:
    accesses = int(region.get("nr_accesses", 0))
    priority = classify_priority(accesses)
    intent = MemoryIntent(
        object_id=f"damon-region-{index}",
        request_id=f"damon-req-{index}",
        block_id=index,
        object_type=ObjectType.KV_CACHE,
        phase=Phase.DECODE if priority == Priority.DECODE_CRITICAL else Phase.IDLE,
        priority=priority,
        allowed_tiers={Tier.HBM, Tier.DRAM},
        current_tier=Tier.DRAM,
        size_bytes=int(region["size_bytes"]),
        request_priority=90 if priority == Priority.DECODE_CRITICAL else 30,
        recency_score=min(accesses / 10.0, 1.0),
        deadline_us=2_000 if priority == Priority.DECODE_CRITICAL else None,
        slack_us=500 if priority == Priority.DECODE_CRITICAL else None,
        prefetch_ok=True,
        pin_requested=priority == Priority.DECODE_CRITICAL,
        created_step=0,
        last_access_step=accesses,
    )
    event_type = EventType.MARKED_DECODE_CRITICAL if priority == Priority.DECODE_CRITICAL else EventType.MARKED_COLD
    return MemoryIntentEvent(
        step=index,
        event_type=event_type,
        intent=intent,
        reason=f"Derived from DAMON nr_accesses={accesses}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert DAMON region counts into MemoryIntentEvent JSONL.")
    parser.add_argument(
        "--input",
        default=str(Path(__file__).resolve().parent / "results" / "damon_hotness_result.json"),
    )
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent / "results" / "damon_hotness_trace.jsonl"),
    )
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    recorder = IntentTraceRecorder()
    for index, region in enumerate(data.get("regions", [])):
        recorder.record(build_event(index, region))
    recorder.to_jsonl(args.out)
    print(f"Wrote {args.out}")
    print("This JSONL can be replayed with `kvmi compare --trace`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
