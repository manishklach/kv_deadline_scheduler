from pathlib import Path

from integrations.vllm.smoke_test_plugin import run_smoke_test
from kv_memory_intent.events import MemoryIntentEvent


def test_smoke_plugin_writes_trace(tmp_path: Path):
    out = tmp_path / "plugin_smoke.jsonl"
    run_smoke_test(out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines
    events = [MemoryIntentEvent.from_json(line) for line in lines]
    event_types = {event.event_type.value for event in events}
    assert "MARKED_DECODE_CRITICAL" in event_types
    assert "SPILLED" in event_types
    assert "FREED" in event_types
