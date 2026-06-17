# v0.5.0

## Bug fixes

- Fixed all Windows absolute paths in markdown link references (`kernel_vm/README.md`, `README.md`, `docs/reproducibility.md`, `CONTRIBUTING.md`)
- Version bumped to `0.5.0`

## New features

- `io_uring_sketch` mode added to the Linux I/O priority benchmark
  (`experiments/linux_io_priority/kv_io_priority_bench.py`); it prints a clear not-yet-implemented message and exits cleanly
- `__version__` exported from the `kv_memory_intent` package

## What is still simulated

- All p50, p95, and p99 latency figures are from the policy simulator, not a real GPU runtime
- The `io_uring` benchmark remains userspace emulation on tmpfs or NVMe, not GPU HBM control
