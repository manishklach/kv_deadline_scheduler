import pytest

from integrations.external_trace.parsers import parse_request_trace_jsonl, parse_telemetry_jsonl


def test_parse_telemetry_jsonl_validates_required_fields(tmp_path):
    path = tmp_path / "telemetry.jsonl"
    path.write_text(
        '{"timestamp_ms": 1000, "gpu_id": 0, "hbm_used_bytes": 1234, "hbm_total_bytes": 4096}\n',
        encoding="utf-8",
    )
    records = parse_telemetry_jsonl(path)
    assert records[0]["gpu_id"] == 0

    invalid = tmp_path / "telemetry_invalid.jsonl"
    invalid.write_text('{"timestamp_ms": 1000, "gpu_id": 0, "hbm_used_bytes": 1234}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        parse_telemetry_jsonl(invalid)


def test_parse_request_trace_jsonl_wraps_request_trace_loader(tmp_path):
    path = tmp_path / "requests.jsonl"
    path.write_text(
        (
            '{"request_id":"req-1","arrival_ms":0,"start_ms":1,"end_ms":2,'
            '"prompt_tokens":128,"generated_tokens":16,"request_priority":75,'
            '"deadline_ms":1000,"model_name":"llama-3-8b","status":"completed"}\n'
        ),
        encoding="utf-8",
    )
    records = parse_request_trace_jsonl(path)
    assert len(records) == 1
    assert records[0].request_id == "req-1"
