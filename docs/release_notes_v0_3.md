# v0.3 — External KV Pressure Profiler

This release turns KV Deadline Scheduler into a stronger external profiling artifact.

It adds KV footprint estimation, external request-trace import, OpenAI-compatible proxy log import, Prometheus GPU memory telemetry ingestion, safer simulator state updates, and CI.

## What Was Added

- Model KV footprint estimator driven by presets or manual model configuration
- External request trace format with JSONL read and write helpers
- Request trace importer that reconstructs approximate `MemoryIntentEvent` sequences from serving logs
- OpenAI-compatible proxy log adapter for chat-completion style usage records
- Prometheus GPU memory telemetry adapter for synthetic pressure signals
- Step-based recency decay in the simulator
- Safer partial intent merging in the simulator for update events
- GitHub Actions CI on push and pull request to `main`

## New CLI Subcommands

| Subcommand | Key flags | Purpose |
|---|---|---|
| `kvmi estimate-kv` | `--model`, `--prompt-tokens`, `--generated-tokens`, `--json` | Estimate approximate KV bytes per token and per request. |
| `kvmi import-request-trace` | `--requests`, `--model`, `--out`, `--logical-block-mb`, `--max-blocks-per-request` | Convert external request traces into approximate `MemoryIntentEvent` JSONL. |
| `kvmi inspect` | `--trace`, `--head`, `--json` | Inspect imported or synthetic traces before replay. |
| `kvmi import-openai-log` | `--requests`, `--out`, `--model`, `--logical-block-tokens` | Convert OpenAI-compatible proxy logs into approximate intent traces. |
| `kvmi import-prometheus` | `--samples`, `--out`, `--max-memory-gb` | Convert GPU memory telemetry into synthetic pressure signals. |

## Notes

- Imported traces remain approximate and simulator-based.
- Model presets are illustrative and not guaranteed exact vendor configurations.
- The profiler remains external and dependency-light.
- There is still no production memory actuation.
- There is still no real GPU HBM control.
- There is still no claim of production speedups.
