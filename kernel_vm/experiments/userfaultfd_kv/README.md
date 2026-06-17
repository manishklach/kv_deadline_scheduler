# userfaultfd KV Migration

`userfaultfd` is a good fit for KV migration emulation because it lets user space intercept page faults and decide how missing pages are populated. That is close to the control point we care about when modeling HBM-to-DRAM KV block movement.

In this track, the "HBM" region is initially missing. A fault handler copies pages from a pre-filled "DRAM" region into that address space, records migration latency, and reports how often decode-like accesses triggered migrations.

## Files

- `kv_uffd_migration.c`
  Reactive migration path: faults trigger `UFFDIO_COPY` from the DRAM backing region.
- `kv_uffd_prefetch.c`
  Adds a simple prefetch heuristic and compares fault-driven migration against proactively populated blocks.

## Build

```bash
cd kernel_vm/experiments/userfaultfd_kv
gcc -O2 -Wall -Wextra kv_uffd_migration.c -o kv_uffd_migration -lpthread
gcc -O2 -Wall -Wextra kv_uffd_prefetch.c -o kv_uffd_prefetch -lpthread
```

## Run

```bash
./kv_uffd_migration
./kv_uffd_prefetch
```

## What The Numbers Mean

- Migration latency is the time between a fault being observed and `UFFDIO_COPY` completing.
- That latency is a user-space proxy for the `miss_penalty_us` concept in the simulator.
- Prefetch hit rate is the fraction of predicted blocks already present before the next decode-like step.

## Scope

This is not real GPU memory control. It is a Linux user-space emulation of KV block miss handling and prefetch behavior.
