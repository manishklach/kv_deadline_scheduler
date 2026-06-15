# Optional Passive Runtime Instrumentation

This document is intentionally scoped as optional future instrumentation, not a required integration path.

KV Deadline Scheduler does not import, patch, or depend on vLLM internals.

The main profiling workflow is external:

- collect request-level serving traces
- estimate KV footprint from model configuration
- reconstruct approximate KV lifecycle events
- replay them through the simulator

If a user controls their serving stack, they may later add passive instrumentation to export richer traces. That would still be external observability work, not an upstream patch requirement.
