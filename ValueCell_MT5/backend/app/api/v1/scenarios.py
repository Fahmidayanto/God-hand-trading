"""Strategy Scenario API endpoints - save/load/delete backtesting scenarios."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic models ───────────────────────────────────────────────────────────

class ScenarioCreate(BaseModel):
    name: str
    trailing_distance: float = 30.00
    tp_trigger: float = 10.00
    tp_ekspansi: float = 20.00
    max_ekspansi: int = 0
    enable_breakeven: bool = False
    breakeven_trigger: float = 15.00
    breakeven_buffer: float = 1.00
    lot_override: float = 0.00
    initial_sl_dist: float = 3.00
    initial_tp_dist: float = 30.00
    sl_min_distance: float = 5.00
    sl_safety_buffer: float = 10.00
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    total_trades: Optional[int] = None
    win_rate: Optional[float] = None
    total_pnl: Optional[float] = None
    max_drawdown: Optional[float] = None
    avg_pnl_per_trade: Optional[float] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS strategy_scenarios (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            trailing_distance FLOAT NOT NULL DEFAULT 30.00,
            tp_trigger FLOAT NOT NULL DEFAULT 10.00,
            tp_ekspansi FLOAT NOT NULL DEFAULT 20.00,
            max_ekspansi INT NOT NULL DEFAULT 0,
            enable_breakeven BOOLEAN NOT NULL DEFAULT FALSE,
            breakeven_trigger FLOAT NOT NULL DEFAULT 15.00,
            breakeven_buffer FLOAT NOT NULL DEFAULT 1.00,
            lot_override FLOAT NOT NULL DEFAULT 0.00,
            initial_sl_dist FLOAT NOT NULL DEFAULT 3.00,
            initial_tp_dist FLOAT NOT NULL DEFAULT 30.00,
            sl_min_distance FLOAT NOT NULL DEFAULT 5.00,
            sl_safety_buffer FLOAT NOT NULL DEFAULT 10.00,
            date_from TEXT,
            date_to TEXT,
            total_trades INT,
            win_rate FLOAT,
            total_pnl FLOAT,
            max_drawdown FLOAT,
            avg_pnl_per_trade FLOAT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    cur.execute("ALTER TABLE strategy_scenarios ADD COLUMN IF NOT EXISTS lot_override FLOAT NOT NULL DEFAULT 0.00")
    cur.execute("ALTER TABLE strategy_scenarios ADD COLUMN IF NOT EXISTS initial_sl_dist FLOAT NOT NULL DEFAULT 3.00")
    cur.execute("ALTER TABLE strategy_scenarios ADD COLUMN IF NOT EXISTS initial_tp_dist FLOAT NOT NULL DEFAULT 30.00")
    cur.execute("ALTER TABLE strategy_scenarios ADD COLUMN IF NOT EXISTS sl_min_distance FLOAT NOT NULL DEFAULT 5.00")
    cur.execute("ALTER TABLE strategy_scenarios ADD COLUMN IF NOT EXISTS sl_safety_buffer FLOAT NOT NULL DEFAULT 10.00")


def _row_to_dict(row):
    keys = [
        "id", "name",
        "trailing_distance", "tp_trigger", "tp_ekspansi", "max_ekspansi",
        "enable_breakeven", "breakeven_trigger", "breakeven_buffer", "lot_override",
        "initial_sl_dist", "initial_tp_dist", "sl_min_distance", "sl_safety_buffer",
        "date_from", "date_to",
        "total_trades", "win_rate", "total_pnl", "max_drawdown", "avg_pnl_per_trade",
        "created_at",
    ]
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in zip(keys, row)}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
@router.get("/")
async def list_scenarios():
    """List all saved strategy scenarios."""
    from app.core.database import get_db_conn, is_pool_ready
    if not is_pool_ready():
        raise HTTPException(status_code=503, detail="Database not ready")
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                _ensure_table(cur)
                cur.execute("SELECT * FROM strategy_scenarios ORDER BY created_at DESC")
                rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        logger.error(f"list_scenarios error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", status_code=201)
@router.post("/", status_code=201)
async def save_scenario(body: ScenarioCreate):
    """Save a new strategy scenario."""
    from app.core.database import get_db_conn, is_pool_ready
    if not is_pool_ready():
        raise HTTPException(status_code=503, detail="Database not ready")
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                _ensure_table(cur)
                cur.execute("""
                    INSERT INTO strategy_scenarios
                        (name, trailing_distance, tp_trigger, tp_ekspansi, max_ekspansi,
                         enable_breakeven, breakeven_trigger, breakeven_buffer, lot_override,
                         initial_sl_dist, initial_tp_dist, sl_min_distance, sl_safety_buffer,
                         date_from, date_to, total_trades, win_rate, total_pnl,
                         max_drawdown, avg_pnl_per_trade)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING *
                """, (
                    body.name, body.trailing_distance, body.tp_trigger, body.tp_ekspansi,
                    body.max_ekspansi, body.enable_breakeven, body.breakeven_trigger,
                    body.breakeven_buffer, body.lot_override, body.initial_sl_dist,
                    body.initial_tp_dist, body.sl_min_distance, body.sl_safety_buffer,
                    body.date_from, body.date_to, body.total_trades, body.win_rate, body.total_pnl,
                    body.max_drawdown, body.avg_pnl_per_trade,
                ))
                row = cur.fetchone()
            conn.commit()
        return _row_to_dict(row)
    except Exception as e:
        logger.error(f"save_scenario error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(scenario_id: int):
    """Delete a scenario by ID."""
    from app.core.database import get_db_conn, is_pool_ready
    if not is_pool_ready():
        raise HTTPException(status_code=503, detail="Database not ready")
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                _ensure_table(cur)
                cur.execute("DELETE FROM strategy_scenarios WHERE id = %s", (scenario_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"delete_scenario error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
