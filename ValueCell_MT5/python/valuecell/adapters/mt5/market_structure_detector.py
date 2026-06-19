"""
Market Structure Detector - HH/LL/CHoCH/BoS Detection

Detects market structure patterns based on swing points:
- Higher Highs (HH)
- Lower Lows (LL)
- Change of Character (CHoCH)
- Break of Structure (BoS)

This implementation follows the same logic as Dev_Bot_v11.cs
"""

from typing import Optional, Dict, List, Tuple
from datetime import datetime
from enum import Enum
import pandas as pd
from loguru import logger


class StructureType(Enum):
    """Types of market structure events."""
    HH = "HH"  # Higher High
    LL = "LL"  # Lower Low
    CHOCH_BULLISH = "CHoCH_Bullish"
    CHOCH_BEARISH = "CHoCH_Bearish"
    BOS_BULLISH = "BoS_Bullish"
    BOS_BEARISH = "BoS_Bearish"


class StructureStatus(Enum):
    """Status of structure events."""
    CONFIRMED = "Confirmed"
    ACTIVE = "Active"
    ACCEPTED = "Accepted"
    REFERENCE = "Reference"


class StructureEvent:
    """Represents a market structure event."""
    
    def __init__(
        self,
        event_type: StructureType,
        price: float,
        time: datetime,
        timeframe: str,
        status: StructureStatus,
        previous_price: float = 0.0,
        previous_time: Optional[datetime] = None
    ):
        self.type = event_type
        self.price = price
        self.time = time
        self.timeframe = timeframe
        self.status = status
        self.previous_price = previous_price
        self.previous_time = previous_time
    
    def __repr__(self):
        return (f"StructureEvent({self.type.value}, {self.price:.2f}, "
                f"{self.time}, {self.status.value})")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage."""
        return {
            "type": self.type.value,
            "price": self.price,
            "time": self.time,
            "timeframe": self.timeframe,
            "status": self.status.value,
            "previous_price": self.previous_price,
            "previous_time": self.previous_time
        }


class MarketStructureDetector:
    """
    Detects market structure patterns (HH/LL/CHoCH/BoS) from OHLCV data.
    
    Algorithm:
    1. Identify swing highs and swing lows
    2. Track accepted HH and LL levels
    3. Detect CHoCH (price breaks opposite extreme)
    4. Detect BoS (price breaks same direction extreme)
    """
    
    def __init__(
        self,
        swing_length: int = 5,
        timeframe: str = "M15",
        realtime_mode: bool = False
    ):
        """
        Initialize Market Structure Detector.
        
        Args:
            swing_length: Number of bars to look left/right for swing detection
            timeframe: Timeframe string (e.g., "M15", "H1", "H4")
            realtime_mode: If True, only detect NEW events (incremental detection)
        """
        self.swing_length = swing_length
        self.timeframe = timeframe
        self.realtime_mode = realtime_mode
        
        # State tracking
        self.last_accepted_hh: float = 0.0
        self.last_accepted_ll: float = 0.0
        self.last_hh_time: Optional[datetime] = None
        self.last_ll_time: Optional[datetime] = None
        
        # CHoCH tracking
        self.choch_bullish_triggered: bool = False
        self.choch_bullish_price: float = 0.0
        self.choch_bearish_triggered: bool = False
        self.choch_bearish_price: float = 0.0
        
        # BoS tracking
        self.bos_bullish_triggered: bool = False
        self.bos_bullish_price: float = 0.0
        self.bos_bearish_triggered: bool = False
        self.bos_bearish_price: float = 0.0
        
        # History
        self.structure_events: List[StructureEvent] = []
        
        # Real-time tracking (prevent duplicate detections)
        self.detected_swing_times: set = set()  # Track timestamps of detected swings
        self.last_processed_time: Optional[datetime] = None
        
        logger.info(f"MarketStructureDetector initialized (swing_length={swing_length}, "
                   f"tf={timeframe}, realtime={realtime_mode})")
    
    def detect(self, df: pd.DataFrame) -> List[StructureEvent]:
        """
        Detect market structure events from OHLCV data.
        
        Args:
            df: DataFrame with columns: time, open, high, low, close
        
        Returns:
            List of new structure events detected
        
        Notes:
            - In realtime_mode=False: Detects ALL events in dataframe (for backtesting)
            - In realtime_mode=True: Only detects NEW events (for live trading)
        """
        if df is None or len(df) < self.swing_length * 2 + 1:
            logger.warning("Insufficient data for structure detection")
            return []
        
        new_events = []
        
        # Find swing highs and lows
        swing_highs = self._find_swing_highs(df)
        swing_lows = self._find_swing_lows(df)
        
        # Process swing highs (potential HH detection)
        for idx, price, time in swing_highs:
            # In realtime mode, skip already detected swings
            if self.realtime_mode and time in self.detected_swing_times:
                continue
            
            event = self._check_higher_high(price, time)
            if event:
                new_events.append(event)
                self.structure_events.append(event)
                
                # Track this swing in realtime mode
                if self.realtime_mode:
                    self.detected_swing_times.add(time)
        
        # Process swing lows (potential LL detection)
        for idx, price, time in swing_lows:
            # In realtime mode, skip already detected swings
            if self.realtime_mode and time in self.detected_swing_times:
                continue
            
            event = self._check_lower_low(price, time)
            if event:
                new_events.append(event)
                self.structure_events.append(event)
                
                # Track this swing in realtime mode
                if self.realtime_mode:
                    self.detected_swing_times.add(time)
        
        # Check for CHoCH and BoS (ONLY on latest bar)
        if len(df) > 0:
            latest_bar = df.iloc[-1]
            current_high = latest_bar['high']
            current_low = latest_bar['low']
            current_time = latest_bar['time']
            
            # In realtime mode, only check if bar is new
            if self.realtime_mode and self.last_processed_time:
                if current_time <= self.last_processed_time:
                    # Bar already processed, skip CHoCH/BoS check
                    return new_events
            
            # Check CHoCH
            choch_event = self._check_choch(current_high, current_low, current_time)
            if choch_event:
                new_events.append(choch_event)
                self.structure_events.append(choch_event)
            
            # Check BoS
            bos_event = self._check_bos(current_high, current_low, current_time)
            if bos_event:
                new_events.append(bos_event)
                self.structure_events.append(bos_event)
            
            # Update last processed time in realtime mode
            if self.realtime_mode:
                self.last_processed_time = current_time
        
        return new_events
    
    def _find_swing_highs(self, df: pd.DataFrame) -> List[Tuple[int, float, datetime]]:
        """
        Find swing highs (local maxima).
        
        A swing high is a bar where high is higher than N bars before and after.
        
        Returns:
            List of (index, price, time) tuples
        """
        swing_highs = []
        
        for i in range(self.swing_length, len(df) - self.swing_length):
            current_high = df.iloc[i]['high']
            
            # Check if current high is higher than surrounding bars
            is_swing_high = True
            
            # Check left side
            for j in range(1, self.swing_length + 1):
                if current_high <= df.iloc[i - j]['high']:
                    is_swing_high = False
                    break
            
            # Check right side
            if is_swing_high:
                for j in range(1, self.swing_length + 1):
                    if current_high <= df.iloc[i + j]['high']:
                        is_swing_high = False
                        break
            
            if is_swing_high:
                swing_highs.append((i, current_high, df.iloc[i]['time']))
        
        return swing_highs
    
    def _find_swing_lows(self, df: pd.DataFrame) -> List[Tuple[int, float, datetime]]:
        """
        Find swing lows (local minima).
        
        A swing low is a bar where low is lower than N bars before and after.
        
        Returns:
            List of (index, price, time) tuples
        """
        swing_lows = []
        
        for i in range(self.swing_length, len(df) - self.swing_length):
            current_low = df.iloc[i]['low']
            
            # Check if current low is lower than surrounding bars
            is_swing_low = True
            
            # Check left side
            for j in range(1, self.swing_length + 1):
                if current_low >= df.iloc[i - j]['low']:
                    is_swing_low = False
                    break
            
            # Check right side
            if is_swing_low:
                for j in range(1, self.swing_length + 1):
                    if current_low >= df.iloc[i + j]['low']:
                        is_swing_low = False
                        break
            
            if is_swing_low:
                swing_lows.append((i, current_low, df.iloc[i]['time']))
        
        return swing_lows
    
    def _check_higher_high(
        self,
        price: float,
        time: datetime
    ) -> Optional[StructureEvent]:
        """
        Check if current swing high is a Higher High.
        
        A Higher High is when current high > last accepted HH.
        
        Args:
            price: Current swing high price
            time: Time of swing high
        
        Returns:
            StructureEvent if HH detected, None otherwise
        """
        if self.last_accepted_hh == 0.0:
            # First HH detected (initialization)
            self.last_accepted_hh = price
            self.last_hh_time = time
            
            logger.info(f"✅ [HH INIT] First HH: {price:.2f} @ {time}")
            
            return StructureEvent(
                StructureType.HH,
                price,
                time,
                self.timeframe,
                StructureStatus.REFERENCE,
                previous_price=0.0,
                previous_time=None
            )
        
        # Check if new high is higher than last accepted HH
        if price > self.last_accepted_hh:
            previous_hh = self.last_accepted_hh
            previous_time = self.last_hh_time
            
            self.last_accepted_hh = price
            self.last_hh_time = time
            
            logger.info(f"✅ [HH UPDATE] HH: {price:.2f} @ {time} (prev: {previous_hh:.2f})")
            
            return StructureEvent(
                StructureType.HH,
                price,
                time,
                self.timeframe,
                StructureStatus.ACCEPTED,
                previous_price=previous_hh,
                previous_time=previous_time
            )
        
        return None
    
    def _check_lower_low(
        self,
        price: float,
        time: datetime
    ) -> Optional[StructureEvent]:
        """
        Check if current swing low is a Lower Low.
        
        A Lower Low is when current low < last accepted LL.
        
        Args:
            price: Current swing low price
            time: Time of swing low
        
        Returns:
            StructureEvent if LL detected, None otherwise
        """
        if self.last_accepted_ll == 0.0:
            # First LL detected (initialization)
            self.last_accepted_ll = price
            self.last_ll_time = time
            
            logger.info(f"✅ [LL INIT] First LL: {price:.2f} @ {time}")
            
            return StructureEvent(
                StructureType.LL,
                price,
                time,
                self.timeframe,
                StructureStatus.REFERENCE,
                previous_price=0.0,
                previous_time=None
            )
        
        # Check if new low is lower than last accepted LL
        if price < self.last_accepted_ll:
            previous_ll = self.last_accepted_ll
            previous_time = self.last_ll_time
            
            self.last_accepted_ll = price
            self.last_ll_time = time
            
            logger.info(f"✅ [LL UPDATE] LL: {price:.2f} @ {time} (prev: {previous_ll:.2f})")
            
            return StructureEvent(
                StructureType.LL,
                price,
                time,
                self.timeframe,
                StructureStatus.ACCEPTED,
                previous_price=previous_ll,
                previous_time=previous_time
            )
        
        return None
    
    def _check_choch(
        self,
        current_high: float,
        current_low: float,
        current_time: datetime
    ) -> Optional[StructureEvent]:
        """
        Check for Change of Character (CHoCH).
        
        CHoCH Bullish: Price breaks above last accepted HH
        CHoCH Bearish: Price breaks below last accepted LL
        
        Args:
            current_high: Current bar's high
            current_low: Current bar's low
            current_time: Current bar's time
        
        Returns:
            StructureEvent if CHoCH detected, None otherwise
        """
        # CHoCH Bullish: Break above last LL (bullish reversal)
        if (self.last_accepted_ll > 0 and 
            not self.choch_bullish_triggered and
            current_high > self.last_accepted_ll):
            
            self.choch_bullish_triggered = True
            self.choch_bullish_price = current_high
            
            logger.info(f"🔥 [CHoCH BULLISH] Price broke above LL {self.last_accepted_ll:.2f} @ {current_time}")
            
            return StructureEvent(
                StructureType.CHOCH_BULLISH,
                current_high,
                current_time,
                self.timeframe,
                StructureStatus.CONFIRMED,
                previous_price=self.last_accepted_ll,
                previous_time=self.last_ll_time
            )
        
        # CHoCH Bearish: Break below last HH (bearish reversal)
        if (self.last_accepted_hh > 0 and 
            not self.choch_bearish_triggered and
            current_low < self.last_accepted_hh):
            
            self.choch_bearish_triggered = True
            self.choch_bearish_price = current_low
            
            logger.info(f"🔥 [CHoCH BEARISH] Price broke below HH {self.last_accepted_hh:.2f} @ {current_time}")
            
            return StructureEvent(
                StructureType.CHOCH_BEARISH,
                current_low,
                current_time,
                self.timeframe,
                StructureStatus.CONFIRMED,
                previous_price=self.last_accepted_hh,
                previous_time=self.last_hh_time
            )
        
        return None
    
    def _check_bos(
        self,
        current_high: float,
        current_low: float,
        current_time: datetime
    ) -> Optional[StructureEvent]:
        """
        Check for Break of Structure (BoS).
        
        BoS Bullish: Price breaks above last accepted HH (continuation)
        BoS Bearish: Price breaks below last accepted LL (continuation)
        
        Args:
            current_high: Current bar's high
            current_low: Current bar's low
            current_time: Current bar's time
        
        Returns:
            StructureEvent if BoS detected, None otherwise
        """
        # BoS Bullish: Break above last HH (bullish continuation)
        if (self.last_accepted_hh > 0 and 
            not self.bos_bullish_triggered and
            current_high > self.last_accepted_hh):
            
            self.bos_bullish_triggered = True
            self.bos_bullish_price = current_high
            
            logger.info(f"🚀 [BoS BULLISH] Price broke above HH {self.last_accepted_hh:.2f} @ {current_time}")
            
            return StructureEvent(
                StructureType.BOS_BULLISH,
                current_high,
                current_time,
                self.timeframe,
                StructureStatus.CONFIRMED,
                previous_price=self.last_accepted_hh,
                previous_time=self.last_hh_time
            )
        
        # BoS Bearish: Break below last LL (bearish continuation)
        if (self.last_accepted_ll > 0 and 
            not self.bos_bearish_triggered and
            current_low < self.last_accepted_ll):
            
            self.bos_bearish_triggered = True
            self.bos_bearish_price = current_low
            
            logger.info(f"🚀 [BoS BEARISH] Price broke below LL {self.last_accepted_ll:.2f} @ {current_time}")
            
            return StructureEvent(
                StructureType.BOS_BEARISH,
                current_low,
                current_time,
                self.timeframe,
                StructureStatus.CONFIRMED,
                previous_price=self.last_accepted_ll,
                previous_time=self.last_ll_time
            )
        
        return None
    
    def reset_choch_bos_flags(self):
        """Reset CHoCH and BoS trigger flags."""
        self.choch_bullish_triggered = False
        self.choch_bearish_triggered = False
        self.bos_bullish_triggered = False
        self.bos_bearish_triggered = False
        
        logger.debug("Reset CHoCH/BoS flags")
    
    def get_current_state(self) -> Dict:
        """
        Get current market structure state.
        
        Returns:
            Dict with current HH, LL, CHoCH, BoS status
        """
        return {
            "last_accepted_hh": self.last_accepted_hh,
            "last_accepted_ll": self.last_accepted_ll,
            "last_hh_time": self.last_hh_time,
            "last_ll_time": self.last_ll_time,
            "choch_bullish_triggered": self.choch_bullish_triggered,
            "choch_bullish_price": self.choch_bullish_price,
            "choch_bearish_triggered": self.choch_bearish_triggered,
            "choch_bearish_price": self.choch_bearish_price,
            "bos_bullish_triggered": self.bos_bullish_triggered,
            "bos_bullish_price": self.bos_bullish_price,
            "bos_bearish_triggered": self.bos_bearish_triggered,
            "bos_bearish_price": self.bos_bearish_price,
            "total_events": len(self.structure_events)
        }
    
    def get_recent_events(self, count: int = 10) -> List[StructureEvent]:
        """
        Get most recent structure events.
        
        Args:
            count: Number of recent events to return
        
        Returns:
            List of most recent StructureEvents
        """
        return self.structure_events[-count:] if len(self.structure_events) >= count else self.structure_events


if __name__ == "__main__":
    """
    Test script for MarketStructureDetector.
    
    Usage:
        cd python
        python -m valuecell.adapters.mt5.market_structure_detector
    """
    from dotenv import load_dotenv
    from valuecell.adapters.mt5.mt5_adapter import MT5Adapter, TIMEFRAME_M15
    import sys
    
    # Load environment variables
    load_dotenv()
    
    # Configure logger
    logger.remove()
    logger.add(sys.stdout, level="INFO", 
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
    
    print("=" * 60)
    print("🧪 MARKET STRUCTURE DETECTOR TEST")
    print("=" * 60)
    
    # Initialize MT5
    print("\n1️⃣  Connecting to MT5...")
    adapter = MT5Adapter()
    if not adapter.initialize():
        print("❌ Failed to connect to MT5")
        sys.exit(1)
    
    print("✅ MT5 Connected")
    
    # Get historical data
    print("\n2️⃣  Fetching historical data (XAUUSD M15, 200 bars)...")
    symbol = "XAUUSD"
    df = adapter.get_rates(symbol, TIMEFRAME_M15, count=200)
    
    if df is None:
        print("❌ Failed to fetch data")
        adapter.shutdown()
        sys.exit(1)
    
    print(f"✅ Retrieved {len(df)} bars")
    
    # Initialize detector
    print("\n3️⃣  Initializing Market Structure Detector...")
    detector = MarketStructureDetector(swing_length=5, timeframe="M15")
    print("✅ Detector initialized")
    
    # Detect structure
    print("\n4️⃣  Detecting market structure...")
    events = detector.detect(df)
    
    print(f"\n✅ Detected {len(events)} structure events:")
    for event in events[-10:]:  # Show last 10 events
        print(f"   - {event.type.value}: {event.price:.2f} @ {event.time} ({event.status.value})")
    
    # Show current state
    print("\n5️⃣  Current Market Structure State:")
    state = detector.get_current_state()
    print(f"   Last HH: {state['last_accepted_hh']:.2f}")
    print(f"   Last LL: {state['last_accepted_ll']:.2f}")
    print(f"   CHoCH Bullish: {'✅' if state['choch_bullish_triggered'] else '❌'}")
    print(f"   CHoCH Bearish: {'✅' if state['choch_bearish_triggered'] else '❌'}")
    print(f"   BoS Bullish: {'✅' if state['bos_bullish_triggered'] else '❌'}")
    print(f"   BoS Bearish: {'✅' if state['bos_bearish_triggered'] else '❌'}")
    
    # Cleanup
    print("\n6️⃣  Cleanup...")
    adapter.shutdown()
    
    print("\n" + "=" * 60)
    print("✅ TEST COMPLETE")
    print("=" * 60)
