# mm_intent_rfc

This directory is the current kernel-facing RFC track for generic Linux memory intent.

Target kernel:

- Linux `6.8.12` validated for RFC patch 0001
- Linux `6.8.y` remains the initial pinned family for this track

Milestone:

- v0 RFC observability only

Scope:

- generic memory-intent registry
- debugfs registration interface
- debugfs dump interface
- no reclaim changes
- no stable ABI
- no production claim

Current validation status:

- patch `0001` now compiles on Linux `6.8.12`
- a patched `6.8.12` kernel has been booted in QEMU
- `debugfs` was mounted and `/sys/kernel/debug/mm_intent/` was present
- a virtual-address range was registered and successfully dumped back

The design goal is to keep kernel-facing names workload-neutral. KV Deadline Scheduler remains the motivating workload, but Linux MM should not grow a KV-specific ABI unless the semantics prove broadly reusable.

## Why Generic Memory Intent Is Better Than KV-Specific Kernel ABI

Linux MM will likely accept generic concepts more readily than application-specific ones.

Examples:

- `MM_INTENT_LATENCY_CRITICAL`
- `MM_INTENT_RECLAIMABLE`
- `MM_INTENT_PREFETCHABLE`
- `MM_INTENT_RECOMPUTE_OK`
- `MM_INTENT_BACKGROUND`

KV Deadline Scheduler can map:

- decode-critical KV blocks -> `MM_INTENT_LATENCY_CRITICAL`
- cold spill candidates -> `MM_INTENT_RECLAIMABLE`
- blocks safe to reconstruct -> `MM_INTENT_RECOMPUTE_OK`

## Patch Order

1. Registry only
2. Observability through proc, `smaps`, or `debugfs`
3. DAMON reporting integration
4. Optional reclaim scaffolding, default off

That order is intentional. Observability comes first. Actual reclaim behavior change comes last.

Patch `0004` is currently scaffolding only. It keeps the enable-state plumbing compile-targeted, but it does not yet make reclaim decisions because owner attribution and reverse mapping from `struct page` to registered userspace ranges are still unresolved research problems.

## Preferred Interface Direction

The current RFC direction prefers:

```text
<pid> <start_vaddr> <length> <intent_flags> <deadline_ns> <priority>
```

over PFN-based registration.

Why:

- userspace knows virtual addresses, not PFNs
- PFNs can change due to migration, compaction, reclaim, and NUMA balancing
- `/proc/pagemap` is restricted on many systems
- VMA or range-level annotation is more natural for userspace workloads

## Files

- `design_notes.md`
- `validation_plan.md`
- `docs/build_and_boot.md`
- `userspace/`
- `scripts/validate_debugfs_interface.sh`
- `scripts/apply_patch1_to_linux_tree.sh`
- `scripts/qemu_smoke_boot.sh`
- `patches/0001-mm-experimental-memory-intent-debugfs-registry.patch`
- `patches/0002-mm-proc-expose-memory-intent-observability.patch`
- `patches/0003-mm-damon-report-memory-intent-for-monitored-regions.patch`
- `patches/0004-mm-vmscan-experimental-intent-aware-reclaim-default-off.patch`
