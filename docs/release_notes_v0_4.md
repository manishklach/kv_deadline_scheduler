# v0.4 — Linux I/O Priority Emulation Track and Runtime Polish

This release keeps the core scheduler prototype honest and simulator-first while tightening reproducibility, adapter behavior, and contributor ergonomics.

It continues the no-kernel-patch Linux I/O priority track and adds implementation polish around deterministic traces, integration parsing, simulator metrics, and developer workflow.

## Summary Tables

### Fixed Bugs

| Area | Change | Why it matters |
|---|---|---|
| Simulator recency decay | Recency decay now happens once per unique step instead of once per event. | Multiple events at the same logical step no longer over-decay live blocks. |
| vLLM slack calculation | `slack_us` now scales with deadline, request priority, and block position instead of using a hardcoded subtraction. | Decode urgency is modeled more realistically for adapter-produced traces. |
| Plot helper failure mode | `plot_sweep_results.py` now validates input CSVs, exits non-zero when `matplotlib` is missing, and prints a completion summary. | Plotting failures are visible and reproducible instead of silent. |

### New Features

| Area | Change | Notes |
|---|---|---|
| Integration parsing | Added `integrations/external_trace/parsers.py` for telemetry JSONL and request-trace JSONL loading. | Request traces wrap the package loader; telemetry validates required fields. |
| Simulator metrics | Added `decode_critical_miss_rate` to `SimulationResult` and the comparison table. | The metric is bounded and exposed in result dictionaries and markdown output. |
| Contributor docs | Added `CONTRIBUTING.md`. | Covers setup, policies, workload profiles, trace format, and style expectations. |
| CI | Added GitHub Actions matrix testing for Python 3.11 and 3.12. | Uses `pip install -e .[dev]` and `python -m pytest --tb=short -q`. |

### New CLI Flags and Reproducibility Improvements

| Command or script | Flag | Purpose |
|---|---|---|
| `kvmi generate` | `--seed` | Reproducible synthetic trace generation. |
| `kvmi demo` | `--seed` | Reproducible built-in demo trace generation. |
| `kvmi sweep --demo` | `--seed` | Reproducible demo-backed HBM sweeps. |
| `kvmi compare` | `--seed` | Reserved for reproducible synthetic comparison workflows and kept consistent with the CLI surface. |
| `kvmi mock-vllm` | `--seed` | Reproducible mock vLLM trace generation. |
| `examples/synthetic_trace_demo.py` | `--seed` | Reproducible example trace output. |
| `examples/mock_vllm_trace_demo.py` | `--seed` | Reproducible example mock-trace output. |

## Verification

Executed during this update:

- `python -m pytest -v`
- `python examples/policy_comparison_demo.py`
- `python examples/mock_vllm_trace_demo.py`

## Scope Notes

- Policy results remain simulated.
- The profiler remains external and does not require a vLLM patch.
- The Linux I/O benchmark remains a no-kernel-patch experiment.
- The mock vLLM adapter remains a passive trace adapter, not a serving-runtime integration.
