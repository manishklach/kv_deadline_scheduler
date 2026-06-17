# Disaggregated Results

This directory compares a network-aware extension against a single-node deadline policy on a 3-node prefill/decode/storage topology.

The key idea is simple:

- a block that lives across the network has a retrieval cost
- deadlines must be compared against network RTT, not just local recency
- if the block cannot arrive before its deadline, recompute can be cheaper than waiting
