# vLLM Integration Plan

## Goal

Integrate with vLLM without changing runtime behavior at first. The initial objective is passive tracing and offline replay, not online actuation.

## Candidate Hooks

- KV block allocation
- KV block free
- prefix cache hit or reuse
- request scheduled
- request preempted
- decode step begins
- speculative draft block created
- draft block committed or rejected
- swap or spill events, if exposed

## Phase 1: Passive Tracing

- Add an intent emitter near KV block lifecycle transitions.
- Record JSONL traces with request, phase, and priority metadata.
- Do not change scheduling, allocation, or placement behavior yet.
- Measure KV lifecycle shape before proposing policy changes.

## Phase 2: Offline Policy Replay

- Feed real traces into this simulator.
- Compare LRU-style policies with intent-aware and deadline-aware policies.
- Find the pressure scenarios where semantics matter most.

## Phase 3: Advisory Mode

- Let the policy engine recommend pin, spill, and prefetch actions.
- Log what the runtime would have done.
- Keep the runtime's actual allocator unchanged until the advisory signal is trustworthy.

## Phase 4: Actuation

- Wire policy recommendations into block placement or eviction decisions.
- Integrate real DRAM, NVMe, or CXL backends later.
- Measure cost of enforcement separately from quality of decisions.

## Metrics

- TTFT
- TPOT
- p50, p95, and p99 token latency
- throughput
- GPU memory used
- KV blocks spilled
- decode-critical misses
- spill miss penalty
- recompute penalty
