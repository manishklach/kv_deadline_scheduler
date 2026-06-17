from __future__ import annotations

import random
from dataclasses import dataclass

from kv_memory_intent.events import MemoryIntentEvent
from kv_memory_intent.schema import EventType, MemoryIntent
from kv_memory_intent.simulator import KVMemorySimulator, SimulationResult, policy_from_name

from .draft_workload import generate_speculative_workload
from .spec_intent import DraftTree, SpeculativeIntentPolicy


@dataclass(slots=True)
class SpeculativeBenchmarkResult:
    policy_name: str
    simulation: SimulationResult
    committed_blocks: int
    freed_rejected_blocks: int
    wasted_hbm_mb_on_rejected_drafts: float

    def to_dict(self) -> dict[str, int | float | str]:
        return {
            "policy_name": self.policy_name,
            "committed_blocks": self.committed_blocks,
            "freed_rejected_blocks": self.freed_rejected_blocks,
            "wasted_hbm_mb_on_rejected_drafts": round(self.wasted_hbm_mb_on_rejected_drafts, 6),
            "p50_latency_us": self.simulation.p50_latency_us,
            "p95_latency_us": self.simulation.p95_latency_us,
            "p99_latency_us": self.simulation.p99_latency_us,
            "decode_critical_misses": self.simulation.decode_critical_misses,
            "decode_critical_miss_rate": self.simulation.decode_critical_miss_rate,
        }


def _build_children(tree: DraftTree) -> dict[int | None, list[int]]:
    children: dict[int | None, list[int]] = {}
    for node_id, node in tree.nodes.items():
        children.setdefault(node.parent_id, []).append(node_id)
    return children


def generate_speculative_lifecycle_trace(
    *,
    acceptance_rate: float = 0.7,
    tree_width: int = 4,
    tree_depth: int = 3,
    seed: int = 42,
) -> tuple[DraftTree, list[MemoryIntentEvent], SpeculativeIntentPolicy]:
    tree, base_events = generate_speculative_workload(
        acceptance_rate=acceptance_rate,
        tree_width=tree_width,
        tree_depth=tree_depth,
        seed=seed,
    )
    policy = SpeculativeIntentPolicy()
    rng = random.Random(seed)
    current_blocks: dict[str, MemoryIntent] = {event.intent.object_id: event.intent for event in base_events}
    children = _build_children(tree)
    lifecycle_events = list(base_events)
    step = max((event.step for event in lifecycle_events), default=-1) + 1

    def free_subtree(intents: list[MemoryIntent]) -> None:
        nonlocal step
        for intent in intents:
            lifecycle_events.append(
                MemoryIntentEvent(
                    step=step,
                    event_type=EventType.FREED,
                    intent=intent.copy_with(last_access_step=step),
                    reason="speculative draft rejected",
                )
            )
            step += 1

    def resolve(node_id: int) -> None:
        nonlocal step
        node = tree.nodes[node_id]
        current = current_blocks.get(node.kv_object_id)
        if current is None:
            return
        verify_event = MemoryIntentEvent(
            step=step,
            event_type=EventType.ACCESSED,
            intent=current.copy_with(last_access_step=step),
            reason="speculative verify",
        )
        accepted = rng.random() < node.acceptance_prob
        doomed_intents = [
            current_blocks[doomed.kv_object_id]
            for doomed in [node, *tree.descendants(node_id)]
            if doomed.kv_object_id in current_blocks
        ]
        policy.process_verify_event(verify_event, tree, accepted=accepted, current_blocks=current_blocks)
        if accepted:
            committed = current_blocks[node.kv_object_id]
            lifecycle_events.append(
                MemoryIntentEvent(
                    step=step,
                    event_type=EventType.COMMITTED,
                    intent=committed.copy_with(last_access_step=step),
                    reason="speculative draft accepted",
                )
            )
            step += 1
            for child_id in children.get(node_id, []):
                resolve(child_id)
            return
        free_subtree(doomed_intents)

    for root_id in children.get(None, []):
        resolve(root_id)

    return tree, sorted(lifecycle_events, key=lambda event: event.step), policy


def run_speculative_policy_suite(
    *,
    hbm_capacity_bytes: int,
    dram_capacity_bytes: int,
    acceptance_rate: float = 0.7,
    tree_width: int = 4,
    tree_depth: int = 3,
    seed: int = 42,
) -> list[SpeculativeBenchmarkResult]:
    _, events, baseline_spec_policy = generate_speculative_lifecycle_trace(
        acceptance_rate=acceptance_rate,
        tree_width=tree_width,
        tree_depth=tree_depth,
        seed=seed,
    )
    policies = [
        policy_from_name("deadline"),
        SpeculativeIntentPolicy(),
    ]
    results: list[SpeculativeBenchmarkResult] = []
    committed_blocks = sum(1 for event in events if event.event_type == EventType.COMMITTED)
    freed_rejected_blocks = sum(1 for event in events if event.event_type == EventType.FREED)

    for policy in policies:
        simulator = KVMemorySimulator(
            policy=policy,
            hbm_capacity_bytes=hbm_capacity_bytes,
            dram_capacity_bytes=dram_capacity_bytes,
        )
        simulation = simulator.run(events)
        wasted = (
            baseline_spec_policy.wasted_hbm_mb_on_rejected_drafts
            if isinstance(policy, SpeculativeIntentPolicy)
            else 0.0
        )
        results.append(
            SpeculativeBenchmarkResult(
                policy_name=policy.name,
                simulation=simulation,
                committed_blocks=committed_blocks,
                freed_rejected_blocks=freed_rejected_blocks,
                wasted_hbm_mb_on_rejected_drafts=wasted,
            )
        )
    return results
