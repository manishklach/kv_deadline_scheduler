from kv_memory_intent.policies import DeadlineAwarePolicy, IntentAwarePolicy, LRUPolicy
from kv_memory_intent.schema import MemoryIntent, ObjectType, Phase, Priority, Tier


def block(name: str, **kwargs) -> MemoryIntent:
    base = dict(
        object_id=name,
        request_id="req-1",
        block_id=int(name.split("-")[-1]) if "-" in name else 0,
        object_type=ObjectType.KV_CACHE,
        phase=Phase.DECODE,
        priority=Priority.HOT,
        allowed_tiers={Tier.HBM, Tier.DRAM},
        current_tier=Tier.HBM,
        size_bytes=1024,
        request_priority=50,
        recency_score=0.5,
        created_step=0,
        last_access_step=0,
    )
    base.update(kwargs)
    return MemoryIntent(**base)


def test_lru_evicts_least_recently_accessed():
    policy = LRUPolicy()
    old = block("b-1", last_access_step=1)
    new = block("b-2", last_access_step=9)
    assert policy.choose_victim([new, old], 1024, 10) == old


def test_intent_aware_avoids_pinned_decode_critical():
    policy = IntentAwarePolicy()
    pinned = block("b-1", priority=Priority.DECODE_CRITICAL, pin_requested=True)
    cold = block(
        "b-2",
        priority=Priority.COLD,
        phase=Phase.DONE,
        request_priority=5,
        recency_score=0.0,
        compression_ok=True,
    )
    assert policy.choose_victim([pinned, cold], 1024, 10) == cold


def test_intent_aware_prefers_cold_over_hot():
    policy = IntentAwarePolicy()
    hot = block("b-1", priority=Priority.HOT, request_priority=90)
    cold = block("b-2", priority=Priority.COLD, request_priority=10, recency_score=0.0)
    assert policy.choose_victim([hot, cold], 1024, 10) == cold


def test_deadline_aware_protects_near_deadline_block():
    policy = DeadlineAwarePolicy()
    near_deadline = block("b-1", priority=Priority.HOT, deadline_us=500, request_priority=80)
    cold = block("b-2", priority=Priority.COLD, deadline_us=None, request_priority=10, recency_score=0.0)
    assert policy.choose_victim([near_deadline, cold], 1024, 10) == cold


def test_deadline_aware_prefetches_near_deadline_block():
    policy = DeadlineAwarePolicy()
    candidate = block(
        "b-1",
        current_tier=Tier.DRAM,
        priority=Priority.HOT,
        prefetch_ok=True,
        deadline_us=4000,
        expected_reuse_window_tokens=3,
    )
    assert policy.should_prefetch(candidate, 10) is True
