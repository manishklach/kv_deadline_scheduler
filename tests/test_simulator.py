from kv_memory_intent.metrics import compare_results
from kv_memory_intent.simulator import KVMemorySimulator, generate_synthetic_kv_workload, policy_from_name


def test_simulator_returns_valid_result():
    trace = generate_synthetic_kv_workload(4, 4, 1024, 20, seed=1)
    result = KVMemorySimulator(policy_from_name("lru"), 8 * 1024, 64 * 1024).run(trace)
    assert result.policy_name == "LRU"
    assert result.total_blocks > 0
    assert result.total_steps > 0


def test_hbm_capacity_is_respected():
    trace = generate_synthetic_kv_workload(3, 5, 2048, 18, seed=2)
    capacity = 10 * 1024
    result = KVMemorySimulator(policy_from_name("lru"), capacity, 64 * 1024).run(trace)
    assert result.actual_peak_hbm_used_bytes <= capacity


def test_synthetic_workload_creates_events():
    trace = generate_synthetic_kv_workload(2, 3, 1024, 5, seed=3)
    assert len(trace) > 0


def test_intent_aware_has_fewer_or_equal_decode_critical_misses_than_lru():
    trace = generate_synthetic_kv_workload(12, 8, 16 * 1024, 100, seed=42)
    lru = KVMemorySimulator(policy_from_name("lru"), 256 * 1024, 4 * 1024 * 1024).run(trace)
    intent = KVMemorySimulator(policy_from_name("intent"), 256 * 1024, 4 * 1024 * 1024).run(trace)
    assert intent.decode_critical_misses <= lru.decode_critical_misses


def test_compare_table_includes_all_policy_names():
    trace = generate_synthetic_kv_workload(8, 6, 8 * 1024, 50, seed=5)
    results = [
        KVMemorySimulator(policy_from_name(name), 128 * 1024, 2 * 1024 * 1024).run(trace)
        for name in ("lru", "intent", "deadline")
    ]
    table = compare_results(results)
    assert "LRU" in table
    assert "IntentAware" in table
    assert "DeadlineAware" in table
