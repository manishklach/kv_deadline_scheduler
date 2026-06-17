# WSL Development Guide

## What Works Well In WSL

- Python simulator
- external KV pressure profiler
- request trace import
- policy comparison
- docs and patch authoring
- compiling userspace C experiments
- `madvise` experiments, with caveats
- THP experiments, with caveats
- basic `userfaultfd` experiments, depending on WSL kernel config

## What Is Limited In WSL

- cannot normally boot an arbitrary patched kernel inside WSL the same way as native Linux
- DAMON may not be enabled
- MGLRU controls may not be exposed
- zswap and swap behavior is not representative
- block I/O scheduler experiments are not representative because storage is virtualized
- `mq-deadline` and NVMe scheduler validation should use native Linux or QEMU

## Recommended WSL Workflow

```bash
pytest

kvmi demo --profile deadline_pressure

kvmi estimate-kv --model llama-3-8b --prompt-tokens 128000 --generated-tokens 1000

kvmi import-request-trace --requests examples/sample_request_trace.jsonl --model llama-3-8b --out imported_trace.jsonl --logical-block-mb 1

kvmi compare --trace imported_trace.jsonl --hbm-mb 4096 --dram-mb 65536

cd kernel_vm/experiments/linux_vm_intent
make
./kv_madvise_experiment

cd ../damon_kv_hotness
python3 kv_region_workload.py --duration-sec 60
```

## Kernel Patch Validation From WSL

There are two reasonable paths:

### A. Develop patches in WSL, validate later on native Linux

Use WSL for:

- editing patches
- building userspace helpers
- maintaining docs

Then validate runtime behavior on a native Linux machine.

### B. Build and boot a patched kernel under QEMU from WSL

Use WSL as the authoring environment, but treat QEMU as the runtime validation target.

Important:

The repo should not claim real kernel validation from WSL alone.

## Checking Kernel Features In WSL

```bash
uname -a
grep DAMON /boot/config-$(uname -r) 2>/dev/null || zcat /proc/config.gz | grep DAMON
grep LRU_GEN /boot/config-$(uname -r) 2>/dev/null || zcat /proc/config.gz | grep LRU_GEN
cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null
ls /sys/kernel/mm/damon 2>/dev/null
ls /sys/kernel/debug 2>/dev/null
```

Config paths may not exist in WSL, so the fallbacks matter.
