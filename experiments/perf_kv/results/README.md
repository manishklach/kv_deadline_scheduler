# perf Results

Observed on WSL2 on 2026-06-17:

| Pattern | Miss rate |
|---|---:|
| sequential | 2.02% |
| KV-random | 47.44% |
| evicted-KV | 41.98% |

Interpretation:

- KV-like random access is much more miss-heavy than sequential access.
- The cold or evicted pattern is also far more miss-heavy than the sequential baseline.
- This is strong support for using a non-trivial simulated miss penalty for cold KV state.

See:

- [`perf_result.json`](perf_result.json)
- [../../docs/wsl_validation_2026_06_17.md](../../docs/wsl_validation_2026_06_17.md)
