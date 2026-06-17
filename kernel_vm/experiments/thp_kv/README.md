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

## Observed On WSL2 (2026-06-17)

Observed result file:

- `seq_normal_mb_s = 7516.74`
- `seq_thp_mb_s = 11005.06`
- `random_normal_mpps = 8.2218`
- `random_thp_mpps = 13.2713`

This particular run showed a positive throughput signal for the THP-backed mapping. The Python wrapper still reported `AnonHugePages_kB = 0`, so the accounting signal is weaker than the throughput signal and should be treated cautiously.

See also:

- [`results/thp_alloc_result.json`](results/thp_alloc_result.json)
- [../../../docs/wsl_validation_2026_06_17.md](../../../docs/wsl_validation_2026_06_17.md)
