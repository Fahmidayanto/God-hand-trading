"""
Database Migration: Add Instant BoS Trigger Support

This migration adds columns to realtime_structures table to support:
1. Event deduplication (processed, processed_at, cycle_number)
2. Instant trigger mechanism
3. Event tracking and audit trail

Run this ONCE after schema creation:
    python scripts/migrate_add_bos_trigger_support.py

Idempotent: Safe to run multiple times (uses ALTER TABLE IF NOT EXISTS)
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from psycopg2 import sql
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
    """Add instant trigger columns to realtime_structures"""

    with conn.cursor() as cur:
        logger.info("🔧 Running migration: Add BoS Trigger Support...")

        # 1. Add processed column if not exists
        logger.info("   Adding 'processed' column...")
        try:
            cur.execute("""
                ALTER TABLE realtime_structures
                ADD COLUMN processed BOOLEAN DEFAULT FALSE
            """)
            logger.info("   ✅ Added 'processed' column")
        except psycopg2.Error as e:
            if "column \"processed\" of relation \"realtime_structures\" already exists" in str(e):
                logger.info("   ℹ️  'processed' column already exists, skipping")
            else:
                logger.error(f"   ❌ Error: {e}")
                raise

        # 2. Add processed_at column if not exists
        logger.info("   Adding 'processed_at' column...")
        try:
            cur.execute("""
                ALTER TABLE realtime_structures
                ADD COLUMN processed_at TIMESTAMP
            """)
            logger.info("   ✅ Added 'processed_at' column")
        except psycopg2.Error as e:
            if "column \"processed_at\" of relation \"realtime_structures\" already exists" in str(e):
                logger.info("   ℹ️  'processed_at' column already exists, skipping")
            else:
                logger.error(f"   ❌ Error: {e}")
                raise

        # 3. Add cycle_number column if not exists
        logger.info("   Adding 'cycle_number' column...")
        try:
            cur.execute("""
                ALTER TABLE realtime_structures
                ADD COLUMN cycle_number BIGINT
            """)
            logger.info("   ✅ Added 'cycle_number' column")
        except psycopg2.Error as e:
            if "column \"cycle_number\" of relation \"realtime_structures\" already exists" in str(e):
                logger.info("   ℹ️  'cycle_number' column already exists, skipping")
            else:
                logger.error(f"   ❌ Error: {e}")
                raise

        # 4. Create index on processed column for faster queries
        logger.info("   Creating index on 'processed' column...")
        try:
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_realtime_structures_processed
                ON realtime_structures(processed)
                WHERE processed = FALSE
            """)
            logger.info("   ✅ Created index on 'processed' column")
        except psycopg2.Error as e:
            logger.warning(f"   ⚠️  Could not create index: {e}")

        # 5. Create index on event_type for faster filtering
        logger.info("   Creating index on 'event_type' column...")
        try:
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_realtime_structures_event_type
                ON realtime_structures(event_type)
            """)
            logger.info("   ✅ Created index on 'event_type' column")
        except psycopg2.Error as e:
            logger.warning(f"   ⚠️  Could not create index: {e}")

        # 6. Add comment/documentation
        logger.info("   Adding column comments...")
        try:
            cur.execute("""
                COMMENT ON COLUMN realtime_structures.processed IS
                'Boolean flag: TRUE when event has been processed by orchestrator (deduplication)'
            """)
            cur.execute("""
                COMMENT ON COLUMN realtime_structures.processed_at IS
                'Timestamp when event was marked as processed (audit trail)'
            """)
            cur.execute("""
                COMMENT ON COLUMN realtime_structures.cycle_number IS
                'Decision cycle number that processed this event (deduplication)'
            """)
            logger.info("   ✅ Added column comments")
        except Exception as e:
            logger.warning(f"   ⚠️  Could not add comments: {e}")

        logger.info("✅ Migration completed successfully!")
        logger.info("")
        logger.info("📊 Schema Changes Summary:")
        logger.info("   • realtime_structures.processed (BOOLEAN, default FALSE)")
        logger.info("   • realtime_structures.processed_at (TIMESTAMP, nullable)")
        logger.info("   • realtime_structures.cycle_number (BIGINT, nullable)")
        logger.info("")
        logger.info("🚀 Instant BoS Trigger is now ENABLED!")


if __name__ == "__main__":
    try:
        conn = get_connection()
        migrate(conn)
        conn.close()
        logger.info("✅ Migration script completed")
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)
