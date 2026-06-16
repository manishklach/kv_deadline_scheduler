# Project Arc

KV Deadline Scheduler is organized as a staged research path rather than a single monolithic system.

The motivating idea is simple: KV cache is not anonymous memory. It is request-state with deadlines. Long-context inference turns that idea into a systems problem because the runtime has to protect decode-critical state under memory pressure while the broader platform only sees buffers, pages, and I/O.

## Why KV Deadlines Matter

Generic memory systems reason about recency, hotness, and capacity pressure. LLM runtimes can reason about richer structure:

- which request owns a KV block
- whether the block is in prefill or decode
- how close the block is to being needed again
- whether the block is tied to a near deadline
- whether eviction is tolerable because recompute is cheap

The central research question is whether that runtime intent can protect the right state better than generic heuristics.

## Why External Profiling Comes Before Runtime Changes

This repository starts with external profiling because it is the lowest-risk way to test the control-plane idea.

External profiling makes it possible to:

- ingest request traces and telemetry from an existing serving stack
- estimate KV pressure from token counts and model configuration
- reconstruct approximate KV lifecycle events
- compare policy behavior without changing an inference runtime

That keeps the research honest. It lets us evaluate the intent model before making stronger claims about deployment or actuation.

## Why Deadline-Aware Simulation Is the Core

The policy simulator is the center of the current prototype.

It provides a controlled way to compare:

- LRU
- HotCold
- PredictiveHotness
- IntentAware
- DeadlineAware

The simulator reports simulated p50, p95, and p99 latency, decode-critical misses, evictions, spills, prefetches, and HBM pressure behavior. Those metrics are enough to test whether richer intent changes which blocks get protected.

## Staged Kernel Paths

```text
External KV pressure profiler
        |
        v
Deadline-aware KV policy simulator
        |
        v
VM path: madvise / DAMON / MGLRU / zswap / tiering
        |
        v
I/O path: io_uring / ioprio / mq-deadline if KV spills to storage
        |
        v
future kernel research
```

## Why the VM Path Comes Before the I/O Path

If KV intent matters before spill, the first kernel-facing question is often about page residency rather than storage scheduling.

The VM path is the closer conceptual match for MEXT-like memory expansion:

- `madvise`
- DAMON and DAMOS
- MGLRU
- zswap and swap
- memory tiering, NUMA, and CXL

That path asks which KV-backed pages should stay resident, which are reclaim candidates, and which may tolerate colder tiers.

The repository now includes a `kernel_vm/` track for these experiments and notes.

## Why I/O Priority Is the Second Kernel-Adjacent Bridge

If KV state spills or prefetch reaches storage, the next question is about I/O urgency.

That is where the Linux-first userspace I/O priority benchmark fits. It emulates a future spill and prefetch backend and asks whether separating critical reads from background writes helps preserve critical-read p99 under storage pressure.

## Why Kernel Scheduler Changes Are Future Work

Kernel scheduler changes are explicitly future work, not a current claim.

The project does not currently prove:

- that Linux `mq-deadline` should change
- that semantic KV hints improve a production scheduler
- that real inference latency improves in deployment

Instead, it defines a staged path:

1. External profiling
1. Deadline-aware simulation
1. VM path: `madvise`, DAMON, MGLRU, zswap, and tiering experiments
1. I/O path: `io_uring`, `ioprio`, and `mq-deadline`-adjacent experiments if KV spills to storage
1. Only then, if justified, research-only kernel patch experiments

That sequence keeps the project grounded while still opening an ambitious systems research direction.
