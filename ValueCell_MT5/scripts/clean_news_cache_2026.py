import os
import glob
import lancedb

def main():
    print("=" * 60)
    print("   Cleaning 2026 Empty News Cache (LanceDB & File Cache)")
    print("============================================================")

    # 1. Clean File Cache (data/news_cache/news_2026-*.json)
    cache_dir = os.path.join(os.getcwd(), "data", "news_cache")
    if os.path.exists(cache_dir):
        pattern = os.path.join(cache_dir, "news_2026-*.json")
        files = glob.glob(pattern)
        print(f"Found {len(files)} 2026 JSON cache files in {cache_dir}")
        for f in files:
            try:
                os.remove(f)
                print(f"  - Deleted: {os.path.basename(f)}")
            except Exception as e:
                print(f"  - Error deleting {f}: {e}")

    # 2. Clean LanceDB news_sentiment_cache for 2026
    lancedb_dir = os.path.join("python", "valuecell", "data", "lancedb")
    if os.path.exists(lancedb_dir):
        try:
            db = lancedb.connect(lancedb_dir)
            if "news_sentiment_cache" in db.table_names():
                tbl = db.open_table("news_sentiment_cache")
                before_count = tbl.count_rows()
                print(f"\nLanceDB news_sentiment_cache before clean: {before_count} rows")
                
                # Delete rows with timestamp starting with '2026' or empty headlines
                try:
                    tbl.delete("timestamp LIKE '2026%' OR news_headlines = '[]'")
                except Exception:
                    # Fallback to re-creating table if filter syntax varies
                    tbl.delete("timestamp LIKE '2026%'")

                after_count = tbl.count_rows()
                print(f"LanceDB news_sentiment_cache after clean: {after_count} rows (deleted {before_count - after_count} rows)")
        except Exception as e:
            print(f"LanceDB clean error: {e}")

    print("\n[OK] Pembersihan 2026 news cache selesai!")

if __name__ == "__main__":
    main()
