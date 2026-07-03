import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.getenv("PGHOST"),
    database=os.getenv("PGDATABASE"),
    user=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
    sslmode="require"
)
conn.autocommit = True
cur = conn.cursor()
cur.execute("""
    SELECT pg_terminate_backend(pid) 
    FROM pg_stat_activity 
    WHERE datname = 'neondb' AND pid != pg_backend_pid()
""")
rows = cur.fetchall()
print(f"Terminated {len(rows)} database connections.")
conn.close()
