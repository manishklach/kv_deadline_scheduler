#ifndef _MEMORY_INTENT_H
#define _MEMORY_INTENT_H

#include <stdbool.h>
#include <string.h>
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

/*
 * Binary wire paths use little-endian encoding for all integer and floating
 * fields. Heterogeneous runtimes should normalize to the helpers below before
 * writing shared-memory or socket-visible payloads.
 */
#define MI_ENDIAN_LITTLE 0x01u
#define MI_ENDIAN_BIG    0x02u

#if defined(__BYTE_ORDER__) && (__BYTE_ORDER__ == __ORDER_BIG_ENDIAN__)
#define MI_HOST_ENDIAN MI_ENDIAN_BIG
#else
#define MI_HOST_ENDIAN MI_ENDIAN_LITTLE
#endif

#define MI_WIRE_ENDIAN MI_ENDIAN_LITTLE

static inline uint16_t mi_bswap16(uint16_t value)
{
    return (uint16_t)((value >> 8) | (value << 8));
}

static inline uint32_t mi_bswap32(uint32_t value)
{
    return ((value & 0x000000FFu) << 24) | ((value & 0x0000FF00u) << 8) | ((value & 0x00FF0000u) >> 8) | ((value & 0xFF000000u) >> 24);
}

static inline uint64_t mi_bswap64(uint64_t value)
{
    return ((uint64_t)mi_bswap32((uint32_t)(value & 0xFFFFFFFFu)) << 32) | (uint64_t)mi_bswap32((uint32_t)(value >> 32));
}

static inline uint16_t mi_host_to_le16(uint16_t value)
{
    return MI_HOST_ENDIAN == MI_ENDIAN_LITTLE ? value : mi_bswap16(value);
}

static inline uint32_t mi_host_to_le32(uint32_t value)
{
    return MI_HOST_ENDIAN == MI_ENDIAN_LITTLE ? value : mi_bswap32(value);
}

static inline uint64_t mi_host_to_le64(uint64_t value)
{
    return MI_HOST_ENDIAN == MI_ENDIAN_LITTLE ? value : mi_bswap64(value);
}

static inline uint16_t mi_le16_to_host(uint16_t value)
{
    return mi_host_to_le16(value);
}

static inline uint32_t mi_le32_to_host(uint32_t value)
{
    return mi_host_to_le32(value);
}

static inline uint64_t mi_le64_to_host(uint64_t value)
{
    return mi_host_to_le64(value);
}

static inline uint32_t mi_float_to_le32(float value)
{
    uint32_t bits = 0;
    memcpy(&bits, &value, sizeof(bits));
    return mi_host_to_le32(bits);
}

static inline float mi_le32_to_float(uint32_t value)
{
    uint32_t host_bits = mi_le32_to_host(value);
    float out = 0.0f;
    memcpy(&out, &host_bits, sizeof(out));
    return out;
}

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
/* Binary wire ABI: little-endian scalar encoding across heterogeneous hosts. */

#endif /* _MEMORY_INTENT_H */
