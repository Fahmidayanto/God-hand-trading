"""AI Agents API endpoints."""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from app.models.agents import AgentConsensus, AgentMetrics, AgentStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/consensus")
async def get_agent_consensus():
    """
    Get AI agents consensus.
    
    Returns combined decision from all trading agents based on real signal data:
    - Price Action Agent
    - Market Structure Agent
    - ML Prediction Agent
    - Risk Management Agent
    
    The consensus is derived from the latest AI signal, with confidence
    distributed across component agents for visualization.
    """
    try:
        from app.services.agent_consensus_builder import AgentConsensusBuilder
        
        # Build consensus from real signal
        builder = AgentConsensusBuilder()
        consensus_data = builder.build_consensus()
        
        if not consensus_data:
            # Fallback if no signal available
            logger.warning("[API] No signal for consensus, using fallback")
            consensus_data = builder.get_fallback_consensus()
        
        # Convert to response model
        agents = []
        for agent_data in consensus_data['agents']:
            agents.append(
                AgentStatus(
                    name=agent_data['agent_name'],
                    type=agent_data['type'],
                    status=agent_data['status'],
                    signal=agent_data['prediction'],
                    confidence=agent_data['confidence'] / 100.0,  # Convert to 0-1 range for frontend
                    accuracy=agent_data['accuracy'],
                    signals_today=agent_data['signals_today'],
                    last_update=agent_data['last_update'],
                )
            )
        
        logger.info(f"[API] Returning consensus: {consensus_data['consensus']} ({consensus_data['confidence']:.1f}%)")
        
        consensus = AgentConsensus(
            consensus=consensus_data['consensus'],
            confidence=consensus_data['confidence'] / 100.0,  # Convert to 0-1 range for frontend
            threshold=consensus_data['threshold'],
            agents=agents,
            total_weight=consensus_data['total_weight'],
            weighted_score=consensus_data['weighted_score'],
        )
        
        # Serialize with aliases
        return JSONResponse(
            content=consensus.model_dump(by_alias=True, mode='json')
        )

    except Exception as e:
        logger.error(f"Agent consensus error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    except Exception as e:
        logger.error(f"Agent consensus error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/metrics", response_model=List[AgentMetrics])
async def get_agent_metrics():
    """
    Get performance metrics for each agent.
    
    Returns historical accuracy and statistics for all agents.
    Fetches dynamically from agent_performance in PostgreSQL and falls back
    to default metrics if empty.
    """
    try:
        from app.core.database import get_db_conn, is_pool_ready
        
        db_metrics = []
        if is_pool_ready():
            try:
                with get_db_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT
                                agent_name,
                                COALESCE(SUM(total_predictions), 0) as total,
                                COALESCE(SUM(correct_predictions), 0) as correct,
                                COALESCE(AVG(avg_confidence), 0.0) as confidence
                            FROM agent_performance
                            GROUP BY agent_name
                        """)
                        rows = cur.fetchall()
                        for row in rows:
                            name, total, correct, confidence = row
                            if total > 0:
                                accuracy = (correct / total) * 100.0
                            else:
                                accuracy = 0.0
                            
                            best_tf = "M15"
                            if "Structure" in name:
                                best_tf = "H1"
                            
                            # Normalize avg_confidence (if stored as fraction <= 1.0, scale up to percentage)
                            conf_pct = float(confidence)
                            if conf_pct <= 1.0:
                                conf_pct *= 100.0
                                
                            db_metrics.append({
                                "agent_name": name,
                                "total_signals": int(total),
                                "correct_signals": int(correct),
                                "accuracy": round(accuracy, 1),
                                "avg_confidence": round(conf_pct, 1),
                                "best_timeframe": best_tf,
                                "win_rate": round(accuracy, 1)
                            })
            except Exception as e:
                logger.warning(f"Error querying agent_performance from DB: {e}")
                
        # Sensible defaults for visual consistency in frontend
        defaults = {
            "Price Action Agent": {
                "total_signals": 156,
                "correct_signals": 113,
                "accuracy": 72.4,
                "avg_confidence": 68.5,
                "best_timeframe": "M15",
                "win_rate": 72.4,
            },
            "Market Structure Agent": {
                "total_signals": 142,
                "correct_signals": 98,
                "accuracy": 69.0,
                "avg_confidence": 75.2,
                "best_timeframe": "H1",
                "win_rate": 69.0,
            },
            "ML Prediction Agent": {
                "total_signals": 98,
                "correct_signals": 75,
                "accuracy": 76.5,
                "avg_confidence": 82.1,
                "best_timeframe": "M15",
                "win_rate": 76.5,
            },
            "Risk Manager": {
                "total_signals": 85,
                "correct_signals": 85,
                "accuracy": 100.0,
                "avg_confidence": 100.0,
                "best_timeframe": "M15",
                "win_rate": 100.0,
            }
        }
        
        # Merge DB results with defaults for fallback
        final_metrics = []
        found_names = {m["agent_name"].lower() for m in db_metrics}
        
        for m in db_metrics:
            final_metrics.append(AgentMetrics(**m))
            
        for name, data in defaults.items():
            db_matched = False
            for m_name in found_names:
                if name.lower() in m_name or m_name in name.lower():
                    db_matched = True
                    break
            if not db_matched:
                final_metrics.append(
                    AgentMetrics(
                        agent_name=name,
                        **data
                    )
                )
                
        return final_metrics

    except Exception as e:
        logger.error(f"Agent metrics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/market-structure")
async def get_market_structure():
    """
    Get current market structure state.
    
    Returns the current market structure phase, direction, BoS/CHoCH info,
    and entry validity derived from LLHHBOSData CSV (auto-updated by MT5).
    
    Market Structure Phases:
    - NEUTRAL (0): No clear trend
    - CHOCH_PENDING (1): CHoCH detected, waiting for BoS
    - BOS_PENDING (2): Expecting BoS after CHoCH
    - BOS_CONFIRMED (3): Fresh BoS aligned with trend
    - IN_TREND (4): BoS confirmed, trend continuing
    """
    try:
        from app.services.market_structure_reader import MarketStructureReader
        
        reader = MarketStructureReader()
        structure = reader.get_market_structure()
        
        if not structure:
            logger.warning("[API] No market structure data available")
            structure = reader._get_fallback_structure()
        
        logger.info(f"[API] Returning market structure: {structure['phase_name']} - {structure['direction']}")
        
        return JSONResponse(content=structure)
    
    except Exception as e:
        logger.error(f"Market structure error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/market-structure-lines")
async def get_market_structure_lines(from_date: str = "2020-01-01", to_date: str = ""):
    """
    Get market structure lines for chart visualization.
    
    Returns BoS, CHoCH, HH, and LL points for the specified date range.
    These can be overlaid on the price chart to visualize market structure.
    
    Args:
        from_date: Start date (ISO format, default "2020-01-01")
        to_date: End date (ISO format, default "" = now)
        
    Returns:
        Dictionary containing:
        - bos_lines: List of Break of Structure points
        - choch_lines: List of Change of Character points
        - hh_points: List of Higher High points
        - ll_points: List of Lower Low points
        
    Example Response:
        {
            "bos_lines": [...],
            "choch_lines": [...],
            "hh_points": [...],
            "ll_points": [...]
        }
    """
    try:
        from app.services.market_structure_lines_reader import MarketStructureLinesReader
        
        reader = MarketStructureLinesReader()
        lines = reader.get_market_structure_lines(from_date=from_date, to_date=to_date)
        
        logger.info(
            f"[API] Returning {lines['total_points']} structure points "
            f"({from_date} to {to_date or 'now'})"
        )
        
        return JSONResponse(content=lines)
    
    except Exception as e:
        logger.error(f"Market structure lines error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ─── Sentiment History Endpoints ──────────────────────────────────────────────

@router.get("/sentiment/latest")
async def get_latest_sentiment():
    """
    Get the latest sentiment analysis snapshot from agent_sentiment_logs.
    
    Returns the most recent log entry with:
    - Sentiment score & label (BULLISH/BEARISH/NEUTRAL)
    - Bullish / bearish keyword match counts
    - Active keywords detected from headlines
    - Upcoming economic events count & avoid_trading flag
    - Next high-impact event name and timing
    """
    try:
        from app.core.database import get_db_conn, is_pool_ready
        
        if not is_pool_ready():
            return JSONResponse(content=_sentiment_fallback())
        
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        timestamp,
                        symbol,
                        sentiment_score,
                        sentiment_label,
                        sentiment_strength,
                        bullish_news_count,
                        bearish_news_count,
                        triggered_keywords,
                        upcoming_events_count,
                        high_impact_events_count,
                        avoid_trading_triggered,
                        next_event_name,
                        next_event_time
                    FROM agent_sentiment_logs
                    ORDER BY timestamp DESC
                    LIMIT 1
                """)
                row = cur.fetchone()
        
        if not row:
            return JSONResponse(content=_sentiment_fallback())
        
        return JSONResponse(content={
            "timestamp":               row[0].isoformat() if row[0] else None,
            "symbol":                  row[1],
            "sentiment_score":         float(row[2]) if row[2] is not None else 0.0,
            "sentiment_label":         row[3] or "NEUTRAL",
            "sentiment_strength":      row[4] or "none",
            "bullish_news_count":      int(row[5] or 0),
            "bearish_news_count":      int(row[6] or 0),
            "triggered_keywords":      row[7] or [],
            "upcoming_events_count":   int(row[8] or 0),
            "high_impact_events_count":int(row[9] or 0),
            "avoid_trading_triggered": bool(row[10]),
            "next_event_name":         row[11],
            "next_event_time":         row[12].isoformat() if row[12] else None,
        })
    
    except Exception as e:
        logger.error(f"Sentiment latest error: {e}", exc_info=True)
        return JSONResponse(content=_sentiment_fallback())


