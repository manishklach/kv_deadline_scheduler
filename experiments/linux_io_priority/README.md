# Linux I/O Priority Emulation Benchmark

This benchmark is a Phase 1 userspace experiment for the kernel-facing KV Deadline Scheduler research track.

It does not test LLM inference directly. It emulates a future KV spill and prefetch backend:

- Critical reads stand for decode-critical KV prefetch.
- Background writes stand for cold KV spill.

The goal is to test whether KV intent can be mapped to userspace I/O priority separation before touching kernel schedulers.

There is no kernel patch here. This is an emulation of KV spill and prefetch I/O classes.

## What It Measures

The benchmark creates two files in a configurable directory:

- `critical_reads.dat`
- `background_spills.dat`

It then runs two concurrent workloads:

- Small random reads against `critical_reads.dat`
- Larger sequential writes against `background_spills.dat`

Two modes are supported:

- `baseline`
  Critical reads and background writes run with the same scheduling behavior.
- `separated`
  The benchmark tries to emulate KV-aware separation by placing critical reads and background writes in different worker processes and, on Linux, attempting best-effort `ioprio` separation. If `ioprio` is unavailable or fails, the benchmark continues with a warning.

## Relationship to KV Deadline Scheduler

KV Deadline Scheduler models deadline-aware handling of KV request-state before it becomes storage I/O.

This benchmark sits later in the stack. It asks a narrower question: if decode-critical KV prefetch and cold KV spill are mapped onto different userspace I/O classes, does critical read tail latency improve under write pressure?

It is an emulation of KV-aware I/O classes, not a production scheduler.

## Example Commands

```bash
python experiments/linux_io_priority/kv_io_priority_bench.py --mode baseline --duration-sec 10 --dir /tmp/kvio
python experiments/linux_io_priority/kv_io_priority_bench.py --mode separated --duration-sec 10 --dir /tmp/kvio
```

Optional JSON output:

```bash
python experiments/linux_io_priority/kv_io_priority_bench.py \
  --mode separated \
  --duration-sec 10 \
  --dir /tmp/kvio \
  --json-out /tmp/kvio/results.json
```

Use JSON output for reproducibility and side-by-side result capture across runs.

## Planned: `io_uring` Mode

A future `--mode io_uring_sketch` will use `io_uring` for async I/O to better model NVMe prefetch latency for KV blocks.

This requires `liburing` ([github.com/axboe/liburing](https://github.com/axboe/liburing)).

Currently not implemented; use `--mode baseline` or `--mode separated`.

## Notes on Interpretation

- Results depend heavily on filesystem, NVMe or SSD behavior, kernel version, cache state, mount options, and permissions.
- No root privileges are required by default.
- For stronger signal, run on Linux with a real NVMe device and relatively cold cache state.
- On non-Linux systems, the benchmark still runs, but `ioprio` separation is disabled.
