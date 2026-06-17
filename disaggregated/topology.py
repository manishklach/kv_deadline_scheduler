from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Node:
    id: int
    role: str
    hbm_gb: int
    dram_gb: int
    rtt_to: dict[int, int]


@dataclass(slots=True)
class ClusterTopology:
    nodes: list[Node]

    def node(self, node_id: int) -> Node:
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise KeyError(node_id)

    def rtt_us(self, src: int, dst: int) -> int:
        if src == dst:
            return 0
        return self.node(src).rtt_to[dst]


DEFAULT_TOPOLOGY = ClusterTopology(
    nodes=[
        Node(id=0, role="prefill", hbm_gb=80, dram_gb=512, rtt_to={1: 50, 2: 200}),
        Node(id=1, role="decode", hbm_gb=80, dram_gb=512, rtt_to={0: 50, 2: 200}),
        Node(id=2, role="storage", hbm_gb=0, dram_gb=2048, rtt_to={0: 200, 1: 200}),
    ]
)
