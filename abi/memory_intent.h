#ifndef _MEMORY_INTENT_H
#define _MEMORY_INTENT_H

#include <stdbool.h>
#include <stdint.h>

#define MEMORY_INTENT_ABI_VERSION 1

/* Object types */
#define MI_TYPE_KV_CACHE    0x01
#define MI_TYPE_WEIGHTS     0x02
#define MI_TYPE_ACTIVATIONS 0x03
#define MI_TYPE_SCRATCH     0x04

/* Phase flags */
#define MI_PHASE_PREFILL 0x01
#define MI_PHASE_DECODE  0x02
#define MI_PHASE_VERIFY  0x03
#define MI_PHASE_DONE    0x04

/* Priority levels */
#define MI_PRI_COLD            0
#define MI_PRI_WARM            1
#define MI_PRI_HOT             2
#define MI_PRI_DECODE_CRITICAL 3

/* Tier flags */
#define MI_TIER_HBM    (1u << 0)
#define MI_TIER_DRAM   (1u << 1)
#define MI_TIER_CXL    (1u << 2)
#define MI_TIER_NVME   (1u << 3)
#define MI_TIER_REMOTE (1u << 4)

/* Intent flags */
#define MI_FLAG_PIN_REQUESTED  (1u << 0)
#define MI_FLAG_RECOMPUTE_OK   (1u << 1)
#define MI_FLAG_COMPRESSION_OK (1u << 2)
#define MI_FLAG_PREFETCH_OK    (1u << 3)
#define MI_FLAG_IS_DRAFT       (1u << 4)
#define MI_FLAG_IS_COMMITTED   (1u << 5)

typedef struct memory_intent {
    /* Identity */
    uint64_t object_id;
    uint64_t request_id;
    uint32_t block_id;
    uint16_t object_type;
    uint16_t abi_version;

    /* Placement */
    uint8_t phase;
    uint8_t priority;
    uint8_t allowed_tiers;
    uint8_t current_tier;

    /* Sizing */
    uint64_t size_bytes;

    /* Scheduling */
    uint32_t deadline_us;
    uint32_t slack_us;
    uint32_t recompute_cost_us;
    uint32_t spill_cost_us;
    uint32_t expected_reuse_window_tokens;
    uint16_t request_priority;
    float recency_score;

    /* Flags */
    uint32_t flags;

    /* Disaggregation */
    uint32_t home_node_id;
    uint32_t replica_node_id;
    uint64_t remote_addr;

    /* Future extension space. Existing fields must never move. */
    uint8_t _reserved[16];
} __attribute__((packed)) memory_intent_t;

/* Wire format: JSONL for traces, binary for low-latency paths. */
/* ABI stability: new fields append at the end; existing offsets never change. */

#endif /* _MEMORY_INTENT_H */
