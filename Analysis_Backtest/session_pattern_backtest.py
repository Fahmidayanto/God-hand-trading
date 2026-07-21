"""
Independent session-pattern backtester for XAUUSD.

Ignores the existing bot/ML logic in this repo. Loads only the raw OHLCV
market data (M15/H1/H4) and SessionZone data from Backtest_result/, builds
entry signals from scratch (single indicators + combined-indicator variants),
simulates trades with ATR-based SL/TP, and ranks every
(strategy x SL/TP profile x entry session) combination by profitability.

Run with:
    "ValueCell_MT5/venv/Scripts/python.exe" Analysis_Backtest/session_pattern_backtest.py
"""

from pathlib import Path
import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "Backtest_result"
OUT_DIR = Path(__file__).resolve().parent / "results"
OUT_DIR.mkdir(parents=True, exist_ok=True)

POINT = 0.01          # XAUUSD price point size in this dataset (2-decimal quoting)
MAX_HOLD_BARS = 96     # 96 * 15min = 24h time-stop, same cap the original EA uses
SL_TP_PROFILES = [
    # (name, sl_atr_mult, tp_atr_mult)
    ("RR1.5_SL1.0ATR", 1.0, 1.5),
    ("RR2.0_SL1.5ATR", 1.5, 3.0),
    ("RR3.0_SL1.0ATR", 1.0, 3.0),
]


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

def load_market(timeframe: str) -> pd.DataFrame:
    files = sorted(DATA_DIR.glob(f"MarketData_XAUUSD_{timeframe}_*.csv"))
    if not files:
        raise FileNotFoundError(f"No MarketData files found for {timeframe}")
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df["Time"] = pd.to_datetime(df["Time"], format="%Y.%m.%d %H:%M:%S")
    df = df.drop_duplicates(subset="Time").sort_values("Time").reset_index(drop=True)
    return df


def load_sessions() -> pd.DataFrame:
    files = sorted(DATA_DIR.glob("SessionZone_XAUUSD_*.csv"))
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df["StartTime"] = pd.to_datetime(df["StartTime"], format="%Y.%m.%d %H:%M:%S")
    df["EndTime"] = pd.to_datetime(df["EndTime"], format="%Y.%m.%d %H:%M:%S")
    df = df.drop_duplicates(subset="StartTime").sort_values("StartTime").reset_index(drop=True)
    df["session_id"] = df.index
    return df


# --------------------------------------------------------------------------
# Indicators
# --------------------------------------------------------------------------

def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def macd(s: pd.Series, fast=12, slow=26, signal=9):
    macd_line = ema(s, fast) - ema(s, slow)
    signal_line = ema(macd_line, signal)
    return macd_line, signal_line


def bollinger(s: pd.Series, n=20, k=2):
    mid = s.rolling(n).mean()
    std = s.rolling(n).std()
    return mid - k * std, mid, mid + k * std


def crossed_up(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a.shift(1) <= b.shift(1)) & (a > b)


def crossed_down(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a.shift(1) >= b.shift(1)) & (a < b)


# --------------------------------------------------------------------------
# Build feature frame
# --------------------------------------------------------------------------

