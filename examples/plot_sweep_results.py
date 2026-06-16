"""Optional plotting helper for sweep CSV output."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot KV Deadline Scheduler sweep results.")
    parser.add_argument("csv_path")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        raise SystemExit(f"CSV file not found: {csv_path}")
    if not csv_path.is_file():
        raise SystemExit(f"CSV path is not a file: {csv_path}")
    if csv_path.stat().st_size == 0:
        raise SystemExit(f"CSV file is empty: {csv_path}")

    try:
        import matplotlib.pyplot as plt  # type: ignore
    except ImportError:
        print("matplotlib is optional. Install it with: pip install matplotlib")
        raise SystemExit(1)

    rows = load_rows(csv_path)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    policies = sorted({row["policy"] for row in rows})

    def plot(metric: str, filename: str, ylabel: str) -> None:
        plt.figure()
        for policy in policies:
            series = [row for row in rows if row["policy"] == policy]
            x_values = [int(row["hbm_mb"]) for row in series]
            y_values = [float(row[metric]) for row in series]
            plt.plot(x_values, y_values, marker="o", label=policy)
        plt.xlabel("HBM capacity (MiB)")
        plt.ylabel(ylabel)
        plt.legend()
        plt.tight_layout()
        plt.savefig(out_dir / filename)
        plt.close()

    plot("p99_latency_us", "p99_latency_vs_hbm.png", "P99 latency (us)")
    plot("decode_critical_misses", "decode_critical_misses_vs_hbm.png", "Decode-critical misses")
    plot(
        "decode_critical_evictions",
        "decode_critical_evictions_vs_hbm.png",
        "Decode-critical evictions",
    )
    print(f"Wrote 3 plots to {out_dir}")


if __name__ == "__main__":
    main()
