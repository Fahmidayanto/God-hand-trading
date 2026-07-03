# Database Inspector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a "Database Inspector" page in the Web Dashboard containing tabs for NeonDB (with stats cards, table selector, and latest 50 records preview) and LanceDB (listing collections and sizes) with full fallback protection.

**Architecture:** Create a FastAPI router with two endpoints utilizing psycopg2 connection pool and local LanceDB check; build a Next/React Router page `/mt5/database` with a glassmorphism theme and register it in layout and sidebar navigation.

**Tech Stack:** React (React Router v7), TypeScript, Tailwind/Vanilla CSS, Python (FastAPI, psycopg2, lancedb Pydantic).

---

## 📂 Proposed File Changes Map

- **[NEW]** [database.py (Backend Router)](file:///d:/Project/Project%20MT5/ValueCell_MT5/backend/app/api/v1/database.py) — Handles stats and table preview queries.
- **[MODIFY]** [main.py (FastAPI App Entry)](file:///d:/Project/Project%20MT5/ValueCell_MT5/backend/app/main.py) — Registers database router under `/api/v1`.
- **[MODIFY]** [MT5Sidebar.tsx (Sidebar navigation)](file:///d:/Project/Project%20MT5/ValueCell_MT5/frontend/src/app/mt5/components/MT5Sidebar.tsx) — Adds sidebar menu item.
- **[MODIFY]** [_layout.tsx (Page Layout Router)](file:///d:/Project/Project%20MT5/ValueCell_MT5/frontend/src/app/mt5/_layout.tsx) — Maps the `/mt5/database` route to `Database` component.
- **[NEW]** [database.tsx (UI Page component)](file:///d:/Project/Project%20MT5/ValueCell_MT5/frontend/src/app/mt5/database.tsx) — Tab-based UI panel with data preview grid.

---

### Task 1: Backend Database Router

**Files:**
- Create: `ValueCell_MT5/backend/app/api/v1/database.py`
- Modify: `ValueCell_MT5/backend/app/main.py`
- Test: `ValueCell_MT5/backend/tests/test_database_router.py`

- [ ] **Step 1: Write the backend database preview router**
  Create [database.py](file:///d:/Project/Project%20MT5/ValueCell_MT5/backend/app/api/v1/database.py) with the following content:
  ```python
  import os
  import logging
  from pathlib import Path
  from typing import List, Dict, Any, Optional
  from fastapi import APIRouter, Query, HTTPException
  from pydantic import BaseModel
  from app.core.database import get_db_conn

  logger = logging.getLogger(__name__)
  router = APIRouter()

  # List of allowed table names to prevent SQL Injection
  ALLOWED_TABLES = [
      "llhhbosdata_xauusd",
      "backtest_results_xauusd",
      "marketdata_xauusd_m15",
      "marketdata_xauusd_h1",
      "marketdata_xauusd_h4",
      "sessionzone_xauusd",
      "csv_load_log"
  ]

  class NeonStats(BaseModel):
      llhhbosdata_xauusd: int = 0
      backtest_results_xauusd: int = 0
      csv_load_log: int = 0
      marketdata_xauusd_m15: int = 0
      marketdata_xauusd_h1: int = 0
      marketdata_xauusd_h4: int = 0
      sessionzone_xauusd: int = 0

  class LanceDBCollectionStats(BaseModel):
      name: str
      count: int

  class DBStatsResponse(BaseModel):
      neon_stats: NeonStats
      lancedb_active: bool
      lancedb_collections: List[LanceDBCollectionStats]

  class TablePreviewResponse(BaseModel):
      table: str
      columns: List[str]
      rows: List[Dict[str, Any]]

  @router.get("/stats", response_model=DBStatsResponse)
  def get_database_stats():
      neon_counts = {}
      
      # 1. Fetch NeonDB Row Counts
      try:
          with get_db_conn() as conn:
              with conn.cursor() as cur:
                  for table in ALLOWED_TABLES:
                      cur.execute(f"SELECT COUNT(*) FROM {table};")
                      count = cur.fetchone()[0]
                      neon_counts[table] = count
      except Exception as exc:
          logger.error(f"[DB] Error fetching NeonDB row counts: {exc}")
          # Fallback default values
          for table in ALLOWED_TABLES:
              neon_counts[table] = 0

      # 2. Check LanceDB status
      lancedb_active = False
      lancedb_collections = []
      
      try:
          # LanceDB path relative to this file
          base_dir = Path(__file__).parent.parent.parent.parent
          lancedb_path = base_dir / "python" / "valuecell" / "data" / "lancedb"
          
          if lancedb_path.exists() and (lancedb_path / "historical_structures.lance").exists():
              import lancedb
              db = lancedb.connect(str(lancedb_path))
              lancedb_active = True
              for table_name in db.table_names():
                  tbl = db.open_table(table_name)
                  count = tbl.count_rows()
                  lancedb_collections.append(
                      LanceDBCollectionStats(name=table_name, count=count)
                  )
      except Exception as exc:
          logger.warning(f"[DB] LanceDB is offline or not found: {exc}")
          lancedb_active = False
          lancedb_collections = []

      return DBStatsResponse(
          neon_stats=NeonStats(**neon_counts),
          lancedb_active=lancedb_active,
          lancedb_collections=lancedb_collections
      )

  @router.get("/neon/preview", response_model=TablePreviewResponse)
  def preview_table(
      table: str = Query(..., description="Name of the table to preview"),
      limit: int = Query(50, ge=1, le=100, description="Max rows to return")
  ):
      if table not in ALLOWED_TABLES:
          raise HTTPException(status_code=400, detail="Invalid table name")

      try:
          with get_db_conn() as conn:
              with conn.cursor() as cur:
                  # Fetch latest 50 rows based on timestamp/time or loaded_at column
                  # Check if time/timestamp column exists for sorting
                  sort_col = "id"
                  if table == "csv_load_log":
                      sort_col = "id"
                  elif table in ("llhhbosdata_xauusd", "sessionzone_xauusd", "marketdata_xauusd_m15", "marketdata_xauusd_h1", "marketdata_xauusd_h4"):
                      sort_col = "time"
                  elif table == "backtest_results_xauusd":
                      sort_col = "entry_time"
                      
                  cur.execute(f"SELECT * FROM {table} ORDER BY {sort_col} DESC LIMIT %s;", (limit,))
                  rows = cur.fetchall()
                  colnames = [desc[0] for desc in cur.description]
                  
                  formatted_rows = []
                  for row in rows:
                      row_dict = {}
                      for col, val in zip(colnames, row):
                          # Format datetime values for JSON serialization
                          if hasattr(val, "isoformat"):
                              row_dict[col] = val.isoformat()
                          else:
                              row_dict[col] = val
                      formatted_rows.append(row_dict)
                      
                  return TablePreviewResponse(
                      table=table,
                      columns=colnames,
                      rows=formatted_rows
                  )
      except Exception as exc:
          logger.error(f"[DB] Error previewing table {table}: {exc}")
          raise HTTPException(status_code=500, detail=f"Database error: {str(exc)}")
  ```

- [ ] **Step 2: Register the database router in main.py**
  Modify [main.py](file:///d:/Project/Project%20MT5/ValueCell_MT5/backend/app/main.py) to import and register the database router:
  Include `from app.api.v1.database import router as database_router` and `app.include_router(database_router, prefix="/api/v1/database", tags=["database"])`.
  Target section:
  ```python
  # Register routers
  app.include_router(trading_router, prefix=f"{settings.API_V1_PREFIX}/trading", tags=["trading"])
  # ADD HERE:
  app.include_router(database_router, prefix=f"{settings.API_V1_PREFIX}/database", tags=["database"])
  ```

- [ ] **Step 3: Run FastAPI backend tests**
  Create a test script `ValueCell_MT5/backend/tests/test_database_router.py` containing:
  ```python
  from fastapi.testclient import TestClient
  from app.main import app

  client = TestClient(app)

  def test_get_stats():
      response = client.get("/api/v1/database/stats")
      assert response.status_code == 200
      data = response.json()
      assert "neon_stats" in data
      assert "lancedb_active" in data

  def test_preview_table_invalid():
      response = client.get("/api/v1/database/neon/preview?table=nonexistent")
      assert response.status_code == 400
  ```
  Run: `pytest ValueCell_MT5/backend/tests/test_database_router.py -v`
  Expected: PASS

- [ ] **Step 4: Commit**
  ```bash
  git add ValueCell_MT5/backend/app/api/v1/database.py ValueCell_MT5/backend/app/main.py ValueCell_MT5/backend/tests/test_database_router.py
  git commit -m "feat: add database stats and preview endpoints to backend"
  ```

---

### Task 2: Frontend Navigation Setup

**Files:**
- Modify: `ValueCell_MT5/frontend/src/app/mt5/components/MT5Sidebar.tsx`
- Modify: `ValueCell_MT5/frontend/src/app/mt5/_layout.tsx`

- [ ] **Step 1: Add DB Inspector link to Sidebar**
  Modify [MT5Sidebar.tsx](file:///d:/Project/Project%20MT5/ValueCell_MT5/frontend/src/app/mt5/components/MT5Sidebar.tsx) to add:
  `{ path: "/mt5/database", label: "DB Inspector", icon: "💾" }` to the `navLinks` list.

- [ ] **Step 2: Add Route Mapping to layout.tsx**
  Modify [_layout.tsx](file:///d:/Project/Project%20MT5/ValueCell_MT5/frontend/src/app/mt5/_layout.tsx):
  - Import Database component: `import Database from "./database";`
  - Register inside `pages` array: `{ path: "/mt5/database", Component: Database },`

- [ ] **Step 3: Commit**
  ```bash
  git add ValueCell_MT5/frontend/src/app/mt5/components/MT5Sidebar.tsx ValueCell_MT5/frontend/src/app/mt5/_layout.tsx
  git commit -m "feat: add database inspector page route to layout and sidebar"
  ```

---

### Task 3: Frontend DB Inspector Page Implementation

**Files:**
- Create: `ValueCell_MT5/frontend/src/app/mt5/database.tsx`

- [ ] **Step 1: Create the Database Inspector page**
  Write [database.tsx](file:///d:/Project/Project%20MT5/ValueCell_MT5/frontend/src/app/mt5/database.tsx) containing:
  ```tsx
  import { useState, useEffect } from "react";

  interface Stats {
    neon_stats: {
      llhhbosdata_xauusd: number;
      backtest_results_xauusd: number;
      csv_load_log: number;
      marketdata_xauusd_m15: number;
      marketdata_xauusd_h1: number;
      marketdata_xauusd_h4: number;
      sessionzone_xauusd: number;
    };
    lancedb_active: boolean;
    lancedb_collections: Array<{ name: string; count: number }>;
  }

  interface TableData {
    table: string;
    columns: string[];
    rows: Array<Record<string, any>>;
  }

  export default function Database() {
    const [activeTab, setActiveTab] = useState<"neon" | "lance">("neon");
    const [stats, setStats] = useState<Stats | null>(null);
    const [selectedTable, setSelectedTable] = useState<string>("llhhbosdata_xauusd");
    const [previewData, setPreviewData] = useState<TableData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const API_BASE = "http://localhost:8000/api/v1/database";

    const fetchStats = async () => {
      try {
        const res = await fetch(`${API_BASE}/stats`);
        if (!res.ok) throw new Error("Failed to fetch database stats");
        const data = await res.json();
        setStats(data);
      } catch (err: any) {
        console.error(err);
      }
    };

    const fetchTablePreview = async (table: string) => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API_BASE}/neon/preview?table=${table}&limit=50`);
        if (!res.ok) throw new Error(`Failed to load data from ${table}`);
        const data = await res.json();
        setPreviewData(data);
      } catch (err: any) {
        setError(err.message || "Failed to load data");
        setPreviewData(null);
      } finally {
        setLoading(false);
      }
    };

    useEffect(() => {
      fetchStats();
    }, []);

    useEffect(() => {
      if (activeTab === "neon") {
        fetchTablePreview(selectedTable);
      }
    }, [selectedTable, activeTab]);

    const handleRefresh = () => {
      fetchStats();
      if (activeTab === "neon") {
        fetchTablePreview(selectedTable);
      }
    };

    return (
      <div className="p-8 max-w-7xl mx-auto text-slate-200">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
              Database Inspector 💾
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Verify database storage row counts and preview records in NeonDB and LanceDB.
            </p>
          </div>
          <button
            onClick={handleRefresh}
            className="px-4 py-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:opacity-90 rounded-lg text-sm font-semibold transition-all shadow-[0_0_15px_rgba(59,130,246,0.3)]"
          >
            🔄 Refresh Data
          </button>
        </div>

        {/* Tab Selection */}
        <div className="flex gap-4 border-b border-slate-700/50 pb-3 mb-6">
          <button
            onClick={() => setActiveTab("neon")}
            className={`px-4 py-2 font-semibold text-sm rounded-lg transition-all ${
              activeTab === "neon"
                ? "text-blue-400 bg-blue-500/10 shadow-[0_0_10px_rgba(59,130,246,0.15)]"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            NeonDB (PostgreSQL)
          </button>
          <button
            onClick={() => setActiveTab("lance")}
            className={`px-4 py-2 font-semibold text-sm rounded-lg transition-all ${
              activeTab === "lance"
                ? "text-purple-400 bg-purple-500/10 shadow-[0_0_10px_rgba(139,92,246,0.15)]"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            LanceDB (Vector Database)
          </button>
        </div>

        {/* NEON DB CONTENT */}
        {activeTab === "neon" && (
          <div>
            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              <div className="glass-card p-5 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md">
                <span className="text-xs uppercase text-slate-500 font-semibold tracking-wider">
                  Total Swing Events
                </span>
                <h3 className="text-2xl font-bold text-slate-100 mt-1">
                  {stats?.neon_stats.llhhbosdata_xauusd ?? 0}{" "}
                  <span className="text-xs font-normal text-slate-500">rows</span>
                </h3>
              </div>
              <div className="glass-card p-5 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md">
                <span className="text-xs uppercase text-slate-500 font-semibold tracking-wider">
                  Total Trade Records
                </span>
                <h3 className="text-2xl font-bold text-slate-100 mt-1">
                  {stats?.neon_stats.backtest_results_xauusd ?? 0}{" "}
                  <span className="text-xs font-normal text-slate-500">rows</span>
                </h3>
              </div>
              <div className="glass-card p-5 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md">
                <span className="text-xs uppercase text-slate-500 font-semibold tracking-wider">
                  File Import Watcher Log
                </span>
                <h3 className="text-2xl font-bold text-slate-100 mt-1">
                  {stats?.neon_stats.csv_load_log ?? 0}{" "}
                  <span className="text-xs font-normal text-slate-500">records</span>
                </h3>
              </div>
            </div>

            {/* Table Control */}
            <div className="flex gap-4 items-center mb-4">
              <span className="text-sm text-slate-400">Select PostgreSQL Table:</span>
              <select
                value={selectedTable}
                onChange={(e) => setSelectedTable(e.target.value)}
                className="bg-slate-950 border border-slate-700/50 text-slate-200 px-3 py-1.5 rounded-lg focus:outline-none"
              >
                <option value="llhhbosdata_xauusd">llhhbosdata_xauusd (Swing Events)</option>
                <option value="backtest_results_xauusd">backtest_results_xauusd (Trades)</option>
                <option value="marketdata_xauusd_m15">marketdata_xauusd_m15 (OHLCV)</option>
                <option value="marketdata_xauusd_h1">marketdata_xauusd_h1 (OHLCV)</option>
                <option value="marketdata_xauusd_h4">marketdata_xauusd_h4 (OHLCV)</option>
                <option value="sessionzone_xauusd">sessionzone_xauusd (Session Zones)</option>
                <option value="csv_load_log">csv_load_log (Import Logger)</option>
              </select>
            </div>

            {/* Data Grid */}
            <div className="bg-slate-900/30 border border-slate-700/30 rounded-xl overflow-hidden backdrop-blur-md">
              {loading && <div className="p-8 text-center text-slate-400">Loading data from NeonDB...</div>}
              {error && <div className="p-8 text-center text-red-400 font-medium">⚠️ Error: {error}</div>}
              {!loading && !error && previewData && (
                <div className="overflow-x-auto max-h-[500px]">
                  <table className="w-full border-collapse text-sm text-left">
                    <thead>
                      <tr className="bg-slate-950/70 border-b border-slate-700/40">
                        {previewData.columns.map((col) => (
                          <th key={col} className="p-3 text-slate-400 font-semibold uppercase text-xs">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/40">
                      {previewData.rows.length === 0 ? (
                        <tr>
                          <td colSpan={previewData.columns.length} className="p-8 text-center text-slate-500">
                            No rows found in this table.
                          </td>
                        </tr>
                      ) : (
                        previewData.rows.map((row, idx) => (
                          <tr key={idx} className="hover:bg-slate-800/20">
                            {previewData.columns.map((col) => (
                              <td key={col} className="p-3 font-mono text-xs">
                                {typeof row[col] === "boolean"
                                  ? String(row[col])
                                  : row[col] === null
                                  ? "NULL"
                                  : String(row[col])}
                              </td>
                            ))}
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* LANCE DB CONTENT */}
        {activeTab === "lance" && (
          <div className="glass-card p-6 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md">
            <h3 className="text-lg font-semibold mb-4">LanceDB Vector Collections Summary</h3>
            {stats?.lancedb_active ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400">
                      <th className="py-2">Collection Name</th>
                      <th className="py-2">Total Vector Records</th>
                      <th className="py-2">Type</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {stats.lancedb_collections.map((col) => (
                      <tr key={col.name}>
                        <td className="py-3 font-semibold text-blue-400">{col.name}</td>
                        <td className="py-3 font-mono">{col.count} vectors</td>
                        <td className="py-3 text-slate-500">In-Memory / Vector</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-6 bg-slate-950/50 rounded-lg border border-slate-800 text-center">
                <p className="text-slate-400 font-medium">⚠️ LanceDB tidak terdeteksi atau belum aktif.</p>
                <p className="text-xs text-slate-500 mt-1">
                  (Track 1 saat ini dinonaktifkan di backend, sehingga database vektor tidak diinisialisasi).
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    );
  }
  ```

- [ ] **Step 2: Commit**
  ```bash
  git add ValueCell_MT5/frontend/src/app/mt5/database.tsx
  git commit -m "feat: implement database inspector page UI grid"
  ```
