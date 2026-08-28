"""
v12opencode walk-forward training harness.

Mirror persis pola train_ml_prediction_v8_walk_forward_normalized.py:
- expanding walk-forward per tahun kalender, train = year < test_year
- target dinormalisasi price-ratio (BASE_REFERENCE_PRICE=4500)
- seleksi model via CV dalam train window saja

Ekstensi terkontrol:
- --families : ablation feature family (F_MTF/F_STRUCT/F_CANDLE/F_SESSION/F_TRADEPLAN/V11)
- --seeds    : multi-seed (ensemble rata-rata prediksi antar seed)
- --embargo-days : buang baris train dalam N hari sebelum awal tahun test
- --model    : dual (legacy grid) | ridge | rf | et | xgb | joint | dualhead
- Guard anti-leakage: kolom outcome dilarang masuk matriks fitur (hard fail)
- Registry eksperimen: experiment_registry.jsonl

Contoh:
  python train_ml_prediction_v12opencode_walk_forward.py --tag base_repro --families NONE
  python train_ml_prediction_v12opencode_walk_forward.py --tag mtf --families F_MTF --model dual
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from loguru import logger

from train_ml_prediction_v5_unconstrained import build_feature_matrix_v5, select_and_fit_regressor
from evaluate_walk_forward_trades import evaluate_scored, gate_check, get_dynamic_lot

TEST_YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
BASE_REFERENCE_PRICE = 4500.0

EXP_DIR = (
    SCRIPT_DIR.parent
    / "python"
    / "valuecell"
    / "models"
    / "saved"
    / "experiments"
    / "v12opencode"
)
DATASET_PATH = EXP_DIR / "dataset_v12opencode_unconstrained.csv"
BASELINE_PATH = EXP_DIR / "baseline_v8_canonical.json"
REGISTRY_PATH = EXP_DIR / "experiment_registry.jsonl"
V5_DATASET_PATH = (
    SCRIPT_DIR.parent
    / "python"
    / "valuecell"
    / "models"
    / "saved"
    / "filter_latest"
    / "dataset_v5_unconstrained.csv"
)

FAMILIES: dict[str, list[str]] = {
    "F_MTF": [
        "m15_ema200_slope", "h1_ema200_slope", "h4_ema200_slope",
        "h1_trend_align", "h4_trend_align", "mtf_alignment_score",
        "price_to_h1_ema_atr", "price_to_h4_ema_atr",
    ],
    "F_STRUCT": [
        "structure_age_hours", "struct_count_5b", "struct_count_10b",
        "struct_count_20b", "trend_strength_ratio", "is_confluence_zone",
    ],
    "F_CANDLE": [
        "candle_body_ratio", "upper_wick_ratio", "lower_wick_ratio",
        "vol_spike_ratio", "vol_regime_ratio", "range_expansion_5b",
    ],
    "F_SESSION": [
        "session_range_exp", "is_prev_high_break", "is_prev_low_break",
        "session_progress_pct",
    ],
    "F_TRADEPLAN": [
        "planned_rr", "init_risk_points", "init_reward_points",
        "spread_to_atr_ratio", "risk_to_atr_ratio",
    ],
    "V11": [
        "planned_rr", "init_risk_points", "init_reward_points",
        "reject_group_NONE", "reject_group_TREND_FILTER_EMA",
        "reject_group_CYCLE_LIMIT", "reject_group_UNCONSTRAINED_SIM",
    ],
}

FORBIDDEN_FEATURES = {
    "profit", "net_profit", "actual_net_profit", "exitprice", "exit_time",
    "closereason", "close_reason", "mfe_target", "mae_target",
    "mfe_points", "mae_points", "final_rr", "ea_status", "ea_reject_reason",
    "mfe_target_norm", "mae_target_norm", "holding_duration",
}

MODEL_GRID_OVERRIDES: dict[str, list[dict]] = {
    # dipakai bila --model ridge/rf/et/xgb : paksa satu keluarga model
}


def _forced_grid(model_mode: str) -> list[tuple[str, object]]:
    from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
    from sklearn.linear_model import Ridge
    from xgboost import XGBRegressor

    if model_mode == "ridge":
        return [("Ridge_alpha10", Ridge(alpha=10.0))]
    if model_mode == "rf":
        return [("RF_d5_n200_leaf15", RandomForestRegressor(n_estimators=200, max_depth=5, min_samples_leaf=15, random_state=42, n_jobs=-1))]
    if model_mode == "et":
        return [("ET_d5_n200_leaf15", ExtraTreesRegressor(n_estimators=200, max_depth=5, min_samples_leaf=15, random_state=42, n_jobs=-1))]
    if model_mode == "xgb":
        return [("XGB_d3_n120_lr002", XGBRegressor(n_estimators=120, max_depth=3, learning_rate=0.02, random_state=42))]
    raise ValueError(model_mode)


def fit_forced_regressor(model_df, y_train, train_mask, seed: int, model_mode: str):
    """Seleksi fitur top-20 via f_regression pada train window, lalu fit model paksaan."""
    from sklearn.feature_selection import SelectKBest, f_regression
    from sklearn.preprocessing import StandardScaler
    from sklearn.base import clone

    X_all = model_df.select_dtypes(include=[np.number])
    X_tr = X_all.loc[train_mask]
    y_tr = y_train.loc[train_mask]
    k = min(20, X_tr.shape[1])
    sel = SelectKBest(f_regression, k=k).fit(X_tr, y_tr)
    feats = list(X_tr.columns[sel.get_support()])
    scaler = StandardScaler().fit(X_tr[feats])
    name, est = _forced_grid(model_mode)[0]
    est2 = clone(est)
    if hasattr(est2, "random_state"):
        est2.set_params(random_state=seed)
    est2.fit(scaler.transform(X_tr[feats]), y_tr)
    return est2, scaler, feats, name


def fit_dual_head(train_df_feat, train_mask, exec_mask, y_label, seed: int):
    """Probabilitas win: LogisticRegression pada fitur terpilih, train hanya EXECUTED."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    X = train_df_feat.loc[train_mask & exec_mask]
    y = y_label.loc[train_mask & exec_mask]
    if len(y) < 50 or y.nunique() < 2:
        return None, None, []
    sel_cols = list(X.columns)
    scaler = StandardScaler().fit(X)
    clf = LogisticRegression(max_iter=1000, random_state=seed)
    clf.fit(scaler.transform(X), y)
    return clf, scaler, sel_cols


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--families", default="NONE", help="NONE atau koma: F_MTF,F_STRUCT,F_CANDLE,F_SESSION,F_TRADEPLAN,V11")
    ap.add_argument("--model", default="dual", choices=["dual", "ridge", "rf", "et", "xgb", "joint", "dualhead"])
    ap.add_argument("--seeds", default="42")
    ap.add_argument("--embargo-days", type=int, default=0)
    ap.add_argument("--dataset-path", type=Path, default=DATASET_PATH)
    ap.add_argument("--restrict-base", action="store_true",
                    help="Batasi universe kolom ke set era-v5 + family terpilih (ablation benar)")
    ap.add_argument("--threshold-mode", default="fixed", choices=["fixed", "nested"],
                    help="nested = pilih RR threshold per fold dari validasi internal (tahun test-1), tanpa sentuh test year")
    ap.add_argument("--skip-eval", action="store_true")
    args = ap.parse_args()

    fam_list = [f.strip() for f in args.families.split(",") if f.strip() and f.strip() != "NONE"]
    for f in fam_list:
        if f not in FAMILIES:
            print(f"Family tidak dikenal: {f}. Pilihan: {list(FAMILIES)}")
            return 1
    seeds = [int(s) for s in args.seeds.split(",")]

    dataset = pd.read_csv(args.dataset_path)
    dataset["entry_time_dt"] = pd.to_datetime(dataset["entry_time"], utc=True)

    if args.restrict_base:
        v5_cols = set(pd.read_csv(V5_DATASET_PATH, nrows=0).columns)
        fam_cols = [c for f in fam_list for c in FAMILIES[f] if c in dataset.columns]
        keep = [c for c in dataset.columns if c in v5_cols or c in fam_cols]
        dropped = sorted(set(dataset.columns) - set(keep))
        dataset = dataset[keep + [c for c in ["entry_time_dt"] if c not in keep]]
        logger.info("RESTRICT-BASE aktif: {} kolom dipertahankan, {} dibuang: {}",
                    len(keep), len(dropped), dropped[:12])

    price_ratio_safe = (dataset["entry_price"] / BASE_REFERENCE_PRICE).clip(lower=1.0 / BASE_REFERENCE_PRICE)
    dataset["mfe_target_norm"] = dataset["mfe_target"] / price_ratio_safe
    dataset["mae_target_norm"] = dataset["mae_target"] / price_ratio_safe

    model_df, _, _ = build_feature_matrix_v5(dataset)
    model_df = model_df.drop(columns=["mfe_target_norm", "mae_target_norm"], errors="ignore")

    extra_cols: list[str] = []
    for f in fam_list:
        for c in FAMILIES[f]:
            if c in dataset.columns and c not in model_df.columns:
                model_df[c] = pd.to_numeric(dataset[c], errors="coerce").fillna(0.0)
                extra_cols.append(c)

    # GUARD anti-leakage
    lower_cols = {c.lower() for c in model_df.columns}
    leaked = sorted(lower_cols & FORBIDDEN_FEATURES)
    if leaked:
        print(f"LEAKAGE GUARD FAIL: kolom terlarang di matriks fitur: {leaked}")
        return 1

    exec_mask = dataset["ea_status"] == "EXECUTED"
    label_win = (dataset["actual_net_profit"] > 0).astype(int)

    out_dir = EXP_DIR / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)

    def _refit_clone(model, feats, scaler, tmask, y_full, sd):
        """Refit ulang winner dengan random_state berbeda (multi-seed bermakna, seleksi tetap deterministik)."""
        from sklearn.base import clone

        m2 = clone(model)
        changed = False
        for p in ("random_state", "estimator__random_state"):
            try:
                m2.set_params(**{p: sd})
                changed = True
            except Exception:
                continue
        if not changed and not hasattr(m2, "random_state"):
            return model
        m2.fit(scaler.transform(model_df.loc[tmask, feats]), y_full.loc[tmask])
        return m2

    all_seed_preds: dict[int, list] = {s: [] for s in seeds}
    winners_log: list[dict] = []
    first_seed = seeds[0]
    nested_threshold_map: dict[int, float] = {}

    for test_year in TEST_YEARS:
        train_mask = dataset["year"] < test_year
        test_mask = dataset["year"] == test_year
        if args.embargo_days > 0:
            test_start = dataset.loc[test_mask, "entry_time_dt"].min()
            cutoff = test_start - pd.Timedelta(days=args.embargo_days)
            train_mask = train_mask & (dataset["entry_time_dt"] <= cutoff)
        n_train, n_test = int(train_mask.sum()), int(test_mask.sum())
        if n_train < 30 or n_test == 0:
            logger.warning("Skipping fold test_year={} (train={}, test={})", test_year, n_train, n_test)
            continue

        y_mfe_tr = dataset.loc[train_mask, "mfe_target_norm"]
        y_mae_tr = dataset.loc[train_mask, "mae_target_norm"]

        # Seleksi model SEKALI per fold (deterministik), lalu refit berseed utk tiap anggota ensemble
        if args.model in ("dual", "dualhead"):
            mfe_model, mfe_scaler, mfe_feats, mfe_w = select_and_fit_regressor(
                model_df, y_mfe_tr, train_mask, f"MFEnorm_f{test_year}"
            )
            mae_model, mae_scaler, mae_feats, mae_w = select_and_fit_regressor(
                model_df, y_mae_tr, train_mask, f"MAEnorm_f{test_year}"
            )
        elif args.model in ("ridge", "rf", "et", "xgb"):
            mfe_model, mfe_scaler, mfe_feats, mfe_w = fit_forced_regressor(
                model_df, y_mfe_tr, train_mask, first_seed, args.model
            )
            mae_model, mae_scaler, mae_feats, mae_w = fit_forced_regressor(
                model_df, y_mae_tr, train_mask, first_seed, args.model
            )
        else:  # joint
            from train_ml_prediction_v10_walk_forward import select_and_fit_joint_regressor

            Y_tr = pd.DataFrame(
                {
                    "MFEnorm": y_mfe_tr.values,
                    "MAEnorm": y_mae_tr.values,
                },
                index=dataset.index[train_mask],
            )
            mfe_model, mfe_scaler, mfe_feats, j_w = select_and_fit_joint_regressor(
                model_df, Y_tr, train_mask, f"Joint_f{test_year}"
            )
            mfe_w = mae_w = j_w
            mae_model, mae_scaler, mae_feats = mfe_model, mfe_scaler, mfe_feats

        Xtest_common = model_df.loc[test_mask]
        ratio_test = price_ratio_safe.loc[test_mask].values

        # Nested threshold: validasi internal = tahun test-1, model temp dilatih < tahun itu
        fold_threshold = 1.05
        threshold_by_year: dict[int, float] | None = None
        if args.threshold_mode == "nested":
            inner_val_year = test_year - 1
            inner_train_mask = dataset["year"] < inner_val_year
            inner_val_mask = dataset["year"] == inner_val_year
            if int(inner_train_mask.sum()) >= 30 and int(inner_val_mask.sum()) >= 15:
                if args.model == "joint":
                    from train_ml_prediction_v10_walk_forward import select_and_fit_joint_regressor as _sel

                    Y_in = pd.DataFrame(
                        {"MFEnorm": dataset.loc[inner_train_mask, "mfe_target_norm"].values,
                         "MAEnorm": dataset.loc[inner_train_mask, "mae_target_norm"].values},
                        index=dataset.index[inner_train_mask],
                    )
                    tm, ts, tf, _ = _sel(model_df, Y_in, inner_train_mask, f"JointThr_f{test_year}")
                    pr = tm.predict(ts.transform(model_df.loc[inner_val_mask, tf]))
                    iv_mfe, iv_mae = np.clip(pr[:, 0] * price_ratio_safe.loc[inner_val_mask].values, 0, None), \
                                     np.clip(pr[:, 1] * price_ratio_safe.loc[inner_val_mask].values, 1, None)
                else:
                    ym = dataset.loc[inner_train_mask, "mfe_target_norm"]
                    tmm, tms, tmf, _ = select_and_fit_regressor(model_df, ym, inner_train_mask, f"MFEThr_f{test_year}")
                    ymae = dataset.loc[inner_train_mask, "mae_target_norm"]
                    tmm2, tms2, tmf2, _ = select_and_fit_regressor(model_df, ymae, inner_train_mask, f"MAEThr_f{test_year}")
                    iv_mfe = tmm.predict(tms.transform(model_df.loc[inner_val_mask, tmf])) * price_ratio_safe.loc[inner_val_mask].values
                    iv_mae = tmm2.predict(tms2.transform(model_df.loc[inner_val_mask, tmf2])) * price_ratio_safe.loc[inner_val_mask].values

                rr_iv = iv_mfe / np.maximum(1.0, iv_mae)
                net_iv = dataset.loc[inner_val_mask, "actual_net_profit"].values
                best_thr, best_dyn = 1.05, -float("inf")
                for thr_c in (1.0, 1.05, 1.1, 1.15):
                    sel = rr_iv >= thr_c
                    n_sel = int(sel.sum())
                    if n_sel < 25:
                        continue
                    lots = np.array([get_dynamic_lot(r) for r in rr_iv[sel]])
                    dyn_iv = float((net_iv[sel] * (lots / 0.01)).sum())
                    if dyn_iv > best_dyn:
                        best_dyn, best_thr = dyn_iv, thr_c
                fold_threshold = best_thr
            threshold_by_year = {int(test_year): fold_threshold}
            nested_threshold_map.update(threshold_by_year)
            logger.info("Fold {} nested threshold = {} (inner-val {})", test_year, fold_threshold, inner_val_year)

        meta_cols = ["year", "entry_time", "signal", "entry_price", "ea_status", "actual_net_profit"]
        for opt_c in ("session_name", "entry_structure", "is_news_blackout", "atr_14_pct"):
            if opt_c in dataset.columns:
                meta_cols.append(opt_c)

        for sd in seeds:
            if sd == first_seed:
                mfe_use, mae_use = mfe_model, mae_model
            elif args.model == "joint":
                # MultiOutputRegressor butuh target 2-D [MFE, MAE]
                mfe_use = _refit_clone(
                    mfe_model, mfe_feats, mfe_scaler, train_mask,
                    dataset[["mfe_target_norm", "mae_target_norm"]], sd,
                )
                mae_use = mfe_use
            else:
                mfe_use = _refit_clone(mfe_model, mfe_feats, mfe_scaler, train_mask, dataset["mfe_target_norm"], sd)
                mae_use = _refit_clone(mae_model, mae_feats, mae_scaler, train_mask, dataset["mae_target_norm"], sd)

            Xs_mfe = mfe_scaler.transform(Xtest_common[mfe_feats])
            if args.model == "joint":
                preds_joint = mfe_use.predict(Xs_mfe)
                pmfe_n, pmae_n = preds_joint[:, 0], preds_joint[:, 1]
            else:
                pmfe_n = mfe_use.predict(Xs_mfe)
                pmae_n = mae_use.predict(mae_scaler.transform(Xtest_common[mae_feats]))
            pmfe = pmfe_n * ratio_test
            pmae = pmae_n * ratio_test
            if args.model in ("joint", "dualhead"):
                pmfe = np.clip(pmfe, 0.0, None)
                pmae = np.clip(pmae, 1.0, None)

            frame = dataset.loc[test_mask, meta_cols].copy()
            frame["predicted_mfe"] = pmfe
            frame["predicted_mae"] = pmae
            frame["fold_threshold"] = fold_threshold

            if args.model == "dualhead":
                clf, cscaler, ccols = fit_dual_head(
                    model_df[mfe_feats], train_mask, exec_mask, label_win, sd
                )
                if clf is not None:
                    frame["p_win"] = clf.predict_proba(cscaler.transform(Xtest_common[ccols]))[:, 1]

            all_seed_preds[sd].append(frame)

        winners_log.append({"fold": test_year, "train_samples": n_train, "test_samples": n_test, "mfe": mfe_w, "mae": mae_w})

    all_seed_preds = {s: pd.concat(fr, ignore_index=True) for s, fr in all_seed_preds.items() if fr}

    if not all_seed_preds:
        print("Tidak ada fold tereksekusi.")
        return 1

    # Ensemble antar-seed: fold mask identik antar-seed sehingga alignment posisi aman
    seed_ids = sorted(all_seed_preds.keys())
    ref = all_seed_preds[seed_ids[0]].drop(columns=["predicted_mfe", "predicted_mae", "p_win"], errors="ignore").copy()
    pmfe_mat = np.column_stack([all_seed_preds[s]["predicted_mfe"].values for s in seed_ids])
    pmae_mat = np.column_stack([all_seed_preds[s]["predicted_mae"].values for s in seed_ids])
    ref["predicted_mfe"] = pmfe_mat.mean(axis=1)
    ref["predicted_mae"] = pmae_mat.mean(axis=1)
    if all("p_win" in all_seed_preds[s].columns for s in seed_ids):
        pw_mat = np.column_stack([all_seed_preds[s]["p_win"].values for s in seed_ids])
        ref["p_win"] = pw_mat.mean(axis=1)

    scored_path = out_dir / f"scored_{args.tag}.csv"
    ref.to_csv(scored_path, index=False)

    meta = {
        "tag": args.tag,
        "families": fam_list,
        "extra_cols": extra_cols,
        "model_mode": args.model,
        "seeds": seeds,
        "embargo_days": args.embargo_days,
        "dataset_sha16": args.dataset_path.stem,
        "scored_csv": str(scored_path),
        "n_rows_scored": int(len(ref)),
        "winners_sample": winners_log[:6],
    }
    (out_dir / f"meta_{args.tag}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"[OK] scored -> {scored_path}")

    if not args.skip_eval:
        res = evaluate_scored(
            scored_path, args.tag, threshold=1.05,
            threshold_by_year=(nested_threshold_map or None),
        )
        raw_baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        baseline = {
            **raw_baseline["metrics"],
            **{k: raw_baseline[k] for k in ("by_year", "by_side", "by_session", "by_vol_regime")},
            "name": raw_baseline.get("canonical_baseline_name", "v8_canonical"),
        }
        ok, failed = gate_check(res, baseline)
        reg_row = {
            "tag": args.tag,
            "families": fam_list,
            "restrict_base": bool(args.restrict_base),
            "model": args.model,
            "seeds": seeds,
            "embargo_days": args.embargo_days,
            "trades": res["trades"],
            "win_rate": round(res["win_rate"], 3),
            "flat_net_pnl": round(res["flat_net_pnl"], 2),
            "dynamic_net_pnl": round(res["dynamic_net_pnl"], 2),
            "pf_dynamic": round(min(res["profit_factor_dynamic"], 999), 3),
            "max_drawdown_dynamic": round(res["max_drawdown_dynamic"], 2),
            "gate_passed": ok,
            "gate_failed": failed,
        }
        with REGISTRY_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(reg_row) + "\n")
        print(f"[REGISTRY] {json.dumps(reg_row)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
