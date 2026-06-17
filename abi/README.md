# Memory Intent ABI

This is the Memory Intent ABI.

Any runtime that implements this header can participate in deadline-aware KV scheduling.

The ABI has two layers:

- `memory_intent.h` for the stable structure layout
- `memory_intent_wire.h` plus `memory_intent_ring.c` for a low-latency shared-memory ring buffer path

The design goal is workload-neutral runtime-to-OS intent propagation, even though KV cache is the motivating use case for this repository.
