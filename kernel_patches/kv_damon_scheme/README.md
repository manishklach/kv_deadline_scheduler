# kv_damon_scheme

`kv_damon_scheme` sketches a DAMON behavior driver that translates `nr_accesses` directly into KV-style priority classes and logs those classifications through a tracepoint.

This is a kernel-module representation of the repository's user-space DAMON-to-intent bridge.

## DAMON Extension Points

Relevant DAMON hooks on modern kernels include:

- `struct damon_ctx`
- `struct damon_target`
- `struct damon_region`
- `struct damos`
- sysfs-driven scheme configuration under `CONFIG_DAMON_SYSFS`
- tracepoints for exporting region-level decisions

This module does not add a new upstream `enum damos_action` value directly. Instead, it documents the intended extension:

```c
/* Intended new action: DAMOS_MARK_KV_INTENT = DAMOS_ACTION_LRU_PRIO + 1 */
```

## How This Fits Into The DAMON Pipeline

1. DAMON samples region access counts.
2. `kv_damon_apply_scheme()` classifies `nr_accesses`.
3. The module emits `kv_intent_classified` trace events.
4. Future userspace tooling can ingest that trace stream and forward it into the Python intent pipeline.

## Build

```bash
make KDIR=/path/to/kernel/build
```

## Load

```bash
sudo insmod kv_damon_scheme.ko
```

## Tracepoint Consumption

Read the tracepoint with tools such as:

```bash
sudo trace-cmd record -e kv_intent:kv_intent_classified
sudo perf record -e kv_intent:kv_intent_classified
```

## sysfs Registration Note

The module code is written so that the actual scheme application logic is isolated in `kv_damon_apply_scheme()`. On a real Linux system with DAMON sysfs support and a matching kernel integration point, that function can be wired into a sysfs-defined scheme pipeline.

## Connection To `kv_damon_to_intent.py`

The tracepoint output matches the data that the Python converter already wants:

- region start and end
- observed `nr_accesses`
- derived KV-style priority

That makes the tracepoint stream a natural feeder for the Python intent pipeline.
