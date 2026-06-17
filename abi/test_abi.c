#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "memory_intent_wire.h"

#define STATIC_ASSERT _Static_assert

STATIC_ASSERT(sizeof(memory_intent_t) == 98, "memory_intent_t size changed");
STATIC_ASSERT(offsetof(memory_intent_t, object_id) == 0, "object_id offset changed");
STATIC_ASSERT(offsetof(memory_intent_t, request_id) == 8, "request_id offset changed");
STATIC_ASSERT(offsetof(memory_intent_t, block_id) == 16, "block_id offset changed");
STATIC_ASSERT(offsetof(memory_intent_t, phase) == 24, "phase offset changed");
STATIC_ASSERT(offsetof(memory_intent_t, size_bytes) == 28, "size_bytes offset changed");
STATIC_ASSERT(offsetof(memory_intent_t, flags) == 62, "flags offset changed");
STATIC_ASSERT(offsetof(memory_intent_t, home_node_id) == 66, "home_node_id offset changed");
STATIC_ASSERT(offsetof(memory_intent_t, _reserved) == 82, "reserved offset changed");

int main(void)
{
    memory_intent_t intent;
    typedef struct test_ring {
        mi_ring_header_t header;
        mi_ring_entry_t entries[MI_RING_CAPACITY];
    } test_ring_t;
    test_ring_t *ring;
    mi_ring_entry_t entry;
    mi_ring_entry_t out;

    memset(&intent, 0, sizeof(intent));
    intent.abi_version = MEMORY_INTENT_ABI_VERSION;
    intent.object_type = MI_TYPE_KV_CACHE;
    intent.phase = MI_PHASE_DECODE;
    intent.priority = MI_PRI_DECODE_CRITICAL;
    intent.allowed_tiers = MI_TIER_HBM | MI_TIER_DRAM;
    intent.current_tier = MI_TIER_HBM;
    intent.size_bytes = 1048576;

    ring = calloc(1, sizeof(*ring));
    if (ring == NULL) {
        fprintf(stderr, "calloc failed\n");
        return 1;
    }
    if (mi_ring_init(&ring->header) != 0) {
        fprintf(stderr, "mi_ring_init failed\n");
        free(ring);
        return 1;
    }

    memset(&entry, 0, sizeof(entry));
    entry.event_type = 1;
    entry.intent = intent;
    entry.timestamp_ns = 42;

    if (mi_ring_push(&ring->header, &entry) != 0) {
        fprintf(stderr, "mi_ring_push failed\n");
        free(ring);
        return 1;
    }
    if (mi_ring_pop(&ring->header, &out) != 0) {
        fprintf(stderr, "mi_ring_pop failed\n");
        free(ring);
        return 1;
    }
    if (out.intent.size_bytes != intent.size_bytes || out.timestamp_ns != 42) {
        fprintf(stderr, "ring contents corrupted\n");
        free(ring);
        return 1;
    }

    printf("memory_intent_t=%zu bytes\n", sizeof(memory_intent_t));
    puts("ABI checks passed");
    free(ring);
    return 0;
}
