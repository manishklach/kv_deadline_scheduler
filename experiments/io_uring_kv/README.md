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
