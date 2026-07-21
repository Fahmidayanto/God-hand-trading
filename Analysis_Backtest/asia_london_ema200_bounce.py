"""
Follow-up analysis:
1. How many points (broker points, 1 point = 0.01 USD, matching the
   original EA's point convention) does price typically travel from
   Asia session open through the Asia->London window?
2. A fresh EMA200(M15) pullback-bounce entry: price was trending
   (clearly above/below EMA200), dips back to touch EMA200, and closes
   back on the trend side -> enter in that direction.
3. For that entry, what TP distance (in points) is "safe" (high hit
   rate, small target) vs "medium" vs "hard" (aggressive, low hit rate,
   big target) -- based on the actual distribution of favorable price
   excursion after entry, then verified with a real SL/TP simulation.

Run with:
    "ValueCell_MT5/venv/Scripts/python.exe" Analysis_Backtest/asia_london_ema200_bounce.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_pattern_backtest import (  # noqa: E402
    build_features, simulate_trades, compute_metrics, OUT_DIR, MAX_HOLD_BARS,
)

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 20)

BROKER_POINT = 0.01  # 1 broker point = 0.01 USD price move (same convention as Dev_Bot TP=3000 points)


def to_points(usd_move: float) -> float:
    return usd_move / BROKER_POINT


# --------------------------------------------------------------------------
# 1) Price travel from Asia open through the Asia -> London window
# --------------------------------------------------------------------------

def session_window_ranges(df: pd.DataFrame) -> pd.DataFrame:
    windows = {
        "Asia_only (08-09)": ["Asia"],
        "Asia+TokyoLondonOverlap (08-10)": ["Asia", "Tokyo_London_Overlap"],
        "Asia+Overlap+London (08-14)": ["Asia", "Tokyo_London_Overlap", "London"],
    }
    rows = []
    df = df.copy()
    df["date"] = df["Time"].dt.date
    for label, sess_list in windows.items():
        sub = df[df["Session"].isin(sess_list)]
        daily = sub.groupby("date").agg(
            open_price=("Open", "first"), close_price=("Close", "last"),
            hi=("High", "max"), lo=("Low", "min"),
        )
        daily["range_usd"] = daily["hi"] - daily["lo"]
        daily["net_move_usd"] = (daily["close_price"] - daily["open_price"]).abs()
        rows.append({
            "window": label,
            "days": len(daily),
            "avg_range_points": to_points(daily["range_usd"].mean()),
            "median_range_points": to_points(daily["range_usd"].median()),
            "p25_range_points": to_points(daily["range_usd"].quantile(0.25)),
            "p75_range_points": to_points(daily["range_usd"].quantile(0.75)),
            "avg_net_move_points": to_points(daily["net_move_usd"].mean()),
            "median_net_move_points": to_points(daily["net_move_usd"].median()),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 2) EMA200(M15) pullback-bounce signal
# --------------------------------------------------------------------------

def build_ema200_bounce_signal(df: pd.DataFrame):
    trend_dist = 0.3  # bar must be clearly on one side of EMA200 before the touch (in ATR units)
    established_up = df["Close"].shift(1) > df["EMA200"].shift(1) + trend_dist * df["ATR14"].shift(1)
    established_down = df["Close"].shift(1) < df["EMA200"].shift(1) - trend_dist * df["ATR14"].shift(1)
    touch_now_up = (df["Low"] <= df["EMA200"]) & (df["Close"] > df["EMA200"])
    touch_now_down = (df["High"] >= df["EMA200"]) & (df["Close"] < df["EMA200"])
    fresh_touch_up = df["Low"].shift(1) > df["EMA200"].shift(1)
    fresh_touch_down = df["High"].shift(1) < df["EMA200"].shift(1)

    long_sig = (established_up & touch_now_up & fresh_touch_up).fillna(False)
    short_sig = (established_down & touch_now_down & fresh_touch_down).fillna(False)
    return long_sig, short_sig


# --------------------------------------------------------------------------
# 3) Max Favorable Excursion (MFE) distribution -> safe/medium/hard TP tiers
# --------------------------------------------------------------------------

def compute_mfe(df: pd.DataFrame, long_sig: pd.Series, short_sig: pd.Series,
                 invalidate_atr_mult: float = 1.0) -> pd.DataFrame:
    close = df["Close"].to_numpy()
    high = df["High"].to_numpy()
    low = df["Low"].to_numpy()
    ema200 = df["EMA200"].to_numpy()
    atr_vals = df["ATR14"].to_numpy()
    session = df["Session"].to_numpy()
    times = df["Time"].to_numpy()
    long_arr = long_sig.to_numpy()
    short_arr = short_sig.to_numpy()
    n = len(df)

    records = []
    for i in range(n):
        if not (long_arr[i] or short_arr[i]):
            continue
        direction = 1 if long_arr[i] else -1
        a = atr_vals[i]
        if np.isnan(a) or a <= 0:
            continue
        entry_price = close[i]
        invalidate_price = ema200[i] - direction * invalidate_atr_mult * a
        limit = min(n - 1, i + MAX_HOLD_BARS)
        mfe = 0.0
        j = i + 1
        while j <= limit:
            fav = (high[j] - entry_price) if direction == 1 else (entry_price - low[j])
            if fav > mfe:
                mfe = fav
            if direction == 1 and close[j] < invalidate_price:
                break
            if direction == -1 and close[j] > invalidate_price:
                break
            j += 1
        records.append((times[i], "LONG" if direction == 1 else "SHORT", session[i], mfe, a))

    return pd.DataFrame(records, columns=["entry_time", "direction", "entry_session", "mfe_usd", "atr_at_entry"])


def main():
    print("Loading features ...")
    df = build_features()

    print("\n================ 1) PERGERAKAN HARGA: ASIA OPEN -> LONDON WINDOW ================")
    ranges = session_window_ranges(df)
    print(ranges.to_string(index=False))

    print("\n================ 2) EMA200(M15) PULLBACK-BOUNCE SIGNAL ================")
    long_sig, short_sig = build_ema200_bounce_signal(df)
    print(f"Total sinyal: LONG={long_sig.sum()}  SHORT={short_sig.sum()}")

    mfe_df = compute_mfe(df, long_sig, short_sig, invalidate_atr_mult=1.0)
    mfe_df["mfe_points"] = mfe_df["mfe_usd"].apply(to_points)
    mfe_df["mfe_atr_ratio"] = mfe_df["mfe_usd"] / mfe_df["atr_at_entry"]
    mfe_df.to_csv(OUT_DIR / "ema200_bounce_mfe.csv", index=False)

    print("\nDistribusi MFE (poin), semua sesi:")
    print(mfe_df["mfe_points"].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).to_string())

    asia_london_sessions = ["Asia", "Tokyo_London_Overlap", "London"]
    mfe_al = mfe_df[mfe_df["entry_session"].isin(asia_london_sessions)]
    print(f"\nDistribusi MFE (poin), khusus entry di window Asia->London ({len(mfe_al)} sinyal):")
    print(mfe_al["mfe_points"].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).to_string())

    print("\nJumlah & rata-rata MFE per sesi entry:")
    print(mfe_df.groupby("entry_session")["mfe_points"].agg(["count", "mean", "median"]).sort_values("mean", ascending=False).to_string())

    # ATR-normalized percentiles -> used to derive TP tiers that generalize
    p25 = mfe_df["mfe_atr_ratio"].quantile(0.25)
    p50 = mfe_df["mfe_atr_ratio"].quantile(0.50)
    p75 = mfe_df["mfe_atr_ratio"].quantile(0.75)
    print(f"\nMFE/ATR ratio percentiles -> aman(p25)={p25:.2f}xATR  medium(p50)={p50:.2f}xATR  hard(p75)={p75:.2f}xATR")

    print("\n================ 3) VERIFIKASI TP AMAN/MEDIUM/HARD DENGAN SIMULASI SL/TP NYATA ================")
    sl_mult = 1.0  # SL fixed 1.0xATR (dekat, karena invalidation EMA200 juga ~1xATR)
    tiers = [("AMAN", p25), ("MEDIUM", p50), ("HARD", p75)]
    for label, tp_mult in tiers:
        trades = simulate_trades(df, long_sig, short_sig, sl_mult=sl_mult, tp_mult=tp_mult)
        m = compute_metrics(trades)
        avg_atr = df["ATR14"].mean()
        approx_tp_points = to_points(tp_mult * avg_atr)
        approx_sl_points = to_points(sl_mult * avg_atr)
        print(f"{label:7s} TP={tp_mult:.2f}xATR (~{approx_tp_points:.0f} poin avg)  SL={sl_mult:.2f}xATR (~{approx_sl_points:.0f} poin avg) "
              f"-> trades={m['trades']:>5} win_rate={m['win_rate']:.3f} PF={m['profit_factor']:.3f} "
              f"net={m['net_profit']:.1f} exp={m['expectancy']:.3f} max_dd={m['max_drawdown']:.1f}")
        trades.to_csv(OUT_DIR / f"ema200_bounce_trades_{label.lower()}.csv", index=False)

    print(f"\nFull CSV reports written to: {OUT_DIR}")


if __name__ == "__main__":
    main()
