# Reproducibility

This repository is designed as a lightweight research prototype with simulated policy evaluation and a Linux-first userspace I/O experiment.

## Environment

- Python: `>=3.11`
- Install:

```bash
pip install -e .[dev]
```

- Test suite:

```bash
pytest
```

## Demo Commands

Default simulation demo:

```bash
kvmi demo --profile deadline_pressure
```

KV estimation:

```bash
kvmi estimate-kv \
  --model llama-3-8b \
  --prompt-tokens 128000 \
  --generated-tokens 1000
```

External request-trace import and comparison:

```bash
kvmi import-request-trace \
  --requests examples/sample_request_trace.jsonl \
  --model llama-3-8b \
  --out imported_trace.jsonl \
  --logical-block-mb 1

kvmi compare --trace imported_trace.jsonl --hbm-mb 4096 --dram-mb 65536
```

## Sweep Commands

Sweep HBM capacity on a built-in demo profile:

```bash
kvmi sweep \
  --demo \
  --profile deadline_pressure \
  --hbm-min-mb 128 \
  --hbm-max-mb 2048 \
  --points 8 \
  --dram-mb 4096 \
  --out sweep.csv
```

Plot the sweep:

```bash
pip install matplotlib
python examples/plot_sweep_results.py sweep.csv --out docs/results/
```

## Linux I/O Benchmark Commands

Baseline:

```bash
python experiments/linux_io_priority/kv_io_priority_bench.py \
  --mode baseline \
  --duration-sec 10 \
  --dir /tmp/kvio \
  --json-out /tmp/kvio/baseline.json
```

Separated:

```bash
python experiments/linux_io_priority/kv_io_priority_bench.py \
  --mode separated \
  --duration-sec 10 \
  --dir /tmp/kvio \
  --json-out /tmp/kvio/separated.json
```

## Caveats

- Policy results are simulated.
- Imported traces are approximate reconstructions from external logs and model metadata.
- The Linux I/O benchmark does not test a real LLM runtime.
- Linux I/O benchmark results vary with filesystem, NVMe or SSD behavior, kernel version, scheduler, cache warmth, free space, and background system load.
- `ioprio` behavior may depend on permissions, kernel support, and whether the platform is Linux.

## Recommendation for Meaningful I/O Runs

For the strongest signal:

- run on Linux
- use a real NVMe device if available
- point `--dir` at that device
- avoid very short durations
- note whether the cache state is warm or relatively cold
- capture JSON output from both `baseline` and `separated` modes

Use [results_template.md](results_template.md) to record results consistently.
