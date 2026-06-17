from __future__ import annotations

from dataclasses import dataclass

from kv_memory_intent.policies import DeadlineAwarePolicy
from kv_memory_intent.schema import MemoryIntent


@dataclass(slots=True)
class RemoteMemoryIntent:
    base: MemoryIntent
    home_node_id: int
    replica_node_id: int = 0
    network_rtt_us: int = 0
    migration_in_flight: bool = False

    def unreachable_in_time(self) -> bool:
        if self.base.deadline_us is None:
            return False
        return self.base.deadline_us < (self.network_rtt_us * 1.5)


class RemoteAwarePolicy(DeadlineAwarePolicy):
    def __init__(self) -> None:
        super().__init__()
        self.name = "RemoteAware"

    def eviction_score(self, block: MemoryIntent, current_step: int) -> float:
        score = super().eviction_score(block, current_step)
        remote_rtt = getattr(block, "network_rtt_us", 0)
        if getattr(block, "migration_in_flight", False):
            return -10_000.0
        if getattr(block, "home_node_id", 0) not in (0, None):
            score -= min(float(remote_rtt) / 10.0, 300.0)
            if block.deadline_us is not None and block.deadline_us < (remote_rtt * 1.5):
                score -= 500.0
        return score

    def classify_retrieval(self, block: MemoryIntent) -> str:
        remote_rtt = getattr(block, "network_rtt_us", 0)
        if getattr(block, "migration_in_flight", False):
            return "MIGRATION_IN_FLIGHT"
        if block.deadline_us is not None and block.deadline_us < (remote_rtt * 1.5):
            return "UNREACHABLE_IN_TIME"
        return "FETCH_REMOTE"
