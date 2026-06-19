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
        logger.info("🔧 Creating schema for DUAL-TRACK SYSTEM...")
        
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
        
        logger.info("✅ Track 1 tables created (6 tables)")
        
        # ========== TRACK 2: AUDIT TABLES (from CSV batch load) ==========
        logger.info("\n📁 TRACK 2: Creating audit tables...")
        
        # 7. Historical OHLCV audit trail
        logger.info("   Creating table: historical_ohlcv_audit")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS historical_ohlcv_audit (
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
                source VARCHAR(20) DEFAULT 'csv_export',
                csv_filename VARCHAR(255),
                loaded_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(timestamp, symbol, timeframe, source)
            )
        """)
        
        # 8. Historical structure events audit trail
        logger.info("   Creating table: historical_structures_audit")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS historical_structures_audit (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                timeframe VARCHAR(10) NOT NULL,
                event_type VARCHAR(20),
                direction VARCHAR(10),
                price DECIMAL(10, 2),
                status VARCHAR(20),
                session VARCHAR(20),
                source VARCHAR(20) DEFAULT 'csv_export',
                csv_filename VARCHAR(255),
                loaded_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # 9. CSV load tracking
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
        
        # 10. Cross-validation results
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
        
        logger.info("✅ Track 2 tables created (4 tables)")
        
        # ========== CREATE INDEXES FOR PERFORMANCE ==========
        logger.info("\n🔍 Creating indexes for performance...")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_realtime_ohlcv_timestamp ON realtime_ohlcv(timestamp DESC)")
        logger.info("   ✅ Index: idx_realtime_ohlcv_timestamp")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_realtime_structures_timestamp ON realtime_structures(timestamp DESC)")
        logger.info("   ✅ Index: idx_realtime_structures_timestamp")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_realtime_structures_event ON realtime_structures(event_type, direction)")
        logger.info("   ✅ Index: idx_realtime_structures_event")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_historical_audit_timestamp ON historical_ohlcv_audit(timestamp DESC)")
        logger.info("   ✅ Index: idx_historical_audit_timestamp")
        
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
        # Track 2
        "historical_ohlcv_audit",
        "historical_structures_audit",
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
