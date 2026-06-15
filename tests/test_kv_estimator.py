from kv_memory_intent.kv_estimator import (
    MODEL_PRESETS,
    ModelKVConfig,
    estimate_kv_bytes,
    estimate_request_kv_bytes,
    kv_bytes_per_token,
)


def test_kv_bytes_per_token_formula():
    config = ModelKVConfig(
        model_name="toy",
        num_layers=2,
        hidden_size=16,
        num_attention_heads=4,
        num_kv_heads=2,
        head_dim=4,
        dtype_bytes=2,
    )
    assert kv_bytes_per_token(config) == 2 * 2 * 4 * 2 * 2


def test_manual_config_works():
    config = ModelKVConfig(
        model_name="toy",
        num_layers=8,
        hidden_size=1024,
        num_attention_heads=8,
        num_kv_heads=None,
        head_dim=None,
    )
    assert estimate_kv_bytes(config, tokens=10, batch_size=2) > 0


def test_preset_config_works():
    config = MODEL_PRESETS["llama-3-8b"]
    assert estimate_request_kv_bytes(config, 1024, 128) > 0


def test_invalid_config_raises():
    try:
        ModelKVConfig(
            model_name="bad",
            num_layers=0,
            hidden_size=1024,
            num_attention_heads=8,
            num_kv_heads=None,
            head_dim=None,
        )
    except ValueError as exc:
        assert "num_layers" in str(exc)
    else:
        raise AssertionError("expected ValueError")
