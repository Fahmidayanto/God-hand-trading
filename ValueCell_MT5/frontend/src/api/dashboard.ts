import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

// Dashboard Types
export interface SystemResources {
  cpu_usage_percent: number;
  memory_usage_mb: number;
  memory_usage_percent: number;
}

export interface SystemStatus {
  mt5_connected: boolean;
  api_version: string;
  trading_mode: string;
  uptime_seconds: number;
  last_update: string;
  account_number?: number;
  server_name?: string;
  system_health_percent: number;
  resources?: SystemResources;
}

export interface DashboardStats {
  balance: number;
  equity: number;
  margin: number;
  free_margin: number;
  margin_level: number;
  profit: number;
  open_positions: number;
}

export interface PerformanceStats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_profit: number;
  total_loss: number;
  net_profit: number;
  profit_factor: number;
  sharpe_ratio: number | null;
  max_drawdown: number;
  avg_win: number;
  avg_loss: number;
  largest_win: number;
  largest_loss: number;
  avg_trade_duration: number;
}

// API Hooks
export const useSystemStatus = () => {
  return useQuery({
    queryKey: ["dashboard", "status"],
    queryFn: () => apiClient.get<SystemStatus>("/dashboard/status"),
    refetchInterval: 5000,
  });
};

export const useDashboardStats = () => {
  return useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: () => apiClient.get<DashboardStats>("/dashboard/stats"),
    refetchInterval: 5000,
  });
};

export const usePerformanceStats = (days: number = 180) => {
  return useQuery({
    queryKey: ["performance", "stats", days],
    queryFn: () => apiClient.get<PerformanceStats>(`/performance/stats?days=${days}`),
    refetchInterval: 30000, // Refresh every 30 seconds
  });
};
