# VM vs I/O Kernel Tracks

KV Deadline Scheduler has two complementary kernel-facing research paths.

## VM Track

This path applies before KV state becomes storage I/O.

It focuses on:

- page residency
- reclaim
- pageout
- swap
- memory tiering

Key mechanisms include:

- DAMON
- MGLRU
- `madvise`
- zswap
- memory tiering

## I/O Track

This path applies after KV state becomes storage I/O.

It focuses on:

- prioritizing decode-critical reads over background spill traffic
- separating urgent prefetch from low-priority writes
- exploring `io_uring`, `ioprio`, and `mq-deadline`-adjacent questions

## Comparison

| Track | Layer | Main question | First experiment |
|---|---|---|---|
| VM | memory residency and reclaim | Which KV-like pages should stay resident? | `madvise` or DAMON hot-cold KV regions |
| I/O | storage request scheduling | How urgent is KV spill or prefetch I/O? | critical reads vs background writes |

The tracks are complementary, not competing.

The VM track asks how to preserve the right pages before they fall out of memory.

The I/O track asks how to prioritize the resulting reads and writes if spill or prefetch reaches storage.

The VM path decides whether KV should become storage traffic at all. The I/O path decides how urgent that storage traffic is once it exists.
