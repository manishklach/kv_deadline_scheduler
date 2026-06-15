from kv_memory_intent.events import MemoryIntentEvent
from kv_memory_intent.schema import EventType, MemoryIntent, ObjectType, Phase, Priority, Tier


def make_intent():
    return MemoryIntent(
        object_id="obj-1",
        request_id="req-1",
        block_id=1,
        object_type=ObjectType.KV_CACHE,
        phase=Phase.PREFILL,
        priority=Priority.HOT,
        allowed_tiers={Tier.HBM, Tier.DRAM},
        current_tier=Tier.HBM,
        size_bytes=2048,
    )


def test_event_json_round_trip():
    event = MemoryIntentEvent(step=1, event_type=EventType.ALLOCATED, intent=make_intent(), latency_us=15)
    restored = MemoryIntentEvent.from_json(event.to_json())
    assert restored.to_dict() == event.to_dict()


def test_negative_step_raises():
    try:
        MemoryIntentEvent(step=-1, event_type=EventType.ALLOCATED, intent=make_intent())
    except ValueError as exc:
        assert "step" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_negative_latency_raises():
    try:
        MemoryIntentEvent(step=0, event_type=EventType.ALLOCATED, intent=make_intent(), latency_us=-1)
    except ValueError as exc:
        assert "latency_us" in str(exc)
    else:
        raise AssertionError("expected ValueError")
