#ifndef _MEMORY_INTENT_WIRE_H
#define _MEMORY_INTENT_WIRE_H

#include <stdbool.h>
#include <stdatomic.h>
#include <stdint.h>

#include "memory_intent.h"

#define MI_RING_MAGIC    0x4B564D49u
#define MI_RING_VERSION  1u
#define MI_RING_CAPACITY 4096u

typedef struct mi_ring_header {
    uint32_t magic;
    uint32_t version;
    uint32_t capacity;
    uint32_t _pad;
    _Atomic uint64_t head;
    _Atomic uint64_t tail;
} mi_ring_header_t;

typedef struct mi_ring_entry {
    uint8_t event_type;
    uint8_t _pad[7];
    memory_intent_t intent;
    uint64_t timestamp_ns;
} mi_ring_entry_t;

int mi_ring_init(mi_ring_header_t *ring);
int mi_ring_push(mi_ring_header_t *ring, const mi_ring_entry_t *entry);
int mi_ring_pop(mi_ring_header_t *ring, mi_ring_entry_t *out);
bool mi_ring_full(const mi_ring_header_t *ring);
bool mi_ring_empty(const mi_ring_header_t *ring);

#endif /* _MEMORY_INTENT_WIRE_H */