def build_features() -> pd.DataFrame:
    m15 = load_market("M15")
    h1 = load_market("H1")[["Time", "Close", "EMA200"]].rename(
        columns={"Close": "H1_Close", "EMA200": "H1_EMA200"}
    )
    h4 = load_market("H4")[["Time", "Close", "EMA200"]].rename(
        columns={"Close": "H4_Close", "EMA200": "H4_EMA200"}
    )
    sessions = load_sessions()

    df = m15.sort_values("Time").reset_index(drop=True)

    # tag each M15 bar with the session zone it falls in (contiguous zones ->
    # backward as-of join on StartTime is correct)
    df = pd.merge_asof(
        df, sessions[["StartTime", "Session", "IsDST", "session_id"]],
        left_on="Time", right_on="StartTime", direction="backward",
    )

    # bring in H1 / H4 context (last known H1/H4 bar as of this M15 bar)
    df = pd.merge_asof(df, h1.sort_values("Time"), on="Time", direction="backward")
    df = pd.merge_asof(df, h4.sort_values("Time"), on="Time", direction="backward")

    # indicators
    df["EMA9"] = ema(df["Close"], 9)
    df["EMA21"] = ema(df["Close"], 21)
    df["EMA50"] = ema(df["Close"], 50)
    # EMA200 already provided by the CSV export, reuse it directly
    df["RSI14"] = rsi(df["Close"], 14)
    df["ATR14"] = atr(df, 14)
    macd_line, signal_line = macd(df["Close"])
    df["MACD"] = macd_line
    df["MACD_SIGNAL"] = signal_line
    bb_low, bb_mid, bb_up = bollinger(df["Close"], 20, 2)
    df["BB_LOW"], df["BB_MID"], df["BB_UP"] = bb_low, bb_mid, bb_up
    df["DONCHIAN_HI20"] = df["High"].shift(1).rolling(20).max()
    df["DONCHIAN_LO20"] = df["Low"].shift(1).rolling(20).min()
    df["ATR_MEDIAN50"] = df["ATR14"].rolling(50).median()

    # session VWAP (typical price, cumulative within each session_id occurrence)
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    grp = df.groupby("session_id")
    cum_tpv = (tp * df["Volume"]).groupby(df["session_id"]).cumsum()
    cum_v = df["Volume"].groupby(df["session_id"]).cumsum().replace(0, np.nan)
    df["SESSION_VWAP"] = cum_tpv / cum_v

    # opening range per session (first hour = first 4 M15 bars of each session)
    df["bar_in_session"] = df.groupby("session_id").cumcount()
    or_high = df[df["bar_in_session"] < 4].groupby("session_id")["High"].max()
    or_low = df[df["bar_in_session"] < 4].groupby("session_id")["Low"].min()
    df["OR_HIGH"] = df["session_id"].map(or_high)
    df["OR_LOW"] = df["session_id"].map(or_low)

    return df


# --------------------------------------------------------------------------
# Strategy signals (edge-triggered long/short boolean series)
# --------------------------------------------------------------------------

def build_strategies(df: pd.DataFrame) -> dict:
    strategies = {}

    # --- single-indicator strategies -------------------------------------
    strategies["EMA9_21_Cross"] = (
        crossed_up(df["EMA9"], df["EMA21"]),
        crossed_down(df["EMA9"], df["EMA21"]),
    )

    strategies["Donchian20_Breakout"] = (
        df["Close"] > df["DONCHIAN_HI20"],
        df["Close"] < df["DONCHIAN_LO20"],
    )

    rsi_up = crossed_up(df["RSI14"], pd.Series(30, index=df.index))
    rsi_down = crossed_down(df["RSI14"], pd.Series(70, index=df.index))
    strategies["RSI_Reversion_30_70"] = (rsi_up, rsi_down)

    strategies["Bollinger_Breakout"] = (
        crossed_up(df["Close"], df["BB_UP"]),
        crossed_down(df["Close"], df["BB_LOW"]),
    )
    strategies["Bollinger_MeanReversion"] = (
        crossed_up(df["Close"], df["BB_LOW"]),
        crossed_down(df["Close"], df["BB_UP"]),
    )

    strategies["MACD_Cross"] = (
        crossed_up(df["MACD"], df["MACD_SIGNAL"]),
        crossed_down(df["MACD"], df["MACD_SIGNAL"]),
    )

    or_break_long = (df["bar_in_session"] >= 4) & (df["Close"] > df["OR_HIGH"]) & \
        (df["Close"].shift(1) <= df["OR_HIGH"].shift(1))
    or_break_short = (df["bar_in_session"] >= 4) & (df["Close"] < df["OR_LOW"]) & \
        (df["Close"].shift(1) >= df["OR_LOW"].shift(1))
    strategies["Opening_Range_Breakout"] = (or_break_long, or_break_short)

    vwap_dev = (df["Close"] - df["SESSION_VWAP"]).abs() > df["ATR14"]
    strategies["Session_VWAP_Reversion"] = (
        vwap_dev & crossed_up(df["Close"], df["SESSION_VWAP"] - df["ATR14"]),
        vwap_dev & crossed_down(df["Close"], df["SESSION_VWAP"] + df["ATR14"]),
    )

    session_open_price = df.groupby("session_id")["Open"].transform("first")
    atr_breakout_long = crossed_up(df["Close"], session_open_price + 1.5 * df["ATR14"])
    atr_breakout_short = crossed_down(df["Close"], session_open_price - 1.5 * df["ATR14"])
    strategies["Session_ATR_Volatility_Breakout"] = (atr_breakout_long, atr_breakout_short)

    # --- combined-indicator strategies ------------------------------------
    uptrend = df["Close"] > df["EMA200"]
    downtrend = df["Close"] < df["EMA200"]
    rsi_pullback_up = crossed_up(df["RSI14"], pd.Series(50, index=df.index))
    rsi_pullback_down = crossed_down(df["RSI14"], pd.Series(50, index=df.index))
    strategies["Combo_EMA200Trend_RSI50Pullback"] = (
        uptrend & rsi_pullback_up,
        downtrend & rsi_pullback_down,
    )

    h1_uptrend = df["H1_Close"] > df["H1_EMA200"]
    h1_downtrend = df["H1_Close"] < df["H1_EMA200"]
    strategies["Combo_H1Trend_M15DonchianBreakout"] = (
        h1_uptrend & (df["Close"] > df["DONCHIAN_HI20"]),
        h1_downtrend & (df["Close"] < df["DONCHIAN_LO20"]),
    )

    macd_cross_up = crossed_up(df["MACD"], df["MACD_SIGNAL"])
    macd_cross_down = crossed_down(df["MACD"], df["MACD_SIGNAL"])
    strategies["Combo_MACDCross_BollingerBreakout"] = (
        macd_cross_up & (df["Close"] > df["BB_MID"]),
        macd_cross_down & (df["Close"] < df["BB_MID"]),
    )

    h4_uptrend = df["H4_Close"] > df["H4_EMA200"]
    h4_downtrend = df["H4_Close"] < df["H4_EMA200"]
    strategies["Combo_H4Trend_OpeningRangeBreakout"] = (
        h4_uptrend & or_break_long,
        h4_downtrend & or_break_short,
    )

    high_vol = df["ATR14"] > df["ATR_MEDIAN50"]
    strategies["Combo_EMACross_ATRVolatilityFilter"] = (
        high_vol & crossed_up(df["EMA9"], df["EMA21"]),
        high_vol & crossed_down(df["EMA9"], df["EMA21"]),
    )

    strategies["Combo_H1H4TrendAlign_EMA9_21Cross"] = (
        h1_uptrend & h4_uptrend & crossed_up(df["EMA9"], df["EMA21"]),
        h1_downtrend & h4_downtrend & crossed_down(df["EMA9"], df["EMA21"]),
    )

    strategies["Combo_RSIReversion_BollingerBand"] = (
        rsi_up & (df["Close"] < df["BB_LOW"]),
        rsi_down & (df["Close"] > df["BB_UP"]),
    )

    return {k: (v[0].fillna(False), v[1].fillna(False)) for k, v in strategies.items()}


