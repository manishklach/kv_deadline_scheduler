# io_uring Results

Observed on WSL2 on 2026-06-17:

| Metric | Value |
|---|---:|
| p50 us | 332.11 |
| p95 us | 1495.30 |
| p99 us | 2378.01 |
| mean us | 601.76 |

Observed sync comparison:

| Mode | p50 us | p95 us | p99 us | total ms |
|---|---:|---:|---:|---:|
| sync | 103.57 | 157.54 | 189.90 | 29.99 |
| `io_uring` | 332.11 | 1495.30 | 2378.01 | 154.05 |

Interpretation:

- The raw `io_uring` prototype is functional on this kernel.
- The current userspace implementation is slower than synchronous reads on this WSL storage path.

See:

- [`io_uring_result.json`](io_uring_result.json)
- [../../docs/wsl_validation_2026_06_17.md](../../docs/wsl_validation_2026_06_17.md)
