"""
Build dataset_v12opencode_unconstrained.csv = dataset v12 comprehensive + perbaikan anti-leakage.

Perbedaan vs build_dataset_v12_comprehensive.py:
- session_range_exp dihitung POINT-IN-TIME: range parsial sesi BERJALAN dari bar M15
  [session_start, entry_time] dibagi range FINAL sesi sebelumnya.
  (Versi v12 lama memakai RangePoints final sesi berjalan dari CSV = look-ahead intra-sesi.)

Output: experiments/v12opencode/dataset_v12opencode_unconstrained.csv
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
BACKTEST_DIR = REPO_ROOT / "Backtest_result"
EXP_DIR = (
    REPO_ROOT
    / "ValueCell_MT5"
    / "python"
    / "valuecell"
    / "models"
    / "saved"
    / "experiments"
    / "v12opencode"
)
SRC_DATASET = EXP_DIR / "sandbox_v12" / "python" / "valuecell" / "models" / "saved" / "filter_latest" / "dataset_v12_unconstrained.csv"
OUT_DATASET = EXP_DIR / "dataset_v12opencode_unconstrained.csv"


def sha16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    df = pd.read_csv(SRC_DATASET)
    df["entry_time_dt"] = pd.to_datetime(df["entry_time"], utc=True)
    df = df.sort_values("entry_time_dt").reset_index(drop=True)

    m15_by_year: dict[str, pd.DataFrame] = {}
    sess_by_year: dict[str, pd.DataFrame] = {}
    for res_file in sorted(BACKTEST_DIR.glob("Backtest_Results_XAUUSD_*.csv")):
        suffix = res_file.stem.replace("Backtest_Results_XAUUSD_", "")
        m15_path = BACKTEST_DIR / f"MarketData_XAUUSD_M15_{suffix}.csv"
        sess_path = BACKTEST_DIR / f"SessionZone_XAUUSD_{suffix}.csv"
        if m15_path.exists():
            m = pd.read_csv(m15_path)
            m.columns = [c.strip().lower() for c in m.columns]
            m["time_dt"] = pd.to_datetime(m["time"], utc=True)
            m15_by_year[suffix] = m.sort_values("time_dt").reset_index(drop=True)
        if sess_path.exists():
            s = pd.read_csv(sess_path)
            s.columns = [c.strip() for c in s.columns]
            s["start_dt"] = pd.to_datetime(s["StartTime"], utc=True)
            s["end_dt"] = pd.to_datetime(s["EndTime"], utc=True)
            sess_by_year[suffix] = s.sort_values("start_dt").reset_index(drop=True)

    n = len(df)
    new_sre = np.zeros(n, dtype=np.float32)
    n_hit_running = 0
    n_prev_missing = 0

    for i, row in df.iterrows():
        t = row["entry_time_dt"]
        yr_key = None
        for sfx in sess_by_year.keys():
            if str(t.year) in sfx:
                yr_key = sfx
                break
        se_df = sess_by_year.get(yr_key)
        if se_df is None:
            continue
        active = se_df[(se_df["start_dt"] <= t) & (t <= se_df["end_dt"])]
        if len(active) == 0:
            continue
        s_row = active.iloc[0]
        prev = se_df[se_df["end_dt"] <= s_row["start_dt"]]
        if len(prev) == 0:
            n_prev_missing += 1
            continue
        prev_rng = max(1.0, float(prev.iloc[-1].get("RangePoints", 100.0)))

        # Range parsial sesi berjalan dari bar M15 yang sudah closed pada t
        m15_df = m15_by_year.get(yr_key)
        if m15_df is None:
            continue
        seg = m15_df[(m15_df["time_dt"] >= s_row["start_dt"]) & (m15_df["time_dt"] <= t)]
        if len(seg) == 0:
            # Belum ada bar M15 closed di sesi berjalan: ekspansi = 0 (belum ada info)
            new_sre[i] = 0.0
            n_hit_running += 1
            continue
        partial_rng = float(seg["high"].max() - seg["low"].min())
        new_sre[i] = partial_rng / prev_rng
        n_hit_running += 1

    changed = int((df["session_range_exp"].astype(float).round(4) != new_sre.round(4)).sum())
    df["session_range_exp"] = new_sre
    df = df.drop(columns=["entry_time_dt"], errors="ignore")
    OUT_DATASET.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DATASET, index=False)

    meta = {
        "source_dataset": str(SRC_DATASET.name),
        "output": OUT_DATASET.name,
        "rows": int(n),
        "cols": int(len(df.columns)),
        "fix": "session_range_exp point-in-time partial range dari M15 [session_start, entry_time]",
        "rows_running_session_evaluated": int(n_hit_running),
        "rows_prev_session_missing": int(n_prev_missing),
        "rows_value_changed_vs_v12": changed,
        "sha256_source_v12": sha16(SRC_DATASET),
        "sha256_output": sha16(OUT_DATASET),
    }
    (EXP_DIR / "dataset_v12opencode_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
