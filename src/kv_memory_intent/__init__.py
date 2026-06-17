"""KV Deadline Scheduler research prototype."""

__version__ = "0.6.0"

from .adapters import (
    VLLMIntentAdapter,
    generate_mock_vllm_trace,
    load_openai_proxy_logs,
    load_prometheus_samples,
    openai_proxy_logs_to_intent_events,
    prometheus_samples_to_intent_events,
)
from .events import MemoryIntentEvent
from .kv_estimator import MODEL_PRESETS, ModelKVConfig, estimate_kv_bytes, estimate_request_kv_bytes, kv_bytes_per_token
from .metrics import compare_results, format_bytes, percentile, write_sweep_csv
from .policies import (
    DeadlineAwarePolicy,
    HotColdPolicy,
    IntentAwarePolicy,
    LRUPolicy,
    PlacementPolicy,
    PredictiveHotnessPolicy,
)
from .schema import EventType, MemoryIntent, ObjectType, Phase, Priority, Tier
from .request_trace import RequestTraceRecord, load_request_trace, write_request_trace
from .simulator import KVMemorySimulator, SimulationResult, WorkloadProfile, generate_synthetic_kv_workload
from .speculative import DraftNode, DraftTree, SpeculativeIntentPolicy, generate_speculative_workload
from .trace import IntentTraceRecorder
from .trace_importer import request_trace_to_intent_events

__all__ = [
    "DeadlineAwarePolicy",
    "EventType",
    "DraftNode",
    "DraftTree",
    "HotColdPolicy",
    "IntentAwarePolicy",
    "IntentTraceRecorder",
    "KVMemorySimulator",
    "LRUPolicy",
    "MODEL_PRESETS",
    "MemoryIntent",
    "MemoryIntentEvent",
    "ModelKVConfig",
    "ObjectType",
    "Phase",
    "PlacementPolicy",
    "Priority",
    "PredictiveHotnessPolicy",
    "RequestTraceRecord",
    "SimulationResult",
    "SpeculativeIntentPolicy",
    "Tier",
    "VLLMIntentAdapter",
    "WorkloadProfile",
    "compare_results",
    "estimate_kv_bytes",
    "estimate_request_kv_bytes",
    "format_bytes",
    "generate_synthetic_kv_workload",
    "generate_mock_vllm_trace",
    "generate_speculative_workload",
    "kv_bytes_per_token",
    "load_openai_proxy_logs",
    "load_prometheus_samples",
    "load_request_trace",
    "openai_proxy_logs_to_intent_events",
    "percentile",
    "prometheus_samples_to_intent_events",
    "request_trace_to_intent_events",
    "write_request_trace",
    "write_sweep_csv",
    "__version__",
]
