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

interface CsvSyncStatusItem {
  filename: string;
  table_name: string;
  local_rows: number;
  db_rows: number;
  status: string;
  loaded_at: string | null;
  is_up_to_date: boolean;
}

const formatDatabaseDate = (val: string): string => {
  if (typeof val !== "string") return val;
  if (val.includes("T")) {
    const parts = val.split("T");
    const datePart = parts[0];
    let timePart = parts[1];
    if (timePart.includes(".")) {
      timePart = timePart.split(".")[0];
    }
    if (timePart.includes("Z")) {
      timePart = timePart.replace("Z", "");
    }
    return `${datePart} ${timePart}`;
  }
  return val;
};

export default function Database() {
  const [activeTab, setActiveTab] = useState<"neon" | "lance" | "sync">("neon");
  const [stats, setStats] = useState<Stats | null>(null);
  const [selectedTable, setSelectedTable] = useState<string>("llhhbosdata_xauusd");
  const [previewCache, setPreviewCache] = useState<Record<string, TableData>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncProgress, setSyncProgress] = useState({ visible: false, percent: 0, step: "" });
  const [dropdownOpen, setDropdownOpen] = useState(false);

  // Sync monitor states
  const [syncData, setSyncData] = useState<CsvSyncStatusItem[]>([]);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncSearch, setSyncSearch] = useState("");
  const [syncFilter, setSyncFilter] = useState<"all" | "synced" | "pending" | "unsynced">("all");

  // Sync diff modal states
  const [selectedDiffFile, setSelectedDiffFile] = useState<string | null>(null);
  const [diffData, setDiffData] = useState<{ type: string; count: number; columns: string[]; rows: any[] } | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [diffError, setDiffError] = useState<string | null>(null);

  // LanceDB collection info modal
  const [selectedCollectionInfo, setSelectedCollectionInfo] = useState<string | null>(null);

  // LanceDB preview (data table) state
  const [selectedLanceCollection, setSelectedLanceCollection] = useState<string>("historical_structures");
  const [selectedLanceLimit, setSelectedLanceLimit] = useState<number>(30);
  const [lancePreviewCache, setLancePreviewCache] = useState<Record<string, TableData>>({});
  const [lanceLoading, setLanceLoading] = useState(false);
  const [lanceError, setLanceError] = useState<string | null>(null);
  const [lanceDropdownOpen, setLanceDropdownOpen] = useState(false);

  const TABLES_METADATA = [
    { value: "llhhbosdata_xauusd", label: "llhhbosdata_xauusd (Swing Events)" },
    { value: "backtest_results_xauusd", label: "backtest_results_xauusd (Trades)" },
    { value: "marketdata_xauusd_m15", label: "marketdata_xauusd_m15 (OHLCV)" },
    { value: "marketdata_xauusd_h1", label: "marketdata_xauusd_h1 (OHLCV)" },
    { value: "marketdata_xauusd_h4", label: "marketdata_xauusd_h4 (OHLCV)" },
    { value: "sessionzone_xauusd", label: "sessionzone_xauusd (Session Zones)" },
    { value: "csv_load_log", label: "csv_load_log (Import Logger)" },
  ];

  const currentLabel = TABLES_METADATA.find(t => t.value === selectedTable)?.label || selectedTable;

  const LANCE_COLLECTIONS_METADATA = [
    { value: "historical_structures", label: "historical_structures (Market Structure Patterns)" },
    { value: "market_conditions", label: "market_conditions (OHLCV + Indicators)" },
    { value: "session_patterns", label: "session_patterns (Session Stats)" },
    { value: "trade_outcomes", label: "trade_outcomes (Trade History for ML)" },
  ];
  const currentLanceLabel = LANCE_COLLECTIONS_METADATA.find(c => c.value === selectedLanceCollection)?.label || selectedLanceCollection;

  // Deskripsi tiap koleksi LanceDB (purpose, vector dim, key fields, use case).
  // Sumber: ValueCell_MT5/python/valuecell/knowledge/lance_db.py
  const LANCE_COLLECTIONS_INFO: Record<string, { purpose: string; vectorDim: number; keyFields: string[]; useCase: string }> = {
    historical_structures: {
      purpose: "Market structure patterns (CHoCH, BoS, HH, LL) untuk similarity search pola historis.",
      vectorDim: 16,
      keyFields: ["event_type", "direction", "price", "ema200", "ema_distance", "session", "outcome", "profit_pips"],
      useCase: "Pattern matcher cari pola struktur mirip kondisi saat ini untuk confidence score.",
    },
    market_conditions: {
      purpose: "Konteks kondisi pasar OHLCV + indikator (EMA200, ATR) per candle.",
      vectorDim: 8,
      keyFields: ["open", "high", "low", "close", "volume", "ema200", "atr", "session"],
      useCase: "Referensi kondisi pasar saat pattern match sedang berjalan.",
    },
    session_patterns: {
      purpose: "Statistik perilaku per sesi trading (London, NewYork, Asia, Sydney).",
      vectorDim: 4,
      keyFields: ["session", "win_rate", "avg_profit_pips", "total_trades", "best_event_type"],
      useCase: "Filter / bobot trade berdasarkan performa historis sesi tersebut.",
    },
    trade_outcomes: {
      purpose: "Trade history + outcome (WIN/LOSS/PENDING) untuk training ML model.",
      vectorDim: 12,
      keyFields: ["ticket", "type", "entry_price", "exit_price", "profit_pips", "outcome", "structure_event", "consensus_score"],
      useCase: "Dataset training ML prediction (v3/v4) dan analisis post-mortem trade.",
    },
  };

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

  const fetchSyncStatus = async (showLoading = true) => {
    if (showLoading) {
      setSyncLoading(true);
    }
    try {
      const res = await fetch(`${API_BASE}/sync-status`);
      if (!res.ok) throw new Error("Failed to fetch sync status");
      const data = await res.json();
      setSyncData(data);
    } catch (err) {
      console.error(err);
    } finally {
      if (showLoading) {
        setSyncLoading(false);
      }
    }
  };

  const handleOpenDiff = async (filename: string) => {
    setSelectedDiffFile(filename);
    setDiffLoading(true);
    setDiffData(null);
    setDiffError(null);
    try {
      const res = await fetch(`${API_BASE}/sync-diff?filename=${filename}`);
      if (!res.ok) throw new Error("Failed to fetch sync diff");
      const data = await res.json();
      setDiffData(data);
    } catch (err: any) {
      console.error(err);
      setDiffError(err.message || "Failed to load sync difference detail");
    } finally {
      setDiffLoading(false);
    }
  };

  const fetchTablePreview = async (table: string, silent = false) => {
    const hasCache = !!previewCache[table];
    if (!hasCache && !silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const res = await fetch(`${API_BASE}/neon/preview?table=${table}&limit=50`);
      if (!res.ok) throw new Error(`Failed to load data from ${table}`);
      const data = await res.json();
      setPreviewCache(prev => ({ ...prev, [table]: data }));
    } catch (err: any) {
      if (!hasCache) {
        setError(err.message || "Failed to load data");
      }
    } finally {
      if (!hasCache) {
        setLoading(false);
      }
    }
  };

  const fetchLancePreview = async (collection: string, limit: number, silent = false) => {
    const cacheKey = `${collection}:${limit}`;
    const hasCache = !!lancePreviewCache[cacheKey];
    if (!hasCache && !silent) {
      setLanceLoading(true);
      setLanceError(null);
    }
    try {
      const res = await fetch(`${API_BASE}/lancedb/preview?collection=${collection}&limit=${limit}`);
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(errBody.detail || `Failed to load ${collection}`);
      }
      const data = await res.json();
      const mapped: TableData = { table: data.collection, columns: data.columns, rows: data.rows };
      setLancePreviewCache(prev => ({ ...prev, [cacheKey]: mapped }));
    } catch (err: any) {
      if (!hasCache) {
        setLanceError(err.message || "Failed to load LanceDB collection");
      }
    } finally {
      if (!hasCache) {
        setLanceLoading(false);
      }
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  useEffect(() => {
    if (activeTab === "neon") {
      fetchTablePreview(selectedTable);
    } else if (activeTab === "sync") {
      fetchSyncStatus();
    } else if (activeTab === "lance" && stats?.lancedb_active) {
      fetchLancePreview(selectedLanceCollection, selectedLanceLimit);
    }
  }, [selectedTable, activeTab]);

  // 1. Check once on mount / tab switch to detect if backend is currently syncing
  useEffect(() => {
    const checkInitialSync = async () => {
      try {
        const res = await fetch(`${API_BASE}/sync-progress`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.is_syncing) {
          setSyncProgress({
            visible: true,
            percent: data.percent,
            step: data.step
          });
        }
      } catch (err) {
        console.error("Error checking initial sync:", err);
      }
    };
    
    if (activeTab === "sync") {
      checkInitialSync();
    }
  }, [activeTab]);

  // 2. Poll sync progress from backend ONLY when modal popup is visible
  useEffect(() => {
    if (!syncProgress.visible) return;
    
    let intervalId: any;
    
    const checkProgress = async () => {
      try {
        const res = await fetch(`${API_BASE}/sync-progress`);
        if (!res.ok) return;
        const data = await res.json();
        
        if (data.is_syncing) {
          setSyncProgress({
            visible: true,
            percent: data.percent,
            step: data.step
          });
        } else {
          // Sync finished: reload data, show 100% and auto-close
          fetchStats();
          if (activeTab === "sync") fetchSyncStatus(false);
          else fetchTablePreview(selectedTable, true);
          
          setSyncProgress({ visible: true, percent: 100, step: "Synchronized successfully!" });
          
          setTimeout(() => {
            setSyncProgress({ visible: false, percent: 0, step: "" });
          }, 800);
        }
      } catch (err) {
        console.error("Error fetching sync progress:", err);
      }
    };

    intervalId = setInterval(checkProgress, 1000); // Poll every 1 second

    return () => clearInterval(intervalId);
  }, [syncProgress.visible, activeTab, selectedTable]);

  const handleManualSync = async () => {
    setSyncProgress({ visible: true, percent: 0, step: "Triggering sync..." });
    try {
      const res = await fetch(`${API_BASE}/sync`, { method: "POST" });
      if (!res.ok) throw new Error("Sync failed");
    } catch (err) {
      console.error(err);
      setSyncProgress({ visible: true, percent: 0, step: "Error during synchronization" });
      setTimeout(() => {
        setSyncProgress(prev => ({ ...prev, visible: false }));
      }, 2000);
    }
  };

  const handleRefresh = () => {
    fetchStats();
    if (activeTab === "neon") {
      fetchTablePreview(selectedTable, false); // force loading spinner
    } else if (activeTab === "lance") {
      // bust lance cache then refetch
      setLancePreviewCache({});
      fetchLancePreview(selectedLanceCollection, selectedLanceLimit, false);
    } else if (activeTab === "sync") {
      fetchSyncStatus();
    }
  };

  const previewData = previewCache[selectedTable] || null;
  const lancePreviewKey = `${selectedLanceCollection}:${selectedLanceLimit}`;
  const lancePreviewData = lancePreviewCache[lancePreviewKey] || null;

  const filteredSyncData = syncData.filter(item => {
    const matchesSearch = item.filename.toLowerCase().includes(syncSearch.toLowerCase()) || 
                          item.table_name.toLowerCase().includes(syncSearch.toLowerCase());
    
    if (syncFilter === "synced") {
      return matchesSearch && item.is_up_to_date;
    } else if (syncFilter === "pending") {
      return matchesSearch && !item.is_up_to_date && item.status !== "not_synced";
    } else if (syncFilter === "unsynced") {
      return matchesSearch && item.status === "not_synced";
    }
    return matchesSearch;
  });

  return (
    <div style={{ width: "100%", paddingLeft: "240px", minHeight: "100vh", overflowX: "hidden" }} className="db-inspector-scroll">
      <style>{`
        .db-inspector-scroll::-webkit-scrollbar {
          width: 8px;
          height: 8px;
        }
        .db-inspector-scroll::-webkit-scrollbar-track {
          background: rgba(15, 23, 42, 0.1);
          border-radius: 8px;
        }
        .db-inspector-scroll::-webkit-scrollbar-thumb {
          background: rgba(59, 130, 246, 0.2);
          border-radius: 8px;
          border: 1px solid rgba(255, 255, 255, 0.05);
        }
        .db-inspector-scroll::-webkit-scrollbar-thumb:hover {
          background: rgba(59, 130, 246, 0.35);
        }
      `}</style>
      <div className="px-12 py-8 text-slate-200">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
            Database Inspector 💾
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Verify database storage row counts and preview records in NeonDB and LanceDB.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleManualSync}
            disabled={syncProgress.visible}
            className="px-4 py-2 bg-emerald-600/20 text-emerald-400 border border-emerald-500/40 hover:bg-emerald-600/30 disabled:opacity-50 rounded-lg text-sm font-semibold transition-all flex items-center gap-2"
          >
            ⚡ Sync Now
          </button>
          <button
            onClick={handleRefresh}
            className="p-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:opacity-90 rounded-lg text-md transition-all shadow-[0_0_15px_rgba(59,130,246,0.3)] flex items-center justify-center h-[38px] w-[38px]"
            title="Refresh Data"
          >
            🔄
          </button>
        </div>
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
        <button
          onClick={() => setActiveTab("sync")}
          className={`px-4 py-2 font-semibold text-sm rounded-lg transition-all ${
            activeTab === "sync"
              ? "text-emerald-400 bg-emerald-500/10 shadow-[0_0_10px_rgba(16,185,129,0.15)]"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          CSV vs NeonDB (Sync Monitor)
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
          <div className="flex gap-3 items-center mb-5 bg-slate-900/20 border border-slate-800/60 p-3 rounded-xl max-w-fit backdrop-blur-sm relative z-20">
            <span className="text-sm text-slate-400 font-medium ml-1">📋 Select Table:</span>
            <div className="relative">
              {/* Dropdown Trigger Button */}
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="bg-slate-950/80 border border-slate-700/40 text-slate-200 pl-4 pr-10 py-1.5 rounded-lg focus:outline-none focus:border-blue-500/60 transition-all cursor-pointer text-sm font-semibold hover:bg-slate-900 shadow-inner flex items-center min-w-[280px] text-left"
              >
                <span className="truncate">{currentLabel}</span>
                <span className="absolute right-3 text-slate-500 text-[10px]">
                  {dropdownOpen ? "▲" : "▼"}
                </span>
              </button>

              {/* Dropdown Popup List */}
              {dropdownOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setDropdownOpen(false)} />
                  <div className="absolute left-0 right-0 mt-2 bg-slate-950/95 border border-blue-500/30 rounded-xl shadow-[0_10px_25px_rgba(0,0,0,0.6)] backdrop-blur-xl overflow-hidden z-50 divide-y divide-slate-900/40 py-1">
                    {TABLES_METADATA.map((tbl) => {
                      const isSelected = selectedTable === tbl.value;
                      return (
                        <button
                          key={tbl.value}
                          onClick={() => {
                            setSelectedTable(tbl.value);
                            setDropdownOpen(false);
                          }}
                          className={`w-full text-left px-4 py-2.5 text-sm transition-all flex items-center justify-between ${
                            isSelected
                              ? "bg-blue-500/15 text-blue-400 font-bold border-l-2 border-blue-500"
                              : "text-slate-300 hover:bg-slate-900/70 hover:text-white"
                          }`}
                        >
                          <span>{tbl.label}</span>
                          {isSelected && <span className="text-xs text-blue-400 drop-shadow-[0_0_5px_rgba(59,130,246,0.6)]">●</span>}
                        </button>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Data Grid */}
          <div className="bg-slate-900/30 border border-slate-700/30 rounded-xl overflow-hidden backdrop-blur-md">
            {loading && <div className="p-8 text-center text-slate-400">Loading data from NeonDB...</div>}
            {error && <div className="p-8 text-center text-red-400 font-medium">⚠️ Error: {error}</div>}
            {!loading && !error && previewData && (
              <div className="overflow-auto max-h-[500px] db-inspector-scroll">
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
                            <td key={col} className="p-3 font-mono text-xs text-slate-300">
                              {(() => {
                                const val = row[col];
                                if (val === null) return "NULL";
                                if (typeof val === "boolean") return String(val);
                                
                                const colLower = col.toLowerCase();
                                if (colLower === "time" || colLower.endsWith("_time") || colLower.endsWith("_at")) {
                                  return formatDatabaseDate(String(val));
                                }
                                return String(val);
                              })()}
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
        <div>
          {/* Collections Summary (compact, with ? info) */}
          <div className="glass-card p-6 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md mb-6">
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
                        <td className="py-3 font-semibold text-blue-400">
                          <span className="inline-flex items-center gap-2">
                            {col.name}
                            <button
                              onClick={() => setSelectedCollectionInfo(col.name)}
                              className="text-slate-500 hover:text-purple-300 transition-all text-[11px] font-bold w-5 h-5 rounded-full border border-slate-700 hover:border-purple-500/60 hover:bg-purple-500/10 flex items-center justify-center leading-none"
                              title={`Info about ${col.name}`}
                            >
                              ?
                            </button>
                          </span>
                        </td>
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

          {/* Data Preview (collection picker + limit + table) */}
          {stats?.lancedb_active && (
            <div className="glass-card p-6">
              <h3 className="text-lg font-semibold mb-4">Data Preview</h3>

              {/* Collection + Limit controls */}
              <div className="flex flex-wrap gap-3 items-center mb-5 glass-chip p-3 max-w-fit relative z-20">
                <span className="text-sm text-slate-400 font-medium ml-1">🗂️ Collection:</span>
                <div className="relative">
                  <button
                    onClick={() => setLanceDropdownOpen(!lanceDropdownOpen)}
                    className="bg-slate-950/80 border border-slate-700/40 text-slate-200 pl-4 pr-10 py-1.5 rounded-lg focus:outline-none focus:border-purple-500/60 transition-all cursor-pointer text-sm font-semibold hover:bg-slate-900 shadow-inner flex items-center min-w-[280px] text-left"
                  >
                    <span className="truncate">{currentLanceLabel}</span>
                    <span className="absolute right-3 text-slate-500 text-[10px]">
                      {lanceDropdownOpen ? "▲" : "▼"}
                    </span>
                  </button>

                  {lanceDropdownOpen && (
                    <>
                      <div className="fixed inset-0 z-40" onClick={() => setLanceDropdownOpen(false)} />
                      <div className="absolute left-0 right-0 mt-2 bg-slate-950/95 border border-purple-500/30 rounded-xl shadow-[0_10px_25px_rgba(0,0,0,0.6)] backdrop-blur-xl overflow-hidden z-50 divide-y divide-slate-900/40 py-1">
                        {LANCE_COLLECTIONS_METADATA.map((c) => {
                          const isSelected = selectedLanceCollection === c.value;
                          return (
                            <button
                              key={c.value}
                              onClick={() => {
                                setSelectedLanceCollection(c.value);
                                setLanceDropdownOpen(false);
                              }}
                              className={`w-full text-left px-4 py-2.5 text-sm transition-all flex items-center justify-between ${
                                isSelected
                                  ? "bg-purple-500/15 text-purple-300 font-bold border-l-2 border-purple-500"
                                  : "text-slate-300 hover:bg-slate-900/70 hover:text-white"
                              }`}
                            >
                              <span>{c.label}</span>
                              {isSelected && <span className="text-xs text-purple-300 drop-shadow-[0_0_5px_rgba(139,92,246,0.6)]">●</span>}
                            </button>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>

                <span className="text-sm text-slate-400 font-medium ml-2">🔢 Limit:</span>
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={selectedLanceLimit}
                  onChange={(e) => {
                    const v = parseInt(e.target.value, 10);
                    if (!isNaN(v)) setSelectedLanceLimit(Math.min(500, Math.max(1, v)));
                  }}
                  className="bg-slate-950/80 border border-slate-700/40 text-slate-200 px-3 py-1.5 rounded-lg focus:outline-none focus:border-purple-500/60 transition-all text-sm font-semibold hover:bg-slate-900 shadow-inner w-[100px]"
                />
                <button
                  onClick={() => {
                    setLancePreviewCache({});
                    fetchLancePreview(selectedLanceCollection, selectedLanceLimit, false);
                  }}
                  className="px-3 py-1.5 bg-purple-600/25 text-purple-200 border border-purple-500/50 hover:bg-purple-600/40 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 neon-glow-purple"
                  title="Refresh preview"
                >
                  🔄 Apply
                </button>
              </div>

              {/* Data Grid — flat glass surface, no padding (table flows edge-to-edge) */}
              <div className="bg-[var(--glass-primary)] backdrop-blur-md border border-slate-700/30 rounded-xl overflow-hidden shadow-[0_8px_32px_rgba(0,0,0,0.4)]">
                {lanceLoading && (
                  <div className="p-8 text-center text-slate-400">Loading data from LanceDB...</div>
                )}
                {lanceError && (
                  <div className="p-8 text-center text-red-400 font-medium">⚠️ Error: {lanceError}</div>
                )}
                {!lanceLoading && !lanceError && lancePreviewData && (
                  <div className="overflow-auto max-h-[500px] db-inspector-scroll">
                    <table className="w-full border-collapse text-sm text-left">
                      <thead>
                        <tr className="glass-header">
                          {lancePreviewData.columns.map((col) => (
                            // Vector column is dropped server-side to keep payload small;
                            // header renders plain column names.
                            <th
                              key={col}
                              className="p-3 text-slate-400 font-semibold uppercase text-xs whitespace-nowrap"
                            >
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/40">
                        {lancePreviewData.rows.length === 0 ? (
                          <tr>
                            <td colSpan={lancePreviewData.columns.length} className="p-8 text-center text-slate-500">
                              No rows found in this collection.
                            </td>
                          </tr>
                        ) : (
                          lancePreviewData.rows.map((row, idx) => (
                            <tr key={idx} className="hover:bg-slate-800/20">
                              {lancePreviewData.columns.map((col) => {
                                const val = row[col];
                                let display: string;
                                if (val === null || val === undefined) display = "NULL";
                                else if (typeof val === "boolean") display = String(val);
                                else if (Array.isArray(val)) display = `[${val.map(v => typeof v === "number" ? v.toFixed(4) : String(v)).join(", ")}]`;
                                else display = String(val);
                                return (
                                  <td
                                    key={col}
                                    className="p-3 font-mono text-xs text-slate-300 align-top"
                                  >
                                    {display}
                                  </td>
                                );
                              })}
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
        </div>
      )}

      {/* SYNC MONITOR CONTENT */}
      {activeTab === "sync" && (
        <div>
          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
            <div className="glass-card p-5 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md">
              <span className="text-xs uppercase text-slate-500 font-semibold tracking-wider">Total CSV Files</span>
              <h3 className="text-2xl font-bold text-slate-100 mt-1">
                {syncData.length} <span className="text-xs font-normal text-slate-500">files</span>
              </h3>
            </div>
            <div className="glass-card p-5 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md">
              <span className="text-xs uppercase text-slate-500 font-semibold tracking-wider">Synced (Up to date)</span>
              <h3 className="text-2xl font-bold text-emerald-400 mt-1">
                {syncData.filter(d => d.is_up_to_date).length} <span className="text-xs font-normal text-slate-500">files</span>
              </h3>
            </div>
            <div className="glass-card p-5 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md">
              <span className="text-xs uppercase text-slate-500 font-semibold tracking-wider">Pending updates</span>
              <h3 className="text-2xl font-bold text-amber-400 mt-1">
                {syncData.filter(d => !d.is_up_to_date && d.status !== 'not_synced').length} <span className="text-xs font-normal text-slate-500">files</span>
              </h3>
            </div>
            <div className="glass-card p-5 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md">
              <span className="text-xs uppercase text-slate-500 font-semibold tracking-wider">Not Synced</span>
              <h3 className="text-2xl font-bold text-slate-400 mt-1">
                {syncData.filter(d => d.status === 'not_synced').length} <span className="text-xs font-normal text-slate-500">files</span>
              </h3>
            </div>
          </div>

          {/* Controls: Search and Filters */}
          <div className="flex flex-col md:flex-row gap-4 items-center justify-between mb-5 bg-slate-900/20 border border-slate-800/60 p-4 rounded-xl backdrop-blur-sm">
            <div className="flex items-center gap-3 w-full md:w-auto">
              <span className="text-sm text-slate-400 font-medium whitespace-nowrap">🔍 Search:</span>
              <input
                type="text"
                placeholder="Search CSV files or tables..."
                value={syncSearch}
                onChange={(e) => setSyncSearch(e.target.value)}
                className="bg-slate-950/80 border border-slate-700/40 text-slate-200 px-4 py-1.5 rounded-lg focus:outline-none focus:border-blue-500/60 transition-all text-sm font-semibold hover:bg-slate-900 shadow-inner w-full md:min-w-[280px]"
              />
            </div>
            <div className="flex gap-2 w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
              {["all", "synced", "pending", "unsynced"].map((type) => (
                <button
                  key={type}
                  onClick={() => setSyncFilter(type as any)}
                  className={`px-3 py-1.5 text-xs rounded-lg border font-semibold uppercase transition-all whitespace-nowrap ${
                    syncFilter === type
                      ? "bg-blue-600/20 text-blue-400 border-blue-500/40 shadow-[0_0_10px_rgba(59,130,246,0.1)]"
                      : "bg-slate-800/40 text-slate-400 border-slate-700/30 hover:text-slate-200 hover:bg-slate-800/80"
                  }`}
                >
                  {type === "all" ? "All Files" : type === "synced" ? "Synced" : type === "pending" ? "Pending" : "Not Synced"}
                </button>
              ))}
            </div>
          </div>

          {/* Data Comparison Table */}
          <div className="bg-slate-900/30 border border-slate-700/30 rounded-xl overflow-hidden backdrop-blur-md">
            {syncLoading && syncData.length === 0 && <div className="p-8 text-center text-slate-400">Comparing CSV and Database logs...</div>}
            {(!syncLoading || syncData.length > 0) && (
              <div className="overflow-auto max-h-[500px] db-inspector-scroll">
                <table className="w-full border-collapse text-sm text-left">
                  <thead>
                    <tr className="bg-slate-950/70 border-b border-slate-700/40">
                      <th className="p-3 text-slate-400 font-semibold uppercase text-xs">CSV Filename</th>
                      <th className="p-3 text-slate-400 font-semibold uppercase text-xs">Target Table</th>
                      <th className="p-3 text-slate-400 font-semibold uppercase text-xs text-right">Local Rows (CSV)</th>
                      <th className="p-3 text-slate-400 font-semibold uppercase text-xs text-right">DB Rows (Neon)</th>
                      <th className="p-3 text-slate-400 font-semibold uppercase text-xs text-center">Status</th>
                      <th className="p-3 text-slate-400 font-semibold uppercase text-xs">Last Updated</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/40">
                    {filteredSyncData.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="p-8 text-center text-slate-500">
                          No matching files found.
                        </td>
                      </tr>
                    ) : (
                      filteredSyncData.map((item) => (
                        <tr
                          key={item.filename}
                          onClick={() => handleOpenDiff(item.filename)}
                          className="hover:bg-slate-800/30 transition-all cursor-pointer"
                        >
                          <td className="p-3 font-medium text-slate-200 max-w-[300px] truncate" title={item.filename}>
                            {item.filename}
                          </td>
                          <td className="p-3 font-mono text-xs text-blue-400">
                            {item.table_name}
                          </td>
                          <td className="p-3 text-right font-mono text-slate-300">
                            {item.local_rows.toLocaleString()}
                          </td>
                          <td className="p-3 text-right font-mono text-slate-300">
                            {item.db_rows.toLocaleString()}
                          </td>
                          <td className="p-3 text-center">
                            {item.is_up_to_date ? (
                              <span className="inline-block px-2.5 py-1 text-[10px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-full tracking-wider uppercase">
                                Synced
                              </span>
                            ) : item.status === "not_synced" ? (
                              <span className="inline-block px-2.5 py-1 text-[10px] font-bold text-slate-400 bg-slate-800/50 border border-slate-700/30 rounded-full tracking-wider uppercase">
                                Not Synced
                              </span>
                            ) : (
                              <span className="inline-block px-2.5 py-1 text-[10px] font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-full tracking-wider uppercase animate-pulse">
                                Pending Sync
                              </span>
                            )}
                          </td>
                          <td className="p-3 text-slate-400 font-mono text-xs">
                            {item.loaded_at ? formatDatabaseDate(item.loaded_at) : "-"}
                          </td>
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

      {/* SYNC DIFF MODAL DIALOG */}
      {selectedDiffFile && (
        <div className="fixed inset-0 z-[999] flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in-50 duration-200">
          <div className="fixed inset-0" onClick={() => setSelectedDiffFile(null)} />
          <div className="relative bg-slate-900 border border-slate-700/50 rounded-2xl w-full max-w-5xl max-h-[85vh] flex flex-col overflow-hidden shadow-2xl z-10 animate-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="flex justify-between items-center px-6 py-4 border-b border-slate-800 bg-slate-950/40">
              <div>
                <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                  <span>📊 Sync Difference Detail</span>
                  {diffData?.type === "csv_extra" && (
                    <span className="text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded font-semibold uppercase">
                      Pending Import
                    </span>
                  )}
                  {diffData?.type === "db_extra" && (
                    <span className="text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded font-semibold uppercase">
                      Extra DB Rows
                    </span>
                  )}
                  {diffData?.type === "synced" && (
                    <span className="text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded font-semibold uppercase">
                      Synced
                    </span>
                  )}
                </h3>
                <p className="text-xs text-slate-400 mt-0.5 truncate max-w-[600px]" title={selectedDiffFile}>
                  File: {selectedDiffFile}
                </p>
              </div>
              <button
                onClick={() => setSelectedDiffFile(null)}
                className="text-slate-400 hover:text-white transition-all text-xl font-bold bg-slate-800/40 hover:bg-slate-800 rounded-lg h-8 w-8 flex items-center justify-center"
              >
                &times;
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 p-6 overflow-y-auto min-h-[300px] flex flex-col justify-between">
              {diffLoading && (
                <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-3 py-16">
                  <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm font-semibold">Scanning files and comparing rows...</span>
                </div>
              )}

              {!diffLoading && diffError && (
                <div className="flex-1 flex items-center justify-center">
                  <div className="bg-red-500/10 border border-red-500/20 text-red-300 p-4 rounded-xl text-sm text-center max-w-lg">
                    <div className="font-bold mb-1">Gagal memuat detail perbandingan</div>
                    <div>{diffError}</div>
                  </div>
                </div>
              )}

              {!diffLoading && !diffError && diffData && (
                <div className="space-y-4 flex-1 flex flex-col">
                  {/* Summary Banner */}
                  {diffData.type === "csv_extra" && (
                    <div className="bg-amber-500/10 border border-amber-500/20 text-amber-300 p-4 rounded-xl text-sm flex flex-col gap-1">
                      <span className="font-bold">⚠️ Temuan Selisih: Data Baru di CSV</span>
                      <span>
                        Terdapat <strong>{diffData.count.toLocaleString()} baris</strong> yang hanya ada di CSV dan tidak ada di NeonDB. Tabel di bawah hanya menampilkan selisih tersebut:
                      </span>
                    </div>
                  )}
                  {diffData.type === "db_extra" && (
                    <div className="bg-blue-500/10 border border-blue-500/20 text-blue-300 p-4 rounded-xl text-sm flex flex-col gap-1">
                      <span className="font-bold">ℹ️ Temuan Selisih: Data Lebih Banyak di Database</span>
                      <span>
                        Terdapat <strong>{diffData.count.toLocaleString()} baris</strong> yang hanya ada di NeonDB dan tidak ada di CSV lokal. Tabel di bawah hanya menampilkan selisih tersebut:
                      </span>
                    </div>
                  )}
                  {diffData.type === "synced" && (
                    <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 p-4 rounded-xl text-sm flex flex-col gap-1 text-center py-10">
                      <span className="font-bold text-lg">✅ Sinkronisasi Sempurna</span>
                      <span>Tidak ada baris yang hanya muncul di salah satu sisi. CSV dan NeonDB sudah sama untuk file ini.</span>
                    </div>
                  )}

                  {/* Diff Table */}
                  {diffData.count > 0 && (
                    <div className="border border-slate-700/30 rounded-xl overflow-hidden bg-slate-950/40 flex-1 min-h-[250px] max-h-[400px] flex flex-col">
                      <div className="overflow-auto flex-1 db-inspector-scroll">
                        <table className="w-full border-collapse text-left text-xs">
                          <thead>
                            <tr className="bg-slate-950 sticky top-0 border-b border-slate-800 z-10">
                              <th className="p-2.5 text-slate-500 font-bold uppercase text-[10px] w-12 text-center">Row</th>
                              {diffData.columns.map((col) => (
                                <th key={col} className="p-2.5 text-slate-400 font-semibold uppercase text-[10px] whitespace-nowrap">
                                  {col}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-900/40">
                            {diffData.rows.map((row, idx) => (
                              <tr key={idx} className="hover:bg-slate-900/60 font-mono">
                                <td className="p-2 text-center text-slate-600 bg-slate-950/10">{idx + 1}</td>
                                {diffData.columns.map((col) => {
                                  const val = row[col];
                                  return (
                                    <td key={col} className="p-2 text-slate-300 max-w-[200px] truncate" title={String(val)}>
                                      {val === null ? "NULL" : String(val)}
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="flex justify-end px-6 py-4 border-t border-slate-800 bg-slate-950/30 gap-3">
              <button
                onClick={() => setSelectedDiffFile(null)}
                className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold px-5 py-2 rounded-lg transition-all"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}

      {/* LANCEDB COLLECTION INFO MODAL */}
      {selectedCollectionInfo && (
        <div className="fixed inset-0 z-[999] flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in-50 duration-200">
          <div className="fixed inset-0" onClick={() => setSelectedCollectionInfo(null)} />
          <div className="relative bg-slate-900 border border-purple-500/30 rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden shadow-2xl z-10 animate-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="flex justify-between items-center px-6 py-4 border-b border-slate-800 bg-slate-950/40">
              <div>
                <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                  <span className="text-purple-400">⛁</span>
                  <span className="font-mono text-blue-400">{selectedCollectionInfo}</span>
                  {LANCE_COLLECTIONS_INFO[selectedCollectionInfo] && (
                    <span className="text-xs bg-purple-500/10 text-purple-300 border border-purple-500/20 px-2 py-0.5 rounded font-semibold uppercase">
                      {LANCE_COLLECTIONS_INFO[selectedCollectionInfo].vectorDim}-dim vector
                    </span>
                  )}
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  LanceDB vector collection description
                </p>
              </div>
              <button
                onClick={() => setSelectedCollectionInfo(null)}
                className="text-slate-400 hover:text-white transition-all text-xl font-bold bg-slate-800/40 hover:bg-slate-800 rounded-lg h-8 w-8 flex items-center justify-center"
              >
                &times;
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 p-6 overflow-y-auto min-h-[200px] flex flex-col gap-5">
              {(() => {
                const info = LANCE_COLLECTIONS_INFO[selectedCollectionInfo];
                if (!info) {
                  return (
                    <div className="text-slate-400 text-sm">
                      Tidak ada deskripsi untuk koleksi ini. Cek
                      <code className="mx-1 px-1.5 py-0.5 bg-slate-950 border border-slate-800 rounded text-purple-300 font-mono text-xs">
                        python/valuecell/knowledge/lance_db.py
                      </code>
                      untuk schema lengkap.
                    </div>
                  );
                }
                return (
                  <>
                    <section>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-1.5">Purpose</div>
                      <p className="text-sm text-slate-200 leading-relaxed">{info.purpose}</p>
                    </section>
                    <section>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-1.5">Use Case</div>
                      <p className="text-sm text-slate-300 leading-relaxed">{info.useCase}</p>
                    </section>
                    <section>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-2">Key Fields</div>
                      <div className="flex flex-wrap gap-2">
                        {info.keyFields.map((f) => (
                          <span
                            key={f}
                            className="inline-block px-2.5 py-1 text-[11px] font-mono font-semibold text-blue-300 bg-blue-500/10 border border-blue-500/20 rounded-md"
                          >
                            {f}
                          </span>
                        ))}
                      </div>
                    </section>
                    <section className="bg-slate-950/50 border border-slate-800 rounded-xl p-3 text-[11px] text-slate-500 font-mono">
                      <span className="text-slate-400">source:</span> python/valuecell/knowledge/lance_db.py
                    </section>
                  </>
                );
              })()}
            </div>

            {/* Modal Footer */}
            <div className="flex justify-end px-6 py-4 border-t border-slate-800 bg-slate-950/30">
              <button
                onClick={() => setSelectedCollectionInfo(null)}
                className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold px-5 py-2 rounded-lg transition-all"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Progress popup for Sync Now */}
      {syncProgress.visible && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[9999] backdrop-blur-sm animate-in fade-in duration-100">
          <div className="bg-slate-900 border border-emerald-500/30 rounded-xl p-6 shadow-2xl w-96">
            <div className="text-center mb-4">
              <div className="text-emerald-400 font-semibold text-sm mb-2">
                🔄 Syncing CSV to NeonDB
              </div>
              <div className="text-3xl font-bold text-white mb-1">
                {syncProgress.percent}%
              </div>
              <div className="text-xs text-slate-400">{syncProgress.step}</div>
            </div>
            <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full transition-all duration-200"
                style={{ width: `${syncProgress.percent}%` }}
              />
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
