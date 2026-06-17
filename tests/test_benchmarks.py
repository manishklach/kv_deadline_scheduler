import json
import subprocess
import sys
from pathlib import Path


def test_reproducible_benchmark_suite_writes_expected_outputs(tmp_path: Path):
    out_dir = tmp_path / "suite"
    config = {
        "seed": 7,
        "out_dir": str(out_dir),
        "policies": ["lru", "deadline"],
        "workloads": [
            {
                "name": "tiny-balanced",
                "profile": "balanced",
                "num_requests": 2,
                "blocks_per_request": 4,
                "block_size_bytes": 262144,
                "decode_steps": 6,
                "hbm_capacity_bytes": 1048576,
                "dram_capacity_bytes": 8388608,
            }
        ],
        "speculative": {
            "enabled": True,
            "hbm_capacity_bytes": 1048576,
            "dram_capacity_bytes": 8388608,
            "acceptance_rate": 0.7,
            "tree_width": 2,
            "tree_depth": 2,
        },
        "mock_vllm": {
            "enabled": True,
            "num_requests": 2,
            "decode_steps": 4,
            "hbm_capacity_bytes": 1048576,
            "dram_capacity_bytes": 8388608,
        },
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    repo_root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [
            sys.executable,
            "benchmarks/run_reproducible_suite.py",
            "--config",
            str(config_path),
        ],
        cwd=repo_root,
        check=True,
    )

    expected_files = {
        "summary.json",
        "policy_metrics.csv",
        "latency_distributions.json",
        "speculative_metrics.json",
    }
    assert expected_files.issubset({path.name for path in out_dir.iterdir()})

    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["seed"] == 7
    assert len(summary["rows"]) == 2
    assert summary["mock_vllm"]
