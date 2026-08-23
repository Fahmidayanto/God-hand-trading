"""
Create Neon PostgreSQL Schema for Multi-Agent Trading System

This script creates all required tables for both tracks:
- Track 1: Real-time tables (from MT5 Python API)
- Track 2: Audit tables (from CSV batch load)

Usage:
    python scripts/create_neon_schema.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()


def get_connection():
    """Create connection to Neon PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("PGHOST"),
            database=os.getenv("PGDATABASE"),
            user=os.getenv("PGUSER"),
            password=os.getenv("PGPASSWORD"),
            sslmode=os.getenv("PGSSLMODE", "require")
        )
        conn.autocommit = True
        logger.info("✅ Connected to Neon PostgreSQL")
        return conn
    except Exception as e:
        logger.error(f"❌ Failed to connect to Neon PostgreSQL: {e}")
        raise


def create_schema(conn):
    """Create all tables for dual-track system"""
    
    with conn.cursor() as cur:
        logger.info("🔧 Dropping existing tables to perform clean rebuild...")
        tables_to_drop = [
            "realtime_ohlcv", "realtime_structures", "trades", "agent_decisions",
            "state_machine", "agent_performance", "agent_sentiment_logs", "historical_ohlcv_audit",
            "historical_structures_audit", "csv_load_log", "cross_validation",
            "llhhbosdata_xauusd", "backtest_results_xauusd", "marketdata_xauusd_m15",
            "marketdata_xauusd_h1", "marketdata_xauusd_h4", "sessionzone_xauusd"
        ]
        for table in tables_to_drop:
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        logger.info("✅ Dropped existing tables.")

        # ========== TRACK 1: REAL-TIME TABLES (from MT5 Python API) ==========
        logger.info("\n📊 TRACK 1: Creating real-time tables...")
        
        # 1. Real-time OHLCV data
        logger.info("   Creating table: realtime_ohlcv")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS realtime_ohlcv (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                timeframe VARCHAR(10) NOT NULL,
                open DECIMAL(10, 2),
                high DECIMAL(10, 2),
                low DECIMAL(10, 2),
                close DECIMAL(10, 2),
                volume BIGINT,
                ema200 DECIMAL(10, 2),
                source VARCHAR(20) DEFAULT 'mt5_api',
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(timestamp, symbol, timeframe, source)
            )
        """)
        
        # 2. Real-time structure events
        logger.info("   Creating table: realtime_structures")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS realtime_structures (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                timeframe VARCHAR(10) NOT NULL,
                event_type VARCHAR(20),
                direction VARCHAR(10),
                price DECIMAL(10, 2),
                phase VARCHAR(50),
                session VARCHAR(20),
                source VARCHAR(20) DEFAULT 'python_detector',
                triggered_trade BOOLEAN DEFAULT FALSE,
                processed BOOLEAN DEFAULT FALSE,
                processed_at TIMESTAMP,
                cycle_number BIGINT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # 3. Trades table
        logger.info("   Creating table: trades")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                ticket BIGINT PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                type VARCHAR(10) NOT NULL,
                entry_price DECIMAL(10, 2),
                stop_loss DECIMAL(10, 2),
                take_profit DECIMAL(10, 2),
                lot_size DECIMAL(10, 2),
                consensus_score DECIMAL(5, 4),
                agent_votes JSONB,
                close_time TIMESTAMP,
                close_price DECIMAL(10, 2),
                profit DECIMAL(10, 2),
                outcome VARCHAR(20)
            )
        """)
        
        # 4. Agent decisions table
        logger.info("   Creating table: agent_decisions")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_decisions (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                timeframe VARCHAR(10) NOT NULL,
                market_structure JSONB,
                ml_prediction JSONB,
                risk_analysis JSONB,
                sentiment JSONB,
                consensus_score DECIMAL(5, 4),
                final_decision VARCHAR(20),
                trade_executed BOOLEAN,
                ticket BIGINT,
                error TEXT
            )
        """)
        
        # 5. State machine table
        logger.info("   Creating table: state_machine")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS state_machine (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                timeframe VARCHAR(10) NOT NULL,
                phase VARCHAR(50),
                last_hh DECIMAL(10, 2),
                last_ll DECIMAL(10, 2),
                choch_detected BOOLEAN,
                bos_detected BOOLEAN,
                metadata JSONB
            )
        """)
        
        # 6. Agent performance table
        logger.info("   Creating table: agent_performance")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_performance (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                agent_name VARCHAR(50) NOT NULL,
                correct_predictions INT DEFAULT 0,
                total_predictions INT DEFAULT 0,
                accuracy DECIMAL(5, 4),
                avg_confidence DECIMAL(5, 4),
                UNIQUE(date, agent_name)
            )
        """)
        
        # 6b. Agent sentiment logs table
        logger.info("   Creating table: agent_sentiment_logs")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_sentiment_logs (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                symbol VARCHAR(10) DEFAULT 'XAUUSD',
                sentiment_score REAL NOT NULL,
                sentiment_label VARCHAR(15) NOT NULL,
                sentiment_strength VARCHAR(15),
                bullish_news_count INT DEFAULT 0,
                bearish_news_count INT DEFAULT 0,
                triggered_keywords TEXT[],
                upcoming_events_count INT DEFAULT 0,
                high_impact_events_count INT DEFAULT 0,
                avoid_trading_triggered BOOLEAN DEFAULT FALSE,
                next_event_name VARCHAR(150),
                next_event_time TIMESTAMP WITH TIME ZONE
            )
        """)
        
        # Create index on timestamp for sentiment logs
        cur.execute("CREATE INDEX IF NOT EXISTS idx_agent_sentiment_logs_time ON agent_sentiment_logs(timestamp DESC)")
        
        logger.info("✅ Track 1 tables created (7 tables)")
        
        # ========== TRACK 2: AUDIT TABLES (from CSV batch load) ==========
        logger.info("\n📁 TRACK 2: Creating audit tables...")
        
        # 7. LLHHBOSData
        logger.info("   Creating table: llhhbosdata_xauusd")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS llhhbosdata_xauusd (
                id SERIAL PRIMARY KEY,
                type VARCHAR(20) NOT NULL,
                direction_action VARCHAR(50),
                price DECIMAL(10, 2),
                time TIMESTAMP NOT NULL,
                timeframe VARCHAR(10) NOT NULL,
                status VARCHAR(20),
                previous_price DECIMAL(10, 2),
                previous_time TIMESTAMP,
                csv_filename VARCHAR(255),
                loaded_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(time, timeframe, type, price)
            )
        """)
        
        # 8. Backtest Results
        logger.info("   Creating table: backtest_results_xauusd")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS backtest_results_xauusd (
                id SERIAL PRIMARY KEY,
                ticket BIGINT,
                symbol VARCHAR(10) NOT NULL,
                type VARCHAR(10) NOT NULL,
                entry_structure VARCHAR(255),
                close_type VARCHAR(255),
                entry_price DECIMAL(10, 2),
                exit_price DECIMAL(10, 2),
                sl DECIMAL(10, 2),
                tp DECIMAL(10, 2),
                profit DECIMAL(10, 2),
                spread_cost DECIMAL(10, 2),
                commission DECIMAL(10, 2),
                swap DECIMAL(10, 2),
                net_profit DECIMAL(10, 2),
                session VARCHAR(50),
                session_isdst VARCHAR(10),
                entry_time TIMESTAMP NOT NULL,
                exit_time TIMESTAMP,
                lot_size DECIMAL(10, 2),
                magic_number INT,
                timeframe VARCHAR(10) NOT NULL,
                status VARCHAR(20),
                reject_reason VARCHAR(255),
                body_ratio DECIMAL(5, 2),
                body_ratio_min DECIMAL(5, 2),
                body_ratio_passed VARCHAR(10),
                body_ratio_mode VARCHAR(255),
                initial_sl DECIMAL(10, 2),
                initial_tp DECIMAL(10, 2),
                final_sl DECIMAL(10, 2),
                final_tp DECIMAL(10, 2),
                initial_risk_points INT,
                initial_reward_points INT,
                final_risk_points INT,
                final_reward_points INT,
                trailing_modified VARCHAR(10),
                trailing_count INT,
                tp_expanded VARCHAR(10),
                tp_expand_count INT,
                max_favorable_points INT,
                max_adverse_points INT,
                close_reason VARCHAR(255),
                csv_filename VARCHAR(255),
                loaded_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(entry_time, ticket, type)
            )
        """)

        # 9. MarketData M15
        logger.info("   Creating table: marketdata_xauusd_m15")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS marketdata_xauusd_m15 (
                id SERIAL PRIMARY KEY,
                time TIMESTAMP NOT NULL,
                open DECIMAL(10, 2),
                high DECIMAL(10, 2),
                low DECIMAL(10, 2),
                close DECIMAL(10, 2),
                volume BIGINT,
                spread INT,
                ema200 DECIMAL(10, 2),
                csv_filename VARCHAR(255),
                loaded_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(time)
            )
        """)

        # 10. MarketData H1
        logger.info("   Creating table: marketdata_xauusd_h1")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS marketdata_xauusd_h1 (
                id SERIAL PRIMARY KEY,
                time TIMESTAMP NOT NULL,
                open DECIMAL(10, 2),
                high DECIMAL(10, 2),
                low DECIMAL(10, 2),
                close DECIMAL(10, 2),
                volume BIGINT,
                spread INT,
                ema200 DECIMAL(10, 2),
                csv_filename VARCHAR(255),
                loaded_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(time)
            )
        """)

        # 11. MarketData H4
        logger.info("   Creating table: marketdata_xauusd_h4")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS marketdata_xauusd_h4 (
                id SERIAL PRIMARY KEY,
                time TIMESTAMP NOT NULL,
                open DECIMAL(10, 2),
                high DECIMAL(10, 2),
                low DECIMAL(10, 2),
                close DECIMAL(10, 2),
                volume BIGINT,
                spread INT,
                ema200 DECIMAL(10, 2),
                csv_filename VARCHAR(255),
                loaded_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(time)
            )
        """)

        # 12. SessionZone
        logger.info("   Creating table: sessionzone_xauusd")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessionzone_xauusd (
                id SERIAL PRIMARY KEY,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                duration_bars INT,
                session VARCHAR(50),
                status VARCHAR(20),
                is_dst VARCHAR(10),
                open_price DECIMAL(10, 2),
                high_price DECIMAL(10, 2),
                low_price DECIMAL(10, 2),
                close_price DECIMAL(10, 2),
                range_points INT,
                csv_filename VARCHAR(255),
                loaded_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(start_time, session)
            )
        """)
        
        # 13. CSV load tracking
        logger.info("   Creating table: csv_load_log")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS csv_load_log (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                file_date DATE,
                rows_loaded INT,
                loaded_at TIMESTAMP DEFAULT NOW(),
                status VARCHAR(20),
                error_message TEXT,
                UNIQUE(filename)
            )
        """)
        
        # 14. Cross-validation results
        logger.info("   Creating table: cross_validation")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cross_validation (
                id SERIAL PRIMARY KEY,
                validation_date DATE NOT NULL,
                timeframe VARCHAR(10),
                event_type VARCHAR(20),
                total_realtime INT,
                total_csv INT,
                matches INT,
                mismatches INT,
                missing_in_realtime INT,
                missing_in_csv INT,
                match_rate DECIMAL(5, 4),
                avg_price_diff DECIMAL(10, 2),
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(validation_date, timeframe)
            )
        """)
        
        logger.info("✅ Track 2 tables created (8 tables)")
        
        # ========== CREATE INDEXES FOR PERFORMANCE ==========
        logger.info("\n🔍 Creating indexes for performance...")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_realtime_ohlcv_timestamp ON realtime_ohlcv(timestamp DESC)")
        logger.info("   ✅ Index: idx_realtime_ohlcv_timestamp")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_realtime_structures_timestamp ON realtime_structures(timestamp DESC)")
        logger.info("   ✅ Index: idx_realtime_structures_timestamp")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_realtime_structures_event ON realtime_structures(event_type, direction)")
        logger.info("   ✅ Index: idx_realtime_structures_event")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_marketdata_m15_time ON marketdata_xauusd_m15(time DESC)")
        logger.info("   ✅ Index: idx_marketdata_m15_time")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_csv_load_date ON csv_load_log(file_date DESC)")
        logger.info("   ✅ Index: idx_csv_load_date")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp DESC)")
        logger.info("   ✅ Index: idx_trades_timestamp")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_agent_decisions_timestamp ON agent_decisions(timestamp DESC)")
        logger.info("   ✅ Index: idx_agent_decisions_timestamp")
        
        logger.info("✅ All indexes created (7 indexes)")


