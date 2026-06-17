#!/usr/bin/env python3
"""Compare synchronous reads against raw io_uring KV prefetch."""

from __future__ import annotations

import json
import os
import random
import statistics
import subprocess
import tempfile
import time
from pathlib import Path


BLOCK_SIZE = 256 * 1024
TOTAL_BLOCKS = 256
DECODE_STEPS = 256
BLOCKS_PER_STEP = 4


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    index = int((pct / 100.0) * (len(ordered) - 1))
    return ordered[index]


def sync_run(path: Path) -> dict[str, float]:
    fd = os.open(path, os.O_RDONLY)
    latencies: list[float] = []
    start_total = time.perf_counter_ns()
    for step in range(DECODE_STEPS):
        start = time.perf_counter_ns()
        for offset in range(BLOCKS_PER_STEP):
            block = ((step * BLOCKS_PER_STEP) + offset) % TOTAL_BLOCKS
            os.pread(fd, BLOCK_SIZE, block * BLOCK_SIZE)
        latencies.append((time.perf_counter_ns() - start) / 1000.0)
    total_ms = (time.perf_counter_ns() - start_total) / 1_000_000.0
    os.close(fd)
    return {
        "p50_us": percentile(latencies, 50.0),
        "p95_us": percentile(latencies, 95.0),
        "p99_us": percentile(latencies, 99.0),
        "total_ms": total_ms,
    }


def main() -> int:
    backing = Path(tempfile.gettempdir()) / "kv_io_uring_prefetch.dat"
    if not backing.exists():
        fd = os.open(backing, os.O_CREAT | os.O_RDWR, 0o644)
        os.ftruncate(fd, TOTAL_BLOCKS * BLOCK_SIZE)
        os.close(fd)

    sync_stats = sync_run(backing)
    script = Path(__file__).resolve().with_name("kv_io_uring_prefetch.py")
    subprocess.run(["python3", str(script)], check=True)
    async_stats = json.loads((Path(__file__).resolve().parent / "results" / "io_uring_result.json").read_text(encoding="utf-8"))

    speedup = sync_stats["total_ms"] / max(async_stats.get("mean_us", 1.0) * DECODE_STEPS / 1000.0, 0.001)
    print("| Mode | p50 us | p95 us | p99 us | total ms |")
    print("|---|---:|---:|---:|---:|")
    print(f"| sync | {sync_stats['p50_us']:.2f} | {sync_stats['p95_us']:.2f} | {sync_stats['p99_us']:.2f} | {sync_stats['total_ms']:.2f} |")
    print(f"| io_uring | {async_stats['p50_us']:.2f} | {async_stats['p95_us']:.2f} | {async_stats['p99_us']:.2f} | {(async_stats['mean_us'] * DECODE_STEPS / 1000.0):.2f} |")
    print(f"| speedup | - | - | - | {speedup:.2f} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
