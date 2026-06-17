from __future__ import annotations

from dataclasses import dataclass, field

from kv_memory_intent.events import MemoryIntentEvent
from kv_memory_intent.policies import DeadlineAwarePolicy
from kv_memory_intent.schema import MemoryIntent, Phase, Priority


@dataclass(slots=True)
class DraftNode:
    token_id: int
    parent_id: int | None
    depth: int
    acceptance_prob: float
    kv_object_id: str


@dataclass(slots=True)
class DraftTree:
    nodes: dict[int, DraftNode] = field(default_factory=dict)

    def descendants(self, node_id: int) -> list[DraftNode]:
        found: list[DraftNode] = []
        pending = [node_id]
        while pending:
            current = pending.pop()
            for child_id, node in self.nodes.items():
                if node.parent_id == current:
                    found.append(node)
                    pending.append(child_id)
        return found


class SpeculativeIntentPolicy(DeadlineAwarePolicy):
    def __init__(self) -> None:
        super().__init__()
        self.name = "SpeculativeIntent"
        self.draft_blocks_freed_on_rejection = 0
        self.wasted_hbm_mb_on_rejected_drafts = 0.0

    def process_verify_event(
        self,
        event: MemoryIntentEvent,
        tree: DraftTree,
        accepted: bool,
        current_blocks: dict[str, MemoryIntent],
    ) -> None:
        node_id = int(event.intent.block_id)
        if accepted:
            for node in [tree.nodes.get(node_id), *tree.descendants(node_id)]:
                if node is None or node.kv_object_id not in current_blocks:
                    continue
                current = current_blocks[node.kv_object_id]
                current_blocks[node.kv_object_id] = current.copy_with(
                    priority=Priority.DECODE_CRITICAL,
                    phase=Phase.DECODE,
                    pin_requested=True,
                    is_draft=False,
                    is_committed=True,
                )
            return

        doomed = [node for node in [tree.nodes.get(node_id), *tree.descendants(node_id)] if node is not None]
        for node in doomed:
            current = current_blocks.pop(node.kv_object_id, None)
            if current is None:
                continue
            self.draft_blocks_freed_on_rejection += 1
            self.wasted_hbm_mb_on_rejected_drafts += current.size_bytes / (1024 * 1024)

    def prepare_draft_intent(self, intent: MemoryIntent, acceptance_prob: float) -> MemoryIntent:
        if not intent.is_draft:
            return intent
        if acceptance_prob < 0.3:
            return intent.copy_with(priority=Priority.COLD, phase=Phase.VERIFY)
        expected_acceptance_latency = max(1, int((1.0 - acceptance_prob) * 2_000))
        return intent.copy_with(deadline_us=expected_acceptance_latency, slack_us=max(expected_acceptance_latency // 2, 1))
