# io_uring KV Prefetch

`io_uring` matters for KV prefetch because it can submit and reap asynchronous reads with low userspace overhead. For a future spill-and-prefetch backend, that makes it a useful bridge between KV intent and Linux storage behavior.

This experiment uses raw syscalls through Python `ctypes` rather than `liburing`, so it stays portable inside this repository and does not require extra installs.

## Files

- `kv_io_uring_prefetch.py`
  Raw `io_uring_setup`, ring mapping, SQE submission, completion reaping, and latency reporting.
- `kv_io_uring_vs_sync.py`
  Side-by-side comparison of synchronous `pread` against the async `io_uring` path.

## Run

```bash
cd experiments/io_uring_kv
python3 kv_io_uring_prefetch.py
python3 kv_io_uring_vs_sync.py
```

## What The Numbers Mean

- Per-step latency is the time from submitting the predicted KV-block reads to reaping all completions.
- Lower p95 and p99 suggest a better prefetch path for near-deadline KV blocks.
- This remains a storage-side approximation, not real GPU HBM control.

## Observed On WSL2 (2026-06-17)

The raw `io_uring` path ran successfully after aligning the `IORING_OP_READ` opcode to the local Linux header ABI.

Observed result:

- `p50_us = 332.11`
- `p95_us = 1495.30`
- `p99_us = 2378.01`

Observed sync comparison:

- sync total time: `29.99 ms`
- `io_uring` total time: `154.05 ms`

That is an honest negative result for this environment: the current userspace `io_uring` prototype works, but it is slower than synchronous `pread` on this WSL storage stack and workload shape.

## Ring Structure

```text
submission queue head/tail ---> SQ ring entries ---> SQEs
                                          |
                                          v
                                  kernel executes reads
                                          |
                                          v
completion queue head/tail <--- CQ ring entries <--- CQEs
```

See also:

- [`results/io_uring_result.json`](results/io_uring_result.json)
- [../../docs/wsl_validation_2026_06_17.md](../../docs/wsl_validation_2026_06_17.md)
