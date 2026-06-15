# Architecture

## Problem Statement

KV-cache pressure in long-context inference is not just a capacity problem. It is also a semantics problem. The runtime knows which blocks are decode-critical, low priority, draft-only, reusable, or close to a deadline. Lower memory tiers often do not.

This prototype explores an observability-first path where the runtime emits intent at the KV block lifecycle level, and an offline policy engine replays that trace to test smarter placement strategies.

## System Diagram

```text
Runtime intent emitter
        |
        v
Intent trace recorder
        |
        v
Policy engine
        |
        v
Tier simulator
        |
        v
Metrics and comparison
```

## Components

### Runtime Intent Emitter

The emitter is represented here by a synthetic workload generator, but the conceptual source is a runtime such as vLLM. It emits semantic state about each KV block across allocation, access, decode, commit, prefetch, and free events.

### Intent Trace Recorder

The recorder stores JSONL traces of `MemoryIntentEvent` objects. These traces are human-readable enough for debugging and stable enough for offline replay.

### Policy Engine

The policy layer compares five behaviors:

- `LRU`: page-like recency without semantics
- `HotCold`: generic access-based hot/cold tracking
- `PredictiveHotness`: access-based hotness with reuse-window inference
- `IntentAware`: protects pinned or decode-critical blocks and prefers eviction of cold low-priority blocks
- `KVDeadline`: extends intent-aware behavior with explicit deadline, slack, and request-priority protection

### Tier Simulator

The simulator models HBM and DRAM pressure, miss penalties, spill latency, and prefetch latency. It is deliberately simple and explicit so the tradeoffs remain inspectable.

### Metrics

The metrics layer reports p50, p95, and p99 simulated latency plus misses, evictions, spills, and decode-critical failure modes.

## Design Principle

> Intent is emitted per KV block lifecycle, not per page fault.

This matters because it:

- reduces overhead relative to fault-level observation
- avoids hot-path callbacks on every low-level memory access
- aligns with the runtime's actual semantic object model
- stays portable across HBM, DRAM, CXL, and NVMe backends

## Observability-First Path

Phase one is passive:

- define the intent schema
- emit traces
- replay policies offline
- compare where LRU fails under pressure

## Actuation-Later Path

A future version can keep the same intent ABI but add enforcement:

- advisory recommendations first
- runtime pin or spill decisions later
- concrete DRAM, CXL, or NVMe movement only after the policy proves useful offline
