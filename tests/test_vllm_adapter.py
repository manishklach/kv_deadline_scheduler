from pathlib import Path

from kv_memory_intent.adapters import VLLMIntentAdapter, generate_mock_vllm_trace
from kv_memory_intent.schema import EventType, Phase, Priority
from kv_memory_intent.simulator import KVMemorySimulator, policy_from_name
from kv_memory_intent.trace import IntentTraceRecorder


def test_adapter_can_allocate_a_block():
    adapter = VLLMIntentAdapter()
    event = adapter.on_block_allocated(step=1, request_id="req-1", block_id=0)
    assert event.event_type == EventType.ALLOCATED
    assert event.intent.object_id == "req-1:kv:0"


def test_adapter_can_access_a_block():
    adapter = VLLMIntentAdapter()
    adapter.on_block_allocated(step=1, request_id="req-1", block_id=0)
    event = adapter.on_block_accessed(step=2, request_id="req-1", block_id=0)
    assert event.event_type == EventType.ACCESSED
    assert event.intent.last_access_step == 2


def test_decode_step_marks_blocks_decode_critical_and_pinned():
    adapter = VLLMIntentAdapter()
    adapter.on_request_scheduled(step=0, request_id="req-1", request_priority=90, deadline_us=900)
    adapter.on_block_allocated(step=1, request_id="req-1", block_id=0)
    events = adapter.on_decode_step(step=2, request_id="req-1", active_block_ids=[0], deadline_us=900)
    assert any(event.event_type == EventType.MARKED_DECODE_CRITICAL for event in events)
    marked = next(event for event in events if event.event_type == EventType.MARKED_DECODE_CRITICAL)
    assert marked.intent.priority == Priority.DECODE_CRITICAL
    assert marked.intent.pin_requested is True


def test_finished_request_emits_done_and_freed_style_events():
    adapter = VLLMIntentAdapter()
    adapter.on_block_allocated(step=1, request_id="req-1", block_id=0)
    events = adapter.on_request_finished(step=2, request_id="req-1", block_ids=[0])
    assert any(event.intent.phase == Phase.DONE for event in events)
    assert any(event.event_type == EventType.FREED for event in events)


def test_jsonl_written_by_adapter_can_be_read(tmp_path: Path):
    adapter = VLLMIntentAdapter()
    adapter.on_block_allocated(step=1, request_id="req-1", block_id=0)
    path = tmp_path / "trace.jsonl"
    adapter.recorder.to_jsonl(path)
    loaded = IntentTraceRecorder.from_jsonl(path)
    assert len(loaded.events) == 1


def test_mock_vllm_trace_has_non_empty_events():
    recorder = generate_mock_vllm_trace(num_requests=4, decode_steps=16, seed=7)
    assert recorder.events


def test_running_simulator_on_mock_trace_produces_valid_result():
    recorder = generate_mock_vllm_trace(num_requests=4, decode_steps=16, seed=7)
    result = KVMemorySimulator(policy_from_name("deadline"), 8 * 1024 * 1024, 32 * 1024 * 1024).run(
        recorder.events
    )
    assert result.policy_name == "KVDeadline"
    assert result.total_blocks > 0
