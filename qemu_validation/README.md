# QEMU Validation

From zero to a running kernel with memory intent patches in four steps.

1. Run `setup.sh`
2. Apply the RFC patches to Linux `6.8.y`
3. Build `bzImage` with `minimal.config`
4. Boot in QEMU and run `test_intent_interface.sh`

Expected output:

```text
/sys/kernel/debug/mm_intent
register
dump
clear
PASS: debugfs memory intent interface responds
```

This harness is meant to make runtime validation reproducible without treating WSL itself as proof of kernel behavior.
