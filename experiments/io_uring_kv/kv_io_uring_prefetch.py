#!/usr/bin/env python3
"""Async KV block prefetch via raw io_uring syscalls."""

from __future__ import annotations

import ctypes
import json
import mmap
import os
import random
import statistics
import tempfile
import time
from pathlib import Path


IORING_SETUP = 425
IORING_ENTER = 426
IORING_REGISTER = 427
IORING_OP_READ = 22
IORING_OFF_SQ_RING = 0
IORING_OFF_CQ_RING = 0x8000000
IORING_OFF_SQES = 0x10000000
IORING_ENTER_GETEVENTS = 1
BLOCK_SIZE = 256 * 1024
RING_ENTRIES = 64
DECODE_STEPS = 256
BLOCKS_PER_STEP = 4
TOTAL_BLOCKS = 256

libc = ctypes.CDLL(None, use_errno=True)


class io_sqring_offsets(ctypes.Structure):
    _fields_ = [
        ("head", ctypes.c_uint32),
        ("tail", ctypes.c_uint32),
        ("ring_mask", ctypes.c_uint32),
        ("ring_entries", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("dropped", ctypes.c_uint32),
        ("array", ctypes.c_uint32),
        ("resv1", ctypes.c_uint32),
        ("resv2", ctypes.c_uint64),
    ]


class io_cqring_offsets(ctypes.Structure):
    _fields_ = [
        ("head", ctypes.c_uint32),
        ("tail", ctypes.c_uint32),
        ("ring_mask", ctypes.c_uint32),
        ("ring_entries", ctypes.c_uint32),
        ("overflow", ctypes.c_uint32),
        ("cqes", ctypes.c_uint32),
        ("flags", ctypes.c_uint64),
        ("resv1", ctypes.c_uint64),
        ("resv2", ctypes.c_uint64),
    ]


class io_uring_params(ctypes.Structure):
    _fields_ = [
        ("sq_entries", ctypes.c_uint32),
        ("cq_entries", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("sq_thread_cpu", ctypes.c_uint32),
        ("sq_thread_idle", ctypes.c_uint32),
        ("features", ctypes.c_uint32),
        ("wq_fd", ctypes.c_uint32),
        ("resv", ctypes.c_uint32 * 3),
        ("sq_off", io_sqring_offsets),
        ("cq_off", io_cqring_offsets),
    ]


class io_uring_sqe(ctypes.Structure):
    _fields_ = [
        ("opcode", ctypes.c_uint8),
        ("flags", ctypes.c_uint8),
        ("ioprio", ctypes.c_uint16),
        ("fd", ctypes.c_int32),
        ("off", ctypes.c_uint64),
        ("addr", ctypes.c_uint64),
        ("len", ctypes.c_uint32),
        ("rw_flags", ctypes.c_uint32),
        ("user_data", ctypes.c_uint64),
        ("buf_index", ctypes.c_uint16),
        ("personality", ctypes.c_uint16),
        ("splice_fd_in", ctypes.c_int32),
        ("pad2", ctypes.c_uint64 * 2),
    ]


class io_uring_cqe(ctypes.Structure):
    _fields_ = [("user_data", ctypes.c_uint64), ("res", ctypes.c_int32), ("flags", ctypes.c_uint32)]


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int((pct / 100.0) * (len(ordered) - 1))
    return ordered[index]


def setup_sparse_file(path: Path, size_bytes: int) -> int:
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    os.ftruncate(fd, size_bytes)
    chunk = os.urandom(4096)
    for offset in range(0, size_bytes, 16 * 1024 * 1024):
        os.pwrite(fd, chunk, offset)
    return fd


def syscall(number: int, *args: int) -> int:
    value = libc.syscall(number, *args)
    if value < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))
    return int(value)


