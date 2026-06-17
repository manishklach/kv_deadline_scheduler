from __future__ import annotations

import random

from kv_memory_intent.events import MemoryIntentEvent
from kv_memory_intent.schema import EventType, MemoryIntent, ObjectType, Phase, Priority, Tier

from .spec_intent import DraftNode, DraftTree


def generate_speculative_workload(
    acceptance_rate: float = 0.7,
    tree_width: int = 4,
    tree_depth: int = 3,
    seed: int = 42,
) -> tuple[DraftTree, list[MemoryIntentEvent]]:
    rng = random.Random(seed)
    tree = DraftTree()
    events: list[MemoryIntentEvent] = []
    node_id = 0
    step = 0
    frontier: list[tuple[int | None, int]] = [(None, 0)]

    while frontier:
        parent_id, depth = frontier.pop(0)
        if depth >= tree_depth:
            continue
        for width_index in range(tree_width):
            acceptance_prob = max(0.05, min(0.95, rng.gauss(acceptance_rate, 0.15)))
            object_id = f"draft:{node_id}"
            tree.nodes[node_id] = DraftNode(
                token_id=1000 + node_id,
                parent_id=parent_id,
                depth=depth,
                acceptance_prob=acceptance_prob,
                kv_object_id=object_id,
            )
            intent = MemoryIntent(
                object_id=object_id,
                request_id="spec-req-0",
                block_id=node_id,
                object_type=ObjectType.KV_CACHE,
                phase=Phase.VERIFY,
                priority=Priority.HOT if acceptance_prob >= 0.3 else Priority.COLD,
                allowed_tiers={Tier.HBM, Tier.DRAM},
                current_tier=Tier.HBM,
                size_bytes=256 * 1024,
                request_priority=80,
                recency_score=1.0 - (depth * 0.1),
                deadline_us=max(1, int((1.0 - acceptance_prob) * 2_000)),
                slack_us=max(1, int((1.0 - acceptance_prob) * 1_000)),
                recompute_cost_us=1500,
                spill_cost_us=100,
                expected_reuse_window_tokens=depth + 1,
                prefetch_ok=False,
                is_draft=True,
                is_committed=False,
                created_step=step,
                last_access_step=step,
            )
            events.append(MemoryIntentEvent(step=step, event_type=EventType.ALLOCATED, intent=intent, reason="draft alloc"))
            step += 1
            verified = intent.copy_with(phase=Phase.VERIFY, recency_score=1.0)
            events.append(MemoryIntentEvent(step=step, event_type=EventType.ACCESSED, intent=verified, reason="draft access"))
            step += 1
            if depth + 1 < tree_depth:
                frontier.append((node_id, depth + 1))
            node_id += 1

    return tree, events
