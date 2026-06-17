# `madvise` Experiment Results (WSL2)

## Environment

- Kernel: WSL2 Linux 6.x
- Swap: WSL swap device was present, but the observed run did not produce useful pageout behavior for the synthetic regions
- `MADV_COLD`: not reliably accepted in the observed run on this environment
- `MADV_PAGEOUT`: not reliably accepted in the observed run on this environment

## Observed Run

Representative output from the validated WSL run:

```text
Before advice:
  hot access:  0.02 us
  warm access: 0.01 us
  cold access: 0.01 us
  done access: 0.01 us
  minor faults: 131795
  major faults: 4
  RSS: 513 MB

Applied advice:
  hot: MADV_WILLNEED: applied
  cold: MADV_COLD: failed: Invalid argument
  cold: MADV_PAGEOUT: failed: Invalid argument
  done: MADV_DONTNEED: failed: Invalid argument

After advice:
  hot access:  0.01 us
  warm access: 0.01 us
  cold access: 0.01 us
  done access: 0.01 us
  minor faults delta: 1
  major faults delta: 0
  RSS: 513 MB
```

## What the Observed WSL Run Means

The `kv_madvise_experiment` binary compiled and ran successfully on WSL2, which confirms the VM-track experiment path is executable on Linux.

However, the particular WSL kernel and guest configuration observed here did not provide stable support for the cold or pageout advice calls used by the experiment. That means the WSL run is useful as a smoke test for the experiment harness, but not yet a strong signal about reclaim semantics.

## Implication for KV Scheduling

The `madvise` track remains viable as a kernel-facing research direction because it uses existing Linux VM interfaces and requires no kernel patch.

The next meaningful validation step is to rerun the experiment on a non-WSL Linux environment, or on WSL with a configuration known to expose the required advice semantics more faithfully, then compare:

- RSS change
- fault behavior
- reaccess latency by region
- behavior with and without memory pressure

## Next Steps

- Re-run on bare-metal Linux or a less virtualized Linux environment
- Re-run with deliberate memory pressure while observing `vmstat` and PSI
- Compare reclaim behavior with and without `MADV_FREE` as a baseline
- Cross-reference [../../../docs/wsl_validation_2026_06_17.md](../../../docs/wsl_validation_2026_06_17.md)
