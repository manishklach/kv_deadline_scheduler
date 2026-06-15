"""Core memory intent schema."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import StrEnum


class ObjectType(StrEnum):
    KV_CACHE = "KV_CACHE"
    WEIGHT = "WEIGHT"
    ACTIVATION = "ACTIVATION"
    SCRATCH = "SCRATCH"


class Phase(StrEnum):
    PREFILL = "PREFILL"
    DECODE = "DECODE"
    VERIFY = "VERIFY"
    ROLLBACK = "ROLLBACK"
    DONE = "DONE"
    IDLE = "IDLE"


class Priority(StrEnum):
    DECODE_CRITICAL = "DECODE_CRITICAL"
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


class Tier(StrEnum):
    HBM = "HBM"
    DRAM = "DRAM"
    CXL = "CXL"
    NVME = "NVME"


class EventType(StrEnum):
    ALLOCATED = "ALLOCATED"
    ACCESSED = "ACCESSED"
    COMMITTED = "COMMITTED"
    MARKED_DECODE_CRITICAL = "MARKED_DECODE_CRITICAL"
    MARKED_COLD = "MARKED_COLD"
    SPILLED = "SPILLED"
    PREFETCHED = "PREFETCHED"
    MISS = "MISS"
    EVICTED = "EVICTED"
    FREED = "FREED"


@dataclass(slots=True)
class MemoryIntent:
    object_id: str
    request_id: str
    block_id: int
    object_type: ObjectType
    phase: Phase
    priority: Priority
    allowed_tiers: set[Tier]
    current_tier: Tier
    size_bytes: int
    request_priority: int = 0
    recency_score: float = 0.0
    deadline_us: int | None = None
    expected_reuse_window_tokens: int | None = None
    recompute_cost_us: int | None = None
    spill_cost_us: int | None = None
    compression_ok: bool = False
    recompute_ok: bool = False
    prefetch_ok: bool = False
    pin_requested: bool = False
    is_draft: bool = False
    is_committed: bool = False
    created_step: int = 0
    last_access_step: int = 0

    def __post_init__(self) -> None:
        if not self.object_id:
            raise ValueError("object_id must not be empty")
        if self.object_type == ObjectType.KV_CACHE and not self.request_id:
            raise ValueError("KV_CACHE objects must include a non-empty request_id")
        if self.block_id < 0:
            raise ValueError("block_id must be >= 0")
        if self.size_bytes <= 0:
            raise ValueError("size_bytes must be > 0")
        if not self.allowed_tiers:
            raise ValueError("allowed_tiers must not be empty")
        if self.current_tier not in self.allowed_tiers:
            raise ValueError("current_tier must be present in allowed_tiers")
        if not 0 <= self.request_priority <= 100:
            raise ValueError("request_priority must be in range 0..100")
        if not 0.0 <= self.recency_score <= 1.0:
            raise ValueError("recency_score must be in range 0.0..1.0")
        if self.priority == Priority.DECODE_CRITICAL:
            self.pin_requested = True

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["object_type"] = self.object_type.value
        data["phase"] = self.phase.value
        data["priority"] = self.priority.value
        data["allowed_tiers"] = [tier.value for tier in sorted(self.allowed_tiers, key=str)]
        data["current_tier"] = self.current_tier.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "MemoryIntent":
        return cls(
            object_id=str(data["object_id"]),
            request_id=str(data["request_id"]),
            block_id=int(data["block_id"]),
            object_type=ObjectType(str(data["object_type"])),
            phase=Phase(str(data["phase"])),
            priority=Priority(str(data["priority"])),
            allowed_tiers={Tier(str(value)) for value in data["allowed_tiers"]},
            current_tier=Tier(str(data["current_tier"])),
            size_bytes=int(data["size_bytes"]),
            request_priority=int(data.get("request_priority", 0)),
            recency_score=float(data.get("recency_score", 0.0)),
            deadline_us=int(data["deadline_us"]) if data.get("deadline_us") is not None else None,
            expected_reuse_window_tokens=(
                int(data["expected_reuse_window_tokens"])
                if data.get("expected_reuse_window_tokens") is not None
                else None
            ),
            recompute_cost_us=(
                int(data["recompute_cost_us"]) if data.get("recompute_cost_us") is not None else None
            ),
            spill_cost_us=int(data["spill_cost_us"]) if data.get("spill_cost_us") is not None else None,
            compression_ok=bool(data.get("compression_ok", False)),
            recompute_ok=bool(data.get("recompute_ok", False)),
            prefetch_ok=bool(data.get("prefetch_ok", False)),
            pin_requested=bool(data.get("pin_requested", False)),
            is_draft=bool(data.get("is_draft", False)),
            is_committed=bool(data.get("is_committed", False)),
            created_step=int(data.get("created_step", 0)),
            last_access_step=int(data.get("last_access_step", 0)),
        )

    def copy_with(self, **kwargs: object) -> "MemoryIntent":
        return replace(self, **kwargs)

    def normalized(self) -> "MemoryIntent":
        if self.phase == Phase.DONE and self.priority != Priority.COLD:
            return self.copy_with(priority=Priority.COLD)
        return self.copy_with()

    def is_decode_critical(self) -> bool:
        return self.priority == Priority.DECODE_CRITICAL or self.phase == Phase.DECODE

    def is_spillable(self) -> bool:
        return len(self.allowed_tiers - {Tier.HBM}) > 0 and not self.pin_requested

    def is_prefetchable(self) -> bool:
        return self.prefetch_ok and self.current_tier != Tier.HBM and Tier.HBM in self.allowed_tiers
