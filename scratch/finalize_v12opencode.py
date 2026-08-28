"""Finalisasi Fase H: spesifikasi lengkap kandidat terbaik + keputusan, tersimpan di experiments dir."""

import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

EXP = Path(__file__).resolve().parents[1] / "ValueCell_MT5" / "python" / "valuecell" / "models" / "saved" / "experiments" / "v12opencode"


def sha16(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def sha16s(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


final_spec = {
    "model_artifact_version": "v12opencode-candidate-NOT-PROMOTED",
    "decision": "REJECT (strict gate)",
    "decision_reason": [
        "per_year_dynamic_net_pnl gagal: 2023 (-4380 vs v8) dan 2024 (-304 vs v8)",
        "per_year_win_rate gagal: 2023 (gap 3.6-3.9pp dalam noise binomial TAPI Net PnL tahun turun -> pengecualian user tidak terpenuhi)",
        "Seluruh gate TOTAL lulus termasuk setelah stress spread/komisi; kegagalan hanya di level tahun 2023 dan 2024",
    ],
    "pareto_champion": {
        "tag": "m03_session_joint",
        "family": "F_SESSION (session_range_exp point-in-time, is_prev_high_break, is_prev_low_break, session_progress_pct)",
        "model": "joint multi-output MFE+MAE (pola v10: Multi_XGB_d3_n120_lr002 / Multi_RF_d5_n200_leaf15 dipilih CV per fold)",
        "feature_base": "restrict-base era-v5 + F_SESSION",
        "dataset": "dataset_v12opencode_unconstrained.csv",
        "dataset_sha256_16": sha16(EXP / "dataset_v12opencode_unconstrained.csv"),
        "anti_leakage_fixes": [
            "H1 strictly closed (t-1h), H4 strictly closed (t-4h) dari build_dataset_v12_comprehensive",
            "session_range_exp dihitung ulang POINT-IN-TIME dari bar M15 parsial sesi berjalan (1939/1942 nilai berubah vs v12)",
            "guard kolom outcome (Profit/Net_Profit/CloseReason/exit dll) hard-fail di harness",
        ],
        "eval_variants": {
            "threshold_105": {"trades": 371, "win_rate": 59.30, "flat_net_pnl": 20860.35, "dynamic_net_pnl": 105975.58, "pf_dynamic": 2.856, "max_dd_dynamic": -2856.98},
            "threshold_100_live_gate": {"trades": 405, "win_rate": 59.26, "flat_net_pnl": 21991.78, "dynamic_net_pnl": 105975.58, "pf_dynamic": 2.856, "max_dd_dynamic": -2856.98, "dyn_ci95": [73503.3, 140160.1]},
        },
        "stress_test_threshold_100": {
            "spr_plus_30pts": {"dynamic_net_pnl": 105599.38, "verdict_vs_v8_total": "PASS"},
            "commission_07usd": {"dynamic_net_pnl": 105097.78, "verdict_vs_v8_total": "PASS"},
            "spr_plus_50pts_commission_07": {"dynamic_net_pnl": 104470.78, "verdict_vs_v8_total": "PASS", "pf": 2.813, "dd": -2890.58},
        },
    },
    "seeds_used": [42, 7, 13, 123, 777],
    "seed_note": "Seleksi model deterministik seed 42 internal legacy selector; multi-seed dilakukan via refit winner dengan random_state berbeda lalu ensemble rata-rata prediksi",
    "folds": "expanding walk-forward 2020-2026, train = year < test_year, tanpa embargo (fidelity legacy); 2019 tanpa fold OOS dan dilaporkan terpisah",
    "baseline_canonical": {
        "name": "v8_walk_forward_normalized_REPLAY_FRESH",
        "spec_file": "baseline_v8_canonical.json",
        "metrics": {"trades": 435, "win_rate": 55.17, "flat_net_pnl": 18884.57, "dynamic_net_pnl": 86960.60, "pf_dynamic": 2.082, "max_dd_dynamic": -8560.25},
        "obsidian_reconciliation": {
            "note_A_405tr_63.0pct_144075": "IN-SAMPLE: model_final men-score data yang sama (scratch/calculate_all_models_reproduced.py) - TERBUKTI reproduksi persis",
            "note_B_400tr_63.5pct_148119": "metode sama pada snapshot artifact LAMA sebelum resync data Juli-Agustus 2026",
            "implication": "Angka Obsidian BUKAN out-of-sample; OOS sebenarnya WR ~55% dan Dynamic ~87K",
        },
    },
    "reproduction_commands": [
        "# 1. Replay baseline v8 canonical (OOS)",
        "ValueCell_MT5/venv/Scripts/python.exe ValueCell_MT5/scripts/train_ml_prediction_v8_walk_forward_normalized.py --output-dir ValueCell_MT5/python/valuecell/models/saved/experiments/v12opencode/replay_v8",
        "ValueCell_MT5/venv/Scripts/python.exe ValueCell_MT5/scripts/evaluate_walk_forward_trades.py --scored <exp>/replay_v8/scored_v8_walk_forward.csv --name v8_OOS_canonical --save-eval <exp>/baseline_v8_canonical_eval.json",
        "# 2. Build dataset kandidat",
        "sandbox-run build_dataset_v12_comprehensive.main() lalu ValueCell_MT5/scripts/build_dataset_v12opencode.py",
        "# 3. Kandidat champion",
        "ValueCell_MT5/venv/Scripts/python.exe ValueCell_MT5/scripts/train_ml_prediction_v12opencode_walk_forward.py --tag m03_session_joint --families F_SESSION --model joint --seeds 42 --restrict-base",
        "# 4. Evaluasi + gate",
        "python scratch/diag_d04_vs_v8.py m03_session_joint 1.0",
    ],
    "code_sha_reference": {"harness": sha16s("train_ml_prediction_v12opencode_walk_forward"), "evaluator": sha16s("evaluate_walk_forward_trades")},
}

(EXP / "final_decision_v12opencode.json").write_text(json.dumps(final_spec, indent=2), encoding="utf-8")
print("Saved:", EXP / "final_decision_v12opencode.json")
