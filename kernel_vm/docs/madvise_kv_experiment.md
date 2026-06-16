# `madvise` KV Experiment

This experiment maps KV-like region intent onto existing Linux `madvise` primitives.

It is a VM-level approximation of intent-aware memory management, not precise accelerator memory control.

## Intent Mapping

| KV intent | Linux primitive to explore | Meaning |
|---|---|---|
| Decode-critical or near deadline | touch or prefault, possibly `MADV_WILLNEED` | keep or bring pages resident |
| Cold or spillable | `MADV_COLD` or `MADV_PAGEOUT` | make reclaim or pageout easier |
| Done or freeable | `MADV_DONTNEED` | drop pages |
| Recompute-ok | `MADV_COLD` or `MADV_PAGEOUT` under pressure | safe candidate for eviction |

## Why `madvise`

`madvise` is one of the simplest existing Linux VM interfaces for expressing coarse memory intent without a kernel patch.

It lets the process say:

- these pages are likely needed soon
- these pages are cold
- these pages can be thrown away
- these pages are candidates for pageout

That makes it a good first-stage experiment for KV intent mapping.

## Metrics to Collect

- access latency before and after advice
- minor faults
- major faults
- RSS change
- page residency if available
- `vmstat` counters
- PSI memory pressure

## Example Observation Questions

- Does `MADV_DONTNEED` reduce RSS for done regions?
- Do cold or pageout regions fault more when accessed later?
- Does the hot region remain fast under repeated access?
- Does memory pressure amplify the differences?

## Caveats

- `madvise` is advisory.
- Behavior depends on kernel version, memory pressure, page type, and permissions.
- It does not provide precise HBM placement, CXL control, or deterministic reclaim behavior.
- Results should be interpreted as evidence about whether coarse intent classes are expressible at the VM layer, not as proof of production benefit.
