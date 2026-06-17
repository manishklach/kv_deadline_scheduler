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
2. Apply the patch:

```bash
git am 0001-mm-experimental-memory-intent-debugfs-registry.patch
```

3. Enable `CONFIG_DEBUG_FS`
4. Enable `CONFIG_EXPERIMENTAL_MEMORY_INTENT` if the patch adds it
5. Build the kernel
6. Boot under QEMU or on a dedicated test machine

If developing on WSL, use WSL for patch authoring and QEMU or native Linux for runtime validation.

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
