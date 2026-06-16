# DAMON + KV Intent Bridge

DAMON monitors memory-access patterns in Linux. DAMOS can apply access-aware operations based on those observations.

That makes DAMON useful for learning which regions appear hot or cold. But hotness alone is not the whole KV question.

KV Deadline Scheduler adds a second signal: request intent.

- DAMON can tell which regions are hot or cold.
- KV Deadline Scheduler can tell which regions are deadline-critical, high-priority, recompute-friendly, spillable, or done.

DAMON is Linux's data access monitoring framework. It can observe which memory regions are hot or cold with controlled overhead. DAMOS can apply access-aware operations.

The bridge is not just hotness. It is hotness plus request intent.

## Comparison

```text
MEXT-like system:
  infer hot/cold pages and move them between DRAM and flash

DAMON-only:
  observe hot/cold memory regions

KV Deadline Scheduler + DAMON:
  combine observed hotness with declared request-state intent
```

## Why This Matters

A region may look cold by recent access history and still matter a great deal if it belongs to decode-critical request-state that is about to be needed again.

Likewise, a region may be warm enough to appear worth protecting, but still be a good reclaim candidate if it is low-priority, spillable, or `recompute_ok`.

That is the main architectural reason to combine DAMON observations with scheduler-declared intent instead of relying on hotness alone.

## Example Intent Mapping

| DAMON observation | KV intent | Possible action |
|---|---|---|
| Hot | Decode-critical | Protect or keep resident |
| Cold | Low priority or spillable | Reclaim or page out |
| Cold | Near deadline soon | Prefetch or promote candidate |
| Warm | High recompute cost | Avoid aggressive reclaim |
| Any | Done or freeable | Drop or reclaim |

## Potential Future Directions

- protect decode-critical regions from reclaim
- reclaim or page out cold, low-priority KV regions
- prefetch near-deadline regions
- feed DAMON hotness statistics back into the policy simulator

## Scope Notes

- No kernel patch is implemented yet.
- This repository does not implement a DAMON control-plane integration.
- DAMON availability depends on kernel build and runtime configuration.
- DAMON sees virtual or physical access patterns, not KV semantics by itself.
- Intent must come from the runtime, profiler, or simulator layer.
- The current work is a research track, not a production VM policy.