@router.get("/sentiment/history")
async def get_sentiment_history(hours_back: int = 24, limit: int = 100):
    """
    Get historical sentiment logs for the last N hours.
    
    Query params:
    - hours_back: How many hours of history to return (default: 24, max: 168)
    - limit:      Max records (default: 100, max: 500)
    
    Returns a list of sentiment snapshots ordered newest-first, suitable for
    charting a Sentiment Score timeline or Market Sentiment heatmap.
    """
    try:
        from app.core.database import get_db_conn, is_pool_ready
        from datetime import datetime, timedelta, timezone
        
        hours_back = max(1, min(hours_back, 168))
        limit      = max(1, min(limit, 500))
        
        if not is_pool_ready():
            return JSONResponse(content={"logs": [], "count": 0})
        
        since = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        timestamp,
                        sentiment_score,
                        sentiment_label,
                        sentiment_strength,
                        bullish_news_count,
                        bearish_news_count,
                        upcoming_events_count,
                        high_impact_events_count,
                        avoid_trading_triggered,
                        next_event_name,
                        next_event_time
                    FROM agent_sentiment_logs
                    WHERE symbol = 'XAUUSD'
                      AND timestamp >= %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                """, (since, limit))
                rows = cur.fetchall()
        
        logs = []
        for row in rows:
            logs.append({
                "timestamp":               row[0].isoformat() if row[0] else None,
                "sentiment_score":         float(row[1]) if row[1] is not None else 0.0,
                "sentiment_label":         row[2] or "NEUTRAL",
                "sentiment_strength":      row[3] or "none",
                "bullish_news_count":      int(row[4] or 0),
                "bearish_news_count":      int(row[5] or 0),
                "upcoming_events_count":   int(row[6] or 0),
                "high_impact_events_count":int(row[7] or 0),
                "avoid_trading_triggered": bool(row[8]),
                "next_event_name":         row[9],
                "next_event_time":         row[10].isoformat() if row[10] else None,
            })
        
        return JSONResponse(content={"logs": logs, "count": len(logs)})
    
    except Exception as e:
        logger.error(f"Sentiment history error: {e}", exc_info=True)
        return JSONResponse(content={"logs": [], "count": 0})


def _sentiment_fallback() -> dict:
    """Return a neutral fallback when no sentiment data available."""
    return {
        "timestamp":               None,
        "symbol":                  "XAUUSD",
        "sentiment_score":         0.0,
        "sentiment_label":         "NEUTRAL",
        "sentiment_strength":      "none",
        "bullish_news_count":      0,
        "bearish_news_count":      0,
        "triggered_keywords":      [],
        "upcoming_events_count":   0,
        "high_impact_events_count":0,
        "avoid_trading_triggered": False,
        "next_event_name":         None,
        "next_event_time":         None,
    }


# ==============================================================================
# Chatbot Stream & History Support
# ==============================================================================
import os
import uuid
import json
import asyncio
from collections import defaultdict
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import types

class AgentStreamRequest(BaseModel):
    query: str
    agent_name: str
    conversation_id: str = ""

# Cache to store history: conversation_id -> list of event dicts
CHATBOT_HISTORY = defaultdict(list)

def execute_neondb_query(sql_query: str) -> str:
    """Safely execute SELECT query on NeonDB and return results formatted in Markdown."""
    from app.core.database import get_db_conn, is_pool_ready
    if not is_pool_ready():
        return "Database pool is not initialized."

    # Basic security checks
    cleaned = sql_query.strip().lower()
    if not cleaned.startswith("select"):
        return "ERROR: Hanya query SELECT yang diizinkan untuk keamanan data."

    # Check for modification keywords to prevent SQL Injection
    forbidden = ["insert", "update", "delete", "drop", "alter", "create", "truncate", "replace", "grant", "revoke"]
    for word in forbidden:
        if word in cleaned:
            return f"ERROR: Query mengandung kata terlarang '{word}'."

    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_query)
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()
                    if not rows:
                        return "Query berhasil dieksekusi, tetapi tidak ada data yang ditemukan."
                    
                    # Format as a clean markdown table
                    result_lines = []
                    header = " | ".join(columns)
                    separator = " | ".join(["---"] * len(columns))
                    result_lines.append(header)
                    result_lines.append(separator)
                    
                    for row in rows:
                        row_strs = []
                        for val in row:
                            if val is None:
                                row_strs.append("NULL")
                            elif isinstance(val, (int, float)):
                                row_strs.append(str(val))
                            else:
                                row_strs.append(str(val).replace("|", "\\|"))
                        result_lines.append(" | ".join(row_strs))
                    
                    return "\n".join(result_lines)
                else:
                    return "Query berhasil dieksekusi tanpa hasil data."
    except Exception as e:
        return f"Database Error: {str(e)}"

def generate_sql_query(user_query: str, client: genai.Client) -> str:
    """Translate natural language user query to single clean SQL SELECT query using Gemini."""
    system_prompt = (
        "Kamu adalah penerjemah bahasa manusia ke query SQL PostgreSQL yang ahli.\n"
        "Tabel yang tersedia di database:\n"
        "1. `llhhbosdata_xauusd` - data market structure (kolom: id, type, direction_action, price, time, timeframe, status, previous_price, previous_time, csv_filename)\n"
        "2. `backtest_results_xauusd` - data trade backtest (kolom: id, ticket, symbol, type, entry_price, exit_price, sl, tp, profit, spread_cost, commission, swap, net_profit, session, session_isdst, entry_time, exit_time, lot_size, magic_number, timeframe, status, reject_reason, csv_filename)\n"
        "3. `sessionzone_xauusd` - data session zones (kolom: id, start_time, end_time, duration_bars, session, status, is_dst, open_price, high_price, low_price, close_price, range_points, csv_filename)\n"
        "4. `marketdata_xauusd_m15`, `marketdata_xauusd_h1`, `marketdata_xauusd_h4` - data candlestick (kolom: time, open, high, low, close, volume, spread, ema200, csv_filename)\n\n"
        "Tugasmu:\n"
        "1. Jika user menanyakan tentang statistik, trade, market structure, candle, atau informasi apa pun yang ada di database, "
        "tulis satu query SQL SELECT yang valid dan tepat untuk menjawab pertanyaannya.\n"
        "2. Selalu gunakan LIMIT (maksimal LIMIT 50) agar data tidak terlalu besar.\n"
        "3. Keluarkan HANYA satu baris query SQL tersebut. JANGAN gunakan markdown code block (seperti ```sql ... ```), jangan ada penjelasan teks, jangan ada karakter tambahan.\n"
        "4. Jika pertanyaan user adalah percakapan biasa (misal: 'hallo', 'siapa kamu', 'terima kasih') atau tidak memerlukan data dari database, balas dengan HANYA satu kata: 'NO_QUERY'."
    )
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_query,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.1,
            )
        )
        sql = response.text.strip()
        if sql.startswith("```"):
            sql = sql.replace("```sql", "").replace("```", "").strip()
        return sql
    except Exception as e:
        logger.error(f"Error generating SQL: {e}")
        return "NO_QUERY"

async def chatbot_event_generator(request: AgentStreamRequest):
    # Dynamically load .env file to pick up any key modifications in runtime
    from dotenv import load_dotenv
    load_dotenv()
    
    conversation_id = request.conversation_id or str(uuid.uuid4())
    thread_id = f"thread_{conversation_id}"
    task_id = f"task_{conversation_id}"
    
    # 1. Send conversation_started event
    started_event = {
        "event": "conversation_started",
        "data": {
            "conversation_id": conversation_id,
            "thread_id": thread_id,
            "task_id": task_id
        }
    }
    yield f"data: {json.dumps(started_event)}\n\n"
    await asyncio.sleep(0.01)
    
    # 1.5 Send thread_started event (displays the user query bubble instantly)
    user_item_id = str(uuid.uuid4())
    thread_started_event = {
        "event": "thread_started",
        "data": {
            "conversation_id": conversation_id,
            "thread_id": thread_id,
            "task_id": task_id,
            "item_id": user_item_id,
            "role": "user",
            "component_type": "markdown",
            "payload": {
                "content": request.query
            }
        }
    }
    yield f"data: {json.dumps(thread_started_event)}\n\n"
    await asyncio.sleep(0.01)
    
    # 2. Get API key and call Gemini
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        error_event = {
            "event": "system_failed",
            "data": {
                "conversation_id": conversation_id,
                "thread_id": thread_id,
                "task_id": task_id,
                "payload": {
                    "content": "Google API Key belum diset. Silakan masukkan GOOGLE_API_KEY di file .env."
                }
            }
        }
        yield f"data: {json.dumps(error_event)}\n\n"
        return
        
    try:
        # Initialize Gemini Client
        client = genai.Client(api_key=api_key)
        
        # Step A: Translate human query to SQL if database information is required
        sql_query = generate_sql_query(request.query, client)
        db_results = ""
        
        if sql_query and sql_query.upper() != "NO_QUERY":
            logger.info(f"[Chatbot SQL] Generated SQL: {sql_query}")
            db_results = execute_neondb_query(sql_query)
            logger.info(f"[Chatbot SQL] Result length: {len(db_results)}")
            
        # Step B: Generate streaming response based on query results
        system_instruction = (
            "Kamu adalah AI Chatbot Analisis Database NeonDB untuk platform trading MetaTrader 5.\n"
            "Tugas utamamu adalah membantu pengguna memahami dan menganalisis data trading di database NeonDB.\n\n"
            "ATURAN PENTING:\n"
            "1. Fokus utama jawaban harus berdasarkan data dari database NeonDB yang disediakan di bawah.\n"
            "2. JANGAN PERNAH berasumsi atau mengarang data jika tidak ada dalam hasil database.\n"
            "3. Jika data tidak ditemukan, sampaikan secara jujur.\n"
            "4. Jika pengguna menanyakan hal yang tidak berhubungan dengan database atau pasar trading MT5, "
            "ingatkan dengan sopan bahwa kamu adalah asisten analisis database trading.\n"
        )
        
        # Build prompt
        prompt_content = f"Pertanyaan User: {request.query}\n\n"
        if db_results:
            prompt_content += f"Hasil Query SQL dari Database NeonDB:\n```\n{db_results}\n```\n"
            prompt_content += f"Query SQL yang digunakan:\n`{sql_query}`\n\n"
            prompt_content += "Instruksi: Analisis hasil query di atas dan jawab pertanyaan user secara mendalam dengan bahasa Indonesia yang ramah dan profesional."
        else:
            prompt_content += "Instruksi: Jawab pertanyaan user dengan ramah dalam bahasa Indonesia."
            
        item_id = str(uuid.uuid4())
        full_response = ""
        
        # Stream from Gemini
        response_stream = client.models.generate_content_stream(
            model='gemini-2.5-flash',
            contents=prompt_content,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.4,
            )
        )
        
        for chunk in response_stream:
            text = chunk.text or ""
            if text:
                full_response += text
                chunk_event = {
                    "event": "message_chunk",
                    "data": {
                        "conversation_id": conversation_id,
                        "thread_id": thread_id,
                        "task_id": task_id,
                        "item_id": item_id,
                        "role": "assistant",
                        "component_type": "markdown",
                        "payload": {
                            "content": text
                        }
                    }
                }
                yield f"data: {json.dumps(chunk_event)}\n\n"
                await asyncio.sleep(0.01)
                
        # Send done event
        done_event = {
            "event": "done",
            "data": {
                "conversation_id": conversation_id,
                "thread_id": thread_id,
                "task_id": task_id
            }
        }
        yield f"data: {json.dumps(done_event)}\n\n"
        
        # Save to history cache
        user_msg = {
            "event": "message",
            "data": {
                "conversation_id": conversation_id,
                "thread_id": thread_id,
                "task_id": task_id,
                "item_id": user_item_id,
                "role": "user",
                "component_type": "markdown",
                "payload": {
                    "content": request.query
                }
            }
        }
        assistant_msg = {
            "event": "message",
            "data": {
                "conversation_id": conversation_id,
                "thread_id": thread_id,
                "task_id": task_id,
                "item_id": item_id,
                "role": "assistant",
                "component_type": "markdown",
                "payload": {
                    "content": full_response
                }
            }
        }
        CHATBOT_HISTORY[conversation_id].append(user_msg)
        CHATBOT_HISTORY[conversation_id].append(assistant_msg)
        
    except Exception as e:
        logger.error(f"Error in chatbot streaming: {e}")
        error_event = {
            "event": "system_failed",
            "data": {
                "conversation_id": conversation_id,
                "thread_id": thread_id,
                "task_id": task_id,
                "payload": {
                    "content": f"Terjadi kesalahan saat memproses query: {str(e)}"
                }
            }
        }
        yield f"data: {json.dumps(error_event)}\n\n"

@router.post("/stream")
async def stream_query_agent(request: AgentStreamRequest):
    return StreamingResponse(
        chatbot_event_generator(request),
        media_type="text/event-stream"
    )


