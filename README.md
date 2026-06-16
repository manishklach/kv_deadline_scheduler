# KV Deadline Scheduler

Deadline-aware KV-cache scheduling for long-context LLM inference memory pressure.

> KV cache is not anonymous memory. It is request-state with deadlines.

Generic memory tiering asks: "Is this page hot?"

KV Deadline Scheduler asks: "Which KV block belongs to decode-critical request-state, how close is it to missing its deadline, and what is the cost of evicting it?"

> Current results are simulated. This repository is a research prototype for profiling and policy comparison, not a claim of production speedups or real GPU memory control.

The public project name is KV Deadline Scheduler. The prototype Python package is currently named `kv_memory_intent`.

![KV Deadline Scheduler architecture](docs/kv_deadline_scheduler_architecture.svg)

_Architecture overview: external traces and telemetry are converted into KV lifecycle events, replayed through policy variants, and summarized with simulated latency and pressure metrics._

## What This Repo Is

KV Deadline Scheduler is a systems research prototype for deadline-aware KV-cache placement under long-context LLM inference pressure.

It defines a runtime-declared KV intent schema, records lifecycle events, estimates KV footprint from model configuration, reconstructs approximate KV block behavior from external request traces, compares access-based and deadline-aware policies, and reports simulated p50, p95, and p99 latency, decode-critical misses, evictions, spills, prefetches, and HBM pressure behavior.

The goal is to test whether deadline-aware scheduling can protect the right request-state under memory pressure better than generic LRU-style heuristics.

## No vLLM Patch Required

KV Deadline Scheduler does not require modifying vLLM.

It can operate as an external KV pressure profiler using request traces, token counts, model configuration, and telemetry. vLLM is one example serving engine, not a dependency. The same workflow can be applied to other serving stacks such as TensorRT-LLM, SGLang, or OpenAI-compatible gateways.

The current external profiling flow is:

```text
Serving logs / request traces / telemetry
                |
                v
External KV pressure profiler
                |
                v
Approximate MemoryIntentEvent JSONL
                |
                v
Policy simulator + deadline-aware scheduler comparison
                |
                v
Simulated latency, miss, spill, and pressure metrics
```

## Current Capabilities

- Runtime-declared KV intent schema
- KV lifecycle event tracing
- Synthetic workload profiles
- External request trace importer
- OpenAI-compatible proxy log importer
- Prometheus GPU memory telemetry importer
- Mock vLLM-style trace generator for demos and regression tests
- LRU, HotCold, PredictiveHotness, IntentAware, and DeadlineAware policies
- Decision logs
- HBM pressure sweeps
- Optional plotting
- Simulated p50, p95, and p99 metrics
- Docs for external trace import and optional runtime instrumentation

## Relationship to Linux Deadline I/O Scheduling

Linux `mq-deadline` handles storage request deadlines. KV Deadline Scheduler handles AI request-state deadlines.

A future bridge can map KV intent to I/O priorities or scheduler hints, but that bridge is still a roadmap item. There is no kernel patch implemented here and no claim of Linux scheduler improvement yet.

## Quickstart

Install the package and run the test suite:

```bash
pip install -e .[dev]
pytest
```

Estimate KV footprint for a representative long-context request:

```bash
kvmi estimate-kv \
  --model llama-3-8b \
  --prompt-tokens 128000 \
  --generated-tokens 1000
```

Import an external request trace and compare policies:

```bash
kvmi import-request-trace \
  --requests examples/sample_request_trace.jsonl \
  --model llama-3-8b \
  --out imported_trace.jsonl \
  --logical-block-mb 1

kvmi inspect --trace imported_trace.jsonl --head 5
kvmi compare --trace imported_trace.jsonl --hbm-mb 4096 --dram-mb 65536
```

Generate a mock serving-style trace for demos:

```bash
kvmi mock-vllm \
  --out mock_vllm_trace.jsonl \
  --requests 16 \
  --decode-steps 256 \
  --compare \
  --hbm-mb 128 \
  --dram-mb 2048
```

