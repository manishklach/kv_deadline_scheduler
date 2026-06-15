"""Event types and serialization."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .schema import EventType, MemoryIntent


@dataclass(slots=True)
class MemoryIntentEvent:
    step: int
    event_type: EventType
    intent: MemoryIntent
    reason: str | None = None
    latency_us: int | None = None

    def __post_init__(self) -> None:
        if self.step < 0:
            raise ValueError("step must be >= 0")
        if self.latency_us is not None and self.latency_us < 0:
            raise ValueError("latency_us must be >= 0 when provided")

    def to_dict(self) -> dict[str, object]:
        return {
            "step": self.step,
            "event_type": self.event_type.value,
            "intent": self.intent.to_dict(),
            "reason": self.reason,
            "latency_us": self.latency_us,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "MemoryIntentEvent":
        return cls(
            step=int(data["step"]),
            event_type=EventType(str(data["event_type"])),
            intent=MemoryIntent.from_dict(dict(data["intent"])),
            reason=str(data["reason"]) if data.get("reason") is not None else None,
            latency_us=int(data["latency_us"]) if data.get("latency_us") is not None else None,
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, value: str) -> "MemoryIntentEvent":
        return cls.from_dict(json.loads(value))
