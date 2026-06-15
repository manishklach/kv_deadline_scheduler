# v0.2 — Passive vLLM-Style Trace Adapter and Deadline-Aware Scheduling

This release continues the deadline-aware project rebranding around the public name **KV Deadline Scheduler** while keeping the internal Python package name `kv_memory_intent` for compatibility.

## Highlights

- Added a policy ladder spanning `LRU`, `HotCold`, `PredictiveHotness`, `IntentAware`, and `DeadlineAware`.
- Added decision logs for simulated eviction, spill, and prefetch choices.
- Added HBM sweep tooling for capacity sensitivity experiments.
- Added optional plotting for sweep outputs.
- Added workload profiles for balanced, deadline-pressure, mixed-priority, speculative, and long-context-heavy traces.
- Added a passive serving-trace adapter that can represent vLLM-style lifecycle signals without importing or modifying vLLM.
- Added mock serving-trace generation and replay through the existing simulator.

## Limitations

- Results remain simulated.
- This is still a research prototype.
- The passive adapter does not change serving-system scheduling behavior.
- There is still no real GPU memory actuation.
- There is still no production CXL or NVMe backend.
- There are still no claims of production serving speedups.
