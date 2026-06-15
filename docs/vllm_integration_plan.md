# External Workload Trace Import Plan

This document is retained for continuity, but the project direction is now external profiling rather than runtime integration.

KV Deadline Scheduler does not require modifying vLLM.

The preferred path is:

1. collect external request traces
2. estimate KV footprint from model configuration
3. reconstruct approximate KV lifecycle events
4. replay those events offline through the simulator
5. compare policy behavior under simulated HBM pressure

Optional future passive instrumentation may exist for users who control their serving stack, but it is not the primary path and is not required for this repository to be useful.
