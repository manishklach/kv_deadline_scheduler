# Kernel Patches

Three levels of kernel integration, from loadable module to RFC patch series.

| Patch | Type | Kernel interface | Requires kernel build? |
|---|---|---|---|
| `kv_intent_shrinker/` | Loadable `.ko` | shrinker, procfs | No (`insmod` on 6.x) |
| `kv_damon_scheme/` | DAMON extension | `damon_ctx`, `TRACE_EVENT` | No (`insmod` on 6.x) |
| `mm_kv_intent/` | Legacy prototype patch series | `mm/vmscan.c` | Yes |
| `mm_intent_rfc/` | RFC patch series | `mm/`, DAMON, observability, optional reclaim | Yes |

## Maturity Levels

### A. Loadable module prototypes

- `kv_intent_shrinker/`
- `kv_damon_scheme/`

These are experimental loadable-module prototypes. They demonstrate kernel-side policy shapes without requiring a full kernel rebuild, but they are kernel-version-dependent and not upstream-ready.

### B. RFC MM patch series

- `mm_intent_rfc/`

This is the current kernel-facing design track. It reframes the idea as generic Linux memory intent rather than a KV-specific kernel ABI. The patches are research-oriented RFC sketches, not upstream-ready patches.

The first compile-targeted RFC patch is a debugfs-only generic memory-intent registry. It does not change reclaim behavior.

### C. Future validated patch series

The eventual target is a pinned Linux version, with:

- `checkpatch.pl` validation
- `sparse` validation
- QEMU or bare-metal testing
- measurable behavior under pressure
- default-off policy changes until observability is proven

## Build Instructions

Build on bare metal or a QEMU VM with a Linux 6.x kernel and matching headers:

```bash
sudo apt install linux-headers-$(uname -r)
cd kernel_patches/kv_intent_shrinker
make
sudo insmod kv_intent_shrinker.ko
cat /proc/kv_intent/status
```

## Why These Patches Are Not Testable On WSL2

WSL2 does not support loading out-of-tree kernel modules, so `insmod` fails even when the code itself is correct.

To test these patches:

- use QEMU with a custom `6.6+` kernel build
- or use a bare-metal Linux machine with module loading enabled

The code in this directory is experimental and research-oriented. Some pieces are loadable-module prototypes; the upstream-style patch series is a design sketch that must be validated against a pinned Linux kernel version before any upstream-readiness claim.

## Design Direction

KV Deadline Scheduler maps KV semantics onto generic memory-intent classes. That distinction matters:

- repository-level language can stay KV-specific
- kernel-facing names should stay workload-neutral

Preferred generic classes for future kernel work include:

- `MM_INTENT_LATENCY_CRITICAL`
- `MM_INTENT_RECLAIMABLE`
- `MM_INTENT_PREFETCHABLE`
- `MM_INTENT_RECOMPUTE_OK`
- `MM_INTENT_BACKGROUND`

The current `mm_kv_intent/` directory is preserved as a legacy prototype. Prefer `mm_intent_rfc/` for the current kernel-facing design.
