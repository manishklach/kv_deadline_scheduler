# Contributing

## Setup

```bash
git clone https://github.com/manishklach/kv_deadline_scheduler.git
cd kv_deadline_scheduler
pip install -e .[dev]
pre-commit install
python -m ruff check src tests
python -m mypy
python -m pytest
```

## Adding a Policy

1. Subclass `PlacementPolicy`.
2. Implement `choose_victim`.
3. Implement `explain_victim_choice`.
4. Register the policy in `policy_from_name` in `src/kv_memory_intent/simulator.py`.

## Adding a Workload Profile

1. Extend the `_profile_settings` dictionary in `src/kv_memory_intent/simulator.py`.
2. Add a test in `tests/test_simulator.py`.

## Trace Format

See [integrations/external_trace/request_trace_format.md](integrations/external_trace/request_trace_format.md).

## Code Style

- Use `ruff` for linting and formatting.
- Type hints are required.
- Use `slots=True` on new dataclasses.

## Optional Plotting Support

Plotting helpers are optional and live behind an extra:

```bash
pip install -e .[plotting]
```

## Before Opening A PR

```bash
python -m ruff check src tests
python -m mypy
python -m pytest
```
