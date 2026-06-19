"""Data models for verification system."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CSVRecord:
    """Represents a single record from a backtest CSV file.
    
    Attributes:
        Ticket: Trade ticket number
        Symbol: Trading symbol (e.g., "XAUUSD")
        Type: Trade type ("BUY" or "SELL")
        EntryPrice: Entry price level
        ExitPrice: Exit price level (0.0 for REJECTED)
        SL: Stop Loss level
        TP: Take Profit level
        Profit: Raw profit before costs
        Spread_Cost: Spread cost
        Commission: Commission cost
        Swap: Swap/overnight fee
        Net_Profit: Final profit after all costs
        Session: Trading session (e.g., "Tokyo_London_Overlap")
        Session_IsDST: Whether DST applies ("YES" or "NO")
        EntryTime: Entry timestamp ("YYYY.MM.DD HH:MM:SS")
        ExitTime: Exit timestamp ("YYYY.MM.DD HH:MM:SS" or "1970.01.01 00:00:00" for REJECTED)
        LotSize: Trade lot size
        MagicNumber: EA magic number
        Timeframe: Trading timeframe
        Status: Execution status ("EXECUTED" or "REJECTED")
        Reject_Reason: Rejection reason ("N/A" or filter name)
    """
    Ticket: int
    Symbol: str
    Type: str
    EntryPrice: float
    ExitPrice: float
    SL: float
    TP: float
    Profit: float
    Spread_Cost: float
    Commission: float
    Swap: float
    Net_Profit: float
    Session: str
    Session_IsDST: str
    EntryTime: str
    ExitTime: str
    LotSize: float
    MagicNumber: int
    Timeframe: str
    Status: str
    Reject_Reason: str


@dataclass
class SignalEntry:
    """Represents a single trading signal entry from markdown.
    
    Attributes:
        number: Entry number in the signal log
        entry_time: Entry timestamp ("YYYY.MM.DD HH:MM")
        type: Trade type ("BUY" or "SELL")
        entry_price: Entry price level
        session: Trading session
        v7_status: V7 status ("✅", "❌", "🚫 H1", or "—")
        v8_status: V8 status
        v9_status: V9 status
        v10_status: V10 status
        profit: Profit string ("+$X.XX" or "-$X.XX" or "—")
        catatan: Notes/summary (e.g., "WIN semua", "V7+V8 WIN")
        analisa: Complete analysis text in Indonesian
    """
    number: int
    entry_time: str
    type: str
    entry_price: float
    session: str
    v7_status: str
    v8_status: str
    v9_status: str
    v10_status: str
    profit: str
    catatan: str
    analisa: str


@dataclass
class VersionData:
    """Represents data for a single backtest version.
    
    Attributes:
        Status: Execution status ("EXECUTED" or "REJECTED")
        Net_Profit: Final profit after all costs
        ExitTime: Exit timestamp
        Swap: Swap/overnight fee
        Reject_Reason: Rejection reason ("N/A" or filter name)
        SL: Stop Loss level
        TP: Take Profit level
    """
    Status: str
    Net_Profit: float
    ExitTime: str
    Swap: float
    Reject_Reason: str
    SL: float
    TP: float


@dataclass
class UnifiedSignal:
    """Represents a unified signal across all 4 backtest versions.
    
    Attributes:
        signal_key: Unique key ("EntryTime_Type_EntryPrice")
        EntryTime: Entry timestamp ("YYYY.MM.DD HH:MM")
        Type: Trade type ("BUY" or "SELL")
        EntryPrice: Entry price level
        Session: Trading session
        v7: Version 7 data
        v8: Version 8 data
        v9: Version 9 data
        v10: Version 10 data
    """
    signal_key: str
    EntryTime: str
    Type: str
    EntryPrice: float
    Session: str
    v7: Optional[VersionData]
    v8: Optional[VersionData]
    v9: Optional[VersionData]
    v10: Optional[VersionData]
