"""Performance analytics endpoint - load from JSON files."""

import json
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/performance", tags=["performance"])

ANALYTICS_DIR = Path(__file__).parent.parent.parent / "Backtest_result"

class MonthlyData(BaseModel):
    month: str
    trades: int
    win_rate: float
    pnl: float
    return_pct: float
    max_dd: float

class PerformanceSummary(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_profit: float
    final_equity: float
    return_pct: float
    avg_win: float
    avg_loss: float

@router.get("/yearly/{year}", response_model=dict)
async def get_yearly_analytics(year: int):
    """Get analytics for a specific year."""
    try:
        filepath = ANALYTICS_DIR / f"analytics_{year}.json"
        if not filepath.exists():
            return {"error": f"No data for year {year}"}
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        return {
            "year": year,
            "summary": data.get("summary", {}),
            "monthly": data.get("monthly", [])
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/monthly")
async def get_monthly_data(
    year: Optional[int] = Query(None, description="Filter by year"),
    month: Optional[int] = Query(None, description="Filter by month")
):
    """Get monthly performance data with optional filters."""
    try:
        # Load all years data
        all_data = {}
        for y in range(2020, 2026):
            filepath = ANALYTICS_DIR / f"analytics_{y}.json"
            if filepath.exists():
                with open(filepath, 'r') as f:
                    all_data[str(y)] = json.load(f)
        
        # Combine and filter
        result = []
        for y_key, y_data in sorted(all_data.items()):
            y_int = int(y_key)
            
            # Skip if year filter doesn't match
            if year and y_int != year:
                continue
            
            monthly_list = y_data.get("monthly", [])
            for m in monthly_list:
                m_str = m["month"]  # Format: "2025.01"
                m_num = int(m_str.split('.')[-1])
                
                # Skip if month filter doesn't match
                if month and m_num != month:
                    continue
                
                result.append(m)
        
        return result
    except Exception as e:
        print(f"Error in get_monthly_data: {e}")
        return []

@router.get("/stats")
async def get_performance_stats(
    year: Optional[int] = Query(None, description="Filter by year"),
    month: Optional[int] = Query(None, description="Filter by month")
):
    """Get aggregated performance statistics with optional filters."""
    try:
        monthly_data = await get_monthly_data(year=year, month=month)
        
        if not monthly_data:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0,
                "total_profit": 0,
                "final_equity": 0,
                "return_pct": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "max_drawdown": 0,
                "sharpe_ratio": 0,
            }
        
        # For year filter, get data from JSON summary if available
        if year and not month:
            filepath = ANALYTICS_DIR / f"analytics_{year}.json"
            if filepath.exists():
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    summary = data.get("summary", {})
                    return {
                        "total_trades": summary.get("total_trades", 0),
                        "winning_trades": summary.get("winning_trades", 0),
                        "losing_trades": summary.get("losing_trades", 0),
                        "win_rate": summary.get("win_rate", 0),
                        "total_profit": summary.get("total_profit", 0),
                        "final_equity": summary.get("final_equity", 0),
                        "return_pct": summary.get("return_pct", 0),
                        "avg_win": summary.get("avg_win", 0),
                        "avg_loss": summary.get("avg_loss", 0),
                        "profit_factor": 0,
                        "max_drawdown": 0,
                        "sharpe_ratio": 0,
                    }
        
        # Calculate aggregated stats from monthly data
        total_trades = sum(m.get("trades", 0) for m in monthly_data)
        total_pnl = monthly_data[-1].get("pnl", 0) if monthly_data else 0
        return_pct = monthly_data[-1].get("return_pct", 0) if monthly_data else 0
        avg_win_rate = sum(m.get("win_rate", 0) for m in monthly_data) / len(monthly_data) if monthly_data else 0
        
        return {
            "total_trades": total_trades,
            "winning_trades": 0,  # Calculated from monthly wins
            "losing_trades": 0,   # Calculated from monthly losses
            "win_rate": avg_win_rate,
            "total_profit": round(total_pnl, 2),
            "final_equity": round(1000 + total_pnl, 2),
            "return_pct": return_pct,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
        }
    except Exception as e:
        print(f"Error in get_performance_stats: {e}")
        return {
            "total_trades": 0,
            "win_rate": 0,
            "total_profit": 0,
            "final_equity": 0,
            "return_pct": 0,
        }

@router.get("/available-years")
async def get_available_years():
    """Get list of available years in analytics data."""
    try:
        years = []
        for y in range(2020, 2026):
            filepath = ANALYTICS_DIR / f"analytics_{y}.json"
            if filepath.exists():
                years.append(y)
        return {"years": sorted(years)}
    except Exception as e:
        return {"years": [], "error": str(e)}
