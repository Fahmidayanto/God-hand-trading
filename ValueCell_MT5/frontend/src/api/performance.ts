import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

// Performance Types
export interface PerformanceStats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_profit: number;
  total_loss: number;
  profit_factor: number;
  sharpe_ratio: number;
  max_drawdown: number;
}

export interface MonthlyPerformance {
  month: string;
  trades: number;
  profit: number;
  win_rate: number;
}

export interface RiskMetrics {
  var_95: number;
  var_99: number;
  expected_shortfall: number;
  volatility: number;
  max_consecutive_losses: number;
}

// API Hooks
export const usePerformanceStats = () => {
  return useQuery({
    queryKey: ["performance", "stats"],
    queryFn: () => apiClient.get<PerformanceStats>("/performance/stats"),
  });
};

export const useMonthlyPerformance = () => {
  return useQuery({
    queryKey: ["performance", "monthly"],
    queryFn: () => apiClient.get<MonthlyPerformance[]>("/performance/monthly"),
  });
};

export const useRiskMetrics = () => {
  return useQuery({
    queryKey: ["performance", "risk"],
    queryFn: () => apiClient.get<RiskMetrics>("/performance/risk"),
  });
};
