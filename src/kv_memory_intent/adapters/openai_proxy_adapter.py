"""Adapter for OpenAI-compatible proxy request logs."""

from __future__ import annotations

import json
from collections.abc import Iterable
from math import ceil
from pathlib import Path

from ..events import MemoryIntentEvent
from ..kv_estimator import MODEL_PRESETS, ModelKVConfig, kv_bytes_per_token
from ..schema import EventType, MemoryIntent, ObjectType, Phase, Priority, Tier


def _resolve_model_config(model_name: str | None) -> ModelKVConfig:
    if model_name and model_name in MODEL_PRESETS:
        preset = MODEL_PRESETS[model_name]
    else:
        preset = MODEL_PRESETS["llama-3-8b"]
    return ModelKVConfig(
        model_name=preset.model_name,
        num_layers=preset.num_layers,
        hidden_size=preset.hidden_size,
        num_attention_heads=preset.num_attention_heads,
        num_kv_heads=preset.num_kv_heads,
        head_dim=preset.head_dim,
        dtype_bytes=preset.dtype_bytes,
    )


def openai_proxy_logs_to_intent_events(
    entries: list[dict[str, object]],
    logical_block_tokens: int = 256,
    model_name_override: str | None = None,
) -> list[MemoryIntentEvent]:
    if logical_block_tokens <= 0:
        raise ValueError("logical_block_tokens must be > 0")

    events: list[MemoryIntentEvent] = []
    sorted_entries = sorted(entries, key=lambda entry: (int(entry.get("created", 0)), str(entry.get("id", ""))))
    for step, entry in enumerate(sorted_entries):
        usage = dict(entry.get("usage", {}))
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens))
        model_name = model_name_override or str(entry.get("model") or "")
        config = _resolve_model_config(model_name)
        bytes_per_block = kv_bytes_per_token(config) * logical_block_tokens
        num_blocks = max(1, ceil(prompt_tokens / logical_block_tokens))
        request_id = str(entry.get("id") or f"request-{step}")

        for block_id in range(num_blocks):
            intent = MemoryIntent(
                object_id=f"{request_id}:proxy:{block_id}",
                request_id=request_id,
                block_id=block_id,
                object_type=ObjectType.KV_CACHE,
                phase=Phase.PREFILL,
                priority=Priority.WARM,
                allowed_tiers={Tier.HBM, Tier.DRAM},
                current_tier=Tier.HBM,
                size_bytes=bytes_per_block,
                request_priority=50,
                recency_score=0.2,
                deadline_us=None,
                slack_us=None,
                arrival_step=step,
                target_decode_step=step + 1,
                expected_reuse_window_tokens=max(1, total_tokens // max(num_blocks, 1)),
                recompute_cost_us=250,
                spill_cost_us=200,
                compression_ok=True,
                recompute_ok=True,
                prefetch_ok=False,
                pin_requested=False,
                is_draft=False,
                is_committed=True,
                created_step=step,
                last_access_step=step,
            )
            events.append(
                MemoryIntentEvent(
                    step=step,
                    event_type=EventType.ALLOCATED,
                    intent=intent,
                    reason="imported from OpenAI-compatible proxy log",
                )
            )

        mark_step = step + 1
        for block_id in range(max(0, num_blocks - 2), num_blocks):
            hot_intent = MemoryIntent(
                object_id=f"{request_id}:proxy:{block_id}",
                request_id=request_id,
                block_id=block_id,
                object_type=ObjectType.KV_CACHE,
                phase=Phase.DECODE,
                priority=Priority.DECODE_CRITICAL,
                allowed_tiers={Tier.HBM, Tier.DRAM},
                current_tier=Tier.HBM,
                size_bytes=bytes_per_block,
                request_priority=50,
                recency_score=1.0,
                deadline_us=2000,
                slack_us=800,
                arrival_step=step,
                target_decode_step=mark_step,
                expected_reuse_window_tokens=1,
                recompute_cost_us=6000,
                spill_cost_us=250,
                compression_ok=False,
                recompute_ok=False,
                prefetch_ok=True,
                pin_requested=True,
                is_draft=False,
                is_committed=True,
                created_step=mark_step,
                last_access_step=mark_step,
            )
            events.append(
                MemoryIntentEvent(
                    step=mark_step,
                    event_type=EventType.MARKED_DECODE_CRITICAL,
                    intent=hot_intent,
                    reason="decode-critical block inferred from proxy completion log",
                )
            )

        free_step = step + ceil(max(completion_tokens, 1) / 64)
        for block_id in range(num_blocks):
            freed_intent = MemoryIntent(
                object_id=f"{request_id}:proxy:{block_id}",
                request_id=request_id,
                block_id=block_id,
                object_type=ObjectType.KV_CACHE,
                phase=Phase.DONE,
                priority=Priority.COLD,
                allowed_tiers={Tier.HBM, Tier.DRAM},
                current_tier=Tier.DRAM,
                size_bytes=bytes_per_block,
                request_priority=50,
                recency_score=0.0,
                deadline_us=None,
                slack_us=None,
                arrival_step=step,
                target_decode_step=None,
                expected_reuse_window_tokens=None,
                recompute_cost_us=0,
                spill_cost_us=0,
                compression_ok=True,
                recompute_ok=False,
                prefetch_ok=False,
                pin_requested=False,
                is_draft=False,
                is_committed=True,
                created_step=free_step,
                last_access_step=free_step,
            )
            events.append(
                MemoryIntentEvent(
                    step=free_step,
                    event_type=EventType.FREED,
                    intent=freed_intent,
                    reason="request completion inferred from proxy log",
                )
            )
    return events


def load_openai_proxy_logs(path: str | Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def write_openai_proxy_logs(entries: Iterable[dict[str, object]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(json.dumps(entry, sort_keys=True) for entry in entries) + "\n", encoding="utf-8")
