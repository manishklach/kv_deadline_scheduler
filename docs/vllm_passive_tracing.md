# Passive vLLM Trace Capture

The passive vLLM trace adapter does not import or modify vLLM.

It provides a small adapter surface that future vLLM hooks can call while preserving the current milestone goal: observability first, no scheduling changes.

Output is JSONL `MemoryIntentEvent`. Those traces can then be replayed through the simulator offline.

## Conceptual Hook Mapping

| vLLM concept | Adapter method |
|---|---|
| Request scheduled | `on_request_scheduled` |
| KV block allocated | `on_block_allocated` |
| Decode step touches blocks | `on_decode_step` |
| Prefix/cache reuse | future `on_prefix_cache_hit` |
| Speculative draft created | `on_block_allocated(..., is_draft=True)` |
| Draft committed | `on_block_committed` |
| Block freed | `on_block_freed` |

> Passive tracing should not change vLLM behavior. The first milestone is to collect real KV lifecycle traces and replay them offline.

## Design Sketch

The adapter supports two modes:

1. standalone mock mode using fake vLLM-like lifecycle events
2. future integration mode where actual vLLM hooks call adapter methods

## Pseudocode Only

```python
# Pseudocode only — actual vLLM hook points may differ.

adapter = VLLMIntentAdapter()

def on_kv_block_allocated(request_id, block_id, phase):
    adapter.on_block_allocated(
        step=current_step(),
        request_id=request_id,
        block_id=block_id,
        phase=phase,
    )

def on_decode_iteration(request_id, active_blocks):
    adapter.on_decode_step(
        step=current_step(),
        request_id=request_id,
        active_block_ids=active_blocks,
        deadline_us=request_deadline(request_id),
        request_priority=request_priority(request_id),
    )

adapter.recorder.to_jsonl("vllm_kv_trace.jsonl")
```

This is a design sketch, not a guaranteed vLLM API.
