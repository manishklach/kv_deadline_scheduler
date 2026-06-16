#!/usr/bin/env python3
"""Create hot, warm, and cold memory regions for external DAMON monitoring."""

from __future__ import annotations

import argparse
import os
import time


MB = 1024 * 1024
PAGE = 4096


def allocate_region(size_mb: int) -> bytearray:
    region = bytearray(size_mb * MB)
    for offset in range(0, len(region), PAGE):
        region[offset] = (offset // PAGE) & 0xFF
    return region


def touch_region(region: bytearray) -> None:
    for offset in range(0, len(region), PAGE):
        region[offset] = (region[offset] + 1) & 0xFF


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate hot, warm, and cold KV-like memory regions.")
    parser.add_argument("--hot-mb", type=int, default=128)
    parser.add_argument("--warm-mb", type=int, default=256)
    parser.add_argument("--cold-mb", type=int, default=512)
    parser.add_argument("--duration-sec", type=float, default=120.0)
    parser.add_argument("--hot-interval-ms", type=float, default=10.0)
    parser.add_argument("--warm-interval-ms", type=float, default=500.0)
    parser.add_argument("--cold-interval-ms", type=float, default=5000.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    hot = allocate_region(args.hot_mb)
    warm = allocate_region(args.warm_mb)
    cold = allocate_region(args.cold_mb)

    print(f"PID: {os.getpid()}", flush=True)
    print(
        f"Allocated hot={args.hot_mb}MB warm={args.warm_mb}MB cold={args.cold_mb}MB",
        flush=True,
    )
    print(
        "Access pattern: "
        f"hot every {args.hot_interval_ms}ms, "
        f"warm every {args.warm_interval_ms}ms, "
        f"cold every {args.cold_interval_ms}ms",
        flush=True,
    )

    start = time.monotonic()
    next_hot = start
    next_warm = start
    next_cold = start
    next_progress = start + 5.0
    end = start + args.duration_sec

    while time.monotonic() < end:
        now = time.monotonic()
        if now >= next_hot:
            touch_region(hot)
            next_hot = now + (args.hot_interval_ms / 1000.0)
        if now >= next_warm:
            touch_region(warm)
            next_warm = now + (args.warm_interval_ms / 1000.0)
        if now >= next_cold:
            touch_region(cold)
            next_cold = now + (args.cold_interval_ms / 1000.0)
        if now >= next_progress:
            elapsed = now - start
            print(f"Progress: {elapsed:.1f}s / {args.duration_sec:.1f}s", flush=True)
            next_progress = now + 5.0
        time.sleep(0.001)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
