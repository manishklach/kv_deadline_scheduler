from kv_memory_intent.adapters.prometheus_adapter import prometheus_samples_to_intent_events
from kv_memory_intent.schema import EventType, Priority


def sample(timestamp: float, used_bytes: int) -> dict[str, object]:
    return {
        "metric": {"gpu": "0", "instance": "node1"},
        "value": [timestamp, str(used_bytes)],
    }


def test_high_pressure_sample_becomes_decode_critical():
    events = prometheus_samples_to_intent_events([sample(1.0, 39 * 1024**3)], max_memory_bytes=40 * 1024**3)
    assert events[0].event_type == EventType.MARKED_DECODE_CRITICAL
    assert events[0].intent.priority == Priority.DECODE_CRITICAL


def test_low_pressure_sample_becomes_cold():
    events = prometheus_samples_to_intent_events([sample(1.0, 10 * 1024**3)], max_memory_bytes=40 * 1024**3)
    assert events[0].event_type == EventType.MARKED_COLD


def test_pressure_transition_preserves_timestamp_order():
    events = prometheus_samples_to_intent_events(
        [
            sample(2.0, 39 * 1024**3),
            sample(1.0, 10 * 1024**3),
        ],
        max_memory_bytes=40 * 1024**3,
    )
    assert events[0].event_type == EventType.MARKED_COLD
    assert events[1].event_type == EventType.MARKED_DECODE_CRITICAL