Optional plotting:

```bash
pip install matplotlib
python examples/plot_sweep_results.py sweep.csv --out docs/results/
```

## External KV Estimation

KV footprint estimates are based on model configuration, attention structure, token counts, and dtype width.

Example:

```bash
kvmi estimate-kv \
  --model llama-3-8b \
  --prompt-tokens 128000 \
  --generated-tokens 1000 \
  --json
```

Representative output:

```json
{
  "approx_batch_kv_bytes": 16908288000,
  "approx_kv_bytes_per_token": 131072,
  "approx_request_kv_bytes": 16908288000,
  "batch_size": 1,
  "generated_tokens": 1000,
  "model_name": "llama-3-8b",
  "note": "Estimated from model configuration. Results are approximate.",
  "prompt_tokens": 128000
}
```

These estimates are approximate and intended for external profiling and simulation.

## External Request Trace Import

Request traces are imported from JSONL records such as `examples/sample_request_trace.jsonl`.

Use the importer to reconstruct approximate KV lifecycle events:

```bash
kvmi import-request-trace \
  --requests examples/sample_request_trace.jsonl \
  --model llama-3-8b \
  --out imported_trace.jsonl \
  --logical-block-mb 1
```

Then inspect and replay:

```bash
kvmi inspect --trace imported_trace.jsonl --head 5
kvmi compare --trace imported_trace.jsonl --hbm-mb 4096 --dram-mb 65536
```

Imported traces are intentionally approximate. They are reconstructed from external logs and model metadata, not from runtime-internal allocation events.

## Policy Matrix

| Policy | Access history | Inferred hotness | Request priority | Deadline | Phase |
|---|---:|---:|---:|---:|---:|
| LRU | Yes | No | No | No | No |
| HotCold | Yes | Yes | No | No | No |
| PredictiveHotness | Yes | Yes | No | No | No |
| IntentAware | Yes | Partial | Yes | Limited | Yes |
| DeadlineAware | Yes | Partial | Yes | Yes | Yes |

## Example Decision

Illustrative example under HBM pressure:

| Policy view | Candidate block | Why it gets evicted |
|---|---|---|
| LRU | `req_7:block_44` | It looks old by recency, even though it belongs to decode-critical request-state with a near deadline. |
| DeadlineAware | `req_12:block_88` | It is a cold, low-priority prefill block with no near deadline and acceptable recompute cost. |

Representative metadata:

```text
req_7:block_44
  phase=DECODE
  priority=DECODE_CRITICAL
  deadline_us=900

req_12:block_88
  phase=PREFILL
  priority=COLD
  request_priority=20
  deadline_us=none
  recompute_ok=true
  expected_reuse_window_tokens=512
```

This is the core thesis. Both are memory blocks, but they are not equally valuable request-state.

## What This Repo Is Not

- Not a production vLLM scheduler
- Not a kernel driver
- Not a real GPU HBM controller
- Not a production CXL or NVMe tiering stack
- Not a MEXT clone
- Not a KV compression method

## Roadmap

Near-term milestones:

1. `v0.4` Offline replay
   Replay real serving traces through LRU, HotCold, PredictiveHotness, IntentAware, and DeadlineAware policies.
1. `v0.5` Advisory scheduler
   Emit pin, spill, and prefetch recommendations without enforcing them in a runtime.
1. `v0.6` Actuation prototype
   Connect recommendations to a runtime-level KV allocation or offload path and measure decode-critical miss behavior on real workloads.

## Repository Layout

| Path | Purpose |
|---|---|
| `src/kv_memory_intent/` | Core schema, simulator, policies, metrics, CLI, and adapters. |
| `tests/` | Regression coverage for schema, simulator behavior, adapters, and CLI-facing flows. |
| `examples/` | Small demos for policy comparison, synthetic traces, plotting, and mock serving traces. |
| `docs/` | Architecture notes, release notes, roadmap, optional instrumentation docs, and diagrams. |
| `integrations/external_trace/` | Request-trace and telemetry format notes for external profiling workflows. |
