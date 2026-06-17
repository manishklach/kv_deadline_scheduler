# mm_kv_intent Patch Series

This directory contains an upstream-style patch series that proposes a new `mm/kv_intent_advisor.c` subsystem.

The series is not applied to any kernel tree in this repository. It documents what an upstream contribution could look like if KV-style memory intent were proposed to Linux MM as a reclaim advisory mechanism.

## Patch Series

- `0001-mm-add-kv_intent_advisor-infrastructure.patch`
- `0002-mm-vmscan-consult-kv_intent_advisor-in-shrink_page_list.patch`
- `0003-mm-kv_intent-add-procfs-userspace-registration-interface.patch`

## Motivation

Userspace serving engines increasingly know more than the kernel about the relative value of resident memory.

For long-context LLM inference in particular, two regions with the same size can have radically different reclaim cost:

- a decode-critical KV block close to deadline
- a cold prefill block with large slack and acceptable recompute cost

This patch series sketches a minimal MM subsystem that allows userspace to register that distinction.

## Apply

```bash
git am 0001-*.patch 0002-*.patch 0003-*.patch
```

## Kernel Config

Enable:

```text
CONFIG_KV_INTENT_ADVISOR=y
```

## Testing Idea

After applying the series:

1. write intents to `/proc/kv_intent/register`
2. run the `kv_madvise_experiment` under memory pressure
3. observe whether `DECODE_CRITICAL` pages survive reclaim more often than `COLD` pages

## Upstream Submission Checklist

- [ ] `checkpatch.pl` clean
- [ ] `sparse` clean
- [ ] tested with `CONFIG_DEBUG_VM=y`
- [ ] `mm/MAINTAINERS` entry added
- [ ] cover letter sent to `linux-mm@kvack.org`
