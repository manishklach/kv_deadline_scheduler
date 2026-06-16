# Kernel I/O Scheduler Research Track

This document outlines a kernel-facing research track for KV Deadline Scheduler.

The scope is intentionally limited. There is no kernel patch implemented here, no claim of Linux scheduler improvement yet, and no change to the current simulator core. This is a roadmap for staged experiments that connect user-space KV intent to storage I/O prioritization.

## Relationship to Linux `mq-deadline`

Linux `mq-deadline` schedules block I/O requests in the kernel block layer. Its unit of control is the submitted storage request.

KV Deadline Scheduler operates earlier in the stack. It schedules and simulates KV-cache request-state before that state becomes I/O. Its unit of control is the KV block or logical request-state object, together with runtime intent such as urgency, deadline, phase, and recompute cost.

These systems are complementary, not the same.

- `mq-deadline` decides how submitted reads and writes are serviced at the block layer.
- KV Deadline Scheduler decides which KV blocks should stay pinned, be spilled, or be prefetched before storage I/O is issued.

In other words, Linux deadline scheduling handles storage request deadlines. KV Deadline Scheduler handles AI request-state deadlines.

## Layer Model

The research path can be viewed as a stack of increasingly concrete control points:

1. Runtime or request layer
   KV block priority, deadline, phase, ownership, reuse window, and recompute cost are defined here.
1. Offload layer
   The runtime or external scheduler decides whether to pin, spill, prefetch, or defer action on a KV block.
1. I/O submission layer
   Offload and prefetch decisions become reads and writes through interfaces such as `io_uring`, `pread` or `pwrite`, or other async I/O paths.
1. Kernel block layer
   The Linux I/O scheduler such as `mq-deadline`, `none`, `bfq`, or `kyber` orders and dispatches the resulting block requests.
1. Device
   The final behavior is constrained by the NVMe device or SSD itself, including queue depth, firmware, and internal scheduling.

## Mapping KV Intent to I/O Classes

One research question is how user-space KV intent could be translated into coarse I/O classes before or during I/O submission.

Illustrative mapping:

| KV intent | Example action | Candidate I/O class |
|---|---|---|
| `DECODE_CRITICAL` prefetch | Pull a near-deadline KV block back before decode resumes | High-priority read |
| `HOT` near-deadline prefetch | Pull a likely-needed block with moderate urgency | High or normal priority read |
| `COLD` spill | Evict low-value state from fast memory | Low-priority write |
| `DONE` cleanup | Flush or retire completed request-state | Idle or background write |
| `recompute_ok=true` block | Deprioritize storage recovery because recompute is acceptable | Lower-priority read or write |

This does not require exact one-to-one kernel primitives at first. The immediate research goal is to define stable intent classes that can be mapped onto whatever priority controls are available in user space.

## No-Kernel-Patch Experiments

A first wave of experiments can stay entirely in user space:

- Use `ionice` or `ioprio` where applicable to separate critical and background operations.
- Use separate `io_uring` rings for decode-critical prefetch traffic versus background spill traffic.
- Use cgroup I/O controls to split critical and background I/O paths.
- Generate a synthetic KV spill and prefetch workload from the existing simulator or external trace importer.
- Measure p50, p95, and p99 read latency under background write pressure.

These experiments would test whether simple I/O separation improves tail behavior for decode-critical reads without any kernel modification.

Example questions:

- Does priority-separated prefetch reduce critical read p99 under heavy spill traffic?
- How much background write delay is introduced?
- Does separation avoid starvation, or just move pressure elsewhere?

## Future Kernel Patch Experiment

A later research stage could explore kernel changes, but it should remain clearly labeled as experimental:

- Add optional request flags or hints for KV I/O class.
- Explore an `mq-deadline` variant that gives stronger service preference to decode-critical KV reads.
- Do not claim upstream suitability.
- Keep the work framed as research, not productization.

The purpose of this stage would be to learn whether block-layer scheduling can preserve AI request-state deadlines better when it receives semantic hints from user space.

## Suggested Evaluation Path

The staged path from user-space KV intent to Linux block-layer prioritization is:

1. Define stable KV urgency classes in user space.
1. Emit those classes in synthetic or trace-replayed spill and prefetch workloads.
1. Map urgency classes onto existing user-space I/O priority controls.
1. Measure tail latency and starvation behavior under mixed read and write pressure.
1. Only if the user-space results justify it, prototype a research-only kernel hint path.

That path keeps the current simulator useful while opening a credible kernel-facing track for future systems work.
