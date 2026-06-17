# DAMON KV Hotness

DAMON gives Linux-native access sampling for virtual-address ranges. That matters here because KV Deadline Scheduler wants a real hotness signal for KV-like memory without requiring GPU instrumentation or a patched serving runtime.

This track treats large anonymous mappings as stand-ins for KV blocks, lets DAMON monitor them through sysfs, and then converts the sampled counts into `MemoryIntentEvent` records for offline replay.

## Why This Matters

- HOT regions approximate decode-critical KV blocks.
- WARM regions approximate near-future reuse.
- COLD regions approximate spill candidates.
- DAMON supplies kernel-observed access counts instead of heuristic guesses from the simulator alone.

## Files

- `kv_damon_controller.py`
  Allocates KV-like regions, configures DAMON through sysfs, runs the access loop, and writes `results/damon_hotness_result.json`.
- `kv_damon_to_intent.py`
  Converts DAMON access counts into `MemoryIntentEvent` JSONL for `kvmi compare --trace`.
- `kv_region_workload.py`
  Older lightweight workload generator kept for manual experiments.
- `run_damon_monitor.sh`
  Best-effort helper script for manual monitoring.

## How To Run

```bash
cd kernel_vm/experiments/damon_kv_hotness
sudo python3 kv_damon_controller.py
python3 kv_damon_to_intent.py
```

## What To Expect

- Regions `0-1` should show the highest `nr_accesses`.
- Regions `2-3` should land in a warm middle band.
- Regions `4-7` should remain near zero after the initial write.
- The converter should emit a JSONL trace with `DECODE_CRITICAL`, `HOT`, `WARM`, and `COLD` classifications.

## Output

- `results/damon_hotness_result.json`
- `results/damon_hotness_trace.jsonl`

## Caveats

- Run the controller with `sudo`; it programs DAMON sysfs directly.
- DAMON sysfs layout can vary across kernels.
- The result is still a research proxy for KV hotness, not production GPU memory telemetry.
