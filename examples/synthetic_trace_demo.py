"""Generate a small synthetic trace and print its summary."""

from __future__ import annotations

from pathlib import Path

from kv_memory_intent.simulator import generate_synthetic_kv_workload
from kv_memory_intent.trace import IntentTraceRecorder


def main() -> None:
    recorder = IntentTraceRecorder()
    recorder.extend(
        generate_synthetic_kv_workload(
            num_requests=8,
            blocks_per_request=8,
            block_size_bytes=16 * 1024,
            decode_steps=64,
            seed=7,
            profile="rag_mixed_priority",
        )
    )
    print(recorder.print_summary())
    out = Path(__file__).with_name("synthetic_trace.jsonl")
    recorder.to_jsonl(out)
    print(f"\nSaved trace to {out}")


if __name__ == "__main__":
    main()
