# WSL Validation Snapshot (2026-06-17)

This document records what was actually exercised on the author's WSL2 environment and what remained blocked by kernel or privilege constraints.

## Environment

| Item | Value |
|---|---|
| Platform | WSL2 |
| Kernel | `6.6.87.2-microsoft-standard-WSL2+` |
| Python | `3.12.3` |
| GCC | `13.3.0` |
| THP mode | `always [madvise] never` |
| `perf_event_paranoid` | `2` |
| `vm.unprivileged_userfaultfd` | `0` |
| DAMON sysfs | not exposed at `/sys/kernel/mm/damon/admin` |

## Status Summary

| Track | Status on this WSL | Evidence |
|---|---|---|
| Policy sweep | Ran successfully | `examples/results/sweep_summary.json` |
| Linux I/O priority | Ran successfully | `experiments/linux_io_priority/results/results_baseline_wsl.json`, `results_separated_wsl.json` |
| `madvise` VM intent | Ran successfully with limited advice support | `kernel_vm/experiments/linux_vm_intent/results/README.md` |
| THP | Ran successfully | `kernel_vm/experiments/thp_kv/results/thp_alloc_result.json` |
| `perf_event_open` | Ran successfully | `experiments/perf_kv/results/perf_result.json` |
| raw `io_uring` | Ran successfully | `experiments/io_uring_kv/results/io_uring_result.json` |
| DAMON | Blocked by missing sysfs interface | controller exits with `DAMON sysfs root not found` |
| `userfaultfd` | Blocked by privilege policy | `vm.unprivileged_userfaultfd = 0`, no non-interactive `sudo` |

## Key Observations

### Policy Sweep

The recalibrated sweep now creates real HBM pressure and shows policy separation:

- `deadline_pressure`: `lru` `dc_miss_rate = 0.04494`
- `deadline_pressure`: `intent` `dc_miss_rate = 0.00281`
- `deadline_pressure`: `deadline` `dc_miss_rate = 0.00281`

This is still simulated, but it is now meaningfully pressureful instead of fitting entirely in HBM.

### Linux I/O Priority

Observed on `/tmp` in WSL:

| Metric | Baseline | Separated |
|---|---:|---:|
| p50 ms | 0.0199 | 0.0197 |
| p95 ms | 0.0493 | 0.0495 |
| p99 ms | 0.1576 | 0.1572 |
| max ms | 48.05 | 14.22 |
| background MB/s | 527.69 | 513.62 |
| `ioprio` active | no | yes |

Interpretation:

- Guest-visible `ioprio` worked.
- Median and p99 were similar.
- Worst-case latency improved materially in separated mode.
- This is a useful signal, but still a virtualized-storage result rather than a bare-metal NVMe claim.

### `madvise`

Observed behavior:

- `MADV_WILLNEED` on the hot region was accepted.
- `MADV_COLD`, `MADV_PAGEOUT`, and `MADV_DONTNEED` returned `EINVAL` in this WSL run.
- RSS remained effectively unchanged.

Interpretation:

- The experiment harness runs.
- This WSL kernel does not expose reclaim semantics strongly enough for the advisory cold/pageout path to be informative.

### THP

Observed result file:

- `seq_normal_mb_s = 7516.74`
- `seq_thp_mb_s = 11005.06`
- `random_normal_mpps = 8.2218`
- `random_thp_mpps = 13.2713`

Interpretation:

- This run showed a positive throughput signal for the THP-backed region.
- `smaps` still reported `AnonHugePages_kB = 0` in the Python wrapper context, so treat this as a useful but not definitive huge-page accounting signal.

### `perf_event_open`

Observed miss rates:

| Pattern | Miss rate |
|---|---:|
| sequential | 2.02% |
| KV-random | 47.44% |
| evicted-KV | 41.98% |

Interpretation:

- KV-random and evicted-KV access patterns are much more miss-heavy than sequential access.
- This supports the simulator's use of a non-trivial miss penalty for cold or poorly placed KV state.

### raw `io_uring`

Observed `io_uring` result:

- `p50_us = 332.11`
- `p95_us = 1495.30`
- `p99_us = 2378.01`

Observed sync-vs-`io_uring` comparison:

| Mode | p50 us | p95 us | p99 us | total ms |
|---|---:|---:|---:|---:|
| sync | 103.57 | 157.54 | 189.90 | 29.99 |
| `io_uring` | 332.11 | 1495.30 | 2378.01 | 154.05 |

Interpretation:

- The raw `io_uring` implementation is functional on this kernel after aligning the opcode to the local ABI.
- On this WSL storage stack and workload shape, the synchronous path was faster than the naive userspace `io_uring` emulation.
- That is still a useful outcome: it means the mechanism works, but the current queueing approach is not yet beneficial here.

## Blocked Tracks

### DAMON

Observed command:

```bash
python3 kernel_vm/experiments/damon_kv_hotness/kv_damon_controller.py
```

Observed result:

```text
DAMON sysfs root not found: /sys/kernel/mm/damon/admin
```

Interpretation:

- DAMON cannot be validated on this machine because the needed sysfs control interface is absent.

### `userfaultfd`

Observed environment:

```text
vm.unprivileged_userfaultfd = 0
sudo: a password is required
```

Interpretation:

- The experiment code is present and compiles, but this session cannot elevate privileges to enable `userfaultfd`.
- Treat this as an environment block, not a result about the mechanism itself.

## Takeaway

This repository now has both:

- simulated policy evidence under real HBM pressure
- partial real Linux evidence for I/O, THP, perf, and `madvise` behavior on WSL

The strongest real-system signals from this snapshot are:

- separated I/O reduced worst-case read latency in the guest
- THP-backed access showed better throughput in this run
- KV-random and evicted access patterns had much higher cache-miss rates than sequential access

The main missing pieces on this machine are DAMON and `userfaultfd`, both blocked by environment capabilities rather than by repository structure.
