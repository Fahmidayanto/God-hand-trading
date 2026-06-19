import { useEffect, useState } from "react";
import Particles from "@tsparticles/react";
import { loadSlim } from "@tsparticles/slim";
import type { Engine } from "@tsparticles/engine";
import MT5Sidebar from "./components/MT5Sidebar";
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

interface MonthlyData {
  month: string;
  trades: number;
  win_rate: number;
  pnl: number;
  return_pct: number;
  max_dd: number;
}

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
  const [stats, setStats] = useState({
    total_return: 0,
    win_rate: 0,
    profit_factor: 0,
    sharpe_ratio: 0,
    avg_win: 0,
    avg_loss: 0,
    max_drawdown: 0,
  });
  const [monthlyData, setMonthlyData] = useState<MonthlyData[]>([]);
  const [monthlyPNL, setMonthlyPNL] = useState<MonthlyPNLData[]>([]);
  const [availableYears, setAvailableYears] = useState<number[]>([]);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
  const [initialBalance, setInitialBalance] = useState<number>(1000);
  const [finalEquity, setFinalEquity] = useState<number>(initialBalance);

  const particlesInit = async (engine: Engine) => {
    await loadSlim(engine);
  };

  useEffect(() => {
    loadAvailableYears();
    loadPerformanceData();
    const interval = setInterval(loadPerformanceData, 10000);
    return () => clearInterval(interval);
  }, [selectedYear, selectedMonth]);

  // Note: finalEquity is now set directly from the API response in loadPerformanceData()
  // The API correctly calculates cumulative equity across all years/months

  const loadAvailableYears = async () => {
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const response = await fetch(`${apiUrl}/performance/backtest/available-years`);
      if (response.ok) {
        const data = await response.json();
        setAvailableYears(data.years || []);
        // Don't auto-select year - let user see all data first
      }
    } catch (error) {
      console.error("Error loading available years:", error);
    }
  };

  const loadPerformanceData = async () => {
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      
      // Build query parameters for backtest data
      const params = new URLSearchParams();
      if (selectedYear) params.append('year', selectedYear.toString());
      if (selectedMonth) params.append('month', selectedMonth.toString());
      const queryString = params.toString() ? '?' + params.toString() : '';
      
      // Fetch stats from backtest analytics
      const statsResponse = await fetch(
        `${apiUrl}/performance/backtest/stats${queryString}`
      );
      if (statsResponse.ok) {
        const statsData = await statsResponse.json();
        setStats({
          total_return: statsData.return_pct ?? 0,
          win_rate: statsData.win_rate ?? 0,
          profit_factor: statsData.profit_factor ?? 0,
          sharpe_ratio: statsData.sharpe_ratio ?? 0,
          avg_win: statsData.avg_win ?? 0,
          avg_loss: statsData.avg_loss ?? 0,
          max_drawdown: statsData.max_drawdown ?? 0,
        });
        // Set final equity from API response (which has correct cumulative value)
        setFinalEquity(statsData.final_equity ?? initialBalance);
      }

      // Fetch monthly data with filters
      const monthlyResponse = await fetch(
        `${apiUrl}/performance/backtest/monthly${queryString}`
      );
      if (monthlyResponse.ok) {
        const monthlyList = await monthlyResponse.json();
        if (Array.isArray(monthlyList) && monthlyList.length > 0) {
          setMonthlyData(monthlyList);
        } else {
          setMonthlyData([]);
        }
      }

      // Fetch monthly P&L data from CSV with year/month filters
      const monthlyPNLResponse = await fetch(
        `${apiUrl}/performance/monthly-pnl${queryString}`
      );
      if (monthlyPNLResponse.ok) {
        const monthlyPNLData = await monthlyPNLResponse.json();
        if (monthlyPNLData.data && Array.isArray(monthlyPNLData.data)) {
          setMonthlyPNL(monthlyPNLData.data);
        } else {
          setMonthlyPNL([]);
        }
      }
    } catch (error) {
      console.error("Error loading performance data:", error);
      // Keep default values on error (already set in state)
    }
  };

  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  
  const formatMonthLabel = (monthStr: string) => {
    const parts = monthStr.split('.');
    if (parts.length === 2) {
      const monthNum = parseInt(parts[1], 10);
      return monthNames[monthNum - 1] || monthStr;
    }
    return monthStr;
  };

  const getChartLabels = () => {
    if (selectedYear && !selectedMonth) {
      return monthlyData.length > 0 ? monthlyData.map(m => formatMonthLabel(m.month ?? '')) : [];
    }
    return monthlyData.length > 0 ? monthlyData.map(m => m.month ?? 'N/A') : [];
  };

  const getPNLChartLabels = () => {
    if (selectedYear && !selectedMonth) {
      return monthlyPNL.length > 0 ? monthlyPNL.map(m => {
        if (m.month_num) {
          return monthNames[m.month_num - 1] || m.month_label;
        }
        return formatMonthLabel(m.month ?? '');
      }) : [];
    }
    return monthlyPNL.length > 0 ? monthlyPNL.map(m => m.month_label ?? `${m.month ?? 'N/A'}-${m.year ?? ''}`) : [];
  };

  const equityData = {
    labels: getChartLabels(),
    datasets: [
      {
        label: "Equity",
        data: monthlyData.length > 0 ? monthlyData.map((m) => {
          // pnl is cumulative profit, so equity = initial + pnl
          return initialBalance + (m.pnl ?? 0);
        }) : [],
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
        data: monthlyData.length > 0 ? [
          monthlyData.reduce((sum, m) => sum + ((m.trades ?? 0) * ((m.win_rate ?? 0) / 100)), 0),
          monthlyData.reduce((sum, m) => sum + ((m.trades ?? 0) * (1 - ((m.win_rate ?? 0) / 100))), 0)
        ] : [0, 0],
        backgroundColor: ["#10b981", "#ef4444"],
        borderWidth: 0,
      },
    ],
  };

  const monthlyReturnsData = {
    labels: getChartLabels(),
    datasets: [
      {
        label: "Monthly Return %",
        data:
          monthlyData.length > 0
            ? monthlyData.map((m) => m.return_pct ?? 0)
            : [],
        backgroundColor: "#3b82f6",
        borderRadius: 8,
      },
    ],
  };

  const drawdownData = {
    labels: getChartLabels(),
    datasets: [
      {
        label: "Drawdown %",
        data: monthlyData.length > 0 ? monthlyData.map(m => m.max_dd ?? 0) : [],
        borderColor: "#ef4444",
        backgroundColor: "rgba(239, 68, 68, 0.1)",
        borderWidth: 2,
        fill: true,
        tension: 0.4,
      },
    ],
  };

  const monthlyProfitLossData = {
    labels: getPNLChartLabels(),
    datasets: [
      {
        label: "Profit",
        data: monthlyPNL.length > 0 ? monthlyPNL.map(m => (m.profit ?? 0) > 0 ? (m.profit ?? 0) : 0) : [],
        backgroundColor: "#10b981",
        borderRadius: 6,
        borderSkipped: false,
      },
      {
        label: "Loss",
        data: monthlyPNL.length > 0 ? monthlyPNL.map(m => (m.loss ?? 0) < 0 ? (m.loss ?? 0) : 0) : [],
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
          autoSkip: false,
          callback: function(value: any, index: number) {
            const labels = getChartLabels();
            // All Years view: show range labels (0-12, 12-24, 24-36, etc.)
            if (!selectedYear) {
              if (index % 12 === 0) {
                const start = index;
                const end = index + 12;
                return `${start}-${end}`;
              }
              return '';
            }
            // Year selected view: show month names
            if (labels[index]) {
              return labels[index];
            }
            return '';
          },
        },
      },
    },
  };

  return (
    <div 
      style={{ 
        background: "var(--bg-deepspace)",
        minHeight: "100vh",
        width: "100%",
        position: "relative",
        overflowX: "hidden",
        overflowY: "auto"
      }}
    >
      <Particles
        id="tsparticles"
        init={particlesInit}
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

      {/* Sidebar */}
      <MT5Sidebar />

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
        <div className="mb-6">
          <h1 className="text-[32px] font-bold mb-2 bg-gradient-to-r from-[var(--neon-blue)] to-[var(--neon-cyan)] bg-clip-text text-transparent">
            📈 Performance Analytics
          </h1>
          <p className="text-[var(--text-tertiary)] text-sm">
            Comprehensive trading performance metrics and analysis
          </p>
        </div>

        {/* Filter Controls */}
        <div className="mb-6">
          <div className="flex gap-4 items-end mb-3">
            <div className="flex flex-col gap-2">
              <label className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold">
                Year
              </label>
              <select
                value={selectedYear ?? ''}
                onChange={(e) => setSelectedYear(e.target.value ? parseInt(e.target.value) : null)}
                className="px-4 py-2 bg-[var(--glass-secondary)] border border-[rgba(100,116,139,0.3)] rounded-lg text-[var(--text-primary)] focus:outline-none focus:border-[var(--neon-blue)] transition-colors"
              >
                <option value="">All Years</option>
                {availableYears.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold">
                Month
              </label>
              <select
                value={selectedMonth ?? ''}
                onChange={(e) => setSelectedMonth(e.target.value ? parseInt(e.target.value) : null)}
                className="px-4 py-2 bg-[var(--glass-secondary)] border border-[rgba(100,116,139,0.3)] rounded-lg text-[var(--text-primary)] focus:outline-none focus:border-[var(--neon-blue)] transition-colors"
              >
                <option value="">All Months</option>
                <option value="1">January</option>
                <option value="2">February</option>
                <option value="3">March</option>
                <option value="4">April</option>
                <option value="5">May</option>
                <option value="6">June</option>
                <option value="7">July</option>
                <option value="8">August</option>
                <option value="9">September</option>
                <option value="10">October</option>
                <option value="11">November</option>
                <option value="12">December</option>
              </select>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold">
                Initial Balance ($)
              </label>
              <input
                type="number"
                value={initialBalance}
                onChange={(e) => setInitialBalance(Math.max(1, parseInt(e.target.value) || 1000))}
                className="px-4 py-2 bg-[var(--glass-secondary)] border border-[rgba(100,116,139,0.3)] rounded-lg text-[var(--text-primary)] focus:outline-none focus:border-[var(--neon-blue)] transition-colors"
                min="1"
              />
            </div>

            {(selectedYear || selectedMonth) && (
              <button
                onClick={() => {
                  setSelectedYear(null);
                  setSelectedMonth(null);
                }}
                className="px-4 py-2 bg-[var(--glass-secondary)] border border-[rgba(100,116,139,0.3)] rounded-lg text-[var(--text-primary)] hover:bg-[rgba(59,130,246,0.2)] hover:border-[var(--neon-blue)] transition-colors flex items-center gap-2"
              >
                <span>🔄</span>
                <span>Clear Filters</span>
              </button>
            )}
          </div>

          {/* Filter Status */}
          {(selectedYear || selectedMonth) && (
            <div className="text-sm text-[var(--text-tertiary)]">
              📊 Showing data for: {' '}
              <span className="text-[var(--neon-cyan)] font-semibold">
                {selectedMonth && selectedYear ? 
                  `${['','January','February','March','April','May','June','July','August','September','October','November','December'][selectedMonth]} ${selectedYear}` :
                  selectedYear ? `Year ${selectedYear}` :
                  selectedMonth ? `Month ${selectedMonth}` : 'All Data'
                }
              </span>
            </div>
          )}
        </div>

        {/* Equity Summary */}
        <div className="grid grid-cols-3 gap-5 mb-6">
          <div className="glass-card !p-5 !mb-0 hover:scale-105 hover:-translate-y-1 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-[3px] before:bg-gradient-to-r before:from-[var(--neon-cyan)] before:to-[var(--neon-blue)]">
            <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
              Starting Balance
            </div>
            <div className="text-[24px] font-bold text-white mono mb-1">
              ${initialBalance.toLocaleString()}
            </div>
            <div className="text-sm text-[var(--text-tertiary)]">Initial Capital</div>
          </div>

          <div className="glass-card !p-5 !mb-0 hover:scale-105 hover:-translate-y-1 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-[3px] before:bg-gradient-to-r before:from-[var(--neon-green)] before:to-[var(--neon-cyan)]">
            <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
              Final Equity
            </div>
            <div className="text-[24px] font-bold text-[#10b981] mono mb-1">
              ${finalEquity.toLocaleString(undefined, {maximumFractionDigits: 2})}
            </div>
            <div className="text-sm text-[var(--text-tertiary)]">Current Portfolio Value</div>
          </div>

          <div className="glass-card !p-5 !mb-0 hover:scale-105 hover:-translate-y-1 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-[3px] before:bg-gradient-to-r before:from-[var(--neon-purple)] before:to-[var(--neon-green)]">
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
            <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
              Total Return
            </div>
            <div className="text-[28px] font-bold positive mono mb-1">
              {(stats.total_return ?? 0) > 0 ? '+' : ''}{(stats.total_return ?? 0).toFixed(2)}%
            </div>
            <div className="text-sm text-[var(--text-tertiary)]">Total gain</div>
          </div>

          <div className="glass-card !p-5 !mb-0 hover:scale-105 hover:-translate-y-1 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-[3px] before:bg-gradient-to-r before:from-[var(--neon-blue)] before:to-[var(--neon-purple)]">
            <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
              Win Rate
            </div>
            <div className={`text-[28px] font-bold mono mb-1 ${(stats.win_rate ?? 0) >= 50 ? 'positive' : 'negative'}`}>
              {(stats.win_rate ?? 0).toFixed(1)}%
            </div>
            <div className="text-sm text-[var(--text-tertiary)]">Success rate</div>
          </div>

          <div className="glass-card !p-5 !mb-0 hover:scale-105 hover:-translate-y-1 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-[3px] before:bg-gradient-to-r before:from-[var(--neon-blue)] before:to-[var(--neon-purple)]">
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
            <h2 className="mb-4 text-xl font-semibold">💰 Equity Curve</h2>
            <div className="h-[350px]">
              <Line data={equityData} options={chartOptions} />
            </div>
          </div>

          {/* Win/Loss Distribution */}
          <div className="glass-card">
            <h2 className="mb-4 text-xl font-semibold">
              📊 Win/Loss Distribution
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
            <h2 className="mb-4 text-xl font-semibold">📅 Monthly Returns</h2>
            <div className="h-[350px]">
              <Bar data={monthlyReturnsData} options={chartOptions} />
            </div>
          </div>

          {/* Drawdown */}
          <div className="glass-card">
            <h2 className="mb-4 text-xl font-semibold">📉 Drawdown Analysis</h2>
            <div className="h-[350px]">
              <Line data={drawdownData} options={chartOptions} />
            </div>
          </div>
        </div>

        {/* Monthly Profit/Loss Chart */}
        {monthlyPNL.length > 0 && (
          <div className="glass-card mb-6">
            <h2 className="mb-4 text-xl font-semibold">💵 Monthly Profit/Loss Breakdown</h2>
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
            <div className="text-5xl mb-3">🎯</div>
            <div className="text-sm text-[var(--text-tertiary)] mb-2">
              Average Win
            </div>
            <div className="text-[32px] font-bold positive mono">
              ${(stats.avg_win ?? 0).toFixed(2)}
            </div>
          </div>

          <div className="glass-card !p-5 !mb-0 text-center">
            <div className="text-5xl mb-3">⚠️</div>
            <div className="text-sm text-[var(--text-tertiary)] mb-2">
              Average Loss
            </div>
            <div className="text-[32px] font-bold negative mono">
              -${(stats.avg_loss ?? 0).toFixed(2)}
            </div>
          </div>

          <div className="glass-card !p-5 !mb-0 text-center">
            <div className="text-5xl mb-3">📊</div>
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
          <h2 className="mb-4 text-xl font-semibold">
            📋 Monthly Performance Summary
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
                      className="border-b border-[rgba(100,116,139,0.1)] hover:bg-[var(--glass-secondary)] transition-colors"
                    >
                      <td className="px-3 py-2 whitespace-nowrap">{month.month_label || `${month.month ?? 'N/A'}-${month.year ?? ''}`}</td>
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
    </div>
  );
}
