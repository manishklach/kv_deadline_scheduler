# MGLRU Reclaim Track

MGLRU is Linux's newer page-reclaim mechanism. It improves reclaim behavior under memory pressure by tracking page generations instead of relying on simpler aging heuristics.

For KV Deadline Scheduler, the core question is:

Can runtime intent help reclaim avoid evicting decode-critical request-state?

## Why MGLRU Matters Here

MGLRU is directly relevant to the VM path because it influences which pages survive pressure and which pages are reclaimed.

That is close to the KV scheduling question:

- which regions should remain resident
- which regions are safe reclaim candidates
- whether hotness alone is enough

## First Experiments

- run `kv_madvise_experiment` under memory pressure
- compare with MGLRU enabled or disabled if the kernel allows it
- observe `pgscan`, `pgsteal`, PSI, major and minor faults, RSS, and access latency by region

The point is not to change reclaim policy yet. The point is to see whether VM signals and KV-like region intent produce measurable differences under pressure.

## Scope Notes

- No kernel patch is implemented here.
- The repository does not yet integrate with MGLRU internals.
- Exact MGLRU controls vary by kernel and distribution.
- These experiments should be treated as observational and exploratory.
