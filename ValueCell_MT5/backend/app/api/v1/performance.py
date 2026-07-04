"""Performance Analytics API endpoints."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.core.mt5_manager import MT5Manager
from app.dependencies import get_mt5_manager
from app.models.performance import (
    MonthlyPerformance,
    PerformanceStats,
    RiskMetrics,
    TradeStatistics,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats", response_model=PerformanceStats)
async def get_performance_stats(
    days: int = Query(180, ge=1, le=365),
    mt5: MT5Manager = Depends(get_mt5_manager),
):
    """
    Get overall performance statistics.
    
    Args:
        days: Number of days to analyze (default 180)
        
    Returns:
        Comprehensive performance metrics
    """
    try:
        # Get trade history
        deals = mt5.get_history_deals(days)

        if not deals:
            # Return empty stats if no trades
            return PerformanceStats(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_profit=0.0,
                total_loss=0.0,
                net_profit=0.0,
                profit_factor=0.0,
                sharpe_ratio=None,
                max_drawdown=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                avg_trade_duration=0.0,
            )

        # Calculate statistics
        total_trades = len(deals)
        winning_trades = [d for d in deals if d["profit"] > 0]
        losing_trades = [d for d in deals if d["profit"] < 0]

        total_profit = sum(d["profit"] for d in winning_trades)
        total_loss = abs(sum(d["profit"] for d in losing_trades))

        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else 0

        # Get real drawdown from agent_decisions (replaces hardcoded -8.3)
        try:
            from app.services.performance_service import get_real_drawdown
            dd_data = get_real_drawdown(days_back=min(days, 30))
            real_max_dd = dd_data.get("max_drawdown_pct", 0.0)
        except Exception:
            real_max_dd = 0.0

        return PerformanceStats(
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            total_profit=total_profit,
            total_loss=total_loss,
            net_profit=total_profit - total_loss,
            profit_factor=profit_factor,
            sharpe_ratio=1.87,  # TODO: Calculate actual Sharpe ratio
            max_drawdown=real_max_dd,  # ← real, was hardcoded -8.3
            avg_win=total_profit / len(winning_trades) if winning_trades else 0,
            avg_loss=total_loss / len(losing_trades) if losing_trades else 0,
            largest_win=max([d["profit"] for d in winning_trades]) if winning_trades else 0,
            largest_loss=min([d["profit"] for d in losing_trades]) if losing_trades else 0,
            avg_trade_duration=120.0,  # TODO: Calculate from timestamps
        )

    except Exception as e:
        logger.error(f"Performance stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/monthly", response_model=List[MonthlyPerformance])
async def get_monthly_performance(
    year: int = Query(None),
    month: int = Query(None)
):
    """
    Get monthly performance breakdown.
    
    Args:
        year: Filter by specific year (optional)
        month: Filter by specific month 1-12 (optional)
    
    Returns performance data grouped by month from backtest CSV files.
    """
    try:
        from app.services.performance_service import get_monthly_pnl_from_csv
        
        # Get monthly P&L data from CSV with filters
        csv_data = get_monthly_pnl_from_csv(year=year, month=month)
        
        if not csv_data:
            # Return empty list if no data
            return []
        
        # Convert CSV data to MonthlyPerformance format
        months = []
        initial_balance = 10000.0
        cumulative_profit = 0.0
        
        for data in csv_data:
            cumulative_profit += data['net_profit']
            
            # Calculate return percentage
            return_pct = (cumulative_profit / initial_balance * 100) if initial_balance > 0 else 0.0
            
            month_perf = MonthlyPerformance(
                month=data['month'],
                year=data['year'],
                trades=data['executed_trades'],
                win_rate=data['win_rate'],
                profit=data['net_profit'],
                return_pct=round(return_pct, 2),
                max_dd=-2.0,  # TODO: Calculate actual max drawdown
                sharpe=1.85,  # TODO: Calculate actual Sharpe ratio
            )
            months.append(month_perf)
        
        return months

    except Exception as e:
        logger.error(f"Monthly performance error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/available-years")
async def get_available_years(symbol: str = Query("XAUUSD")):
    """
    Get list of available years from backtest CSV files.
    
    Returns:
        {
            "years": [2020, 2021, 2022, 2023, 2024, 2025, 2026],
            "latest_year": 2026
        }
    """
    try:
        from app.services.performance_service import list_available_years
        
        years = list_available_years(symbol)
        latest_year = max(years) if years else None
        
        return {
            "years": sorted(years),
            "latest_year": latest_year
        }
    
    except Exception as e:
        logger.error(f"Error getting available years: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/monthly-pnl")
async def get_monthly_pnl_detailed(
    symbol: str = Query("XAUUSD"),
    year: int = Query(None),
    month: int = Query(None)
):
    """
    Get detailed monthly Profit/Loss data from backtest CSV for charting.
    
    Args:
        symbol: Trading symbol (default: XAUUSD)
        year: Filter by specific year (optional)
        month: Filter by specific month 1-12 (optional)
    
    Returns:
        {
            "data": [
                {
                    "month": "January",
                    "year": 2025,
                    "month_num": 1,
                    "month_label": "Jan 2025",
                    "trades": 12,
                    "executed_trades": 10,
                    "profit": 450.50,
                    "loss": -200.30,
                    "net_profit": 250.20,
                    "win_rate": 70.0,
                    "winning_trades": 7,
                    "losing_trades": 3
                },
                ...
            ],
            "total_net_profit": 3056.69,
            "total_trades": 38,
            "avg_monthly_profit": 382.09,
            "best_month": "March",
            "worst_month": "July"
        }
    """
    try:
        from app.services.performance_service import get_monthly_pnl_from_csv
        
        # Pass both year and month to the service
        csv_data = get_monthly_pnl_from_csv(symbol, year, month)
        
        if not csv_data:
            return {
                "data": [],
                "total_net_profit": 0.0,
                "total_trades": 0,
                "avg_monthly_profit": 0.0,
                "best_month": None,
                "worst_month": None
            }
        
        # Add month label for display
        for data in csv_data:
            data['month_label'] = f"{data['month'][:3]} {data['year']}"
        
        # Calculate summary stats
        total_net_profit = sum(d['net_profit'] for d in csv_data)
        total_trades = sum(d['executed_trades'] for d in csv_data)
        avg_monthly_profit = total_net_profit / len(csv_data) if csv_data else 0.0
        
        # Find best and worst months
        best_month = max(csv_data, key=lambda x: x['net_profit']) if csv_data else None
        worst_month = min(csv_data, key=lambda x: x['net_profit']) if csv_data else None
        
        return {
            "data": csv_data,
            "total_net_profit": round(total_net_profit, 2),
            "total_trades": total_trades,
            "avg_monthly_profit": round(avg_monthly_profit, 2),
            "best_month": f"{best_month['month']} {best_month['year']}" if best_month else None,
            "worst_month": f"{worst_month['month']} {worst_month['year']}" if worst_month else None
        }
    
    except Exception as e:
        logger.error(f"Monthly P&L error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/risk", response_model=RiskMetrics)
async def get_risk_metrics(
    mt5: MT5Manager = Depends(get_mt5_manager),
):
    """
    Get current risk metrics.
    
    Returns risk exposure, position limits, daily loss, etc.
    """
    try:
        from app.config import get_settings

        settings = get_settings()

        # Get account and positions
        account = mt5.get_account_info()
        positions = mt5.get_positions()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to fetch account data",
            )

        # Calculate exposure
        total_margin = sum(
            abs(pos.get("profit", 0)) for pos in positions
        )
        balance = account["balance"]
        current_exposure = (total_margin / balance * 100) if balance > 0 else 0

        # Calculate daily loss (placeholder)
        daily_loss = account.get("profit", 0.0)
        daily_loss_pct = (daily_loss / balance * 100) if balance > 0 else 0

        # Determine risk status
        if current_exposure > 10:
            risk_status = "CRITICAL"
        elif current_exposure > 5:
            risk_status = "HIGH"
        elif current_exposure > 2:
            risk_status = "MEDIUM"
        else:
            risk_status = "LOW"

        return RiskMetrics(
            current_exposure=current_exposure,
            max_risk_allowed=settings.MAX_RISK_PER_TRADE * 100,
            open_positions=len(positions),
            max_positions_allowed=settings.MAX_OPEN_POSITIONS,
            daily_loss=daily_loss,
            max_daily_loss_allowed=settings.MAX_DAILY_LOSS * balance,
            risk_status=risk_status,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Risk metrics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ─── Lapisan 4: Performa Historis Endpoints ───────────────────────────────────

@router.get("/session-stats")
async def get_session_stats(days_back: int = Query(30, ge=1, le=90)):
    """
    Get win rate broken down by trading session (London, New York, Sydney, Overlap).

    Win rate is computed from agent signal direction vs next 3 M15 candles
    (signal quality / predictive accuracy). This is the most meaningful metric
    available while the system is in paper trading mode (no actual closed trades).

    Query params:
    - days_back: How many days of history to analyse (default: 30, max: 90)

    Returns:
        {
          "sessions": {
            "LONDON":   {"label": "London", "win_rate": 68.5, "total": 14, ...},
            "NEW_YORK": {...},
            ...
          },
          "days_back": 30,
          "method": "signal_quality",
          "note": "..."
        }
    """
    try:
        from app.services.performance_service import get_session_performance
        data = get_session_performance(days_back=days_back)
        return JSONResponse(content=data)
    except Exception as e:
        logger.error(f"Session stats error: {e}", exc_info=True)
        return JSONResponse(content={
            "sessions": {},
            "days_back": days_back,
            "error": str(e),
        })


@router.get("/last-signals")
async def get_last_signals(n: int = Query(3, ge=1, le=20)):
    """
    Get the last N non-HOLD agent signals with their WIN/LOSS/PENDING result.

    Each signal is evaluated by comparing the entry price to the close price
    3 M15-candles after the decision timestamp.

    Query params:
    - n: Number of signals to return (default: 3, max: 20)

    Returns:
        {
          "signals": [
            {
              "id": 28,
              "timestamp": "2026-06-15T...",
              "session": "LONDON",
              "direction": "BUY",
              "consensus_score": 0.72,
              "entry_price": 3312.5,
              "exit_price": 3315.2,
              "pnl_estimate": 2.7,
              "result": "WIN"
            },
            ...
          ]
        }
    """
    try:
        from app.services.performance_service import get_last_n_signals
        data = get_last_n_signals(n=n)
        return JSONResponse(content=data)
    except Exception as e:
        logger.error(f"Last signals error: {e}", exc_info=True)
        return JSONResponse(content={"signals": [], "error": str(e)})


@router.get("/drawdown")
async def get_drawdown(days_back: int = Query(30, ge=1, le=90)):
    """
    Get real drawdown calculated from agent_decisions equity simulation.

    Replaces the hardcoded -8.3% value. Builds a simulated equity curve
    from WIN/LOSS outcomes of all BUY/SELL signals vs market price 3 candles
    later, then computes the max drawdown from the peak.

    Query params:
    - days_back: How many days to include (default: 30, max: 90)

    Returns:
        {
          "current_drawdown_pct": -2.1,
          "max_drawdown_pct": -5.4,
          "total_signals": 18,
          "wins": 12,
          "losses": 6,
          "win_rate": 66.7,
          "peak_equity": 101.4,
          "current_equity": 99.2,
          "equity_curve": [...],
          "method": "simulated"
        }
    """
    try:
        from app.services.performance_service import get_real_drawdown
        data = get_real_drawdown(days_back=days_back)
        return JSONResponse(content=data)
    except Exception as e:
        logger.error(f"Drawdown error: {e}", exc_info=True)
        return JSONResponse(content={
            "current_drawdown_pct": 0.0,
            "max_drawdown_pct":     0.0,
            "error": str(e),
        })


# ─────────────────────────────────────────────────────────────────────────────
# BACKTEST ANALYTICS ENDPOINTS (Load from JSON files)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/backtest/stats")
async def get_backtest_stats(
    year: int = Query(None, description="Filter by year (2020-2025)"),
    month: int = Query(None, description="Filter by month (1-12)")
):
    """
    Get backtest performance statistics from JSON analytics files.
    
    Can filter by year and/or month for specific time periods.
    Returns summary stats calculated from backtest CSV data.
    """
    try:
        from pathlib import Path
        import json
        
        # Resolve path to Backtest_result folder
        current_file = Path(__file__).resolve()
        backtest_dir = current_file.parent.parent.parent.parent.parent.parent / "Backtest_result"
        
        logger.info(f"Looking for analytics in: {backtest_dir}")
        
        # Case 1: Year is specified (with or without month filter)
        if year:
            filepath = backtest_dir / f"analytics_{year}.json"
            if not filepath.exists():
                return {
                    "error": f"No analytics data for year {year}",
                    "year": year
                }
            
            with open(filepath, 'r') as f:
                data = json.load(f)
                
                # If month is specified, filter monthly data for that month
                if month:
                    monthly_list = data.get("monthly", [])
                    filtered = [m for m in monthly_list if int(m["month"].split('.')[-1]) == month]
                    if not filtered:
                        return {
                            "error": f"No data found for {year}-{month:02d}",
                            "year": year,
                            "month": month
                        }
                    # Return stats for the single month
                    m = filtered[0]
                    return {
                        "year": year,
                        "month": month,
                        "total_trades": m.get("trades", 0),
                        "total_profit": m.get("pnl", 0),
                        "final_equity": 1000 + m.get("pnl", 0),
                        "return_pct": m.get("return_pct", 0),
                        "win_rate": m.get("win_rate", 0),
                    }
                else:
                    # Return full year summary
                    summary = data.get("summary", {})
                    return {
                        "year": year,
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
        
        # Case 2: No year specified - aggregate data from all years
        # Load all yearly summaries and combine them
        all_summaries = []
        for y in range(2020, 2026):
            filepath = backtest_dir / f"analytics_{y}.json"
            if filepath.exists():
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    summary = data.get("summary", {})
                    if summary:
                        all_summaries.append({
                            "year": y,
                            "summary": summary,
                            "monthly": data.get("monthly", [])
                        })
        
        if not all_summaries:
            return {
                "error": "No analytics data available",
                "total_trades": 0,
                "win_rate": 0,
                "total_profit": 0,
                "final_equity": 0,
                "return_pct": 0,
            }
        
        # If month filter is specified, get data from that month across all years
        if month:
            monthly_data = []
            for summary_data in all_summaries:
                for m in summary_data["monthly"]:
                    m_num = int(m["month"].split('.')[-1])
                    if m_num == month:
                        monthly_data.append(m)
            
            if not monthly_data:
                return {
                    "error": f"No data found for month {month} across all years",
                    "month": month
                }
            
            # Aggregate stats for this month across all years
            total_trades = sum(m.get("trades", 0) for m in monthly_data)
            avg_win_rate = sum(m.get("win_rate", 0) for m in monthly_data) / len(monthly_data) if monthly_data else 0
            total_profit = monthly_data[-1].get("pnl", 0) if monthly_data else 0
            
            # Calculate avg_win and avg_loss from monthly data
            # Note: monthly data doesn't have avg_win/avg_loss directly, need to derive from yearly summaries
            # Calculate winning/losing trades in monthly data
            winning_trades_month = sum(m.get("trades", 0) * m.get("win_rate", 0) / 100 for m in monthly_data)
            losing_trades_month = total_trades - winning_trades_month
            
            # Get avg_win/avg_loss from yearly summaries for this month
            monthly_avg_win = 0
            monthly_avg_loss = 0
            for summary_data in all_summaries:
                for m in summary_data["monthly"]:
                    m_num = int(m["month"].split('.')[-1])
                    if m_num == month:
                        year_summary = summary_data["summary"]
                        if year_summary.get("winning_trades", 0) > 0:
                            monthly_avg_win += year_summary.get("avg_win", 0) * (m.get("trades", 0) * m.get("win_rate", 0) / 100)
                        if year_summary.get("losing_trades", 0) > 0:
                            monthly_avg_loss += year_summary.get("avg_loss", 0) * (m.get("trades", 0) * (1 - m.get("win_rate", 0) / 100))
            
            avg_win = monthly_avg_win / winning_trades_month if winning_trades_month > 0 else 0
            avg_loss = monthly_avg_loss / losing_trades_month if losing_trades_month > 0 else 0
            
            return {
                "month": month,
                "total_trades": total_trades,
                "total_profit": total_profit,
                "final_equity": 1000 + total_profit,
                "return_pct": (total_profit / 10) if total_profit >= 0 else 0,
                "win_rate": avg_win_rate,
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
                "data_points": len(monthly_data)
            }
        
        # Aggregate all yearly summaries (all years, all months)
        total_trades = sum(s["summary"].get("total_trades", 0) for s in all_summaries)
        winning_trades = sum(s["summary"].get("winning_trades", 0) for s in all_summaries)
        losing_trades = sum(s["summary"].get("losing_trades", 0) for s in all_summaries)
        total_profit = sum(s["summary"].get("total_profit", 0) for s in all_summaries)
        avg_win_rate = sum(s["summary"].get("win_rate", 0) for s in all_summaries) / len(all_summaries) if all_summaries else 0
        
        # Calculate avg_win and avg_loss from all years
        total_avg_win = sum(s["summary"].get("avg_win", 0) * s["summary"].get("winning_trades", 0) for s in all_summaries)
        total_avg_loss = sum(s["summary"].get("avg_loss", 0) * s["summary"].get("losing_trades", 0) for s in all_summaries)
        avg_win = total_avg_win / winning_trades if winning_trades > 0 else 0
        avg_loss = total_avg_loss / losing_trades if losing_trades > 0 else 0
        
        # Calculate final equity based on cumulative profit from all years
        initial_capital = 1000
        cumulative_profit = total_profit
        final_equity = initial_capital + cumulative_profit
        return_pct = (cumulative_profit / initial_capital * 100) if initial_capital > 0 else 0
        
        return {
            "period": "all_years",
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": avg_win_rate,
            "total_profit": total_profit,
            "final_equity": final_equity,
            "return_pct": return_pct,
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
        }
    
    except Exception as e:
        logger.error(f"Backtest stats error: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/backtest/monthly")
async def get_backtest_monthly(
    year: int = Query(None, description="Filter by year"),
    month: int = Query(None, description="Filter by month (1-12)")
):
    """
    Get monthly backtest performance data with optional year/month filters.
    
    Returns array of monthly performance metrics from analytics JSON files.
    When no filters: returns data from ALL years (2020-2025)
    When year specified: returns data for that year only
    When month specified: returns data for that month across all years
    """
    try:
        from pathlib import Path
        import json
        
        # Resolve path to Backtest_result folder
        current_file = Path(__file__).resolve()
        backtest_dir = current_file.parent.parent.parent.parent.parent.parent / "Backtest_result"
        
        result = []
        
        # Load all years if no year filter, or specific year if filtered
        years_to_load = [year] if year else range(2020, 2026)
        
        for y in years_to_load:
            filepath = backtest_dir / f"analytics_{y}.json"
            if not filepath.exists():
                continue
            
            with open(filepath, 'r') as f:
                data = json.load(f)
                monthly_list = data.get("monthly", [])
                
                for m in monthly_list:
                    m_num = int(m["month"].split('.')[-1])
                    
                    # Skip if month filter doesn't match
                    if month and m_num != month:
                        continue
                    
                    result.append(m)
        
        # Sort by month name to ensure correct order
        result.sort(key=lambda x: x.get("month", ""))
        
        return result
    
    except Exception as e:
        logger.error(f"Backtest monthly error: {e}", exc_info=True)
        return []


@router.get("/backtest/available-years")
async def get_backtest_available_years(symbol: str = Query("XAUUSD")):
    """
    Get list of available years from backtest CSV files.

    Reads the actual ``Backtest_Results_{symbol}_*.csv`` files in the
    ``Backtest_result`` folder (the ``analytics_*.json`` files are no longer
    generated, so we derive the years directly from the CSVs).
    """
    try:
        from app.services.performance_service import list_available_years

        years = list_available_years(symbol)
        latest_year = max(years) if years else None

        return {
            "years": sorted(years),
            "latest_year": latest_year,
        }

    except Exception as e:
        logger.error(f"Available years error: {e}", exc_info=True)
        return {"years": [], "error": str(e)}


@router.get("/backtest/summary")
async def get_backtest_summary(
    symbol: str = Query("XAUUSD"),
    year: int = Query(None, description="Filter by year"),
):
    """
    Real backtest metrics from Backtest_Summary_{symbol}_*.csv files.

    Returns max_drawdown, profit_factor, win_rate, total_trades — sourced
    from the actual summary CSVs written by the backtest engine.
    """
    try:
        from app.services.performance_service import get_backtest_summary_from_csv

        data = get_backtest_summary_from_csv(symbol, year)
        if not data:
            return {"max_drawdown": 0, "profit_factor": 0, "win_rate": 0,
                    "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
                    "total_profit": 0, "per_year": {}}
        return data

    except Exception as e:
        logger.error(f"Backtest summary error: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/backtest/monthly-trades")
async def get_backtest_monthly_trades(
    symbol: str = Query("XAUUSD"),
    year: int = Query(..., description="Filter by year"),
    month: int = Query(..., description="Filter by month (1-12)"),
):
    """
    Get detailed trade list for a specific year and month from Backtest_Results CSV files.
    """
    try:
        from app.services.performance_service import get_monthly_trades_from_csv

        trades = get_monthly_trades_from_csv(symbol, year, month)
        return {"data": trades, "count": len(trades)}

    except Exception as e:
        logger.error(f"Backtest monthly trades error: {e}", exc_info=True)
        return {"error": str(e), "data": []}


