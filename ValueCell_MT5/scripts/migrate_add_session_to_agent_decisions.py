"""
Migration: Add `session` column to `agent_decisions` table.

Run once:
    python scripts/migrate_add_session_to_agent_decisions.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"), override=True)

from app.core.database import init_db_pool, get_db_conn


def _get_session_from_hour(hour: int) -> str:
    """Classify UTC hour into trading session."""
    if 22 <= hour or hour < 8:
        return "SYDNEY"
    elif 8 <= hour < 12:
        return "LONDON"
    elif 12 <= hour < 16:
        return "NEW_YORK"
    else:
        return "OVERLAP"


def main():
    ok = init_db_pool()
    if not ok:
        print("[ERROR] Could not initialize DB pool. Check .env credentials.")
        sys.exit(1)

    with get_db_conn() as conn:
        with conn.cursor() as cur:

            # 1. Check if column already exists
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'agent_decisions'
                  AND column_name = 'session'
            """)
            if cur.fetchone():
                print("[OK] Column 'session' already exists in agent_decisions. Nothing to do.")
                return

            # 2. Add session column
            print("Adding column 'session' to agent_decisions...")
            cur.execute("""
                ALTER TABLE agent_decisions
                ADD COLUMN session VARCHAR(20) DEFAULT 'UNKNOWN'
            """)
            print("[OK] Column added.")

            # 3. Backfill existing rows
            cur.execute("SELECT id, timestamp FROM agent_decisions WHERE session IS NULL OR session = 'UNKNOWN'")
            rows = cur.fetchall()
            print(f"Backfilling {len(rows)} existing rows...")

            for row_id, ts in rows:
                if ts is None:
                    continue
                session = _get_session_from_hour(ts.hour)
                cur.execute(
                    "UPDATE agent_decisions SET session = %s WHERE id = %s",
                    (session, row_id),
                )

            print(f"[OK] Backfilled {len(rows)} rows.")

        conn.commit()
        print("[DONE] Migration complete.")


if __name__ == "__main__":
    main()
