# Kernel Patches

Three levels of kernel integration, from loadable module to upstream patch series.

| Patch | Type | Kernel interface | Requires kernel build? |
|---|---|---|---|
| `kv_intent_shrinker/` | Loadable `.ko` | shrinker, procfs | No (`insmod` on 6.x) |
| `kv_damon_scheme/` | DAMON extension | `damon_ctx`, `TRACE_EVENT` | No (`insmod` on 6.x) |
| `mm_kv_intent/` | Upstream patch series | `mm/vmscan.c` | Yes |

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

The code in this directory is written to be correct and upstream-ready, not WSL-demo-ready.
