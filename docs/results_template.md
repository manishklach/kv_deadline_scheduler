# Results Template

Use this template to record both simulation and Linux I/O benchmark runs.

## System

- CPU:
- Kernel:
- Storage:
- Filesystem:
- Python:
- Device scheduler:
- Test directory:

## KV Simulation Result

| Policy | P99 latency | Decode-critical misses | Evictions | Spills |
|---|---:|---:|---:|---:|
| LRU |  |  |  |  |
| HotCold |  |  |  |  |
| PredictiveHotness |  |  |  |  |
| IntentAware |  |  |  |  |
| DeadlineAware |  |  |  |  |

## I/O Priority Result

| Mode | Critical read p50 | p95 | p99 | Background MB/s | ioprio active |
|---|---:|---:|---:|---:|---:|
| baseline |  |  |  |  |  |
| separated |  |  |  |  |  |

## Notes

- cache state:
- device used:
- run duration:
- observed variability:
