"""
Import Specific Year CSV Data into Neon DB and LanceDB
Usage: python scratch/import_specific_year.py 2026
"""
import os
import sys
from pathlib import Path

# Force UTF-8 stdout
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "ValueCell_MT5" / "backend"
PYTHON_DIR = PROJECT_ROOT / "ValueCell_MT5" / "python"
LANCEDB_PATH = PYTHON_DIR / "valuecell" / "data" / "lancedb"

sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(PYTHON_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from app.core.database import init_db_pool, close_db_pool
from app.services.csv_watcher_service import CSVWatcherService

def run_import(year_filter: str = "2026"):
    print(f"=== Memulai Impor CSV Spesifik: {year_filter} ===")
    
    if not init_db_pool(minconn=1, maxconn=5):
        print("ERR: Gagal inisialisasi pool database Neon.")
        return

    watcher = CSVWatcherService(check_interval_seconds=5)
    watcher.is_syncing = True
    
    # Inisialisasi LanceDB
    from valuecell.knowledge.lance_db import LanceDBManager
    watcher.lancedb = LanceDBManager(str(LANCEDB_PATH))
    print(f"OK Terhubung ke LanceDB: {LANCEDB_PATH}")
    
    backtest_dir = watcher.backtest_dir
    csv_files = sorted(list(backtest_dir.glob(f"*{year_filter}*.csv")))
    valid_files = [fp for fp in csv_files if watcher._map_filename_to_table(fp.name)]
    
    print(f"Ditemukan {len(valid_files)} file CSV valid untuk tahun {year_filter}:")
    for f in valid_files:
        tbl = watcher._map_filename_to_table(f.name)
        print(f"   - {f.name} -> {tbl}")
        
    print()
    for idx, file_path in enumerate(valid_files, 1):
        tbl = watcher._map_filename_to_table(file_path.name)
        print(f"[{idx}/{len(valid_files)}] Memproses {file_path.name}...")
        try:
            watcher._process_file_incrementally(file_path, tbl)
            print(f"   OK Berhasil memproses {file_path.name}")
        except Exception as e:
            print(f"   ERR Gagal memproses {file_path.name}: {e}")
            
    close_db_pool()
    print(f"\n=== SELESAI IMPOR TAHUN {year_filter} ===")

if __name__ == "__main__":
    raw_args = sys.argv[1:]
    years_to_run = []
    for arg in raw_args:
        if "-" in arg and not arg.startswith("-"):
            start, end = arg.split("-")
            years_to_run.extend([str(y) for y in range(int(start), int(end) + 1)])
        elif "," in arg:
            years_to_run.extend([y.strip() for y in arg.split(",") if y.strip()])
        else:
            years_to_run.append(arg.strip())
            
    if not years_to_run:
        years_to_run = ["2026"]
        
    for y in sorted(years_to_run, reverse=True):
        run_import(y)
