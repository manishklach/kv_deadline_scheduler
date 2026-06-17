# I/O Priority Benchmark Results (WSL / tmpfs)

## Environment

- Platform: WSL2, Linux 6.x, virtualized block-backed environment
- Storage: WSL virtual disk and `/tmp`-backed benchmark directory
- Python: 3.12, stdlib only

## Results Summary

| metric | baseline (ioprio=off) | separated (ioprio=on) | delta |
|---|---:|---:|---:|
| p50 (ms) | 0.0705 | 0.0780 | +10.6% |
| p95 (ms) | 0.1733 | 0.1953 | +12.7% |
| p99 (ms) | 0.4391 | 0.4974 | +13.3% |
| max (ms) | 13.139 | 11.097 | -15.5% |
| bg MB/s | 1164.8 | 1024.7 | -140.1 MB/s |

## Interpretation

- p50 through p99 are slightly higher in separated mode. This is plausible on WSL or other virtualized storage stacks: the Linux kernel receives `ioprio` hints, but the host-side virtualization layer may not enforce meaningful priority boundaries for the guest's block traffic.
- The `ioprio_set` path is still useful to test because it confirms the benchmark runs end-to-end and that priority changes are accepted by the guest kernel.
- Max latency is lower in separated mode. That is the only positive signal in this run: the more urgent class may occasionally suppress the worst background-write spikes even when the rest of the latency distribution does not improve.
- These results are most informative as a baseline. The benchmark should be rerun on bare-metal Linux with a real NVMe-backed filesystem before drawing conclusions about KV-aware I/O prioritization.

## Next Steps

- Re-run on bare-metal Linux with NVMe and a real block device-backed directory
- Re-run with the benchmark directory pointed at a non-WSL storage target
- Use the new `--iterations` flag to average across multiple runs
