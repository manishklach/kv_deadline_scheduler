# v0.4 — Linux I/O Priority Emulation Track

This release adds a no-kernel-patch Linux I/O priority benchmark that emulates decode-critical KV prefetch reads and cold KV spill writes.

It connects the deadline-aware KV policy layer to a kernel-adjacent I/O scheduling research path without claiming kernel changes or production inference speedups.

## Highlights

- Added a Linux-first userspace benchmark for mixed versus separated I/O behavior:
  `experiments/linux_io_priority/kv_io_priority_bench.py`
- Expanded the repository narrative around the staged research arc from:
  external KV pressure profiling,
  to deadline-aware simulation,
  to KV I/O class mapping,
  to Linux I/O priority emulation
- Added reproducibility and results-capture docs for public benchmarking and reporting

## Scope Notes

- Policy results remain simulated.
- The profiler remains external and does not require a vLLM patch.
- The Linux I/O benchmark does not require a kernel patch.
- The benchmark is sensitive to filesystem, cache state, kernel behavior, and storage hardware.
