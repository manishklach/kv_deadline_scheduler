# Results

This directory is for generated sweep outputs and optional plots from KV Deadline Scheduler experiments.

## Generate Sweep Results

```bash
kvmi sweep --demo --profile deadline_pressure --out sweep.csv
```

Or sweep an existing trace:

```bash
kvmi sweep --trace trace.jsonl --hbm-min-mb 128 --hbm-max-mb 2048 --points 8 --dram-mb 4096 --out sweep.csv
```

## Plot Results

```bash
pip install matplotlib
python examples/plot_sweep_results.py sweep.csv --out docs/results/
```

This can generate:

- `p99_latency_vs_hbm.png`
- `decode_critical_misses_vs_hbm.png`
- `decode_critical_evictions_vs_hbm.png`

## What The Charts Mean

- `p99_latency_vs_hbm.png`: how sensitive each policy is to tight HBM capacity.
- `decode_critical_misses_vs_hbm.png`: whether a policy protects the most urgent request-state blocks.
- `decode_critical_evictions_vs_hbm.png`: whether pressure handling evicts the wrong KV state.

Generated PNG and CSV files are usually local artifacts unless you intentionally commit them.
