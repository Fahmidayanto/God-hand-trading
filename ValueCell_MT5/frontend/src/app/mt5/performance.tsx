import { useEffect, useRef, useState } from "react";
import Particles from "@tsparticles/react";
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  Target,
  Trophy,
  Activity,
  Gauge,
  Scale,
  Calendar,
  CalendarDays,
  Layers,
  RotateCcw,
  DollarSign,
  ArrowDownRight,
  X,
  Loader2,
  BarChart3,
  CircleDollarSign,
  ClipboardList,
} from "lucide-react";
import MT5Footer from "./components/MT5Footer";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { Line, Doughnut, Bar } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface MonthlyPNLData {
  month: string;
  year: number;
  month_num: number;
  month_label: string;
  trades: number;
  executed_trades: number;
  profit: number;
  loss: number;
  net_profit: number;
  win_rate: number;
  winning_trades: number;
  losing_trades: number;
}

export default function PerformancePage() {
  const pageRef = useRef<HTMLDivElement>(null);
  const [monthlyPNL, setMonthlyPNL] = useState<MonthlyPNLData[]>([]);
  const [availableYears, setAvailableYears] = useState<number[]>([]);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
  const [isYearOpen, setIsYearOpen] = useState(false);
  const [isMonthOpen, setIsMonthOpen] = useState(false);
  const yearDropdownRef = useRef<HTMLDivElement>(null);
  const monthDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (yearDropdownRef.current && !yearDropdownRef.current.contains(event.target as Node)) {
        setIsYearOpen(false);
      }
      if (monthDropdownRef.current && !monthDropdownRef.current.contains(event.target as Node)) {
        setIsMonthOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const [initialBalance, setInitialBalance] = useState<number>(1000);
  const [summary, setSummary] = useState<{
    max_drawdown: number; profit_factor: number; win_rate: number;
  }>({ max_drawdown: 0, profit_factor: 0, win_rate: 0 });

  // Pop-up states
  const [selectedMonthTrades, setSelectedMonthTrades] = useState<any[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalTitle, setModalTitle] = useState("");
  const [isLoadingTrades, setIsLoadingTrades] = useState(false);

  const handleMonthRowClick = async (year: number, monthNum: number, monthLabel: string) => {
    setIsLoadingTrades(true);
    setModalTitle(monthLabel);
    setIsModalOpen(true);
    setSelectedMonthTrades([]);
    
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const response = await fetch(`${apiUrl}/performance/backtest/monthly-trades?year=${year}&month=${monthNum}`);
      if (response.ok) {
        const result = await response.json();
        setSelectedMonthTrades(result.data || []);
      }
    } catch (error) {
      console.error("Error loading monthly trades:", error);
    } finally {
      setIsLoadingTrades(false);
    }
  };

  useEffect(() => {
    loadAvailableYears();
    loadPerformanceData();
    const interval = setInterval(loadPerformanceData, 10000);
    return () => clearInterval(interval);
  }, [selectedYear, selectedMonth]);

  const loadAvailableYears = async () => {
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const response = await fetch(`${apiUrl}/performance/backtest/available-years`);
      if (response.ok) {
        const data = await response.json();
        setAvailableYears(data.years || []);
      }
    } catch (error) {
      console.error("Error loading available years:", error);
    }
  };

  const loadPerformanceData = async () => {
    if (!pageRef.current?.offsetParent) return;
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const params = new URLSearchParams();
      if (selectedYear) params.append('year', selectedYear.toString());
      if (selectedMonth) params.append('month', selectedMonth.toString());
      const queryString = params.toString() ? '?' + params.toString() : '';

      // Summary metrics from Backtest_Summary CSVs (real drawdown / profit factor)
      const summaryResponse = await fetch(
        `${apiUrl}/performance/backtest/summary${queryString}`
      );
      if (summaryResponse.ok) {
        const s = await summaryResponse.json();
        setSummary({
          max_drawdown: s.max_drawdown ?? 0,
          profit_factor: s.profit_factor ?? 0,
          win_rate: s.win_rate ?? 0,
        });
      }

      const monthlyPNLResponse = await fetch(
        `${apiUrl}/performance/monthly-pnl${queryString}`
      );
      if (monthlyPNLResponse.ok) {
        const res = await monthlyPNLResponse.json();
        setMonthlyPNL(res.data && Array.isArray(res.data) ? res.data : []);
      }
    } catch (error) {
      console.error("Error loading performance data:", error);
    }
  };

  // ponytail: all derived from monthlyPNL — no dead /backtest/* endpoints needed

  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  // Cumulative equity curve from monthlyPNL
  const equityCurve: number[] = [];
  let cumPnl = 0;
  for (const m of monthlyPNL) {
    cumPnl += m.net_profit ?? 0;
    equityCurve.push(initialBalance + cumPnl);
  }
  const finalEquity = equityCurve.length > 0 ? equityCurve[equityCurve.length - 1] : initialBalance;

  // Stats derived from monthlyPNL
  const totalTrades = monthlyPNL.reduce((s, m) => s + (m.executed_trades ?? 0), 0);
  const totalWinTrades = monthlyPNL.reduce((s, m) => s + (m.winning_trades ?? 0), 0);
  const totalLoseTrades = monthlyPNL.reduce((s, m) => s + (m.losing_trades ?? 0), 0);
  const totalProfit = monthlyPNL.reduce((s, m) => s + (m.profit ?? 0), 0);
  const totalLoss = Math.abs(monthlyPNL.reduce((s, m) => s + (m.loss ?? 0), 0));
  const avgWin = totalWinTrades > 0 ? totalProfit / totalWinTrades : 0;
  const avgLoss = totalLoseTrades > 0 ? totalLoss / totalLoseTrades : 0;

  const stats = {
    total_return: initialBalance > 0 ? ((finalEquity - initialBalance) / initialBalance) * 100 : 0,
    win_rate: totalTrades > 0 ? (totalWinTrades / totalTrades) * 100 : 0,
    // ponytail: PF and drawdown from Backtest_Summary CSV (real), sharpe needs daily equity
    profit_factor: summary.profit_factor,
    sharpe_ratio: 0,
    avg_win: avgWin,
    avg_loss: avgLoss,
    max_drawdown: summary.max_drawdown,
  };

  const chartLabels = monthlyPNL.map(m => m.month_label ?? `${monthNames[(m.month_num ?? 1) - 1] ?? ''} ${m.year ?? ''}`);

  const equityData = {
    labels: chartLabels,
    datasets: [
      {
        label: "Equity",
        data: equityCurve,
        borderColor: "#10b981",
        backgroundColor: "rgba(16, 185, 129, 0.1)",
        borderWidth: 3,
        fill: true,
        tension: 0.4,
      },
    ],
  };

  const winLossData = {
    labels: ["Wins", "Losses"],
    datasets: [
      {
        data: [totalWinTrades, totalLoseTrades],
        backgroundColor: ["#10b981", "#ef4444"],
        borderWidth: 0,
      },
    ],
  };

  const monthlyReturnsData = {
    labels: chartLabels,
    datasets: [
      {
        label: "Monthly Return %",
        data: monthlyPNL.map(m => {
          const equity = m.net_profit ?? 0;
          return initialBalance > 0 ? (equity / initialBalance) * 100 : 0;
        }),
        backgroundColor: "#3b82f6",
        borderRadius: 8,
      },
    ],
  };

  const drawdownData = {
    labels: chartLabels,
    datasets: [
      {
        label: "Drawdown %",
        data: (() => {
          let peakEq = initialBalance, cum = 0;
          const drawdowns: number[] = [];
          for (const m of monthlyPNL) {
            cum += m.net_profit ?? 0;
            const eq = initialBalance + cum;
            peakEq = Math.max(peakEq, eq);
            drawdowns.push(peakEq > 0 ? ((eq - peakEq) / peakEq) * 100 : 0);
          }
          return drawdowns;
        })(),
        borderColor: "#ef4444",
        backgroundColor: "rgba(239, 68, 68, 0.1)",
        borderWidth: 2,
        fill: true,
        tension: 0.4,
      },
    ],
  };

  const monthlyProfitLossData = {
    labels: chartLabels,
    datasets: [
      {
        label: "Profit",
        data: monthlyPNL.map(m => Math.max(0, m.profit ?? 0)),
        backgroundColor: "#10b981",
        borderRadius: 6,
        borderSkipped: false,
      },
      {
        label: "Loss",
        data: monthlyPNL.map(m => Math.min(0, m.loss ?? 0)),
        backgroundColor: "#ef4444",
        borderRadius: 6,
        borderSkipped: false,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "rgba(17, 24, 39, 0.9)",
        titleColor: "#f8fafc",
        bodyColor: "#cbd5e1",
        borderColor: "#3b82f6",
        borderWidth: 1,
      },
    },
    scales: {
      y: {
        grid: { color: "rgba(100, 116, 139, 0.1)" },
        ticks: { color: "#94a3b8", font: { size: 12 } },
      },
      x: {
        grid: { color: "rgba(100, 116, 139, 0.1)" },
        ticks: {
          color: "#94a3b8",
          font: { size: 11 },
          maxRotation: 0,
          minRotation: 0,
          autoSkip: true,
          maxTicksLimit: 24,
        },
      },
    },
  };

  return (
    <div
      ref={pageRef}
      style={{ 
        background: "var(--bg-deepspace)",
        minHeight: "100vh",
        width: "100%",
        position: "relative",
        overflowX: "auto",
        overflowY: "auto"
      }}
    >
      <Particles
        id="tsparticles-performance"
        options={{
            background: { color: { value: "transparent" } },
            fpsLimit: 60,
            particles: {
              number: { value: 80, density: { enable: true } },
              color: { value: "#3b82f6" },
              shape: { type: "circle" },
              opacity: { value: 0.3 },
              size: { value: { min: 1, max: 3 } },
              links: {
                enable: true,
                distance: 150,
                color: "#3b82f6",
                opacity: 0.2,
                width: 1,
              },
              move: {
                enable: true,
                speed: 1,
                direction: "none",
                outModes: { default: "out" },
              },
            },
            interactivity: {
              events: {
                onHover: { enable: true, mode: "grab" },
                onClick: { enable: true, mode: "push" },
              },
              modes: {
                grab: { distance: 140, links: { opacity: 0.5 } },
                push: { quantity: 4 },
              },
            },
          }}
          className="fixed inset-0 pointer-events-none"
          style={{ zIndex: 0 }}
        />

      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          zIndex: 1,
          background:
            "radial-gradient(circle at 20% 50%, rgba(59, 130, 246, 0.15) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(139, 92, 246, 0.15) 0%, transparent 50%), radial-gradient(circle at 50% 80%, rgba(16, 185, 129, 0.1) 0%, transparent 50%), var(--bg-deepspace)",
        }}
      />

      <div 
        className="relative z-10" 
        style={{ 
          width: "100%",
          paddingLeft: "240px", // Space for sidebar (exact sidebar width)
          minHeight: "100vh"
        }}
      >
        <div className="px-12 py-8">

        {/* Page Header */}
        <div className="flex items-center gap-4 mb-8">
          <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-white/[0.03] border border-white/[0.08] backdrop-blur-md hover:scale-105 transition-transform duration-200 ease-out shadow-[0_0_15px_rgba(var(--neon-blue-rgb),0.15)] select-none">
            <TrendingUp size={26} aria-hidden="true" className="text-[var(--text-primary)]" />
          </div>
          <div>
            <h1 className="text-[36px] font-bold text-[var(--text-primary)] leading-none mb-1">
              Performance Analytics
            </h1>
            <p className="text-[var(--text-tertiary)] text-base">
              Comprehensive trading performance metrics and analysis
            </p>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="mb-6">
          <div className="glass-card !p-5 !mb-0 relative overflow-visible z-[40]">
            {/* Decorative gradient glow */}
            <div
              className="absolute -top-24 -right-24 w-64 h-64 rounded-full pointer-events-none"
              style={{
                background:
                  "radial-gradient(circle, rgba(59,130,246,0.18) 0%, transparent 70%)",
              }}
            />
            <div
              className="absolute -bottom-24 -left-24 w-64 h-64 rounded-full pointer-events-none"
              style={{
                background:
                  "radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%)",
              }}
            />

            <div className="relative flex flex-wrap gap-4 items-end">
              {/* Year */}
              <div className="flex flex-col gap-2 min-w-[160px] flex-1" ref={yearDropdownRef}>
                <label className="flex items-center gap-2 text-[11px] text-[var(--text-tertiary)] uppercase tracking-[0.15em] font-semibold">
                  <Calendar className="w-3.5 h-3.5 text-[var(--neon-cyan)]" />
                  Year
                </label>
                <div className="relative group">
                  <button
                    onClick={() => {
                      setIsYearOpen(!isYearOpen);
                      setIsMonthOpen(false);
                    }}
                    className="w-full text-left pl-11 pr-10 py-2.5 bg-[rgba(15,23,42,0.4)] backdrop-blur-md border border-[rgba(6,182,212,0.2)] hover:border-[var(--neon-cyan)] hover:shadow-[0_0_12px_rgba(6,182,212,0.2)] focus:outline-none rounded-xl text-[var(--text-primary)] text-sm font-medium transition-all duration-300 cursor-pointer flex justify-between items-center"
                  >
                    <span>{selectedYear ? selectedYear : "All Years"}</span>
                  </button>
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                    <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-gradient-to-br from-[rgba(6,182,212,0.18)] to-[rgba(59,130,246,0.18)] border border-[rgba(6,182,212,0.3)]">
                      <CalendarDays className="w-4 h-4 text-[var(--neon-cyan)]" />
                    </div>
                  </div>
                  <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3.5 text-[var(--text-tertiary)] group-hover:text-[var(--neon-cyan)] transition-colors">
                    <svg className={`w-4 h-4 transform transition-transform duration-200 ${isYearOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                  
                  {isYearOpen && (
                    <div className="absolute z-[100] w-full mt-2 bg-[rgba(15,23,42,0.9)] backdrop-blur-xl border border-[rgba(6,182,212,0.25)] rounded-xl shadow-[0_4px_30px_rgba(0,0,0,0.4),0_0_20px_rgba(6,182,212,0.15)] transition-all overflow-visible">
                      <div
                        onClick={() => {
                          setSelectedYear(null);
                          setIsYearOpen(false);
                        }}
                        className={`px-4 py-2.5 text-sm cursor-pointer hover:bg-[rgba(6,182,212,0.15)] transition-all flex items-center justify-between rounded-t-xl ${
                          selectedYear === null ? "text-[var(--neon-cyan)] bg-[rgba(6,182,212,0.1)] font-semibold shadow-[inset_0_0_8px_rgba(6,182,212,0.2)]" : "text-slate-300"
                        }`}
                      >
                        <span>All Years</span>
                        {selectedYear === null && <span className="w-1.5 h-1.5 rounded-full bg-[var(--neon-cyan)] shadow-[0_0_6px_var(--neon-cyan)]" />}
                      </div>
                      {availableYears.map((year, idx) => (
                        <div
                          key={year}
                          onClick={() => {
                            setSelectedYear(year);
                            setIsYearOpen(false);
                          }}
                          className={`px-4 py-2.5 text-sm cursor-pointer hover:bg-[rgba(6,182,212,0.15)] transition-all flex items-center justify-between ${
                            idx === availableYears.length - 1 ? "rounded-b-xl" : ""
                          } ${
                            selectedYear === year ? "text-[var(--neon-cyan)] bg-[rgba(6,182,212,0.1)] font-semibold shadow-[inset_0_0_8px_rgba(6,182,212,0.2)]" : "text-slate-300"
                          }`}
                        >
                          <span>{year}</span>
                          {selectedYear === year && <span className="w-1.5 h-1.5 rounded-full bg-[var(--neon-cyan)] shadow-[0_0_6px_var(--neon-cyan)]" />}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Month */}
              <div className="flex flex-col gap-2 min-w-[160px] flex-1" ref={monthDropdownRef}>
                <label className="flex items-center gap-2 text-[11px] text-[var(--text-tertiary)] uppercase tracking-[0.15em] font-semibold">
                  <Layers className="w-3.5 h-3.5 text-[var(--neon-purple)]" />
                  Month
                </label>
                <div className="relative group">
                  <button
                    onClick={() => {
                      setIsMonthOpen(!isMonthOpen);
                      setIsYearOpen(false);
                    }}
                    className="w-full text-left pl-11 pr-10 py-2.5 bg-[rgba(15,23,42,0.4)] backdrop-blur-md border border-[rgba(168,85,247,0.2)] hover:border-[var(--neon-purple)] hover:shadow-[0_0_12px_rgba(168,85,247,0.2)] focus:outline-none rounded-xl text-[var(--text-primary)] text-sm font-medium transition-all duration-300 cursor-pointer flex justify-between items-center"
                  >
                    <span>
                      {selectedMonth
                        ? ['January','February','March','April','May','June','July','August','September','October','November','December'][selectedMonth - 1]
                        : "All Months"}
                    </span>
                  </button>
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                    <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-gradient-to-br from-[rgba(139,92,246,0.18)] to-[rgba(59,130,246,0.18)] border border-[rgba(139,92,246,0.3)]">
                      <Layers className="w-4 h-4 text-[var(--neon-purple)]" />
                    </div>
                  </div>
                  <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3.5 text-[var(--text-tertiary)] group-hover:text-[var(--neon-purple)] transition-colors">
                    <svg className={`w-4 h-4 transform transition-transform duration-200 ${isMonthOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                  
                  {isMonthOpen && (
                    <div className="absolute z-[100] w-full mt-2 bg-[rgba(15,23,42,0.9)] backdrop-blur-xl border border-[rgba(168,85,247,0.25)] rounded-xl shadow-[0_4px_30px_rgba(0,0,0,0.4),0_0_20px_rgba(168,85,247,0.15)] transition-all overflow-visible">
                      <div
                        onClick={() => {
                          setSelectedMonth(null);
                          setIsMonthOpen(false);
                        }}
                        className={`px-4 py-2.5 text-sm cursor-pointer hover:bg-[rgba(168,85,247,0.15)] transition-all flex items-center justify-between rounded-t-xl ${
                          selectedMonth === null ? "text-[var(--neon-purple)] bg-[rgba(168,85,247,0.1)] font-semibold shadow-[inset_0_0_8px_rgba(168,85,247,0.2)]" : "text-slate-300"
                        }`}
                      >
                        <span>All Months</span>
                        {selectedMonth === null && <span className="w-1.5 h-1.5 rounded-full bg-[var(--neon-purple)] shadow-[0_0_6px_var(--neon-purple)]" />}
                      </div>
                      {[
                        { val: 1, label: 'January' },
                        { val: 2, label: 'February' },
                        { val: 3, label: 'March' },
                        { val: 4, label: 'April' },
                        { val: 5, label: 'May' },
                        { val: 6, label: 'June' },
                        { val: 7, label: 'July' },
                        { val: 8, label: 'August' },
                        { val: 9, label: 'September' },
                        { val: 10, label: 'October' },
                        { val: 11, label: 'November' },
                        { val: 12, label: 'December' },
                      ].map((month, idx, arr) => (
                        <div
                          key={month.val}
                          onClick={() => {
                            setSelectedMonth(month.val);
                            setIsMonthOpen(false);
                          }}
                          className={`px-4 py-2.5 text-sm cursor-pointer hover:bg-[rgba(168,85,247,0.15)] transition-all flex items-center justify-between ${
                            idx === arr.length - 1 ? "rounded-b-xl" : ""
                          } ${
                            selectedMonth === month.val ? "text-[var(--neon-purple)] bg-[rgba(168,85,247,0.1)] font-semibold shadow-[inset_0_0_8px_rgba(168,85,247,0.2)]" : "text-slate-300"
                          }`}
                        >
                          <span>{month.label}</span>
                          {selectedMonth === month.val && <span className="w-1.5 h-1.5 rounded-full bg-[var(--neon-purple)] shadow-[0_0_6px_var(--neon-purple)]" />}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Initial Balance */}
              <div className="flex flex-col gap-2 min-w-[180px] flex-1">
                <label className="flex items-center gap-2 text-[11px] text-[var(--text-tertiary)] uppercase tracking-[0.15em] font-semibold">
                  <Wallet className="w-3.5 h-3.5 text-[var(--neon-emerald)]" />
                  Initial Balance
                </label>
                <div className="relative group">
                  <input
                    type="number"
                    value={initialBalance}
                    onChange={(e) => setInitialBalance(Math.max(1, parseInt(e.target.value) || 1000))}
                    className="w-full appearance-none pl-11 pr-12 py-2.5 bg-[rgba(15,23,42,0.6)] border border-[rgba(100,116,139,0.25)] rounded-xl text-[var(--text-primary)] text-sm font-semibold focus:outline-none focus:border-[var(--neon-blue)] focus:ring-2 focus:ring-[rgba(59,130,246,0.25)] hover:border-[rgba(59,130,246,0.45)] transition-all duration-200 mono"
                    min="1"
                  />
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                    <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-gradient-to-br from-[rgba(16,185,129,0.18)] to-[rgba(6,182,212,0.18)] border border-[rgba(16,185,129,0.3)]">
                      <DollarSign className="w-4 h-4 text-[var(--neon-emerald)]" />
                    </div>
                  </div>
                  <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3.5 text-xs font-semibold text-[var(--text-tertiary)] uppercase">
                    USD
                  </span>
                </div>
              </div>

              {/* Clear Filters */}
              {(selectedYear || selectedMonth) && (
                <button
                  onClick={() => {
                    setSelectedYear(null);
                    setSelectedMonth(null);
                  }}
                  className="px-4 py-2.5 bg-gradient-to-r from-[rgba(239,68,68,0.12)] to-[rgba(139,92,246,0.12)] border border-[rgba(239,68,68,0.35)] rounded-xl text-[var(--text-primary)] text-sm font-semibold hover:from-[rgba(239,68,68,0.22)] hover:to-[rgba(139,92,246,0.22)] hover:border-[var(--neon-ruby)] hover:shadow-[0_0_20px_rgba(239,68,68,0.25)] transition-all duration-200 flex items-center gap-2 self-end"
                >
                  <RotateCcw className="w-4 h-4" />
                  <span>Reset</span>
                </button>
              )}
            </div>

            {/* Filter Status */}
            {(selectedYear || selectedMonth) && (
              <div className="relative mt-4 pt-4 border-t border-[rgba(100,116,139,0.15)] flex items-center gap-2 text-sm">
                <span className="text-[var(--text-tertiary)]">Showing data for:</span>
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[rgba(59,130,246,0.12)] border border-[rgba(59,130,246,0.3)] text-[var(--neon-cyan)] font-semibold text-xs">
                  <Activity className="w-3.5 h-3.5" />
                  {selectedMonth && selectedYear ?
                    `${['','January','February','March','April','May','June','July','August','September','October','November','December'][selectedMonth]} ${selectedYear}` :
                    selectedYear ? `Year ${selectedYear}` :
                    selectedMonth ? `${['','January','February','March','April','May','June','July','August','September','October','November','December'][selectedMonth]}` : 'All Data'
                  }
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Equity Summary */}
        <div className="grid grid-cols-3 gap-5 mb-6">
          <div className="glass-card !p-5 !mb-0 hover:scale-105 hover:-translate-y-1 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-[3px] before:bg-gradient-to-r before:from-[var(--neon-cyan)] before:to-[var(--neon-blue)]">
            <div className="absolute top-4 right-4 flex items-center justify-center w-11 h-11 rounded-xl bg-gradient-to-br from-[rgba(6,182,212,0.15)] to-[rgba(59,130,246,0.15)] border border-[rgba(6,182,212,0.25)]">
              <Wallet className="w-5 h-5 text-[var(--neon-cyan)]" />
            </div>
            <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
              Starting Balance
            </div>
            <div className="text-[24px] font-bold text-white mono mb-1">
              ${initialBalance.toLocaleString()}
            </div>
            <div className="text-sm text-[var(--text-tertiary)]">Initial Capital</div>
          </div>

          <div className="glass-card !p-5 !mb-0 hover:scale-105 hover:-translate-y-1 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-[3px] before:bg-gradient-to-r before:from-[var(--neon-green)] before:to-[var(--neon-cyan)]">
            <div className="absolute top-4 right-4 flex items-center justify-center w-11 h-11 rounded-xl bg-gradient-to-br from-[rgba(16,185,129,0.15)] to-[rgba(6,182,212,0.15)] border border-[rgba(16,185,129,0.25)]">
              <TrendingUp className="w-5 h-5 text-[var(--neon-emerald)]" />
            </div>
            <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
              Final Equity
            </div>
            <div className="text-[24px] font-bold text-[#10b981] mono mb-1">
              ${finalEquity.toLocaleString(undefined, {maximumFractionDigits: 2})}
            </div>
            <div className="text-sm text-[var(--text-tertiary)]">Current Portfolio Value</div>
          </div>

          <div className="glass-card !p-5 !mb-0 hover:scale-105 hover:-translate-y-1 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-[3px] before:bg-gradient-to-r before:from-[var(--neon-purple)] before:to-[var(--neon-green)]">
            <div className="absolute top-4 right-4 flex items-center justify-center w-11 h-11 rounded-xl bg-gradient-to-br from-[rgba(139,92,246,0.15)] to-[rgba(16,185,129,0.15)] border border-[rgba(139,92,246,0.25)]">
              {finalEquity >= initialBalance ? (
                <Trophy className="w-5 h-5 text-[var(--neon-purple)]" />
              ) : (
                <ArrowDownRight className="w-5 h-5 text-[var(--neon-ruby)]" />
              )}
            </div>
            <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
              Total Gain
            </div>
            <div className={`text-[24px] font-bold mono mb-1 ${finalEquity > initialBalance ? 'text-[#10b981]' : 'text-[#ef4444]'}`}>
              ${(finalEquity - initialBalance).toLocaleString(undefined, {maximumFractionDigits: 2})}
            </div>
            <div className="text-sm text-[var(--text-tertiary)]">Profit/Loss</div>
          </div>
        </div>

        {/* Performance Stats */}
        <div className="grid grid-cols-4 gap-5 mb-6">
          <div className="glass-card !p-5 !mb-0 hover:scale-105 hover:-translate-y-1 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-[3px] before:bg-gradient-to-r before:from-[var(--neon-blue)] before:to-[var(--neon-purple)]">
            <div className="absolute top-4 right-4 flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-[rgba(59,130,246,0.15)] to-[rgba(139,92,246,0.15)] border border-[rgba(59,130,246,0.25)]">
              <TrendingUp className="w-5 h-5 text-[var(--neon-blue)]" />
            </div>
            <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
              Total Return
            </div>
            <div className="text-[28px] font-bold positive mono mb-1">
              {(stats.total_return ?? 0) > 0 ? '+' : ''}{(stats.total_return ?? 0).toFixed(2)}%
            </div>
            <div className="text-sm text-[var(--text-tertiary)]">Total gain</div>
          </div>

          <div className="glass-card !p-5 !mb-0 hover:scale-105 hover:-translate-y-1 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-[3px] before:bg-gradient-to-r before:from-[var(--neon-blue)] before:to-[var(--neon-purple)]">
            <div className="absolute top-4 right-4 flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-[rgba(59,130,246,0.15)] to-[rgba(139,92,246,0.15)] border border-[rgba(59,130,246,0.25)]">
              <Target className="w-5 h-5 text-[var(--neon-blue)]" />
            </div>
            <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
              Win Rate
            </div>
            <div className={`text-[28px] font-bold mono mb-1 ${(stats.win_rate ?? 0) >= 50 ? 'positive' : 'negative'}`}>
              {(stats.win_rate ?? 0).toFixed(1)}%
            </div>
            <div className="text-sm text-[var(--text-tertiary)]">Success rate</div>
          </div>

          <div className="glass-card !p-5 !mb-0 hover:scale-105 hover:-translate-y-1 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-[3px] before:bg-gradient-to-r before:from-[var(--neon-blue)] before:to-[var(--neon-purple)]">
            <div className="absolute top-4 right-4 flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-[rgba(59,130,246,0.15)] to-[rgba(139,92,246,0.15)] border border-[rgba(59,130,246,0.25)]">
              <Scale className="w-5 h-5 text-[var(--neon-blue)]" />
            </div>
            <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
              Profit Factor
            </div>
            <div className={`text-[28px] font-bold mono mb-1 ${(stats.profit_factor ?? 0) >= 1.5 ? 'positive' : (stats.profit_factor ?? 0) >= 1.0 ? 'neutral' : 'negative'}`}>
              {(stats.profit_factor ?? 0).toFixed(2)}
            </div>
            <div className="text-sm text-[var(--text-tertiary)]">
              {(stats.profit_factor ?? 0) >= 2 ? 'Excellent' : (stats.profit_factor ?? 0) >= 1.5 ? 'Good' : (stats.profit_factor ?? 0) >= 1.0 ? 'Fair' : 'Poor'}
            </div>
          </div>

          <div className="glass-card !p-5 !mb-0 hover:scale-105 hover:-translate-y-1 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-[3px] before:bg-gradient-to-r before:from-[var(--neon-blue)] before:to-[var(--neon-purple)]">
            <div className="absolute top-4 right-4 flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-[rgba(59,130,246,0.15)] to-[rgba(139,92,246,0.15)] border border-[rgba(59,130,246,0.25)]">
              <Gauge className="w-5 h-5 text-[var(--neon-blue)]" />
            </div>
            <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
              Sharpe Ratio
            </div>
            <div className={`text-[28px] font-bold mono mb-1 ${(stats.sharpe_ratio ?? 0) >= 1.5 ? 'positive' : (stats.sharpe_ratio ?? 0) >= 1.0 ? 'neutral' : 'negative'}`}>
              {(stats.sharpe_ratio ?? 0).toFixed(2)}
            </div>
            <div className="text-sm text-[var(--text-tertiary)]">
              {(stats.sharpe_ratio ?? 0) >= 2 ? 'Excellent' : (stats.sharpe_ratio ?? 0) >= 1.5 ? 'Above average' : (stats.sharpe_ratio ?? 0) >= 1.0 ? 'Average' : 'Below average'}
            </div>
          </div>
        </div>

        {/* Charts Grid */}
        <div className="grid grid-cols-[2fr_1fr] gap-5 mb-6">
          {/* Equity Curve */}
          <div className="glass-card">
            <h2 className="mb-4 text-xl font-semibold inline-flex items-center gap-2"><Wallet size={18} aria-hidden="true" /> Equity Curve</h2>
            <div className="h-[350px]">
              <Line data={equityData} options={chartOptions} />
            </div>
          </div>

          {/* Win/Loss Distribution */}
          <div className="glass-card">
            <h2 className="mb-4 text-xl font-semibold inline-flex items-center gap-2">
              <BarChart3 size={18} aria-hidden="true" /> Win/Loss Distribution
            </h2>
            <div className="h-[350px]">
              <Doughnut
                data={winLossData}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: {
                      position: "bottom",
                      labels: { color: "#cbd5e1", padding: 15 },
                    },
                  },
                }}
              />
            </div>
          </div>
        </div>

        {/* Monthly Performance & Drawdown */}
        <div className="grid grid-cols-[2fr_1fr] gap-5 mb-6">
          {/* Monthly Returns */}
          <div className="glass-card">
            <h2 className="mb-4 text-xl font-semibold inline-flex items-center gap-2"><CalendarDays size={18} aria-hidden="true" /> Monthly Returns</h2>
            <div className="h-[350px]">
              <Bar data={monthlyReturnsData} options={chartOptions} />
            </div>
          </div>

          {/* Drawdown */}
          <div className="glass-card">
            <h2 className="mb-4 text-xl font-semibold inline-flex items-center gap-2"><TrendingDown size={18} aria-hidden="true" /> Drawdown Analysis</h2>
            <div className="h-[350px]">
              <Line data={drawdownData} options={chartOptions} />
            </div>
          </div>
        </div>

        {/* Monthly Profit/Loss Chart */}
        {monthlyPNL.length > 0 && (
          <div className="glass-card mb-6">
            <h2 className="mb-4 text-xl font-semibold inline-flex items-center gap-2"><CircleDollarSign size={18} aria-hidden="true" /> Monthly Profit/Loss Breakdown</h2>
            <div className="h-[350px]">
              <Bar 
                data={monthlyProfitLossData} 
                options={{
                  ...chartOptions,
                  scales: {
                    ...chartOptions.scales,
                    x: {
                      stacked: false,
                      grid: { color: "rgba(100, 116, 139, 0.1)" },
                      ticks: { color: "#94a3b8" },
                    },
                    y: {
                      stacked: false,
                      grid: { color: "rgba(100, 116, 139, 0.1)" },
                      ticks: { color: "#94a3b8" },
                    },
                  },
                }} 
              />
            </div>
          </div>
        )}

        {/* Key Metrics */}
        <div className="grid grid-cols-3 gap-5 mb-6">
          <div className="glass-card !p-5 !mb-0 text-center">
            <div className="flex items-center justify-center w-14 h-14 mx-auto mb-3 rounded-2xl bg-gradient-to-br from-[rgba(16,185,129,0.18)] to-[rgba(6,182,212,0.18)] border border-[rgba(16,185,129,0.3)]">
              <TrendingUp className="w-7 h-7 text-[var(--neon-emerald)]" />
            </div>
            <div className="text-sm text-[var(--text-tertiary)] mb-2">
              Average Win
            </div>
            <div className="text-[32px] font-bold positive mono">
              ${(stats.avg_win ?? 0).toFixed(2)}
            </div>
          </div>

          <div className="glass-card !p-5 !mb-0 text-center">
            <div className="flex items-center justify-center w-14 h-14 mx-auto mb-3 rounded-2xl bg-gradient-to-br from-[rgba(239,68,68,0.18)] to-[rgba(139,92,246,0.18)] border border-[rgba(239,68,68,0.3)]">
              <TrendingDown className="w-7 h-7 text-[var(--neon-ruby)]" />
            </div>
            <div className="text-sm text-[var(--text-tertiary)] mb-2">
              Average Loss
            </div>
            <div className="text-[32px] font-bold negative mono">
              -${(stats.avg_loss ?? 0).toFixed(2)}
            </div>
          </div>

          <div className="glass-card !p-5 !mb-0 text-center">
            <div className="flex items-center justify-center w-14 h-14 mx-auto mb-3 rounded-2xl bg-gradient-to-br from-[rgba(239,68,68,0.18)] to-[rgba(251,191,36,0.18)] border border-[rgba(251,191,36,0.3)]">
              <Activity className="w-7 h-7 text-[var(--neon-amber)]" />
            </div>
            <div className="text-sm text-[var(--text-tertiary)] mb-2">
              Max Drawdown
            </div>
            <div className="text-[32px] font-bold negative mono">
              -{(stats.max_drawdown ?? 0).toFixed(1)}%
            </div>
          </div>
        </div>

        {/* Monthly Performance Table */}
        <div className="glass-card">
          <h2 className="mb-4 text-xl font-semibold inline-flex items-center gap-2">
            <ClipboardList size={18} aria-hidden="true" /> Monthly Performance Summary
          </h2>

          <div className="overflow-hidden">
            <table className="w-full border-collapse text-sm">
              <thead className="bg-[var(--glass-secondary)]">
                <tr>
                  <th className="px-3 py-2 text-left text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold whitespace-nowrap">
                    Month
                  </th>
                  <th className="px-3 py-2 text-left text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold whitespace-nowrap">
                    Trades
                  </th>
                  <th className="px-3 py-2 text-left text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold whitespace-nowrap">
                    Win Rate
                  </th>
                  <th className="px-3 py-2 text-left text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold whitespace-nowrap">
                    Profit
                  </th>
                  <th className="px-3 py-2 text-left text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold whitespace-nowrap">
                    Loss
                  </th>
                  <th className="px-3 py-2 text-left text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold whitespace-nowrap">
                    Net P&L
                  </th>
                  <th className="px-3 py-2 text-left text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold whitespace-nowrap">
                    Return %
                  </th>
                </tr>
              </thead>
              <tbody>
                {monthlyPNL.length === 0 ? (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-3 py-6 text-center text-[var(--text-tertiary)]"
                    >
                      No monthly data available
                    </td>
                  </tr>
                ) : (
                  monthlyPNL.map((month, idx) => (
                    <tr
                      key={idx}
                      onClick={() => handleMonthRowClick(month.year, month.month_num, month.month_label || `${month.month} ${month.year}`)}
                      className="border-b border-[rgba(100,116,139,0.1)] hover:bg-cyan-500/10 cursor-pointer transition-colors"
                      title="Klik untuk melihat detail transaksi"
                    >
                      <td className="px-3 py-2 whitespace-nowrap font-medium text-slate-200">{month.month_label || `${month.month ?? 'N/A'}-${month.year ?? ''}`}</td>
                      <td className="px-3 py-2 whitespace-nowrap mono">{month.executed_trades ?? month.trades ?? 0}</td>
                      <td
                        className={`px-3 py-2 whitespace-nowrap ${
                          (month.win_rate ?? 0) >= 60 ? "positive" : "neutral"
                        }`}
                      >
                        {(month.win_rate ?? 0).toFixed(1)}%
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap mono font-semibold positive">
                        {(month.profit ?? 0).toFixed(2)}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap mono font-semibold negative">
                        {(month.loss ?? 0).toFixed(2)}
                      </td>
                      <td
                        className={`px-3 py-2 whitespace-nowrap mono font-semibold ${
                          (month.net_profit ?? 0) >= 0 ? "positive" : "negative"
                        }`}
                      >
                        {(month.net_profit ?? 0) >= 0 ? "+" : ""}{(month.net_profit ?? 0).toFixed(2)}
                      </td>
                      <td
                        className={`px-3 py-2 whitespace-nowrap mono font-semibold ${
                          ((month.net_profit ?? 0) / initialBalance * 100) >= 0 ? "positive" : "negative"
                        }`}
                      >
                        {((month.net_profit ?? 0) / initialBalance * 100).toFixed(2)}%
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer */}
        <MT5Footer />
        </div>
      </div>

      {/* Monthly Trades Detail Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xl animate-in fade-in duration-200">
          <div className="w-full max-w-[95vw] xl:max-w-[1400px] bg-slate-900/90 border border-slate-800 rounded-3xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] overflow-hidden flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-200 relative">
            {/* Premium Gradient Top Accent Line */}
            <div className="absolute top-0 left-0 w-full h-[3px] bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-500" />
            
            {/* Header */}
            <div className="p-6 pt-7 border-b border-slate-800 flex items-center justify-between bg-slate-900/40">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-cyan-500/10 text-cyan-300 border border-cyan-500/15">
                  <CalendarDays className="size-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-100 tracking-tight">
                    Detail Transaksi - {modalTitle}
                  </h3>
                  <p className="text-xs text-slate-400">
                    Daftar transaksi yang ditutup pada bulan ini
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-2 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-all cursor-pointer hover:scale-105 active:scale-95 duration-150"
                title="Tutup"
              >
                <X className="size-5" />
              </button>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-5">
              {isLoadingTrades ? (
                <div className="py-20 flex flex-col items-center justify-center gap-3 text-slate-400">
                  <Loader2 className="size-8 text-cyan-500 animate-spin" />
                  <span className="text-sm">Memuat data transaksi...</span>
                </div>
              ) : selectedMonthTrades.length === 0 ? (
                <div className="py-20 text-center text-slate-400 text-sm italic">
                  Tidak ada transaksi yang tercatat pada bulan ini.
                </div>
              ) : (
                <>
                  {/* Summary Dashboard Cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="bg-slate-950/30 border border-slate-800/60 rounded-xl p-4 flex flex-col">
                      <span className="text-xs text-slate-400 uppercase tracking-wider mb-1">Total Trades</span>
                      <span className="text-2xl font-bold text-slate-200 mono">{selectedMonthTrades.length}</span>
                    </div>
                    <div className="bg-slate-950/30 border border-slate-800/60 rounded-xl p-4 flex flex-col">
                      <span className="text-xs text-slate-400 uppercase tracking-wider mb-1">Win Rate</span>
                      <span className="text-2xl font-bold text-cyan-400 mono">
                        {(() => {
                          const wins = selectedMonthTrades.filter(t => t.net_profit > 0).length;
                          return ((wins / selectedMonthTrades.length) * 100).toFixed(1);
                        })()}%
                      </span>
                    </div>
                    <div className="bg-slate-950/30 border border-slate-800/60 rounded-xl p-4 flex flex-col">
                      <span className="text-xs text-slate-400 uppercase tracking-wider mb-1">Net P&L</span>
                      <span className={`text-2xl font-bold mono ${
                        selectedMonthTrades.reduce((sum, t) => sum + t.net_profit, 0) >= 0 ? "text-emerald-400" : "text-rose-500"
                      }`}>
                        {selectedMonthTrades.reduce((sum, t) => sum + t.net_profit, 0) >= 0 ? "+" : ""}
                        ${selectedMonthTrades.reduce((sum, t) => sum + t.net_profit, 0).toFixed(2)}
                      </span>
                    </div>
                  </div>

                  {/* Trades Detail Table */}
                  <div className="border border-slate-800/80 rounded-xl overflow-hidden bg-slate-950/20">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm text-left">
                        <thead className="bg-slate-900/60 border-b border-slate-800 text-slate-400 text-xs uppercase font-semibold whitespace-nowrap">
                          <tr>
                            <th className="py-3 px-4">Ticket</th>
                            <th className="py-3 px-4">Type</th>
                            <th className="py-3 px-4 text-right">Lot</th>
                            <th className="py-3 px-4 text-right">Entry Price</th>
                            <th className="py-3 px-4 text-right">Exit Price</th>
                            <th className="py-3 px-4 text-right">Net Profit</th>
                            <th className="py-3 px-4">Entry Time</th>
                            <th className="py-3 px-4">Exit Time</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60 text-slate-200">
                          {[...selectedMonthTrades]
                            .sort((a, b) => (a.entry_time || "").localeCompare(b.entry_time || ""))
                            .map((trade) => {
                              const isWin = trade.net_profit >= 0;
                              return (
                                <tr key={trade.ticket} className="hover:bg-slate-800/30 transition-colors whitespace-nowrap">
                                  <td className="py-3 px-4 mono text-xs text-slate-400">#{trade.ticket}</td>
                                  <td className="py-3 px-4">
                                    <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold tracking-wider ${
                                      trade.type === "BUY" 
                                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
                                        : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                                    }`}>
                                      {trade.type}
                                    </span>
                                  </td>
                                  <td className="py-3 px-4 text-right mono">{trade.lot_size.toFixed(2)}</td>
                                  <td className="py-3 px-4 text-right mono">${trade.entry_price.toFixed(2)}</td>
                                  <td className="py-3 px-4 text-right mono">${trade.exit_price.toFixed(2)}</td>
                                  <td className={`py-3 px-4 text-right mono font-semibold ${
                                    isWin ? "text-emerald-400" : "text-rose-500"
                                  }`}>
                                    {isWin ? "+" : ""}${trade.net_profit.toFixed(2)}
                                  </td>
                                  <td className="py-3 px-4 text-xs text-slate-400">{trade.entry_time}</td>
                                  <td className="py-3 px-4 text-xs text-slate-400">{trade.exit_time}</td>
                                </tr>
                              );
                            })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              )}
            </div>
            
            {/* Footer */}
            <div className="p-4 border-t border-slate-800 bg-slate-900/30 flex justify-end">
              <button
                onClick={() => setIsModalOpen(false)}
                className="px-5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold transition-all cursor-pointer"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
