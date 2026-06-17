# Linux VM / Memory-Management Track

The I/O scheduler path handles KV after it becomes storage traffic.
The VM path decides whether KV should become storage traffic at all.

KV Deadline Scheduler operates above Linux VM. It classifies KV-like request-state by deadline, phase, priority, recompute cost, and spillability.

Linux VM decides:

- which pages remain resident
- which pages are reclaimed
- which pages are swapped or compressed
- which pages move across memory tiers
- which cold regions can be monitored and acted on

This is closer to MEXT-like architecture because MEXT-style systems observe memory hotness and move colder pages out of DRAM while trying to prefetch or promote likely-needed pages. Linux VM has similar architectural hooks through DAMON, reclaim, `madvise`, zswap or swap, and memory tiering.

KV Deadline Scheduler can supply intent such as:

- `DECODE_CRITICAL`
- near-deadline
- high-priority request
- cold spillable
- `recompute_ok`
- done or freeable

Linux VM supplies mechanisms such as:

- `madvise`
- DAMON and DAMOS
- MGLRU
- zswap and swap
- memory tiering, NUMA, and CXL
- memory cgroups

```text
KV request-state intent
        |
        v
VM intent mapping
        |
        v
madvise / DAMON / reclaim / zswap / memory tiering
        |
        v
resident DRAM vs reclaimed/swap/tiered memory
        |
        v
fault latency / p99 token latency impact
```

## Why This Track Exists

The I/O track asks what to do after KV spill or prefetch becomes storage I/O.

The VM track asks an earlier question: which KV-backed pages should stay resident, which are candidates for reclaim or pageout, and which should be treated as cold or freeable before storage scheduling even begins.

That makes the VM track the closer conceptual match for memory-expansion or memory-tiering systems.

## What This Track Is

- A research track for mapping KV intent to Linux VM mechanisms.
- A set of no-kernel-patch experiments using existing VM interfaces.
- A future path toward intent-aware reclaim or tiering research.

## What This Track Is Not

- Not a MEXT clone.
- Not a production memory tiering system.
- Not a kernel ABI proposal yet.
- Not real GPU HBM control.
- Not proof of LLM speedup.

## First-Stage Scope

This repository does not add a risky kernel patch, a KV-specific Linux ABI, or a production memory-management integration.

The first stage stays with existing Linux VM interfaces:

- `madvise` experiments for hot, cold, spillable, and freeable regions
- DAMON monitoring of KV-like hot and cold memory regions
- documentation for MGLRU, zswap, swap, and memory-tiering research directions

These experiments are approximations. `madvise` is advisory. DAMON availability depends on kernel configuration. None of this is precise HBM control or a production MEXT clone.

## First Experiments

- `madvise`-based KV region experiment.
- DAMON hot and cold region monitoring.
- MGLRU reclaim observation under synthetic KV-like pressure.
- zswap or swap observation for cold KV-like regions.

## Contents

- [docs/vm_vs_io_kernel_tracks.md](docs/vm_vs_io_kernel_tracks.md)
- [docs/damon_intent_bridge.md](docs/damon_intent_bridge.md)
- [docs/madvise_kv_experiment.md](docs/madvise_kv_experiment.md)
- [docs/mglru_reclaim_track.md](docs/mglru_reclaim_track.md)
- [docs/zswap_swap_track.md](docs/zswap_swap_track.md)
- [experiments/linux_vm_intent/README.md](experiments/linux_vm_intent/README.md)
- [experiments/damon_kv_hotness/README.md](experiments/damon_kv_hotness/README.md)
