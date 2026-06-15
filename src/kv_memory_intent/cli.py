"""Command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .metrics import compare_results
from .simulator import KVMemorySimulator, generate_synthetic_kv_workload, policy_from_name
from .trace import IntentTraceRecorder


def _mb_to_bytes(value: int) -> int:
    return value * 1024 * 1024


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kvmi", description="KV memory intent simulator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate a synthetic trace")
    generate.add_argument("--out", required=True)
    generate.add_argument("--requests", type=int, default=64)
    generate.add_argument("--blocks-per-request", type=int, default=32)
    generate.add_argument("--decode-steps", type=int, default=1000)
    generate.add_argument("--block-kb", type=int, default=16)

    simulate = subparsers.add_parser("simulate", help="Run one policy on a trace")
    simulate.add_argument("--trace", required=True)
    simulate.add_argument("--policy", choices=["lru", "intent", "deadline"], required=True)
    simulate.add_argument("--hbm-mb", type=int, default=512)
    simulate.add_argument("--dram-mb", type=int, default=4096)
    simulate.add_argument("--json", action="store_true")

    compare = subparsers.add_parser("compare", help="Compare all policies on one trace")
    compare.add_argument("--trace", required=True)
    compare.add_argument("--hbm-mb", type=int, default=512)
    compare.add_argument("--dram-mb", type=int, default=4096)

    subparsers.add_parser("demo", help="Generate a default workload and compare policies")
    return parser


def _default_trace() -> IntentTraceRecorder:
    recorder = IntentTraceRecorder()
    recorder.extend(
        generate_synthetic_kv_workload(
            num_requests=24,
            blocks_per_request=12,
            block_size_bytes=16 * 1024,
            decode_steps=180,
            seed=42,
        )
    )
    return recorder


def _run_simulation(trace: IntentTraceRecorder, policy_name: str, hbm_mb: int, dram_mb: int) -> dict[str, object]:
    simulator = KVMemorySimulator(
        policy=policy_from_name(policy_name),
        hbm_capacity_bytes=_mb_to_bytes(hbm_mb),
        dram_capacity_bytes=_mb_to_bytes(dram_mb),
    )
    result = simulator.run(trace.events)
    return result.to_dict()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "generate":
        recorder = IntentTraceRecorder()
        recorder.extend(
            generate_synthetic_kv_workload(
                num_requests=args.requests,
                blocks_per_request=args.blocks_per_request,
                block_size_bytes=args.block_kb * 1024,
                decode_steps=args.decode_steps,
            )
        )
        recorder.to_jsonl(args.out)
        print(recorder.print_summary())
        return

    if args.command == "simulate":
        trace = IntentTraceRecorder.from_jsonl(args.trace)
        result = _run_simulation(trace, args.policy, args.hbm_mb, args.dram_mb)
        print(json.dumps(result, indent=2, sort_keys=True) if args.json else _result_markdown(result))
        return

    if args.command == "compare":
        trace = IntentTraceRecorder.from_jsonl(args.trace)
        results = [
            KVMemorySimulator(
                policy=policy_from_name(policy_name),
                hbm_capacity_bytes=_mb_to_bytes(args.hbm_mb),
                dram_capacity_bytes=_mb_to_bytes(args.dram_mb),
            ).run(trace.events)
            for policy_name in ("lru", "intent", "deadline")
        ]
        print(compare_results(results))
        return

    if args.command == "demo":
        trace = _default_trace()
        print(trace.print_summary())
        print()
        results = [
            KVMemorySimulator(
                policy=policy_from_name(policy_name),
                hbm_capacity_bytes=4 * 1024 * 1024,
                dram_capacity_bytes=64 * 1024 * 1024,
            ).run(trace.events)
            for policy_name in ("lru", "intent", "deadline")
        ]
        print(compare_results(results))
        return


def _result_markdown(result: dict[str, object]) -> str:
    lines = ["## Simulation Result", ""]
    for key, value in result.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
