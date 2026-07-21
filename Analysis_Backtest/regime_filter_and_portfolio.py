"""
Follow-up analysis on top of session_pattern_backtest.py.

1. Adds an ADX(14) regime filter (computed on H1) to the two best
   overall trend-following combos, to see if it fixes the losing
   years found in the base backtest.
2. Builds a 2-sleeve portfolio: regime-filtered trend-following combo
   (H1Trend + M15 Donchian breakout) + Sydney Bollinger mean-reversion,
   and checks whether the combination is more consistent year-to-year
   than either sleeve alone.
3. Runs a wider SL/TP grid on the regime-filtered trend combo to see
   if profitability can be improved further.

Run with:
    "ValueCell_MT5/venv/Scripts/python.exe" Analysis_Backtest/regime_filter_and_portfolio.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_pattern_backtest import (  # noqa: E402
    build_features, simulate_trades, compute_metrics, crossed_up, crossed_down,
    load_market, POINT, OUT_DIR,
)

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 20)


def wilder_smooth(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1 / n, adjust=False).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr_w = wilder_smooth(tr, n)
    plus_di = 100 * wilder_smooth(pd.Series(plus_dm, index=df.index), n) / atr_w
    minus_di = 100 * wilder_smooth(pd.Series(minus_dm, index=df.index), n) / atr_w
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return wilder_smooth(dx, n)


def year_breakdown(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    t = trades.copy()
    t["year"] = pd.to_datetime(t["entry_time"]).dt.year

    def pf(g):
        win = g.loc[g.net_points > 0, "net_points"].sum()
        loss = -g.loc[g.net_points <= 0, "net_points"].sum()
        return win / loss if loss > 0 else np.inf

    rows = []
    for yr, g in t.groupby("year"):
        rows.append({"year": yr, "trades": len(g), "win_rate": (g.net_points > 0).mean(),
                     "pf": pf(g), "net": g.net_points.sum()})
    return pd.DataFrame(rows)


def main():
    print("Loading features (reusing session_pattern_backtest) ...")
    df = build_features()

    print("Computing ADX(14) on H1 and merging onto M15 ...")
    h1 = load_market("H1")
    h1["H1_ADX14"] = adx(h1, 14)
    h1 = h1[["Time", "H1_ADX14"]].sort_values("Time")
    df = pd.merge_asof(df.sort_values("Time"), h1, on="Time", direction="backward")

    # --- base (un-filtered) trend combo signals, for reference -----------
    h1_uptrend = df["H1_Close"] > df["H1_EMA200"]
    h1_downtrend = df["H1_Close"] < df["H1_EMA200"]
    donchian_long = df["Close"] > df["DONCHIAN_HI20"]
    donchian_short = df["Close"] < df["DONCHIAN_LO20"]
    base_long = (h1_uptrend & donchian_long).fillna(False)
    base_short = (h1_downtrend & donchian_short).fillna(False)

    print("\n================ 1) REGIME FILTER SWEEP (H1Trend + M15 Donchian, RR2.0_SL1.5ATR) ================")
    for adx_thresh in [0, 15, 20, 25, 30]:
        regime_ok = (df["H1_ADX14"] > adx_thresh).fillna(False)
        long_sig = base_long & regime_ok
        short_sig = base_short & regime_ok
        trades = simulate_trades(df, long_sig, short_sig, sl_mult=1.5, tp_mult=3.0)
        m = compute_metrics(trades)
        print(f"ADX > {adx_thresh:>2}: trades={m['trades']:>6}  win_rate={m['win_rate']:.3f}  "
              f"PF={m['profit_factor']:.3f}  net={m['net_profit']:.1f}  max_dd={m['max_drawdown']:.1f}")

    print("\nYear breakdown, ADX > 25 filter:")
    regime_ok = (df["H1_ADX14"] > 25).fillna(False)
    trend_trades = simulate_trades(df, base_long & regime_ok, base_short & regime_ok, 1.5, 3.0)
    print(year_breakdown(trend_trades).to_string(index=False))

    print("\nYear breakdown, NO regime filter (ADX > 0), for comparison:")
    trend_trades_nofilter = simulate_trades(df, base_long, base_short, 1.5, 3.0)
    print(year_breakdown(trend_trades_nofilter).to_string(index=False))

    # --- 2) wider SL/TP grid on the regime-filtered trend combo ----------
    print("\n================ 2) WIDER SL/TP GRID (H1Trend + M15 Donchian, ADX>25) ================")
    grid_rows = []
    for sl_mult in [1.0, 1.25, 1.5, 2.0]:
        for tp_mult in [1.5, 2.0, 2.5, 3.0, 4.0]:
            if tp_mult <= sl_mult:
                continue
            trades = simulate_trades(df, base_long & regime_ok, base_short & regime_ok, sl_mult, tp_mult)
            m = compute_metrics(trades)
            grid_rows.append({"sl_mult": sl_mult, "tp_mult": tp_mult, **m})
    grid_df = pd.DataFrame(grid_rows).sort_values("profit_factor", ascending=False)
    print(grid_df[grid_df["trades"] >= 100].to_string(index=False))
    grid_df.to_csv(OUT_DIR / "regime_filtered_sltp_grid.csv", index=False)

    # --- 3) Sydney Bollinger mean-reversion sleeve ------------------------
    print("\n================ 3) SYDNEY BOLLINGER MEAN-REVERSION SLEEVE ================")
    bb_low, bb_mid, bb_up = df["BB_LOW"], df["BB_MID"], df["BB_UP"]
    mr_long = crossed_up(df["Close"], bb_low).fillna(False)
    mr_short = crossed_down(df["Close"], bb_up).fillna(False)
    is_sydney = (df["Session"] == "Sydney").fillna(False)
    mr_trades_all = simulate_trades(df, mr_long & is_sydney, mr_short & is_sydney, sl_mult=1.5, tp_mult=3.0)
    print("Sydney mean-reversion (RR2.0_SL1.5ATR) year breakdown:")
    print(year_breakdown(mr_trades_all).to_string(index=False))
    print("\nOverall:", compute_metrics(mr_trades_all))

    # pick best regime-filtered trend profile from the grid for the portfolio
    best = grid_df[grid_df["trades"] >= 100].iloc[0]
    print(f"\nBest regime-filtered trend profile for portfolio: SL={best['sl_mult']}xATR TP={best['tp_mult']}xATR "
          f"(PF={best['profit_factor']:.3f}, trades={best['trades']:.0f})")
    trend_trades_best = simulate_trades(df, base_long & regime_ok, base_short & regime_ok,
                                         best["sl_mult"], best["tp_mult"])

    # --- 4) combined 2-sleeve portfolio ------------------------------------
    print("\n================ 4) COMBINED PORTFOLIO: Regime-filtered trend sleeve + Sydney MeanRev sleeve ================")
    trend_trades_best = trend_trades_best.copy()
    trend_trades_best["sleeve"] = "TrendFollow_H1_Donchian_ADXfiltered"
    mr_trades_all = mr_trades_all.copy()
    mr_trades_all["sleeve"] = "Sydney_BollingerMeanReversion"

    portfolio = pd.concat([trend_trades_best, mr_trades_all], ignore_index=True)
    portfolio["entry_time"] = pd.to_datetime(portfolio["entry_time"])
    portfolio = portfolio.sort_values("entry_time").reset_index(drop=True)
    portfolio.to_csv(OUT_DIR / "portfolio_trades.csv", index=False)

    print("Combined portfolio overall metrics:", compute_metrics(portfolio))
    print("\nCombined portfolio year breakdown:")
    print(year_breakdown(portfolio).to_string(index=False))

    print("\nPer-sleeve overall metrics:")
    for sleeve, g in portfolio.groupby("sleeve"):
        print(f"  {sleeve}: {compute_metrics(g)}")

    # equity curve / drawdown of the combined portfolio, in chronological order
    equity = portfolio["net_points"].cumsum()
    running_max = equity.cummax()
    dd = (equity - running_max)
    print(f"\nCombined portfolio max drawdown: {dd.min():.1f} points, "
          f"final equity: {equity.iloc[-1]:.1f} points, total trades: {len(portfolio)}")


if __name__ == "__main__":
    main()
