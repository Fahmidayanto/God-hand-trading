import json
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "ValueCell_MT5" / ".env")
sys.path.insert(0, str(ROOT / "ValueCell_MT5" / "python"))

from valuecell.agents.llm_msa_agent import LLMMSAAgent
from valuecell.agents.market_structure_agent import MarketStructureAgent


BACKTEST_DIR = ROOT / "Backtest_result"


def market_row(file_name: str, timestamp: str) -> pd.DataFrame:
    frame = pd.read_csv(BACKTEST_DIR / file_name)
    row = frame.loc[frame["Time"] == timestamp].copy()
    return row.rename(columns=str.lower).drop(columns=["time"])


events = pd.read_csv(
    BACKTEST_DIR / "LLHHBOSData_XAUUSD_2026-08-28.csv",
    skiprows=1,
)
events = events.loc[
    events["Time"].isin(
        [
            "2025.12.31 08:00:00",
            "2026.01.02 20:30:00",
            "2026.01.05 04:45:00",
            "2026.01.05 17:00:00",
        ]
    )
]
structure_events = [
    {
        "type": row["Type"],
        "direction": row["Direction/Action"],
        "price": float(row["Price"]),
        "time": row["Time"],
        "timeframe": row["Timeframe"],
        "status": row["Status"],
    }
    for _, row in events.iterrows()
]

df_m15 = market_row(
    "MarketData_XAUUSD_M15_2026-08-28.csv",
    "2026.01.05 17:00:00",
)
df_h1 = market_row(
    "MarketData_XAUUSD_H1_2026-08-28.csv",
    "2026.01.05 17:00:00",
)
df_h4 = market_row(
    "MarketData_XAUUSD_H4_2026-08-28.csv",
    "2026.01.05 16:00:00",
)

msa = MarketStructureAgent(use_patterns=True)
msa_result = msa.analyze(
    df_m15=df_m15,
    df_h1=df_h1,
    df_h4=df_h4,
    structure_events=structure_events,
    session="London",
)
evidence = msa_result["evidence_snapshot"]
if msa_result.get("phase") != "PENDING_SETUP":
    raise RuntimeError(
        f"Expected PENDING_SETUP, got {msa_result.get('phase')}"
    )

llm = LLMMSAAgent(
    provider="suniesis",
    timeout_seconds=240.0,
    suniesis_model_timeout_seconds=220.0,
    suniesis_model_ids=(
        "gpt-5.4-mini",
        "gpt-5.6-luna",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.5",
        "gpt-5.4",
        "gpt-5.3-codex-spark",
        "codex-auto-review",
    ),
)
llm.analyze(evidence)
report = llm.wait_for_result(evidence["setup_id"], timeout=245.0)

history = evidence.get("historical_evidence") or {}
summary = {
    "msa": {
        "phase": msa_result.get("phase"),
        "signal": msa_result.get("signal"),
        "direction": evidence.get("setup", {}).get("direction"),
        "trigger_price": evidence.get("structure_context", {}).get("trigger_price"),
        "current_price": evidence.get("structure_context", {}).get("current_price"),
        "initial_confidence": msa_result.get("pre_signal", {}).get(
            "initial_confidence"
        ),
    },
    "evidence": {
        "total_patterns": history.get("total_count"),
        "completed_patterns": history.get("completed_count"),
        "top_matches_sent": len(history.get("top_matches", [])),
        "full_patterns_sent": "patterns" in history,
        "win_rate": history.get("win_rate"),
        "weighted_statistics": history.get("weighted_statistics"),
        "outcome_distribution": history.get("outcome_distribution"),
        "net_profit_statistics": history.get("net_profit_statistics"),
        "outcome_characteristics": history.get("outcome_characteristics"),
    },
    "llm_report": report,
}

print("REAL_REPLAY_RESULT")
print(json.dumps(summary, indent=2, ensure_ascii=True, default=str))