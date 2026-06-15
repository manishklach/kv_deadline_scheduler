# KV Deadline Scheduler

Deadline-aware KV-cache scheduling for long-context LLM inference memory pressure.

KV cache is not anonymous memory. It is request-state with deadlines.

Generic memory tiering asks: "Is this page hot?"

KV Deadline Scheduler asks: "Which KV block belongs to decode-critical request-state, how close is it to missing its deadline, and what is the cost of evicting it?"

> Current results are simulated and prototype-oriented. They are intended to test the interface and policy behavior, not to claim production speedups or real GPU memory control.

The public project name is KV Deadline Scheduler. The prototype Python package is currently named `kv_memory_intent`.

## What This Repo Is

KV Deadline Scheduler is a systems research prototype for deadline-aware KV-cache placement under long-context LLM inference pressure. It defines a runtime-declared KV intent schema, records lifecycle events, generates synthetic and serving-trace-derived workloads, compares access-based and deadline-aware policies, and reports simulated p50, p95, and p99 latency, decode-critical misses, evictions, spills, prefetches, and HBM pressure behavior.

## No vLLM Patch Required

KV Deadline Scheduler does not require modifying vLLM.

The current external profiling flow is:

1. collect or export request-level serving traces
2. estimate KV footprint from model configuration and token counts
3. reconstruct approximate KV block lifecycle events
4. replay those events through deadline-aware scheduling policies
5. compare miss, eviction, and p99 behavior under simulated HBM pressure

```text
Serving system logs / request traces / telemetry
        |
        v
External KV pressure profiler
        |
        v
MemoryIntentEvent JSONL
        |
        v
Policy simulator + deadline-aware scheduler comparison
```

## What This Repo Is Not

- Not a production vLLM scheduler
- Not a kernel driver
- Not a real GPU HBM controller
- Not a production CXL/NVMe tiering stack
- Not a MEXT clone
- Not a KV compression method

## Current Capabilities

- Runtime-declared KV intent schema
- KV lifecycle event tracing
- Synthetic workload profiles
- Mock serving trace adapter
- External request trace importer
- LRU, HotCold, PredictiveHotness, IntentAware, DeadlineAware policies
- Decision logs
- HBM pressure sweeps
- Optional plotting
- Simulated p50/p95/p99 metrics
- Docs for passive optional instrumentation and external profiling

## External KV Estimation

Estimate KV footprint from model configuration:

```bash
kvmi estimate-kv \
  --model llama-3-8b \
  --prompt-tokens 128000 \
  --generated-tokens 1000
```

Example output:

```text
Approx KV per token: X MB
Approx request KV: Y GB
Approx batch KV: Z GB
```

These estimates are approximate and intended for profiling and simulation.

## External Request Trace Import

Import request logs into approximate KV lifecycle traces:

```bash
kvmi import-request-trace \
  --requests examples/sample_request_trace.jsonl \
  --model llama-3-8b \
  --out imported_trace.jsonl \
  --logical-block-mb 1
```

Then inspect and compare:

```bash
kvmi inspect --trace imported_trace.jsonl --head 5
kvmi compare --trace imported_trace.jsonl --hbm-mb 4096 --dram-mb 65536
```

Imported traces are approximate reconstructions. They do not depend on serving-engine internals.

## Synthetic and Mock Workloads

Synthetic profiles:

- `balanced`
- `deadline_pressure`
- `rag_mixed_priority`
- `speculative_decode`
- `long_context_extreme`

Mock serving-trace generation:

```bash
kvmi mock-vllm --out mock_vllm_trace.jsonl --requests 16 --decode-steps 256 --compare --hbm-mb 128 --dram-mb 2048
```

The `mock-vllm` command is a compatibility path for vLLM-style serving logs. It is still an external trace generator, not a runtime patch or dependency on vLLM internals.

## Policy Matrix

| Policy | Uses access history | Uses inferred hotness | Uses declared request priority | Uses deadline | Uses phase |
|---|---:|---:|---:|---:|---:|
| LRU | Yes | No | No | No | No |
| HotCold | Yes | Yes | No | No | No |
| PredictiveHotness | Yes | Yes | No | No | No |
| IntentAware | Yes | Partial | Yes | No/limited | Yes |
| DeadlineAware | Yes | Partial | Yes | Yes | Yes |

## Quickstart

```bash
pip install -e .
pytest

kvmi estimate-kv \
  --model llama-3-8b \
  --prompt-tokens 128000 \
  --generated-tokens 1000

kvmi import-request-trace \
  --requests examples/sample_request_trace.jsonl \
  --model llama-3-8b \
  --out imported_trace.jsonl \
  --logical-block-mb 1

kvmi inspect --trace imported_trace.jsonl --head 5
kvmi compare --trace imported_trace.jsonl --hbm-mb 4096 --dram-mb 65536
```

Optional plotting:

```bash
pip install matplotlib
python examples/plot_sweep_results.py sweep.csv --out docs/results/
```

## Near-Term Roadmap

Completed:

- synthetic simulator
- policy ladder
- mock serving trace
- external request trace importer

Next:

- add adapters for common serving logs
- import OpenAI-compatible proxy logs
- ingest Prometheus GPU memory telemetry
- calibrate the simulator against real p99 token latency
- advisory scheduler
- actuation later

Optional future:

- passive runtime instrumentation for users who control their serving stack

## Repository Layout

```text
kv_deadline_scheduler/
  README.md
  pyproject.toml
  src/kv_memory_intent/
  integrations/external_trace/
  docs/
  examples/
  tests/
```
