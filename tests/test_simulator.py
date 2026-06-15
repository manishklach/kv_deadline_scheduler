from pathlib import Path

from kv_memory_intent.metrics import SWEEP_COLUMNS, compare_results, write_sweep_csv
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


def test_workload_profiles_generate_non_empty_traces():
    for profile in (
        "balanced",
        "deadline_pressure",
        "rag_mixed_priority",
        "speculative_decode",
        "long_context_extreme",
    ):
        trace = generate_synthetic_kv_workload(2, 3, 1024, 5, seed=3, profile=profile)
        assert len(trace) > 0


def test_intent_aware_has_fewer_or_equal_decode_critical_misses_than_lru():
    trace = generate_synthetic_kv_workload(12, 8, 16 * 1024, 100, seed=42, profile="deadline_pressure")
    lru = KVMemorySimulator(policy_from_name("lru"), 256 * 1024, 4 * 1024 * 1024).run(trace)
    intent = KVMemorySimulator(policy_from_name("intent"), 256 * 1024, 4 * 1024 * 1024).run(trace)
    assert intent.decode_critical_misses <= lru.decode_critical_misses


def test_compare_table_includes_all_policy_names():
    trace = generate_synthetic_kv_workload(8, 6, 8 * 1024, 50, seed=5)
    results = [
        KVMemorySimulator(policy_from_name(name), 128 * 1024, 2 * 1024 * 1024).run(trace)
        for name in ("lru", "hotcold", "predictive", "intent", "deadline")
    ]
    table = compare_results(results)
    assert "LRU" in table
    assert "HotCold" in table
    assert "PredictiveHotness" in table
    assert "IntentAware" in table
    assert "KVDeadline" in table


def test_sweep_output_csv_contains_expected_columns(tmp_path: Path):
    out = tmp_path / "sweep.csv"
    write_sweep_csv(
        [
            {
                "policy": "KVDeadline",
                "hbm_mb": 128,
                "p50_latency_us": 50.0,
                "p95_latency_us": 250.0,
                "p99_latency_us": 5000.0,
                "total_misses": 10,
                "decode_critical_misses": 2,
                "evictions": 4,
                "decode_critical_evictions": 0,
                "spills": 4,
                "prefetches": 1,
                "hbm_bytes_saved": 1024,
            }
        ],
        out,
    )
    header = out.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header == SWEEP_COLUMNS


def test_decision_log_gets_written(tmp_path: Path):
    trace = generate_synthetic_kv_workload(8, 6, 8 * 1024, 50, seed=5, profile="deadline_pressure")
    simulator = KVMemorySimulator(policy_from_name("deadline"), 128 * 1024, 2 * 1024 * 1024)
    simulator.run(trace)
    out = tmp_path / "decisions.jsonl"
    simulator.write_decision_log(out)
    assert out.exists()
    assert out.read_text(encoding="utf-8").strip()
