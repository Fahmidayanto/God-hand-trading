"""
Execution Module - MT5 Order Execution & Position Management

This module handles:
- Order placement via MT5 Python API
- Position monitoring and tracking
- SL/TP modifications
- Position closure
- Paper trading mode
"""

from .execution_agent import ExecutionAgent

__all__ = ["ExecutionAgent"]
