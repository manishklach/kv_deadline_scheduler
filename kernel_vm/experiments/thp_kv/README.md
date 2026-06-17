# THP KV Allocation

Transparent Huge Pages in `madvise` mode offer a Linux-native way to explore whether larger page mappings help KV-like accesses by reducing TLB pressure.

This track compares two large anonymous regions:

- default 4 KB pages
- `MADV_HUGEPAGE` promoted regions that may back with 2 MB pages

## Files

- `kv_thp_alloc.c`
  Measures sequential and random KV-like access throughput across the two mappings and writes JSON results.
- `kv_thp_alloc.py`
  Runs the binary, inspects `/proc/self/smaps` and `/proc/self/status`, and adds MemoryIntent-oriented interpretation.

## Build And Run

```bash
cd kernel_vm/experiments/thp_kv
gcc -O2 -Wall -Wextra kv_thp_alloc.c -o kv_thp_alloc -lpthread
./kv_thp_alloc
python3 kv_thp_alloc.py
```

## Why This Matters

A 2 MB THP-backed KV block can reduce TLB pressure by roughly `512x` compared with 4 KB pages. That does not guarantee better serving latency, but it is a meaningful kernel-facing primitive for long-context KV experiments.
