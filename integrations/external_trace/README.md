# External Trace Import

KV Deadline Scheduler is designed to work as an external profiler and simulator.

This is not an upstream vLLM patch. It is an external trace and import workflow for serving-system request logs, token counts, deadlines, and optional memory telemetry.

Supported inputs in this milestone:

- request-level serving traces
- model KV configuration or presets
- optional serving metadata such as request priority and deadlines

Planned later inputs:

- gateway logs
- proxy logs
- Prometheus GPU memory telemetry
- token latency telemetry
