from pathlib import Path

from kv_memory_intent.kv_estimator import MODEL_PRESETS
from kv_memory_intent.request_trace import RequestTraceRecord
from kv_memory_intent.trace import IntentTraceRecorder
from kv_memory_intent.trace_importer import request_trace_to_intent_events
from kv_memory_intent.simulator import KVMemorySimulator, policy_from_name


def sample_records() -> list[RequestTraceRecord]:
    return [
        RequestTraceRecord(
            request_id="short",
            arrival_ms=0,
            start_ms=5,
            end_ms=100,
            prompt_tokens=512,
            generated_tokens=64,
            request_priority=80,
            deadline_ms=2000,
            model_name="llama-3-8b",
        ),
        RequestTraceRecord(
            request_id="long",
            arrival_ms=10,
            start_ms=20,
            end_ms=1000,
            prompt_tokens=128000,
            generated_tokens=1024,
            request_priority=40,
            deadline_ms=10000,
            model_name="llama-3-8b",
        ),
    ]


def test_import_creates_non_empty_events():
    events = request_trace_to_intent_events(
        sample_records(),
        MODEL_PRESETS["llama-3-8b"],
        max_blocks_per_request=256,
    )
    assert events


def test_long_context_request_produces_more_blocks_than_short_request():
    events = request_trace_to_intent_events(
        sample_records(),
        MODEL_PRESETS["llama-3-8b"],
        max_blocks_per_request=256,
    )
    counts: dict[str, set[int]] = {}
    for event in events:
        counts.setdefault(event.intent.request_id, set()).add(event.intent.block_id)
    assert len(counts["long"]) > len(counts["short"])


def test_deadlines_and_priority_are_propagated():
    events = request_trace_to_intent_events(
        sample_records(),
        MODEL_PRESETS["llama-3-8b"],
        max_blocks_per_request=256,
    )
    hot = [event for event in events if event.intent.priority.value == "DECODE_CRITICAL"]
    assert hot
    assert any(event.intent.deadline_us is not None for event in hot)
    assert any(event.intent.request_priority == 80 for event in hot)


def test_imported_trace_can_be_written_read_and_simulated(tmp_path: Path):
    events = request_trace_to_intent_events(
        sample_records(),
        MODEL_PRESETS["llama-3-8b"],
        max_blocks_per_request=256,
    )
    recorder = IntentTraceRecorder()
    recorder.extend(events)
    path = tmp_path / "intent_trace.jsonl"
    recorder.to_jsonl(path)
    loaded = IntentTraceRecorder.from_jsonl(path)
    assert loaded.events
    result = KVMemorySimulator(policy_from_name("deadline"), 64 * 1024 * 1024, 1024 * 1024 * 1024).run(
        loaded.events
    )
    assert result.total_blocks > 0
