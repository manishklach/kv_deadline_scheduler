# Disaggregated KV Scheduling

Most KV cache systems assume a single node. As LLMs scale to trillion-parameter serving stacks, KV state is increasingly disaggregated across the network.

This module extends deadline-aware scheduling to multi-node topologies.

It models:

- prefill/decode disaggregation
- network RTT as part of the miss cost
- local recompute versus remote fetch decisions

References:

- Mooncake (Qian et al. 2024)
- LMCache
- DistKV
- MemServe
