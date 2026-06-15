# Telemetry Format

Optional telemetry can later be combined with request traces to calibrate the simulator.

Example:

```json
{"timestamp_ms":1000,"gpu_memory_used_bytes":123456789,"gpu_memory_free_bytes":987654321,"active_requests":8,"tokens_per_second":450,"p99_token_latency_ms":80}
```

Potential future calibration inputs:

- request traces
- memory telemetry
- token latency telemetry
- model configuration

This milestone does not require telemetry ingestion yet. The format is documented so future versions can combine telemetry with imported request traces and estimated KV footprints.
