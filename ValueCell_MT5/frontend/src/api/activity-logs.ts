import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import {
  Target, Zap, Flag, RefreshCw, Rocket, ArrowDown, ArrowUp, Inbox, Send, Pencil,
  OctagonX, Minus, FileText, XCircle, Info, AlertTriangle, CircleDot, CircleStop,
  Link2, Unlink, BarChart3, TrendingUp,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

// Activity Log Types
export type EventType =
  | "SIGNAL_GENERATED"
  | "SIGNAL_EXECUTED"
  | "SIGNAL_CLOSED"
  | "STRUCTURE_CHOCH"
  | "STRUCTURE_BOS"
  | "STRUCTURE_LL"
  | "STRUCTURE_HH"
  | "POSITION_OPENED"
  | "POSITION_CLOSED"
  | "POSITION_MODIFIED"
  | "TRADE_WIN"
  | "TRADE_LOSS"
  | "TRADE_BREAKEVEN"
  | "ORDER_PLACED"
  | "ORDER_CANCELLED"
  | "SYSTEM_INFO"
  | "SYSTEM_ERROR"
  | "SYSTEM_WARNING"
  | "SYSTEM_STARTUP"
  | "SYSTEM_SHUTDOWN"
  | "CONNECTION_ESTABLISHED"
  | "CONNECTION_LOST"
  | "AGENT_SYNC"
  | "PRICE_UPDATE"
  | "MARKET_ANALYSIS";

export type Severity = "INFO" | "SUCCESS" | "WARNING" | "ERROR";

export interface ActivityLog {
  id: string;
  timestamp: string;
  event_type: EventType;
  severity: Severity;
  icon: string;
  title: string;
  message: string;
  metadata?: Record<string, any>;
}

export interface ActivityLogsResponse {
  success: boolean;
  total: number;
  logs: ActivityLog[];
  has_more: boolean;
}

// Icon mapping for event types (Lucide components)
export const EVENT_TYPE_ICONS: Record<EventType, LucideIcon> = {
  SIGNAL_GENERATED: Target,
  SIGNAL_EXECUTED: Zap,
  SIGNAL_CLOSED: Flag,
  STRUCTURE_CHOCH: RefreshCw,
  STRUCTURE_BOS: Rocket,
  STRUCTURE_LL: ArrowDown,
  STRUCTURE_HH: ArrowUp,
  POSITION_OPENED: Inbox,
  POSITION_CLOSED: Send,
  POSITION_MODIFIED: Pencil,
  TRADE_WIN: Target,
  TRADE_LOSS: OctagonX,
  TRADE_BREAKEVEN: Minus,
  ORDER_PLACED: FileText,
  ORDER_CANCELLED: XCircle,
  SYSTEM_INFO: Info,
  SYSTEM_ERROR: XCircle,
  SYSTEM_WARNING: AlertTriangle,
  SYSTEM_STARTUP: CircleDot,
  SYSTEM_SHUTDOWN: CircleStop,
  CONNECTION_ESTABLISHED: Link2,
  CONNECTION_LOST: Unlink,
  AGENT_SYNC: RefreshCw,
  PRICE_UPDATE: BarChart3,
  MARKET_ANALYSIS: TrendingUp,
};

// Severity class mapping
export const SEVERITY_CLASSES: Record<Severity, string> = {
  INFO: "log-info",
  SUCCESS: "log-success",
  WARNING: "log-warning",
  ERROR: "log-error",
};

export interface UseActivityLogsOptions {
  limit?: number;
  since?: string;
  eventType?: EventType;
  severity?: Severity;
  refreshInterval?: number;
}

// API Hook
export const useActivityLogs = ({
  limit = 10,
  since,
  eventType,
  severity,
  refreshInterval = 5000,
}: UseActivityLogsOptions = {}) => {
  return useQuery({
    queryKey: ["activity-logs", limit, since, eventType, severity],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.append("limit", limit.toString());
      
      if (since) params.append("since", since);
      if (eventType) params.append("event_type", eventType);
      if (severity) params.append("severity", severity);

      const response = await apiClient.get<ActivityLogsResponse>(
        `/activity-logs?${params.toString()}`
      );
      
      return response;
    },
    refetchInterval: refreshInterval,
    staleTime: 1000, // Consider data stale after 1 second
  });
};
