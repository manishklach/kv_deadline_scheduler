"""External request trace format for KV pressure profiling."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(slots=True)
class RequestTraceRecord:
    request_id: str
    arrival_ms: int
    start_ms: int | None
    end_ms: int | None
    prompt_tokens: int
    generated_tokens: int
    request_priority: int = 50
    deadline_ms: int | None = None
    model_name: str | None = None
    status: str = "completed"

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("request_id must not be empty")
        if self.arrival_ms < 0:
            raise ValueError("arrival_ms must be >= 0")
        if self.prompt_tokens < 0:
            raise ValueError("prompt_tokens must be >= 0")
        if self.generated_tokens < 0:
            raise ValueError("generated_tokens must be >= 0")
        if not 0 <= self.request_priority <= 100:
            raise ValueError("request_priority must be in range 0..100")
        if self.deadline_ms is not None and self.deadline_ms <= 0:
            raise ValueError("deadline_ms must be > 0 when provided")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "RequestTraceRecord":
        return cls(
            request_id=str(data["request_id"]),
            arrival_ms=int(data["arrival_ms"]),
            start_ms=int(data["start_ms"]) if data.get("start_ms") is not None else None,
            end_ms=int(data["end_ms"]) if data.get("end_ms") is not None else None,
            prompt_tokens=int(data["prompt_tokens"]),
            generated_tokens=int(data["generated_tokens"]),
            request_priority=int(data.get("request_priority", 50)),
            deadline_ms=int(data["deadline_ms"]) if data.get("deadline_ms") is not None else None,
            model_name=str(data["model_name"]) if data.get("model_name") is not None else None,
            status=str(data.get("status", "completed")),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, value: str) -> "RequestTraceRecord":
        return cls.from_dict(json.loads(value))


def load_request_trace(path: str | Path) -> list[RequestTraceRecord]:
    records: list[RequestTraceRecord] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(RequestTraceRecord.from_json(line))
    return records


def write_request_trace(records: Iterable[RequestTraceRecord], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(record.to_json() for record in records) + "\n", encoding="utf-8")
