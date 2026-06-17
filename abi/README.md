# Memory Intent ABI

This is the Memory Intent ABI.

Any runtime that implements this header can participate in deadline-aware KV scheduling.

The ABI has two layers:

- `memory_intent.h` for the stable structure layout
- `memory_intent_wire.h` plus `memory_intent_ring.c` for a low-latency shared-memory ring buffer path

Binary wire compatibility notes:

- the packed struct layout stays offset-stable
- shared-memory and other binary wire paths use little-endian scalar encoding
- helper functions in `memory_intent.h` normalize `u16`, `u32`, `u64`, and `float` fields for heterogeneous environments

The design goal is workload-neutral runtime-to-OS intent propagation, even though KV cache is the motivating use case for this repository.
