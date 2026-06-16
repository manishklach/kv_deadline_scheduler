# Serving Trace Import Plan

KV Deadline Scheduler treats vLLM as an example serving engine, not a dependency.

No upstream patch is required. The primary path is external trace import:

1. collect request traces, token counts, and optional telemetry
2. estimate KV footprint from model configuration
3. reconstruct approximate KV lifecycle events
4. replay those events through the simulator
5. compare policy behavior under simulated HBM pressure

Optional runtime instrumentation may later help users who control their serving stack export richer traces, but it is not required for this repository to be useful.
