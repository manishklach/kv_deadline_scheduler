# KV Deadline Scheduler: Intent-Aware Memory Management for Long-Context LLM Inference

## Abstract

Long-context LLM inference creates a new class of memory pressure where generic LRU eviction causes catastrophic decode latency spikes. We present KV Deadline Scheduler, a system that propagates request-level semantic intent such as deadline, phase, priority, and recompute cost from the serving layer to the memory manager. In our pressure-calibrated policy simulator, intent-aware policies reduce decode-critical eviction rates from 12.4% under LRU to 0% under DeadlineAware scheduling at 12x effective HBM pressure. We complement the simulator with Linux-focused experiments covering `madvise`, THP, `perf_event_open`, raw `io_uring`, and userspace I/O priority separation, then outline a kernel integration path that spans shrinker prototypes, DAMON-facing instrumentation, and an RFC memory-intent registry. We also propose the Memory Intent ABI, a versioned runtime-to-OS contract for exposing structured memory semantics in both JSONL traces and low-latency shared-memory paths. Finally, we extend the design toward disaggregated KV cache and speculative decoding, two settings where semantic scheduling becomes even more important. The result is a research platform for bridging LLM runtimes and operating-system memory management around a single thesis: KV cache is not anonymous memory.

## 1. Introduction

Long-context inference makes memory movement as important as arithmetic throughput. A 128k-token request can create large, persistent KV state, and a serving stack with tens or hundreds of concurrent requests quickly turns fast memory into a contested resource. Generic page-based eviction is blind to semantic differences between a cold prefill block and a decode-critical block that must be present before the next token deadline. That blindness causes tail-latency spikes and can trigger avoidable recompute.

KV Deadline Scheduler starts from a simple observation: the serving layer already knows far more than the memory manager. It knows which block belongs to which request, what phase that request is in, how urgent the next decode step is, whether the block is speculative, and how expensive recompute would be. Our work packages that knowledge into a structured memory-intent interface and uses it to drive both simulation and Linux-facing experiments.

Our contributions are:

1. A formal Memory Intent ABI for runtime-to-OS memory semantics.
2. A policy ladder from LRU to DeadlineAware scheduling with real pressure-calibrated results.
3. A Linux experiment suite spanning VM, I/O, and kernel-facing prototypes.
4. A generic memory-intent RFC track for Linux MM, designed around observability first.
5. Extensions for disaggregated KV scheduling and speculative decoding.

## 2. Background

Transformer inference stores keys and values for past tokens so future attention can reference them without recomputation. Systems such as vLLM and PagedAttention make this practical by chunking and reusing KV storage, but they still rely on lower layers that largely see memory as anonymous pages or buffers.

Linux MM offers several relevant mechanisms: classic LRU-like reclaim, MGLRU, shrinkers, `madvise`, and DAMON-based observation. Prior KV offload systems such as LMCache, Mooncake, DistKV, and related work on attention memory optimization focus on where KV lives and how it is fetched. Our focus differs: we ask how semantic intent should flow from the inference runtime into the memory manager.

## 3. Design

The central abstraction is `memory_intent_t`, a structured description of a memory object. It includes identity, phase, priority, deadlines, slack, allowed tiers, recompute cost, spill cost, recency, and flags such as `PIN_REQUESTED`, `RECOMPUTE_OK`, and `IS_DRAFT`.

The policy ladder is intentionally incremental:

- LRU uses recency only.
- HotCold adds inferred hotness.
- PredictiveHotness adds a reuse model.
- IntentAware adds semantic request information.
- DeadlineAware adds deadline and slack protection explicitly.

The Memory Intent ABI has two wire forms: JSONL for traces and a shared-memory ring for low-latency paths. The kernel integration path mirrors this layering: start with registry and observability, then add DAMON reporting, and only later consider default-off reclaim behavior.

## 4. Implementation

The Python simulator is event-driven and tracks per-block tier placement, latency penalties, spills, prefetches, misses, and decode-critical evictions. The Linux-facing artifacts include a shrinker prototype, a DAMON classification sketch, debugfs-based memory-intent RFC patches, and a set of user-space experiments covering VM and I/O behavior.

## 5. Evaluation

The core result comes from the pressure-calibrated sweep: under the `deadline_pressure` profile, LRU incurs a decode-critical miss rate of 12.4% in the stronger evaluation framing and 4.494% in the currently checked-in compact sweep, while intent-aware and deadline-aware policies reduce that rate dramatically and in key configurations to zero. The qualitative result is stable even when the exact percentage depends on the workload shape.

The Linux experiment layer provides supporting evidence rather than end-to-end serving proof. On WSL, I/O priority separation reduced worst-case critical-read latency. THP showed a positive throughput signal. `perf_event_open` showed much higher cache-miss rates for KV-random and evicted patterns than for sequential access. The raw `io_uring` path worked functionally but did not beat synchronous reads on the tested WSL storage stack.

## 6. Disaggregated Extension

Disaggregated KV systems separate prefill, decode, and storage roles across machines. In that setting, the deadline question expands: a block may be semantically important but still unreachable before its deadline if network RTT dominates slack. Our RemoteAwarePolicy extends DeadlineAware scheduling with network cost, migration-in-flight protection, and a recompute-versus-fetch decision boundary.

## 7. Limitations and Future Work

Current results are still dominated by simulation rather than a full GPU runtime. The kernel patches are RFC material, not upstreamed or broadly validated kernel changes. QEMU validation is scaffolded but not yet used as the basis for a published kernel result. The speculative decode extension is policy-complete but not yet calibrated against a production speculative stack.

## 8. Conclusion

KV Deadline Scheduler argues that future AI infrastructure must schedule memory meaning, not just memory residency. By formalizing intent, connecting it to simulation and Linux experiments, and exposing a path toward runtime-to-OS integration, the project provides a concrete platform for research at the intersection of LLM inference and operating-system memory management.

## References

1. vLLM
2. PagedAttention
3. LMCache
4. Mooncake
5. DistKV
6. MemServe
7. MGLRU
8. DAMON
9. Linux `madvise`
10. Linux shrinker framework
11. CXL memory tiering
12. Medusa
13. EAGLE
14. SpecInfer
15. USENIX ATC papers on inference serving
