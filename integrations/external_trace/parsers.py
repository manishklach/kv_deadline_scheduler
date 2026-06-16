"""Helpers for loading documented external trace integration formats."""

from __future__ import annotations

import json
from pathlib import Path

from kv_memory_intent.request_trace import RequestTraceRecord, load_request_trace


def parse_telemetry_jsonl(path: str | Path) -> list[dict]:
    required_fields = {"timestamp_ms", "gpu_id", "hbm_used_bytes", "hbm_total_bytes"}
    records: list[dict] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        missing_fields = sorted(required_fields - payload.keys())
        if missing_fields:
            raise ValueError(f"telemetry record missing required fields: {', '.join(missing_fields)}")
        records.append(payload)
    return records


def parse_request_trace_jsonl(path: str | Path) -> list[RequestTraceRecord]:
    return load_request_trace(path)
