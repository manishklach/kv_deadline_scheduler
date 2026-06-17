# userspace helper

This helper registers memory-intent ranges with the experimental debugfs interface.

It is meant for RFC v0 validation only.

## Build

```bash
make
```

## Usage

```bash
./mm_intent_register <pid> <start_hex> <length_hex> <flags_hex> <deadline_ns> <priority>
```

## Example Workflow

1. Run `kv_madvise_experiment` or `kv_region_workload.py`
2. Get the PID and address range if available
3. Register a range
4. Read the dump

Example:

```bash
./mm_intent_register 1234 0x7f0000000000 0x200000 0x1 1000000 90
cat /sys/kernel/debug/mm_intent/dump
```

Important:

- this is experimental `debugfs`
- this is not a stable ABI
- this is not a production registration interface
