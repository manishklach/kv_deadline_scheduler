# Illustrative Results Example

The table below is illustrative only. It is not a claimed benchmark result.

Actual numbers will vary with device type, filesystem, kernel I/O scheduler, cache warmth, free space, and host load.

| Mode | `ioprio` active | Critical reads | Background write MB/s | Critical p50 ms | Critical p95 ms | Critical p99 ms | Max critical ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| `baseline` | No | 18240 | 412.7 | 0.84 | 4.72 | 9.91 | 18.44 |
| `separated` | Yes | 18510 | 397.3 | 0.79 | 3.21 | 6.42 | 12.18 |

Illustrative interpretation:

- The separated mode gives up some background spill throughput.
- Critical read p95 and p99 improve because background writes are treated as lower-priority work.
- Whether this happens on a real system depends on the storage stack and whether Linux priority controls are honored.
