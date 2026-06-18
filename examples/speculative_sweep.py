#!/usr/bin/env python3
"""Run a focused speculative decoding policy sweep.

Writes:
- examples/results/speculative_sweep.json
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from kv_memory_intent.speculative import run_speculative_policy_suite


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark speculative decoding-aware policies.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--acceptance-rate", type=float, default=0.7)
    parser.add_argument("--tree-width", type=int, default=4)
    parser.add_argument("--tree-depth", type=int, default=3)
    parser.add_argument("--hbm-mb", type=int, default=16)
    parser.add_argument("--dram-mb", type=int, default=256)
    args = parser.parse_args()

    results = run_speculative_policy_suite(
        hbm_capacity_bytes=args.hbm_mb * 1024 * 1024,
        dram_capacity_bytes=args.dram_mb * 1024 * 1024,
        acceptance_rate=args.acceptance_rate,
        tree_width=args.tree_width,
        tree_depth=args.tree_depth,
        seed=args.seed,
    )

    payload = {
        "meta": {
            "seed": args.seed,
            "acceptance_rate": args.acceptance_rate,
            "tree_width": args.tree_width,
            "tree_depth": args.tree_depth,
            "hbm_mb": args.hbm_mb,
            "dram_mb": args.dram_mb,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "results": [result.to_dict() for result in results],
    }

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "speculative_sweep.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print("| Policy | P50 (us) | P95 (us) | P99 (us) | DC miss rate | Freed rejected | Wasted HBM MB |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for row in payload["results"]:
        print(
            "| "
            + " | ".join(
                [
                    str(row["policy_name"]),
                    str(row["p50_latency_us"]),
                    str(row["p95_latency_us"]),
                    str(row["p99_latency_us"]),
                    str(row["decode_critical_miss_rate"]),
                    str(row["freed_rejected_blocks"]),
                    str(row["wasted_hbm_mb_on_rejected_drafts"]),
                ]
            )
            + " |"
        )

    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
