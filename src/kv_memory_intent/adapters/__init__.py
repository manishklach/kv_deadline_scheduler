"""Passive adapter skeletons for future runtime integrations."""

from .vllm_adapter import VLLMIntentAdapter, generate_mock_vllm_trace

__all__ = ["VLLMIntentAdapter", "generate_mock_vllm_trace"]
