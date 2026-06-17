# perf KV Counters

This track connects the simulator's miss-penalty story to hardware-observed cache behavior. Using `perf_event_open()` on the current process, it counts cache references, cache misses, and instructions across KV-like access patterns.

## Build

```bash
cd experiments/perf_kv
gcc -O2 -Wall -Wextra kv_perf_counters.c -o kv_perf_counters -lpthread
```

## Run

```bash
./kv_perf_counters
```

## Patterns

- Sequential: 64-byte stride through a large mapping
- KV-random: accesses concentrated at random 4 MB block offsets
- Evicted KV: `MADV_COLD` before access to emulate a colder restart

## Why This Matters

The simulator's `miss_penalty_us` is a modeling simplification. These counters help ground that idea in real cache-miss behavior on Linux.
