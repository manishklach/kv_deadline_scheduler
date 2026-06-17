"""Passive vLLM-style trace adapter."""

from __future__ import annotations

from ..events import MemoryIntentEvent
from ..schema import EventType, MemoryIntent, ObjectType, Phase, Priority, Tier
from ..trace import IntentTraceRecorder


class VLLMIntentAdapter:
    """
    Passive adapter for mapping vLLM-style KV block lifecycle signals
    into MemoryIntentEvent records.

    This adapter intentionally does not import vLLM. It provides a small
    stable surface that future vLLM hooks can call.
    """

    def __init__(
        self,
        recorder: IntentTraceRecorder | None = None,
        default_block_size_bytes: int = 16 * 1024,
        default_allowed_tiers: set[Tier] | None = None,
    ) -> None:
        self.recorder = recorder or IntentTraceRecorder()
        self.default_block_size_bytes = default_block_size_bytes
        self.default_allowed_tiers = default_allowed_tiers or {Tier.HBM, Tier.DRAM}
        self.blocks: dict[tuple[str, int], MemoryIntent] = {}
        self.request_metadata: dict[str, dict[str, int | None]] = {}

    def _object_id(self, request_id: str, block_id: int) -> str:
        return f"{request_id}:kv:{block_id}"

    def _sequence_request_id(self, sequence: object) -> str:
        request_id = getattr(sequence, "request_id", None) or getattr(sequence, "seq_id", None)
        if request_id is None:
            raise ValueError("sequence must expose request_id or seq_id")
        return str(request_id)

    def _sequence_block_ids(self, sequence: object) -> list[int]:
        block_ids = getattr(sequence, "active_block_ids", None)
        if block_ids is None:
            block_ids = getattr(sequence, "block_ids", None)
        if block_ids is None:
            return []
        return [int(block_id) for block_id in block_ids]

    def _request_defaults(self, request_id: str) -> dict[str, int | None]:
        return self.request_metadata.setdefault(
            request_id,
            {
                "request_priority": 50,
                "deadline_us": None,
                "arrival_step": None,
                "last_decode_step": None,
            },
        )

    def _record(self, event: MemoryIntentEvent) -> MemoryIntentEvent:
        self.recorder.record(event)
        self.blocks[(event.intent.request_id, event.intent.block_id)] = event.intent.copy_with()
        return event

    def _compute_slack(
        self,
        deadline_us: int,
        *,
        offset: int = 0,
        request_priority: int = 50,
    ) -> int:
        base = max(50, deadline_us // 5)
        position_penalty = offset * 40
        priority_bonus = (request_priority // 10) * 10
        return max(50, base - position_penalty + priority_bonus)

    def _make_intent(
        self,
        request_id: str,
        block_id: int,
        *,
        phase: Phase,
        priority: Priority,
        request_priority: int | None = None,
        deadline_us: int | None = None,
        size_bytes: int | None = None,
        is_draft: bool = False,
        is_committed: bool = False,
        prefetch_ok: bool = False,
        pin_requested: bool = False,
        compression_ok: bool = False,
        recompute_ok: bool = False,
        expected_reuse_window_tokens: int | None = None,
        recency_score: float = 0.0,
        created_step: int = 0,
        last_access_step: int = 0,
    ) -> MemoryIntent:
        request_meta = self._request_defaults(request_id)
        resolved_priority = (
            request_priority if request_priority is not None else int(request_meta.get("request_priority") or 50)
        )
        resolved_deadline = deadline_us if deadline_us is not None else request_meta.get("deadline_us")
        arrival_step = request_meta.get("arrival_step")
        resolved_slack = (
            self._compute_slack(int(resolved_deadline), offset=0, request_priority=resolved_priority)
            if isinstance(resolved_deadline, int)
            else None
        )
        return MemoryIntent(
            object_id=self._object_id(request_id, block_id),
            request_id=request_id,
            block_id=block_id,
            object_type=ObjectType.KV_CACHE,
            phase=phase,
            priority=priority,
            allowed_tiers=set(self.default_allowed_tiers),
            current_tier=Tier.HBM,
            size_bytes=size_bytes or self.default_block_size_bytes,
            request_priority=resolved_priority,
            recency_score=recency_score,
            deadline_us=resolved_deadline if isinstance(resolved_deadline, int) else None,
            slack_us=resolved_slack,
            arrival_step=int(arrival_step) if isinstance(arrival_step, int) else None,
            target_decode_step=None,
            expected_reuse_window_tokens=expected_reuse_window_tokens,
            recompute_cost_us=4_000 if priority == Priority.DECODE_CRITICAL else 250,
            spill_cost_us=200,
            compression_ok=compression_ok,
            recompute_ok=recompute_ok,
            prefetch_ok=prefetch_ok,
            pin_requested=pin_requested,
            is_draft=is_draft,
            is_committed=is_committed,
            created_step=created_step,
            last_access_step=last_access_step,
        )

    def _get_or_create_block(
        self,
        step: int,
        request_id: str,
        block_id: int,
        *,
        phase: Phase,
        priority: Priority,
        decode_critical: bool = False,
        request_priority: int | None = None,
        deadline_us: int | None = None,
        is_draft: bool = False,
        reason_prefix: str = "",
    ) -> tuple[MemoryIntent, str | None]:
        key = (request_id, block_id)
        if key in self.blocks:
            resolved_priority = request_priority if request_priority is not None else self.blocks[key].request_priority
            resolved_deadline = deadline_us if deadline_us is not None else self.blocks[key].deadline_us
            block = self.blocks[key].copy_with(
                phase=phase,
                priority=Priority.DECODE_CRITICAL if decode_critical else priority,
                request_priority=resolved_priority,
                deadline_us=resolved_deadline,
                slack_us=(
                    self._compute_slack(resolved_deadline, offset=0, request_priority=resolved_priority)
                    if resolved_deadline is not None
                    else self.blocks[key].slack_us
                ),
                prefetch_ok=decode_critical or self.blocks[key].prefetch_ok,
                pin_requested=decode_critical or self.blocks[key].pin_requested,
                is_draft=is_draft if is_draft else self.blocks[key].is_draft,
                last_access_step=step,
            )
            self.blocks[key] = block
            return block, None
        block = self._make_intent(
            request_id,
            block_id,
            phase=phase,
            priority=Priority.DECODE_CRITICAL if decode_critical else priority,
            request_priority=request_priority,
            deadline_us=deadline_us,
            is_draft=is_draft,
            prefetch_ok=decode_critical,
            pin_requested=decode_critical,
            created_step=step,
            last_access_step=step,
        )
        self.blocks[key] = block
        warning = "block was lazily created by adapter because access arrived before allocation"
        if reason_prefix:
            warning = f"{reason_prefix}; {warning}"
        return block, warning

    def on_request_scheduled(
        self,
        step: int,
        request_id: str,
        request_priority: int = 50,
        deadline_us: int | None = None,
    ) -> list[MemoryIntentEvent]:
        self.request_metadata[request_id] = {
            "request_priority": request_priority,
            "deadline_us": deadline_us,
            "arrival_step": step,
            "last_decode_step": None,
        }
        return []

    def on_block_allocated(
        self,
        step: int,
        request_id: str,
        block_id: int,
        phase: Phase = Phase.PREFILL,
        request_priority: int | None = None,
        deadline_us: int | None = None,
        size_bytes: int | None = None,
        is_draft: bool = False,
    ) -> MemoryIntentEvent:
        priority = Priority.WARM if phase == Phase.PREFILL else Priority.COLD if is_draft else Priority.HOT
        intent = self._make_intent(
            request_id,
            block_id,
            phase=phase,
            priority=priority,
            request_priority=request_priority,
            deadline_us=deadline_us,
            size_bytes=size_bytes,
            is_draft=is_draft,
            is_committed=False,
            prefetch_ok=False,
            pin_requested=False,
            compression_ok=False,
            recompute_ok=False,
            expected_reuse_window_tokens=32 if phase == Phase.PREFILL else 64,
            recency_score=0.2,
            created_step=step,
            last_access_step=step,
        )
        event = MemoryIntentEvent(
            step=step,
            event_type=EventType.ALLOCATED,
            intent=intent,
            reason="vLLM-style block allocation",
        )
        return self._record(event)

    def on_block_accessed(
        self,
        step: int,
        request_id: str,
        block_id: int,
        phase: Phase = Phase.DECODE,
        decode_critical: bool = False,
    ) -> MemoryIntentEvent:
        priority = Priority.DECODE_CRITICAL if decode_critical else Priority.HOT if phase == Phase.DECODE else Priority.WARM
        block, warning = self._get_or_create_block(
            step,
            request_id,
            block_id,
            phase=phase,
            priority=priority,
            decode_critical=decode_critical,
        )
        event = MemoryIntentEvent(
            step=step,
            event_type=EventType.ACCESSED,
            intent=block.copy_with(
                recency_score=1.0,
                last_access_step=step,
                prefetch_ok=decode_critical,
                pin_requested=decode_critical or block.pin_requested,
            ),
            reason=warning or "vLLM-style block access",
        )
        return self._record(event)

    def on_decode_step(
        self,
        step: int,
        request_id: str,
        active_block_ids: list[int],
        deadline_us: int | None = None,
        request_priority: int | None = None,
    ) -> list[MemoryIntentEvent]:
        request_meta = self._request_defaults(request_id)
        if request_priority is not None:
            request_meta["request_priority"] = request_priority
        if deadline_us is not None:
            request_meta["deadline_us"] = deadline_us
        request_meta["last_decode_step"] = step

        events: list[MemoryIntentEvent] = []
        for offset, block_id in enumerate(active_block_ids):
            block, warning = self._get_or_create_block(
                step,
                request_id,
                block_id,
                phase=Phase.DECODE,
                priority=Priority.DECODE_CRITICAL,
                decode_critical=True,
                request_priority=request_priority,
                deadline_us=deadline_us,
                reason_prefix=f"decode step for {request_id}",
            )
            marked = MemoryIntentEvent(
                step=step,
                event_type=EventType.MARKED_DECODE_CRITICAL,
                intent=block.copy_with(
                    phase=Phase.DECODE,
                    priority=Priority.DECODE_CRITICAL,
                    pin_requested=True,
                    prefetch_ok=True,
                    deadline_us=deadline_us if deadline_us is not None else block.deadline_us,
                    slack_us=(
                        self._compute_slack(
                            deadline_us,
                            offset=offset,
                            request_priority=int(request_meta.get("request_priority") or 50),
                        )
                        if deadline_us is not None
                        else block.slack_us
                    ),
                    target_decode_step=step + offset,
                    expected_reuse_window_tokens=1 + offset,
                    recency_score=max(0.8, 1.0 - (offset * 0.1)),
                    last_access_step=step,
                ),
                reason=warning or "vLLM-style decode-critical marking",
            )
            events.append(self._record(marked))
            events.append(self.on_block_accessed(step, request_id, block_id, phase=Phase.DECODE, decode_critical=True))
        return events

    def on_prefill_step(
        self,
        step: int,
        request_id: str,
        block_ids: list[int],
    ) -> list[MemoryIntentEvent]:
        events: list[MemoryIntentEvent] = []
        for block_id in block_ids:
            block, warning = self._get_or_create_block(
                step,
                request_id,
                block_id,
                phase=Phase.PREFILL,
                priority=Priority.WARM,
            )
            event = MemoryIntentEvent(
                step=step,
                event_type=EventType.ACCESSED,
                intent=block.copy_with(
                    phase=Phase.PREFILL,
                    priority=Priority.WARM,
                    prefetch_ok=False,
                    pin_requested=False,
                    recency_score=0.7,
                    last_access_step=step,
                ),
                reason=warning or "vLLM-style prefill access",
            )
            events.append(self._record(event))
        return events

    def on_block_committed(
        self,
        step: int,
        request_id: str,
        block_id: int,
    ) -> MemoryIntentEvent:
        block, warning = self._get_or_create_block(
            step,
            request_id,
            block_id,
            phase=Phase.VERIFY,
            priority=Priority.WARM,
        )
        event = MemoryIntentEvent(
            step=step,
            event_type=EventType.COMMITTED,
            intent=block.copy_with(
                is_committed=True,
                is_draft=False,
                priority=Priority.WARM if block.phase != Phase.DECODE else Priority.HOT,
                last_access_step=step,
            ),
            reason=warning or "vLLM-style draft commit",
        )
        return self._record(event)

    def on_block_marked_cold(
        self,
        step: int,
        request_id: str,
        block_id: int,
        expected_reuse_window_tokens: int | None = None,
    ) -> MemoryIntentEvent:
        block, warning = self._get_or_create_block(
            step,
            request_id,
            block_id,
            phase=Phase.IDLE,
            priority=Priority.COLD,
        )
        event = MemoryIntentEvent(
            step=step,
            event_type=EventType.MARKED_COLD,
            intent=block.copy_with(
                phase=Phase.IDLE,
                priority=Priority.COLD,
                compression_ok=True,
                recompute_ok=not block.is_committed,
                prefetch_ok=expected_reuse_window_tokens is None or expected_reuse_window_tokens < 1_000,
                expected_reuse_window_tokens=expected_reuse_window_tokens,
                pin_requested=False,
                recency_score=0.0,
            ),
            reason=warning or "vLLM-style cold marking",
        )
        return self._record(event)

    def on_block_freed(
        self,
        step: int,
        request_id: str,
        block_id: int,
    ) -> MemoryIntentEvent:
        block, warning = self._get_or_create_block(
            step,
            request_id,
            block_id,
            phase=Phase.DONE,
            priority=Priority.COLD,
        )
        event = MemoryIntentEvent(
            step=step,
            event_type=EventType.FREED,
            intent=block.copy_with(
                phase=Phase.DONE,
                priority=Priority.COLD,
                pin_requested=False,
                prefetch_ok=False,
                current_tier=Tier.DRAM if Tier.DRAM in block.allowed_tiers else block.current_tier,
                recency_score=0.0,
            ),
            reason=warning or "vLLM-style block free",
        )
        return self._record(event)

    def on_request_finished(
        self,
        step: int,
        request_id: str,
        block_ids: list[int],
    ) -> list[MemoryIntentEvent]:
        events: list[MemoryIntentEvent] = []
        for block_id in block_ids:
            key = (request_id, block_id)
            block, warning = self._get_or_create_block(
                step,
                request_id,
                block_id,
                phase=Phase.DONE,
                priority=Priority.COLD,
            )
            cold_event = MemoryIntentEvent(
                step=step,
                event_type=EventType.MARKED_COLD,
                intent=block.copy_with(
                    phase=Phase.DONE,
                    priority=Priority.COLD,
                    pin_requested=False,
                    prefetch_ok=False,
                    compression_ok=True,
                    recompute_ok=False,
                    recency_score=0.0,
                ),
                reason=warning or "request finished; block marked done",
            )
            events.append(self._record(cold_event))
            events.append(self.on_block_freed(step + 1, request_id, block_id))
            self.blocks.pop(key, None)
        self.request_metadata.pop(request_id, None)
        return events

    def emit_sequence_accesses(self, sequence: object) -> list[MemoryIntentEvent]:
        request_id = self._sequence_request_id(sequence)
        block_ids = self._sequence_block_ids(sequence)
        decode_depth = int(getattr(sequence, "decode_depth", 0) or 0)
        deadline_us = getattr(sequence, "deadline_us", None)
        request_priority = getattr(sequence, "request_priority", None)
        if request_id not in self.request_metadata:
            self.on_request_scheduled(
                step=int(getattr(sequence, "step", 0) or 0),
                request_id=request_id,
                request_priority=int(request_priority) if request_priority is not None else 50,
                deadline_us=int(deadline_us) if deadline_us is not None else None,
            )
        if decode_depth > 0:
            return self.on_decode_step(
                step=int(getattr(sequence, "step", 0) or 0),
                request_id=request_id,
                active_block_ids=block_ids,
                deadline_us=int(deadline_us) if deadline_us is not None else None,
                request_priority=int(request_priority) if request_priority is not None else None,
            )
        return self.on_prefill_step(
            step=int(getattr(sequence, "step", 0) or 0),
            request_id=request_id,
            block_ids=block_ids,
        )

    def emit_sequence_spill(self, sequence: object) -> list[MemoryIntentEvent]:
        request_id = self._sequence_request_id(sequence)
        step = int(getattr(sequence, "step", 0) or 0)
        events: list[MemoryIntentEvent] = []
        for block_id in self._sequence_block_ids(sequence):
            key = (request_id, block_id)
            block = self.blocks.get(key)
            if block is None:
                continue
            event = MemoryIntentEvent(
                step=step,
                event_type=EventType.SPILLED,
                intent=block.copy_with(current_tier=Tier.DRAM),
                reason="sequence preempted; block spilled",
            )
            events.append(self._record(event))
        return events

    def emit_sequence_free(self, sequence: object) -> list[MemoryIntentEvent]:
        request_id = self._sequence_request_id(sequence)
        step = int(getattr(sequence, "step", 0) or 0)
        return self.on_request_finished(step=step, request_id=request_id, block_ids=self._sequence_block_ids(sequence))


def generate_mock_vllm_trace(
    *,
    num_requests: int,
    decode_steps: int,
    recorder: IntentTraceRecorder | None = None,
    seed: int = 42,
) -> IntentTraceRecorder:
    import random

    rng = random.Random(seed)
    adapter = VLLMIntentAdapter(recorder=recorder, default_block_size_bytes=256 * 1024)
    request_ids = [f"req-{index:03d}" for index in range(num_requests)]
    block_counts: dict[str, int] = {}
    current_step = 0

    for index, request_id in enumerate(request_ids):
        high_priority = index < max(1, num_requests // 4)
        speculative = index % 3 == 0
        rag = index % 4 == 1
        request_priority = 90 if high_priority else 20 if rag else 55
        deadline_us = 900 if high_priority else 8_000 if rag else 2_500
        adapter.on_request_scheduled(
            current_step,
            request_id,
            request_priority=request_priority,
            deadline_us=deadline_us,
        )
        # Use fewer but larger mock blocks so the trace still creates realistic
        # HBM pressure without becoming too slow for demos and tests.
        block_count = 18 if high_priority else 44 if rag else 36
        block_counts[request_id] = block_count
        for block_id in range(block_count):
            adapter.on_block_allocated(
                current_step,
                request_id,
                block_id,
                phase=Phase.PREFILL,
                request_priority=request_priority,
                deadline_us=deadline_us,
                is_draft=speculative and block_id < 2,
            )
            current_step += 1
        adapter.on_prefill_step(current_step, request_id, list(range(min(3, block_count))))
        current_step += 1

    for decode_step in range(decode_steps):
        request_id = request_ids[decode_step % len(request_ids)]
        block_count = block_counts[request_id]
        request_meta = adapter.request_metadata.get(request_id, {})
        active_ids = [max(block_count - 2, 0), block_count - 1]
        adapter.on_decode_step(
            current_step,
            request_id,
            active_ids,
            deadline_us=int(request_meta.get("deadline_us") or 2_500),
            request_priority=int(request_meta.get("request_priority") or 50),
        )
        current_step += 1
        cold_id = decode_step % max(1, block_count - 2)
        adapter.on_block_marked_cold(
            current_step,
            request_id,
            cold_id,
            expected_reuse_window_tokens=256 if request_meta.get("request_priority") == 20 else 64,
        )
        current_step += 1
        if decode_step % 7 == 0:
            speculative_request = request_ids[(decode_step + 1) % len(request_ids)]
            if block_counts[speculative_request] > 1:
                adapter.on_block_committed(current_step, speculative_request, 1)
                current_step += 1
        if decode_step % 11 == 0:
            extra_req = request_ids[rng.randrange(len(request_ids))]
            extra_block = rng.randrange(block_counts[extra_req])
            adapter.on_block_accessed(current_step, extra_req, extra_block, phase=Phase.PREFILL, decode_critical=False)
            current_step += 1

    for request_id in request_ids:
        adapter.on_request_finished(current_step, request_id, list(range(block_counts[request_id])))
        current_step += 2

    return adapter.recorder
