import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { type ApiResponse, apiClient } from "@/lib/api-client";

// Trading Types
export interface AccountStats {
  balance: number;
  equity: number;
  margin: number;
  free_margin: number;
  margin_level: number;
  profit: number;
  open_positions: number;
}

export interface Position {
  ticket: number;
  symbol: string;
  type: string;
  volume: number;
  open_price: number;
  current_price: number;
  profit: number;
  swap: number;
  commission: number;
  open_time: string;
}

export interface TradingSignal {
  signal: string;
  confidence: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  timestamp: string;
}

export interface OrderRequest {
  symbol: string;
  order_type: string;
  volume: number;
  price?: number;
  sl?: number;
  tp?: number;
  comment?: string;
}

// API Hooks
export const useDashboardStats = () => {
  return useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: () => apiClient.get<AccountStats>("/dashboard/stats"),
    refetchInterval: 5000, // Refresh every 5 seconds
  });
};

export const useAccountInfo = () => {
  return useQuery({
    queryKey: ["dashboard", "account"],
    queryFn: () => apiClient.get("/dashboard/account"),
  });
};

export const usePositions = () => {
  return useQuery({
    queryKey: ["trading", "positions"],
    queryFn: () => apiClient.get<Position[]>("/trading/positions"),
    refetchInterval: 3000,
  });
};

export const useTradingSignal = () => {
  return useQuery({
    queryKey: ["trading", "signal"],
    queryFn: () => apiClient.get<TradingSignal>("/trading/signal"),
    refetchInterval: 10000,
  });
};

export const usePlaceOrder = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (order: OrderRequest) =>
      apiClient.post("/trading/order", order),
    onSuccess: () => {
      toast.success("Order placed successfully");
      queryClient.invalidateQueries({ queryKey: ["trading", "positions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", "stats"] });
    },
    onError: (error) => {
      toast.error(`Failed to place order: ${error}`);
    },
  });
};

export const useCandles = (symbol: string, timeframe: string, count: number = 100) => {
  return useQuery({
    queryKey: ["trading", "candles", symbol, timeframe, count],
    queryFn: () =>
      apiClient.get(`/trading/candles?symbol=${symbol}&timeframe=${timeframe}&count=${count}`),
    enabled: !!symbol && !!timeframe,
  });
};

export const useTradeHistory = () => {
  return useQuery({
    queryKey: ["trading", "history"],
    queryFn: () => apiClient.get("/trading/history"),
  });
};
