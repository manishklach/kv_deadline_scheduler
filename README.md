# KV Deadline Scheduler

Deadline-aware KV-cache scheduling for long-context LLM inference memory pressure.

Generic memory tiering asks: "Is this page hot?"

KV Deadline Scheduler asks: "Which request-state block is closest to missing its deadline, and what is the cost of evicting it?"

KV cache is not anonymous memory. It is request-state with deadlines.

> Current results are from a deterministic simulator and synthetic traces. They are intended to test the interface and policy behavior, not to claim production vLLM speedups.

This prototype tests the control-plane interface before implementing real memory movement.

The repository is branded as KV Deadline Scheduler. The prototype Python package is currently `kv_memory_intent`.

## Problem

Long-context inference can hit KV-cache pressure before raw compute becomes the dominant bottleneck.

- Lower memory layers usually see pages, buffers, and access bits.
- The runtime sees request ownership, decode urgency, deadlines, slack, reuse windows, and spillability.
- Generic hot/cold heuristics can evict the wrong blocks.
- The result is avoidable misses, refetch or recompute cost, and p95 or p99 token-latency spikes.

## Core Idea

This prototype treats each KV block as semantic request-state with intent metadata:

- request priority
- phase
- deadline and optional slack
- target decode step
- expected reuse window
- recompute and spill cost
- spillability, compression, and prefetch eligibility

Policies can then:

- pin decode-critical blocks
- spill cold low-priority blocks first
- prefetch likely-needed blocks before decode pressure turns into misses
- explain why they protected one block and sacrificed another

## Policy Matrix

| Policy | Uses access history | Uses inferred hotness | Uses declared request priority | Uses deadline | Uses phase |
|---|---:|---:|---:|---:|---:|
| LRU | Yes | No | No | No | No |
| HotCold | Yes | Yes | No | No | No |
| PredictiveHotness | Yes | Yes | No | No | No |
| IntentAware | Yes | Partial | Yes | No/limited | Yes |
| KVDeadline | Yes | Partial | Yes | Yes | Yes |

## What This Prototype Does

- Defines a concrete Python schema for KV intent and lifecycle events.
- Generates deterministic synthetic KV traces across multiple workload profiles.
- Simulates `LRU`, `HotCold`, `PredictiveHotness`, `IntentAware`, and `KVDeadline`.
- Reports simulated p50, p95, and p99 latency, misses, spills, evictions, and decode-critical failure modes.
- Records decision logs for evictions, spills, and prefetches.
- Sweeps HBM capacity to make pressure sensitivity visible.
- Includes a passive vLLM adapter skeleton for future trace capture.

## What This Prototype Does Not Do Yet

- No kernel driver
- No real vLLM behavior change
- No CUDA memory movement
- No real CXL or NVMe backend
- No production scheduler
- No real MEXT implementation or production comparison
- No real GPU HBM control

## Quickstart

```bash
pip install -e .
pytest
kvmi demo --profile deadline_pressure
kvmi generate --profile rag_mixed_priority --out trace.jsonl --requests 64 --blocks-per-request 32 --decode-steps 1000 --block-kb 16
kvmi compare --trace trace.jsonl --hbm-mb 512 --dram-mb 4096
kvmi sweep --trace trace.jsonl --hbm-min-mb 128 --hbm-max-mb 2048 --points 8 --dram-mb 4096 --out sweep.csv
```

Optional plotting:

```bash
pip install matplotlib
python examples/plot_sweep_results.py sweep.csv --out docs/results/
```

## Passive vLLM Trace Adapter

The next step toward real-runtime integration is passive tracing.

`KV Deadline Scheduler` includes a vLLM-style adapter skeleton that maps KV block lifecycle events into `MemoryIntentEvent` JSONL traces without importing or modifying vLLM.

This lets the project move from synthetic traces to real-runtime traces in stages:

1. mock vLLM-like traces,
2. passive vLLM hooks,
3. offline replay,
4. advisory scheduling,
5. eventual actuation.

Quickstart:

```bash
kvmi mock-vllm --out mock_vllm_trace.jsonl --requests 16 --decode-steps 256 --compare --hbm-mb 128 --dram-mb 2048
```

## Workload Profiles

- `balanced`: general-purpose default.
- `deadline_pressure`: many decode-critical blocks with tight deadlines.
- `rag_mixed_priority`: mixes interactive requests with low-priority background queries.
- `speculative_decode`: emits draft blocks where uncommitted drafts are often safe victims.
- `long_context_extreme`: large cold KV working set plus a small urgent decode hot set.

## Example Output

Illustrative comparison:

| Policy | P50 latency | P95 latency | P99 latency | Misses | Decode-critical misses | Evictions | Decode-critical evictions | Spills | Prefetches | HBM saved | P99 improvement vs LRU | Decode-critical miss reduction vs LRU |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LRU | 50.0 us | 5050.0 us | 5050.0 us | 25 | 25 | 121 | 0 | 121 | 0 | 16.0 KiB | 0.0% | 0.0% |
| HotCold | 50.0 us | 5050.0 us | 5050.0 us | 22 | 22 | 116 | 0 | 116 | 0 | 16.0 KiB | 0.0% | 12.0% |
| PredictiveHotness | 50.0 us | 5050.0 us | 5050.0 us | 18 | 18 | 109 | 0 | 109 | 0 | 16.0 KiB | 0.0% | 28.0% |
| IntentAware | 50.0 us | 250.0 us | 250.0 us | 0 | 0 | 96 | 0 | 96 | 0 | 16.0 KiB | 95.0% | 100.0% |
| KVDeadline | 50.0 us | 250.0 us | 250.0 us | 0 | 0 | 96 | 0 | 96 | 0 | 16.0 KiB | 95.0% | 100.0% |

## Example Decision

At step 420:

LRU evicts:
- `req_7:block_44`
- phase: `DECODE`
- priority: `DECODE_CRITICAL`
- deadline_us: `900`

KVDeadline evicts:
- `req_12:block_88`
- phase: `PREFILL`
- priority: `COLD`
- deadline_us: `none`
- recompute_ok: `true`
- expected_reuse_window_tokens: `512`

This is the core thesis: both are memory blocks, but they are not equally valuable request-state.

## Architecture

```text
LLM runtime / vLLM
        |
        | emits KV block intent
        v
Memory intent trace / ABI
        |
        v
Policy engine
        |
        +--> pin decode-critical blocks
        +--> spill cold blocks
        +--> prefetch near-deadline blocks
        v
HBM / DRAM / CXL / NVMe
```

## How This Differs From Predictive Memory Tiering

Predictive memory tiering infers hot pages from below.

KV Deadline Scheduler explores runtime-declared memory meaning from above.

The point is not to replace access-based signals. The point is that the runtime already knows request urgency and deadline risk that lower memory tiers should not have to infer from anonymous accesses alone.

## Future Integration

- Instrument the vLLM KV cache manager and block pool.
- Add passive trace capture first.
- Replay real traces offline before changing runtime behavior.
- Add advisory mode next.
- Explore LMCache-style backends for future actuation.
- Benchmark p99 behavior on long-context serving workloads.

## Repository Layout

```text
kv_deadline_scheduler/
  README.md
  pyproject.toml
  src/kv_memory_intent/
  docs/
  examples/
  tests/
```
