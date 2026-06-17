from kv_memory_intent.events import MemoryIntentEvent
from kv_memory_intent.schema import EventType, MemoryIntent, ObjectType, Phase, Priority, Tier
from kv_memory_intent.speculative import (
    DraftNode,
    DraftTree,
    SpeculativeIntentPolicy,
    generate_speculative_lifecycle_trace,
    generate_speculative_workload,
    run_speculative_policy_suite,
)


def make_intent(object_id: str, block_id: int, draft: bool = True) -> MemoryIntent:
    return MemoryIntent(
        object_id=object_id,
        request_id="spec-req",
        block_id=block_id,
        object_type=ObjectType.KV_CACHE,
        phase=Phase.VERIFY,
        priority=Priority.HOT,
        allowed_tiers={Tier.HBM, Tier.DRAM},
        current_tier=Tier.HBM,
        size_bytes=1024,
        request_priority=90,
        recency_score=1.0,
        deadline_us=1000,
        slack_us=500,
        recompute_cost_us=1000,
        spill_cost_us=100,
        expected_reuse_window_tokens=2,
        is_draft=draft,
        is_committed=not draft,
        created_step=0,
        last_access_step=0,
    )


def test_prepare_draft_intent_downgrades_low_probability_blocks():
    policy = SpeculativeIntentPolicy()
    intent = make_intent("draft:1", 1, draft=True)
    prepared = policy.prepare_draft_intent(intent, 0.2)
    assert prepared.priority == Priority.COLD


def test_verify_rejection_frees_descendants():
    policy = SpeculativeIntentPolicy()
    tree = DraftTree(
        nodes={
            1: DraftNode(token_id=1, parent_id=None, depth=0, acceptance_prob=0.2, kv_object_id="draft:1"),
            2: DraftNode(token_id=2, parent_id=1, depth=1, acceptance_prob=0.2, kv_object_id="draft:2"),
        }
    )
    current = {"draft:1": make_intent("draft:1", 1), "draft:2": make_intent("draft:2", 2)}
    event = MemoryIntentEvent(step=0, event_type=EventType.ACCESSED, intent=make_intent("draft:1", 1))
    policy.process_verify_event(event, tree, accepted=False, current_blocks=current)
    assert current == {}
    assert policy.draft_blocks_freed_on_rejection == 2


def test_generate_speculative_workload_produces_events():
    tree, events = generate_speculative_workload()
    assert tree.nodes
    assert events
    assert events[0].event_type == EventType.ALLOCATED


def test_generate_speculative_lifecycle_trace_includes_terminal_events():
    tree, events, policy = generate_speculative_lifecycle_trace(seed=7)
    assert tree.nodes
    assert any(event.event_type == EventType.COMMITTED for event in events)
    assert any(event.event_type == EventType.FREED for event in events)
    assert policy.draft_blocks_freed_on_rejection >= 0


def test_speculative_policy_suite_returns_deadline_and_speculative_results():
    results = run_speculative_policy_suite(
        hbm_capacity_bytes=2 * 1024 * 1024,
        dram_capacity_bytes=32 * 1024 * 1024,
        seed=7,
    )
    names = {result.policy_name for result in results}
    assert "KVDeadline" in names
    assert "SpeculativeIntent" in names
