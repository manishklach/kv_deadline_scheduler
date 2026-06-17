# Design Notes

## Scope

This RFC track is experimental and research-oriented. It is not upstream-ready.

The immediate goal is not to change reclaim behavior. The immediate goal is to create a kernel-visible observability path for region-level memory intent so userspace experiments can compare:

- region hotness
- region intent
- reclaim pressure
- eventual policy recommendations

## Known Design Issues In The Legacy KV-Specific Patch Track

### PFN registration is fragile

PFNs are not a good first userspace interface:

- userspace normally sees virtual addresses
- `/proc/pagemap` access is often restricted
- PFNs are unstable under migration, compaction, and reclaim

Preferred future direction:

```text
<pid> <start_vaddr> <length> <intent_flags> <deadline_ns> <priority>
```

### Range lookup needs a real range data structure

Hashing by `start_pfn` and then probing with arbitrary `pfn` is insufficient for range lookup.

Better options:

- interval tree
- maple tree
- VMA annotations
- xarray for a page-granular prototype
- linear scan only for tiny prototypes

### Reclaim behavior change is too early

The first useful validation step is observability only:

1. registry
2. reporting
3. DAMON integration
4. optional policy

Changing `vmscan` before the reporting path is validated makes debugging harder and upstream review less credible.

### procfs is a prototype, not a stable ABI

For experiments, procfs or debugfs are acceptable.

For a real design, a stable ABI might eventually look more like:

- `madvise`
- `process_madvise`
- `prctl`
- or a clearly bounded `debugfs`/tracepoint experiment first

## Mapping KV Semantics To Generic Memory Intent

KV Deadline Scheduler should stay free to use workload-specific language in userspace.

Kernel-facing mapping should look like:

| KV meaning | Generic memory-intent class |
|---|---|
| decode-critical block | `MM_INTENT_LATENCY_CRITICAL` |
| cold spillable block | `MM_INTENT_RECLAIMABLE` |
| prefetch candidate | `MM_INTENT_PREFETCHABLE` |
| recompute-safe block | `MM_INTENT_RECOMPUTE_OK` |
| low-value background state | `MM_INTENT_BACKGROUND` |
