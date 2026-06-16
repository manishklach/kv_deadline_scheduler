from kv_memory_intent.adapters.openai_proxy_adapter import openai_proxy_logs_to_intent_events
from kv_memory_intent.schema import EventType


def make_entry(identifier: str, created: int, model: str = "gpt-4") -> dict[str, object]:
    return {
        "id": identifier,
        "model": model,
        "created": created,
        "usage": {
            "prompt_tokens": 4096,
            "completion_tokens": 512,
            "total_tokens": 4608,
        },
    }


def test_single_log_entry_produces_allocate_mark_and_free():
    events = openai_proxy_logs_to_intent_events([make_entry("chatcmpl-1", 2)])
    event_types = {event.event_type for event in events}
    assert EventType.ALLOCATED in event_types
    assert EventType.MARKED_DECODE_CRITICAL in event_types
    assert EventType.FREED in event_types


def test_entries_are_sorted_by_created_timestamp():
    events = openai_proxy_logs_to_intent_events(
        [make_entry("late", 20), make_entry("early", 10)]
    )
    first_alloc = next(event for event in events if event.event_type == EventType.ALLOCATED)
    assert first_alloc.intent.request_id == "early"


def test_unrecognized_model_falls_back_to_llama3_8b():
    events = openai_proxy_logs_to_intent_events([make_entry("chatcmpl-1", 1, model="unknown-model")])
    assert events
