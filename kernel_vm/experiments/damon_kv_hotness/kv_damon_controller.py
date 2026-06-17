#!/usr/bin/env python3
"""Monitor KV-like regions with DAMON sysfs and export hotness results."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path


MB = 1024 * 1024
PROT_READ = 1
PROT_WRITE = 2
MAP_PRIVATE = 2
MAP_ANONYMOUS = 0x20

libc = ctypes.CDLL(None, use_errno=True)
libc.mmap.restype = ctypes.c_void_p
libc.mmap.argtypes = [
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_longlong,
]
libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]


@dataclass
class RegionSpec:
    index: int
    address: int
    size_bytes: int
    pattern: str
    every_n: int
    nr_accesses: int = 0
    classification: str = "UNKNOWN"


def allocate_region(size_mb: int) -> tuple[ctypes.Array[ctypes.c_ubyte], int]:
    size_bytes = size_mb * MB
    address = libc.mmap(None, size_bytes, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0)
    if address in (0, ctypes.c_void_p(-1).value):
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))
    buffer_type = ctypes.c_ubyte * size_bytes
    buffer = buffer_type.from_address(address)
    return buffer, int(address)


def make_regions(count: int, size_mb: int) -> list[RegionSpec]:
    regions: list[RegionSpec] = []
    for index in range(count):
        _, buffer, address = allocate_region(size_mb)
        for offset in range(0, size_mb * MB, 4096):
            buffer[offset] = (index + offset // 4096) & 0xFF
        if index <= 1:
            pattern = "HOT"
            every_n = 1
        elif index <= 3:
            pattern = "WARM"
            every_n = 5
        else:
            pattern = "COLD"
            every_n = 0
        regions.append(
            RegionSpec(index=index, address=address, size_bytes=size_mb * MB, pattern=pattern, every_n=every_n)
        )
    return regions


def write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def configure_damon(admin_root: Path, pid: int, regions: list[RegionSpec], sample_us: int, aggr_us: int) -> Path:
    write_text(admin_root / "nr_kdamonds", "1\n")
    kdamond = admin_root / "kdamonds" / "0"
    contexts = kdamond / "contexts"
    write_text(kdamond / "state", "off\n")
    write_text(kdamond / "nr_contexts", "1\n")
    context = contexts / "0"
    write_text(context / "operations", "vaddr\n")
    intervals = context / "monitoring_attrs" / "intervals"
    write_text(intervals / "sample_us", f"{sample_us}\n")
    write_text(intervals / "aggr_us", f"{aggr_us}\n")
    write_text(intervals / "update_us", f"{aggr_us}\n")
    targets = context / "targets"
    write_text(context / "nr_targets", "1\n")
    target = targets / "0"
    write_text(target / "pid_target", f"{pid}\n")
    write_text(target / "nr_regions", f"{len(regions)}\n")
    regions_root = target / "regions"
    for region in regions:
        node = regions_root / str(region.index)
        write_text(node / "start", f"{region.address}\n")
        write_text(node / "end", f"{region.address + region.size_bytes}\n")
    write_text(kdamond / "state", "on\n")
    return kdamond


def infer_classification(accesses: int) -> str:
    if accesses >= 10:
        return "HOT"
    if accesses >= 3:
        return "WARM"
    return "COLD"


def poll_access_counts(target_regions: Path, regions: list[RegionSpec]) -> None:
    for region in regions:
        region_dir = target_regions / str(region.index)
        nr_accesses_path = region_dir / "nr_accesses"
        if nr_accesses_path.exists():
            raw = read_text(nr_accesses_path).split()
            try:
                region.nr_accesses = int(raw[0])
            except (IndexError, ValueError):
                region.nr_accesses = 0
        region.classification = infer_classification(region.nr_accesses)


def touch_region(region: RegionSpec, loop_index: int) -> None:
    if region.every_n == 0 or loop_index % region.every_n != 0:
        return
    pointer = (ctypes.c_ubyte * region.size_bytes).from_address(region.address)
    stride = 4096
    for offset in range(0, region.size_bytes, stride):
        pointer[offset] = (pointer[offset] + 1) & 0xFF


def print_table(regions: list[RegionSpec]) -> None:
    print("Region | Addr       | Size  | Pattern | DAMON nr_accesses | Classification")
    for region in regions:
        size_mb = region.size_bytes // MB
        print(
            f"{region.index:>6} | 0x{region.address:x} | {size_mb:>4}MB | "
            f"{region.pattern:<7} | {region.nr_accesses:>17} | {region.classification}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a DAMON-monitored KV-like hotness workload.")
    parser.add_argument("--regions", type=int, default=8)
    parser.add_argument("--region-mb", type=int, default=64)
    parser.add_argument("--duration-sec", type=int, default=30)
    parser.add_argument("--poll-sec", type=int, default=2)
    parser.add_argument("--sample-ms", type=int, default=5)
    parser.add_argument("--aggregate-ms", type=int, default=100)
    parser.add_argument("--sysfs-root", default="/sys/kernel/mm/damon/admin")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    admin_root = Path(args.sysfs_root)
    if not admin_root.exists():
        raise SystemExit(f"DAMON sysfs root not found: {admin_root}")
    if os.geteuid() != 0:
        raise SystemExit("Run with sudo so DAMON sysfs can be configured.")

    results_dir = Path(__file__).resolve().parent / "results"
    ensure_dir(results_dir)
    regions = make_regions(args.regions, args.region_mb)
    kdamond = configure_damon(
        admin_root,
        os.getpid(),
        regions,
        sample_us=args.sample_ms * 1000,
        aggr_us=args.aggregate_ms * 1000,
    )
    target_regions = kdamond / "contexts" / "0" / "targets" / "0" / "regions"

    print(f"Configured DAMON for PID {os.getpid()} with {len(regions)} regions.")
    print(f"Polling every {args.poll_sec}s for {args.duration_sec}s.")
    started = time.monotonic()
    iteration = 0
    try:
        while time.monotonic() - started < args.duration_sec:
            for region in regions:
                touch_region(region, iteration)
            poll_access_counts(target_regions, regions)
            print_table(regions)
            print("")
            iteration += 1
            time.sleep(args.poll_sec)
    finally:
        write_text(kdamond / "state", "off\n")

    payload = {
        "pid": os.getpid(),
        "duration_sec": args.duration_sec,
        "sample_ms": args.sample_ms,
        "aggregate_ms": args.aggregate_ms,
        "regions": [asdict(region) for region in regions],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "DAMON access counts are sampled from Linux sysfs and remain an experimental hotness proxy.",
    }
    out_path = results_dir / "damon_hotness_result.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
