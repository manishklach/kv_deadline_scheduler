# THP Results

Observed on WSL2 on 2026-06-17:

| Metric | Value |
|---|---:|
| sequential MB/s, 4 KB pages | 7516.74 |
| sequential MB/s, THP | 11005.06 |
| random MPPS, 4 KB pages | 8.2218 |
| random MPPS, THP | 13.2713 |

Notes:

- This run showed a positive throughput signal for the THP-backed mapping.
- `AnonHugePages_kB` remained `0` in the wrapper observation, so the accounting signal is weaker than the throughput signal.

See:

- [`thp_alloc_result.json`](thp_alloc_result.json)
- [../../../../docs/wsl_validation_2026_06_17.md](../../../../docs/wsl_validation_2026_06_17.md)
