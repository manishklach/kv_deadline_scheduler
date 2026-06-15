"""Compare policies on a synthetic trace."""

from __future__ import annotations

from kv_memory_intent.metrics import compare_results
from kv_memory_intent.simulator import KVMemorySimulator, generate_synthetic_kv_workload, policy_from_name


def main() -> None:
    trace = generate_synthetic_kv_workload(
        num_requests=16,
        blocks_per_request=12,
        block_size_bytes=16 * 1024,
        decode_steps=120,
        seed=11,
    )
    results = [
        KVMemorySimulator(
            policy=policy_from_name(name),
            hbm_capacity_bytes=3 * 1024 * 1024,
            dram_capacity_bytes=32 * 1024 * 1024,
        ).run(trace)
        for name in ("lru", "intent", "deadline")
    ]
    print(compare_results(results))
    print(
        "\nIntent-aware policies reduce decode-critical misses by protecting pinned "
        "decode blocks and evicting cold low-priority blocks first."
    )


if __name__ == "__main__":
    main()
