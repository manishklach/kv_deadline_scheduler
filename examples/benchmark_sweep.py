#!/usr/bin/env python3
"""Benchmark all five policies across all five workload profiles.

Writes:
- examples/results/sweep_summary.csv
- examples/results/sweep_summary.json
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import time
from pathlib import Path

from kv_memory_intent.simulator import (
    KVMemorySimulator,
    generate_synthetic_kv_workload,
    policy_from_name,
)

POLICIES = ["lru", "hotcold", "predictive", "intent", "deadline"]
PROFILES = [
    "balanced",
    "deadline_pressure",
    "rag_mixed_priority",
    "speculative_decode",
    "long_context_extreme",
]


def run_sweep(
    seed: int,
    requests: int,
    blocks_per_req: int,
    block_size_mb: int,
    decode_steps: int,
    hbm_mb: int,
    dram_mb: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for profile in PROFILES:
        events = generate_synthetic_kv_workload(
            num_requests=requests,
            blocks_per_request=blocks_per_req,
            block_size_bytes=block_size_mb * 1024 * 1024,
            decode_steps=decode_steps,
            profile=profile,
            seed=seed,
        )
        for policy_name in POLICIES:
            policy = policy_from_name(policy_name)
            simulator = KVMemorySimulator(
                policy,
                hbm_capacity_bytes=hbm_mb * 1024 * 1024,
                dram_capacity_bytes=dram_mb * 1024 * 1024,
            )
            start = time.perf_counter()
            result = simulator.run(events)
            elapsed = time.perf_counter() - start
            rows.append(
                {
                    "profile": profile,
                    "policy": policy_name,
                    "p50_ms": round(result.p50_latency_us / 1000.0, 4),
                    "p95_ms": round(result.p95_latency_us / 1000.0, 4),
                    "p99_ms": round(result.p99_latency_us / 1000.0, 4),
                    "dc_miss_rate": round(result.decode_critical_miss_rate, 5),
                    "total_blocks": result.total_blocks,
                    "evictions": result.eviction_count,
                    "sim_sec": round(elapsed, 4),
                }
            )
    return rows


def write_outputs(meta: dict[str, object], rows: list[dict[str, object]]) -> tuple[Path, Path]:
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "sweep_summary.csv"
    json_path = out_dir / "sweep_summary.json"

    fieldnames = [
        "profile",
        "policy",
        "p50_ms",
        "p95_ms",
        "p99_ms",
        "dc_miss_rate",
        "total_blocks",
        "evictions",
        "sim_sec",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    json_path.write_text(json.dumps({"meta": meta, "results": rows}, indent=2) + "\n", encoding="utf-8")
    return csv_path, json_path


def print_grouped_table(rows_or_data: list[dict[str, object]] | dict[str, object]) -> None:
    rows = rows_or_data
    if isinstance(rows_or_data, dict) and "meta" in rows_or_data:
        rows = rows_or_data["results"]
    for profile in PROFILES:
        print(f"\nProfile: {profile}")
        print("| Policy | P50 (ms) | P95 (ms) | P99 (ms) | DC miss rate | Evictions | Sim sec |")
        print("|---|---:|---:|---:|---:|---:|---:|")
        for row in rows:
            if row["profile"] != profile:
                continue
            print(
                "| "
                + " | ".join(
                    [
                        str(row["policy"]),
                        f"{row['p50_ms']}",
                        f"{row['p95_ms']}",
                        f"{row['p99_ms']}",
                        f"{row['dc_miss_rate']}",
                        f"{row['evictions']}",
                        f"{row['sim_sec']}",
                    ]
                )
                + " |"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark all five policies across all five workload profiles.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--requests", type=int, default=64)
    parser.add_argument("--blocks-per-req", type=int, default=24)
    parser.add_argument("--block-size-mb", type=int, default=1)
    parser.add_argument("--decode-steps", type=int, default=32)
    parser.add_argument("--hbm-mb", type=int, default=128)
    parser.add_argument("--dram-mb", type=int, default=4096)
    args = parser.parse_args()

    workload_mb = args.requests * args.blocks_per_req * args.block_size_mb
    pressure_ratio = workload_mb / args.hbm_mb
    print(f"Workload: {workload_mb} MB | HBM: {args.hbm_mb} MB | Pressure: {pressure_ratio:.1f}x")
    if workload_mb <= args.hbm_mb:
        print("WARNING: workload fits entirely in HBM — no eviction pressure.")
        print("Increase --requests or --block-size-mb for meaningful results.")

    rows = run_sweep(
        args.seed,
        args.requests,
        args.blocks_per_req,
        args.block_size_mb,
        args.decode_steps,
        args.hbm_mb,
        args.dram_mb,
    )
    meta = {
        "seed": args.seed,
        "requests": args.requests,
        "blocks_per_req": args.blocks_per_req,
        "block_size_mb": args.block_size_mb,
        "decode_steps": args.decode_steps,
        "hbm_mb": args.hbm_mb,
        "dram_mb": args.dram_mb,
        "workload_mb": workload_mb,
        "pressure_ratio": round(pressure_ratio, 1),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    csv_path, json_path = write_outputs(meta, rows)
    print_grouped_table({"meta": meta, "results": rows})
    print(f"\nWrote {csv_path}")
    print(f"Wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
