# DAMON KV Hotness Workload

This directory contains a simple KV-like region workload for DAMON experiments.

It does not configure DAMON automatically. Instead, it creates a process with hot, warm, and cold memory-access patterns so you can attach DAMON externally if your kernel exposes the necessary interfaces.

## Files

- `kv_region_workload.py`
  Creates hot, warm, and cold regions and touches them at different rates.
- `run_damon_monitor.sh`
  Best-effort helper script that checks for common DAMON control paths and prints guidance.

## Example

```bash
python kv_region_workload.py --duration-sec 120
sudo ./run_damon_monitor.sh <PID> 60
```

## What to Expect

- The workload prints its PID and region sizes.
- The hot region should show the highest activity.
- The warm region should show periodic activity.
- The cold region should show much less activity.

## Caveats

- DAMON must be enabled in the kernel.
- DAMON availability depends on kernel config and distro support.
- The control interface varies by kernel.
- This is access-pattern observability, not policy enforcement.
- DAMON does not know KV semantics unless paired with intent metadata.
