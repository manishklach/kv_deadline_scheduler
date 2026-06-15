from kv_memory_intent.adapters import VLLMIntentAdapter
from kv_memory_intent.schema import EventType


def test_vllm_adapter_skeleton_creates_valid_events():
    adapter = VLLMIntentAdapter()
    event = adapter.on_block_allocated(1, "req-1:block:1", "req-1", 1)
    assert event.event_type == EventType.ALLOCATED
    assert event.intent.request_id == "req-1"
    assert event.intent.object_id == "req-1:block:1"
