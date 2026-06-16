# KV Cache Is Request-State With Deadlines: From LLM Memory Pressure to Linux I/O Scheduling

## Outline

1. Long-context inference creates KV pressure
   Explain why longer prompts, larger batches, and persistent serving push KV state into the foreground.

1. Generic memory systems see pages and I/O
   Describe the limits of access-only reasoning when the platform only sees hot and cold pages or reads and writes.

1. Runtimes see request-state
   Introduce the richer information available at the serving layer: request ownership, phase, deadline, priority, and recompute cost.

1. Deadline-aware KV scheduling
   Show how KV Deadline Scheduler compares generic policies with intent-aware and deadline-aware policies under simulated pressure.

1. External pressure profiling without modifying vLLM
   Explain the external-profiler path using request traces, token counts, model configuration, and telemetry, with no upstream patch required.

1. Mapping KV intent to I/O classes
   Connect decode-critical prefetch and background spill to coarse read and write urgency classes.

1. No-kernel-patch Linux I/O experiment
   Introduce the userspace benchmark that tests mixed versus separated I/O behavior without a kernel patch.

1. Future: `io_uring`, cgroups, `mq-deadline` hints, kernel scheduler research
   Frame the kernel-adjacent path as future work driven by evidence from userspace experiments.

1. What this project proves and does not prove
   Reiterate the honest scope:
   simulated policies, external profiling, no vLLM patch, no kernel patch, and no production speedup claim yet.
