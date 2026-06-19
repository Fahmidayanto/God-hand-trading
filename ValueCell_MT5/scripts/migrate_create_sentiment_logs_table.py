"""
Database Migration: Create Agent Sentiment Logs Table

This migration creates the agent_sentiment_logs table to store historical
sentiment analysis, including headlines analysis, keywords, and upcoming events.

Run this ONCE:
    python scripts/migrate_create_sentiment_logs_table.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from dotenv import load_dotenv
from loguru import logger

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
        logger.error(f"❌ Failed to connect: {e}")
        raise


def migrate(conn):
    """Create agent_sentiment_logs table"""

    with conn.cursor() as cur:
        logger.info("🔧 Running migration: Create agent_sentiment_logs table...")

        # 1. Create table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_sentiment_logs (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                symbol VARCHAR(10) DEFAULT 'XAUUSD',
                
                -- Sentiment scores & labels
                sentiment_score REAL NOT NULL,
                sentiment_label VARCHAR(15) NOT NULL,
                sentiment_strength VARCHAR(15),
                
                -- News statistics
                bullish_news_count INT DEFAULT 0,
                bearish_news_count INT DEFAULT 0,
                triggered_keywords TEXT[],
                
                -- Calendar events
                upcoming_events_count INT DEFAULT 0,
                high_impact_events_count INT DEFAULT 0,
                avoid_trading_triggered BOOLEAN DEFAULT FALSE,
                next_event_name VARCHAR(150),
                next_event_time TIMESTAMP WITH TIME ZONE
            )
        """)
        logger.info("   ✅ Created/Verified agent_sentiment_logs table")

        # 2. Create index on timestamp
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_sentiment_logs_time 
            ON agent_sentiment_logs(timestamp DESC)
        """)
        logger.info("   ✅ Created/Verified index on timestamp")

        # 3. Add column comments
        try:
            cur.execute("COMMENT ON TABLE agent_sentiment_logs IS 'Logs of SentimentAgent calculations per cycle'")
            cur.execute("COMMENT ON COLUMN agent_sentiment_logs.sentiment_score IS 'Calculated score from -1.0 to 1.0'")
            cur.execute("COMMENT ON COLUMN agent_sentiment_logs.sentiment_label IS 'BULLISH, BEARISH, or NEUTRAL'")
            cur.execute("COMMENT ON COLUMN agent_sentiment_logs.avoid_trading_triggered IS 'True if filtered by high-impact event'")
            logger.info("   ✅ Added table and column comments")
        except Exception as e:
            logger.warning(f"   ⚠️ Could not add comments: {e}")

        logger.info("✅ Migration completed successfully!")


if __name__ == "__main__":
    try:
        conn = get_connection()
        migrate(conn)
        conn.close()
        logger.info("✅ Migration script completed")
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)
