# Linux VM Intent Experiment

This is a VM-level experiment, not an LLM benchmark.

It emulates KV-like memory regions with different intent classes:

- decode-critical hot region
- warm region
- cold spillable region
- done or freeable region

The experiment tests whether existing Linux `madvise` primitives can express some KV memory intent without a kernel patch.

## What It Tests

- Whether `MADV_DONTNEED` changes behavior for done or freeable regions
- Whether cold or spillable regions behave differently after `MADV_COLD` or `MADV_PAGEOUT`
- Whether hot regions remain fast under repeated access
- Whether faults and RSS change after advice

## What It Does Not Test

- A real LLM workload
- GPU HBM control
- A production memory tiering system
- Guaranteed reclaim behavior

## What It Does

The C program:

- allocates a large anonymous memory region
- divides it into logical KV-like regions
- touches all pages initially
- repeatedly touches the hot region
- applies `madvise` to cold or freeable regions
- measures access latency, fault counts, and approximate RSS

## Build and Run

```bash
cd kernel_vm/experiments/linux_vm_intent
make
./kv_madvise_experiment
```

Optional system observation:

```bash
vmstat 1
cat /proc/pressure/memory
cat /proc/$(pidof kv_madvise_experiment)/smaps_rollup
```

## Caveats

- Results depend on kernel version and memory pressure.
- `MADV_COLD` and `MADV_PAGEOUT` may not be available.
- Linux may not reclaim cold pages unless there is pressure.
- This is not GPU HBM control.
