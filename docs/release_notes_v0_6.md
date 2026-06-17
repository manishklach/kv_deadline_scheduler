# v0.6.0

## Summary

This release expands KV Deadline Scheduler from a simulator-plus-experiments repo into a broader Linux memory-systems research artifact.

The biggest additions are:

- real WSL-backed validation notes for userspace and VM-path experiments
- new kernel-facing experiment tracks for THP, perf counters, raw `io_uring`, and kernel patch design
- a generic `mm_intent_rfc` track that reframes the Linux MM work as workload-neutral memory intent instead of a KV-specific kernel ABI

## Highlights

### Pressure-calibrated simulator results

The benchmark sweep now runs with pressureful defaults and emits metadata with each result set.

Representative result:

- `deadline_pressure` `dc_miss_rate`
  - `lru = 0.04494`
  - `intent = 0.00281`
  - `deadline = 0.00281`

This restores the core signal the project is meant to demonstrate: semantic policies protect the right request-state under pressure better than generic recency heuristics.

### Real Linux experiment results captured in-repo

This release records actual WSL2 runs for:

- Linux I/O priority benchmark
- `madvise` VM intent experiment
- THP allocation experiment
- `perf_event_open` cache-miss experiment
- raw `io_uring` prefetch prototype

The new validation snapshot is documented in:

- `docs/wsl_validation_2026_06_17.md`

Important outcomes:

- separated I/O reduced worst-case critical-read latency on WSL
- THP-backed access showed a positive throughput signal in the observed run
- KV-random and evicted patterns had much higher cache-miss rates than sequential access
- DAMON and `userfaultfd` remained environment-limited on this machine and are documented honestly as such

### Kernel VM and patch tracks matured

The repo now contains:

- `kernel_vm/` experiment tracks for `madvise`, DAMON, THP, and `userfaultfd`
- `kernel_patches/` for loadable-module prototypes and RFC patch-series design

The kernel patch story was also cleaned up:

- old KV-specific MM patches are preserved as a legacy prototype
- the current RFC lane is now `kernel_patches/mm_intent_rfc/`
- the first compile-targeted RFC milestone is now a debugfs-only, observability-first memory-intent registry aimed at Linux `6.8.y`

## New Kernel-Facing Additions

### Loadable module prototypes

- `kernel_patches/kv_intent_shrinker/`
- `kernel_patches/kv_damon_scheme/`

These demonstrate kernel-side policy shapes, but are explicitly labeled as experimental and not upstream-ready.

### RFC MM lane

- `kernel_patches/mm_intent_rfc/`

This track now emphasizes:

- generic memory intent, not KV-specific ABI naming
- virtual-address ranges, not PFN registration
- debugfs-only registration for RFC v0
- observability before reclaim policy

Added RFC v0 support files:

- `userspace/mm_intent_register.c`
- `docs/build_and_boot.md`
- `scripts/validate_debugfs_interface.sh`

### WSL-specific development guidance

A new document:

- `docs/wsl_development.md`

explains what WSL is good for, what it is not good for, and why kernel patch validation should happen on native Linux or QEMU rather than being inferred from WSL alone.

## Documentation Improvements

This release also improves the public-facing documentation:

- README now includes WSL guidance for experiments and kernel patch validation
- kernel patch maturity is described more honestly
- per-experiment result notes are checked into the repo
- RFC design notes and validation plans are now explicit

## Compatibility And Scope Notes

- the Python package name remains `kv_memory_intent`
- CLI and Python package behavior remain compatible
- `53` tests still pass
- the kernel patch material remains experimental, research-oriented, and not production-ready
- no release in this series claims real GPU HBM control or upstream Linux MM acceptance

## Suggested Next Step

The next kernel-facing milestone should expose generic memory intent through `smaps` or another observability surface before any DAMON policy or reclaim behavior work is enabled.
