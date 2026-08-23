import sys
from pathlib import Path
sys.path.insert(0, str(Path("ValueCell_MT5/python")))
import lancedb

db_path = Path("ValueCell_MT5/python/valuecell/data/lancedb")
db = lancedb.connect(str(db_path))
tables = db.table_names() if hasattr(db, "table_names") else db.list_tables()
print("=== LanceDB Tables ===")
for t in tables:
    try:
        tbl = db.open_table(t)
        print(f"  {t}: {len(tbl)} records")
    except Exception as e:
        print(f"  {t}: err ({e})")
