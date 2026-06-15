# Related Work

This repository is intentionally modest in scope. It is a simulator-first prototype, not a claim that it supersedes production systems.

## Relevant Areas

- serving systems such as vLLM and PagedAttention-derived approaches
- KV-cache offload systems
- LMCache-style KV reuse and offload approaches
- vAttention-style virtual memory approaches
- generic memory tiering systems
- predictive memory tiering such as MEXT-style systems
- CXL memory pooling
- OS paging, swap, LRU, and MGLRU

## Main Distinction

Most memory-tiering systems infer demand from access behavior.

This repo asks whether AI runtimes should declare deadline-aware memory intent directly.

That is the core difference:

- predictive systems infer hotness from below
- intent-aware systems accept runtime meaning from above

These approaches are complementary, not mutually exclusive. A practical system may combine both.