def verify_schema(conn):
    """Verify all tables were created successfully"""
    logger.info("\n🔍 Verifying schema...")
    
    expected_tables = [
        # Track 1
        "realtime_ohlcv",
        "realtime_structures",
        "trades",
        "agent_decisions",
        "state_machine",
        "agent_performance",
        "agent_sentiment_logs",
        # Track 2
        "llhhbosdata_xauusd",
        "backtest_results_xauusd",
        "marketdata_xauusd_m15",
        "marketdata_xauusd_h1",
        "marketdata_xauusd_h4",
        "sessionzone_xauusd",
        "csv_load_log",
        "cross_validation",
    ]
    
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        existing_tables = [row[0] for row in cur.fetchall()]
        
        logger.info(f"\n📋 Found {len(existing_tables)} tables in database:")
        for table in existing_tables:
            status = "✅" if table in expected_tables else "⚠️"
            logger.info(f"   {status} {table}")
        
        # Check if all expected tables exist
        missing_tables = set(expected_tables) - set(existing_tables)
        if missing_tables:
            logger.warning(f"\n⚠️ Missing tables: {missing_tables}")
            return False
        else:
            logger.info(f"\n✅ All {len(expected_tables)} expected tables created successfully!")
            return True


def get_table_counts(conn):
    """Get row counts for all tables"""
    logger.info("\n📊 Table row counts:")
    
    tables = [
        "realtime_ohlcv",
        "realtime_structures",
        "trades",
        "agent_decisions",
        "state_machine",
        "agent_performance",
        "agent_sentiment_logs",
        "llhhbosdata_xauusd",
        "backtest_results_xauusd",
        "marketdata_xauusd_m15",
        "marketdata_xauusd_h1",
        "marketdata_xauusd_h4",
        "sessionzone_xauusd",
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
    logger.info("🗄️  NEON POSTGRESQL SCHEMA CREATION")
    logger.info("=" * 70)
    
    # Check credentials
    required_env = ["PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD"]
    missing_env = [env for env in required_env if not os.getenv(env)]
    
    if missing_env:
        logger.error(f"❌ Missing environment variables: {missing_env}")
        logger.error("   Please configure them in .env file")
        sys.exit(1)
    
    logger.info("\n✅ Environment variables configured:")
    logger.info(f"   Host: {os.getenv('PGHOST')}")
    logger.info(f"   Database: {os.getenv('PGDATABASE')}")
    logger.info(f"   User: {os.getenv('PGUSER')}")
    logger.info(f"   SSL Mode: {os.getenv('PGSSLMODE', 'require')}")
    
    try:
        # Connect to database
        conn = get_connection()
        
        # Create schema
        create_schema(conn)
        
        # Verify schema
        verification_success = verify_schema(conn)
        
        # Get table counts
        get_table_counts(conn)
        
        # Close connection
        conn.close()
        logger.info("\n🔌 Connection closed")
        
        if verification_success:
            logger.info("\n" + "=" * 70)
            logger.info("✅ SCHEMA CREATION COMPLETE!")
            logger.info("=" * 70)
            logger.info("\n📊 Summary:")
            logger.info("   - Track 1 (Real-time): 6 tables")
            logger.info("   - Track 2 (Audit): 4 tables")
            logger.info("   - Total: 10 tables")
            logger.info("   - Indexes: 7 indexes")
            logger.info("\n🚀 Next steps:")
            logger.info("   1. Test connection: python scripts/test_neon_connection.py")
            logger.info("   2. Test insert: python scripts/test_neon_insert.py")
            logger.info("   3. Start real-time loop: python main.py")
        else:
            logger.warning("\n⚠️ Schema creation completed with warnings")
            logger.warning("   Please check the logs above for details")
        
    except Exception as e:
        logger.error(f"\n❌ Schema creation failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
