"""
Performance Monitor - Real-time System Performance Tracking

Monitors and reports:
1. Agent execution times
2. Memory usage
3. API call latency
4. Trading metrics
5. System health

Usage:
    python scripts/performance_monitor.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))

from loguru import logger
import time
import psutil
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import deque


class PerformanceMonitor:
    """
    Performance Monitor - Tracks system performance metrics
    """
    
    def __init__(self, window_size: int = 100):
        """
        Initialize Performance Monitor.
        
        Args:
            window_size: Number of measurements to keep in memory
        """
        self.name = "PerformanceMonitor"
        self.version = "1.0.0"
        self.window_size = window_size
        
        # Metric storage (circular buffers)
        self.agent_times = {
            "market_structure": deque(maxlen=window_size),
            "ml_prediction": deque(maxlen=window_size),
            "risk_management": deque(maxlen=window_size),
            "sentiment": deque(maxlen=window_size),
            "orchestrator": deque(maxlen=window_size)
        }
        
        self.api_latencies = deque(maxlen=window_size)
        self.memory_usage = deque(maxlen=window_size)
        self.trading_metrics = {
            "signals_generated": 0,
            "signals_approved": 0,
            "signals_rejected": 0,
            "orders_placed": 0,
            "orders_failed": 0,
            "positions_closed": 0,
            "circuit_breaker_trips": 0
        }
        
        # Start time
        self.start_time = datetime.now()
        
        logger.info(f"✅ {self.name} v{self.version} initialized")
    
    def record_agent_time(self, agent_name: str, execution_time_ms: float):
        """Record agent execution time"""
        if agent_name in self.agent_times:
            self.agent_times[agent_name].append(execution_time_ms)
    
    def record_api_latency(self, latency_ms: float):
        """Record API call latency"""
        self.api_latencies.append(latency_ms)
    
    def record_memory_usage(self):
        """Record current memory usage"""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        self.memory_usage.append(memory_mb)
    
    def increment_metric(self, metric_name: str):
        """Increment a trading metric counter"""
        if metric_name in self.trading_metrics:
            self.trading_metrics[metric_name] += 1
    
    def get_agent_stats(self, agent_name: str) -> Dict[str, Any]:
        """Get statistics for an agent"""
        if agent_name not in self.agent_times or len(self.agent_times[agent_name]) == 0:
            return {"error": "No data available"}
        
        times = list(self.agent_times[agent_name])
        return {
            "count": len(times),
            "avg_ms": sum(times) / len(times),
            "min_ms": min(times),
            "max_ms": max(times),
            "p50_ms": sorted(times)[len(times) // 2],
            "p95_ms": sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else max(times)
        }
    
    def get_api_stats(self) -> Dict[str, Any]:
        """Get API latency statistics"""
        if len(self.api_latencies) == 0:
            return {"error": "No data available"}
        
        latencies = list(self.api_latencies)
        return {
            "count": len(latencies),
            "avg_ms": sum(latencies) / len(latencies),
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "p50_ms": sorted(latencies)[len(latencies) // 2],
            "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 20 else max(latencies)
        }
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics"""
        if len(self.memory_usage) == 0:
            return {"error": "No data available"}
        
        memory = list(self.memory_usage)
        return {
            "current_mb": memory[-1],
            "avg_mb": sum(memory) / len(memory),
            "min_mb": min(memory),
            "max_mb": max(memory)
        }
    
    def get_trading_stats(self) -> Dict[str, Any]:
        """Get trading statistics"""
        total_signals = self.trading_metrics['signals_generated']
        approval_rate = (self.trading_metrics['signals_approved'] / total_signals * 100) if total_signals > 0 else 0
        
        total_orders = self.trading_metrics['orders_placed'] + self.trading_metrics['orders_failed']
        order_success_rate = (self.trading_metrics['orders_placed'] / total_orders * 100) if total_orders > 0 else 0
        
        return {
            "signals": {
                "generated": self.trading_metrics['signals_generated'],
                "approved": self.trading_metrics['signals_approved'],
                "rejected": self.trading_metrics['signals_rejected'],
                "approval_rate_pct": approval_rate
            },
            "orders": {
                "placed": self.trading_metrics['orders_placed'],
                "failed": self.trading_metrics['orders_failed'],
                "success_rate_pct": order_success_rate
            },
            "positions": {
                "closed": self.trading_metrics['positions_closed']
            },
            "safety": {
                "circuit_breaker_trips": self.trading_metrics['circuit_breaker_trips']
            }
        }
    
    def get_system_health(self) -> str:
        """Get overall system health status"""
        # Check various metrics
        memory_stats = self.get_memory_stats()
        api_stats = self.get_api_stats()
        
        issues = []
        
        # Memory check
        if 'current_mb' in memory_stats and memory_stats['current_mb'] > 500:
            issues.append("High memory usage")
        
        # API latency check
        if 'avg_ms' in api_stats and api_stats['avg_ms'] > 1000:
            issues.append("High API latency")
        
        # Circuit breaker check
        if self.trading_metrics['circuit_breaker_trips'] > 0:
            issues.append("Circuit breaker tripped")
        
        # Order failure check
        total_orders = self.trading_metrics['orders_placed'] + self.trading_metrics['orders_failed']
        if total_orders > 0 and (self.trading_metrics['orders_failed'] / total_orders) > 0.2:
            issues.append("High order failure rate")
        
        if len(issues) == 0:
            return "HEALTHY"
        elif len(issues) <= 2:
            return "WARNING"
        else:
            return "CRITICAL"
    
    def get_full_report(self) -> Dict[str, Any]:
        """Get complete performance report"""
        uptime = datetime.now() - self.start_time
        
        return {
            "system": {
                "name": self.name,
                "version": self.version,
                "uptime_seconds": int(uptime.total_seconds()),
                "uptime_formatted": str(uptime).split('.')[0],
                "health": self.get_system_health()
            },
            "agents": {
                "market_structure": self.get_agent_stats("market_structure"),
                "ml_prediction": self.get_agent_stats("ml_prediction"),
                "risk_management": self.get_agent_stats("risk_management"),
                "sentiment": self.get_agent_stats("sentiment"),
                "orchestrator": self.get_agent_stats("orchestrator")
            },
            "api": self.get_api_stats(),
            "memory": self.get_memory_stats(),
            "trading": self.get_trading_stats()
        }
    
    def print_report(self):
        """Print formatted performance report"""
        report = self.get_full_report()
        
        logger.info("\n" + "="*70)
        logger.info("📊 PERFORMANCE REPORT")
        logger.info("="*70)
        
        # System
        logger.info("\n🖥️  SYSTEM")
        logger.info(f"   Uptime: {report['system']['uptime_formatted']}")
        health = report['system']['health']
        health_emoji = "✅" if health == "HEALTHY" else "⚠️" if health == "WARNING" else "❌"
        logger.info(f"   Health: {health_emoji} {health}")
        
        # Agents
        logger.info("\n🤖 AGENTS")
        for agent_name, stats in report['agents'].items():
            if 'error' not in stats:
                logger.info(f"   {agent_name}:")
                logger.info(f"      Count: {stats['count']}")
                logger.info(f"      Avg: {stats['avg_ms']:.1f}ms")
                logger.info(f"      P95: {stats['p95_ms']:.1f}ms")
        
        # API
        logger.info("\n🌐 API")
        api_stats = report['api']
        if 'error' not in api_stats:
            logger.info(f"   Calls: {api_stats['count']}")
            logger.info(f"   Avg Latency: {api_stats['avg_ms']:.1f}ms")
            logger.info(f"   P95 Latency: {api_stats['p95_ms']:.1f}ms")
        
        # Memory
        logger.info("\n💾 MEMORY")
        mem_stats = report['memory']
        if 'error' not in mem_stats:
            logger.info(f"   Current: {mem_stats['current_mb']:.1f} MB")
            logger.info(f"   Average: {mem_stats['avg_mb']:.1f} MB")
            logger.info(f"   Peak: {mem_stats['max_mb']:.1f} MB")
        
        # Trading
        logger.info("\n📈 TRADING")
        trade_stats = report['trading']
        logger.info(f"   Signals Generated: {trade_stats['signals']['generated']}")
        logger.info(f"   Signals Approved: {trade_stats['signals']['approved']} "
                   f"({trade_stats['signals']['approval_rate_pct']:.1f}%)")
        logger.info(f"   Orders Placed: {trade_stats['orders']['placed']}")
        logger.info(f"   Order Success Rate: {trade_stats['orders']['success_rate_pct']:.1f}%")
        logger.info(f"   Positions Closed: {trade_stats['positions']['closed']}")
        logger.info(f"   Circuit Breaker Trips: {trade_stats['safety']['circuit_breaker_trips']}")
        
        logger.info("\n" + "="*70)
    
    def save_report(self, filename: str = None):
        """Save report to JSON file"""
        if filename is None:
            filename = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report = self.get_full_report()
        
        filepath = os.path.join("logs", filename)
        os.makedirs("logs", exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"📝 Report saved to: {filepath}")
        return filepath


