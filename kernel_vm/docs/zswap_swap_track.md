# zswap / swap Track

zswap is a compressed RAM cache in front of the swap device.

Conceptually, this maps well to the idea of a cheaper or slower memory tier before flash-backed storage.

That makes it relevant for cold KV-like regions that are no longer decode-critical but may still be worth keeping in a compressed intermediate tier before full swap I/O.

## Why This Track Matters

Cold KV regions could be candidates for compression or pageout rather than immediate protection in fast memory.

Potential experiments:

- enable zswap
- run a synthetic KV-like memory pressure workload
- mark cold regions with `MADV_COLD` or `MADV_PAGEOUT`
- observe:
- swap-ins and swap-outs
- zswap pool statistics
- major-fault latency
- access latency for cold versus hot regions
- CPU overhead

## Research Question

Can cold or `recompute_ok` KV-like regions tolerate compressed or swapped storage better than near-deadline or decode-critical regions?

## Caveats

- zswap trades CPU time for reduced swap I/O.
- It is not KV-aware by default.
- Behavior depends on memory pressure and swap configuration.
- This repository does not yet automate zswap setup or interpretation.