# --------------------------------------------------------------------------
# Trade simulation
# --------------------------------------------------------------------------

def simulate_trades(df: pd.DataFrame, long_sig: pd.Series, short_sig: pd.Series,
                     sl_mult: float, tp_mult: float) -> pd.DataFrame:
    close = df["Close"].to_numpy()
    high = df["High"].to_numpy()
    low = df["Low"].to_numpy()
    atr_vals = df["ATR14"].to_numpy()
    spread_vals = df["Spread"].to_numpy()
    times = df["Time"].to_numpy()
    session_ids = df["session_id"].to_numpy()
    session_names = df["Session"].to_numpy()
    long_arr = long_sig.to_numpy()
    short_arr = short_sig.to_numpy()

    n = len(df)
    trades = []
    i = 0
    while i < n:
        if long_arr[i] or short_arr[i]:
            direction = 1 if long_arr[i] else -1
            a = atr_vals[i]
            if np.isnan(a) or a <= 0:
                i += 1
                continue
            entry_price = close[i]
            sl_price = entry_price - direction * sl_mult * a
            tp_price = entry_price + direction * tp_mult * a
            entry_idx = i
            limit = min(n - 1, i + MAX_HOLD_BARS)
            exit_idx = None
            exit_reason = None
            j = i + 1
            while j <= limit:
                if direction == 1:
                    hit_sl = low[j] <= sl_price
                    hit_tp = high[j] >= tp_price
                else:
                    hit_sl = high[j] >= sl_price
                    hit_tp = low[j] <= tp_price
                if hit_sl:  # conservative: SL wins if both hit same bar
                    exit_idx, exit_reason = j, "SL"
                    break
                if hit_tp:
                    exit_idx, exit_reason = j, "TP"
                    break
                j += 1
            if exit_idx is None:
                exit_idx = limit
                exit_reason = "TIME"
            if exit_reason == "SL":
                exit_price = sl_price
            elif exit_reason == "TP":
                exit_price = tp_price
            else:
                exit_price = close[exit_idx]

            gross = direction * (exit_price - entry_price)
            net = gross - spread_vals[entry_idx] * POINT
            trades.append((
                times[entry_idx], times[exit_idx],
                "LONG" if direction == 1 else "SHORT",
                session_ids[entry_idx], session_names[entry_idx],
                session_ids[exit_idx], session_names[exit_idx],
                exit_reason, entry_price, sl_price, tp_price, exit_price,
                gross, net, exit_idx - entry_idx,
            ))
            i = exit_idx + 1
            continue
        i += 1

    return pd.DataFrame(trades, columns=[
        "entry_time", "exit_time", "direction",
        "entry_session_id", "entry_session", "exit_session_id", "exit_session",
        "exit_reason", "entry_price", "sl_price", "tp_price", "exit_price",
        "gross_points", "net_points", "hold_bars",
    ])


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------

