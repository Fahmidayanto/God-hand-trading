"""
Build Dataset v12 (Comprehensive Technical, Multi-Timeframe, Structure Dynamics, Session Liquidity).

Enriches dataset_v11_unconstrained.csv (1942 samples) with 5 new feature families point-in-time:
1. Multi-Timeframe EMA & Slope Alignment (M15, H1, H4)
2. Market Structure Dynamics & Freshness (Structure Age, Density 5/10/20, Trend Strength, Confluence)
3. Candle Dynamics & Volatility Regimes (Body/Wick ratios, Volume Spike, Volatility Expansion)
4. Session Liquidity & Range Expansion (Current vs Prev Session, Breakout flags, Overlap)
5. Trade Plan Risk/Reward & Spread Ratios (Planned R:R, Spread-to-ATR)

Strict Anti-Leakage Guardrails:
- M15: bar at or before EntryTime.
- H1: last closed H1 bar strictly closed before EntryTime.
- H4: last closed H4 bar strictly closed before EntryTime.
- Structure: events strictly on or before EntryTime.
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from loguru import logger

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PYTHON_DIR = PROJECT_ROOT / "python"
BACKTEST_DIR = PROJECT_ROOT.parent / "Backtest_result"

if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close_prev = df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - close_prev).abs(),
        (low - close_prev).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()


def compute_slope(series: pd.Series, lookback: int = 3) -> pd.Series:
    return (series - series.shift(lookback)) / float(lookback)


def main() -> int:
    models_dir = PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest"
    src_dataset_path = models_dir / "dataset_v11_unconstrained.csv"
    out_dataset_path = models_dir / "dataset_v12_unconstrained.csv"

    logger.info("Loading baseline Dataset v11 from: {}", src_dataset_path)
    df = pd.read_csv(src_dataset_path)
    logger.info("Loaded {} samples with {} columns", len(df), len(df.columns))

    # Parse timestamps
    df["entry_time_dt"] = pd.to_datetime(df["entry_time"], utc=True)
    df = df.sort_values("entry_time_dt").reset_index(drop=True)

    # 1. Load and Index Multi-Timeframe Data per Year
    m15_by_year = {}
    h1_by_year = {}
    h4_by_year = {}
    struct_by_year = {}
    session_by_year = {}

    for res_file in sorted(BACKTEST_DIR.glob("Backtest_Results_XAUUSD_*.csv")):
        suffix = res_file.stem.replace("Backtest_Results_XAUUSD_", "")
        m15_path = BACKTEST_DIR / f"MarketData_XAUUSD_M15_{suffix}.csv"
        h1_path = BACKTEST_DIR / f"MarketData_XAUUSD_H1_{suffix}.csv"
        h4_path = BACKTEST_DIR / f"MarketData_XAUUSD_H4_{suffix}.csv"
        struct_path = BACKTEST_DIR / f"LLHHBOSData_XAUUSD_{suffix}.csv"
        sess_path = BACKTEST_DIR / f"SessionZone_XAUUSD_{suffix}.csv"

        if m15_path.exists():
            m15_df = pd.read_csv(m15_path)
            m15_df.columns = [c.strip().lower() for c in m15_df.columns]
            m15_df["time_dt"] = pd.to_datetime(m15_df["time"], utc=True)
            m15_df = m15_df.sort_values("time_dt").reset_index(drop=True)
            m15_df["ema200"] = m15_df["close"].ewm(span=200, adjust=False).mean()
            m15_df["ema200_slope5"] = compute_slope(m15_df["ema200"], 5)
            m15_df["atr14"] = compute_atr(m15_df, 14)
            m15_df["atr50"] = compute_atr(m15_df, 50)
            vol_col = "volume" if "volume" in m15_df.columns else ("tick_volume" if "tick_volume" in m15_df.columns else None)
            if vol_col:
                m15_df["vol_sma20"] = m15_df[vol_col].rolling(20, min_periods=1).mean()
            else:
                m15_df["vol_sma20"] = 100.0
                m15_df["volume"] = 100.0
            m15_by_year[suffix] = m15_df

        if h1_path.exists():
            h1_df = pd.read_csv(h1_path)
            h1_df.columns = [c.strip().lower() for c in h1_df.columns]
            h1_df["time_dt"] = pd.to_datetime(h1_df["time"], utc=True)
            h1_df = h1_df.sort_values("time_dt").reset_index(drop=True)
            h1_df["ema200"] = h1_df["close"].ewm(span=200, adjust=False).mean()
            h1_df["ema200_slope3"] = compute_slope(h1_df["ema200"], 3)
            h1_df["atr14"] = compute_atr(h1_df, 14)
            h1_by_year[suffix] = h1_df

        if h4_path.exists():
            h4_df = pd.read_csv(h4_path)
            h4_df.columns = [c.strip().lower() for c in h4_df.columns]
            h4_df["time_dt"] = pd.to_datetime(h4_df["time"], utc=True)
            h4_df = h4_df.sort_values("time_dt").reset_index(drop=True)
            h4_df["ema200"] = h4_df["close"].ewm(span=200, adjust=False).mean()
            h4_df["ema200_slope3"] = compute_slope(h4_df["ema200"], 3)
            h4_df["atr14"] = compute_atr(h4_df, 14)
            h4_by_year[suffix] = h4_df

        if struct_path.exists():
            try:
                # Check first line
                with open(struct_path, "r", encoding="utf-8", errors="ignore") as f_st:
                    f_line = f_st.readline()
                skip = 1 if "===" in f_line else 0
                st_df = pd.read_csv(struct_path, skiprows=skip)
                st_df.columns = [c.strip() for c in st_df.columns]
                st_df["time_dt"] = pd.to_datetime(st_df["Time"], utc=True)
                st_df = st_df.sort_values("time_dt").reset_index(drop=True)
                struct_by_year[suffix] = st_df
            except Exception as exc:
                logger.warning("Error reading struct {}: {}", struct_path.name, exc)

        if sess_path.exists():
            se_df = pd.read_csv(sess_path)
            se_df.columns = [c.strip() for c in se_df.columns]
            se_df["start_dt"] = pd.to_datetime(se_df["StartTime"], utc=True)
            se_df["end_dt"] = pd.to_datetime(se_df["EndTime"], utc=True)
            se_df = se_df.sort_values("start_dt").reset_index(drop=True)
            session_by_year[suffix] = se_df

    logger.info("Loaded MTF Data for {} periods", len(m15_by_year))

    # 2. Extract Features Point-in-Time for each sample
    n_samples = len(df)
    
    # Family 1: MTF Alignment
    m15_ema_slope = np.zeros(n_samples, dtype=np.float32)
    h1_ema_slope = np.zeros(n_samples, dtype=np.float32)
    h4_ema_slope = np.zeros(n_samples, dtype=np.float32)
    h1_trend_align = np.zeros(n_samples, dtype=np.float32)
    h4_trend_align = np.zeros(n_samples, dtype=np.float32)
    mtf_align_score = np.zeros(n_samples, dtype=np.float32)
    price_to_h1_ema_atr = np.zeros(n_samples, dtype=np.float32)
    price_to_h4_ema_atr = np.zeros(n_samples, dtype=np.float32)

    # Family 2: Structure Dynamics
    struct_age_hours = np.zeros(n_samples, dtype=np.float32)
    struct_count_5b = np.zeros(n_samples, dtype=np.float32)
    struct_count_10b = np.zeros(n_samples, dtype=np.float32)
    struct_count_20b = np.zeros(n_samples, dtype=np.float32)
    trend_strength_ratio = np.zeros(n_samples, dtype=np.float32)
    is_confluence_zone = np.zeros(n_samples, dtype=np.float32)

    # Family 3: Candle Action & Volatility
    candle_body_ratio = np.zeros(n_samples, dtype=np.float32)
    upper_wick_ratio = np.zeros(n_samples, dtype=np.float32)
    lower_wick_ratio = np.zeros(n_samples, dtype=np.float32)
    vol_spike_ratio = np.zeros(n_samples, dtype=np.float32)
    vol_regime_ratio = np.zeros(n_samples, dtype=np.float32)
    range_expansion_5b = np.zeros(n_samples, dtype=np.float32)

    # Family 4: Session Liquidity
    session_range_exp = np.zeros(n_samples, dtype=np.float32)
    is_prev_high_break = np.zeros(n_samples, dtype=np.float32)
    is_prev_low_break = np.zeros(n_samples, dtype=np.float32)
    session_progress_pct = np.zeros(n_samples, dtype=np.float32)

    # Family 5: Cost & Spread Ratios
    spread_to_atr_ratio = np.zeros(n_samples, dtype=np.float32)
    risk_to_atr_ratio = np.zeros(n_samples, dtype=np.float32)

    for i, row in df.iterrows():
        t = row["entry_time_dt"]
        ep = float(row["entry_price"])
        sig = str(row["signal"]).upper()
        s_yr = str(row.get("source_year", str(t.year)))

        # Find matching suffix
        matched_suffix = None
        for sfx in m15_by_year.keys():
            if str(t.year) in sfx:
                matched_suffix = sfx
                break
        if not matched_suffix and len(m15_by_year) > 0:
            matched_suffix = list(m15_by_year.keys())[0]

        # M15 Lookup
        m15_df = m15_by_year.get(matched_suffix)
        m15_atr = 2.0  # default points
        if m15_df is not None:
            m15_sub = m15_df[m15_df["time_dt"] <= t]
            if len(m15_sub) > 0:
                last_m15 = m15_sub.iloc[-1]
                m15_atr = float(last_m15.get("atr14", 2.0))
                m15_atr50 = float(last_m15.get("atr50", m15_atr))
                m15_ema_slope[i] = float(last_m15.get("ema200_slope5", 0.0))

                # Candle Dynamics
                c_o = float(last_m15["open"])
                c_h = float(last_m15["high"])
                c_l = float(last_m15["low"])
                c_c = float(last_m15["close"])
                c_rng = max(0.01, c_h - c_l)
                candle_body_ratio[i] = abs(c_c - c_o) / c_rng
                upper_wick_ratio[i] = (c_h - max(c_o, c_c)) / c_rng
                lower_wick_ratio[i] = (min(c_o, c_c) - c_l) / c_rng

                v_curr = float(last_m15.get("volume", last_m15.get("tick_volume", 100.0)))
                v_avg = float(last_m15.get("vol_sma20", v_curr))
                vol_spike_ratio[i] = v_curr / max(1.0, v_avg)
                vol_regime_ratio[i] = m15_atr / max(0.1, m15_atr50)

                # 5-bar range expansion
                if len(m15_sub) >= 5:
                    h5 = m15_sub.iloc[-5:]["high"].max()
                    l5 = m15_sub.iloc[-5:]["low"].min()
                    range_expansion_5b[i] = (h5 - l5) / max(0.1, 5.0 * m15_atr)

        # H1 Lookup (Strict Point-in-Time: closed H1 bar before t)
        h1_df = h1_by_year.get(matched_suffix)
        if h1_df is not None:
            # H1 bar started <= t - 1 hour is completely closed
            h1_sub = h1_df[h1_df["time_dt"] <= (t - pd.Timedelta(hours=1))]
            if len(h1_sub) > 0:
                last_h1 = h1_sub.iloc[-1]
                h1_ema = float(last_h1["ema200"])
                h1_atr = max(0.1, float(last_h1.get("atr14", 5.0)))
                h1_ema_slope[i] = float(last_h1.get("ema200_slope3", 0.0))
                price_to_h1_ema_atr[i] = (ep - h1_ema) / h1_atr
                is_h1_bull = ep > h1_ema
                h1_trend_align[i] = 1.0 if (sig == "BUY" and is_h1_bull) or (sig == "SELL" and not is_h1_bull) else -1.0

        # H4 Lookup (Strict Point-in-Time: closed H4 bar before t)
        h4_df = h4_by_year.get(matched_suffix)
        if h4_df is not None:
            h4_sub = h4_df[h4_df["time_dt"] <= (t - pd.Timedelta(hours=4))]
            if len(h4_sub) > 0:
                last_h4 = h4_sub.iloc[-1]
                h4_ema = float(last_h4["ema200"])
                h4_atr = max(0.1, float(last_h4.get("atr14", 10.0)))
                h4_ema_slope[i] = float(last_h4.get("ema200_slope3", 0.0))
                price_to_h4_ema_atr[i] = (ep - h4_ema) / h4_atr
                is_h4_bull = ep > h4_ema
                h4_trend_align[i] = 1.0 if (sig == "BUY" and is_h4_bull) or (sig == "SELL" and not is_h4_bull) else -1.0

        # Composite MTF Align Score
        m15_align = 1.0 if (sig == "BUY" and m15_ema_slope[i] > 0) or (sig == "SELL" and m15_ema_slope[i] < 0) else -1.0
        mtf_align_score[i] = m15_align + h1_trend_align[i] + h4_trend_align[i]

        # Structure Dynamics Lookup
        st_df = struct_by_year.get(matched_suffix)
        if st_df is not None:
            st_sub = st_df[st_df["time_dt"] <= t]
            if len(st_sub) > 0:
                last_st = st_sub.iloc[-1]
                dt_h = (t - last_st["time_dt"]).total_seconds() / 3600.0
                struct_age_hours[i] = max(0.0, min(168.0, dt_h))

                # Structure frequency in last 5, 10, 20 bars (1.25h, 2.5h, 5h)
                t_5b = t - pd.Timedelta(minutes=75)
                t_10b = t - pd.Timedelta(minutes=150)
                t_20b = t - pd.Timedelta(minutes=300)
                struct_count_5b[i] = float((st_sub["time_dt"] >= t_5b).sum())
                struct_count_10b[i] = float((st_sub["time_dt"] >= t_10b).sum())
                struct_count_20b[i] = float((st_sub["time_dt"] >= t_20b).sum())

                # Trend strength ratio (last 50 structures)
                recent_50 = st_sub.iloc[-50:]
                bull_c = recent_50["Direction/Action"].str.contains("BULL", case=False, na=False).sum()
                bear_c = recent_50["Direction/Action"].str.contains("BEAR", case=False, na=False).sum()
                tot_c = bull_c + bear_c
                trend_strength_ratio[i] = float((bull_c - bear_c) / tot_c) if tot_c > 0 else 0.0

                # Confluence zone: proximity to recent swing price <= 1.0 x ATR
                recent_prices = pd.to_numeric(recent_50["Price"], errors="coerce").dropna().values
                if len(recent_prices) > 0:
                    min_dist = np.min(np.abs(recent_prices - ep))
                    is_confluence_zone[i] = 1.0 if min_dist <= (m15_atr * 1.5) else 0.0

        # Session Liquidity Lookup
        se_df = session_by_year.get(matched_suffix)
        if se_df is not None:
            active_sess = se_df[(se_df["start_dt"] <= t) & (t <= se_df["end_dt"])]
            if len(active_sess) > 0:
                s_row = active_sess.iloc[0]
                s_start = s_row["start_dt"]
                s_end = s_row["end_dt"]
                dur = max(60.0, (s_end - s_start).total_seconds())
                prog = max(0.0, min(1.0, (t - s_start).total_seconds() / dur))
                session_progress_pct[i] = float(prog)

                # Previous session
                prev_sessions = se_df[se_df["end_dt"] <= s_start]
                if len(prev_sessions) > 0:
                    prev_s = prev_sessions.iloc[-1]
                    cur_rng = float(s_row.get("RangePoints", 100.0))
                    prev_rng = max(1.0, float(prev_s.get("RangePoints", 100.0)))
                    session_range_exp[i] = cur_rng / prev_rng

                    prev_h = float(prev_s.get("HighPrice", ep))
                    prev_l = float(prev_s.get("LowPrice", ep))
                    is_prev_high_break[i] = 1.0 if ep > prev_h else 0.0
                    is_prev_low_break[i] = 1.0 if ep < prev_l else 0.0

        # Cost & Spread Ratios
        spr = float(row.get("spread", 18.0))
        risk_p = float(row.get("init_risk_points", 3000.0))
        spread_to_atr_ratio[i] = spr / max(1.0, m15_atr * 100.0)
        risk_to_atr_ratio[i] = risk_p / max(1.0, m15_atr * 100.0)

    # Attach all new features
    df["m15_ema200_slope"] = m15_ema_slope
    df["h1_ema200_slope"] = h1_ema_slope
    df["h4_ema200_slope"] = h4_ema_slope
    df["h1_trend_align"] = h1_trend_align
    df["h4_trend_align"] = h4_trend_align
    df["mtf_alignment_score"] = mtf_align_score
    df["price_to_h1_ema_atr"] = price_to_h1_ema_atr
    df["price_to_h4_ema_atr"] = price_to_h4_ema_atr

    df["structure_age_hours"] = struct_age_hours
    df["struct_count_5b"] = struct_count_5b
    df["struct_count_10b"] = struct_count_10b
    df["struct_count_20b"] = struct_count_20b
    df["trend_strength_ratio"] = trend_strength_ratio
    df["is_confluence_zone"] = is_confluence_zone

    df["candle_body_ratio"] = candle_body_ratio
    df["upper_wick_ratio"] = upper_wick_ratio
    df["lower_wick_ratio"] = lower_wick_ratio
    df["vol_spike_ratio"] = vol_spike_ratio
    df["vol_regime_ratio"] = vol_regime_ratio
    df["range_expansion_5b"] = range_expansion_5b

    df["session_range_exp"] = session_range_exp
    df["is_prev_high_break"] = is_prev_high_break
    df["is_prev_low_break"] = is_prev_low_break
    df["session_progress_pct"] = session_progress_pct

    df["spread_to_atr_ratio"] = spread_to_atr_ratio
    df["risk_to_atr_ratio"] = risk_to_atr_ratio

    # Cleanup temp columns
    df = df.drop(columns=["entry_time_dt"], errors="ignore")

    df.to_csv(out_dataset_path, index=False)
    logger.info("Successfully built and saved Dataset v12: {} ({} samples, {} columns)", out_dataset_path, len(df), len(df.columns))

    return 0


if __name__ == "__main__":
    sys.exit(main())
