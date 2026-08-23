import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Setup paths and env
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

for env_candidate in [BACKEND_DIR / ".env", PROJECT_ROOT / ".env", PROJECT_ROOT.parent / ".env"]:
    if env_candidate.exists():
        load_dotenv(env_candidate)

logging.basicConfig(level=logging.INFO)
from app.core.database import init_db_pool, close_db_pool
from app.services.csv_watcher_service import CSVWatcherService

def main():
    print("Initializing DB Pool...")
    if init_db_pool():
        print("DB Pool ready.")
        watcher = CSVWatcherService()
        print("Running initial historical scan...")
        watcher._scan_and_load_all()
        print("Initial scan completed successfully!")
        close_db_pool()
    else:
        print("Failed to initialize DB pool.")

if __name__ == "__main__":
    main()
