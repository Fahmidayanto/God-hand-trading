"""Rebuild the v8 source dataset from raw backtest CSV files only."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "ValueCell_MT5" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from train_ml_prediction_v5_unconstrained import build_dataset_v5_unconstrained  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backtest-dir", type=Path, default=REPO_ROOT / "Backtest_result")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=False)
    dataset, build_info = build_dataset_v5_unconstrained(args.backtest_dir)
    if dataset.empty:
        raise RuntimeError("Raw CSV reconstruction produced no samples")

    dataset_path = args.output_dir / "dataset_v5_unconstrained_rebuilt.csv"
    dataset.to_csv(dataset_path, index=False)
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "backtest_dir": str(args.backtest_dir),
        "dataset_path": str(dataset_path),
        "dataset_sha256": sha256(dataset_path),
        "rows": int(len(dataset)),
        "columns": int(len(dataset.columns)),
        "years": sorted(int(year) for year in dataset["year"].unique()),
        "build_info": build_info,
    }
    (args.output_dir / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())