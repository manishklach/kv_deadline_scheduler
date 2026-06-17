# vLLM Integration Architecture

```text
vLLM Engine
    |
    v
KVIntentPlugin
    |
    +--> Memory Intent ABI ring buffer
    |
    +--> VLLMIntentAdapter JSONL trace
    |
    v
kv_intent_shrinker / RFC registry
    |
    v
Linux reclaim / observability path
    |
    v
Prometheus + KV Deadline Scheduler metrics
```
