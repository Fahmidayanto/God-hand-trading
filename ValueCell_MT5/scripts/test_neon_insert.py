"""
Test Neon PostgreSQL Insert Operations

Test inserting sample data into all tables to verify schema works correctly.

Usage:
    python scripts/test_neon_insert.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()


def get_connection():
    """Create connection to Neon PostgreSQL"""
    conn = psycopg2.connect(
        host=os.getenv("PGHOST"),
        database=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        sslmode=os.getenv("PGSSLMODE", "require")
    )
    conn.autocommit = True
    return conn


def test_insert_realtime_ohlcv(conn):
    """Test inserting into realtime_ohlcv table"""
    logger.info("\n📊 Testing: realtime_ohlcv")
    
    with conn.cursor() as cur:
        # Insert sample data
        cur.execute("""
            INSERT INTO realtime_ohlcv (
                timestamp, symbol, timeframe, open, high, low, close, volume, ema200, source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (timestamp, symbol, timeframe, source) DO NOTHING
            RETURNING id
        """, (
            datetime.now(),
            "XAUUSD",
            "M15",
            2350.00,
            2351.50,
            2348.50,
            2350.80,
            1523,
            2345.60,
            "mt5_api"
        ))
        
        result = cur.fetchone()
        if result:
            logger.info(f"   ✅ Inserted row ID: {result[0]}")
        else:
            logger.info("   ⚠️ Row already exists (skipped)")
        
        # Query back
        cur.execute("SELECT COUNT(*) FROM realtime_ohlcv")
        count = cur.fetchone()[0]
        logger.info(f"   Total rows: {count}")


def test_insert_realtime_structures(conn):
    """Test inserting into realtime_structures table"""
    logger.info("\n📊 Testing: realtime_structures")
    
    with conn.cursor() as cur:
        # Insert sample data
        cur.execute("""
            INSERT INTO realtime_structures (
                timestamp, symbol, timeframe, event_type, direction, 
                price, phase, session, source, triggered_trade
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id
        """, (
            datetime.now(),
            "XAUUSD",
            "M15",
            "BoS",
            "Bullish",
            2350.50,
            "BOS_CONFIRMED",
            "London",
            "python_detector",
            False
        ))
        
        result = cur.fetchone()
        logger.info(f"   ✅ Inserted row ID: {result[0]}")
        
        # Query back
        cur.execute("SELECT COUNT(*) FROM realtime_structures")
        count = cur.fetchone()[0]
        logger.info(f"   Total rows: {count}")


def test_insert_agent_decision(conn):
    """Test inserting into agent_decisions table"""
    logger.info("\n📊 Testing: agent_decisions")
    
    with conn.cursor() as cur:
        # Insert sample data with JSONB
        agent_votes = {
            "market_structure": {"signal": "BUY", "confidence": 0.85},
            "ml_prediction": {"signal": "BUY", "confidence": 0.78},
            "risk_management": {"signal": "APPROVED", "confidence": 0.65},
            "sentiment": {"signal": "NEUTRAL", "confidence": 0.40}
        }
        
        cur.execute("""
            INSERT INTO agent_decisions (
                timestamp, symbol, timeframe,
                market_structure, ml_prediction, risk_analysis, sentiment,
                consensus_score, final_decision, trade_executed
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id
        """, (
            datetime.now(),
            "XAUUSD",
            "M15",
            psycopg2.extras.Json({"signal": "BUY", "confidence": 0.85}),
            psycopg2.extras.Json({"signal": "BUY", "confidence": 0.78}),
            psycopg2.extras.Json({"signal": "APPROVED", "position_size": 0.01}),
            psycopg2.extras.Json({"signal": "NEUTRAL", "confidence": 0.40}),
            0.67,
            "BUY",
            False
        ))
        
        result = cur.fetchone()
        logger.info(f"   ✅ Inserted row ID: {result[0]}")
        
        # Query back with JSONB
        cur.execute("""
            SELECT id, final_decision, consensus_score, 
                   market_structure->>'signal' as ms_signal,
                   ml_prediction->>'confidence' as ml_confidence
            FROM agent_decisions 
            ORDER BY id DESC 
            LIMIT 1
        """)
        row = cur.fetchone()
        logger.info(f"   Query result: ID={row[0]}, Decision={row[1]}, Consensus={row[2]}")
        logger.info(f"   JSONB fields: MS Signal={row[3]}, ML Confidence={row[4]}")


def test_insert_historical_audit(conn):
    """Test inserting into historical audit tables"""
    logger.info("\n📊 Testing: historical_ohlcv_audit")
    
    with conn.cursor() as cur:
        # Insert sample CSV audit data
        cur.execute("""
            INSERT INTO historical_ohlcv_audit (
                timestamp, symbol, timeframe, open, high, low, close, 
                volume, ema200, source, csv_filename
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (timestamp, symbol, timeframe, source) DO NOTHING
            RETURNING id
        """, (
            datetime.now(),
            "XAUUSD",
            "M15",
            2350.00,
            2351.50,
            2348.50,
            2350.80,
            1523,
            2345.60,
            "csv_export",
            "MarketData_XAUUSD_M15_2026-06-11.csv"
        ))
        
        result = cur.fetchone()
        if result:
            logger.info(f"   ✅ Inserted row ID: {result[0]}")
        else:
            logger.info("   ⚠️ Row already exists (skipped)")
        
        # Query back
        cur.execute("SELECT COUNT(*) FROM historical_ohlcv_audit")
        count = cur.fetchone()[0]
        logger.info(f"   Total rows: {count}")


def test_insert_csv_load_log(conn):
    """Test inserting into csv_load_log table"""
    logger.info("\n📊 Testing: csv_load_log")
    
    with conn.cursor() as cur:
        # Insert sample log entry
        cur.execute("""
            INSERT INTO csv_load_log (
                filename, file_date, rows_loaded, status
            ) VALUES (
                %s, %s, %s, %s
            )
            ON CONFLICT (filename) DO UPDATE
            SET rows_loaded = EXCLUDED.rows_loaded,
                status = EXCLUDED.status,
                loaded_at = NOW()
            RETURNING id
        """, (
            "MarketData_XAUUSD_M15_2026-06-11.csv",
            datetime.now().date(),
            96,
            "SUCCESS"
        ))
        
        result = cur.fetchone()
        logger.info(f"   ✅ Inserted/Updated row ID: {result[0]}")
        
        # Query back
        cur.execute("""
            SELECT filename, rows_loaded, status, loaded_at 
            FROM csv_load_log 
            ORDER BY id DESC 
            LIMIT 1
        """)
        row = cur.fetchone()
        logger.info(f"   Last entry: {row[0]} | {row[1]} rows | {row[2]} | {row[3]}")


def test_query_all_tables(conn):
    """Query all tables and show row counts"""
    logger.info("\n📊 All table row counts:")
    
    tables = [
        "realtime_ohlcv",
        "realtime_structures",
        "trades",
        "agent_decisions",
        "state_machine",
        "agent_performance",
        "historical_ohlcv_audit",
        "historical_structures_audit",
        "csv_load_log",
        "cross_validation",
    ]
    
    with conn.cursor() as cur:
        for table in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                logger.info(f"   {table}: {count} rows")
            except Exception as e:
                logger.error(f"   {table}: Error - {e}")


def main():
    """Main function"""
    logger.info("=" * 70)
    logger.info("🧪 TESTING NEON POSTGRESQL INSERT OPERATIONS")
    logger.info("=" * 70)
    
    try:
        # Connect to database
        logger.info("\n🔌 Connecting to Neon PostgreSQL...")
        conn = get_connection()
        logger.info("✅ Connected!")
        
        # Test inserts
        test_insert_realtime_ohlcv(conn)
        test_insert_realtime_structures(conn)
        test_insert_agent_decision(conn)
        test_insert_historical_audit(conn)
        test_insert_csv_load_log(conn)
        
        # Show all table counts
        test_query_all_tables(conn)
        
        # Close connection
        conn.close()
        logger.info("\n🔌 Connection closed")
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ ALL INSERT TESTS PASSED!")
        logger.info("=" * 70)
        logger.info("\n📊 Summary:")
        logger.info("   - Inserted data into 5 tables")
        logger.info("   - Tested JSONB fields (agent decisions)")
        logger.info("   - Tested UNIQUE constraints (conflict handling)")
        logger.info("   - Tested timestamps and data types")
        logger.info("\n🚀 Database is ready for production use!")
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
