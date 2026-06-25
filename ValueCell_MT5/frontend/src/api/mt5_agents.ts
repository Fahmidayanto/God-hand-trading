import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

// AI Agents Types
export interface AgentConsensus {
  consensus: string;
  confidence: number;
  agents: {
    agent_name: string;
    prediction: string;
    confidence: number;
  }[];
  timestamp: string;
}

export interface AgentMetrics {
  agent_name: string;
  total_predictions: number;
  correct_predictions: number;
  accuracy: number;
  avg_confidence: number;
  last_active: string;
}

// Market Structure Types
export interface MarketStructure {
  phase: number;
  phase_name: string;
  direction: string;
  choch_price: number;
  choch_time: string | null;
  choch_direction: string;
  bos_target_price: number;
  bos_price: number;
  bos_time: string | null;
  bos_direction: string;
  bars_since_bos: number;
  bos_chain_count: number;
  h1_above_ema200: boolean;
  h1_trend_aligned: boolean;
  is_entry_valid: boolean;
  last_updated: string | null;
}

// Market Structure Lines for Chart
export interface MarketStructurePoint {
  time: string;
  timestamp: number;
  price: number;
  type: string;
  direction: string;
  timeframe: string;
  status?: string;
  // For BoS/CHoCH: the price level that was broken (used to find formation time)
  previous_price?: number;
}

export interface MarketStructureLines {
  bos_lines: MarketStructurePoint[];
  choch_lines: MarketStructurePoint[];
  hh_points: MarketStructurePoint[];
  ll_points: MarketStructurePoint[];
  total_points: number;
  time_range_hours: number;
  last_updated: string;
}

// API Hooks
export const useAgentConsensus = () => {
  return useQuery({
    queryKey: ["agents", "consensus"],
    queryFn: () => apiClient.get<AgentConsensus>("/agents/consensus"),
    refetchInterval: 15000, // Refresh every 15 seconds
  });
};

export const useAgentMetrics = () => {
  return useQuery({
    queryKey: ["agents", "metrics"],
    queryFn: () => apiClient.get<AgentMetrics[]>("/agents/metrics"),
  });
};

export const useMarketStructure = () => {
  return useQuery({
    queryKey: ["agents", "market-structure"],
    queryFn: () => apiClient.get<MarketStructure>("/agents/market-structure"),
    refetchInterval: 15000, // Refresh every 15 seconds
  });
};

export const useMarketStructureLines = (fromDate?: string, toDate?: string) => {
  const params = new URLSearchParams();
  if (fromDate) params.set("from_date", fromDate);
  if (toDate) params.set("to_date", toDate);
  const queryString = params.toString();
  return useQuery({
    queryKey: ["agents", "market-structure-lines", fromDate ?? "2020-01-01"],
    queryFn: () => apiClient.get<MarketStructureLines>(`/agents/market-structure-lines?${queryString}`),
    refetchInterval: 900000, // Refresh every 15 minutes
    staleTime: 900000, // Don't refetch within 15 minutes
  });
};

// Session Zones (shadow background bands on the chart)
export interface SessionZone {
  start_time: number; // unix seconds
  end_time: number; // unix seconds
  session: string;
  status: string; // "CLOSED" | "OPEN"
  open_price: number;
  high_price: number;
  low_price: number;
  close_price: number;
  range_points: number;
  duration_bars: number;
  is_dst: boolean;
}

export interface SessionZonesResponse {
  zones: SessionZone[];
  total_zones: number;
}

export const useSessionZones = (
  daysOrFromDate: number | string = 2,
  symbol: string = "XAUUSD"
) => {
  // Determine if parameter is a date string (YYYY-MM-DD) or number of days
  const isDateString = typeof daysOrFromDate === "string" && /^\d{4}-\d{2}-\d{2}$/.test(daysOrFromDate);
  
  const queryString = isDateString
    ? `/trading/session-zones?symbol=${symbol}&from_date=${daysOrFromDate}`
    : `/trading/session-zones?symbol=${symbol}&days=${daysOrFromDate}`;

  return useQuery({
    queryKey: ["trading", "session-zones", symbol, daysOrFromDate],
    queryFn: () => apiClient.get<SessionZonesResponse>(queryString),
    refetchInterval: 30000, // Refresh every 30 seconds to extend the live session
  });
};
