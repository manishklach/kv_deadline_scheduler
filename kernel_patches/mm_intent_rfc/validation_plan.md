# Validation Plan

## Target Kernel

Choose and pin a specific Linux version first, for example:

- `6.8.y`
- or `6.10.y`

Do not treat the RFC patches as version-agnostic until they are validated against a specific tree.

## Validation Steps

1. Apply patches one at a time with `git am`
2. Run `checkpatch.pl`
3. Run `sparse` if available
4. Build the kernel or module set
5. Boot under QEMU
6. Tag regions from `kv_madvise_experiment`
7. Confirm `smaps`, proc, or `debugfs` observability reports intent
8. Run the DAMON workload and confirm intent appears alongside hot/cold observations
9. Only then enable the default-off reclaim policy patch

## Success Criteria

- patch 1 compiles cleanly on the pinned tree
- userspace can register memory intent by virtual-address range
- observability path shows registered intent without changing reclaim
- DAMON reporting can correlate hotness with intent
- reclaim policy remains disabled by default until measurements justify enabling it
