# Roadmap

This roadmap is organized around the staged research arc of KV Deadline Scheduler.

## Completed

- Synthetic simulator
- External request trace importer
- KV estimator
- Policy ladder
- Linux I/O scheduler track documentation
- Userspace I/O priority experiment
- Linux VM or memory-management track skeleton
- `madvise` KV intent experiment
- DAMON hot and cold workload

## Next

- Collect real OpenAI-compatible gateway logs
- Ingest GPU memory telemetry
- Run `kv_madvise_experiment` on Linux
- Collect DAMON hot and cold region traces
- Compare MGLRU behavior under KV-like memory pressure
- Test zswap and swap behavior for cold KV regions
- Run the I/O benchmark on a real Linux NVMe device and publish results
- Add an `io_uring` version of the benchmark
- Add a cgroup I/O class experiment
- Advisory scheduler
- Only then consider kernel patches for intent-aware reclaim or tiering

## Next Kernel Patch Steps

- Consolidate `mm_kv_intent` into generic `mm_intent_rfc`
- Make patch 1 compile on a pinned Linux version
- Add `smaps` or `debugfs` observability before policy changes
- Add DAMON reporting integration for memory-intent visibility
- Postpone reclaim behavior changes until observability is validated
