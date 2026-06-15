"""Trace recording utilities."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable

from .events import MemoryIntentEvent
from .metrics import format_bytes
from .schema import EventType, Tier


class IntentTraceRecorder:
    def __init__(self) -> None:
        self.events: list[MemoryIntentEvent] = []

    def record(self, event: MemoryIntentEvent) -> None:
        self.events.append(event)

    def extend(self, events: Iterable[MemoryIntentEvent]) -> None:
        self.events.extend(events)

    def to_jsonl(self, path: str | Path) -> None:
        output = Path(path)
        output.write_text("\n".join(event.to_json() for event in self.events) + "\n", encoding="utf-8")

    @classmethod
    def from_jsonl(cls, path: str | Path) -> "IntentTraceRecorder":
        recorder = cls()
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                recorder.record(MemoryIntentEvent.from_json(line))
        return recorder

    def summary(self) -> dict[str, object]:
        events_by_type = Counter(event.event_type.value for event in self.events)
        latest_by_object: dict[str, MemoryIntentEvent] = {}
        identities: set[tuple[str, int]] = set()
        for event in self.events:
            latest_by_object[event.intent.object_id] = event
            identities.add((event.intent.request_id, event.intent.block_id))

        bytes_by_tier = Counter()
        decode_critical_bytes = 0
        committed_blocks = 0
        draft_blocks = 0
        total_bytes = 0
        for event in latest_by_object.values():
            intent = event.intent
            total_bytes += intent.size_bytes
            bytes_by_tier[intent.current_tier.value] += intent.size_bytes
            if intent.is_decode_critical():
                decode_critical_bytes += intent.size_bytes
            if intent.is_committed:
                committed_blocks += 1
            if intent.is_draft:
                draft_blocks += 1

        return {
            "total_events": len(self.events),
            "events_by_type": dict(sorted(events_by_type.items())),
            "total_unique_blocks": len(identities) if identities else len(latest_by_object),
            "total_bytes_represented": total_bytes,
            "bytes_by_current_tier": dict(sorted(bytes_by_tier.items())),
            "decode_critical_bytes": decode_critical_bytes,
            "committed_blocks": committed_blocks,
            "draft_blocks": draft_blocks,
            "spill_events": events_by_type.get(EventType.SPILLED.value, 0),
            "miss_events": events_by_type.get(EventType.MISS.value, 0),
            "eviction_events": events_by_type.get(EventType.EVICTED.value, 0),
            "prefetch_events": events_by_type.get(EventType.PREFETCHED.value, 0),
        }

    def print_summary(self) -> str:
        summary = self.summary()
        lines = [
            "## Trace Summary",
            "",
            f"- Total events: {summary['total_events']}",
            f"- Unique blocks: {summary['total_unique_blocks']}",
            f"- Total bytes represented: {format_bytes(int(summary['total_bytes_represented']))}",
            f"- Decode-critical bytes: {format_bytes(int(summary['decode_critical_bytes']))}",
            f"- Committed blocks: {summary['committed_blocks']}",
            f"- Draft blocks: {summary['draft_blocks']}",
            f"- Spill events: {summary['spill_events']}",
            f"- Miss events: {summary['miss_events']}",
            f"- Eviction events: {summary['eviction_events']}",
            f"- Prefetch events: {summary['prefetch_events']}",
            "",
            "### Bytes By Tier",
        ]
        for tier in Tier:
            lines.append(
                f"- {tier.value}: {format_bytes(int(summary['bytes_by_current_tier'].get(tier.value, 0)))}"
            )
        lines.extend(["", "### Events By Type"])
        for event_type, count in summary["events_by_type"].items():
            lines.append(f"- {event_type}: {count}")
        return "\n".join(lines)
