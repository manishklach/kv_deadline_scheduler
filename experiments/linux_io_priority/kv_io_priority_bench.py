#!/usr/bin/env python3
"""Userspace I/O priority emulation benchmark for KV Deadline Scheduler.

This benchmark does not exercise a real LLM runtime. It emulates:

- decode-critical KV prefetch as small random reads
- cold KV spill as larger sequential writes
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import multiprocessing as mp
import os
import platform
import random
import sys
import time
from pathlib import Path
from typing import Any


MB = 1024 * 1024
KB = 1024

IOPRIO_WHO_PROCESS = 1
IOPRIO_CLASS_NONE = 0
IOPRIO_CLASS_RT = 1
IOPRIO_CLASS_BE = 2
IOPRIO_CLASS_IDLE = 3

LINUX_IOPRIO_SET_SYSCALL = {
    "x86_64": 251,
    "amd64": 251,
    "i386": 289,
    "i686": 289,
    "aarch64": 30,
    "arm64": 30,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Emulate KV prefetch reads and spill writes, then compare mixed "
            "versus priority-separated I/O behavior."
        )
    )
    parser.add_argument("--dir", required=True, help="Directory for test files.")
    parser.add_argument("--critical-mb", type=int, default=256)
    parser.add_argument("--background-mb", type=int, default=1024)
    parser.add_argument("--block-kb", type=int, default=128)
    parser.add_argument("--duration-sec", type=float, default=10.0)
    parser.add_argument(
        "--mode",
        choices=["baseline", "separated", "io_uring_sketch"],
        default="baseline",
    )
    parser.add_argument("--json-out", help="Optional path for JSON results.")
    return parser.parse_args()


def ensure_file(path: Path, size_bytes: int, pattern_byte: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size == size_bytes:
        return

    chunk = bytes([pattern_byte]) * (4 * MB)
    with path.open("wb") as fh:
        remaining = size_bytes
        while remaining > 0:
            to_write = min(len(chunk), remaining)
            fh.write(chunk[:to_write])
            remaining -= to_write
        fh.flush()
        os.fsync(fh.fileno())


def percentile(values_ms: list[float], pct: float) -> float:
    if not values_ms:
        return 0.0
    if len(values_ms) == 1:
        return values_ms[0]
    ordered = sorted(values_ms)
    rank = (len(ordered) - 1) * pct
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def linux_ioprio_set(class_id: int, data: int) -> tuple[bool, str | None]:
    if sys.platform != "linux":
        return False, "ioprio unavailable on non-Linux platforms"

    arch = platform.machine().lower()
    syscall_no = LINUX_IOPRIO_SET_SYSCALL.get(arch)
    if syscall_no is None:
        return False, f"unsupported architecture for ioprio syscall: {arch}"

    try:
        libc = ctypes.CDLL(None, use_errno=True)
    except OSError as exc:
        return False, f"failed to load libc: {exc}"

    mask = (class_id << 13) | data
    result = libc.syscall(syscall_no, IOPRIO_WHO_PROCESS, 0, mask)
    if result != 0:
        err = ctypes.get_errno()
        return False, os.strerror(err)
    return True, None


def maybe_apply_priority(role: str, mode: str) -> dict[str, Any]:
    info: dict[str, Any] = {
        "role": role,
        "mode": mode,
        "nice_delta_applied": 0,
        "ioprio_active": False,
        "warning": None,
    }
    if mode != "separated":
        return info

    try:
        if role == "background":
            os.nice(10)
            info["nice_delta_applied"] = 10
    except (AttributeError, OSError) as exc:
        info["warning"] = f"nice adjustment failed: {exc}"

    if role == "critical":
        ok, warning = linux_ioprio_set(IOPRIO_CLASS_BE, 0)
    else:
        ok, warning = linux_ioprio_set(IOPRIO_CLASS_IDLE, 0)

    info["ioprio_active"] = ok
    if warning and not info["warning"]:
        info["warning"] = f"ioprio inactive: {warning}"
    return info


def read_at(fd: int, size: int, offset: int) -> bytes:
    if hasattr(os, "pread"):
        return os.pread(fd, size, offset)
    os.lseek(fd, offset, os.SEEK_SET)
    return os.read(fd, size)


def write_at(fd: int, payload: bytes, offset: int) -> int:
    if hasattr(os, "pwrite"):
        return os.pwrite(fd, payload, offset)
    os.lseek(fd, offset, os.SEEK_SET)
    return os.write(fd, payload)


def critical_reader(
    file_path: str,
    file_size: int,
    block_size: int,
    duration_sec: float,
    mode: str,
    result_path: str,
) -> None:
    priority_info = maybe_apply_priority("critical", mode)
    latencies_ms: list[float] = []
    read_count = 0
    end_time = time.monotonic() + duration_sec
    max_offset = max(0, file_size - block_size)
    rng = random.Random(1337)
    fd = os.open(file_path, os.O_RDONLY)
    try:
        while time.monotonic() < end_time:
            if max_offset == 0:
                offset = 0
            else:
                block_index = rng.randint(0, max_offset // block_size)
                offset = block_index * block_size
            start = time.perf_counter()
            data = read_at(fd, block_size, offset)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            if not data:
                break
            latencies_ms.append(elapsed_ms)
            read_count += 1
    finally:
        os.close(fd)

    Path(result_path).write_text(
        json.dumps(
            {
                "kind": "critical",
                "priority": priority_info,
                "latencies_ms": latencies_ms,
                "read_count": read_count,
            }
        ),
        encoding="utf-8",
    )


def background_writer(
    file_path: str,
    file_size: int,
    write_size: int,
    duration_sec: float,
    mode: str,
    result_path: str,
) -> None:
    priority_info = maybe_apply_priority("background", mode)
    bytes_written = 0
    end_time = time.monotonic() + duration_sec
    max_offset = max(1, file_size)
    payload = b"S" * write_size
    offset = 0
    fd = os.open(file_path, os.O_RDWR)
    try:
        while time.monotonic() < end_time:
            if offset + write_size > max_offset:
                offset = 0
            written = write_at(fd, payload, offset)
            bytes_written += written
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)

    Path(result_path).write_text(
        json.dumps(
            {
                "kind": "background",
                "priority": priority_info,
                "bytes_written": bytes_written,
            }
        ),
        encoding="utf-8",
    )


def build_result(
    mode: str,
    start_time: float,
    end_time: float,
    critical_result: dict[str, Any],
    background_result: dict[str, Any],
) -> dict[str, Any]:
    latencies_ms = critical_result["latencies_ms"]
    duration = end_time - start_time
    ioprio_active = bool(
        critical_result["priority"]["ioprio_active"]
        or background_result["priority"]["ioprio_active"]
    )
    warnings = [
        msg
        for msg in [
            critical_result["priority"].get("warning"),
            background_result["priority"].get("warning"),
        ]
        if msg
    ]
    return {
        "mode": mode,
        "duration_sec": duration,
        "critical_read_count": critical_result["read_count"],
        "background_write_mbps": (
            background_result["bytes_written"] / MB / duration if duration > 0 else 0.0
        ),
        "critical_read_latency_ms": {
            "p50": percentile(latencies_ms, 0.50),
            "p95": percentile(latencies_ms, 0.95),
            "p99": percentile(latencies_ms, 0.99),
            "max": max(latencies_ms) if latencies_ms else 0.0,
        },
        "ioprio_active": ioprio_active,
        "priority_warnings": warnings,
    }


def print_summary(result: dict[str, Any]) -> None:
    latency = result["critical_read_latency_ms"]
    print(f"Mode: {result['mode']}")
    print(f"Duration: {result['duration_sec']:.2f} sec")
    print(f"Critical reads: {result['critical_read_count']}")
    print(f"Background write throughput: {result['background_write_mbps']:.2f} MB/s")
    print(f"Critical read p50: {latency['p50']:.3f} ms")
    print(f"Critical read p95: {latency['p95']:.3f} ms")
    print(f"Critical read p99: {latency['p99']:.3f} ms")
    print(f"Critical read max: {latency['max']:.3f} ms")
    print(f"ioprio active: {'yes' if result['ioprio_active'] else 'no'}")
    for warning in result["priority_warnings"]:
        print(f"Warning: {warning}")


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    base_dir = Path(args.dir)
    critical_path = base_dir / "critical_reads.dat"
    background_path = base_dir / "background_spills.dat"
    critical_size = args.critical_mb * MB
    background_size = args.background_mb * MB
    block_size = args.block_kb * KB
    write_size = max(block_size * 4, MB)

    ensure_file(critical_path, critical_size, pattern_byte=0x43)
    ensure_file(background_path, background_size, pattern_byte=0x53)

    critical_result_path = base_dir / "critical_result.json"
    background_result_path = base_dir / "background_result.json"
    start_time = time.monotonic()
    critical_process = mp.Process(
        target=critical_reader,
        args=(
            str(critical_path),
            critical_size,
            block_size,
            args.duration_sec,
            args.mode,
            str(critical_result_path),
        ),
    )
    background_process = mp.Process(
        target=background_writer,
        args=(
            str(background_path),
            background_size,
            write_size,
            args.duration_sec,
            args.mode,
            str(background_result_path),
        ),
    )

    critical_process.start()
    background_process.start()
    critical_process.join()
    background_process.join()
    end_time = time.monotonic()

    received = {
        "critical": json.loads(critical_result_path.read_text(encoding="utf-8")),
        "background": json.loads(background_result_path.read_text(encoding="utf-8")),
    }
    critical_result_path.unlink(missing_ok=True)
    background_result_path.unlink(missing_ok=True)

    return build_result(
        args.mode,
        start_time,
        end_time,
        received["critical"],
        received["background"],
    )


def main() -> int:
    args = parse_args()
    if args.mode == "io_uring_sketch":
        print(
            "io_uring mode: not yet implemented.\n"
            "Requires liburing and Python cffi/ctypes bindings.\n"
            "Planned for a future release.\n"
            "Run with --mode baseline or --mode separated instead."
        )
        raise SystemExit(0)
    if args.block_kb <= 0:
        raise SystemExit("--block-kb must be positive")
    if args.critical_mb <= 0 or args.background_mb <= 0:
        raise SystemExit("file sizes must be positive")
    if args.duration_sec <= 0:
        raise SystemExit("--duration-sec must be positive")

    result = run_benchmark(args)
    print_summary(result)

    if args.json_out:
        json_path = Path(args.json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
