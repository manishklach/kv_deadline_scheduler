# I/O Priority Benchmark Results (WSL / tmpfs)

## Environment

- Platform: WSL2, Linux 6.x, virtualized block-backed environment
- Storage: WSL virtual disk and `/tmp`-backed benchmark directory
- Python: 3.12, stdlib only

## Results Summary

| metric | baseline (ioprio=off) | separated (ioprio=on) | delta |
|---|---:|---:|---:|
| p50 (ms) | 0.0199 | 0.0197 | -0.9% |
| p95 (ms) | 0.0493 | 0.0495 | +0.4% |
| p99 (ms) | 0.1576 | 0.1572 | -0.2% |
| max (ms) | 48.050 | 14.225 | -70.4% |
| bg MB/s | 527.69 | 513.62 | -14.07 MB/s |

## Interpretation

- p50 through p99 were nearly identical in this run, even though `ioprio` was active in separated mode.
- The `ioprio_set` path is still useful to test because it confirms the benchmark runs end-to-end and that priority changes are accepted by the guest kernel.
- Max latency was much lower in separated mode. That is the main positive signal from this run: the more urgent class may suppress the worst background-write spikes even when the rest of the distribution barely moves.
- These results are most informative as a baseline. The benchmark should be rerun on bare-metal Linux with a real NVMe-backed filesystem before drawing conclusions about KV-aware I/O prioritization.

## Next Steps

- Re-run on bare-metal Linux with NVMe and a real block device-backed directory
- Re-run with the benchmark directory pointed at a non-WSL storage target
- Use the new `--iterations` flag to average across multiple runs
- Cross-reference [../../docs/wsl_validation_2026_06_17.md](../../docs/wsl_validation_2026_06_17.md)
