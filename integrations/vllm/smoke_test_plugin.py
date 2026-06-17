from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

from kv_memory_intent.adapters import VLLMIntentAdapter
from kv_memory_intent.trace import IntentTraceRecorder

try:
    from .vllm_kv_intent_plugin import KVIntentPlugin
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from integrations.vllm.vllm_kv_intent_plugin import KVIntentPlugin


@dataclass(slots=True)
class FakeSequence:
    request_id: str
    block_ids: list[int]
    step: int
    decode_depth: int
    deadline_us: int
    request_priority: int

    @property
    def active_block_ids(self) -> list[int]:
        return self.block_ids


@dataclass(slots=True)
class FakeStepOutput:
    running_sequences: list[FakeSequence]


def run_smoke_test(out_path: Path) -> Path:
    recorder = IntentTraceRecorder()
    adapter = VLLMIntentAdapter(recorder=recorder, default_block_size_bytes=256 * 1024)
    adapter.on_request_scheduled(step=0, request_id="req-smoke", request_priority=90, deadline_us=900)
    for block_id in range(4):
        adapter.on_block_allocated(step=block_id, request_id="req-smoke", block_id=block_id)

    plugin = KVIntentPlugin(adapter=adapter, out_path=out_path)
    sequence = FakeSequence(
        request_id="req-smoke",
        block_ids=[0, 1, 2, 3],
        step=10,
        decode_depth=1,
        deadline_us=900,
        request_priority=90,
    )
    plugin.on_scheduler_step(FakeStepOutput(running_sequences=[sequence]))
    plugin.on_sequence_preempted(sequence)
    plugin.on_sequence_finished(sequence)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local smoke test for the vLLM KV intent plugin harness.")
    parser.add_argument("--out", default="integrations/vllm/results/plugin_smoke.jsonl")
    args = parser.parse_args()
    path = run_smoke_test(Path(args.out))
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
