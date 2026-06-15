"""Passive vLLM adapter skeleton."""

from __future__ import annotations

from ..events import MemoryIntentEvent
from ..schema import EventType, MemoryIntent, ObjectType, Phase, Priority, Tier


class VLLMIntentAdapter:
    """
    Passive adapter skeleton for mapping vLLM KV block lifecycle events
    into MemoryIntentEvent records.

    This file intentionally does not import vLLM. It documents the expected
    integration points and provides helper methods that future hooks can call.
    """

    def _make_intent(
        self,
        object_id: str,
        request_id: str,
        block_id: int,
        phase: Phase,
        priority: Priority,
        current_tier: Tier = Tier.HBM,
        size_bytes: int = 16 * 1024,
        request_priority: int = 50,
    ) -> MemoryIntent:
        return MemoryIntent(
            object_id=object_id,
            request_id=request_id,
            block_id=block_id,
            object_type=ObjectType.KV_CACHE,
            phase=phase,
            priority=priority,
            allowed_tiers={Tier.HBM, Tier.DRAM},
            current_tier=current_tier,
            size_bytes=size_bytes,
            request_priority=request_priority,
        )

    def on_block_allocated(self, step: int, object_id: str, request_id: str, block_id: int) -> MemoryIntentEvent:
        return MemoryIntentEvent(
            step=step,
            event_type=EventType.ALLOCATED,
            intent=self._make_intent(object_id, request_id, block_id, Phase.PREFILL, Priority.WARM),
            reason="vLLM passive allocation hook",
        )

    def on_block_accessed(self, step: int, object_id: str, request_id: str, block_id: int) -> MemoryIntentEvent:
        return MemoryIntentEvent(
            step=step,
            event_type=EventType.ACCESSED,
            intent=self._make_intent(object_id, request_id, block_id, Phase.DECODE, Priority.HOT),
            reason="vLLM passive access hook",
        )

    def on_block_freed(self, step: int, object_id: str, request_id: str, block_id: int) -> MemoryIntentEvent:
        return MemoryIntentEvent(
            step=step,
            event_type=EventType.FREED,
            intent=self._make_intent(object_id, request_id, block_id, Phase.DONE, Priority.COLD),
            reason="vLLM passive free hook",
        )

    def on_request_scheduled(self, step: int, object_id: str, request_id: str, block_id: int) -> MemoryIntentEvent:
        return MemoryIntentEvent(
            step=step,
            event_type=EventType.MARKED_DECODE_CRITICAL,
            intent=self._make_intent(object_id, request_id, block_id, Phase.DECODE, Priority.DECODE_CRITICAL),
            reason="vLLM request scheduled hook",
        )

    def on_decode_step(self, step: int, object_id: str, request_id: str, block_id: int) -> MemoryIntentEvent:
        return MemoryIntentEvent(
            step=step,
            event_type=EventType.ACCESSED,
            intent=self._make_intent(object_id, request_id, block_id, Phase.DECODE, Priority.DECODE_CRITICAL),
            reason="vLLM decode step hook",
        )

    def on_prefill_step(self, step: int, object_id: str, request_id: str, block_id: int) -> MemoryIntentEvent:
        return MemoryIntentEvent(
            step=step,
            event_type=EventType.ACCESSED,
            intent=self._make_intent(object_id, request_id, block_id, Phase.PREFILL, Priority.WARM),
            reason="vLLM prefill step hook",
        )
