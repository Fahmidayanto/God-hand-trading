import sys
import logging
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

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