def compute_metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return dict(trades=0, win_rate=np.nan, profit_factor=np.nan,
                     net_profit=0.0, expectancy=np.nan, max_drawdown=0.0)
    wins = trades["net_points"] > 0
    gross_win = trades.loc[wins, "net_points"].sum()
    gross_loss = -trades.loc[~wins, "net_points"].sum()
    profit_factor = gross_win / gross_loss if gross_loss > 0 else np.inf
    equity = trades["net_points"].cumsum()
    running_max = equity.cummax()
    drawdown = (equity - running_max).min()
    return dict(
        trades=len(trades),
        win_rate=wins.mean(),
        profit_factor=profit_factor,
        net_profit=trades["net_points"].sum(),
        expectancy=trades["net_points"].mean(),
        max_drawdown=drawdown,
    )


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    print("Loading data & building features ...")
    df = build_features()
    print(f"  {len(df):,} M15 bars from {df['Time'].min()} to {df['Time'].max()}")

    strategies = build_strategies(df)
    print(f"Testing {len(strategies)} strategies x {len(SL_TP_PROFILES)} SL/TP profiles ...")

    overall_rows = []
    session_rows = []
    transition_rows = []
    all_trades = []

    for strat_name, (long_sig, short_sig) in strategies.items():
        for profile_name, sl_mult, tp_mult in SL_TP_PROFILES:
            trades = simulate_trades(df, long_sig, short_sig, sl_mult, tp_mult)
            if trades.empty:
                continue
            trades["strategy"] = strat_name
            trades["sltp_profile"] = profile_name
            all_trades.append(trades)

            m = compute_metrics(trades)
            overall_rows.append({"strategy": strat_name, "sltp_profile": profile_name, **m})

            for sess, g in trades.groupby("entry_session"):
                m2 = compute_metrics(g)
                session_rows.append({
                    "strategy": strat_name, "sltp_profile": profile_name,
                    "entry_session": sess, **m2,
                })

            for (esess, xsess), g in trades.groupby(["entry_session", "exit_session"]):
                m3 = compute_metrics(g)
                transition_rows.append({
                    "strategy": strat_name, "sltp_profile": profile_name,
                    "entry_session": esess, "exit_session": xsess, **m3,
                })

    overall_df = pd.DataFrame(overall_rows).sort_values("profit_factor", ascending=False)
    session_df = pd.DataFrame(session_rows).sort_values("profit_factor", ascending=False)
    transition_df = pd.DataFrame(transition_rows).sort_values("profit_factor", ascending=False)
    trades_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()

    overall_df.to_csv(OUT_DIR / "overall_ranking.csv", index=False)
    session_df.to_csv(OUT_DIR / "session_ranking.csv", index=False)
    transition_df.to_csv(OUT_DIR / "session_transition_ranking.csv", index=False)
    trades_df.to_csv(OUT_DIR / "all_trades.csv", index=False)

    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)

    print("\n================ TOP 15 OVERALL (strategy x SL/TP profile) ================")
    print(overall_df[overall_df["trades"] >= 30].head(15).to_string(index=False))

    print("\n================ TOP 20 BY ENTRY SESSION (min 20 trades) ================")
    print(session_df[session_df["trades"] >= 20].head(20).to_string(index=False))

    print("\n================ TOP 20 SESSION-TO-SESSION TRANSITIONS (min 15 trades) ================")
    print(transition_df[transition_df["trades"] >= 15].head(20).to_string(index=False))

    print(f"\nFull CSV reports written to: {OUT_DIR}")


if __name__ == "__main__":
    main()
