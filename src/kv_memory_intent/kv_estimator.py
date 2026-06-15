"""KV footprint estimation helpers for external profiling."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ModelKVConfig:
    model_name: str
    num_layers: int
    hidden_size: int
    num_attention_heads: int
    num_kv_heads: int | None
    head_dim: int | None
    dtype_bytes: int = 2

    def __post_init__(self) -> None:
        if not self.model_name:
            raise ValueError("model_name must not be empty")
        if self.num_layers <= 0:
            raise ValueError("num_layers must be > 0")
        if self.hidden_size <= 0:
            raise ValueError("hidden_size must be > 0")
        if self.num_attention_heads <= 0:
            raise ValueError("num_attention_heads must be > 0")
        if self.num_kv_heads is not None and self.num_kv_heads <= 0:
            raise ValueError("num_kv_heads must be > 0 when provided")
        if self.dtype_bytes <= 0:
            raise ValueError("dtype_bytes must be > 0")
        inferred_head_dim = self.hidden_size // self.num_attention_heads
        if self.head_dim is None:
            self.head_dim = inferred_head_dim
        if self.head_dim <= 0:
            raise ValueError("head_dim must be > 0")
        if self.num_kv_heads is None:
            self.num_kv_heads = self.num_attention_heads


MODEL_PRESETS: dict[str, ModelKVConfig] = {
    # These presets are illustrative approximations for demos and trace import.
    "llama-3-8b": ModelKVConfig(
        model_name="llama-3-8b",
        num_layers=32,
        hidden_size=4096,
        num_attention_heads=32,
        num_kv_heads=8,
        head_dim=128,
        dtype_bytes=2,
    ),
    "llama-3-70b": ModelKVConfig(
        model_name="llama-3-70b",
        num_layers=80,
        hidden_size=8192,
        num_attention_heads=64,
        num_kv_heads=8,
        head_dim=128,
        dtype_bytes=2,
    ),
    "mistral-7b": ModelKVConfig(
        model_name="mistral-7b",
        num_layers=32,
        hidden_size=4096,
        num_attention_heads=32,
        num_kv_heads=8,
        head_dim=128,
        dtype_bytes=2,
    ),
}


def kv_bytes_per_token(config: ModelKVConfig) -> int:
    return (
        config.num_layers
        * int(config.num_kv_heads)
        * int(config.head_dim)
        * 2  # K and V
        * config.dtype_bytes
    )


def estimate_kv_bytes(config: ModelKVConfig, tokens: int, batch_size: int = 1) -> int:
    if tokens < 0:
        raise ValueError("tokens must be >= 0")
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")
    return kv_bytes_per_token(config) * tokens * batch_size


def estimate_request_kv_bytes(
    config: ModelKVConfig,
    prompt_tokens: int,
    generated_tokens: int,
) -> int:
    if prompt_tokens < 0:
        raise ValueError("prompt_tokens must be >= 0")
    if generated_tokens < 0:
        raise ValueError("generated_tokens must be >= 0")
    return estimate_kv_bytes(config, prompt_tokens + generated_tokens, batch_size=1)
