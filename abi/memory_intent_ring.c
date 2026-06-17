#include "memory_intent_wire.h"

#include <errno.h>
#include <stddef.h>
#include <string.h>

static mi_ring_entry_t *mi_ring_entries(mi_ring_header_t *ring)
{
    return (mi_ring_entry_t *)(ring + 1);
}

static const mi_ring_entry_t *mi_ring_entries_const(const mi_ring_header_t *ring)
{
    return (const mi_ring_entry_t *)(ring + 1);
}

int mi_ring_init(mi_ring_header_t *ring)
{
    if (ring == NULL) {
        return EINVAL;
    }
    ring->magic = MI_RING_MAGIC;
    ring->version = MI_RING_VERSION;
    ring->capacity = MI_RING_CAPACITY;
    ring->_pad = 0;
    atomic_store(&ring->head, 0);
    atomic_store(&ring->tail, 0);
    return 0;
}

bool mi_ring_full(const mi_ring_header_t *ring)
{
    uint64_t head = atomic_load(&ring->head);
    uint64_t tail = atomic_load(&ring->tail);
    return (head - tail) >= ring->capacity;
}

bool mi_ring_empty(const mi_ring_header_t *ring)
{
    return atomic_load(&ring->head) == atomic_load(&ring->tail);
}

int mi_ring_push(mi_ring_header_t *ring, const mi_ring_entry_t *entry)
{
    uint64_t head;
    mi_ring_entry_t *entries;

    if (ring == NULL || entry == NULL) {
        return EINVAL;
    }
    if (ring->magic != MI_RING_MAGIC || ring->version != MI_RING_VERSION || ring->capacity == 0) {
        return EPROTO;
    }
    if (mi_ring_full(ring)) {
        return ENOSPC;
    }

    head = atomic_load(&ring->head);
    entries = mi_ring_entries(ring);
    entries[head & (ring->capacity - 1)] = *entry;
    atomic_store(&ring->head, head + 1);
    return 0;
}

int mi_ring_pop(mi_ring_header_t *ring, mi_ring_entry_t *out)
{
    uint64_t tail;
    const mi_ring_entry_t *entries;

    if (ring == NULL || out == NULL) {
        return EINVAL;
    }
    if (ring->magic != MI_RING_MAGIC || ring->version != MI_RING_VERSION || ring->capacity == 0) {
        return EPROTO;
    }
    if (mi_ring_empty(ring)) {
        return ENODATA;
    }

    tail = atomic_load(&ring->tail);
    entries = mi_ring_entries_const(ring);
    *out = entries[tail & (ring->capacity - 1)];
    atomic_store(&ring->tail, tail + 1);
    return 0;
}
