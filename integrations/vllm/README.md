# vLLM Integration

How to attach KV Deadline Scheduler to a running vLLM instance.

The integration goal is zero required vLLM source modification.

High-level flow:

1. wrap the engine or callback surface
2. emit `MemoryIntentEvent` records on scheduler steps, preemption, and finish
3. write those events into the ABI ring buffer or JSONL traces

Expected output:

- active KV blocks marked as accessed
- decode tail blocks promoted to decode-critical
- preempted sequences marked as spilled
- finished sequences marked as freed
