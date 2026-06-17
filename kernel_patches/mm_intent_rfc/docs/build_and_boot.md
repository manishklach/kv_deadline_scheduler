# Build And Boot

Target kernel:

- Linux `6.8.y` initially

Milestone:

- RFC v0 observability only

## Scope

- generic memory-intent registry
- debugfs registration interface
- debugfs dump interface
- no reclaim changes
- no stable ABI
- no production claim

## Build Steps

1. Clone a Linux `6.8.y` tree
2. Apply all four patches in order:

```bash
git am ../kernel_patches/mm_intent_rfc/patches/*.patch
```

3. Enable `CONFIG_DEBUG_FS`
4. Enable `CONFIG_EXPERIMENTAL_MEMORY_INTENT` and `CONFIG_EXPERIMENTAL_MEMORY_INTENT_PROC` if the patches add them
5. (Optional) Enable `CONFIG_EXPERIMENTAL_MEMORY_INTENT_RECLAIM` for reclaim experiments -- default-off by design
6. Build the kernel
7. Boot under QEMU or on a dedicated test machine

If developing on WSL, use WSL for patch authoring and QEMU or native Linux for runtime validation.

Helper scripts in this repository:

- `scripts/apply_patch1_to_linux_tree.sh <linux-tree>`
- `scripts/qemu_smoke_boot.sh <linux-tree>`

The smoke boot helper builds a tiny initramfs, boots the patched kernel in QEMU, mounts `debugfs`, writes one registration line for PID `1`, and prints the resulting `dump` output.

## Runtime Setup

Mount debugfs:

```bash
mount -t debugfs none /sys/kernel/debug
```

Verify:

```bash
ls /sys/kernel/debug/mm_intent
```

Expected files:

- `register`
- `dump`
- `clear`

Validated example:

```text
mm_intent boot ok
mm_intent dump begin
1 0x100000 0x102000 0x1 1000000 90
mm_intent dump end
```
