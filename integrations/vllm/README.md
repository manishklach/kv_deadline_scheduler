# vLLM Integration

This directory holds the optional vLLM-facing integration path for KV Deadline Scheduler.

The design goal is still zero required upstream vLLM source modification. The preferred architecture is to wrap engine surfaces or request telemetry, emit `MemoryIntentEvent` records, and feed those records into JSONL traces or the ABI ring buffer.

## What is implemented

- A `KVIntentPlugin` shim that maps scheduler, preemption, and finish callbacks into intent events
- Adapter helpers for sequence access, spill, and free emission
- A local smoke harness that exercises the plugin against a fake engine surface
- A pytest regression test for the smoke harness

## What is not yet claimed

- No validated production vLLM deployment
- No published end-to-end latency numbers from a real serving stack
- No upstream compatibility guarantee across vLLM versions

## Event path

1. Wrap the engine or callback surface
2. Emit `MemoryIntentEvent` records on scheduler steps, preemption, and finish
3. Write those events into JSONL traces or the ABI ring buffer

Expected output:

- active KV blocks marked as accessed
- decode-tail blocks promoted to decode-critical
- preempted sequences marked as spilled
- finished sequences marked as freed

## Smoke harness

```bash
python integrations/vllm/smoke_test_plugin.py --out integrations/vllm/results/plugin_smoke.jsonl
```

This harness validates the plugin-to-adapter data path against a fake engine surface. It is useful for regression testing and public documentation, but it is still a harness rather than a real deployment study.
