from pathlib import Path

from kv_memory_intent.request_trace import RequestTraceRecord, load_request_trace, write_request_trace


def test_request_trace_json_round_trip():
    record = RequestTraceRecord(
        request_id="req-1",
        arrival_ms=0,
        start_ms=1,
        end_ms=10,
        prompt_tokens=128,
        generated_tokens=16,
        request_priority=90,
        deadline_ms=1000,
        model_name="llama-3-8b",
    )
    restored = RequestTraceRecord.from_json(record.to_json())
    assert restored.to_dict() == record.to_dict()


def test_request_trace_write_and_load(tmp_path: Path):
    records = [
        RequestTraceRecord(
            request_id="req-1",
            arrival_ms=0,
            start_ms=1,
            end_ms=10,
            prompt_tokens=128,
            generated_tokens=16,
        )
    ]
    path = tmp_path / "requests.jsonl"
    write_request_trace(records, path)
    loaded = load_request_trace(path)
    assert len(loaded) == 1
    assert loaded[0].request_id == "req-1"
