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
                            <td key={col} className="p-3 font-mono text-xs text-slate-300">
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
