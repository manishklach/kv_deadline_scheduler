"""Generate and replay a mock vLLM-style KV lifecycle trace."""

from __future__ import annotations

import argparse
from pathlib import Path

from kv_memory_intent.adapters import generate_mock_vllm_trace
from kv_memory_intent.metrics import compare_results
from kv_memory_intent.simulator import KVMemorySimulator, policy_from_name


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and replay a mock serving-trace demo.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    recorder = generate_mock_vllm_trace(num_requests=8, decode_steps=128, seed=args.seed)
    out = Path(__file__).with_name("mock_vllm_trace.jsonl")
    recorder.to_jsonl(out)
    summary = recorder.summary()
    print(f"Generated mock vLLM trace: {out}")
    print(f"Events: {summary['total_events']}")
    print(f"Unique KV blocks: {summary['total_unique_blocks']}")
    print(f"Decode-critical bytes: {summary['decode_critical_bytes']}")
    print()
    print(recorder.print_summary())
    print()
    print("Running policy comparison...")
    results = [
        KVMemorySimulator(
            policy=policy_from_name(policy_name),
            hbm_capacity_bytes=48 * 1024 * 1024,
            dram_capacity_bytes=2048 * 1024 * 1024,
        ).run(recorder.events)
        for policy_name in ("lru", "hotcold", "predictive", "intent", "deadline")
    ]
    print(compare_results(results))


if __name__ == "__main__":
    main()