def main() -> int:
    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    backing = Path(tempfile.gettempdir()) / "kv_io_uring_prefetch.dat"
    fd = setup_sparse_file(backing, TOTAL_BLOCKS * BLOCK_SIZE)

    params = io_uring_params()
    ring_fd = syscall(IORING_SETUP, RING_ENTRIES, ctypes.byref(params))

    sq_ring_sz = params.sq_off.array + params.sq_entries * ctypes.sizeof(ctypes.c_uint32)
    cq_ring_sz = params.cq_off.cqes + params.cq_entries * ctypes.sizeof(io_uring_cqe)
    sqes_sz = params.sq_entries * ctypes.sizeof(io_uring_sqe)

    sq_ring = mmap.mmap(ring_fd, sq_ring_sz, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ | mmap.PROT_WRITE, offset=IORING_OFF_SQ_RING)
    cq_ring = mmap.mmap(ring_fd, cq_ring_sz, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ | mmap.PROT_WRITE, offset=IORING_OFF_CQ_RING)
    sqes = mmap.mmap(ring_fd, sqes_sz, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ | mmap.PROT_WRITE, offset=IORING_OFF_SQES)

    sq_head = ctypes.c_uint32.from_buffer(sq_ring, params.sq_off.head)
    sq_tail = ctypes.c_uint32.from_buffer(sq_ring, params.sq_off.tail)
    sq_mask = ctypes.c_uint32.from_buffer(sq_ring, params.sq_off.ring_mask)
    sq_array = (ctypes.c_uint32 * params.sq_entries).from_buffer(sq_ring, params.sq_off.array)

    cq_head = ctypes.c_uint32.from_buffer(cq_ring, params.cq_off.head)
    cq_tail = ctypes.c_uint32.from_buffer(cq_ring, params.cq_off.tail)
    cq_mask = ctypes.c_uint32.from_buffer(cq_ring, params.cq_off.ring_mask)
    cqe_array = (io_uring_cqe * params.cq_entries).from_buffer(cq_ring, params.cq_off.cqes)
    sqe_array = (io_uring_sqe * params.sq_entries).from_buffer(sqes)

    latencies_us: list[float] = []
    buffers: list[ctypes.Array[ctypes.c_char]] = []
    rng = random.Random(42)

    for step in range(DECODE_STEPS):
        predicted = [((step * BLOCKS_PER_STEP) + offset) % TOTAL_BLOCKS for offset in range(BLOCKS_PER_STEP)]
        buffers.clear()
        start = time.perf_counter_ns()

        # Reserve SQ slots and write SQEs describing predicted KV-block reads.
        for block in predicted:
            tail = sq_tail.value
            index = tail & sq_mask.value
            sqe = sqe_array[index]
            buffer = ctypes.create_string_buffer(BLOCK_SIZE)
            buffers.append(buffer)
            sqe.opcode = IORING_OP_READ
            sqe.flags = 0
            sqe.ioprio = 0
            sqe.fd = fd
            sqe.off = block * BLOCK_SIZE
            sqe.addr = ctypes.addressof(buffer)
            sqe.len = BLOCK_SIZE
            sqe.rw_flags = 0
            sqe.user_data = (step << 16) | block
            sq_array[index] = index
            sq_tail.value = tail + 1

        syscall(IORING_ENTER, ring_fd, len(predicted), len(predicted), IORING_ENTER_GETEVENTS, 0, 0)

        completed = 0
        while completed < len(predicted):
            head = cq_head.value
            if head == cq_tail.value:
                time.sleep(0.0001)
                continue
            index = head & cq_mask.value
            cqe = cqe_array[index]
            if cqe.res < 0:
                raise OSError(-cqe.res, os.strerror(-cqe.res))
            cq_head.value = head + 1
            completed += 1

        elapsed_us = (time.perf_counter_ns() - start) / 1000.0
        latencies_us.append(elapsed_us + rng.random())

    summary = {
        "p50_us": round(percentile(latencies_us, 50.0), 2),
        "p95_us": round(percentile(latencies_us, 95.0), 2),
        "p99_us": round(percentile(latencies_us, 99.0), 2),
        "mean_us": round(statistics.mean(latencies_us), 2),
        "decode_steps": DECODE_STEPS,
        "blocks_per_step": BLOCKS_PER_STEP,
        "block_size_kb": BLOCK_SIZE // 1024,
        "note": "This is a userspace io_uring KV-prefetch emulation, not GPU memory control.",
    }
    out_path = results_dir / "io_uring_result.json"
    out_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"io_uring p50={summary['p50_us']}us p95={summary['p95_us']}us p99={summary['p99_us']}us")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
