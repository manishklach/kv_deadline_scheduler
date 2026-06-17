from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kv_memory_intent import KVMemorySimulator, generate_mock_vllm_trace, generate_synthetic_kv_workload
from kv_memory_intent.simulator import policy_from_name
from kv_memory_intent.speculative import run_speculative_policy_suite


@dataclass(slots=True)
class SuiteRun:
    workload: str
    policy: str
    total_blocks: int
    p50_latency_us: float
    p95_latency_us: float
    p99_latency_us: float
    decode_critical_misses: int
    decode_critical_miss_rate: float
    eviction_count: int
    spill_count: int
    prefetch_count: int
    capacity_exhaustion_events: int
    pinned_capacity_exhaustion_events: int


def _distribution(latencies: list[int]) -> dict[str, int | float]:
    if not latencies:
        return {"count": 0, "min_us": 0, "max_us": 0, "mean_us": 0.0}
    return {
        "count": len(latencies),
        "min_us": min(latencies),
        "max_us": max(latencies),
        "mean_us": round(sum(latencies) / len(latencies), 6),
    }


def _run_workload_suite(config: dict[str, Any], seed: int) -> tuple[list[SuiteRun], dict[str, dict[str, int | float]]]:
    rows: list[SuiteRun] = []
    distributions: dict[str, dict[str, int | float]] = {}
    for workload in config["workloads"]:
        events = generate_synthetic_kv_workload(
            num_requests=int(workload["num_requests"]),
            blocks_per_request=int(workload["blocks_per_request"]),
            block_size_bytes=int(workload["block_size_bytes"]),
            decode_steps=int(workload["decode_steps"]),
            profile=str(workload["profile"]),
            seed=seed,
        )
        for policy_name in config["policies"]:
            simulator = KVMemorySimulator(
                policy_from_name(str(policy_name)),
                hbm_capacity_bytes=int(workload["hbm_capacity_bytes"]),
                dram_capacity_bytes=int(workload["dram_capacity_bytes"]),
            )
            result = simulator.run(events)
            key = f"{workload['name']}::{policy_name}"
            distributions[key] = _distribution(simulator.latencies)
            rows.append(
                SuiteRun(
                    workload=str(workload["name"]),
                    policy=str(policy_name),
                    total_blocks=result.total_blocks,
                    p50_latency_us=result.p50_latency_us,
                    p95_latency_us=result.p95_latency_us,
                    p99_latency_us=result.p99_latency_us,
                    decode_critical_misses=result.decode_critical_misses,
                    decode_critical_miss_rate=result.decode_critical_miss_rate,
                    eviction_count=result.eviction_count,
                    spill_count=result.spill_count,
                    prefetch_count=result.prefetch_count,
                    capacity_exhaustion_events=result.capacity_exhaustion_events,
                    pinned_capacity_exhaustion_events=result.pinned_capacity_exhaustion_events,
                )
            )
    return rows, distributions


def _run_mock_vllm_suite(config: dict[str, Any]) -> list[dict[str, Any]]:
    if not config.get("enabled", False):
        return []
    recorder = generate_mock_vllm_trace(
        num_requests=int(config["num_requests"]),
        decode_steps=int(config["decode_steps"]),
    )
    results: list[dict[str, Any]] = []
    for policy_name in ("lru", "deadline"):
        simulator = KVMemorySimulator(
            policy_from_name(policy_name),
            hbm_capacity_bytes=int(config["hbm_capacity_bytes"]),
            dram_capacity_bytes=int(config["dram_capacity_bytes"]),
        )
        simulation = simulator.run(recorder.events)
        results.append(
            {
                "policy": policy_name,
                "total_blocks": simulation.total_blocks,
                "p99_latency_us": simulation.p99_latency_us,
                "decode_critical_miss_rate": simulation.decode_critical_miss_rate,
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the reproducible KV Deadline Scheduler benchmark suite.")
    parser.add_argument("--config", default="benchmarks/configs/default_suite.json")
    args = parser.parse_args()

    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    out_dir = Path(str(config["out_dir"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = int(config.get("seed", 42))

    rows, distributions = _run_workload_suite(config, seed)
    speculative_results = []
    if config.get("speculative", {}).get("enabled", False):
        speculative = config["speculative"]
        speculative_results = [
            result.to_dict()
            for result in run_speculative_policy_suite(
                hbm_capacity_bytes=int(speculative["hbm_capacity_bytes"]),
                dram_capacity_bytes=int(speculative["dram_capacity_bytes"]),
                acceptance_rate=float(speculative["acceptance_rate"]),
                tree_width=int(speculative["tree_width"]),
                tree_depth=int(speculative["tree_depth"]),
                seed=seed,
            )
        ]
    mock_vllm_results = _run_mock_vllm_suite(config.get("mock_vllm", {}))

    csv_path = out_dir / "policy_metrics.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()) if rows else list(SuiteRun.__annotations__.keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    (out_dir / "latency_distributions.json").write_text(
        json.dumps(distributions, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "speculative_metrics.json").write_text(
        json.dumps(speculative_results, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "seed": seed,
                "config": config,
                "rows": [asdict(row) for row in rows],
                "mock_vllm": mock_vllm_results,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
