"""Command-line interface for KV Deadline Scheduler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapters import generate_mock_vllm_trace
from .metrics import SWEEP_COLUMNS, compare_results, write_sweep_csv
from .simulator import KVMemorySimulator, WorkloadProfile, generate_synthetic_kv_workload, policy_from_name
from .trace import IntentTraceRecorder

POLICY_ORDER = ("lru", "hotcold", "predictive", "intent", "deadline")


def _mb_to_bytes(value: int) -> int:
    return value * 1024 * 1024


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kvmi",
        description="KV Deadline Scheduler: deadline-aware KV-cache scheduling simulator for long-context LLM inference memory pressure.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser(
        "generate",
        help="Generate a synthetic KV deadline-pressure trace.",
        description="Generate a deterministic synthetic KV trace for deadline-aware scheduling experiments.",
    )
    generate.add_argument("--out", required=True, help="Output JSONL trace path.")
    generate.add_argument("--requests", type=int, default=64)
    generate.add_argument("--blocks-per-request", type=int, default=32)
    generate.add_argument("--decode-steps", type=int, default=1000)
    generate.add_argument("--block-kb", type=int, default=16)
    generate.add_argument(
        "--profile",
        choices=["balanced", "deadline_pressure", "rag_mixed_priority", "speculative_decode", "long_context_extreme"],
        default="balanced",
        help="Synthetic workload profile.",
    )

    simulate = subparsers.add_parser(
        "simulate",
        help="Run one KV placement policy on a trace.",
        description="Simulate a single access-based or deadline-aware KV placement policy on a trace.",
    )
    simulate.add_argument("--trace", required=True)
    simulate.add_argument("--policy", choices=["lru", "hotcold", "predictive", "intent", "deadline"], required=True)
    simulate.add_argument("--hbm-mb", type=int, default=512)
    simulate.add_argument("--dram-mb", type=int, default=4096)
    simulate.add_argument("--json", action="store_true")
    simulate.add_argument("--decision-log", help="Optional JSONL path for eviction/spill/prefetch decisions.")

    compare = subparsers.add_parser(
        "compare",
        help="Compare access-based and deadline-aware KV placement policies.",
        description="Compare LRU, hot/cold, predictive-hotness, intent-aware, and deadline-aware KV policies on the same trace.",
    )
    compare.add_argument("--trace", required=True)
    compare.add_argument("--hbm-mb", type=int, default=512)
    compare.add_argument("--dram-mb", type=int, default=4096)
    compare.add_argument("--decision-log-dir", help="Optional directory for per-policy decision logs.")

    demo = subparsers.add_parser(
        "demo",
        help="Run the default KV Deadline Scheduler demo.",
        description="Generate a default synthetic workload, compare policies, and print an example scheduling decision.",
    )
    demo.add_argument(
        "--profile",
        choices=["balanced", "deadline_pressure", "rag_mixed_priority", "speculative_decode", "long_context_extreme"],
        default="balanced",
    )

    mock_vllm = subparsers.add_parser(
        "mock-vllm",
        help="Generate a passive vLLM-style KV lifecycle trace.",
        description="Generate a mock vLLM-style JSONL trace through the passive adapter and optionally compare policies on it.",
    )
    mock_vllm.add_argument("--out", required=True, help="Output JSONL trace path.")
    mock_vllm.add_argument("--requests", type=int, default=8)
    mock_vllm.add_argument("--decode-steps", type=int, default=128)
    mock_vllm.add_argument("--compare", action="store_true")
    mock_vllm.add_argument("--hbm-mb", type=int, default=128)
    mock_vllm.add_argument("--dram-mb", type=int, default=2048)

    sweep = subparsers.add_parser(
        "sweep",
        help="Sweep HBM capacity to measure p99 latency sensitivity under KV pressure.",
        description="Run policy sweeps across HBM capacities and write CSV output for research-style comparison plots.",
    )
    sweep.add_argument("--trace", help="Input trace JSONL. Omit when using --demo.")
    sweep.add_argument("--demo", action="store_true", help="Generate the trace in memory instead of reading --trace.")
    sweep.add_argument("--hbm-min-mb", type=int, default=128)
    sweep.add_argument("--hbm-max-mb", type=int, default=2048)
    sweep.add_argument("--points", type=int, default=8)
    sweep.add_argument("--dram-mb", type=int, default=4096)
    sweep.add_argument("--out", required=True, help="Output CSV path.")
    sweep.add_argument(
        "--profile",
        choices=["balanced", "deadline_pressure", "rag_mixed_priority", "speculative_decode", "long_context_extreme"],
        default="balanced",
    )
    return parser


def _default_trace(profile: WorkloadProfile, compact: bool = False) -> IntentTraceRecorder:
    recorder = IntentTraceRecorder()
    recorder.extend(
        generate_synthetic_kv_workload(
            num_requests=12 if compact else 24,
            blocks_per_request=8 if compact else 12,
            block_size_bytes=16 * 1024,
            decode_steps=90 if compact else 180,
            seed=42,
            profile=profile,
        )
    )
    return recorder


def _result_markdown(result: dict[str, object]) -> str:
    lines = ["## Simulation Result", ""]
    for key, value in result.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _simulate(trace: IntentTraceRecorder, policy_name: str, hbm_mb: int, dram_mb: int) -> tuple[KVMemorySimulator, dict[str, object]]:
    simulator = KVMemorySimulator(
        policy=policy_from_name(policy_name),
        hbm_capacity_bytes=_mb_to_bytes(hbm_mb),
        dram_capacity_bytes=_mb_to_bytes(dram_mb),
    )
    result = simulator.run(trace.events)
    return simulator, result.to_dict()


def _load_trace(args: argparse.Namespace) -> IntentTraceRecorder:
    if getattr(args, "demo", False):
        return _default_trace(args.profile, compact=getattr(args, "command", "") == "sweep")
    return IntentTraceRecorder.from_jsonl(args.trace)


def _demo_decision_example(trace: IntentTraceRecorder) -> str:
    lru_sim, _ = _simulate(trace, "lru", 4, 64)
    deadline_sim, _ = _simulate(trace, "deadline", 4, 64)
    lru_decision = next((entry for entry in lru_sim.decision_log if entry["action"] in {"evict", "spill"}), None)
    deadline_decision = next(
        (entry for entry in deadline_sim.decision_log if entry["action"] in {"evict", "spill"}),
        None,
    )
    if lru_decision is None or deadline_decision is None:
        return "No decision example was generated."
    return (
        "## Example Decision\n\n"
        f"At step {deadline_decision['step']}:\n\n"
        "LRU-like decision:\n"
        f"- {lru_decision['victim_object_id']}\n"
        f"- phase: {lru_decision['victim_phase']}\n"
        f"- priority: {lru_decision['victim_priority']}\n"
        f"- deadline_us: {lru_decision['victim_deadline_us']}\n\n"
        "KVDeadline decision:\n"
        f"- {deadline_decision['victim_object_id']}\n"
        f"- phase: {deadline_decision['victim_phase']}\n"
        f"- priority: {deadline_decision['victim_priority']}\n"
        f"- deadline_us: {deadline_decision['victim_deadline_us']}\n"
        f"- reason: {deadline_decision['reason']}\n"
    )


def _sweep_rows(trace: IntentTraceRecorder, hbm_values: list[int], dram_mb: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for hbm_mb in hbm_values:
        for policy_name in POLICY_ORDER:
            simulator = KVMemorySimulator(
                policy=policy_from_name(policy_name),
                hbm_capacity_bytes=_mb_to_bytes(hbm_mb),
                dram_capacity_bytes=_mb_to_bytes(dram_mb),
            )
            result = simulator.run(trace.events)
            rows.append(
                {
                    "policy": result.policy_name,
                    "hbm_mb": hbm_mb,
                    "p50_latency_us": result.p50_latency_us,
                    "p95_latency_us": result.p95_latency_us,
                    "p99_latency_us": result.p99_latency_us,
                    "total_misses": result.miss_count,
                    "decode_critical_misses": result.decode_critical_misses,
                    "evictions": result.eviction_count,
                    "decode_critical_evictions": result.decode_critical_evictions,
                    "spills": result.spill_count,
                    "prefetches": result.prefetch_count,
                    "hbm_bytes_saved": result.hbm_bytes_saved,
                }
            )
    return rows


def _even_points(start: int, end: int, count: int) -> list[int]:
    if count <= 1:
        return [start]
    step = (end - start) / float(count - 1)
    return [int(round(start + (step * index))) for index in range(count)]


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
                profile=args.profile,
            )
        )
        recorder.to_jsonl(args.out)
        print(recorder.print_summary())
        return

    if args.command == "simulate":
        trace = IntentTraceRecorder.from_jsonl(args.trace)
        simulator, result = _simulate(trace, args.policy, args.hbm_mb, args.dram_mb)
        if args.decision_log:
            simulator.write_decision_log(args.decision_log)
        print(json.dumps(result, indent=2, sort_keys=True) if args.json else _result_markdown(result))
        return

    if args.command == "compare":
        trace = IntentTraceRecorder.from_jsonl(args.trace)
        decision_dir = Path(args.decision_log_dir) if args.decision_log_dir else None
        if decision_dir is not None:
            decision_dir.mkdir(parents=True, exist_ok=True)
        typed_results = []
        for policy_name in POLICY_ORDER:
            simulator = KVMemorySimulator(
                policy=policy_from_name(policy_name),
                hbm_capacity_bytes=_mb_to_bytes(args.hbm_mb),
                dram_capacity_bytes=_mb_to_bytes(args.dram_mb),
            )
            typed_result = simulator.run(trace.events)
            typed_results.append(typed_result)
            if decision_dir is not None:
                simulator.write_decision_log(decision_dir / f"{typed_result.policy_name}.jsonl")
        print(compare_results(typed_results))
        return

    if args.command == "demo":
        trace = _default_trace(args.profile)
        print(trace.print_summary())
        print()
        results = []
        for policy_name in POLICY_ORDER:
            simulator = KVMemorySimulator(
                policy=policy_from_name(policy_name),
                hbm_capacity_bytes=4 * 1024 * 1024,
                dram_capacity_bytes=64 * 1024 * 1024,
            )
            results.append(simulator.run(trace.events))
        print(compare_results(results))
        print()
        print(_demo_decision_example(trace))
        return

    if args.command == "mock-vllm":
        trace = generate_mock_vllm_trace(num_requests=args.requests, decode_steps=args.decode_steps)
        trace.to_jsonl(args.out)
        summary = trace.summary()
        print(f"Generated mock vLLM trace: {args.out}")
        print(f"Events: {summary['total_events']}")
        print(f"Unique KV blocks: {summary['total_unique_blocks']}")
        print(f"Decode-critical bytes: {summary['decode_critical_bytes']}")
        print()
        print(trace.print_summary())
        if args.compare:
            print()
            print("Running policy comparison...")
            typed_results = []
            for policy_name in POLICY_ORDER:
                simulator = KVMemorySimulator(
                    policy=policy_from_name(policy_name),
                    hbm_capacity_bytes=_mb_to_bytes(args.hbm_mb),
                    dram_capacity_bytes=_mb_to_bytes(args.dram_mb),
                )
                typed_results.append(simulator.run(trace.events))
            print(compare_results(typed_results))
        return

    if args.command == "sweep":
        if not args.demo and not args.trace:
            parser.error("sweep requires --trace or --demo")
        trace = _load_trace(args)
        hbm_values = _even_points(args.hbm_min_mb, args.hbm_max_mb, args.points)
        rows = _sweep_rows(trace, hbm_values, args.dram_mb)
        write_sweep_csv(rows, args.out)
        print(f"Wrote sweep CSV with columns: {', '.join(SWEEP_COLUMNS)}")
        print(f"Output: {args.out}")
        return


if __name__ == "__main__":
    main()
