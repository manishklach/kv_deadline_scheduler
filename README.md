# kv-memory-intent

Runtime-declared memory intent for KV-cache orchestration.

Generic memory tiering asks: "Is this page hot?"

LLM runtimes can answer a better question:

"What is this memory, when is it needed, and what does it cost to be wrong?"

`kv-memory-intent` is an observability-first, simulator-first research prototype for KV-cache pressure. It explores whether runtime-declared intent can help a placement policy make better choices than generic LRU-style eviction when HBM is tight.

KV cache is not anonymous memory. It is request-state with deadlines.

## Problem

Long-context inference can hit KV-cache pressure before raw compute becomes the dominant bottleneck.

- Lower memory layers usually see pages, buffers, and access bits.
- The runtime sees request ownership, decode urgency, deadlines, reuse windows, and spillability.
- Generic hot/cold heuristics can evict the wrong blocks.
- The result is avoidable misses, refetch or recompute cost, and p95 or p99 token-latency spikes.

## Core Idea

This prototype treats each KV block as a semantic object that carries intent metadata such as:

- priority
- phase
- deadline
- expected reuse window
- recompute cost
- spill cost
- spillability, compression, and prefetch eligibility

Policies can then use that intent to:

- pin decode-critical blocks
- spill cold low-priority blocks first
- prefetch likely-needed blocks before decode pressure turns into misses

## Why KV Cache First

- KV cache has a large and dynamic footprint.
- It grows with context and request concurrency.
- Different blocks have different urgency.
- Request ownership and decode phase matter.
- It is a clean benchmark surface for an intent-aware control plane.

## What This Prototype Does

- Defines a concrete Python schema for memory intent and lifecycle events.
- Generates deterministic synthetic KV traces that create memory pressure.
- Simulates `LRU`, `IntentAware`, and `DeadlineAware` policies.
- Reports simulated p50, p95, and p99 latency, misses, spills, evictions, and decode-critical failure modes.

## What This Prototype Does Not Do Yet

- No kernel driver
- No real vLLM behavior change
- No CUDA memory movement
- No real CXL or NVMe backend
- No production scheduler

This repo is intentionally a systems research MVP, not a production memory-tiering stack.

## Quickstart

```bash
pip install -e .
pytest
kvmi demo
```

Generate and compare a larger trace:

```bash
kvmi generate --out trace.jsonl --requests 64 --blocks-per-request 32 --decode-steps 1000 --block-kb 16
kvmi compare --trace trace.jsonl --hbm-mb 512 --dram-mb 4096
```

## Example Output

Illustrative example:

| Policy | P50 latency | P95 latency | P99 latency | Misses | Decode-critical misses | Evictions | Decode-critical evictions | Spills | Prefetches | HBM saved | P99 improvement vs LRU | Decode-critical miss reduction vs LRU |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LRU | 50.0 us | 5050.0 us | 5250.0 us | 87 | 31 | 160 | 14 | 160 | 0 | 0.0 B | 0.0% | 0.0% |
| IntentAware | 50.0 us | 5050.0 us | 5050.0 us | 64 | 9 | 160 | 1 | 160 | 0 | 0.0 B | 3.8% | 71.0% |
| DeadlineAware | 50.0 us | 5050.0 us | 5050.0 us | 60 | 6 | 160 | 0 | 160 | 22 | 0.0 B | 3.8% | 80.6% |

All metrics are simulated. The point is not to claim production wins today. The point is to test whether intent-aware placement can protect the right KV blocks under pressure.

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

`kv-memory-intent` explores runtime-declared memory meaning from above.

The thesis is not that prediction is useless. It is that the runtime already knows facts the memory system should not have to rediscover from anonymous accesses.

## Future Integration

- Instrument the vLLM KV cache manager and block pool.
- Add a TensorRT-LLM adapter.
- Replay real traces offline before changing runtime behavior.
- Explore LMCache-style backends for actuation.
- Benchmark p99 behavior on long-context serving workloads.

## Research Questions

- Does intent-aware policy reduce decode-critical misses?
- What metadata is necessary versus optional?
- How often should intent be emitted?
- Can p99 improve without hurting throughput?
- What is the smallest useful ABI across runtimes?

## Repository Layout

```text
kv-memory-intent/
  README.md
  pyproject.toml
  src/kv_memory_intent/
  examples/
  tests/
  docs/
```
