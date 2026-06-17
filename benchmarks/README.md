# Reproducible Benchmark Suite

This directory contains a scripted benchmark harness for reproducible KV Deadline Scheduler runs.

The suite is simulator-first and research-oriented. It does not claim real GPU HBM control or production vLLM speedups.

What it covers:

- synthetic workload sweeps across policy variants
- latency-distribution capture for each workload and policy pair
- speculative policy comparison through lifecycle replay
- optional mock-vLLM trace replay for adapter regressions

Outputs:

- `summary.json`
- `policy_metrics.csv`
- `latency_distributions.json`
- `speculative_metrics.json`

Run:

```bash
python benchmarks/run_reproducible_suite.py --config benchmarks/configs/default_suite.json
```

The default suite is intended to be a clean, scriptable baseline for paper figures, README snapshots, and repeatable local comparisons. Results remain workload-model dependent and should be interpreted as simulator outputs, not production inference measurements.
