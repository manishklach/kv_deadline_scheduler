from kv_memory_intent.schema import MemoryIntent, ObjectType, Phase, Priority, Tier


def make_intent(**kwargs):
    base = dict(
        object_id="obj-1",
        request_id="req-1",
        block_id=0,
        object_type=ObjectType.KV_CACHE,
        phase=Phase.PREFILL,
        priority=Priority.HOT,
        allowed_tiers={Tier.HBM, Tier.DRAM},
        current_tier=Tier.HBM,
        size_bytes=1024,
    )
    base.update(kwargs)
    return MemoryIntent(**base)


def test_valid_memory_intent():
    intent = make_intent()
    assert intent.object_id == "obj-1"


def test_invalid_empty_object_id_raises():
    try:
        make_intent(object_id="")
    except ValueError as exc:
        assert "object_id" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_invalid_size_raises():
    try:
        make_intent(size_bytes=0)
    except ValueError as exc:
        assert "size_bytes" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_current_tier_not_allowed_raises():
    try:
        make_intent(allowed_tiers={Tier.DRAM}, current_tier=Tier.HBM)
    except ValueError as exc:
        assert "current_tier" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_decode_critical_auto_pins():
    intent = make_intent(priority=Priority.DECODE_CRITICAL, pin_requested=False)
    assert intent.pin_requested is True


def test_to_dict_from_dict_round_trip():
    intent = make_intent(
        request_priority=77,
        recency_score=0.4,
        compression_ok=True,
        recompute_ok=True,
        prefetch_ok=True,
        slack_us=900,
        arrival_step=4,
        target_decode_step=10,
    )
    round_trip = MemoryIntent.from_dict(intent.to_dict())
    assert round_trip.to_dict() == intent.to_dict()


def test_deadline_score_ordering():
    urgent = make_intent(
        phase=Phase.DECODE,
        priority=Priority.DECODE_CRITICAL,
        deadline_us=500,
        slack_us=200,
        request_priority=90,
        recompute_cost_us=5000,
    )
    cold = make_intent(
        phase=Phase.DONE,
        priority=Priority.COLD,
        deadline_us=None,
        request_priority=10,
        recompute_cost_us=50,
    )
    assert urgent.effective_deadline_score(10) > cold.effective_deadline_score(10)
    assert urgent.eviction_risk_score(10) > cold.eviction_risk_score(10)
