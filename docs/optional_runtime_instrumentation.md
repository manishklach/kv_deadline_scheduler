# Optional Runtime Instrumentation

This document covers an optional future path for users who control their own serving stack.

vLLM is only an example serving engine. KV Deadline Scheduler does not import it, depend on its internals, or require an upstream patch.

The primary workflow remains external:

- collect request-level serving traces
- estimate KV footprint from model configuration
- reconstruct approximate KV lifecycle events
- replay them through the simulator

If a team controls its runtime, it may later add passive instrumentation to export richer lifecycle traces. That instrumentation is optional and should preserve serving behavior.
