# Linux I/O Priority Benchmark Plan

This directory is reserved for a future userspace benchmark that studies how KV-style I/O classes interact with Linux storage prioritization.

There is no kernel patch implemented here and no benchmark harness yet. This is an experimental plan.

## Benchmark Idea

Create two workload files:

- `critical_reads.bin`
- `background_spills.bin`

The benchmark would compare:

- Normal mixed I/O with no explicit separation
- Priority-separated I/O for critical reads versus background spill writes

Potential implementation paths include `io_uring`, async file I/O, `ionice`, `ioprio`, or cgroup I/O controls, depending on platform support.

## Example Workload Shape

- `critical_reads.bin`
  Represents decode-critical KV prefetch traffic that must complete before token generation stalls.
- `background_spills.bin`
  Represents low-priority KV spill traffic created by memory pressure.

The benchmark should inject background write pressure while repeatedly measuring completion time for critical reads.

## Metrics

- Critical read p99 latency
- Aggregate throughput
- Starvation behavior
- Background write delay

## Research Goal

The goal is to test whether separating KV-inspired I/O classes in user space improves tail latency for critical reads under concurrent spill pressure.

Any future kernel-specific work should be justified by these userspace results first.
