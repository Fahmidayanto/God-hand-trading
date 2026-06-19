"""
Test Neon PostgreSQL Connection

Simple script to verify database connection and credentials.

Usage:
    python scripts/test_neon_connection.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()


def test_connection():
    """Test connection to Neon PostgreSQL"""
    logger.info("=" * 70)
    logger.info("🔌 TESTING NEON POSTGRESQL CONNECTION")
    logger.info("=" * 70)
    
    # Check credentials
    logger.info("\n📋 Checking credentials...")
    credentials = {
        "PGHOST": os.getenv("PGHOST"),
        "PGDATABASE": os.getenv("PGDATABASE"),
        "PGUSER": os.getenv("PGUSER"),
        "PGPASSWORD": os.getenv("PGPASSWORD"),
        "PGSSLMODE": os.getenv("PGSSLMODE", "require"),
    }
    
    for key, value in credentials.items():
        if value:
            if key == "PGPASSWORD":
                masked = value[:3] + "*" * (len(value) - 3) if len(value) > 3 else "***"
                logger.info(f"   ✅ {key}: {masked}")
            else:
                logger.info(f"   ✅ {key}: {value}")
        else:
            logger.error(f"   ❌ {key}: Not set")
            return False
    
    # Test connection
    logger.info("\n🔌 Attempting to connect...")
    try:
        conn = psycopg2.connect(
            host=credentials["PGHOST"],
            database=credentials["PGDATABASE"],
            user=credentials["PGUSER"],
            password=credentials["PGPASSWORD"],
            sslmode=credentials["PGSSLMODE"]
        )
        
        logger.info("✅ Connection successful!")
        
        # Get database version
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
            logger.info(f"\n📊 Database info:")
            logger.info(f"   Version: {version.split(',')[0]}")
            
            # Get current database name
            cur.execute("SELECT current_database()")
            db_name = cur.fetchone()[0]
            logger.info(f"   Database: {db_name}")
            
            # Get current user
            cur.execute("SELECT current_user")
            user = cur.fetchone()[0]
            logger.info(f"   User: {user}")
            
            # Get current timestamp
            cur.execute("SELECT NOW()")
            timestamp = cur.fetchone()[0]
            logger.info(f"   Server time: {timestamp}")
        
        conn.close()
        logger.info("\n🔌 Connection closed")
        logger.info("\n" + "=" * 70)
        logger.info("✅ CONNECTION TEST PASSED!")
        logger.info("=" * 70)
        return True
        
    except psycopg2.OperationalError as e:
        logger.error(f"\n❌ Connection failed: {e}")
        logger.error("\n💡 Troubleshooting:")
        logger.error("   1. Check your internet connection")
        logger.error("   2. Verify credentials in .env file")
        logger.error("   3. Check if Neon database is active")
        logger.error("   4. Verify SSL mode is set to 'require'")
        return False
    
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
