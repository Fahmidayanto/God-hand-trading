import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Loader2, Database as DatabaseIcon, Zap, RefreshCw, Search, TableProperties, Layers, Hash, Info, ListFilter, AlertTriangle } from "lucide-react";

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
    { value: "news_sentiment_cache", label: "news_sentiment_cache (LLM News Cache)" },
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
    news_sentiment_cache: {
      purpose: "Menyimpan data cache berita dan kalender ekonomi yang didapatkan LLM saat pembentukan HH/LL/BOS.",
      vectorDim: 2,
      keyFields: ["timestamp", "event_type", "news_headlines", "upcoming_events"],
      useCase: "Menghindari pemanggilan API LLM berulang pada replay simulasi dan menyediakan riwayat data berita di DB Inspector secara instan.",
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
    <div style={{ width: "100%", paddingLeft: "240px", minHeight: "100vh", overflowX: "auto" }} className="db-inspector-scroll">
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
          background: rgba(var(--neon-blue-rgb), 0.2);
          border-radius: 8px;
          border: 1px solid rgba(255, 255, 255, 0.05);
        }
        .db-inspector-scroll::-webkit-scrollbar-thumb:hover {
          background: rgba(var(--neon-blue-rgb), 0.35);
        }
      `}</style>
      <div className="px-12 py-8 text-slate-200">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-4">
          <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-white/[0.03] border border-white/[0.08] backdrop-blur-md text-2xl hover:scale-105 transition-transform duration-200 ease-out shadow-[0_0_15px_rgba(var(--neon-blue-rgb),0.15)] select-none">
            💾
          </div>
          <div>
            <h1 className="text-[36px] font-bold text-[var(--text-primary)] leading-none mb-1">
              Database Inspector
            </h1>
            <p className="text-[var(--text-tertiary)] text-base">
              Verify database storage row counts and preview records in NeonDB and LanceDB.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleManualSync}
            disabled={syncProgress.visible}
            className={cn(
              "px-4 py-2 rounded-lg text-sm font-semibold transition-all cursor-pointer active:scale-95 duration-100 flex items-center gap-2 border disabled:opacity-50",
              syncProgress.visible
                ? "bg-emerald-600/10 text-emerald-400 border-emerald-500/25"
                : "bg-emerald-500/10 text-emerald-400 border-emerald-500/35 hover:bg-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.15)] hover:shadow-[0_0_22px_rgba(16,185,129,0.35)] animate-pulse"
            )}
          >
            {syncProgress.visible ? (
              <Loader2 className="w-4 h-4 text-emerald-400 animate-spin" />
            ) : (
              <Zap className="w-4 h-4 text-emerald-400" />
            )}
            <span>Sync Now</span>
          </button>
          <button
            onClick={handleRefresh}
            className="p-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:opacity-90 rounded-lg text-md transition-all active:scale-95 duration-100 cursor-pointer shadow-[0_0_15px_rgba(59,130,246,0.3)] flex items-center justify-center h-[38px] w-[38px]"
            title="Refresh Data"
          >
            <RefreshCw className="w-4 h-4 text-white hover:rotate-180 duration-500 transition-all" />
          </button>
        </div>
      </div>

      {/* Tab Selection */}
      <div className="flex mb-6 max-w-fit">
        <div className="inline-flex p-0.5 bg-[rgba(15,23,42,0.6)] border border-slate-800/60 rounded-xl overflow-hidden shadow-inner">
          <button
            onClick={() => setActiveTab("neon")}
            className={cn(
              "px-4 py-2.5 font-semibold text-xs rounded-lg transition-all duration-200 cursor-pointer active:scale-95",
              activeTab === "neon"
                ? "bg-[rgba(59,130,246,0.15)] text-blue-400 border border-blue-500/25 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            )}
          >
            NeonDB (PostgreSQL)
          </button>
          <button
            onClick={() => setActiveTab("lance")}
            className={cn(
              "px-4 py-2.5 font-semibold text-xs rounded-lg transition-all duration-200 cursor-pointer active:scale-95",
              activeTab === "lance"
                ? "bg-[rgba(139,92,246,0.15)] text-purple-400 border border-purple-500/25 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            )}
          >
            LanceDB (Vector Database)
          </button>
          <button
            onClick={() => setActiveTab("sync")}
            className={cn(
              "px-4 py-2.5 font-semibold text-xs rounded-lg transition-all duration-200 cursor-pointer active:scale-95",
              activeTab === "sync"
                ? "bg-[rgba(16,185,129,0.15)] text-emerald-400 border border-emerald-500/25 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            )}
          >
            CSV vs NeonDB (Sync Monitor)
          </button>
        </div>
      </div>

      {/* NEON DB CONTENT */}
      {activeTab === "neon" && (
        <div>
          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <div className="glass-card p-5 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(0,0,0,0.5)] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-all duration-300">
              <span className="text-[9px] uppercase text-slate-500 font-semibold tracking-wider mb-1 block">
                Total Swing Events
              </span>
              <h3 className="text-2xl font-bold font-mono text-slate-100 mt-1">
                {(stats?.neon_stats.llhhbosdata_xauusd ?? 0).toLocaleString()}{" "}
                <span className="text-xs font-normal text-slate-500">rows</span>
              </h3>
            </div>
            <div className="glass-card p-5 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(0,0,0,0.5)] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-all duration-300">
              <span className="text-[9px] uppercase text-slate-500 font-semibold tracking-wider mb-1 block">
                Total Trade Records
              </span>
              <h3 className="text-2xl font-bold font-mono text-slate-100 mt-1">
                {(stats?.neon_stats.backtest_results_xauusd ?? 0).toLocaleString()}{" "}
                <span className="text-xs font-normal text-slate-500">rows</span>
              </h3>
            </div>
            <div className="glass-card p-5 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(0,0,0,0.5)] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-all duration-300">
              <span className="text-[9px] uppercase text-slate-500 font-semibold tracking-wider mb-1 block">
                File Import Watcher Log
              </span>
              <h3 className="text-2xl font-bold font-mono text-slate-100 mt-1">
                {(stats?.neon_stats.csv_load_log ?? 0).toLocaleString()}{" "}
                <span className="text-xs font-normal text-slate-500">records</span>
              </h3>
            </div>
          </div>

          <div className="flex gap-3 items-center mb-5 bg-slate-900/20 border border-slate-800/60 p-3 rounded-xl max-w-fit backdrop-blur-sm relative z-20">
            <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider ml-1 flex items-center gap-1.5">
              <TableProperties className="w-3.5 h-3.5 text-slate-400" />
              <span>Select Table:</span>
            </span>
            <div className="relative">
              {/* Dropdown Trigger Button */}
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="bg-slate-950/80 border border-slate-700/40 text-slate-200 pl-4 pr-10 py-1.5 rounded-lg focus:outline-none focus:border-blue-500/60 transition-all active:scale-95 duration-100 cursor-pointer text-sm font-semibold hover:bg-slate-900 shadow-inner flex items-center min-w-[280px] text-left"
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
                  <div className="absolute left-0 right-0 mt-2 bg-slate-950/95 border border-blue-500/30 rounded-xl shadow-[0_10px_25px_rgba(0,0,0,0.6)] backdrop-blur-xl overflow-hidden z-50 divide-y divide-slate-900/40 py-1 animate-in fade-in zoom-in-95 slide-in-from-top-2 duration-150 ease-out origin-top-left">
                    {TABLES_METADATA.map((tbl) => {
                      const isSelected = selectedTable === tbl.value;
                      return (
                        <button
                          key={tbl.value}
                          onClick={() => {
                            setSelectedTable(tbl.value);
                            setDropdownOpen(false);
                          }}
                          className={`w-full text-left px-4 py-2.5 text-sm transition-all flex items-center justify-between cursor-pointer ${
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
          <div className="bg-[rgba(15,23,42,0.45)] border border-slate-800/80 rounded-xl overflow-hidden backdrop-blur-md shadow-[inset_0_1px_0_rgba(255,255,255,0.03),_0_20px_50px_rgba(0,0,0,0.5)]">
            {loading && <div className="p-8 text-center text-slate-400">Loading data from NeonDB...</div>}
            {error && <div className="p-8 text-center text-red-400 font-medium">⚠️ Error: {error}</div>}
            {!loading && !error && previewData && (
              <div className="overflow-auto max-h-[500px] db-inspector-scroll">
                <table className="w-full border-collapse text-sm text-left">
                  <thead>
                    <tr className="bg-[rgba(10,15,30,0.65)] border-b border-slate-800/80">
                      {previewData.columns.map((col) => (
                        <th key={col} className="p-3.5 text-slate-500 font-semibold uppercase text-[9px] tracking-wider whitespace-nowrap">
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
                        <tr key={idx} className="group hover:bg-blue-500/5 transition-colors duration-150">
                          {previewData.columns.map((col, cIdx) => (
                            <td 
                              key={col} 
                              className={cn(
                                "p-3 font-mono text-xs text-slate-300 align-middle max-w-[280px] truncate",
                                cIdx === 0 && "border-l-2 border-l-transparent group-hover:border-l-blue-500 pl-3 transition-all"
                              )}
                            >
                              {(() => {
                                const val = row[col];
                                if (val === null) {
                                  return <span className="text-slate-600 font-semibold italic">NULL</span>;
                                }
                                if (typeof val === "boolean") {
                                  return <span className="text-cyan-400 font-semibold">{String(val)}</span>;
                                }
                                
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
          {/* Collections Summary (compact, with info button) */}
          <div className="glass-card p-6 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md mb-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
            <h3 className="text-lg font-semibold mb-4 text-slate-100 flex items-center gap-2">
              <Layers className="w-5 h-5 text-purple-400" />
              <span>LanceDB Vector Collections Summary</span>
            </h3>
            {stats?.lancedb_active ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-500">
                      <th className="py-2.5 px-3 text-[10px] uppercase tracking-wider font-semibold">Collection Name</th>
                      <th className="py-2.5 px-3 text-[10px] uppercase tracking-wider font-semibold">Total Vector Records</th>
                      <th className="py-2.5 px-3 text-[10px] uppercase tracking-wider font-semibold">Type</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/40">
                    {stats.lancedb_collections.map((col) => (
                      <tr key={col.name} className="group hover:bg-purple-950/10 transition-colors duration-200">
                        <td className="py-3 px-3 font-semibold text-blue-400 border-l-2 border-l-transparent group-hover:border-l-purple-500 pl-3 transition-all">
                          <span className="inline-flex items-center gap-2.5">
                            {col.name}
                            <button
                              onClick={() => setSelectedCollectionInfo(col.name)}
                              className="text-purple-400 hover:text-white transition-all text-[10px] w-5 h-5 rounded-full border border-purple-500/20 hover:border-purple-500/60 bg-purple-500/10 hover:bg-purple-500/35 flex items-center justify-center cursor-pointer active:scale-95 duration-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]"
                              title={`Info tentang ${col.name}`}
                            >
                              <Info className="w-3 h-3 text-purple-400 hover:text-white transition-colors" />
                            </button>
                          </span>
                        </td>
                        <td className="py-3 px-3 font-mono text-slate-300">
                          {col.count.toLocaleString()} vectors
                        </td>
                        <td className="py-3 px-3 text-slate-500">
                          <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold uppercase bg-purple-500/10 text-purple-400 border border-purple-500/15">
                            Vector Store
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 bg-slate-950/30 rounded-xl border border-dashed border-red-500/30 text-center flex flex-col items-center justify-center gap-2 max-w-xl mx-auto my-4 shadow-[0_0_20px_rgba(239,68,68,0.05)]">
                <AlertTriangle className="w-8 h-8 text-red-500 animate-bounce" />
                <p className="text-slate-200 font-bold text-sm">LanceDB tidak terdeteksi atau belum aktif</p>
                <p className="text-xs text-slate-500 max-w-sm leading-relaxed">
                  Track 1 saat ini dinonaktifkan di backend, sehingga database vektor tidak diinisialisasi untuk sesi ini.
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
                <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider ml-1 flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-purple-400" />
                  <span>Collection:</span>
                </span>
                <div className="relative">
                  <button
                    onClick={() => setLanceDropdownOpen(!lanceDropdownOpen)}
                    className="bg-slate-950/80 border border-slate-700/40 text-slate-200 pl-4 pr-10 py-1.5 rounded-lg focus:outline-none focus:border-purple-500/60 transition-all active:scale-95 duration-100 cursor-pointer text-sm font-semibold hover:bg-slate-900 shadow-inner flex items-center min-w-[280px] text-left"
                  >
                    <span className="truncate">{currentLanceLabel}</span>
                    <span className="absolute right-3 text-slate-500 text-[10px]">
                      {lanceDropdownOpen ? "▲" : "▼"}
                    </span>
                  </button>

                  {lanceDropdownOpen && (
                    <>
                      <div className="fixed inset-0 z-40" onClick={() => setLanceDropdownOpen(false)} />
                      <div className="absolute left-0 right-0 mt-2 bg-slate-950/95 border border-purple-500/30 rounded-xl shadow-[0_10px_25px_rgba(0,0,0,0.6)] backdrop-blur-xl overflow-hidden z-50 divide-y divide-slate-900/40 py-1 animate-in fade-in zoom-in-95 slide-in-from-top-2 duration-150 ease-out origin-top-left">
                        {LANCE_COLLECTIONS_METADATA.map((c) => {
                          const isSelected = selectedLanceCollection === c.value;
                          return (
                            <button
                              key={c.value}
                              onClick={() => {
                                setSelectedLanceCollection(c.value);
                                setLanceDropdownOpen(false);
                              }}
                              className={`w-full text-left px-4 py-2.5 text-sm transition-all flex items-center justify-between cursor-pointer ${
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

                <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider ml-2 flex items-center gap-1.5">
                  <Hash className="w-3.5 h-3.5 text-slate-400" />
                  <span>Limit:</span>
                </span>
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
                  className="px-3 py-1.5 bg-purple-600/25 text-purple-200 border border-purple-500/50 hover:bg-purple-600/40 rounded-lg text-xs font-semibold transition-all active:scale-95 duration-100 cursor-pointer flex items-center gap-1.5 neon-glow-purple"
                  title="Refresh preview"
                >
                  <RefreshCw className="w-3 h-3 text-purple-200" />
                  <span>Apply</span>
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
                                const isArray = Array.isArray(val);
                                return (
                                  <td
                                    key={col}
                                    className="p-3 font-mono text-xs text-slate-300 align-top max-w-[280px]"
                                  >
                                    {val === null || val === undefined ? (
                                      <span className="text-slate-600">NULL</span>
                                    ) : typeof val === "boolean" ? (
                                      <span className="text-cyan-400">{String(val)}</span>
                                    ) : isArray ? (
                                      <div className="flex flex-wrap gap-1 max-h-[72px] overflow-y-auto elegant-scrollbar py-0.5">
                                        {val.map((v, i) => {
                                          const numVal = typeof v === "number" ? v.toFixed(4) : String(v);
                                          return (
                                            <span 
                                              key={i} 
                                              className="inline-block px-1.5 py-0.5 rounded bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 border border-purple-500/15 text-[10px] transition-all hover:scale-105"
                                            >
                                              {numVal}
                                            </span>
                                          );
                                        })}
                                      </div>
                                    ) : (
                                      <span className="truncate block" title={String(val)}>{String(val)}</span>
                                    )}
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
            <div className="glass-card p-5 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(0,0,0,0.5)] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-all duration-300">
              <span className="text-[9px] uppercase text-slate-500 font-semibold tracking-wider mb-1 block">Total CSV Files</span>
              <h3 className="text-2xl font-bold font-mono text-slate-100 mt-1">
                {syncData.length} <span className="text-xs font-normal text-slate-500">files</span>
              </h3>
            </div>
            <div className="glass-card p-5 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(0,0,0,0.5)] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-all duration-300">
              <span className="text-[9px] uppercase text-slate-500 font-semibold tracking-wider mb-1 block">Synced (Up to date)</span>
              <h3 className="text-2xl font-bold font-mono text-emerald-400 mt-1">
                {syncData.filter(d => d.is_up_to_date).length} <span className="text-xs font-normal text-slate-500">files</span>
              </h3>
            </div>
            <div className="glass-card p-5 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(0,0,0,0.5)] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-all duration-300">
              <span className="text-[9px] uppercase text-slate-500 font-semibold tracking-wider mb-1 block">Pending updates</span>
              <h3 className="text-2xl font-bold font-mono text-amber-400 mt-1">
                {syncData.filter(d => !d.is_up_to_date && d.status !== 'not_synced').length} <span className="text-xs font-normal text-slate-500">files</span>
              </h3>
            </div>
            <div className="glass-card p-5 border border-slate-700/30 rounded-xl bg-slate-900/40 backdrop-blur-md hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(0,0,0,0.5)] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-all duration-300">
              <span className="text-[9px] uppercase text-slate-500 font-semibold tracking-wider mb-1 block">Not Synced</span>
              <h3 className="text-2xl font-bold font-mono text-slate-400 mt-1">
                {syncData.filter(d => d.status === 'not_synced').length} <span className="text-xs font-normal text-slate-500">files</span>
              </h3>
            </div>
          </div>

          {/* Controls: Search and Filters */}
          <div className="flex flex-col md:flex-row gap-4 items-center justify-between mb-5 bg-slate-900/20 border border-slate-800/60 p-4 rounded-xl backdrop-blur-sm">
            <div className="flex items-center gap-3 w-full md:w-auto">
              <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider whitespace-nowrap flex items-center gap-1.5">
                <Search className="w-3.5 h-3.5 text-slate-400" />
                <span>Search:</span>
              </span>
              <input
                type="text"
                placeholder="Search CSV files or tables..."
                value={syncSearch}
                onChange={(e) => setSyncSearch(e.target.value)}
                className="bg-slate-950/80 border border-slate-700/40 text-slate-200 px-4 py-1.5 rounded-lg focus:outline-none focus:border-blue-500/60 transition-all text-sm font-semibold hover:bg-slate-900 shadow-inner w-full md:min-w-[280px]"
              />
            </div>
            <div className="inline-flex p-0.5 bg-[rgba(15,23,42,0.6)] border border-slate-800/60 rounded-xl overflow-hidden shadow-inner">
              {["all", "synced", "pending", "unsynced"].map((type) => (
                <button
                  key={type}
                  onClick={() => setSyncFilter(type as any)}
                  className={cn(
                    "px-3 py-1.5 text-xs rounded-lg font-semibold uppercase transition-all whitespace-nowrap cursor-pointer active:scale-95 duration-100",
                    syncFilter === type
                      ? "bg-[rgba(59,130,246,0.15)] text-blue-400 border border-blue-500/25 shadow-sm"
                      : "text-slate-400 hover:text-slate-200"
                  )}
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
        <div className="fixed inset-0 z-[999] flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-md animate-in fade-in duration-300">
          <div className="fixed inset-0" onClick={() => setSelectedDiffFile(null)} />
          <div 
            className="relative bg-slate-900/95 border border-slate-800 rounded-2xl w-full max-w-5xl max-h-[85vh] flex flex-col overflow-hidden shadow-[inset_0_1px_0_rgba(255,255,255,0.05),_0_25px_60px_rgba(0,0,0,0.8)] z-10 transform perspective-1000 rotate-x-4 animate-in zoom-in-95 duration-250 ease-out"
            style={{ transformStyle: "preserve-3d" }}
          >
            {/* Modal Header */}
            <div className="flex justify-between items-center px-6 py-4 border-b border-slate-800 bg-slate-950/40">
              <div>
                <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                  <TableProperties className="w-5 h-5 text-blue-400" />
                  <span>Sync Difference Detail</span>
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
                <p className="text-[10px] font-mono text-slate-500 mt-0.5 truncate max-w-[600px]" title={selectedDiffFile}>
                  File: {selectedDiffFile}
                </p>
              </div>
              <button
                onClick={() => setSelectedDiffFile(null)}
                className="text-slate-400 hover:text-white transition-all text-xl font-bold bg-slate-800/40 hover:bg-slate-800 rounded-lg h-8 w-8 flex items-center justify-center cursor-pointer active:scale-95 duration-100"
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
        <div className="fixed inset-0 z-[999] flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-md animate-in fade-in duration-300">
          <div className="fixed inset-0" onClick={() => setSelectedCollectionInfo(null)} />
          <div 
            className="relative bg-slate-900/95 border border-purple-500/25 rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden shadow-[inset_0_1px_0_rgba(255,255,255,0.05),_0_25px_60px_rgba(0,0,0,0.8),_0_0_40px_rgba(168,85,247,0.12)] z-10 transform perspective-1000 rotate-x-4 animate-in zoom-in-95 duration-250 ease-out"
            style={{ transformStyle: "preserve-3d" }}
          >
            {/* Modal Header */}
            <div className="flex justify-between items-center px-6 py-4 border-b border-slate-800 bg-slate-950/40">
              <div>
                <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                  <Layers className="w-5 h-5 text-purple-400" />
                  <span className="font-mono text-blue-400">{selectedCollectionInfo}</span>
                  {LANCE_COLLECTIONS_INFO[selectedCollectionInfo] && (
                    <span className="text-xs bg-purple-500/10 text-purple-300 border border-purple-500/20 px-2 py-0.5 rounded font-semibold uppercase">
                      {LANCE_COLLECTIONS_INFO[selectedCollectionInfo].vectorDim}-dim vector
                    </span>
                  )}
                </h3>
                <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider mt-0.5">
                  LanceDB vector collection description
                </p>
              </div>
              <button
                onClick={() => setSelectedCollectionInfo(null)}
                className="text-slate-400 hover:text-white transition-all text-xl font-bold bg-slate-800/40 hover:bg-slate-800 rounded-lg h-8 w-8 flex items-center justify-center cursor-pointer active:scale-95 duration-100"
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
        <div className="fixed inset-0 bg-slate-950/85 backdrop-blur-md flex items-center justify-center z-[9999] animate-in fade-in duration-300">
          <div 
            className="bg-slate-900/90 border border-emerald-500/25 rounded-2xl p-6 w-96 shadow-[inset_0_1px_0_rgba(255,255,255,0.1),_0_25px_60px_rgba(0,0,0,0.8),_0_0_45px_rgba(16,185,129,0.18)] transform perspective-1000 rotate-x-6 animate-in zoom-in-90 duration-350 ease-out"
            style={{ transformStyle: "preserve-3d" }}
          >
            <div className="flex flex-col items-center justify-center text-center mb-5">
              <div className="relative flex items-center justify-center w-12 h-12 mb-3 bg-emerald-500/10 rounded-full border border-emerald-500/25 shadow-[0_0_15px_rgba(16,185,129,0.2)]">
                <Loader2 className="w-6 h-6 text-emerald-400 animate-spin" />
              </div>
              <div className="text-emerald-400 font-semibold text-xs tracking-wider uppercase mb-1">
                Syncing CSV to NeonDB
              </div>
              <div className="text-3xl font-mono font-bold text-white mb-1 shadow-sm">
                {syncProgress.percent}%
              </div>
              <div className="text-[10px] font-medium text-slate-400 max-w-[240px] truncate">{syncProgress.step}</div>
            </div>
            <div className="w-full h-3 bg-slate-950/80 border border-slate-800/40 rounded-full shadow-[inset_0_2px_4px_rgba(0,0,0,0.8)] relative overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 rounded-full transition-all duration-150 shadow-[0_0_12px_rgba(16,185,129,0.5)] relative overflow-hidden"
                style={{ width: `${syncProgress.percent}%` }}
              >
                {/* cylindrical light reflection gloss overlay */}
                <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.15),transparent)]" />
              </div>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
