"""Design-level vLLM KV intent plugin with zero required upstream vLLM patching."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from kv_memory_intent.adapters import VLLMIntentAdapter
from kv_memory_intent.events import MemoryIntentEvent
from kv_memory_intent.schema import EventType


@dataclass(slots=True)
class KVIntentPlugin:
    """Thin proxy-style integration sketch for vLLM callback or engine wrapping.

    This file is intentionally explicit about data flow rather than tied to one
    exact vLLM release. A production integration would bind to the actual
    callback surface exposed by the installed vLLM version.
    """

    adapter: VLLMIntentAdapter
    out_path: Path

    def _append(self, events: list[MemoryIntentEvent]) -> None:
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        with self.out_path.open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(event.to_json() + "\n")

    def on_scheduler_step(self, step_output: object) -> None:
        events: list[MemoryIntentEvent] = []
        running_sequences = getattr(step_output, "running_sequences", [])
        for sequence in running_sequences:
            sequence_events = self.adapter.emit_sequence_accesses(sequence)
            events.extend(sequence_events)
            if getattr(sequence, "decode_depth", 0) > 0:
                for event in sequence_events[-4:]:
                    critical = MemoryIntentEvent(
                        step=event.step,
                        event_type=EventType.MARKED_DECODE_CRITICAL,
                        intent=event.intent.copy_with(pin_requested=True),
                        reason="decode tail promoted by KVIntentPlugin",
                    )
                    events.append(critical)
        self._append(events)

    def on_sequence_preempted(self, seq: object) -> None:
        events = self.adapter.emit_sequence_spill(seq)
        self._append(events)

    def on_sequence_finished(self, seq: object) -> None:
        events = self.adapter.emit_sequence_free(seq)
        self._append(events)
