"""Metrics and formatting helpers."""

from __future__ import annotations

import csv
from math import floor
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .simulator import SimulationResult


SWEEP_COLUMNS = [
    "policy",
    "hbm_mb",
    "p50_latency_us",
    "p95_latency_us",
    "p99_latency_us",
    "total_misses",
    "decode_critical_misses",
    "evictions",
    "decode_critical_evictions",
    "spills",
    "prefetches",
    "hbm_bytes_saved",
]


def percentile(values: list[int | float], p: float) -> float:
    if not values:
        return 0.0
    if p < 0 or p > 100:
        raise ValueError("p must be in range 0..100")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (p / 100.0)
    lower = floor(rank)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def format_bytes(num_bytes: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    value = float(num_bytes)
    for unit in units:
        if abs(value) < 1024.0 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} TiB"


def compare_results(results: list["SimulationResult"]) -> str:
    if not results:
        return "No results."
    baseline = next((result for result in results if result.policy_name == "LRU"), results[0])
    header = (
        "| Policy | P50 latency | P95 latency | P99 latency | Misses | Decode-critical misses | "
        "Decode-critical miss rate | Evictions | Decode-critical evictions | Spills | Prefetches | HBM saved | "
        "P99 improvement vs LRU | Decode-critical miss reduction vs LRU |"
    )
    separator = "|" + "|".join(["---"] * 14) + "|"
    rows = [header, separator]
    for result in results:
        p99_improvement = (
            ((baseline.p99_latency_us - result.p99_latency_us) / baseline.p99_latency_us) * 100.0
            if baseline.p99_latency_us
            else 0.0
        )
        miss_reduction = (
            ((baseline.decode_critical_misses - result.decode_critical_misses) / baseline.decode_critical_misses)
            * 100.0
            if baseline.decode_critical_misses
            else 0.0
        )
        rows.append(
            "| "
            + " | ".join(
                [
                    result.policy_name,
                    f"{result.p50_latency_us:.1f} us",
                    f"{result.p95_latency_us:.1f} us",
                    f"{result.p99_latency_us:.1f} us",
                    str(result.miss_count),
                    str(result.decode_critical_misses),
                    f"{result.decode_critical_miss_rate:.3f}",
                    str(result.eviction_count),
                    str(result.decode_critical_evictions),
                    str(result.spill_count),
                    str(result.prefetch_count),
                    format_bytes(result.hbm_bytes_saved),
                    f"{p99_improvement:.1f}%",
                    f"{miss_reduction:.1f}%",
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def write_sweep_csv(rows: list[dict[str, object]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SWEEP_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
