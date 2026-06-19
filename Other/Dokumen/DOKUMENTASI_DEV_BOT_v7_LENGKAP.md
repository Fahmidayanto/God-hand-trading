# 📘 DOKUMENTASI LENGKAP - DEV BOT v7.cs
## Expert Advisor untuk MetaTrader 5 - Pattern Detection & Automated Trading

**File Path:** `d:\Project\Project MT5\Dev Bot v7.cs`  
**Language:** MQL5 (MetaQuotes Language 5)  
**Baris Code:** ~3,500+ lines (M15 specific - optimized version)  
**Versi:** 7.0 (Production Ready - May 2026 Update)  
**Status:** Active Production EA - Pattern Detection Focused  
**Instrumen:** XAUUSD (Gold)  
**Timeframe:** M15 (15-min primary) & H1 (1-hour confirmation) dual timeframe  
**Tanggal Update:** May 12, 2026  
**Update Focus:** Session Zone Tracking, Enhanced Trailing Stop, Spread/Commission Tracking

---

## 📋 DAFTAR ISI

1. [Overview & Purpose](#-overview--purpose)
2. [Architecture & Modules](#-architecture--modules)
3. [Data Structures](#-data-structures)
4. [Global Variables](#-global-variables)
5. [Input Parameters (Updated May 2026)](#-input-parameters)
6. [Core Functions](#-core-functions)
7. [Pattern Detection Logic](#-pattern-detection-logic)
8. [Trading Execution Module](#-trading-execution-module)
9. [Trailing Stop System](#-trailing-stop-system-updated-may-2026)
10. [Data Export System](#-data-export-system)
11. [Session Zone Tracking](#-session-zone-tracking)
12. [Entry Filters & Conditions](#-entry-filters--conditions-updated-may-2026)
13. [End-to-End Workflow](#️-end-to-end-workflow)

---

## 🎯 OVERVIEW & PURPOSE

### Deskripsi Singkat
**Dev Bot v7.cs** adalah Expert Advisor (Robot Trading) otomatis untuk MetaTrader 5 yang dirancang untuk:
- ✅ **Deteksi Smart Money Concept (SMC) Patterns** - HH, LL, BoS, CHoCH
- ✅ **Dual Timeframe Analysis** - Sinergis antara M15 (execution) dan H1 (confirmation)
- ✅ **Automated Trade Execution** - Entry otomatis saat kondisi terpenuhi
- ✅ **Smart Risk Management** - Trailing stop 3-tahap, dynamic SL/TP
- ✅ **Comprehensive Data Logging** - Export hasil ke CSV untuk AI training
- ✅ **Session Zone Tracking** - Monitor trading sessions (Asia, London, NY, Sydney)

### Tujuan Utama
```
INPUT: Real-time market data XAUUSD (M15 & H1)
       ↓
PROCESS: Deteksi pola trading, analyze market structure, filter sinyal
       ↓
OUTPUT: Otomatis execute trades dengan risk management
       ↓
RESULT: CSV files untuk backtesting, analysis, dan AI model training
```

### Instrumen & Timeframe
- **Symbol:** XAUUSD (Gold/Emas)
- **Primary Timeframe:** M15 (untuk entry signals)
- **Secondary Timeframe:** H1 (untuk confirmation & filter)
- **Session Monitoring:** Dual-session (H1 & M15)

---

## 🏗️ ARCHITECTURE & MODULES

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│          DEV BOT v7.cs - EXPERT ADVISOR (MQL5)              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 1. INITIALIZATION MODULE (OnInit)                   │   │
│  │    - Initialize indicators (EMA200 H1 & M15)        │   │
│  │    - Setup trading object (CTrade)                  │   │
│  │    - Load historical data (backfill)                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 2. MARKET DATA CAPTURE (Every Tick)                 │   │
│  │    - Read M15 OHLC data                             │   │
│  │    - Read H1 OHLC data                              │   │
│  │    - Calculate EMA200 values                        │   │
│  │    - Detect new candles (bar opening)               │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 3. PATTERN DETECTION MODULE (Per Candle)            │   │
│  │    ┌─ M15 Detection:                                │   │
│  │    │  ├─ HH/LL Detection (Higher High/Lower Low)    │   │
│  │    │  ├─ BoS Detection (Break of Structure)         │   │
│  │    │  └─ CHoCH Detection (Change of Character)      │   │
│  │    │                                                 │   │
│  │    └─ H1 Detection:                                 │   │
│  │       ├─ HH/LL Detection                            │   │
│  │       ├─ BoS Detection                              │   │
│  │       └─ CHoCH Detection                            │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 4. SIGNAL FILTERING & VALIDATION                    │   │
│  │    - Cross-confirm dengan H1 trend                  │   │
│  │    - Check EMA200 alignment                         │   │
│  │    - Validate breakout levels                       │   │
│  │    - Check blackout hours (low liquidity)           │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 5. TRADE EXECUTION MODULE                           │   │
│  │    - Calculate entry price                          │   │
│  │    - Calculate SL & TP levels                       │   │
│  │    - Execute BUY or SELL order                      │   │
│  │    - Track trade metrics                            │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 6. POSITION MANAGEMENT MODULE                       │   │
│  │    - Monitor active positions                       │   │
│  │    - Apply trailing stop (3 levels)                 │   │
│  │    - Check minimum hold time                        │   │
│  │    - Force close if max hold time exceeded          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 7. DATA LOGGING & EXPORT MODULE                     │   │
│  │    - Log all patterns detected (HH, LL, BoS, CHoCH) │   │
│  │    - Record all trades executed                     │   │
│  │    - Export market structure snapshots              │   │
│  │    - Generate CSV files untuk backtest analysis     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 8. SESSION ZONE TRACKING MODULE                     │   │
│  │    - Identify active trading session (4 sessions)   │   │
│  │    - Record session-specific metrics                │   │
│  │    - Track session performance                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Module Breakdown

| Module | Location | Purpose | Key Functions |
|--------|----------|---------|---|
| **Initialization** | OnInit() | Setup & warm-up | Initialize indicators, backfill history |
| **Market Data** | OnTick() | Real-time data capture | Read OHLC, EMA values, detect bars |
| **Pattern Detection** | DetectAndDraw_M15/H1() | Identify trading patterns | Detect HH, LL, BoS, CHoCH |
| **Signal Filtering** | Filter Functions | Validate signals | EMA check, H1 confirmation, session check |
| **Trade Execution** | Trade.Buy/Sell() | Execute orders | Entry logic, lot sizing, SL/TP |
| **Position Mgmt** | ApplyTrailingStop_M15() | Manage positions | Trailing stop, hold time checks |
| **Data Logging** | SaveLLHHBOSToArray() | Store pattern data | In-memory arrays, later exported |
| **Data Export** | ExportAllData() | Output to CSV | 6 CSV file types |
| **Session Tracking** | UpdateSessionZoneTracking() | Monitor sessions | Identify & track 4 trading sessions |

---

## 📊 DATA STRUCTURES

### 1. BacktestTrade Structure

**Purpose:** Store detail setiap trade yang dieksekusi

```cpp
struct BacktestTrade
{
    ulong     ticket;           // Unique trade identifier (dari MT5)
    string    symbol;           // "XAUUSD"
    string    type;             // "BUY" atau "SELL"
    double    entry_price;      // Harga open trade (entry point)
    double    exit_price;       // Harga close trade (exit point)
    double    sl;               // Stop Loss price level
    double    tp;               // Take Profit price level
    double    profit;           // Profit/Loss dalam currency/pips
    datetime  entry_time;       // Waktu entry (timestamp)
    datetime  exit_time;        // Waktu exit (timestamp)
    double    lot_size;         // Ukuran posisi (0.01 - 0.1 lots)
    ulong     magic_number;     // Magic number untuk filtering
    string    timeframe;        // "M15" atau "H1"
    double    spread_cost;      // Cost dari bid-ask spread
    double    commission;       // Broker commission
    string    session_name;     // "Asia", "London", "NewYork", "Sydney"
};
```

**Usage:** Setiap kali trade ditutup, data disimpan di array global `g_BacktestTrades[]` untuk later export ke CSV.

---

### 2. LLHHBOSData Structure

**Purpose:** Store smart money pattern data (LL, HH, BoS, CHoCH)

```cpp
struct LLHHBOSData
{
    string    type;             // "LL", "HH", "BoS", atau "CHoCH"
    string    direction;        // "Bullish" atau "Bearish"
    double    price;            // Price level di mana pattern terdeteksi
    datetime  time;             // Waktu detection (bar opening time)
    string    timeframe;        // "M15" atau "H1"
    string    status;           // "Confirmed", "Active", "Target", "Rejected"
    double    previous_price;   // Previous HH/LL level (untuk reference)
    datetime  previous_time;    // Waktu previous level
};
```

**Usage:** Stored di `g_LLHHBOSData[]` array. Later sorted by time dan exported ke `LLHHBOSData_XAUUSD_*.csv`.

---

### 3. AcceptedLevelHistory Structure

**Purpose:** Track history dari accepted levels (valid HH & LL)

```cpp
struct AcceptedLevelHistory
{
    string    type;             // "HH" atau "LL"
    double    price;            // Price level
    datetime  time;             // Detection time
    string    timeframe;        // "M15" atau "H1"
};
```

**Usage:** Membantu tracking perubahan accepted levels untuk validation logic.

---

### 4. UnifiedEvent Structure

**Purpose:** Unified event log untuk sorting chronologically

```cpp
struct UnifiedEvent
{
    datetime  time;             // Waktu event (untuk sorting)
    string    type;             // "CHoCH", "BoS", "HH", "LL"
    string    direction;        // "Bullish", "Bearish"
    double    price;            // Price level
    string    timeframe;        // "M15" atau "H1"
    string    status;           // "Confirmed", "Accepted"
    double    previousPrice;    // Previous reference price
    string    previousTime;     // Previous time
};
```

**Usage:** Membantu sorting & organizing semua events chronologically untuk export.

---

### 5. MarketStructureRecord Structure

**Purpose:** Comprehensive snapshot dari market structure state per candle

```cpp
struct MarketStructureRecord
{
    datetime  time;                    // Candle time
    string    timeframe;               // "M15" atau "H1"
    
    // Levels
    double    lastAcceptedHH;          // Last accepted Higher High price
    double    lastAcceptedLL;          // Last accepted Lower Low price
    
    // CHoCH Status (Bullish & Bearish)
    bool      chochBullishTriggered;   // Flag: CHoCH Bullish occurred
    double    chochBullishPrice;       // Price saat CHoCH bullish
    
    bool      chochBearishTriggered;   // Flag: CHoCH Bearish occurred
    double    chochBearishPrice;       // Price saat CHoCH bearish
    
    // BoS Status (Bullish & Bearish)
    bool      bosBullishTriggered;     // Flag: BoS Bullish occurred
    double    bosBullishPrice;         // Price saat BoS bullish
    
    bool      bosBearishTriggered;     // Flag: BoS Bearish occurred
    double    bosBearishPrice;         // Price saat BoS bearish
    
    // Technical Indicators
    double    ema200;                  // EMA200 value at this time
};
```

**Usage:** Captured per candle, exported ke `MarketStructureToCSV()` untuk detailed analysis.

---

### 6. SessionZoneRecord Structure

**Purpose:** Track trading session zones performance

```cpp
struct SessionZoneRecord
{
    datetime  time;               // Start time of session
    string    sessionName;        // "Sydney", "Asia", "London", "NewYork"
    bool      isSessionActive;    // Is this session currently active
    double    sessionOpenPrice;   // Opening price saat session start
    double    sessionHighPrice;   // Highest price dalam session
    double    sessionLowPrice;    // Lowest price dalam session
    double    sessionClosePrice;  // Closing price saat session end
    int       sessionBarsCount;   // Jumlah bars dalam session
};
```

**Usage:** Exported ke `SessionZone_XAUUSD_*.csv` untuk session-specific analysis.

---

### 7. TradeRecord_M15 Structure

**Purpose:** Track individual trades per timeframe (M15)

```cpp
struct TradeRecord_M15
{
    ulong     ticket;            // Trade ticket from MT5
    double    entry_price;       // Entry price
    double    sl;                // Stop Loss level
    double    tp;                // Take Profit level
    datetime  entry_time;        // Entry time
    double    exit_price;        // Exit price (when closed)
    datetime  exit_time;         // Exit time (when closed)
    double    profit;            // Profit/Loss
    string    type;              // "BUY" atau "SELL"
};
```

**Usage:** Tracks active & closed trades untuk the M15 timeframe specifically.

---

## 🌐 GLOBAL VARIABLES

### Category 1: Pattern Level Tracking

**M15 Pattern Variables:**
```cpp
double    lastHH_M15;                    // Last Higher High price detected
datetime  timeLastHH_M15;                // Time of last HH

double    lastLL_M15;                    // Last Lower Low price detected
datetime  timeLastLL_M15;                // Time of last LL

double    lastValidHH_M15;               // Accepted HH (valid)
double    lastValidLL_M15;               // Accepted LL (valid)

double    lastRejectedHH_M15;            // Rejected HH (invalid)
datetime  timeRejectedHH_M15;            // Time HH was rejected

double    lastRejectedLL_M15;            // Rejected LL (invalid)
datetime  timeRejectedLL_M15;            // Time LL was rejected
```

**H1 Pattern Variables:** (Similar struktur untuk H1)
```cpp
double    lastHH_H1, lastLL_H1;
datetime  timeLastHH_H1, timeLastLL_H1;
double    lastValidHH_H1, lastValidLL_H1;
// ... etc
```

---

### Category 2: Pattern State Flags

**CHoCH Flags (Bullish/Bearish):**
```cpp
// M15
bool      chochBullish_M15;              // Flag: CHoCH Bullish active
datetime  time_choch_bullish_M15;        // Time CHoCH bullish triggered
bool      chochBearish_M15;              // Flag: CHoCH Bearish active
datetime  time_choch_bearish_M15;        // Time CHoCH bearish triggered

// H1
bool      chochBullish_H1;
datetime  time_choch_bullish_H1;
bool      chochBearish_H1;
datetime  time_choch_bearish_H1;
```

**BoS Flags (Bullish/Bearish):**
```cpp
// M15
bool      bosBullishConfirmedFlag_M15;   // Flag: BoS Bullish confirmed
datetime  timeBoSBullish_M15;            // Time BoS bullish triggered
bool      bosBearishConfirmedFlag_M15;   // Flag: BoS Bearish confirmed
datetime  timeBoSBearish_M15;            // Time BoS bearish triggered

// H1
bool      bosBullishConfirmedFlag_H1;
datetime  timeBoSBullish_H1;
bool      bosBearishConfirmedFlag_H1;
datetime  timeBoSBearish_H1;
```

**Trend Flags:**
```cpp
// M15
bool      isInTrendBullish_M15;          // Currently in bullish trend
bool      isInTrendBearish_M15;          // Currently in bearish trend

// H1
bool      isInTrendBullish_H1;
bool      isInTrendBearish_H1;
```

---

### Category 3: Entry & Exit Management

**Entry Counters:**
```cpp
// M15
int       entryCountBuy_M15;             // Number of buy entries dalam current cycle
int       entryCountSell_M15;            // Number of sell entries dalam current cycle
datetime  lastEntryTime_M15;             // Time of last buy entry
datetime  lastSellEntryTime_M15;         // Time of last sell entry

// H1
int       entryCountBuy_H1;
int       entryCountSell_H1;
datetime  lastEntryTime_H1;
datetime  lastSellEntryTime_H1;
```

**Position Tracking:**
```cpp
// M15
bool      hasBuyPosition_M15;            // Is there an active BUY position
bool      hasSellPosition_M15;           // Is there an active SELL position
bool      lastHasBuyPosition_M15;        // Previous state (untuk change detection)
bool      lastHasSellPosition_M15;       // Previous state

TradeRecord_M15 activeBuyTrade_M15;      // Active buy trade data
TradeRecord_M15 activeSellTrade_M15;     // Active sell trade data
```

---

### Category 4: Trailing Stop Management

**Trailing Stop Flags:**
```cpp
// M15
double    buyEntryPrice_M15;             // Entry price of buy position
double    sellEntryPrice_M15;            // Entry price of sell position
bool      trailingStopActiveBuy_M15;     // Is trailing stop active for buy
bool      trailingStopActiveSell_M15;    // Is trailing stop active for sell

// H1
double    buyEntryPrice_H1;
double    sellEntryPrice_H1;
bool      trailingStopActiveBuy_H1;
bool      trailingStopActiveSell_H1;
```

---

### Category 5: Session Zone Tracking

**Session Variables:**
```cpp
string    currentActiveSession;          // Current active session name
datetime  lastSessionChange;             // Time of last session change
double    sessionOpenPrice;              // Open price of current session
double    sessionHighPrice;              // High price dalam current session
double    sessionLowPrice;               // Low price dalam current session
int       sessionBarsCount;              // Number of bars dalam session

// For each session
double    asiaSessionHigh, asiaSessionLow;
double    londonSessionHigh, londonSessionLow;
double    nySessionHigh, nySessionLow;
double    sydneySessionHigh, sydneySessionLow;
```

---

### Category 6: Array Storage

**Global Arrays untuk Data Storage:**
```cpp
BacktestTrade     g_BacktestTrades[];    // Array: All trades (resizable)
int               g_TradeCount;          // Counter: Total trades

LLHHBOSData       g_LLHHBOSData[];       // Array: All patterns (LL, HH, BoS, CHoCH)
int               g_LLHHBOSCount;        // Counter: Total patterns

UnifiedEvent      g_UnifiedEvents[];     // Array: All events (unified, sorted by time)
int               g_UnifiedEventCount;   // Counter: Total events

MarketStructureRecord g_StructureRecords[]; // Array: Market structure snapshots
int               g_StructureRecordsCount;   // Counter: Total records

SessionZoneRecord g_SessionZoneRecords[];    // Array: Session zone data
int               g_SessionZoneRecordsCount; // Counter: Total sessions
```

---

## ⚙️ INPUT PARAMETERS (Updated May 2026)

### M15 Timeframe Parameters

**Pattern Detection:**
```cpp
input int   WindowSize_M15 = 25;    // Ukuran window untuk deteksi high/low
input int   ZoneLength_M15 = 100;   // Panjang zona yang digambar
input int   MovingPeriod_M15 = 200; // Periode EMA200
input int   MovingShift_M15 = 0;    // Shift EMA (default 0)
```

**Entry & Risk Parameters:**
```cpp
//--- Entry 1 Parameters
input int   DefaultSL_Buy_M15 = 3000;   // SL untuk Buy Entry 1 (pips)
input int   DefaultTP_Buy_M15 = 3000;   // TP untuk Buy Entry 1 (pips)
input int   DefaultSL_Sell_M15 = 3000;  // SL untuk Sell Entry 1 (pips)
input int   DefaultTP_Sell_M15 = 3000;  // TP untuk Sell Entry 1 (pips)

//--- Entry 2 Parameters (Aggressive)
input int   Entry2SL_Buy_M15 = 2000;    // SL untuk Buy Entry 2 (pips)
input int   Entry2TP_Buy_M15 = 2500;    // TP untuk Buy Entry 2 (pips)
input int   Entry2SL_Sell_M15 = 2000;   // SL untuk Sell Entry 2 (pips)
input int   Entry2TP_Sell_M15 = 2500;   // TP untuk Sell Entry 2 (pips)

//--- Entry 3 Parameters (Widest)
input int   Entry3SL_Buy_M15 = 3500;    // SL untuk Buy Entry 3 (pips)
input int   Entry3TP_Buy_M15 = 3000;    // TP untuk Buy Entry 3 (pips)
input int   Entry3SL_Sell_M15 = 3500;   // SL untuk Sell Entry 3 (pips)
input int   Entry3TP_Sell_M15 = 3000;   // TP untuk Sell Entry 3 (pips)
```

**Cycle & Hold Time:**
```cpp
input int   MaxEntriesPerCycle_M15 = 2; // Max entries per trend (FIX #4: 3→2)
input int   MinHoldHours_M15 = 4;       // Minimum hold time before TP (hours)
input int   MaxHoldHours_M15 = 24;      // Force close after this (hours)
```

**Magic Numbers & Lot Size:**
```cpp
input ulong MagicNumber_M15 = 12345;    // Magic number untuk EA
input double LOT_SIZE = 0.05;           // Fixed lot size per entry
```

**Backfill & Warm-up:**
```cpp
input bool  BackfillOnLoad_M15 = true;  // Scan history saat attach
input int   WarmupBars_M15 = 500;       // Jumlah bar history untuk backfill
```

---

### H1 Timeframe Parameters

**Pattern Detection:**
```cpp
input int   WindowSize_H1 = 15;    // Ukuran window untuk deteksi high/low (H1)
input int   ZoneLength_H1 = 50;    // Panjang zona yang digambar (H1)
input int   MovingPeriod_H1 = 200; // Periode EMA200 (H1)
input int   MovingShift_H1 = 0;    // Shift EMA (H1)
```

**Backfill:**
```cpp
input bool  BackfillOnLoad_H1 = true;   // Scan history saat attach
input int   WarmupBars_H1 = 500;        // Jumlah bar history untuk backfill
```

---

### Session Zone Parameters (NEW May 2026)

```cpp
input bool  EnableSessionZone = true;              // Enable/Disable tracking
input bool  ShowSessionZoneVisuals = true;         // Tampilkan zona di chart
input bool  ExportSessionZoneData = true;          // Export ke CSV
input color SessionAsiaColor = clrRed;             // Warna Asia Session
input color SessionLondonColor = clrYellow;        // Warna London Session
input color SessionNewYorkColor = clrBlue;         // Warna NY Session
input color SessionSydneyColor = clrGreen;         // Warna Sydney Session
```

---

## ⚙️ CORE FUNCTIONS

### 1. OnInit() - Initialization Function (Updated)

**Purpose:** Called once when EA attached to chart

**Workflow:**
```
1. Initialize trading object (CTrade)
   ├─ Setup CTrade for order execution
   └─ Configure magic number & settings

2. Initialize EMA200 indicators (DUAL TIMEFRAME)
   ├─ Create iMA handle untuk M15
   ├─ Create iMA handle untuk H1
   └─ Validate handle creation

3. Add indicators to chart for visualization
   ├─ ChartIndicatorAdd(EMA_M15)
   └─ ChartIndicatorAdd(EMA_H1)

4. Backfill historical data (if enabled)
   ├─ If BackfillOnLoad_M15: WarmUp_M15(500 bars)
   ├─ If BackfillOnLoad_H1: WarmUp_H1(500 bars)
   └─ DrawAllHistoricalPatterns() - Detect patterns dari history

5. Return INIT_SUCCEEDED
```

**Code (Updated):**
```cpp
int OnInit()
{
    // Initialize EMA200 handles
    handleEMA_M15 = iMA(_Symbol, PERIOD_M15, MovingPeriod_M15, MovingShift_M15, 
                        MODE_EMA, PRICE_CLOSE);
    if (handleEMA_M15 == INVALID_HANDLE)
    {
        Print("❌ Gagal membuat handle EMA200 untuk M15");
        return INIT_FAILED;
    }

    handleEMA_H1 = iMA(_Symbol, PERIOD_H1, MovingPeriod_H1, MovingShift_H1, 
                       MODE_EMA, PRICE_CLOSE);
    if (handleEMA_H1 == INVALID_HANDLE)
    {
        Print("❌ Gagal membuat handle EMA200 untuk H1");
        return INIT_FAILED;
    }

    // Add indicators to chart
    ChartIndicatorAdd(0, 0, handleEMA_M15);
    ChartIndicatorAdd(0, 0, handleEMA_H1);

    // Setup trading object
    trade.SetExpertMagicNumber(MagicNumber_M15);
    Print("✅ EMA200 handle berhasil dibuat untuk M15 & H1");

    // Backfill historical data (NEW)
    if (BackfillOnLoad_M15)
        WarmUp_M15(WarmupBars_M15);

    if (BackfillOnLoad_H1)
        WarmUp_H1(WarmupBars_H1);

    return INIT_SUCCEEDED;
}
```

**Input Parameters:**
```cpp
input bool   BackfillOnLoad_M15 = true;   // Langsung scan & gambar dari history
input int    WarmupBars_M15     = 500;    // Jumlah bar history untuk backfill
input bool   BackfillOnLoad_H1  = true;   // Langsung scan & gambar dari history
input int    WarmupBars_H1      = 500;    // Jumlah bar history untuk backfill
input bool   EnableSessionZone  = true;   // Enable Session Zone tracking
input bool   ShowSessionZoneVisuals = true; // Tampilkan zona sesi di chart
```

---

### 2. OnTick() - Main Loop (Every Tick) (Updated)

**Purpose:** Main event handler - dipanggil setiap tick (every price update)

**High-Level Workflow:**
```
REPEAT (setiap tick):
    1. Read current market data (OHLC M15 & H1)
    2. Get EMA200 values untuk both timeframes
    3. Check if new bar opened (new candle formed)
    4. IF new candle:
        ├─ DetectAndDraw_M15() - Pattern detection M15
        ├─ DetectAndDraw_H1()  - Pattern detection H1
        ├─ CheckTradeClosure_M15() - Monitor existing trades
        ├─ ApplyTrailingStop_M15() - Apply 3-stage trailing
        ├─ CheckTrailingReset_M15() - Reset flags when closed
        ├─ UpdateSessionZoneTracking() - Update session data (NEW)
        ├─ CaptureMarketStructureState_M15() - Snapshot M15
        └─ CaptureMarketStructureState_H1() - Snapshot H1
    5. Log status flags (untuk debugging)
```

**Key Operations:**
- Market data capture dari M15 & H1
- Pattern detection logic (HH, LL, CHoCH, BoS)
- Entry filter validation
- Trade execution logic
- Position management with trailing stops
- Session zone tracking (NEW)
- Market structure snapshots
- Data logging for export

---

### 3. OnDeinit() - Cleanup Function (Updated)

**Purpose:** Called when EA removed from chart (backtest ends, manual removal, etc)

**Workflow:**
```
1. Close all indicator handles
   ├─ Release handleEMA_M15
   └─ Release handleEMA_H1

2. Export all collected data
   └─ Call ExportAllData()
      ├─ ExportBacktestToCSV() (with spread/commission)
      ├─ ExportBacktestSummaryToCSV()
      ├─ ExportLLHHBOSToCSV() (merged & sorted)
      ├─ ExportMarketDataToCSV(M15, H1)
      ├─ ExportMarketStructureToCSV() (NEW)
      └─ ExportSessionZoneToCSV() (NEW)

3. Print summary to Journal
```

**Code (Updated):**
```cpp
void OnDeinit(const int reason)
{
    PrintFormat("🔄 [DEINIT] EA dihentikan. Reason: %d", reason);
    
    // Close indicator handles
    if (handleEMA_M15 != INVALID_HANDLE) 
        IndicatorRelease(handleEMA_M15);
    if (handleEMA_H1 != INVALID_HANDLE) 
        IndicatorRelease(handleEMA_H1);
    
    // Export all collected data
    ExportAllData();
    
    Print("✅ EA cleanup complete. All data exported.");
}
```

**Reason Codes:**
- 0: DEINIT_NORMAL (manual removal)
- 1: DEINIT_REMOVE (removed by user)
- 2: DEINIT_CHARTCHANGE (timeframe changed)
- 3: DEINIT_CHARTCLOSE (chart closed)
- 5: DEINIT_PARAMETERS (parameters changed)
- 6: DEINIT_ACCOUNT (account switched)

---

### 4. OnTester() - Backtest Results Handler (Updated)

**Purpose:** Called when backtest completes in Strategy Tester

**Workflow:**
```
1. Export all backtest data
   └─ Call ExportAllData()

2. Calculate final statistics
   ├─ Sum all profits
   ├─ Count total trades
   └─ Calculate metrics

3. Return total profit as optimization criterion
```

**Code (Updated):**
```cpp
double OnTester()
{
    Print("📊 [TESTER] Backtest selesai. Mengexport data...");
    
    // Export all data
    ExportAllData();
    
    // Calculate total profit
    double totalProfit = 0;
    for (int i = 0; i < g_TradeCount; i++)
        totalProfit += g_BacktestTrades[i].profit;
    
    PrintFormat("📊 [TESTER] Total Profit: %.2f | Total Trades: %d | Win Rate: %.1f%%",
                totalProfit, g_TradeCount, 
                (g_TradeCount > 0 ? (winCount / g_TradeCount * 100) : 0));
    
    // Return total profit for optimization
    return totalProfit;
}
```

**Return Value Usage:**
- Used by Strategy Tester for optimization criterion
- Positive values = profitable backtest
- Negative values = losing backtest
- Used to rank multiple EA configurations

---

## 🔍 PATTERN DETECTION LOGIC

### Pattern Types Detected

#### 1. **HH (Higher High)** 📈

**Definition:** Harga high dari candle sekarang > high dari previous significant high

**Detection Logic:**
```
IF current_high > lastAcceptedHH + threshold
   AND current_high > lastLoggedValidHH:
   
   ┌─ First time detecting this level
   └─ Store as NEW Higher High

IF this HH is at a resistance level:
   ├─ Mark as "Accepted" ✓
   ├─ Save to LLHHBOSData array
   └─ Update lastAcceptedHH value

IF this HH is rejected (price falls below it):
   ├─ Mark as "Rejected" ✗
   ├─ Log rejection
   └─ Don't count as accepted level
```

**Visual Representation:**
```
Price
  │        ╭─── HH₂ (Accepted)
  │       ╱  ╲  
  │      ╱    ╲      ╭─── HH₃ (Accepted)
  │     ╱      ╲    ╱  ╲
  │ HH₁        ╭─── HH₂' (Rejected)
  └─────────────────────────────────
      Time
```

---

#### 2. **LL (Lower Low)** 📉

**Definition:** Harga low dari candle sekarang < low dari previous significant low

**Detection Logic:**
```
IF current_low < lastAcceptedLL - threshold
   AND current_low < lastLoggedValidLL:
   
   ├─ First time detecting this level
   └─ Store as NEW Lower Low

IF this LL is at a support level:
   ├─ Mark as "Accepted" ✓
   ├─ Save to LLHHBOSData array
   └─ Update lastAcceptedLL value

IF this LL is rejected (price rises above it):
   ├─ Mark as "Rejected" ✗
   ├─ Log rejection
   └─ Don't count as accepted level
```

---

#### 3. **CHoCH (Change of Character)** 🔄

**Definition:** Market structure completely reverses (trend change)

**Bullish CHoCH:**
```
Signal: price > lastAcceptedHH + 50 pips
Meaning: Market decisively breaks above previous high
Action: Switch from bearish to bullish bias
```

**Bearish CHoCH:**
```
Signal: price < lastAcceptedLL - 50 pips
Meaning: Market decisively breaks below previous low
Action: Switch from bullish to bearish bias
```

**Logic:**
```cpp
if (!chochBullish_M15 && !isInTrendBullish_M15 &&
    (lastAcceptedHH_M15 > 0 && rates_M15[1].close > lastAcceptedHH_M15 + 50 * _Point))
{
    chochBullish_M15 = true;
    time_choch_bullish_M15 = TimeCurrent();
    postChoCH_HH_M15 = lastAcceptedHH_M15;  // Store target for BoS
    time_postChoCH_HH_M15 = TimeCurrent();
    
    SaveLLHHBOSToArray("CHoCH", "Bullish", lastAcceptedHH_M15, 
                       TimeCurrent(), "M15", "Confirmed");
    
    PrintFormat("✅ CHOCH BULLISH M15: Price %.2f broke above %.2f at %s",
                rates_M15[1].close, lastAcceptedHH_M15, 
                TimeToString(TimeCurrent()));
}
```

---

#### 4. **BoS (Break of Structure)** 💥

**Definition:** Price aggressively breaks through previous CHoCH level

**Bullish BoS:**
```
Prerequisites:
  ├─ Bullish CHoCH already active
  └─ postChoCH_HH_M15 level defined

Signal: price > postChoCH_HH_M15 + 50 pips
Meaning: Aggressive breakout continuation
Action: Entry signal untuk BUY dengan high confidence
```

**Bearish BoS:**
```
Prerequisites:
  ├─ Bearish CHoCH already active
  └─ postChoCH_LL_M15 level defined

Signal: price < postChoCH_LL_M15 - 50 pips
Meaning: Aggressive breakout continuation
Action: Entry signal untuk SELL dengan high confidence
```

**Code Logic:**
```cpp
if (postChoCH_HH_M15 > 0 && 
    (chochBullish_M15 && !isInTrendBullish_M15 && 
     rates_M15[1].close > postChoCH_HH_M15 + 50 * _Point))
{
    bosBullishConfirmedFlag_M15 = true;
    timeBoSBullish_M15 = TimeCurrent();
    
    SaveLLHHBOSToArray("BoS", "Bullish", postChoCH_HH_M15,
                       TimeCurrent(), "M15", "Confirmed");
    
    // Ready for BUY entry
    isInTrendBullish_M15 = true;
}
```

---

### Pattern Detection Flow

```
EVERY NEW M15 CANDLE:
    │
    ├─ Copy rates & detect HIGH
    │   ├─ Compare dengan lastAcceptedHH_M15
    │   ├─ IF new_high > last_high:
    │   │   └─ Potential new HH detected
    │   └─ IF new_high < last_high:
    │       └─ Could be rejection
    │
    ├─ Check HH Acceptance Logic
    │   ├─ IF valid setup & conditions met:
    │   │   ├─ lastAcceptedHH_M15 = new_high
    │   │   ├─ timeLastHH_M15 = current_time
    │   │   └─ Save to g_LLHHBOSData[]
    │   └─ ELSE mark as rejected
    │
    ├─ Check CHoCH Bullish Trigger
    │   └─ IF price > lastAcceptedHH_M15 + 50 pips:
    │       ├─ chochBullish_M15 = TRUE
    │       └─ postChoCH_HH_M15 = lastAcceptedHH_M15
    │
    ├─ Check BoS Bullish Trigger
    │   └─ IF price > postChoCH_HH_M15 + 50 pips:
    │       ├─ bosBullishConfirmedFlag_M15 = TRUE
    │       └─ READY FOR BUY ENTRY
    │
    ├─ Similar logic untuk LOW (LL, CHoCH Bearish, BoS Bearish)
    │
    └─ Draw visual elements di chart
        ├─ Horizontal lines untuk accepted levels
        ├─ Boxes untuk rejected levels
        └─ Labels untuk pattern info
```

---

## 💰 TRADING EXECUTION MODULE

### Entry Logic - Buy Trade

**Trigger Conditions:**
```cpp
if (bosBullishConfirmedFlag_M15 &&          // BoS bullish confirmed
    rates_M15[0].close > ema200_M15 &&      // Price above EMA200
    entryCountBuy_M15 < MaxEntriesPerCycle_M15 && // Not exceeded max entries
    IsH1ConfirmedBullish() &&               // H1 must be bullish too
    IsEMATrendingUp_M15() &&                // M15 EMA trending up
    !isBlackoutHour)                        // Not in low-liquidity hour
{
    // Calculate entry parameters
    if (entryCountBuy_M15 == 0) {           // First entry
        entryPrice_M15 = Ask;
        sl_M15 = Ask - 3000 * _Point;       // 3000 pips SL
        tp_M15 = Ask + 2000 * _Point;       // 2000 pips TP
    } else if (entryCountBuy_M15 == 1) {    // Second entry
        entryPrice_M15 = Ask;
        sl_M15 = Ask - 3000 * _Point;
        tp_M15 = Ask + 2500 * _Point;       // Wider TP
    } else {                                // Third entry
        entryPrice_M15 = Ask;
        sl_M15 = Ask - 3500 * _Point;
        tp_M15 = Ask + 3000 * _Point;
    }
    
    // Execute BUY
    if (trade.Buy(0.05, NULL, entryPrice_M15, sl_M15, tp_M15, "BoS Buy M15"))
    {
        // Record trade
        TradeRecord_M15 newTrade;
        newTrade.ticket = trade.ResultOrder();
        newTrade.entry_price = entryPrice_M15;
        newTrade.sl = sl_M15;
        newTrade.tp = tp_M15;
        newTrade.entry_time = TimeCurrent();
        newTrade.type = "BUY";
        
        activeBuyTrade_M15 = newTrade;
        entryCountBuy_M15++;
        lastEntryTime_M15 = TimeCurrent();
        
        SaveTradeToArray(...);  // Save untuk export later
    }
}
```

**Entry Parameters Setiap Cycle:**

| Entry | SL (Pips) | TP (Pips) | Risk:Reward | Purpose |
|-------|-----------|-----------|-------------|---------|
| Entry 1 | 3000 | 2000 | 1:0.67 | Initial entry, validate direction |
| Entry 2 | 3000 | 2500 | 1:0.83 | Aggression, increase profit target |
| Entry 3 | 3500 | 3000 | 1:0.86 | Final entry, wide TP untuk coverage |

---

### Entry Logic - Sell Trade

**Similar dengan buy, tapi dengan kondisi bearish:**

```cpp
if (bosBearishConfirmedFlag_M15 &&          // BoS bearish confirmed
    rates_M15[0].close < ema200_M15 &&      // Price below EMA200
    entryCountSell_M15 < MaxEntriesPerCycle_M15 &&
    IsH1ConfirmedBearish() &&               // H1 must be bearish too
    !IsEMATrendingUp_M15() &&               // M15 EMA trending down
    !isSellBlackoutHour)
{
    // Calculate entry (similar logic dengan buy)
    // ...
    
    // Execute SELL
    if (trade.Sell(0.05, NULL, entryPrice_M15, sl_M15, tp_M15))
    {
        // Record trade
        // ...
    }
}
```

---

### Lot Size Management

**Current Implementation:**
```cpp
// Fixed lot size per entry
double LOT_SIZE = 0.05;  // 0.05 lots = 5 micro lots

// Future: Dynamic lot sizing (connected to AI Server)
// double lot_size = CalculateLotFromConfidence(ai_confidence_score);
//   - If confidence 0.50: lot = 0.015 (small)
//   - If confidence 0.68: lot = 0.05  (medium)
//   - If confidence 0.95: lot = 0.15  (large)
```

---

## 🛑 TRAILING STOP SYSTEM (Updated May 2026)

### 3-Level Trailing Stop Logic (BUY Positions)

**Purpose:** Protect profit & minimize risk dengan dynamic stop loss progression

**3 Stages (M15 Optimized):**

#### Stage 1: Break Even (Trigger: Profit ≥ 800 pips)
```
When:    Profit reaches 800 pips (from entry)
Action:  Move SL to entry price (Break Even)
         Move TP to entry + 3000 pips
Benefit: Risk becomes 0 pips, capital fully protected
Effect:  Can't lose money, worst case break even
```

#### Stage 2: 50% Profit Lock (Trigger: Profit ≥ 2500 pips)
```
When:    Profit reaches 2500 pips (from entry)
Action:  Move SL to entry + 2000 pips (lock 2000 pips profit)
         Move TP to entry + 7500 pips
Benefit: Guaranteed minimum 2000 pips profit
Effect:  Maximum loss becomes 500 pips, minimum gain 2000 pips
```

#### Stage 3: Full Profit Trail (Trigger: Profit ≥ 4000 pips)
```
When:    Profit reaches 4000 pips (from entry)
Action:  Move SL to entry + 3000 pips (lock 3000 pips profit)
         Move TP to entry + 6000 pips
Benefit: Let winners run with tight protection
Effect:  Maximize profit potential, guaranteed 3000 pips profit
```

**Code Implementation (BUY):**
```cpp
void ApplyTrailingStop_M15()
{
    // For each BUY position
    double profitPoints = (currentBid - positionOpen) / _Point;
    
    // STAGE 1: Break Even (800 pips profit)
    if(profitPoints >= 800 && !trailingActivatedBuy_M15)
    {
        double newSL = positionOpen;  // Move SL to entry
        double newTP = positionOpen + 3000 * _Point;
        trade.PositionModify(ticket, newSL, newTP);
        trailingActivatedBuy_M15 = true;  // Mark as activated
        PrintFormat("✅ [TRAILING STEP 1] BUY: Profit %.1f pips >= 800 | SL moved to BE", profitPoints);
    }
    
    // STAGE 2: 50% Profit Lock (2500 pips profit)
    else if(profitPoints >= 2500 && trailingActivatedBuy_M15 == true)
    {
        double newSL = positionOpen + 2000 * _Point;  // Lock 2000 pips
        double newTP = positionOpen + 7500 * _Point;
        trade.PositionModify(ticket, newSL, newTP);
        trailingActivatedBuy_M15 = 2;  // Mark stage 2 active
        PrintFormat("✅ [TRAILING STEP 2] BUY: Profit %.1f pips >= 2500 | SL to +2000, TP to +7500", profitPoints);
    }
    
    // STAGE 3: Full Trail (4000 pips profit)
    else if(profitPoints >= 4000 && trailingActivatedBuy_M15 == 2)
    {
        double newSL = positionOpen + 3000 * _Point;  // Lock 3000 pips
        double newTP = positionOpen + 6000 * _Point;
        trade.PositionModify(ticket, newSL, newTP);
        trailingActivatedBuy_M15 = 3;  // Mark stage 3 active
        PrintFormat("✅ [TRAILING STEP 3] BUY: Profit %.1f pips >= 4000 | SL to +3000, TP to +6000", profitPoints);
    }
}
```

---

### 3-Level Trailing Stop Logic (SELL Positions)

**Same 3-stage progression, but inverted for SELL:**

#### Stage 1 (Profit ≥ 800 pips)
```
SL: Entry - 500 pips (gives room for small loss)
TP: Entry - (DefaultTP_Sell + 1000) pips
```

#### Stage 2 (Profit ≥ 2000 pips)
```
SL: Entry - (DefaultSL_Sell + 1500) pips
TP: Entry - (DefaultTP_Sell + 2500) pips
```

#### Stage 3 (Profit ≥ 2500 pips)
```
SL: Entry - (DefaultSL_Sell + 1000) pips
TP: Entry - (DefaultTP_Sell + 1000) pips
```

---

### Real-Time Trailing Stop Logging

**Detailed Logging Example (BUY):**
```
📊 [TRAILING BUY M15] Time=10:15:30 | Bid=2106.50 | Entry=2100.00 | SL=2100.00 | TP=2103.00 | Profit=650 poin | Status: Step 0
📊 [TRAILING BUY M15] Time=10:30:00 | Bid=2108.50 | Entry=2100.00 | SL=2100.00 | TP=2103.00 | Profit=850 poin | Status: Step 1 Aktif
✅ [TRAILING STEP 1 M15] BUY: Profit 850 poin >= 800 | SL moved to BE, TP to +3000
📊 [TRAILING BUY M15] Time=10:45:00 | Bid=2112.00 | Entry=2100.00 | SL=2100.00 | TP=2103.00 | Profit=2000 poin | Status: Step 1 Aktif
✅ [TRAILING STEP 2 M15] BUY: Profit 2500 poin >= 2500 | SL to +2000, TP to +7500
```

---

### Trailing Stop Reset Logic

**Reset Conditions:**
```cpp
void CheckTrailingReset_M15()
{
    bool hasBuyPosition_M15 = false;
    bool hasSellPosition_M15 = false;
    
    // Scan semua posisi aktif untuk EA ini
    for(int i = PositionsTotal()-1; i >= 0; i--)
    {
        if(PositionGetInteger(POSITION_MAGIC) == MagicNumber_M15 && 
           PositionGetString(POSITION_SYMBOL) == _Symbol)
        {
            if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
                hasBuyPosition_M15 = true;
            else if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL)
                hasSellPosition_M15 = true;
        }
    }
    
    // Reset BUY trailing jika posisi sudah ditutup
    if(lastHasBuyPosition_M15 && !hasBuyPosition_M15) 
    {
        trailingActivatedBuy_M15 = false;
        Print("[TRAILING RESET M15] Buy flags reset - Position closed");
    }
    
    // Reset SELL trailing jika posisi sudah ditutup
    if(lastHasSellPosition_M15 && !hasSellPosition_M15) 
    {
        trailingActivatedSell_M15 = false;
        Print("[TRAILING RESET M15] Sell flags reset - Position closed");
    }
}
```

---

### Trailing Stop Profit Visualization

```
PROFIT PROGRESSION (BUY Example):

Price   │
        │
   2112 │  Current Price → +1200 pips from entry
        │ ╭─ TP (+6000) = 2106.00
   2110 │ │
   2108 │ │
   2106 │ ├─ Stage 3 SL: Entry+3000 = 2103.00 (locked profit)
        │ │
   2104 │ │
        │ ├─ Stage 2 SL: Entry+2000 = 2102.00 (step down)
   2102 │ │
        │ │
   2100 │ ├─ Entry Price = 2100.00
        │ │
   2099 │ └─ Original SL = 2097.00
        │
        Timeline: Entry → 800 pips → 2500 pips → 4000 pips
                  Step 0   Step 1      Step 2      Step 3
        
        Result: From BE (0 loss) → Lock 2000 pips → Lock 3000 pips
                Gradual protection, unlimited upside until TP
```

---

## 📤 DATA EXPORT SYSTEM

### Export Functions Overview (Updated May 2026)

| Function | Output File | Data Type | Purpose | Status |
|----------|-------------|-----------|---------|--------|
| ExportBacktestToCSV() | Backtest_Results_*.csv | All trades + Spread/Commission | Trade details & costs | ✅ Enhanced |
| ExportBacktestSummaryToCSV() | Backtest_Summary_*.csv | Summary metrics | Overall performance | ✅ Active |
| ExportMarketDataToCSV() | MarketData_*_M15/H1.csv | OHLC + EMA | Price history | ✅ Active |
| ExportLLHHBOSToCSV() | LLHHBOSData_*.csv | Patterns (merged + sorted) | Pattern detection log | ✅ Enhanced |
| ExportMarketStructureToCSV() | MarketStructure_*.csv | Structure state | Market snapshots | ✅ New |
| ExportSessionZoneToCSV() | SessionZone_*.csv | Session metrics | Session performance | ✅ NEW |

---

### 1. Backtest_Results_XAUUSD_*.csv (Enhanced)

**Purpose:** Export detail setiap trade dengan spread cost & commission

**Columns (NEW):**
```
Ticket, Symbol, Type, EntryPrice, ExitPrice, SL, TP, Profit,
Spread_Cost, Commission, Net_Profit, Session,
EntryTime, ExitTime, LotSize, MagicNumber, Timeframe
```

**Example Content:**
```
1, XAUUSD, BUY, 2100.50, 2102.75, 2099.00, 2105.00, 225, 2.50, 0.50, 222.00, Asia,
2025-12-30 10:15:00, 2025-12-30 12:45:00, 0.05, 12345, M15

2, XAUUSD, SELL, 2102.75, 2100.25, 2103.50, 2097.00, 250, 2.50, 0.50, 247.00, London,
2025-12-30 13:00:00, 2025-12-30 14:30:00, 0.05, 12345, M15
```

**Key Metrics (NEW):**
- **Spread Cost:** Estimated bid-ask spread impact (entry + exit)
  - Estimated ~2.5 pips per transaction untuk XAUUSD
  - Cost = (spread_pips × volume × _Point) × 100
- **Commission:** Broker commission per deal
  - Extracted from HistoryDealGetDouble(DEAL_COMMISSION)
- **Net_Profit:** Actual profit after costs
  - Net_Profit = Profit - Spread_Cost - Commission

**Used By:**
- AI model training (realistic P&L calculation)
- Profit/loss analysis (with transaction costs)
- Strategy validation (true profitability)
- Performance analysis (net returns)

**Implementation:**
```cpp
void SaveTradeToArray(ulong ticket, string symbol, string type, 
                      double entry_price, double exit_price, 
                      double sl, double tp, double profit,
                      datetime entry_time, datetime exit_time,
                      double lot_size, ulong magic, string tf,
                      double spread_cost = 0, double commission = 0, string session = "")
{
    // Calculate spread cost: ~2.5 pips per transaction
    double spreadCost = 0;
    double commission = 0;
    
    // Extract from history deals
    HistorySelect(0, TimeCurrent());
    int totalDeals = HistoryDealsTotal();
    for(int j = totalDeals-1; j >= 0; j--)
    {
        ulong dealTicket = HistoryDealGetTicket(j);
        if(HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID) == ticket)
        {
            // Accumulate spread cost
            double spreadPips = 2.5;  // XAUUSD typical spread
            spreadCost += spreadPips * HistoryDealGetDouble(dealTicket, DEAL_VOLUME) * _Point * 100;
            
            // Accumulate commission
            commission += MathAbs(HistoryDealGetDouble(dealTicket, DEAL_COMMISSION));
        }
    }
    
    // Save trade with all costs
    SaveTradeToArray(..., spreadCost, commission, session);
}
```

---

### 2. Backtest_Summary_XAUUSD_*.csv (Same)

**Purpose:** Overall backtest metrics (1 row per backtest)

**Columns:**
```
Total_Trades, Winning_Trades, Losing_Trades, Win_Rate, 
Total_Profit, Max_Drawdown, Profit_Factor, Start_Date, 
End_Date, Timeframe, Instrument
```

**Example Content:**
```
100, 62, 38, 62%, 5000, 8%, 2.5, 2025-12-01, 2025-12-30, M15, XAUUSD
```

---

### 3. LLHHBOSData_XAUUSD_*.csv (Enhanced - Merged & Sorted)

**Purpose:** Pattern detection log dengan unified events sorted by time

**New Features:**
- Merges CHoCH/BoS events dengan HH/LL Update events
- Sorts ALL events chronologically (bubble sort)
- Shows complete market structure evolution

**Columns:**
```
Type, Direction/Action, Price, Time, Timeframe, Status,
PreviousPrice, PreviousTime
```

**Example Content:**
```
HH, Update, 2105.50, 2025-12-30 10:00:00, H1, Accepted, N/A, N/A
LL, Update, 2098.75, 2025-12-30 11:30:00, M15, Accepted, N/A, N/A
CHoCH, Bullish, 2106.00, 2025-12-30 13:00:00, H1, Confirmed, 2105.00, 2025-12-30 12:00:00
BoS, Bullish, 2103.25, 2025-12-30 14:00:00, M15, Confirmed, 2102.00, 2025-12-30 13:45:00
HH, Update, 2106.50, 2025-12-30 15:30:00, M15, Accepted, 2105.50, 2025-12-30 10:00:00
```

**Implementation:**
```cpp
void ExportLLHHBOSToCSV()
{
    // Step 1: Merge CHoCH/BoS + HH/LL Updates
    // Skip: LL/HH with "Reference" direction
    
    // Step 2: Sort by time (Bubble Sort)
    for (int i = 0; i < g_UnifiedEventCount - 1; i++)
    {
        for (int j = i + 1; j < g_UnifiedEventCount; j++)
        {
            if (g_UnifiedEvents[i].time > g_UnifiedEvents[j].time)
            {
                // Swap events
                UnifiedEvent temp = g_UnifiedEvents[i];
                g_UnifiedEvents[i] = g_UnifiedEvents[j];
                g_UnifiedEvents[j] = temp;
            }
        }
    }
    
    // Step 3: Write sorted events to CSV
}
```

---

### 4. MarketStructure_XAUUSD_*.csv (NEW Export)

**Purpose:** Comprehensive market structure snapshots per candle

**Columns:**
```
Time, Timeframe, LastAcceptedHH, LastAcceptedLL, EMA200,
CHoCH_Bullish, CHoCH_Bullish_Price, CHoCH_Bearish, CHoCH_Bearish_Price,
BoS_Bullish, BoS_Bullish_Price, BoS_Bearish, BoS_Bearish_Price
```

**Example Content:**
```
2025-12-30 10:00:00, M15, 2105.50, 2098.75, 2102.00, NO, N/A, NO, N/A, NO, N/A, NO, N/A
2025-12-30 10:15:00, M15, 2105.50, 2098.75, 2102.10, YES, 2106.00, NO, N/A, NO, N/A, NO, N/A
2025-12-30 10:30:00, M15, 2105.50, 2098.75, 2102.20, YES, 2106.00, NO, N/A, YES, 2106.50, NO, N/A
```

**Used By:**
- Detailed market structure analysis
- Pattern detection validation
- State transition tracking
- AI feature engineering

---

### 5. SessionZone_XAUUSD_*.csv (NEW - May 2026)

**Purpose:** Track performance per trading session

**Columns:**
```
Time, Session, IsActive, OpenPrice, HighPrice, LowPrice, 
ClosePrice, BarsCount, SessionRangePoints
```

**Example Content:**
```
2025-12-30 22:00:00, Sydney, YES, 2099.50, 2100.25, 2099.00, 2100.00, 4, 125
2025-12-30 08:00:00, London, YES, 2100.50, 2102.00, 2100.00, 2101.75, 8, 200
2025-12-30 13:00:00, London_NewYork_Overlap, YES, 2101.75, 2103.50, 2101.00, 2102.50, 6, 250
2025-12-30 17:00:00, NewYork, YES, 2102.50, 2105.00, 2102.00, 2104.75, 10, 300
```

**Analysis Possible:**
- Which session most profitable
- Session-specific volatility (Range in points)
- Liquidity per session (bar activity)
- Best entry times identification

---

### Export Workflow (OnDeinit)

```cpp
void OnDeinit(const int reason)
{
    PrintFormat("🔄 [DEINIT] EA dihentikan. Reason: %d", reason);
    
    // Export semua data saat EA dihapus/backtest selesai
    ExportAllData();
}

void ExportAllData()
{
    Print("📦 [EXPORT] Memulai export semua data...");
    
    // 1. Export backtest results (dengan spread/commission)
    ExportBacktestToCSV();
    
    // 2. Export backtest summary
    ExportBacktestSummaryToCSV();
    
    // 3. Export LL, HH, BOS, CHoCH data (merged & sorted)
    ExportLLHHBOSToCSV();
    
    // 4. Export Market Structure Records
    ExportMarketStructureToCSV();
    
    // 5. Export Session Zone data (NEW)
    ExportSessionZoneToCSV();
    
    // 6. Export market data M15 & H1
    ExportMarketDataToCSV(PERIOD_M15, 50000000);
    ExportMarketDataToCSV(PERIOD_H1, 20000000);
    
    Print("✅ [EXPORT] Semua data berhasil di-export ke folder MQL5/Files/");
}
```

---

## 🌍 SESSION ZONE TRACKING

### Input Parameters untuk Session Zone Tracking

```cpp
input bool   EnableSessionZone = true;           // Enable/Disable Session Zone tracking
input bool   ShowSessionZoneVisuals = true;      // Tampilkan zona sesi di chart
input bool   ExportSessionZoneData = true;       // Export data session zone ke CSV
input color  SessionAsiaColor = clrRed;          // Warna Asia Session
input color  SessionLondonColor = clrYellow;     // Warna London Session
input color  SessionNewYorkColor = clrBlue;      // Warna New York Session
input color  SessionSydneyColor = clrGreen;      // Warna Sydney Session
```

### 4 Trading Sessions Defined (GMT)

```
Sydney Session (22:00 - 06:00 UTC)
├─ Time Zone: UTC+10:00 (AEDT)
├─ Duration: 8 hours
├─ Characteristics: Low volatility, Asian traders starting
├─ Typical Range: 30-60 pips
└─ Best For: Range trading, support/resistance

Asia Session (22:00 - 07:00 UTC)  
├─ Time Zone: UTC+8:00 (SGT/HKT)
├─ Duration: 9 hours
├─ Characteristics: Building liquidity, range-bound
├─ Typical Range: 50-80 pips
└─ Best For: Breakout preparation

London Session (08:00 - 16:00 UTC)
├─ Time Zone: UTC+0:00 (GMT)
├─ Duration: 8 hours
├─ Characteristics: HIGH LIQUIDITY, trending moves
├─ Typical Range: 100-150 pips
└─ Best For: Trend trading, high probability setups

NewYork Session (13:00 - 22:00 UTC)
├─ Time Zone: UTC-5:00 (EST)
├─ Duration: 9 hours
├─ Characteristics: Highest volatility, major moves, overlap London
├─ Typical Range: 80-120 pips
└─ Best For: Aggressive trading, news driven

London_NewYork_Overlap (13:00 - 16:00 UTC)
├─ Time Zone: Overlap period
├─ Duration: 3 hours
├─ Characteristics: PEAK LIQUIDITY, maximum volatility
├─ Typical Range: 150-200 pips
└─ Best For: Breakout, trend continuation
```

### Session Detection Logic (Updated)

```cpp
string GetCurrentSession()
{
    // Ambil waktu GMT
    datetime currentTime = TimeCurrent();
    MqlDateTime dtStruct;
    TimeToStruct(currentTime, dtStruct);
    
    int hour = dtStruct.hour;
    int dayOfWeek = dtStruct.day_of_week;
    
    // Jika weekend (Sabtu=6/Minggu=0), tidak ada sesi aktif
    if (dayOfWeek == 0 || dayOfWeek == 6)
        return "Weekend";
    
    // Session times (GMT)
    if ((hour >= 22) || (hour < 7))
        return "Asia";
    else if ((hour >= 8) && (hour < 13))
        return "London";
    else if ((hour >= 13) && (hour < 17))
        return "London_NewYork_Overlap";
    else if ((hour >= 17) && (hour < 22))
        return "NewYork";
    else
        return "NoSession";
}
```

### Session Zone Record Structure (Updated)

```cpp
struct SessionZoneRecord
{
    datetime  time;                 // Waktu candle
    string    sessionName;          // Nama sesi
    bool      isSessionActive;      // Apakah sesi aktif pada waktu ini
    double    sessionOpenPrice;     // Harga open saat sesi dimulai
    double    sessionHighPrice;     // Harga high dalam sesi
    double    sessionLowPrice;      // Harga low dalam sesi
    double    sessionClosePrice;    // Harga close dalam sesi
    int       sessionBarsCount;     // Jumlah bar dalam sesi
    // BARU: Range calculation
    double    sessionRangePoints;   // Range dalam points (High-Low) / _Point
};
```

### Session Zone Tracking Features (Real-Time)

**Per Session, EA Tracks:**
- Opening price (saat session start)
- Session high (highest price dalam session)
- Session low (lowest price dalam session)
- Session close (closing price saat session end)
- Bar count (jumlah candles dalam session)
- Range in points (high - low / _Point)

**Session Change Detection:**
```cpp
void UpdateSessionZoneTracking()
{
    // Deteksi perubahan sesi otomatis
    if (session != currentActiveSession)
    {
        // Simpan record sesi yang telah selesai
        SaveSessionZoneRecord(lastSessionChangeTime, currentActiveSession, false,
                             sessionOpenPrice, sessionHighPrice, sessionLowPrice, 
                             currentClose, sessionBarsCount);
        
        // Set sesi baru dengan harga entry
        currentActiveSession = session;
        sessionOpenPrice = currentClose;
        sessionHighPrice = currentClose;
        sessionLowPrice = currentClose;
        sessionBarsCount = 1;
    }
    else
    {
        // Update high/low dalam sesi yang sama
        if (currentClose > sessionHighPrice)
            sessionHighPrice = currentClose;
        if (currentClose < sessionLowPrice)
            sessionLowPrice = currentClose;
        
        sessionBarsCount++;
    }
}
```

### Session Zone Visuals (Chart Display)

```cpp
void DrawSessionRangeShadows()
{
    // Jika tidak diaktifkan, skip
    if (!ShowSessionZoneVisuals) return;
    
    // Gambar shadow untuk setiap session dengan:
    // - Transparent 80% background color
    // - Session name label di tengah
    // - Behind candles untuk visibility
    
    SessionTime sessions[] = {
        {"Asia", 22, 7, SessionAsiaColor},
        {"London", 8, 16, SessionLondonColor},
        {"NewYork", 17, 22, SessionNewYorkColor},
        {"Sydney", 21, 6, SessionSydneyColor}
    };
    
    // Draw rectangle shadow untuk setiap session
    // dengan warna transparent 80% (30% opacity)
}

void DisplaySessionInfo()
{
    // Tampilkan label session info real-time:
    // Current Session: [Name]
    // Open: [Price]
    // High: [Price]
    // Low: [Price]
    // Bars: [Count]
}
```

### Session Zone Export to CSV

**SessionZone_XAUUSD_*.csv Columns:**
```
Time, Session, IsActive, OpenPrice, HighPrice, LowPrice, 
ClosePrice, BarsCount, SessionRangePoints
```

**Example:**
```
2025-12-30 22:00:00, Sydney, YES, 2099.50, 2100.25, 2099.00, 2100.00, 4, 125
2025-12-30 08:00:00, London, YES, 2100.50, 2102.00, 2100.00, 2101.75, 8, 200
2025-12-30 13:00:00, London_NewYork_Overlap, YES, 2101.75, 2103.50, 2101.00, 2102.50, 6, 250
```

**Usage Analysis:**
- Identify which session is most profitable
- Session-specific volatility tracking
- Liquidity per session measurement
- Optimal trading times identification

---

## ✅ ENTRY FILTERS & CONDITIONS (Updated May 2026)

### Filter 1: H1 Confirmation (Dual Timeframe Alignment)

**Purpose:** Ensure M15 trades align dengan H1 trend (higher timeframe confirmation)

**For BUY Entry:**
```cpp
bool IsH1ConfirmedBullish()
{
    double emaH1 = GetEMA200_H1();  // Get current H1 EMA200
    
    MqlRates h1Rate[];
    ArraySetAsSeries(h1Rate, true);
    if (CopyRates(_Symbol, PERIOD_H1, 0, 1, h1Rate) < 1) 
        return false;
    
    // Condition: H1 Close > H1 EMA200
    bool bullishConfirmed = (emaH1 > 0 && h1Rate[0].close > emaH1);
    
    if (!bullishConfirmed)
        PrintFormat("❌ [H1 FILTER REJECT] BUY Entry rejected: "
                    "H1 Close (%.5f) NOT above H1 EMA200 (%.5f)", 
                    h1Rate[0].close, emaH1);
    
    return bullishConfirmed;
}
```

**For SELL Entry:**
```cpp
bool IsH1ConfirmedBearish()
{
    double emaH1 = GetEMA200_H1();
    MqlRates h1Rate[];
    ArraySetAsSeries(h1Rate, true);
    if (CopyRates(_Symbol, PERIOD_H1, 0, 1, h1Rate) < 1) 
        return false;
    
    // Condition: H1 Close < H1 EMA200
    bool bearishConfirmed = (emaH1 > 0 && h1Rate[0].close < emaH1);
    return bearishConfirmed;
}
```

**Example Practical:**
```
Saat BoS Bullish M15 Terdeteksi (price = 2106.00):

✅ SCENARIO LOLOS:
   H1 Close: 2105.80
   H1 EMA200: 2104.50
   Check: 2105.80 > 2104.50 ? YES ✓
   Result: PASS → Boleh Entry BUY

❌ SCENARIO DITOLAK:
   H1 Close: 2100.50
   H1 EMA200: 2103.00
   Check: 2100.50 > 2103.00 ? NO ✗
   Result: FAIL → Skip Entry
   Reason: Walau M15 bullish, H1 bearish = high risk
```

---

### Filter 2: M15 EMA Trending Direction (Momentum Confirmation)

**Purpose:** Confirm M15 trend dengan EMA200 slope (only accept if trending same direction)

**For BUY Entry:**
```cpp
bool IsEMATrendingUp_M15()
{
    double emaCurrent = 0, emaPrevious = 0;
    double emaBuffer[];
    
    // Get current M15 bar EMA
    if (CopyBuffer(iMA(_Symbol, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE), 
                   0, 0, 1, emaBuffer) > 0)
        emaCurrent = emaBuffer[0];
    
    // Get previous M15 bar EMA
    if (CopyBuffer(iMA(_Symbol, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE), 
                   0, 1, 1, emaBuffer) > 0)
        emaPrevious = emaBuffer[0];
    
    bool trendingUp = (emaCurrent > emaPrevious);
    PrintFormat("📈 [EMA SLOPE M15] Current: %.5f vs Previous: %.5f → Trending: %s", 
                emaCurrent, emaPrevious, trendingUp ? "UP" : "DOWN");
    
    return trendingUp;
}
```

**Logic:**
```
Current Candle EMA > Previous Candle EMA? 
    YES → Trending UP → ✓ PASS for BUY
    NO  → Trending DOWN → ✗ FAIL (divergence warning)
```

**Example Practical:**
```
Saat BoS Bullish M15 Terdeteksi:

✅ SCENARIO LOLOS:
   Current EMA: 2102.50
   Previous EMA: 2102.30
   Check: 2102.50 > 2102.30 ? YES ✓
   Result: PASS → EMA trending up, momentum bullish

❌ SCENARIO DITOLAK:
   Current EMA: 2102.20
   Previous EMA: 2102.50
   Check: 2102.20 > 2102.50 ? NO ✗
   Result: FAIL → EMA falling (bearish divergence)
   Why: Harga break above tapi EMA sudah mulai turun = warning sign
```

---

### Filter 3: Blackout Hours (Liquidity Protection)

**Purpose:** Avoid trading saat liquidity rendah & spread lebar

**Blackout Schedule (GMT):**
```
17:00-18:00 UTC → Session Transition (Low Volatility)
    - Between London close dan NY open
    - Reduced volume, wider spreads
    - Action: Skip BUY/SELL entries
    
21:00-22:00 UTC → Before NY Session (Reduced Volume)
    - Sell-specific blackout (lower volatility before NY explosion)
    - Action: Skip SELL entries specifically
```

**Code Implementation:**
```cpp
// Global variables
static bool isBlackoutHour = false;
static bool isSellBlackoutHour = false;

// In OnTick() or CheckNewBar():
int current_hour = (TimeCurrent() % 86400) / 3600;

// Buy Blackout: 17:00 - 18:00 UTC (hour == 17)
isBlackoutHour = (current_hour == 17);

// Sell Blackout: 21:00 - 22:00 UTC (hour == 21)
isSellBlackoutHour = (current_hour == 21);

// Use dalam entry filter
if (bosBullishConfirmedFlag_M15 && !isBlackoutHour)
{
    // Can execute BUY entry
}

if (bosBearishConfirmedFlag_M15 && !isSellBlackoutHour)
{
    // Can execute SELL entry
}
```

**Example Scenario:**
```
Current Time: 16:30 UTC (Not blackout)
Status: ✓ PASS → London session strong, good liquidity → Can enter BUY/SELL

Current Time: 17:30 UTC (Blackout hour)
Status: ✗ FAIL → Session transition, low volume → Skip entry
Risk: Entry at 17:35 UTC, spread normal
      Then 17:36 UTC, NY open delayed, spreads widen 5+ pips
      Position immediately in loss due to slippage

Current Time: 21:30 UTC (Sell blackout)
Status: BUY: ✓ PASS (can enter)
       SELL: ✗ FAIL (skip for SELL specifically)
```

---

### Filter 4: Max Entries Per Cycle (Batch Control)

**Purpose:** Don't over-leverage with too many entries in one trend cycle

**Rule:**
```cpp
input int MaxEntriesPerCycle_M15 = 2;  // Changed from 3 to 2 (FIX #4)

// Check during entry
if (entryCountBuy_M15 < MaxEntriesPerCycle_M15)
{
    // Can execute entry
}
else
{
    // Skip entry - already hit max
    PrintFormat("⚠️ [ENTRY LIMIT] Buy entries: %d >= Max %d | Skip this entry",
                entryCountBuy_M15, MaxEntriesPerCycle_M15);
}
```

**Entry Sequence:**
```
BoS Signal 1 → entryCountBuy = 1 → ✓ ACCEPTED (Entry 1)
15 min later: BoS continues → entryCountBuy = 1 → entryCountBuy = 2 → ✓ ACCEPTED (Entry 2)
30 min later: BoS continues → entryCountBuy = 2 >= 2 → ✗ REJECTED (cycle overextended)
```

**Rationale:**
- Entry 1: Validate direction (test water)
- Entry 2: Confirm trend, aggression (increase position)
- Entry 3+: Typically reversal coming, risk increases
- Limit to 2 entries = safer, proven strategy

---

### Filter 5: Minimum Entry Spacing (Cadence Control)

**Purpose:** Ensure sufficient time between entries for first trade to move

**Rule:**
```cpp
// Check time since last entry
int timeSinceLastEntry_minutes = (TimeCurrent() - lastEntryTime_M15) / 60;
int MINIMUM_SPACING_MINUTES = 45;  // 3 candles × 15 min

if (timeSinceLastEntry_minutes >= MINIMUM_SPACING_MINUTES)
{
    // Enough time passed, can enter again
}
else
{
    PrintFormat("⏳ [ENTRY SPACING] Only %d min since last entry. Need %d min",
                timeSinceLastEntry_minutes, MINIMUM_SPACING_MINUTES);
}
```

**Entry Timeline Example:**
```
10:00 UTC - Entry 1 Executed ✓
           lastEntryTime_M15 = 10:00

10:30 UTC - Entry 2 Signal
           timeSinceLastEntry = 30 min
           30 < 45 min? YES → ✗ REJECTED (too soon)

10:45 UTC - Entry 2 Signal again
           timeSinceLastEntry = 45 min
           45 >= 45 min? YES → ✓ ACCEPTED (spacing OK)

11:30 UTC - Entry 3 Signal (if MaxEntries > 2)
           timeSinceLastEntry = 90 min
           90 >= 45 min? YES → ✓ ACCEPTED (spacing OK)
```

---

### Entry Filter Summary Table

| Filter | Condition | For BUY | For SELL | Purpose |
|--------|-----------|---------|----------|---------|
| H1 Confirmation | H1 Close vs EMA200 | Close > EMA200 | Close < EMA200 | Align to higher timeframe |
| EMA Trending | M15 EMA slope | Current > Previous | Current < Previous | Momentum confirmation |
| Blackout Hours | Current hour GMT | hour ≠ 17 | hour ≠ 21 | Avoid low liquidity |
| Max Entries | Entry count | < 2 | < 2 | Prevent over-leverage |
| Entry Spacing | Time since last entry | ≥ 45 min | ≥ 45 min | Room for first trade |

---

### Complete Entry Check Example

```cpp
// ALL FILTERS MUST PASS for entry
if (bosBullishConfirmedFlag_M15 &&           // Pattern: BoS detected
    IsH1ConfirmedBullish() &&                // Filter 1: ✓ H1 bullish
    IsEMATrendingUp_M15() &&                 // Filter 2: ✓ M15 EMA trending up
    !isBlackoutHour &&                       // Filter 3: ✓ Not blackout hour
    entryCountBuy_M15 < MaxEntriesPerCycle_M15 && // Filter 4: ✓ Within max entries
    (TimeCurrent() - lastEntryTime_M15) >= 45*60) // Filter 5: ✓ 45 min spacing
{
    // ✅ ALL FILTERS PASSED → EXECUTE BUY ENTRY
    trade.Buy(0.05, NULL, Ask, SL, TP, "BoS Buy M15");
    entryCountBuy_M15++;
    lastEntryTime_M15 = TimeCurrent();
}
else
{
    // ✗ REJECTED - At least one filter failed
    // Find which filter failed for debugging
}
```

---

## 🔄️ END-TO-END WORKFLOW

### Complete Trading Cycle (Start to Finish)

```
╔════════════════════════════════════════════════════════════════╗
║  PHASE 1: INITIALIZATION (OnInit)                             ║
╚════════════════════════════════════════════════════════════════╝

1. EA attached to XAUUSD chart (M15 or H1 timeframe)
   │
   ├─ Initialize CTrade object
   │
   ├─ Create EMA200 indicator handles
   │  ├─ handleEMA_M15 = iMA(M15, 200, EMA)
   │  └─ handleEMA_H1 = iMA(H1, 200, EMA)
   │
   ├─ Backfill historical data (if enabled)
   │  ├─ WarmUp_M15() - Load last 1000 M15 bars
   │  ├─ WarmUp_H1() - Load last 1000 H1 bars
   │  └─ DrawAllHistoricalPatterns() - Detect patterns dari history
   │
   └─ Ready for live trading

┌──────────────────────────────────────────────────────────────┐
│ PHASE 2: MARKET DATA CAPTURE (OnTick - Every Tick)          │
└──────────────────────────────────────────────────────────────┘

2. Every tick (price update):
   
   ├─ Copy M15 rates: Copy last 2 M15 candles
   │  ├─ rates_M15[0] = current candle
   │  └─ rates_M15[1] = previous candle (already closed)
   │
   ├─ Copy H1 rates: Copy last H1 candle
   │
   ├─ Get EMA200 values:
   │  ├─ ema200_M15 = iMA buffer current value
   │  └─ ema200_H1 = iMA buffer current value
   │
   ├─ Check if NEW M15 candle formed
   │  └─ IF rates_M15[1].time > lastProcessedTime_M15:
   │      └─ NEW CANDLE DETECTED
   │
   └─ IF new candle → Proceed to Phase 3

┌──────────────────────────────────────────────────────────────┐
│ PHASE 3: PATTERN DETECTION (Per New Candle)                 │
└──────────────────────────────────────────────────────────────┘

3. For each new M15 candle:
   
   ├─ DETECT HIGH (HH - Higher High)
   │  ├─ IF rates_M15[1].high > lastAcceptedHH_M15:
   │  │  ├─ Could be new HH
   │  │  ├─ Validate against rejection logic
   │  │  └─ IF valid → Accept as new HH
   │  │      ├─ lastAcceptedHH_M15 = new price
   │  │      ├─ SaveLLHHBOSToArray("HH", "Bullish", ...)
   │  │      └─ Draw horizontal line pada chart
   │  └─ ELSE → Potential rejection
   │
   ├─ DETECT LOW (LL - Lower Low)
   │  └─ Similar logic dengan HH detection
   │
   ├─ CHECK CHoCH BULLISH TRIGGER
   │  ├─ IF !chochBullish_M15 && !isInTrendBullish_M15:
   │  │  ├─ IF price > lastAcceptedHH_M15 + 50 pips:
   │  │  │  ├─ chochBullish_M15 = TRUE
   │  │  │  ├─ postChoCH_HH_M15 = lastAcceptedHH_M15 (store target)
   │  │  │  ├─ SaveLLHHBOSToArray("CHoCH", "Bullish", ...)
   │  │  │  └─ Log: "✅ CHoCH BULLISH DETECTED"
   │  │  └─ ELSE → Wait for breakout
   │  └─ Next: wait for BoS signal
   │
   ├─ CHECK CHoCH BEARISH TRIGGER
   │  └─ Similar logic (inverted conditions)
   │
   ├─ CHECK BoS BULLISH TRIGGER
   │  ├─ IF chochBullish_M15 && !isInTrendBullish_M15:
   │  │  ├─ IF price > postChoCH_HH_M15 + 50 pips:
   │  │  │  ├─ bosBullishConfirmedFlag_M15 = TRUE
   │  │  │  ├─ isInTrendBullish_M15 = TRUE
   │  │  │  ├─ SaveLLHHBOSToArray("BoS", "Bullish", ...)
   │  │  │  └─ Log: "💥 BoS BULLISH - READY FOR ENTRY"
   │  │  └─ ELSE → Keep waiting
   │  └─ Next: proceed to Phase 4 (Entry Filters)
   │
   ├─ CHECK BoS BEARISH TRIGGER
   │  └─ Similar logic (inverted conditions)
   │
   ├─ CAPTURE MARKET STRUCTURE SNAPSHOT
   │  ├─ CaptureMarketStructureState_M15():
   │  │  ├─ time, lastAcceptedHH, lastAcceptedLL
   │  │  ├─ chochBullish status, bosBullish status
   │  │  └─ ema200 value, all state flags
   │  └─ Save to g_StructureRecords[] array
   │
   └─ UPDATE SESSION ZONE TRACKING
      ├─ Detect current session
      ├─ Update session high/low/close
      └─ Save to g_SessionZoneRecords[] array

┌──────────────────────────────────────────────────────────────┐
│ PHASE 4: ENTRY FILTERS & SIGNAL VALIDATION                  │
└──────────────────────────────────────────────────────────────┘

4. When BoS Bullish detected:
   
   ├─ Check Filter 1: H1 Confirmation
   │  └─ IsH1ConfirmedBullish()?
   │     ├─ Get H1 close price
   │     ├─ Compare dengan H1 EMA200
   │     └─ IF close > EMA200 → PASS ✓
   │        ELSE → FAIL ✗ → Skip entry
   │
   ├─ Check Filter 2: M15 EMA Trending Up
   │  └─ IsEMATrendingUp_M15()?
   │     ├─ Get current M15 EMA
   │     ├─ Get previous M15 EMA (1 bar ago)
   │     └─ IF current > previous → PASS ✓
   │        ELSE → FAIL ✗ → Skip entry
   │
   ├─ Check Filter 3: Not Blackout Hour
   │  └─ !isBlackoutHour?
   │     ├─ IF current hour in [17, 18] → FAIL ✗
   │     ELSE → PASS ✓
   │
   ├─ Check Filter 4: Max Entries Not Exceeded
   │  └─ entryCountBuy_M15 < 3?
   │     ├─ IF already 3 entries → FAIL ✗
   │     ELSE → PASS ✓
   │
   ├─ Check Filter 5: Minimum Entry Spacing
   │  └─ TimeSinceLastEntry > 3 candles?
   │     ├─ IF too soon → FAIL ✗
   │     ELSE → PASS ✓
   │
   └─ IF ALL FILTERS PASS → Proceed to Phase 5

┌──────────────────────────────────────────────────────────────┐
│ PHASE 5: TRADE EXECUTION (BUY Entry)                        │
└──────────────────────────────────────────────────────────────┘

5. Execute BUY Trade:
   
   ├─ Calculate Entry Parameters (depends on entry number)
   │  │
   │  ├─ IF entryCountBuy_M15 == 0 (First entry):
   │  │  ├─ entryPrice = Ask
   │  │  ├─ sl = Ask - 3000 pips
   │  │  ├─ tp = Ask + 2000 pips
   │  │  └─ lot = 0.05
   │  │
   │  ├─ IF entryCountBuy_M15 == 1 (Second entry):
   │  │  ├─ entryPrice = Ask
   │  │  ├─ sl = Ask - 3000 pips
   │  │  ├─ tp = Ask + 2500 pips (wider TP)
   │  │  └─ lot = 0.05
   │  │
   │  ├─ IF entryCountBuy_M15 == 2 (Third entry):
   │  │  ├─ entryPrice = Ask
   │  │  ├─ sl = Ask - 3500 pips
   │  │  ├─ tp = Ask + 3000 pips (widest TP)
   │  │  └─ lot = 0.05
   │  │
   │  └─ Total risk per trade: 3000-3500 pips max
   │     Total reward: 2000-3000 pips target
   │     Risk:Reward Ratio: 1:0.67 to 1:0.86 (protection focused)
   │
   ├─ Execute ORDER
   │  ├─ trade.Buy(0.05, NULL, entryPrice, sl, tp, "BoS Buy M15")
   │  │
   │  └─ IF order successful:
   │     ├─ Get ticket number (trade.ResultOrder())
   │     ├─ Record in TradeRecord_M15:
   │     │  ├─ ticket, entry_price, sl, tp
   │     │  ├─ entry_time = TimeCurrent()
   │     │  └─ type = "BUY"
   │     │
   │     ├─ Set flags:
   │     │  ├─ activeBuyTrade_M15 = newTrade
   │     │  ├─ entryCountBuy_M15++
   │     │  ├─ hasBuyPosition_M15 = true
   │     │  └─ lastEntryTime_M15 = TimeCurrent()
   │     │
   │     ├─ Save to global array:
   │     │  ├─ SaveTradeToArray(...all trade details...)
   │     │  └─ g_TradeCount++
   │     │
   │     ├─ Log success:
   │     │  └─ Print("✅ BUY Entry #X: Price %.2f | SL %.2f | TP %.2f")
   │     │
   │     └─ Ready for Phase 6 (Position Management)
   │
   └─ IF order failed:
      ├─ Log error reason
      ├─ Trade cancelled
      └─ Wait for next signal

┌──────────────────────────────────────────────────────────────┐
│ PHASE 6: POSITION MANAGEMENT (While Trade Open)              │
└──────────────────────────────────────────────────────────────┘

6. Monitor active BUY position:
   
   ├─ APPLY TRAILING STOP (3 Stages):
   │  │
   │  ├─ Stage 1: Break Even
   │  │  ├─ Profit > 50% of TP distance?
   │  │  ├─ YES → Move SL to entry price (Break Even)
   │  │  │   ├─ Risk becomes 0 pips
   │  │  │   └─ Capital protected
   │  │  └─ NO → Keep original SL
   │  │
   │  ├─ Stage 2: 50% Profit Lock
   │  │  ├─ Profit > 75% of TP distance?
   │  │  ├─ YES → Move SL to 50% profit level
   │  │  │   ├─ Lock in half the profit
   │  │  │   └─ Continue hoping for TP
   │  │  └─ NO → Keep current SL
   │  │
   │  ├─ Stage 3: Trailing Stop
   │  │  ├─ Profit >= 95% of TP distance?
   │  │  ├─ YES → Tight trailing SL (100 pips behind price)
   │  │  │   ├─ Only move SL upward (never down)
   │  │  │   ├─ "Let winners run"
   │  │  │   └─ Maximize profit potential
   │  │  └─ NO → Keep current SL
   │  │
   │  └─ Apply via trade.PositionModify()
   │
   ├─ CHECK HOLD TIME CONSTRAINTS:
   │  │
   │  ├─ Minimum Hold Time:
   │  │  ├─ IsTradeHoldingMinimumTime(trade)?
   │  │  ├─ Must hold at least 2 hours
   │  │  └─ Prevents TP/SL too quickly
   │  │
   │  └─ Maximum Hold Time:
   │     ├─ ShouldForceCloseTrade(trade)?
   │     ├─ IF > 24 hours → Force close
   │     ├─ Prevents overnight risk
   │     └─ trade.PositionClose(ticket)
   │
   ├─ CHECK TRADE CLOSURE CONDITIONS:
   │  │
   │  ├─ IF TP hit:
   │  │  ├─ Position automatically closes (MT5)
   │  │  ├─ Exit price = TP price
   │  │  ├─ Profit = TP - Entry = max profit
   │  │  └─ Go to Phase 7 (Logging)
   │  │
   │  ├─ IF SL hit:
   │  │  ├─ Position automatically closes
   │  │  ├─ Exit price = SL price
   │  │  ├─ Loss = Entry - SL = max loss
   │  │  └─ Go to Phase 7 (Logging)
   │  │
   │  └─ IF Force Close:
   │     ├─ trade.PositionClose(ticket)
   │     ├─ Exit price = current price
   │     ├─ Profit/Loss = current price - entry
   │     └─ Go to Phase 7 (Logging)
   │
   └─ REPEAT: Check every candle until closure

┌──────────────────────────────────────────────────────────────┐
│ PHASE 7: TRADE LOGGING & RESULT RECORDING                   │
└──────────────────────────────────────────────────────────────┘

7. Trade closes (either TP, SL, or forced):
   
   ├─ Get closed trade details from MT5
   │  ├─ Query HistoryDealsTotal()
   │  ├─ Find matching ticket
   │  └─ Get exit_price, exit_time, profit
   │
   ├─ Update TradeRecord:
   │  ├─ exit_price = closed price
   │  ├─ exit_time = close time
   │  ├─ profit = final P&L
   │  └─ Calculate session_name = GetCurrentSession()
   │
   ├─ Save to global array:
   │  ├─ SaveTradeToArray(...complete record...)
   │  ├─ g_TradeCount++
   │  └─ Store in g_BacktestTrades[] array
   │
   ├─ Reset position flags:
   │  ├─ hasBuyPosition_M15 = false
   │  ├─ activeBuyTrade_M15.ticket = 0
   │  ├─ entryCountBuy_M15 = 0 (reset entry counter)
   │  └─ trailingStopActiveBuy_M15 = false
   │
   ├─ Log result:
   │  ├─ Print("Trade closed: Type=BUY, Entry=2100.50, Exit=2102.75")
   │  ├─ Print("Profit=+225 pips, Session=Asia")
   │  └─ Update statistics
   │
   └─ READY: Wait for next signal

┌──────────────────────────────────────────────────────────────┐
│ PHASE 8: DATA EXPORT (OnDeinit or OnTester)                 │
└──────────────────────────────────────────────────────────────┘

8. When backtest ends or EA removed:
   
   ├─ ExportBacktestToCSV()
   │  └─ → Backtest_Results_XAUUSD_2025-12-30.csv
   │     (All trades detail)
   │
   ├─ ExportBacktestSummaryToCSV()
   │  └─ → Backtest_Summary_XAUUSD_2025-12-30.csv
   │     (Overall metrics: win rate, profit factor, drawdown)
   │
   ├─ ExportMarketDataToCSV(M15)
   │  └─ → MarketData_XAUUSD_M15_2025-12-30.csv
   │     (OHLC data dengan EMA200)
   │
   ├─ ExportMarketDataToCSV(H1)
   │  └─ → MarketData_XAUUSD_H1_2025-12-30.csv
   │     (OHLC data dengan EMA200)
   │
   ├─ ExportLLHHBOSToCSV()
   │  └─ → LLHHBOSData_XAUUSD_2025-12-30.csv
   │     (All patterns: LL, HH, BoS, CHoCH with timestamps)
   │
   ├─ ExportSessionZoneToCSV()
   │  └─ → SessionZone_XAUUSD_2025-12-30.csv
   │     (Session-specific metrics)
   │
   └─ CSV files ready for:
      ├─ Analysis (Jupyter Notebook)
      ├─ Database upload (PostgreSQL Neon)
      ├─ AI model training (XGBoost)
      └─ Strategy optimization

┌──────────────────────────────────────────────────────────────┐
│ PHASE 9: AI MODEL TRAINING (Optional - Post-Backtest)       │
└──────────────────────────────────────────────────────────────┘

9. After backtest data collected:
   
   ├─ Python AI Server processes:
   │  ├─ Load Backtest_Results_*.csv
   │  ├─ Load LLHHBOSData_*.csv (10 pattern features)
   │  ├─ Load MarketData_*.csv (10 market features)
   │  └─ Combine → 20-feature vector
   │
   ├─ Data Processor extracts:
   │  ├─ Market Features (10):
   │  │  ├─ profit_ratio, win_rate, avg_win/loss
   │  │  ├─ risk_reward, winning_streak, losing_streak
   │  │  ├─ volatility, momentum, time_of_day
   │  │  └─ (calculated from Backtest_Results)
   │  │
   │  └─ Pattern Features (10):
   │     ├─ ll_count_h1, hh_count_h1, bos_count_h1, choch_count_h1
   │     ├─ ll_count_m15, hh_count_m15, bos_count_m15, choch_count_m15
   │     ├─ pattern_frequency, bullish_pattern_ratio
   │     └─ (counted from LLHHBOSData)
   │
   ├─ XGBoost Model trains on 20 features
   │  ├─ Labels: profitable (1) vs loss (0)
   │  ├─ 150 trees, max_depth=6, learning_rate=0.08
   │  └─ Cross-validation untuk avoid overfitting
   │
   ├─ Save trained model:
   │  ├─ trading_model.pkl (serialized XGBoost)
   │  ├─ scaler.pkl (StandardScaler for features)
   │  └─ training_metrics.json (accuracy, precision, recall)
   │
   └─ Ready for LIVE PREDICTION:
      └─ When EA sends signal to Python Server
         ├─ Extract 20 features dari current market data
         ├─ Run XGBoost.predict() 
         └─ Return confidence score (0.0 - 1.0)

CYCLE COMPLETE ✓

Pattern detected → Filtered → Trade executed → Managed → Closed → Logged → Model trained
                                                                                    ↓
                                    Next cycle begins with improved predictions
```

---

## 📊 SUMMARY: Key Statistics

| Metric | Value | Purpose |
|--------|-------|---------|
| **Total Lines** | ~4,500 | Complete EA implementation |
| **Timeframes** | 2 (M15, H1) | Dual-frame strategy |
| **Patterns** | 4 (HH, LL, BoS, CHoCH) | Smart Money recognition |
| **Entry Filters** | 5 | Signal validation |
| **CSV Exports** | 6 types | Comprehensive data capture |
| **Trailing Stages** | 3 (BE, 50%, Trail) | Dynamic risk management |
| **Sessions Tracked** | 4 (Sydney, Asia, London, NY) | Session-specific analysis |
| **Data Array Size** | Dynamic | Unlimited trade recording |
| **AI Features** | 20 (10 market + 10 pattern) | XGBoost model input |

---

**Document Version:** 1.0  
**Completeness:** 100% End-to-End Coverage  
**Date:** April 20, 2026  
**Status:** ✅ PRODUCTION READY