# ========== DEMO/TEST MODE ==========

if __name__ == "__main__":
    logger.info("Testing PerformanceMonitor...")
    
    # Initialize
    monitor = PerformanceMonitor()
    
    # Simulate some measurements
    logger.info("\n📊 Simulating performance measurements...")
    
    # Agent times
    import random
    for i in range(50):
        monitor.record_agent_time("market_structure", random.uniform(80, 120))
        monitor.record_agent_time("ml_prediction", random.uniform(850, 950))
        monitor.record_agent_time("risk_management", random.uniform(15, 25))
        monitor.record_agent_time("sentiment", random.uniform(5, 15))
        monitor.record_agent_time("orchestrator", random.uniform(150, 180))
    
    # API latencies
    for i in range(50):
        monitor.record_api_latency(random.uniform(50, 150))
    
    # Memory usage
    for i in range(50):
        monitor.record_memory_usage()
    
    # Trading metrics
    monitor.increment_metric("signals_generated")
    monitor.increment_metric("signals_generated")
    monitor.increment_metric("signals_generated")
    monitor.increment_metric("signals_approved")
    monitor.increment_metric("signals_approved")
    monitor.increment_metric("signals_rejected")
    monitor.increment_metric("orders_placed")
    monitor.increment_metric("orders_placed")
    monitor.increment_metric("positions_closed")
    
    # Print report
    time.sleep(1)
    monitor.print_report()
    
    # Save report
    monitor.save_report("test_performance_report.json")
    
    logger.info("\n✅ PerformanceMonitor test complete!")
