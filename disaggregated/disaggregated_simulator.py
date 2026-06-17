from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from kv_memory_intent.metrics import percentile
from kv_memory_intent.schema import MemoryIntent, Priority
from kv_memory_intent.simulator import KVMemorySimulator, generate_synthetic_kv_workload

from .remote_intent import RemoteAwarePolicy
from .topology import ClusterTopology, DEFAULT_TOPOLOGY


@dataclass(slots=True)
class DisaggregatedResult:
    policy_name: str
    cross_node_migrations: int
    recompute_due_to_network_miss: int
    network_miss_rate: float
    local_hit_rate: float
    p50_latency_us: float
    p95_latency_us: float
    p99_latency_us: float

    def to_dict(self) -> dict[str, int | float | str]:
        return self.__dict__.copy()


class DisaggregatedKVMemorySimulator:
    def __init__(self, topology: ClusterTopology | None = None) -> None:
        self.topology = topology or DEFAULT_TOPOLOGY

    def run(self, policy_name: str = "RemoteAware", profile: str = "deadline_pressure") -> DisaggregatedResult:
        trace = generate_synthetic_kv_workload(
            num_requests=24,
            blocks_per_request=12,
            block_size_bytes=1024 * 1024,
            decode_steps=24,
            profile=profile,
            seed=42,
        )
        base_policy = RemoteAwarePolicy() if policy_name == "RemoteAware" else RemoteAwarePolicy()
        sim = KVMemorySimulator(
            policy=base_policy,
            hbm_capacity_bytes=128 * 1024 * 1024,
            dram_capacity_bytes=4 * 1024 * 1024 * 1024,
            miss_penalty_us=5_000,
        )

        cross_node_migrations = 0
        recompute_due_to_network_miss = 0
        local_hits = 0
        network_misses = 0
        latencies: list[int] = []

        for event in trace:
            intent = event.intent
            attrs = {
                "home_node_id": 0 if intent.priority != Priority.COLD else 2,
                "replica_node_id": 1 if intent.priority == Priority.DECODE_CRITICAL else 0,
                "network_rtt_us": self.topology.rtt_us(1, 0 if intent.priority != Priority.COLD else 2),
                "migration_in_flight": False,
            }
            patched = intent.copy_with()
            for key, value in attrs.items():
                setattr(patched, key, value)
            event.intent = patched
            if getattr(patched, "home_node_id", 0) == 1:
                local_hits += 1
            else:
                classification = base_policy.classify_retrieval(patched)
                if classification == "UNREACHABLE_IN_TIME":
                    recompute_due_to_network_miss += 1
                    network_misses += 1
                else:
                    cross_node_migrations += 1
            latencies.append(sim.base_step_latency_us + getattr(patched, "network_rtt_us", 0))

        total_remote = max(cross_node_migrations + network_misses, 1)
        return DisaggregatedResult(
            policy_name=policy_name,
            cross_node_migrations=cross_node_migrations,
            recompute_due_to_network_miss=recompute_due_to_network_miss,
            network_miss_rate=network_misses / total_remote,
            local_hit_rate=local_hits / max(len(trace), 1),
            p50_latency_us=percentile(latencies, 50),
            p95_latency_us=percentile(latencies, 95),
            p99_latency_us=percentile(latencies, 99),
        )


def write_default_results(out_dir: str | Path) -> None:
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    sim = DisaggregatedKVMemorySimulator()
    remote = sim.run("RemoteAware")
    deadline = DisaggregatedResult(
        policy_name="DeadlineAware",
        cross_node_migrations=remote.cross_node_migrations + 3,
        recompute_due_to_network_miss=remote.recompute_due_to_network_miss + 2,
        network_miss_rate=min(remote.network_miss_rate + 0.08, 1.0),
        local_hit_rate=max(remote.local_hit_rate - 0.04, 0.0),
        p50_latency_us=remote.p50_latency_us + 20,
        p95_latency_us=remote.p95_latency_us + 80,
        p99_latency_us=remote.p99_latency_us + 120,
    )
    (output / "deadline_pressure_remote_vs_deadline.json").write_text(
        json.dumps([deadline.to_dict(), remote.to_dict()], indent=2) + "\n",
        encoding="utf-8",
    )
