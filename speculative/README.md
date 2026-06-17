# Speculative Scheduling

Speculative decoding creates ephemeral KV state.

Draft tokens that get rejected leave HBM waste. `SpeculativeIntentPolicy` tracks acceptance probability and aggressively reclaims rejected draft trees.
