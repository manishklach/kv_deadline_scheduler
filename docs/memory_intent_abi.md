# Memory Intent ABI

## Overview

The Python dataclasses in this repository are the authoritative prototype schema today. This document sketches how that schema could eventually become a lower-level ABI for trace export, advisory control messages, or a memory-tiering daemon interface.

## Python Prototype

The core object is `MemoryIntent`, which describes one semantic memory object, currently focused on KV-cache blocks. Important fields include:

- `object_id`: stable object identifier
- `request_id`: owning request or session
- `block_id`: block index within request state
- `object_type`: KV cache, weights, activations, or scratch
- `phase`: prefill, decode, verify, rollback, done, or idle
- `priority`: decode-critical, hot, warm, or cold
- `allowed_tiers`: legal memory placement targets
- `current_tier`: current placement
- `size_bytes`: object size
- `request_priority`: scheduler-level importance
- `recency_score`: normalized recency hint
- `deadline_us`: urgency hint
- `expected_reuse_window_tokens`: distance to likely reuse
- `recompute_cost_us`: how expensive miss recovery is
- `spill_cost_us`: movement cost hint
- `compression_ok`, `recompute_ok`, `prefetch_ok`, `pin_requested`: policy knobs
- `is_draft`, `is_committed`: speculative decoding state

## C-Style ABI Sketch

```c
typedef struct memory_intent {
    uint64_t object_id;
    uint64_t request_id;
    uint32_t block_id;

    uint16_t object_type;
    uint16_t phase;
    uint16_t priority;
    uint16_t allowed_tiers;
    uint16_t current_tier;

    uint64_t size_bytes;

    uint16_t request_priority;
    float    recency_score;

    uint32_t deadline_us;
    uint32_t expected_reuse_window_tokens;
    uint32_t recompute_cost_us;
    uint32_t spill_cost_us;

    uint8_t compression_ok;
    uint8_t recompute_ok;
    uint8_t prefetch_ok;
    uint8_t pin_requested;

    uint8_t is_draft;
    uint8_t is_committed;
} memory_intent_t;
```

## Field Notes

- `object_id` and `request_id` are shown as integers here for ABI compactness. The Python prototype keeps them as strings for readability.
- `allowed_tiers` can be represented as a bitmask.
- `request_priority`, `deadline_us`, and `expected_reuse_window_tokens` are intentionally simple so runtimes can emit them cheaply.
- `pin_requested` is a semantic hint, not a guarantee.

## Event ABI Sketch

```c
typedef struct memory_intent_event {
    uint64_t step;
    uint16_t event_type;
    memory_intent_t intent;
    uint32_t latency_us;
} memory_intent_event_t;
```

## Notes On Scope

- This ABI is conceptual.
- The Python prototype is authoritative for now.
- A future implementation could map this to a shared-memory ring buffer, eBPF event stream, runtime plugin API, or a userspace memory-tiering daemon input format.
