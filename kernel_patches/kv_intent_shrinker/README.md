# kv_intent_shrinker

`kv_intent_shrinker` is a loadable kernel module that registers a custom shrinker and a small procfs control plane at `/proc/kv_intent/`.

The module is the kernel-side analogue of the repository's `DeadlineAwarePolicy`: userspace registers logical KV-block intent, and the shrinker consults that metadata when deciding what is reclaimable.

## What The Module Does

- stores per-block KV intent metadata in the kernel
- exposes `/proc/kv_intent/register` and `/proc/kv_intent/unregister`
- exposes `/proc/kv_intent/status` as JSON lines
- registers a `struct shrinker`
- counts reclaimable blocks as non-pinned `COLD` or `WARM` blocks
- scans and removes the most reclaimable metadata entries first

The module does not directly free GPU memory or userspace buffers. It demonstrates how a kernel shrinker would consume intent metadata and rank reclaim candidates.

## Build

```bash
make KDIR=/path/to/kernel/build
```

## Load

```bash
sudo insmod kv_intent_shrinker.ko
```

## Use

```bash
echo "12345 5000 3 1048576" > /proc/kv_intent/register
cat /proc/kv_intent/status
echo "12345" > /proc/kv_intent/unregister
```

Input fields for `register`:

```text
object_id_hash deadline_us priority size_bytes
```

Priority values:

- `0` = `COLD`
- `1` = `WARM`
- `2` = `HOT`
- `3` = `DECODE_CRITICAL`

## Connection To The Python Simulator

The procfs interface mirrors a subset of `MemoryIntent` fields:

- `object_id_hash`
- `deadline_us`
- `priority`
- `pin_requested` is inferred for `DECODE_CRITICAL` in userspace or future interface extensions
- `size_bytes`

`kv_damon_to_intent.py` could later be extended to emit writes to `/proc/kv_intent/register` instead of only JSONL traces.

## Why It Is Not Testable On WSL2

WSL2 does not support loading out-of-tree modules, so `insmod` fails even when the module source is correct.

To test this module, use:

- a bare-metal Linux machine
- or QEMU with a custom `6.x` kernel and module loading enabled
