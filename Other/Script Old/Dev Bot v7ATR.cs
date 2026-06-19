//+------------------------------------------------------------------+
//| File: HH_LL_Extraction_M15.mq5                                  |
//| Purpose: Isolate HH/LL Detection and Horizontal Zone Drawing     |
//| Timeframe: M15 (15-minute) specific implementation              |
//| Note: This version is specifically optimized for M15 timeframe  |
//+------------------------------------------------------------------+
#include <Trade/Trade.mqh>  // Untuk fungsi trading
#include <Tools/datetime.mqh>  // Untuk manipulasi waktu
CTrade trade;  // Objek untuk eksekusi trading

//+------------------------------------------------------------------+
//| BACKTEST DATA EXPORT - Struct & Global Variables                  |
//+------------------------------------------------------------------+
struct BacktestTrade
{
    ulong     ticket;
    string    symbol;
    string    type;          // "BUY" atau "SELL"
    double    entry_price;
    double    exit_price;
    double    sl;
    double    tp;
    double    profit;
    datetime  entry_time;
    datetime  exit_time;
    double    lot_size;
    ulong     magic_number;
    string    timeframe;     // "M15" atau "H1"
    double    spread_cost;   // Cost dari bid-ask spread (dalam currency)
    double    commission;    // Komisi broker (dalam currency)
    string    session_name;  // Trading session (Asia, London, NewYork, Sydney)
};

BacktestTrade g_BacktestTrades[];   // Array dinamis untuk menyimpan semua trade
int           g_TradeCount = 0;     // Jumlah trade yang tersimpan

//+------------------------------------------------------------------+
//| STRUKTUR DATA UNTUK LL, HH, BOS, CHoCH                             |
//+------------------------------------------------------------------+
struct LLHHBOSData
{
    string    type;           // "LL", "HH", "BoS", "CHoCH"
    string    direction;      // "Bullish" atau "Bearish"
    double    price;          // Harga level
    datetime  time;           // Waktu terdeteksi
    string    timeframe;      // "M15" atau "H1"
    string    status;         // "Confirmed", "Active", "Target"
    double    previous_price; // Harga sebelumnya untuk referensi
    datetime  previous_time;  // Waktu sebelumnya
};

LLHHBOSData g_LLHHBOSData[];        // Array dinamis untuk menyimpan LL, HH, BOS, CHoCH
int         g_LLHHBOSCount = 0;     // Jumlah data yang tersimpan

//+------------------------------------------------------------------+
//| STRUKTUR DATA UNTUK HISTORY ACCEPTED LEVELS (HH & LL)             |
//+------------------------------------------------------------------+
struct AcceptedLevelHistory
{
    string    type;           // "HH" atau "LL"
    double    price;          // Harga level
    datetime  time;           // Waktu terdeteksi
    string    timeframe;      // "M15" atau "H1"
};

AcceptedLevelHistory g_AcceptedLevelHistory[];  // Array untuk menyimpan semua update HH & LL
int                  g_AcceptedLevelHistoryCount = 0; // Jumlah history yang tersimpan

//+------------------------------------------------------------------+
//| STRUKTUR DATA UNIFIED EVENT (untuk sorting berdasarkan waktu)      |
//+------------------------------------------------------------------+
struct UnifiedEvent
{
    datetime  time;           // Waktu untuk sorting
    string    type;           // "CHoCH", "BoS", "HH", "LL"
    string    direction;      // "Bullish", "Bearish", "Update"
    double    price;          // Harga
    string    timeframe;      // "M15" atau "H1"
    string    status;         // "Confirmed", "Accepted"
    double    previousPrice;  // Harga sebelumnya
    string    previousTime;   // Waktu sebelumnya
};

UnifiedEvent g_UnifiedEvents[];  // Array untuk menyimpan semua events tergabung
int          g_UnifiedEventCount = 0; // Jumlah unified events

//+------------------------------------------------------------------+
//| STRUKTUR DATA UNTUK MARKET STRUCTURE RECORD (Comprehensive)       |
//+------------------------------------------------------------------+
struct MarketStructureRecord
{
    datetime  time;                    // Waktu candle
    string    timeframe;               // "M15" atau "H1"
    
    // Levels
    double    lastAcceptedHH;          // Last accepted Higher High
    double    lastAcceptedLL;          // Last accepted Lower Low
    
    // CHoCH Status
    bool      chochBullishTriggered;   // CHoCH Bullish terjadi
    double    chochBullishPrice;       // Harga saat CHoCH Bullish
    
    bool      chochBearishTriggered;   // CHoCH Bearish terjadi
    double    chochBearishPrice;       // Harga saat CHoCH Bearish
    
    // BoS Status
    bool      bosBullishTriggered;     // BoS Bullish terjadi
    double    bosBullishPrice;         // Harga saat BoS Bullish
    
    bool      bosBearishTriggered;     // BoS Bearish terjadi
    double    bosBearishPrice;         // Harga saat BoS Bearish
    
    // EMA Data
    double    ema200;                  // Nilai EMA200
};

MarketStructureRecord g_StructureRecords[];  // Array untuk menyimpan market structure records
int                   g_StructureRecordsCount = 0; // Jumlah records

//+------------------------------------------------------------------+
//| Simpan LL, HH, BOS, CHoCH data ke array global                     |
//+------------------------------------------------------------------+
void SaveLLHHBOSToArray(string type, string direction, double price,
                        datetime time, string timeframe, string status,
                        double prev_price = 0, datetime prev_time = 0)
{
    int newSize = g_LLHHBOSCount + 1;
    ArrayResize(g_LLHHBOSData, newSize);
    
    g_LLHHBOSData[g_LLHHBOSCount].type           = type;
    g_LLHHBOSData[g_LLHHBOSCount].direction      = direction;
    g_LLHHBOSData[g_LLHHBOSCount].price          = price;
    g_LLHHBOSData[g_LLHHBOSCount].time           = time;
    g_LLHHBOSData[g_LLHHBOSCount].timeframe      = timeframe;
    g_LLHHBOSData[g_LLHHBOSCount].status         = status;
    g_LLHHBOSData[g_LLHHBOSCount].previous_price = prev_price;
    g_LLHHBOSData[g_LLHHBOSCount].previous_time  = prev_time;
    
    g_LLHHBOSCount = newSize;
    PrintFormat("💾 [SAVED] %s %s: %.5f @ %s | Timeframe: %s | Status: %s",
                type, direction, price, TimeToString(time, TIME_DATE|TIME_SECONDS), 
                timeframe, status);
}

//+------------------------------------------------------------------+
//| Simpan accepted level (HH/LL) ke history array                    |
//+------------------------------------------------------------------+
void SaveAcceptedLevelToHistory(string type, double price, datetime time, string timeframe)
{
    int newSize = g_AcceptedLevelHistoryCount + 1;
    ArrayResize(g_AcceptedLevelHistory, newSize);
    
    g_AcceptedLevelHistory[g_AcceptedLevelHistoryCount].type       = type;
    g_AcceptedLevelHistory[g_AcceptedLevelHistoryCount].price      = price;
    g_AcceptedLevelHistory[g_AcceptedLevelHistoryCount].time       = time;
    g_AcceptedLevelHistory[g_AcceptedLevelHistoryCount].timeframe  = timeframe;
    
    g_AcceptedLevelHistoryCount = newSize;
}

//+------------------------------------------------------------------+
//| Simpan Market Structure Record (HH, LL, CHoCH, BoS, EMA)          |
//+------------------------------------------------------------------+
void SaveMarketStructureRecord(datetime time, string timeframe,
                                double lastHH, double lastLL, double ema200Value,
                                bool chochBull, double chochBullPrice,
                                bool chochBear, double chochBearPrice,
                                bool bosBull, double bosBullPrice,
                                bool bosBear, double bosBearPrice)
{
    int newSize = g_StructureRecordsCount + 1;
    ArrayResize(g_StructureRecords, newSize);
    
    g_StructureRecords[g_StructureRecordsCount].time                    = time;
    g_StructureRecords[g_StructureRecordsCount].timeframe               = timeframe;
    g_StructureRecords[g_StructureRecordsCount].lastAcceptedHH          = lastHH;
    g_StructureRecords[g_StructureRecordsCount].lastAcceptedLL          = lastLL;
    g_StructureRecords[g_StructureRecordsCount].ema200                  = ema200Value;
    
    g_StructureRecords[g_StructureRecordsCount].chochBullishTriggered   = chochBull;
    g_StructureRecords[g_StructureRecordsCount].chochBullishPrice       = chochBullPrice;
    
    g_StructureRecords[g_StructureRecordsCount].chochBearishTriggered   = chochBear;
    g_StructureRecords[g_StructureRecordsCount].chochBearishPrice       = chochBearPrice;
    
    g_StructureRecords[g_StructureRecordsCount].bosBullishTriggered     = bosBull;
    g_StructureRecords[g_StructureRecordsCount].bosBullishPrice         = bosBullPrice;
    
    g_StructureRecords[g_StructureRecordsCount].bosBearishTriggered     = bosBear;
    g_StructureRecords[g_StructureRecordsCount].bosBearishPrice         = bosBearPrice;
    
    g_StructureRecordsCount = newSize;
}

//+------------------------------------------------------------------+
//| Simpan trade yang sudah ditutup ke array global                   |
//+------------------------------------------------------------------+
void SaveTradeToArray(ulong ticket, string symbol, string type, 
                      double entry_price, double exit_price, 
                      double sl, double tp, double profit,
                      datetime entry_time, datetime exit_time,
                      double lot_size, ulong magic, string tf,
                      double spread_cost = 0, double commission = 0, string session = "")
{
    int newSize = g_TradeCount + 1;
    ArrayResize(g_BacktestTrades, newSize);
    
    g_BacktestTrades[g_TradeCount].ticket       = ticket;
    g_BacktestTrades[g_TradeCount].symbol       = symbol;
    g_BacktestTrades[g_TradeCount].type         = type;
    g_BacktestTrades[g_TradeCount].entry_price  = entry_price;
    g_BacktestTrades[g_TradeCount].exit_price   = exit_price;
    g_BacktestTrades[g_TradeCount].sl           = sl;
    g_BacktestTrades[g_TradeCount].tp           = tp;
    g_BacktestTrades[g_TradeCount].profit       = profit;
    g_BacktestTrades[g_TradeCount].entry_time   = entry_time;
    g_BacktestTrades[g_TradeCount].exit_time    = exit_time;
    g_BacktestTrades[g_TradeCount].lot_size     = lot_size;
    g_BacktestTrades[g_TradeCount].magic_number = magic;
    g_BacktestTrades[g_TradeCount].timeframe    = tf;
    g_BacktestTrades[g_TradeCount].spread_cost  = spread_cost;
    g_BacktestTrades[g_TradeCount].commission   = commission;
    g_BacktestTrades[g_TradeCount].session_name = session;
    
    g_TradeCount = newSize;
    double net_profit = profit - spread_cost - commission;
    PrintFormat("💾 [SAVED] Trade #%d: %s %s [%s] | Entry: %.5f | Exit: %.5f | Profit: %.2f | Spread: %.2f | Commission: %.2f | Net: %.2f",
                g_TradeCount, type, tf, session, entry_price, exit_price, profit, spread_cost, commission, net_profit);
}

//+------------------------------------------------------------------+
//| Export hasil backtest ke file CSV                                  |
//+------------------------------------------------------------------+
void ExportBacktestToCSV()
{
    if (g_TradeCount == 0)
    {
        Print("⚠️ [EXPORT] Tidak ada trade untuk di-export.");
        return;
    }
    
    string dateStr = TimeToString(TimeCurrent(), TIME_DATE);
    StringReplace(dateStr, ".", "-");
    string filename = "Backtest_Results_" + _Symbol + "_" + dateStr + ".csv";
    
    int handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ",");
    if (handle == INVALID_HANDLE)
    {
        PrintFormat("❌ [EXPORT] Gagal membuat file: %s | Error: %d", filename, GetLastError());
        return;
    }
    
    // Header
    FileWrite(handle, "Ticket", "Symbol", "Type", "EntryPrice", "ExitPrice", 
              "SL", "TP", "Profit", "Spread_Cost", "Commission", "Net_Profit",
              "Session", "EntryTime", "ExitTime", "LotSize", "MagicNumber", "Timeframe");
    
    // Data rows
    for (int i = 0; i < g_TradeCount; i++)
    {
        double net_profit = g_BacktestTrades[i].profit - g_BacktestTrades[i].spread_cost - g_BacktestTrades[i].commission;
        
        FileWrite(handle, 
                  IntegerToString(g_BacktestTrades[i].ticket),
                  g_BacktestTrades[i].symbol,
                  g_BacktestTrades[i].type,
                  DoubleToString(g_BacktestTrades[i].entry_price, _Digits),
                  DoubleToString(g_BacktestTrades[i].exit_price, _Digits),
                  DoubleToString(g_BacktestTrades[i].sl, _Digits),
                  DoubleToString(g_BacktestTrades[i].tp, _Digits),
                  DoubleToString(g_BacktestTrades[i].profit, 2),
                  DoubleToString(g_BacktestTrades[i].spread_cost, 2),
                  DoubleToString(g_BacktestTrades[i].commission, 2),
                  DoubleToString(net_profit, 2),
                  g_BacktestTrades[i].session_name,
                  TimeToString(g_BacktestTrades[i].entry_time, TIME_DATE|TIME_SECONDS),
                  TimeToString(g_BacktestTrades[i].exit_time, TIME_DATE|TIME_SECONDS),
                  DoubleToString(g_BacktestTrades[i].lot_size, 2),
                  IntegerToString(g_BacktestTrades[i].magic_number),
                  g_BacktestTrades[i].timeframe);
    }
    
    FileClose(handle);
    PrintFormat("✅ [EXPORT] Backtest results berhasil di-export: %s (%d trades)", filename, g_TradeCount);
}

//+------------------------------------------------------------------+
//| Export summary backtest ke file CSV                                |
//+------------------------------------------------------------------+
void ExportBacktestSummaryToCSV()
{
    if (g_TradeCount == 0) return;
    
    string dateStr = TimeToString(TimeCurrent(), TIME_DATE);
    StringReplace(dateStr, ".", "-");
    string filename = "Backtest_Summary_" + _Symbol + "_" + dateStr + ".csv";
    
    // Hitung statistik
    int    winCount    = 0;
    int    loseCount   = 0;
    double totalProfit = 0;
    double maxDrawdown = 0;
    double runningPnL  = 0;
    double peakPnL     = 0;
    double grossProfit = 0;
    double grossLoss   = 0;
    datetime startDate = g_BacktestTrades[0].entry_time;
    datetime endDate   = g_BacktestTrades[g_TradeCount-1].exit_time;
    
    for (int i = 0; i < g_TradeCount; i++)
    {
        double p = g_BacktestTrades[i].profit;
        totalProfit += p;
        runningPnL  += p;
        
        if (p > 0) { winCount++; grossProfit += p; }
        else       { loseCount++; grossLoss += MathAbs(p); }
        
        if (runningPnL > peakPnL) peakPnL = runningPnL;
        double dd = peakPnL - runningPnL;
        if (dd > maxDrawdown) maxDrawdown = dd;
    }
    
    double winRate      = (g_TradeCount > 0) ? (double)winCount / g_TradeCount * 100.0 : 0;
    double profitFactor = (grossLoss > 0) ? grossProfit / grossLoss : 0;
    
    int handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ",");
    if (handle == INVALID_HANDLE)
    {
        PrintFormat("❌ [EXPORT] Gagal membuat file summary: %s", filename);
        return;
    }
    
    FileWrite(handle, "Symbol", "TotalTrades", "WinningTrades", "LosingTrades", 
              "WinRate", "TotalProfit", "MaxDrawdown", "ProfitFactor", 
              "StartDate", "EndDate");
    FileWrite(handle, 
              _Symbol,
              IntegerToString(g_TradeCount),
              IntegerToString(winCount),
              IntegerToString(loseCount),
              DoubleToString(winRate, 2),
              DoubleToString(totalProfit, 2),
              DoubleToString(maxDrawdown, 2),
              DoubleToString(profitFactor, 2),
              TimeToString(startDate, TIME_DATE|TIME_SECONDS),
              TimeToString(endDate, TIME_DATE|TIME_SECONDS));
    
    FileClose(handle);
    PrintFormat("✅ [EXPORT] Summary: %d trades | Win: %d (%.1f%%) | Profit: %.2f | DD: %.2f | PF: %.2f",
                g_TradeCount, winCount, winRate, totalProfit, maxDrawdown, profitFactor);
}

//+------------------------------------------------------------------+
//| Export market data (OHLCV + EMA200) ke file CSV                    |
//+------------------------------------------------------------------+
void ExportMarketDataToCSV(ENUM_TIMEFRAMES tf, int barsToExport)
{
    string tfStr = (tf == PERIOD_M15) ? "M15" : "H1";
    string dateStr = TimeToString(TimeCurrent(), TIME_DATE);
    StringReplace(dateStr, ".", "-");
    string filename = "MarketData_" + _Symbol + "_" + tfStr + "_" + dateStr + ".csv";
    
    MqlRates rates[];
    ArraySetAsSeries(rates, true);
    int copied = CopyRates(_Symbol, tf, 0, barsToExport, rates);
    if (copied <= 0)
    {
        PrintFormat("❌ [EXPORT] Gagal mengambil data %s: %d", tfStr, GetLastError());
        return;
    }
    
    // Ambil EMA200
    int emaHandle = (tf == PERIOD_M15) ? handleEMA_M15 : handleEMA_H1;
    double emaBuffer[];
    ArraySetAsSeries(emaBuffer, true);
    int emaCopied = CopyBuffer(emaHandle, 0, 0, barsToExport, emaBuffer);
    
    int handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ",");
    if (handle == INVALID_HANDLE)
    {
        PrintFormat("❌ [EXPORT] Gagal membuat file: %s | Error: %d", filename, GetLastError());
        return;
    }
    
    // Header
    FileWrite(handle, "Time", "Open", "High", "Low", "Close", "Volume", "Spread", "EMA200");
    
    // Data (dari terlama ke terbaru)
    for (int i = copied - 1; i >= 0; i--)
    {
        double emaVal = (i < emaCopied) ? emaBuffer[i] : 0;
        FileWrite(handle,
                  TimeToString(rates[i].time, TIME_DATE|TIME_SECONDS),
                  DoubleToString(rates[i].open, _Digits),
                  DoubleToString(rates[i].high, _Digits),
                  DoubleToString(rates[i].low, _Digits),
                  DoubleToString(rates[i].close, _Digits),
                  IntegerToString(rates[i].tick_volume),
                  IntegerToString(rates[i].spread),
                  DoubleToString(emaVal, _Digits));
    }
    
    FileClose(handle);
    PrintFormat("✅ [EXPORT] Market data %s berhasil di-export: %s (%d bars)", tfStr, filename, copied);
}

//+------------------------------------------------------------------+
//| Export LL, HH, BOS, CHoCH data ke file CSV (sorted by time)        |
//+------------------------------------------------------------------+
void ExportLLHHBOSToCSV()
{
    string dateStr = TimeToString(TimeCurrent(), TIME_DATE);
    StringReplace(dateStr, ".", "-");
    string filename = "LLHHBOSData_" + _Symbol + "_" + dateStr + ".csv";
    
    int handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ",");
    if (handle == INVALID_HANDLE)
    {
        PrintFormat("❌ [EXPORT] Gagal membuat file: %s | Error: %d", filename, GetLastError());
        return;
    }
    
    // ===== Step 1: Merge CHoCH/BoS dan HH/LL ke dalam UnifiedEvent array =====
    int totalEvents = 0;
    
    // Count total events
    totalEvents = g_LLHHBOSCount; // CHoCH + BoS
    totalEvents += g_AcceptedLevelHistoryCount; // HH/LL Updates
    
    // Create unified events array
    ArrayResize(g_UnifiedEvents, totalEvents);
    g_UnifiedEventCount = 0;
    
    // Add CHoCH/BoS events
    for (int i = 0; i < g_LLHHBOSCount; i++)
    {
        // Skip LL,Reference dan HH,Reference entries
        if ((g_LLHHBOSData[i].type == "LL" || g_LLHHBOSData[i].type == "HH") && 
            g_LLHHBOSData[i].direction == "Reference")
        {
            continue;
        }
        
        g_UnifiedEvents[g_UnifiedEventCount].time           = g_LLHHBOSData[i].time;
        g_UnifiedEvents[g_UnifiedEventCount].type           = g_LLHHBOSData[i].type;
        g_UnifiedEvents[g_UnifiedEventCount].direction      = g_LLHHBOSData[i].direction;
        g_UnifiedEvents[g_UnifiedEventCount].price          = g_LLHHBOSData[i].price;
        g_UnifiedEvents[g_UnifiedEventCount].timeframe      = g_LLHHBOSData[i].timeframe;
        g_UnifiedEvents[g_UnifiedEventCount].status         = g_LLHHBOSData[i].status;
        g_UnifiedEvents[g_UnifiedEventCount].previousPrice  = g_LLHHBOSData[i].previous_price;
        g_UnifiedEvents[g_UnifiedEventCount].previousTime   = TimeToString(g_LLHHBOSData[i].previous_time, TIME_DATE|TIME_SECONDS);
        
        g_UnifiedEventCount++;
    }
    
    // Add HH/LL Update events
    for (int i = 0; i < g_AcceptedLevelHistoryCount; i++)
    {
        g_UnifiedEvents[g_UnifiedEventCount].time           = g_AcceptedLevelHistory[i].time;
        g_UnifiedEvents[g_UnifiedEventCount].type           = g_AcceptedLevelHistory[i].type;
        g_UnifiedEvents[g_UnifiedEventCount].direction      = "Update";
        g_UnifiedEvents[g_UnifiedEventCount].price          = g_AcceptedLevelHistory[i].price;
        g_UnifiedEvents[g_UnifiedEventCount].timeframe      = g_AcceptedLevelHistory[i].timeframe;
        g_UnifiedEvents[g_UnifiedEventCount].status         = "Accepted";
        g_UnifiedEvents[g_UnifiedEventCount].previousPrice  = 0;
        g_UnifiedEvents[g_UnifiedEventCount].previousTime   = "";
        
        g_UnifiedEventCount++;
    }
    
    // ===== Step 2: Sort by time (Bubble Sort) =====
    for (int i = 0; i < g_UnifiedEventCount - 1; i++)
    {
        for (int j = i + 1; j < g_UnifiedEventCount; j++)
        {
            if (g_UnifiedEvents[i].time > g_UnifiedEvents[j].time)
            {
                // Swap
                UnifiedEvent temp = g_UnifiedEvents[i];
                g_UnifiedEvents[i] = g_UnifiedEvents[j];
                g_UnifiedEvents[j] = temp;
            }
        }
    }
    
    // ===== Step 3: Write to CSV =====
    FileWrite(handle, "=== Market Structure Events (Sorted by Time) ===", "", "", "", "", "", "", "");
    FileWrite(handle, "Type", "Direction/Action", "Price", "Time", "Timeframe", 
              "Status", "PreviousPrice", "PreviousTime");
    
    // Write sorted events
    for (int i = 0; i < g_UnifiedEventCount; i++)
    {
        FileWrite(handle,
                  g_UnifiedEvents[i].type,
                  g_UnifiedEvents[i].direction,
                  DoubleToString(g_UnifiedEvents[i].price, _Digits),
                  TimeToString(g_UnifiedEvents[i].time, TIME_DATE|TIME_SECONDS),
                  g_UnifiedEvents[i].timeframe,
                  g_UnifiedEvents[i].status,
                  (g_UnifiedEvents[i].previousPrice > 0) ? DoubleToString(g_UnifiedEvents[i].previousPrice, _Digits) : "",
                  g_UnifiedEvents[i].previousTime);
    }
    
    if (g_UnifiedEventCount == 0)  
    {
        Print("⚠️ [EXPORT] Tidak ada Market Structure Events untuk di-export.");
        FileClose(handle);
        return;
    }
    
    FileClose(handle);
    PrintFormat("✅ [EXPORT] Market Structure Events berhasil di-export (sorted): %s (%d events)", filename, g_UnifiedEventCount);
}

//+------------------------------------------------------------------+
//| Export Market Structure Records ke file CSV                       |
//+------------------------------------------------------------------+
void ExportMarketStructureToCSV()
{
    if (g_StructureRecordsCount == 0)
    {
        Print("⚠️ [EXPORT] Tidak ada Market Structure Records untuk di-export.");
        return;
    }
    
    string dateStr = TimeToString(TimeCurrent(), TIME_DATE);
    StringReplace(dateStr, ".", "-");
    string filename = "MarketStructure_" + _Symbol + "_" + dateStr + ".csv";
    
    int handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ",");
    if (handle == INVALID_HANDLE)
    {
        PrintFormat("❌ [EXPORT] Gagal membuat file: %s | Error: %d", filename, GetLastError());
        return;
    }
    
    // Header
    FileWrite(handle, "Time", "Timeframe", "LastAcceptedHH", "LastAcceptedLL", "EMA200",
              "CHoCH_Bullish", "CHoCH_Bullish_Price", "CHoCH_Bearish", "CHoCH_Bearish_Price",
              "BoS_Bullish", "BoS_Bullish_Price", "BoS_Bearish", "BoS_Bearish_Price");
    
    // Data rows
    for (int i = 0; i < g_StructureRecordsCount; i++)
    {
        FileWrite(handle,
                  TimeToString(g_StructureRecords[i].time, TIME_DATE|TIME_SECONDS),
                  g_StructureRecords[i].timeframe,
                  DoubleToString(g_StructureRecords[i].lastAcceptedHH, _Digits),
                  DoubleToString(g_StructureRecords[i].lastAcceptedLL, _Digits),
                  DoubleToString(g_StructureRecords[i].ema200, _Digits),
                  (g_StructureRecords[i].chochBullishTriggered) ? "YES" : "NO",
                  (g_StructureRecords[i].chochBullishTriggered) ? DoubleToString(g_StructureRecords[i].chochBullishPrice, _Digits) : "N/A",
                  (g_StructureRecords[i].chochBearishTriggered) ? "YES" : "NO",
                  (g_StructureRecords[i].chochBearishTriggered) ? DoubleToString(g_StructureRecords[i].chochBearishPrice, _Digits) : "N/A",
                  (g_StructureRecords[i].bosBullishTriggered) ? "YES" : "NO",
                  (g_StructureRecords[i].bosBullishTriggered) ? DoubleToString(g_StructureRecords[i].bosBullishPrice, _Digits) : "N/A",
                  (g_StructureRecords[i].bosBearishTriggered) ? "YES" : "NO",
                  (g_StructureRecords[i].bosBearishTriggered) ? DoubleToString(g_StructureRecords[i].bosBearishPrice, _Digits) : "N/A");
    }
    
    FileClose(handle);
    PrintFormat("✅ [EXPORT] Market Structure Records berhasil di-export: %s (%d entries)", filename, g_StructureRecordsCount);
}

//+------------------------------------------------------------------+
//| Export semua data (dipanggil dari OnDeinit/OnTester)               |
//+------------------------------------------------------------------+
void ExportAllData()
{
    Print("📦 [EXPORT] Memulai export semua data...");
    
    // 1. Export backtest results
    ExportBacktestToCSV();
    
    // 2. Export backtest summary
    ExportBacktestSummaryToCSV();
    
    // 3. Export LL, HH, BOS, CHoCH data (MERGED dengan Accepted Level History)
    ExportLLHHBOSToCSV();  // ✅ AKTIF - Menyimpan CHoCH, BoS, HH/LL updates
    
    // 4. Export Market Structure Records
    ExportMarketStructureToCSV();
    
    // 5. Export Session Zone data (NEW)
    ExportSessionZoneToCSV();  // ✅ AKTIF - Menyimpan data sesi trading
    
    // 6. Export market data M15 (5000 bars terakhir)
    ExportMarketDataToCSV(PERIOD_M15, 50000000);
    
    // 7. Export market data H1 (2000 bars terakhir)
    ExportMarketDataToCSV(PERIOD_H1, 20000000);
    
    Print("✅ [EXPORT] Semua data berhasil di-export ke folder MQL5/Files/");
}

//+------------------------------------------------------------------+
//| SESSION ZONE TRACKING - Modul Terpisah                           |
//+------------------------------------------------------------------+
// Input parameters untuk Session Zone
input bool EnableSessionZone = true;           // Enable/Disable Session Zone tracking
input bool ShowSessionZoneVisuals = true;      // Tampilkan zona sesi di chart
input bool ExportSessionZoneData = true;       // Export data session zone ke CSV
input color SessionAsiaColor = clrRed;       // Warna Asia Session
input color SessionLondonColor = clrYellow;    // Warna London Session
input color SessionNewYorkColor = clrBlue;     // Warna New York Session
input color SessionSydneyColor = clrGreen;     // Warna Sydney Session

// Struct untuk Session Zone
struct SessionZoneRecord
{
    datetime  time;           // Waktu candle
    string    sessionName;    // Nama sesi: "Asia", "London", "NewYork", "Sydney"
    bool      isSessionActive;// Apakah sesi aktif pada waktu ini
    double    sessionOpenPrice; // Harga open saat sesi dimulai
    double    sessionHighPrice; // Harga high dalam sesi
    double    sessionLowPrice;  // Harga low dalam sesi
    double    sessionClosePrice; // Harga close dalam sesi
    int       sessionBarsCount; // Jumlah bar dalam sesi
};

SessionZoneRecord g_SessionZoneRecords[];     // Array untuk menyimpan session zone records
int               g_SessionZoneRecordsCount = 0; // Jumlah records

// Global variables untuk Session Zone
static string currentActiveSession = "";      // Sesi yang sedang aktif
static datetime lastSessionChangeTime = 0;    // Waktu perubahan sesi terakhir
static double sessionOpenPrice = 0;           // Harga open sesi yang sedang berjalan
static double sessionHighPrice = 0;           // Harga high sesi yang sedang berjalan
static double sessionLowPrice = 0;            // Harga low sesi yang sedang berjalan
static int sessionBarsCount = 0;              // Jumlah bar dalam sesi

// Array untuk menyimpan zona visual
string g_SessionZoneNames[];                  // Nama-nama zona yang digambar
int g_SessionZoneNamesCount = 0;

//+------------------------------------------------------------------+
//| Deteksi sesi trading berdasarkan GMT time                        |
//+------------------------------------------------------------------+
string GetCurrentSession()
{
    // Ambil waktu GMT
    datetime currentTime = TimeCurrent();
    MqlDateTime dtStruct;
    TimeToStruct(currentTime, dtStruct);
    
    int hour = dtStruct.hour;
    int dayOfWeek = dtStruct.day_of_week;
    
    // Jika weekend (Sabtu/Minggu), tidak ada sesi aktif
    if (dayOfWeek == 0 || dayOfWeek == 6)
        return "Weekend";
    
    // Session times (GMT)
    // Asia Session: 22:00 - 07:00 (Tokyo)
    // London Session: 08:00 - 16:00 (London)
    // New York Session: 13:00 - 22:00 (New York)
    // Sydney Session: 21:00 - 06:00 (Sydney - overlaps dengan Asia)
    
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

//+------------------------------------------------------------------+
//| Simpan Session Zone Record ke array global                       |
//+------------------------------------------------------------------+
void SaveSessionZoneRecord(datetime time, string sessionName, bool isActive,
                          double openPrice, double highPrice, double lowPrice,
                          double closePrice, int barsCount)
{
    int newSize = g_SessionZoneRecordsCount + 1;
    ArrayResize(g_SessionZoneRecords, newSize);
    
    g_SessionZoneRecords[g_SessionZoneRecordsCount].time              = time;
    g_SessionZoneRecords[g_SessionZoneRecordsCount].sessionName       = sessionName;
    g_SessionZoneRecords[g_SessionZoneRecordsCount].isSessionActive   = isActive;
    g_SessionZoneRecords[g_SessionZoneRecordsCount].sessionOpenPrice  = openPrice;
    g_SessionZoneRecords[g_SessionZoneRecordsCount].sessionHighPrice  = highPrice;
    g_SessionZoneRecords[g_SessionZoneRecordsCount].sessionLowPrice   = lowPrice;
    g_SessionZoneRecords[g_SessionZoneRecordsCount].sessionClosePrice = closePrice;
    g_SessionZoneRecords[g_SessionZoneRecordsCount].sessionBarsCount  = barsCount;
    
    g_SessionZoneRecordsCount = newSize;
}

//+------------------------------------------------------------------+
//| Helper: Blend color dengan white untuk efek transparency 70%      |
//+------------------------------------------------------------------+
color MakeTransparent70(color clr)
{
    // 70% transparent = 30% opacity
    // Blend dengan white: newColor = color * 0.3 + white * 0.7
    uchar r = (uchar)((clr & 0xFF) * 30 / 100 + 255 * 70 / 100);
    uchar g = (uchar)(((clr >> 8) & 0xFF) * 30 / 100 + 255 * 70 / 100);
    uchar b = (uchar)(((clr >> 16) & 0xFF) * 30 / 100 + 255 * 70 / 100);
    
    return (uchar)b << 16 | (uchar)g << 8 | (uchar)r;
}

//+------------------------------------------------------------------+
//| Helper: Blend color dengan white untuk efek transparency 80%      |
//+------------------------------------------------------------------+
color MakeTransparent80(color clr)
{
    // 80% transparent = 20% opacity
    // Blend dengan white: newColor = color * 0.2 + white * 0.8
    uchar r = (uchar)((clr & 0xFF) * 20 / 100 + 255 * 80 / 100);
    uchar g = (uchar)(((clr >> 8) & 0xFF) * 20 / 100 + 255 * 80 / 100);
    uchar b = (uchar)(((clr >> 16) & 0xFF) * 20 / 100 + 255 * 80 / 100);
    
    return (uchar)b << 16 | (uchar)g << 8 | (uchar)r;
}

//+------------------------------------------------------------------+
//| Gambar shadow range untuk setiap session zone                     |
//+------------------------------------------------------------------+
void DrawSessionRangeShadows()
{
    if (!ShowSessionZoneVisuals) return;
    
    // Ambil data current time
    MqlDateTime currentDt;
    TimeToStruct(TimeCurrent(), currentDt);
    
    // Define session times (GMT)
    struct SessionTime {
        string name;
        int startHour;
        int endHour;
        color shadowColor;
    };
    
    SessionTime sessions[] = {
        {"Asia", 22, 7, SessionAsiaColor},
        {"London", 8, 16, SessionLondonColor},
        {"NewYork", 17, 22, SessionNewYorkColor},
        {"Sydney", 21, 6, SessionSydneyColor}
    };
    
    // Ambil range chart untuk top dan bottom price
    double highPrice = 999999;  // Sangat tinggi untuk cover top
    double lowPrice = 0;         // Sangat rendah untuk cover bottom
    
    // Ambil chart high/low untuk position label
    double topLabelPrice = 999999 - 5000;  // Sedikit dari atas
    
    // Draw shadows untuk setiap session
    for (int i = 0; i < ArraySize(sessions); i++)
    {
        // Hitung waktu start dan end untuk shadow
        datetime shadowStartTime, shadowEndTime;
        
        // Untuk session yang cross midnight (Asia: 22-7, Sydney: 21-6)
        if (sessions[i].startHour > sessions[i].endHour)
        {
            // Hari ini: start hour sampai tengah malam
            // Besok: jam 0 sampai end hour
            MqlDateTime startDt = currentDt;
            startDt.hour = sessions[i].startHour;
            startDt.min = 0;
            startDt.sec = 0;
            shadowStartTime = StructToTime(startDt);
            
            MqlDateTime endDt = currentDt;
            endDt.day = endDt.day + 1;
            endDt.hour = sessions[i].endHour;
            endDt.min = 0;
            endDt.sec = 0;
            shadowEndTime = StructToTime(endDt);
        }
        else
        {
            // Session normal (tidak cross midnight)
            MqlDateTime startDt = currentDt;
            startDt.hour = sessions[i].startHour;
            startDt.min = 0;
            startDt.sec = 0;
            shadowStartTime = StructToTime(startDt);
            
            MqlDateTime endDt = currentDt;
            endDt.hour = sessions[i].endHour;
            endDt.min = 0;
            endDt.sec = 0;
            shadowEndTime = StructToTime(endDt);
        }
        
        // Nama object shadow
        string shadowName = "SessionShadow_" + sessions[i].name + "_" + IntegerToString((int)shadowStartTime);
        
        // Hapus shadow lama jika ada
        ObjectDelete(0, shadowName);
        
        // Buat rectangle shadow dengan warna transparent 80%
        ObjectCreate(0, shadowName, OBJ_RECTANGLE, 0, shadowStartTime, highPrice, shadowEndTime, lowPrice);
        ObjectSetInteger(0, shadowName, OBJPROP_COLOR, MakeTransparent80(sessions[i].shadowColor));
        ObjectSetInteger(0, shadowName, OBJPROP_STYLE, STYLE_SOLID);
        ObjectSetInteger(0, shadowName, OBJPROP_WIDTH, 0);  // Borderless untuk tampilan clean
        ObjectSetInteger(0, shadowName, OBJPROP_FILL, true);  // Filled
        ObjectSetInteger(0, shadowName, OBJPROP_BACK, true);  // Behind candles
        
        // Tambah label nama session di TOP chart
        string labelName = "SessionLabel_" + sessions[i].name + "_" + IntegerToString((int)shadowStartTime);
        ObjectDelete(0, labelName);
        
        datetime labelTime = shadowStartTime + (shadowEndTime - shadowStartTime) / 2;  // Tengah-tengah waktu
        
        ObjectCreate(0, labelName, OBJ_TEXT, 0, labelTime, topLabelPrice);
        ObjectSetInteger(0, labelName, OBJPROP_COLOR, C'255,255,255');  // White text
        ObjectSetInteger(0, labelName, OBJPROP_FONTSIZE, 9);
        ObjectSetInteger(0, labelName, OBJPROP_ANCHOR, ANCHOR_CENTER);
        ObjectSetString(0, labelName, OBJPROP_TEXT, sessions[i].name);
        ObjectSetInteger(0, labelName, OBJPROP_BACK, false);  // In front
    }
    
    ChartRedraw();
}

//+------------------------------------------------------------------+
//| Update Session Zone tracking setiap bar baru                     |
//+------------------------------------------------------------------+
void UpdateSessionZoneTracking()
{
    if (!EnableSessionZone) return;
    
    static datetime lastProcessedTime = 0;
    datetime currentTime = TimeCurrent();
    
    // Proses hanya jika ada bar baru
    if (currentTime == lastProcessedTime)
        return;
    
    lastProcessedTime = currentTime;
    
    // Ambil harga close terkini
    MqlRates currentRate[];
    ArraySetAsSeries(currentRate, true);
    if (CopyRates(_Symbol, PERIOD_CURRENT, 0, 1, currentRate) < 1)
        return;
    double currentClose = currentRate[0].close;
    
    string session = GetCurrentSession();
    
    // Deteksi perubahan sesi
    if (session != currentActiveSession)
    {
        if (currentActiveSession != "" && currentActiveSession != "NoSession")
        {
            PrintFormat("📊 [SESSION] Sesi %s berakhir | Duration: %d bars | High: %.5f | Low: %.5f",
                       currentActiveSession, sessionBarsCount, sessionHighPrice, sessionLowPrice);
            
            // Simpan record sesi yang telah selesai
            SaveSessionZoneRecord(lastSessionChangeTime, currentActiveSession, false,
                                 sessionOpenPrice, sessionHighPrice, sessionLowPrice, 
                                 currentClose, sessionBarsCount);
        }
        
        // Set sesi baru
        currentActiveSession = session;
        lastSessionChangeTime = currentTime;
        sessionOpenPrice = currentClose;
        sessionHighPrice = currentClose;
        sessionLowPrice = currentClose;
        sessionBarsCount = 1;
        
        if (session != "NoSession" && session != "Weekend")
        {
            PrintFormat("🔔 [SESSION] Sesi %s dimulai | Open: %.5f | Time: %s",
                       session, sessionOpenPrice, TimeToString(currentTime));
        }
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

//+------------------------------------------------------------------+
//| Export Session Zone data ke CSV                                   |
//+------------------------------------------------------------------+
void ExportSessionZoneToCSV()
{
    if (!ExportSessionZoneData || g_SessionZoneRecordsCount == 0)
    {
        if (g_SessionZoneRecordsCount == 0)
            Print("⚠️ [SESSION EXPORT] Tidak ada data session zone untuk di-export.");
        return;
    }
    
    string dateStr = TimeToString(TimeCurrent(), TIME_DATE);
    StringReplace(dateStr, ".", "-");
    string filename = "SessionZone_" + _Symbol + "_" + dateStr + ".csv";
    
    int handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ",");
    if (handle == INVALID_HANDLE)
    {
        PrintFormat("❌ [SESSION EXPORT] Gagal membuat file: %s | Error: %d", filename, GetLastError());
        return;
    }
    
    // Header
    FileWrite(handle, "Time", "Session", "IsActive", "OpenPrice", "HighPrice", "LowPrice", 
              "ClosePrice", "BarsCount", "SessionRangePoints");
    
    // Data rows
    for (int i = 0; i < g_SessionZoneRecordsCount; i++)
    {
        double rangePoints = (g_SessionZoneRecords[i].sessionHighPrice - g_SessionZoneRecords[i].sessionLowPrice) / _Point;
        FileWrite(handle,
                  TimeToString(g_SessionZoneRecords[i].time, TIME_DATE|TIME_SECONDS),
                  g_SessionZoneRecords[i].sessionName,
                  g_SessionZoneRecords[i].isSessionActive ? "YES" : "NO",
                  DoubleToString(g_SessionZoneRecords[i].sessionOpenPrice, _Digits),
                  DoubleToString(g_SessionZoneRecords[i].sessionHighPrice, _Digits),
                  DoubleToString(g_SessionZoneRecords[i].sessionLowPrice, _Digits),
                  DoubleToString(g_SessionZoneRecords[i].sessionClosePrice, _Digits),
                  IntegerToString(g_SessionZoneRecords[i].sessionBarsCount),
                  DoubleToString(rangePoints, 0));
    }
    
    FileClose(handle);
    PrintFormat("✅ [SESSION EXPORT] Session Zone data berhasil di-export: %s (%d records)", 
               filename, g_SessionZoneRecordsCount);
}

//+------------------------------------------------------------------+
//| Tampilkan informasi sesi di label                                |
//+------------------------------------------------------------------+
void DisplaySessionInfo()
{
    if (!EnableSessionZone) return;
    
    string infoText = "Current Session: " + currentActiveSession;
    infoText += "\n" + "Open: " + DoubleToString(sessionOpenPrice > 0 ? sessionOpenPrice : 0, _Digits);
    infoText += "\n" + "High: " + DoubleToString(sessionHighPrice > 0 ? sessionHighPrice : 0, _Digits);
    infoText += "\n" + "Low: " + DoubleToString(sessionLowPrice > 0 ? sessionLowPrice : 0, _Digits);
    infoText += "\n" + "Bars: " + IntegerToString(sessionBarsCount);
    
    string labelName = "SessionInfoLabel";
    ObjectDelete(0, labelName);
    
    ObjectCreate(0, labelName, OBJ_LABEL, 0, 0, 0);
    ObjectSetInteger(0, labelName, OBJPROP_XDISTANCE, 10);
    ObjectSetInteger(0, labelName, OBJPROP_YDISTANCE, 100);
    ObjectSetInteger(0, labelName, OBJPROP_FONTSIZE, 9);
    ObjectSetString(0, labelName, OBJPROP_TEXT, infoText);
    ObjectSetInteger(0, labelName, OBJPROP_COLOR, clrWhite);
}


//----------------------------------------------------------------------------------------------//
//Khusus H1
//----------------------------------------------------------------------------------------------//
input int WindowSize_H1 = 15;    // Ukuran window untuk deteksi high/low (H1)
input int ZoneLength_H1 = 50;   // Panjang zona yang digambar (H1)
input int MovingPeriod_H1 = 200;  // Periode moving average
input int MovingShift_H1 = 0;

double   lastHH_byTime_H1 = -1;  // Last higher high (nilai harga) H1
datetime lastTimeHH_H1    = 0;   // Waktu last HH H1
double   lastLL_byTime_H1 = -1;  // Last lower low (nilai harga) H1
datetime lastTimeLL_H1    = 0;   // Waktu last LL H1
int lastLogHour_H1 = -1;  // Jam terakhir log EMA H1

// --- Variabel konfirmasi ---
static double lastAcceptedHH_H1      = -1;  // Last HH yang diterima (valid) H1
static double lastAcceptedLL_H1      = -1;  // Last LL yang diterima (valid) H1

// --- Variabel penolakan ---
static   double lastLoggedDeniedHH_H1          = -1;  // Last HH yang ditolak H1
static   datetime lastLoggedDeniedHHBarTime_H1 = 0;   // Waktu bar HH ditolak H1
static   datetime lastLoggedDeniedHHLogTime_H1 = 0;   // Waktu log penolakan HH H1
static   double lastLoggedDeniedLL_H1          = -1;  // Last LL yang ditolak H1
static   datetime lastLoggedDeniedLLBarTime_H1 = 0;   // Waktu bar LL ditolak H1
static   datetime lastLoggedDeniedLLLogTime_H1 = 0;   // Waktu log penolakan LL H1

// --- Variabel pencegahan spam log HH ---
static double lastLoggedValidHH_H1       = -1;  // Last valid HH yang dilog H1
static datetime lastLoggedValidHHTime_H1 = 0;   // Waktu log valid HH H1
static double lastLoggedValidLL_H1       = -1;  // Last valid LL yang dilog H1
static datetime lastLoggedValidLLTime_H1 = 0;   // Waktu log valid LL H1

// Interval log penolakan (dioptimalkan untuk H1)
static int deniedLogIntervalSeconds_H1  = 300;  // Interval log penolakan (detik) H1
static datetime lastProcessedTime_HH_H1 = 0;    // Waktu terakhir proses HH H1
static datetime lastProcessedTime_LL_H1 = 0;    // Waktu terakhir proses LL H1

// --- Variabel aktif ---
double activeCHoCH_HH_H1 = -1;  // CHoCH HH aktif H1
double activeBoS_HH_H1   = -1;  // BoS HH aktif H1
double activeCHoCH_LL_H1 = -1;  // CHoCH LL aktif H1
double activeBoS_LL_H1   = -1;  // BoS LL aktif H1

// --- Variabel post-CHoCH ---
double   postChoCH_HH_H1      = -1;  // HH setelah CHoCH H1
datetime time_postChoCH_HH_H1 = 0;   // Waktu post-CHoCH HH H1
double   postChoCH_LL_H1      = -1;  // LL setelah CHoCH H1
datetime time_postChoCH_LL_H1 = 0;   // Waktu post-CHoCH LL H1

// --- Variabel BoS ---
double   lastBoS_HH_H1      = -1;  // Last BoS HH H1
datetime time_lastBoS_HH_H1 = 0;   // Waktu last BoS HH H1
double   lastBoS_LL_H1      = -1;  // Last BoS LL H1
datetime time_lastBoS_LL_H1 = 0;   // Waktu last BoS LL H1

// --- Flags konfirmasi bullish ---
static bool chochBullishConfirmedFlag_H1 = false;  // Flag konfirmasi CHoCH bullish H1
static bool hhAfterChochConfirmedFlag_H1 = false;  // Flag HH setelah CHoCH H1
static bool bosBullishConfirmedFlag_H1   = false;  // Flag konfirmasi BoS bullish H1
static bool hhAfterBosConfirmedFlag_H1   = false;  // Flag HH setelah BoS H1

// --- Flags konfirmasi bearish ---
static bool chochBearishConfirmedFlag_H1 = false;  // Flag konfirmasi CHoCH bearish H1
static bool llAfterChochConfirmedFlag_H1 = false;  // Flag LL setelah CHoCH H1
static bool bosBearishConfirmedFlag_H1   = false;  // Flag konfirmasi BoS bearish H1
static bool llAfterBosConfirmedFlag_H1   = false;  // Flag LL setelah BoS H1

// --- Flags tren ---
bool chochBullish_H1     = false;  // Flag CHoCH bullish H1
bool chochBearish_H1     = false;  // Flag CHoCH bearish H1
bool isInTrendBullish_H1 = false;  // Flag dalam tren bullish H1
bool isInTrendBearish_H1 = false;  // Flag dalam tren bearish H1

// --- Variabel target CHoCH ---
static double targetChoCHBullishHH_H1    = -1;  // Target HH untuk CHoCH bullish H1
static double targetChoCHBearishLL_H1    = -1;  // Target LL untuk CHoCH bearish H1
static double targetChoCHBearishLowLL_H1 = -1;  // Target LL terendah untuk CHoCH bearish H1
static double targetBoSBearishLL_H1      = -1;  // Target LL untuk BoS bearish H1
static double targetBoSBearishLowLL_H1   = -1;  // Target HH untuk BoS bullish H1
double preChochHH_H1                     = -1;  // HH sebelum CHoCH H1
double preChochLL_H1                     = -1;  // LL sebelum CHoCH H1

// --- Variabel lainnya ---
static bool hlAfterHHChochSaved_H1 = false;  // Kunci agar MODE 1 hanya aktif 1x H1
static bool isSearchingForNewHL_H1 = false;  // Flag untuk mencari Higher Low baru H1

// --- Variabel untuk pelacakan perubahan flag ---
static string lastLoggedFlagStatusBullish_H1 = "";  // Status bullish flag terakhir yang dilog H1
static string lastLoggedFlagStatusBearish_H1 = "";  // Status bearish flag terakhir yang dilog H1

// --- Penyimpanan status log sebelumnya ---
static datetime lastBoSTimeLogged_H1 = 0;

// Waktu bar terakhir diproses H1
datetime lastBarTime_H1 = 0;
static bool bosBullishJustLogged_H1 = false;



// Waktu terakhir bar HH/LL diproses H1
datetime lastAcceptedLLTime_H1 = 0;
double   lastConfirmedHL_H1      = -1;  // HL valid yang sudah dikunci H1
datetime time_lastConfirmedHL_H1 = 0;   // waktu HL valid H1
datetime timeBoSBullish_H1 = 0;
datetime timeBoSBearish_H1 = 0;

// --- Variabel untuk pelacakan LL sebelum HHAfterBoS ---
static double llBeforeHHAfterBos_H1       = -1;     // LL sebelum HHAfterBoS terkonfirmasi H1
static datetime timeLLBeforeHHAfterBos_H1 = 0;      // Waktu LL sebelum HHAfterBoS terkonfirmasi H1
static bool llBeforeHHAfterBosSaved_H1    = false;  // Flag apakah LL sebelum HHAfterBoS sudah disimpan H1
int    bos_counter_H1                     = 0;      // 0 adalah nilai awal H1

// --- Variabel tambahan untuk pelacakan LL terendah absolut sejak HH terakhir setelah BoS ---
static double lowestLLSinceLastHHAfterBos_H1 = -1;  // LL terendah absolut sejak HH terakhir setelah BoS H1
static datetime time_lastHHAfterBos_H1       = 0;   // Waktu HH terakhir setelah BoS H1

static double hhBeforellAfterBos_H1       = -1;     // HH sebelum LLAfterBoS terkonfirmasi H1
static datetime timehhBeforellAfterBos_H1 = 0;      // Waktu HH sebelum LLAfterBoS terkonfirmasi H1

static datetime time_lastAcceptedLLTime_H1 = 0;  // Last LL bearish yang diterima (valid) H1

// --- Deklarasi global tambahan H1 ---
datetime timeHHAfterBosConfirmed_H1 = 0;  // Inisialisasi dengan 0

double   absoluteLowestLL_H1       = -1;
datetime timeAbsoluteLowestLL_H1   = 0;
bool     absoluteLowFound_H1       = false;
bool     searchCompleted_H1        = false;

double   absoluteHighestHH_H1       = -1;
datetime timeAbsoluteHighestHH_H1   = 0;
bool     absoluteHighFound_H1       = false;
bool     bearishSearchCompleted_H1  = false;

datetime time_choch_bearish_H1 = 0;  // Waktu CHoCH Bearish H1
datetime time_choch_bullish_H1 = 0;  // Waktu CHoCH Bull H1

// Di bagian deklarasi variabel global (di luar fungsi)
string previousLLBoxName_H1 = "";

bool hasEnteredTrade_H1 = false;
datetime lastEntryTime_H1 = 0;

bool hasEnteredSellTrade_H1 = false;
datetime lastSellEntryTime_H1 = 0;
int entryCountBuy_H1 = 0;      // Counter untuk entry BUY H1
int entryCountSell_H1 = 0;     // Counter untuk entry SELL H1

// Parameter input untuk SL dan TP (dioptimalkan untuk H1)
// input int DefaultSL_Buy_H1  = 300;   // Stop Loss untuk Buy Entry 1 (dalam poin) H1
// input int DefaultTP_Buy_H1  = 500;   // Take Profit untuk Buy Entry 1 (dalam poin) H1
// input int DefaultSL_Sell_H1 = 300;   // Stop Loss untuk Sell Entry 1 (dalam poin) H1
// input int DefaultTP_Sell_H1 = 500;   // Take Profit untuk Sell Entry 1 (dalam poin) H1
// //--- Entry 2 parameters H1
// input int Entry2SL_Buy_H1  = 300;    // Stop Loss untuk Buy Entry 2 (dalam poin) H1
// input int Entry2TP_Buy_H1  = 600;    // Take Profit untuk Buy Entry 2 (dalam poin) H1
// input int Entry2SL_Sell_H1 = 300;   // Stop Loss untuk Sell Entry 2 (dalam poin) H1
// input int Entry2TP_Sell_H1 = 600;   // Take Profit untuk Sell Entry 2 (dalam poin) H1
// //--- Entry 3 parameters H1
// input int Entry3SL_Buy_H1  = 350;    // Stop Loss untuk Buy Entry 3 (dalam poin) H1
// input int Entry3TP_Buy_H1  = 800;    // Take Profit untuk Buy Entry 3 (dalam poin) H1
// input int Entry3SL_Sell_H1 = 350;   // Stop Loss untuk Sell Entry 3 (dalam poin) H1
// input int Entry3TP_Sell_H1 = 800;   // Take Profit untuk Sell Entry 3 (dalam poin) H1
// input ulong MagicNumber_H1 = 12346; // Magic number untuk EA H1
// input int MaxEntriesPerCycle_H1 = 3; // Max entries per CHoCH cycle H1

// --- Variabel untuk trailing stop H1 ---
double buyEntryPrice_H1 = 0.0;    // Harga entry posisi buy H1
double sellEntryPrice_H1 = 0.0;   // Harga entry posisi sell H1
bool trailingActivatedBuy_H1 = false; // Flag trailing aktif untuk buy H1
bool trailingActivatedSell_H1 = false; // Flag trailing aktif untuk sell H1

int handleEMA_H4;  // Handle untuk EMA200 di timeframe H4
double ema200_H4;  // Nilai EMA200 di timeframe H4
double lastClose_H4; // Harga close terakhir di H4

bool   g_BackfillMode_M15     = false;  // internal flag (jangan atur manual)
int    g_CopyCountOverride_M15 = 60;    // default sama seperti sebelumnya (dipakai jika diperlukan)
datetime lastWarmupTime_M15   = 0;


struct TradeRecord_H1
{
    ulong     ticket;
    double    entry_price;
    double    sl;
    double    tp;
    datetime  entry_time;
    double    exit_price;
    datetime  exit_time;
    double    profit;
    string    type;
};

TradeRecord_H1 currentBuyTrade_H1;   // Untuk posisi buy aktif H1
TradeRecord_H1 currentSellTrade_H1;  // Untuk posisi sell aktif H1

void ResetMode2_H1()
{
    absoluteLowestLL_H1 = -1;
    timeAbsoluteLowestLL_H1 = 0;
    absoluteLowFound_H1 = false;
    searchCompleted_H1 = false;
}

void ResetMode2Bearish_H1()
{
    absoluteHighestHH_H1 = -1;
    timeAbsoluteHighestHH_H1 = 0;
    absoluteHighFound_H1 = false;
    bearishSearchCompleted_H1 = false;
}

void UpdateAcceptedLevelVisuals_H1(double level, string type, datetime time) 
{
    // Simpan ke history sebelum menggambar visual
    if (level != -1)
    {
        SaveAcceptedLevelToHistory(type, level, time, "H1");
    }
    
    string lineName  = "line_lastAccepted" + type + "_H1";
    string labelName = "label_lastAccepted" + type + "_H1";
    color lineColor  = (type == "HH") ? clrOrange : clrAqua;
    int   labelOffset = (type == "HH") ? 20 : -20;

    ObjectDelete(0, lineName);
    ObjectDelete(0, labelName);

    if (level != -1) {
        ObjectCreate(0, lineName, OBJ_HLINE, 0, 0, level);
        ObjectSetInteger(0, lineName, OBJPROP_COLOR, lineColor);
        ObjectSetInteger(0, lineName, OBJPROP_STYLE, STYLE_DASHDOT);

        ObjectCreate(0, labelName, OBJ_TEXT, 0, time, level + labelOffset * _Point);
        ObjectSetInteger(0, labelName, OBJPROP_COLOR, lineColor);
        ObjectSetInteger(0, labelName, OBJPROP_FONTSIZE, 8);
        ObjectSetString(0, labelName, OBJPROP_TEXT,
                        "lastAccepted" + type + "_H1: " + DoubleToString(level, _Digits));
    }
}


// void GetH1Data()
// {
//     MqlRates h1Rates[];
//     if (CopyRates(_Symbol, PERIOD_H1, 0, 1, h1Rates) == 1)
//     {
//         lastClose_H1 = h1Rates[0].close;
//     }
//     else
//     {
//         Print("❌ Gagal ambil data H1");
//     }

//     double bufferEMA_H1[];
//     if (CopyBuffer(handleEMA_H1, 0, 0, 1, bufferEMA_H1) == 1)
//     {
//         ema200_H1 = bufferEMA_H1[0];
//     }
//     else
//     {
//         Print("❌ Gagal ambil EMA200 H1");
//     }
// }



//------------------------------------------------------------------------------+
//Global variabel M15
//------------------------------------------------------------------------------+

// Parameter input yang bisa diubah user (M15 optimized)
input int WindowSize_M15 = 25;    // Ukuran window untuk deteksi high/low (M15)
input int ZoneLength_M15 = 100;  // Panjang zona yang digambar (M15)
input int MovingPeriod_M15 = 200;  // Periode moving average (M15)
input int MovingShift_M15 = 0;  // Shift moving average (M15)

// --- Assume these variables are declared globally in the original script ---
// --- Variabel high/low ---
double   lastHH_byTime_M15 = -1;  // Last higher high (nilai harga) M15
datetime lastTimeHH_M15    = 0;   // Waktu last HH M15
double   lastLL_byTime_M15 = -1;  // Last lower low (nilai harga) M15
datetime lastTimeLL_M15    = 0;   // Waktu last LL M15
int lastLogHour_M15 = -1;  // Jam terakhir log EMA M15

// --- Variabel konfirmasi ---
static double lastAcceptedHH_M15      = -1;  // Last HH yang diterima (valid) M15
static double lastAcceptedLL_M15      = -1;  // Last LL yang diterima (valid) M15
static double lastAcceptedLL_Bear_M15 = -1;  // Last LL bearish yang diterima (valid) - Unused?

// --- Variabel penolakan ---
static   double lastLoggedDeniedHH_M15          = -1;  // Last HH yang ditolak M15
static   datetime lastLoggedDeniedHHBarTime_M15 = 0;   // Waktu bar HH ditolak M15
static   datetime lastLoggedDeniedHHLogTime_M15 = 0;   // Waktu log penolakan HH M15
static   double lastLoggedDeniedLL_M15          = -1;  // Last LL yang ditolak M15
static   datetime lastLoggedDeniedLLBarTime_M15 = 0;   // Waktu bar LL ditolak M15
static   datetime lastLoggedDeniedLLLogTime_M15 = 0;   // Waktu log penolakan LL M15
datetime lastDeniedBarTime_HH_M15               = 0;   // Waktu bar terakhir HH ditolak - Unused?

// --- Variabel pencegahan spam log HH ---
static double lastLoggedValidHH_M15       = -1;  // Last valid HH yang dilog M15
static datetime lastLoggedValidHHTime_M15 = 0;   // Waktu log valid HH M15
static double lastLoggedValidLL_M15       = -1;  // Last valid LL yang dilog M15
static datetime lastLoggedValidLLTime_M15 = 0;   // Waktu log valid LL M15

// Interval log penolakan
static int deniedLogIntervalSeconds_M15  = 30;  // Interval log penolakan (detik) M15
static datetime lastProcessedTime_HH_M15 = 0;   // Waktu terakhir proses HH M15
static datetime lastProcessedTime_LL_M15 = 0;   // Waktu terakhir proses LL M15

// --- Variabel aktif ---
double activeCHoCH_HH_M15 = -1;  // CHoCH HH aktif - Unused in pure detection? M15
double activeBoS_HH_M15   = -1;  // BoS HH aktif - Unused in pure detection? M15
double activeCHoCH_LL_M15 = -1;  // CHoCH LL aktif - Unused in pure detection? M15
double activeBoS_LL_M15   = -1;  // BoS LL aktif - Unused in pure detection? M15

// --- Variabel post-CHoCH ---
double   postChoCH_HH_M15      = -1;  // HH setelah CHoCH - Unused in pure detection? M15
datetime time_postChoCH_HH_M15 = 0;   // Waktu post-CHoCH HH - Unused in pure detection? M15
double   postChoCH_LL_M15      = -1;  // LL setelah CHoCH - Unused in pure detection? M15
datetime time_postChoCH_LL_M15 = 0;   // Waktu post-CHoCH LL - Unused in pure detection? M15

// --- Variabel BoS ---
double   lastBoS_HH_M15      = -1;  // Last BoS HH - Unused in pure detection? M15
datetime time_lastBoS_HH_M15 = 0;   // Waktu last BoS HH - Unused in pure detection? M15
double   lastBoS_LL_M15      = -1;  // Last BoS LL - Unused in pure detection? M15
datetime time_lastBoS_LL_M15 = 0;   // Waktu last BoS LL - Unused in pure detection? M15

// --- Flags konfirmasi bullish ---
static bool chochBullishConfirmedFlag_M15 = false;  // Flag konfirmasi CHoCH bullish - Influences logic M15
static bool hhAfterChochConfirmedFlag_M15 = false;  // Flag HH setelah CHoCH - Influences logic M15
static bool bosBullishConfirmedFlag_M15   = false;  // Flag konfirmasi BoS bullish - Influences logic M15
static bool hhAfterBosConfirmedFlag_M15   = false;  // Flag HH setelah BoS - Influences logic M15

// --- Flags konfirmasi bearish ---
static bool chochBearishConfirmedFlag_M15 = false;  // Flag konfirmasi CHoCH bearish - Influences logic M15
static bool llAfterChochConfirmedFlag_M15 = false;  // Flag LL setelah CHoCH - Influences logic M15
static bool bosBearishConfirmedFlag_M15   = false;  // Flag konfirmasi BoS bearish - Influences logic M15
static bool llAfterBosConfirmedFlag_M15   = false;  // Flag LL setelah BoS - Influences logic M15

// --- Flags tren ---
bool chochBullish_M15     = false;  // Flag CHoCH bullish - Influences logic M15
bool chochBearish_M15     = false;  // Flag CHoCH bearish - Influences logic M15
bool isInTrendBullish_M15 = false;  // Flag dalam tren bullish - Influences logic M15
bool isInTrendBearish_M15 = false;  // Flag dalam tren bearish - Influences logic M15

// --- Variabel target CHoCH ---
static double targetChoCHBullishHH_M15    = -1;  // Target HH untuk CHoCH bullish - Influences logic M15
static double targetChoCHBearishLL_M15    = -1;  // Target LL untuk CHoCH bearish - Influences logic M15
static double targetChoCHBearishLowLL_M15 = -1;  // Target LL terendah untuk CHoCH bearish - Influences logic M15
static double targetBoSBearishLL_M15      = -1;  // Target LL untuk BoS bearish - Influences logic M15
static double targetBoSBearishLowLL_M15   = -1;  // Target HH untuk BoS bullish - Influences logic M15
double preChochHH_M15                     = -1;  // HH sebelum CHoCH - Influences logic M15
double preChochLL_M15                     = -1;  // LL sebelum CHoCH - Influences logic M15

// --- Variabel lainnya ---
static bool hlAfterHHChochSaved_M15 = false;  // 🔒 Kunci agar MODE 1 hanya aktif 1x - Influences logic M15
static bool isSearchingForNewHL_M15 = false;  // Flag untuk mencari Higher Low baru - Influences logic M15

// --- Variabel untuk pelacakan perubahan flag ---
static string lastLoggedFlagStatusBullish_M15 = "";  // Status bullish flag terakhir yang dilog M15
static string lastLoggedFlagStatusBearish_M15 = "";  // Status bearish flag terakhir yang dilog M15

// --- Penyimpanan status log sebelumnya ---
static datetime lastBoSTimeLogged_M15 = 0;

// Waktu bar terakhir diproses
datetime lastBarTime_M15 = 0;
static bool bosBullishJustLogged_M15 = false;

// Variabel indikator
int handleEMA_M15 = 0;  // Handle untuk EMA M15
double ema200_M15 = 0;  // Nilai EMA200 M15

// Waktu terakhir bar HH/LL diproses
datetime lastAcceptedLLTime_M15 = 0;
double   lastConfirmedHL_M15      = -1;  // HL valid yang sudah dikunci M15
datetime time_lastConfirmedHL_M15 = 0;   // waktu HL valid M15
datetime timeBoSBullish_M15 = 0;
datetime timeBoSBearish_M15 = 0;

// --- Variabel untuk pelacakan LL sebelum HHAfterBoS ---
static double llBeforeHHAfterBos_M15       = -1;     // LL sebelum HHAfterBoS terkonfirmasi M15
static datetime timeLLBeforeHHAfterBos_M15 = 0;      // Waktu LL sebelum HHAfterBoS terkonfirmasi M15
static bool llBeforeHHAfterBosSaved_M15    = false;  // Flag apakah LL sebelum HHAfterBoS sudah disimpan M15
int    bos_counter_M15                     = 0;      // 0 adalah nilai awal M15

// --- Variabel tambahan untuk pelacakan LL terendah absolut sejak HH terakhir setelah BoS ---
static double lowestLLSinceLastHHAfterBos_M15 = -1;  // LL terendah absolut sejak HH terakhir setelah BoS M15
static datetime time_lastHHAfterBos_M15       = 0;   // Waktu HH terakhir setelah BoS M15

static double hhBeforellAfterBos_M15       = -1;     // LL sebelum HHAfterBoS terkonfirmasi M15
static datetime timehhBeforellAfterBos_M15 = 0;      // Waktu LL sebelum HHAfterBoS terkonfirmasi M15

static datetime time_lastAcceptedLLTime_M15 = 0;  // Last LL bearish yang diterima (valid) - Unused? M15
// --- Akhir variabel tambahan ---
// --- Tambahkan deklarasi global di sini ---
datetime timeHHAfterBosConfirmed_M15 = 0;  // Inisialisasi dengan 0 (atau waktu default lainnya) M15

double   absoluteLowestLL_M15       = -1;
datetime timeAbsoluteLowestLL_M15   = 0;
bool     absoluteLowFound_M15       = false;
bool     searchCompleted_M15        = false;
// --- Akhir deklarasi global ---

double   absoluteHighestHH_M15       = -1;
datetime timeAbsoluteHighestHH_M15   = 0;
bool     absoluteHighFound_M15       = false;
bool     bearishSearchCompleted_M15  = false;

datetime time_choch_bearish_M15 = 0;  // Waktu CHoCH Bearish M15
datetime time_choch_bullish_M15 = 0;  // Waktu CHoCH Bull M15

// Di bagian deklarasi variabel global (di luar fungsi)
string previousLLBoxName_M15 = "";

bool hasEnteredTrade_M15 = false;

datetime lastEntryTime_M15 = 0;

bool hasEnteredSellTrade_M15 = false;
datetime lastSellEntryTime_M15 = 0;
int entryCountBuy_M15 = 0;      // Counter untuk entry BUY M15
int entryCountSell_M15 = 0;     // Counter untuk entry SELL M15

int handleEMA_H1;  // Handle untuk EMA200 di timeframe H1
double ema200_H1;  // Nilai EMA200 di timeframe H1
double lastClose_H1; // Harga close terakhir di H1

// ==================== ATR-BASED SL/TP SYSTEM (OPSI 2: HYBRID) ====================
input bool UseATRBasedSLTP_M15 = true;   // 🔄 Enable ATR-based dynamic SL/TP (HYBRID MODE)
input int ATR_Period = 14;               // ATR periode (default: 14)
input double ATRVolatilityHigh = 150.0;  // Threshold ATR untuk "High Volatility" (poin)
input double ATRVolatilityNormal = 80.0; // Threshold ATR untuk "Normal Volatility" (poin)
input double SLMultiplierHigh = 2.0;     // SL multiplier saat volatilitas TINGGI (x ATR)
input double SLMultiplierNormal = 2.5;   // SL multiplier saat volatilitas NORMAL (x ATR)
input double SLMultiplierLow = 3.0;      // SL multiplier saat volatilitas RENDAH (x ATR)
input double TPMultiplierHigh = 3.0;     // TP multiplier saat volatilitas TINGGI (x ATR)
input double TPMultiplierNormal = 3.5;   // TP multiplier saat volatilitas NORMAL (x ATR)
input double TPMultiplierLow = 4.0;      // TP multiplier saat volatilitas RENDAH (x ATR)
input double LLDistanceMultiplier = 0.8; // Multiplier untuk distansi ke LL (untuk conservative SL)
input double HHDistanceMultiplier = 1.2; // Multiplier untuk distansi ke HH (untuk profit target)
// 🔄 HYBRID APPROACH: Minimum values untuk ensure profit tidak terlalu kecil
input double MinimumTP_Points = 2000.0;  // Minimum TP dalam poin (jangan kurang dari ini)
input double MinimumSL_Points = 1500.0;  // Minimum SL dalam poin (jangan kurang dari ini)
// ================================================================================"

// Parameter input untuk SL dan TP M15 (FALLBACK - gunakan jika ATR disabled)
//--- Entry 1 parameters M15
input int DefaultSL_Buy_M15  = 3000;   // Stop Loss untuk Buy Entry 1 (dalam poin) M15 [FALLBACK]
input int DefaultTP_Buy_M15  = 3000;   // Take Profit untuk Buy Entry 1 (dalam poin) M15 [FALLBACK]
input int DefaultSL_Sell_M15 = 3000;   // Stop Loss untuk Sell Entry 1 (dalam poin) M15 [FALLBACK]
input int DefaultTP_Sell_M15 = 3000;   // Take Profit untuk Sell Entry 1 (dalam poin) M15 [FALLBACK]
//--- Entry 2 parameters M15
input int Entry2SL_Buy_M15  = 3000;   // Stop Loss untuk Buy Entry 2 (dalam poin) M15 [FALLBACK]
input int Entry2TP_Buy_M15  = 2500;   // Take Profit untuk Buy Entry 2 (dalam poin) M15 [FALLBACK]
input int Entry2SL_Sell_M15 = 3000;  // Stop Loss untuk Sell Entry 2 (dalam poin) M15 [FALLBACK]
input int Entry2TP_Sell_M15 = 2500;  // Take Profit untuk Sell Entry 2 (dalam poin) M15 [FALLBACK]
//--- Entry 3 parameters M15
input int Entry3SL_Buy_M15  = 3500;   // Stop Loss untuk Buy Entry 3 (dalam poin) M15 [FALLBACK]
input int Entry3TP_Buy_M15  = 3000;   // Take Profit untuk Buy Entry 3 (dalam poin) M15 [FALLBACK]
input int Entry3SL_Sell_M15 = 3500;  // Stop Loss untuk Sell Entry 3 (dalam poin) M15 [FALLBACK]
input int Entry3TP_Sell_M15 = 3000;  // Take Profit untuk Sell Entry 3 (dalam poin) M15 [FALLBACK]
input ulong MagicNumber_M15 = 12345; // Magic number untuk EA M15
input int MaxEntriesPerCycle_M15 = 1; // Max entries per CHoCH cycle M15 // FIX #4: Changed from 3 to 1

// FIX #3: Hold time constraints
input int MinHoldHours_M15 = 4;  // Minimum hold time before allowing TP exit (hours)
input int MaxHoldHours_M15 = 24; // Maximum hold time, force close after this (hours)

//+------------------------------------------------------------------+
//| Capture Current Market Structure State                            |
//+------------------------------------------------------------------+
void CaptureMarketStructureState_M15(MqlRates &ratesM15[], int barIndex)
{
    // Get EMA200 value
    double ema200Value = 0;
    if (iMA(_Symbol, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE) != INVALID_HANDLE)
    {
        double emaBuffer[];
        int emaCopied = CopyBuffer(iMA(_Symbol, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE), 0, barIndex, 1, emaBuffer);
        if (emaCopied > 0) ema200Value = emaBuffer[0];
    }
    
    // Capture current state
    SaveMarketStructureRecord(
        ratesM15[barIndex].time,
        "M15",
        lastAcceptedHH_M15,
        lastAcceptedLL_M15,
        ema200Value,
        chochBullish_M15,
        postChoCH_HH_M15,
        chochBearish_M15,
        postChoCH_LL_M15,
        bosBullishConfirmedFlag_M15,
        postChoCH_HH_M15,
        bosBearishConfirmedFlag_M15,
        postChoCH_LL_M15
    );
}

void CaptureMarketStructureState_H1(MqlRates &ratesH1[], int barIndex)
{
    // Get EMA200 value
    double ema200Value = 0;
    if (iMA(_Symbol, PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE) != INVALID_HANDLE)
    {
        double emaBuffer[];
        int emaCopied = CopyBuffer(iMA(_Symbol, PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE), 0, barIndex, 1, emaBuffer);
        if (emaCopied > 0) ema200Value = emaBuffer[0];
    }
    
    // Capture current state
    SaveMarketStructureRecord(
        ratesH1[barIndex].time,
        "H1",
        lastAcceptedHH_H1,
        lastAcceptedLL_H1,
        ema200Value,
        chochBullish_H1,
        postChoCH_HH_H1,
        chochBearish_H1,
        postChoCH_LL_H1,
        bosBullishConfirmedFlag_H1,
        postChoCH_HH_H1,
        bosBearishConfirmedFlag_H1,
        postChoCH_LL_H1
    );
}

// --- Variabel untuk trailing stop ---
double buyEntryPrice_M15 = 0.0;    // Harga entry posisi buy M15
double sellEntryPrice_M15 = 0.0;   // Harga entry posisi sell M15
bool trailingActivatedBuy_M15 = false; // Flag trailing aktif untuk buy M15
bool trailingActivatedSell_M15 = false; // Flag trailing aktif untuk sell M15

input bool BackfillOnLoad_M15 = true;   // langsung scan & gambar dari history saat attach
input int  WarmupBars_M15     = 500;    // jumlah bar history untuk backfill

input bool BackfillOnLoad_H1 = true;   // langsung scan & gambar dari history saat attach
input int  WarmupBars_H1    = 500;    // jumlah bar history untuk backfill

bool g_BackfillMode_H1 = false; // true saat proses backfill (gambar saja, tanpa entry)



struct TradeRecord_M15
{
    ulong     ticket;
    double    entry_price;
    double    sl;
    double    tp;
    datetime  entry_time;
    double    exit_price;
    datetime  exit_time;
    double    profit;
    string    type;
};

TradeRecord_M15 currentBuyTrade_M15;   // Untuk posisi buy aktif M15
TradeRecord_M15 currentSellTrade_M15;  // Untuk posisi sell aktif M15

//+------------------------------------------------------------------+
//| FUNGSI BARU: Mengelola objek visual lastAcceptedHH dan lastAcceptedLL M15 |
//+------------------------------------------------------------------+
void UpdateAcceptedLevelVisuals_M15(double level, string type, datetime time) 
{
    // Simpan ke history sebelum menggambar visual
    if (level != -1)
    {
        SaveAcceptedLevelToHistory(type, level, time, "M15");
    }
    
    string lineName    = "line_lastAccepted" + type + "_M15";             // Nama objek garis, misal: "line_lastAcceptedHH_M15"
    string labelName   = "label_lastAccepted" + type + "_M15";            // Nama objek label, misal: "label_lastAcceptedHH_M15"
    color  lineColor   = (type == "HH") ? clrBlue : clrMagenta;  // Warna biru untuk HH, Magenta untuk LL
    int    labelOffset = (type == "HH") ? 10 : -10;              // Offset label agar tidak tumpang tindih dengan garis
    
    ObjectDelete(0, lineName); // Hapus garis lama jika ada
    ObjectDelete(0, labelName); // Hapus label lama jika ada
    
    if (level != -1) { // Jika level valid (bukan -1)
        // --- Gambar Garis Horizontal Putus-Putus ---
        ObjectCreate(0, lineName, OBJ_HLINE, 0, 0, level); // Buat objek garis horizontal
        ObjectSetInteger(0, lineName, OBJPROP_COLOR, lineColor); // Set warna
        ObjectSetInteger(0, lineName, OBJPROP_WIDTH, 1); // Set ketebalan
        ObjectSetInteger(0, lineName, OBJPROP_STYLE, STYLE_DASHDOT); // *** SET PUTUS-PUTUS (DOT/LINE) ***
        
        // --- Gambar Label ---
        ObjectCreate(0, labelName, OBJ_TEXT, 0, time, level + labelOffset * _Point); // Buat objek teks
        ObjectSetInteger(0, labelName, OBJPROP_COLOR, lineColor); // Set warna label
        ObjectSetInteger(0, labelName, OBJPROP_FONTSIZE, 8); // Set ukuran font
        ObjectSetString(0, labelName, OBJPROP_TEXT,
                                     "lastAccepted" + type + "_M15: " + DoubleToString(level, _Digits)); // Set teks label
    }
}

//+---------------------------------------------------------------+
//| Fungsi utilitas untuk menggambar garis tren pendek dengan label M15 |
//+---------------------------------------------------------------+
void DrawLineShort_M15(string name, datetime t1, double p1, datetime t2, double p2, color col, string label)
{
    // Buat garis tren
    ObjectCreate(0, name, OBJ_TREND, 0, t1, p1, t2, p2);
    ObjectSetInteger(0, name, OBJPROP_COLOR, col);
    ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
    ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
    ObjectSetInteger(0, name, OBJPROP_BACK, true); // Gambar di latar belakang
    
    // Buat label teks
    string labelName = name + "_label_M15";
    // Hitung posisi label → Geser ke kanan 1 bar dan naik sedikit untuk visibilitas
    datetime labelTime  = t2 + PeriodSeconds(PERIOD_M15);                                                   // Geser ke kanan 1 candle M15
    double   labelPrice = p1 + (label == "CHoCH" || label == "BoS" ? 8 * _Point : -10 * _Point);  // Naikkan/geser sesuai label
    
    ObjectCreate(0, labelName, OBJ_TEXT, 0, labelTime, labelPrice);
    ObjectSetInteger(0, labelName, OBJPROP_COLOR, col);
    ObjectSetInteger(0, labelName, OBJPROP_FONTSIZE, 9);  // Font lebih jelas
    ObjectSetInteger(0, labelName, OBJPROP_CORNER, CORNER_LEFT_UPPER); // Sudut kiri atas
    ObjectSetString(0, labelName, OBJPROP_TEXT, label + "_M15");
}

void ResetMode2_M15()
{
                absoluteLowestLL_M15 = -1; // -1 berarti belum ditemukan
                timeAbsoluteLowestLL_M15 = 0;
                absoluteLowFound_M15 = false; // Flag untuk menandai apakah LL terendah absolut sudah ditemukan
                searchCompleted_M15 = false; // Flag untuk menandai apakah pencarian selesai (setelah menemukan LL > terendah)

}

void ResetMode2Bearish_M15()
{
    absoluteHighestHH_M15      = -1;
    timeAbsoluteHighestHH_M15  = 0;
    absoluteHighFound_M15      = false;
    bearishSearchCompleted_M15 = false;
}


int OnInit()
{
    handleEMA_M15 = iMA(_Symbol, PERIOD_M15, MovingPeriod_M15, MovingShift_M15, MODE_EMA, PRICE_CLOSE);
    if (handleEMA_M15 == INVALID_HANDLE)
    {
        Print("❌ Gagal membuat handle EMA200 untuk M15");
        return INIT_FAILED;
    }

    // Tambahkan ini untuk EMA H1
    handleEMA_H1 = iMA(_Symbol, PERIOD_H1, MovingPeriod_H1, MovingShift_H1, MODE_EMA, PRICE_CLOSE);
    if (handleEMA_H1 == INVALID_HANDLE)
    {
        Print("❌ Gagal membuat handle EMA200 untuk H1");
        return INIT_FAILED;
    }

    ChartIndicatorAdd(0, 0, handleEMA_M15);
    ChartIndicatorAdd(0, 0, handleEMA_H1);

    trade.SetExpertMagicNumber(MagicNumber_M15);
    Print("✅ EMA200 handle berhasil dibuat untuk M15 & H1");
    return INIT_SUCCEEDED;

    // ====== NEW: langsung backfill ======
    if (BackfillOnLoad_M15)
        WarmUp_M15(WarmupBars_M15);

    if (BackfillOnLoad_H1)
        WarmUp_H1(WarmupBars_H1);

    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Fungsi OnDeinit: Dipanggil saat EA dihapus dari chart             |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    PrintFormat("🔄 [DEINIT] EA dihentikan. Reason: %d", reason);
    
    // Export semua data saat EA dihapus/backtest selesai
    ExportAllData();
}

//+------------------------------------------------------------------+
//| Fungsi OnTester: Dipanggil saat backtest selesai di Strategy Tester|
//+------------------------------------------------------------------+
double OnTester()
{
    Print("📊 [TESTER] Backtest selesai. Mengexport data...");
    
    // Export semua data
    ExportAllData();
    
    // Return profit sebagai custom optimization criterion
    double totalProfit = 0;
    for (int i = 0; i < g_TradeCount; i++)
        totalProfit += g_BacktestTrades[i].profit;
    
    PrintFormat("📊 [TESTER] Total Profit: %.2f | Total Trades: %d", totalProfit, g_TradeCount);
    return totalProfit;
}

//+------------------------------------------------------------------+
//| Fungsi trailing stop 3 tahap (REAL-TIME + LOGGING DETAIL) M15    |
//+------------------------------------------------------------------+
void ApplyTrailingStop_M15()
{
    double currentBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double currentAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    for(int i = PositionsTotal()-1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket <= 0) continue;
        // Pastikan posisi milik EA ini
        if(PositionGetInteger(POSITION_MAGIC) != MagicNumber_M15 || 
           PositionGetString(POSITION_SYMBOL) != _Symbol)
            continue;

        double positionOpen = PositionGetDouble(POSITION_PRICE_OPEN);
        double sl = PositionGetDouble(POSITION_SL);
        ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

        if(posType == POSITION_TYPE_BUY)
        {
            double profitPoints = (currentBid - positionOpen) / _Point;
            // 🔍 LOG DETAIL UNTUK BUY TRAILING M15
            PrintFormat("📊 [TRAILING BUY M15] Time=%s | Bid=%.5f | Entry=%.5f | SL=%.5f | TP=%.5f | Profit=%.1f poin | Status: %s",
                        TimeToString(TimeCurrent(), TIME_MINUTES),
                        currentBid,
                        positionOpen,
                        sl,
                        PositionGetDouble(POSITION_TP),
                        profitPoints,
                        !trailingActivatedBuy_M15 ? "Step 0" :
                        trailingActivatedBuy_M15 == 1 ? "Step 1 Aktif" :
                        trailingActivatedBuy_M15 == 2 ? "Step 2 Aktif" : "Step 3 Aktif");

            // --- TAHAP 1: Aktifkan saat profit >= 800 poin ---
            if(profitPoints >= 800 && !trailingActivatedBuy_M15)
            {
                double newSL = positionOpen; // Set SL ke harga entry + 500 poin
                double newTP = positionOpen  + 3000 * _Point;
                PrintFormat("✅ [TRAILING STEP 1 M15] BUY: Profit %.1f poin >= 800 | Akan set SL=%.5f, TP=%.5f",
                            profitPoints, newSL, newTP);
                if(trade.PositionModify(ticket, newSL, newTP))
                {
                    Print("[TRAILING STEP 1 M15] BUY: SL & TP berhasil diatur.");
                    trailingActivatedBuy_M15 = true;
                }
                else
                {
                    Print("❌ [TRAILING STEP 1 M15] Gagal modify posisi BUY: ", GetLastError());
                }
            }
            // --- TAHAP 2: Aktifkan saat profit >= 2500 poin ---
            else if(profitPoints >= 2500 && trailingActivatedBuy_M15 == true && sl <= positionOpen + DefaultSL_Buy_M15 * _Point)
            {
                double newSL = positionOpen +  2000 * _Point;
                double newTP = positionOpen + (DefaultTP_Buy_M15 + 4500) * _Point;
                PrintFormat("✅ [TRAILING STEP 2 M15] BUY: Profit %.1f poin >= 2500 | Akan set SL=%.5f",
                            profitPoints, newSL);
                if(trade.PositionModify(ticket, newSL, newTP))
                {
                    Print("[TRAILING STEP 2 M15] BUY: SL & TP dinaikkan.");
                    trailingActivatedBuy_M15 = 2;
                }
                else
                {
                    Print("❌ [TRAILING STEP 2 M15] Gagal modify posisi BUY: ", GetLastError());
                }
            }
            // --- TAHAP 3: Aktifkan saat profit >= 3000 poin ---
            else if(profitPoints >= 4000 && trailingActivatedBuy_M15 == 2 && sl <= positionOpen + (DefaultSL_Buy_M15 + 500) * _Point)
            {
                double newSL = positionOpen +  3000 * _Point;
                double newTP = positionOpen + 6000 * _Point;
                PrintFormat("✅ [TRAILING STEP 3 M15] BUY: Profit %.1f poin >= 3000 | Akan set SL=%.5f",
                            profitPoints, newSL);
                if(trade.PositionModify(ticket, newSL, newTP))
                {
                    Print("[TRAILING STEP 3 M15] BUY: SL & TP dinaikkan ke level tertinggi.");
                    trailingActivatedBuy_M15 = 3;
                }
                else
                {
                    Print("❌ [TRAILING STEP 3 M15] Gagal modify posisi BUY: ", GetLastError());
                }
            }
        }
        else if(posType == POSITION_TYPE_SELL)
        {
            double profitPoints = (positionOpen - currentAsk) / _Point;
            // 🔍 LOG DETAIL UNTUK SELL TRAILING M15
            PrintFormat("📊 [TRAILING SELL M15] Time=%s | Ask=%.5f | Entry=%.5f | SL=%.5f | TP=%.5f | Profit=%.1f poin | Status: %s",
                        TimeToString(TimeCurrent(), TIME_MINUTES),
                        currentAsk,
                        positionOpen,
                        sl,
                        PositionGetDouble(POSITION_TP),
                        profitPoints,
                        !trailingActivatedSell_M15 ? "Step 0" :
                        trailingActivatedSell_M15 == 1 ? "Step 1 Aktif" :
                        trailingActivatedSell_M15 == 2 ? "Step 2 Aktif" : "Step 3 Aktif");

            // --- TAHAP 1: Aktifkan saat profit >= 800 poin ---
            if(profitPoints >= 800 && !trailingActivatedSell_M15)
            {
                double newSL = positionOpen - 500 * _Point; // Set SL ke harga entry + 500 poin
                double newTP = positionOpen - (DefaultTP_Sell_M15 + 1000) * _Point;
                PrintFormat("✅ [TRAILING STEP 1 M15] SELL: Profit %.1f poin >= 800 | Akan set SL=%.5f, TP=%.5f",
                            profitPoints, newSL, newTP);
                if(trade.PositionModify(ticket, newSL, newTP))
                {
                    Print("[TRAILING STEP 1 M15] SELL: SL & TP berhasil diatur.");
                    trailingActivatedSell_M15 = true;
                }
                else
                {
                    Print("❌ [TRAILING STEP 1 M15] Gagal modify posisi SELL: ", GetLastError());
                }
            }
            // --- TAHAP 2: Aktifkan saat profit >= 1800 poin ---
            else if(profitPoints >= 2000 && trailingActivatedSell_M15 == true && sl >= positionOpen - DefaultSL_Sell_M15 * _Point)
            {
                double newSL = positionOpen - (DefaultSL_Sell_M15 + 1500) * _Point;
                double newTP = positionOpen - (DefaultTP_Sell_M15 + 2500) * _Point;
                PrintFormat("✅ [TRAILING STEP 2 M15] SELL: Profit %.1f poin >= 1800 | Akan set SL=%.5f",
                            profitPoints, newSL);
                if(trade.PositionModify(ticket, newSL, newTP))
                {
                    Print("[TRAILING STEP 2 M15] SELL: SL & TP diturunkan.");
                    trailingActivatedSell_M15 = 2;
                }
                else
                {
                    Print("❌ [TRAILING STEP 2 M15] Gagal modify posisi SELL: ", GetLastError());
                }
            }
            // --- TAHAP 3: Aktifkan saat profit >= 2500 poin ---
            else if(profitPoints >= 2500 && trailingActivatedSell_M15 == 2 && sl >= positionOpen - (DefaultSL_Sell_M15 + 500) * _Point)
            {
                double newSL = positionOpen - (DefaultSL_Sell_M15 + 1000) * _Point;
                double newTP = positionOpen - (DefaultTP_Sell_M15 + 1000) * _Point;
                PrintFormat("✅ [TRAILING STEP 3 M15] SELL: Profit %.1f poin >= 2500 | Akan set SL=%.5f",
                            profitPoints, newSL);
                if(trade.PositionModify(ticket, newSL, newTP))
                {
                    Print("[TRAILING STEP 3 M15] SELL: SL & TP diturunkan lebih jauh.");
                    trailingActivatedSell_M15 = 3;
                }
                else
                {
                    Print("❌ [TRAILING STEP 3 M15] Gagal modify posisi SELL: ", GetLastError());
                }
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Reset trailing flags saat tidak ada posisi M15                   |
//+------------------------------------------------------------------+
void CheckTrailingReset_M15()
{
    static bool lastHasBuyPosition_M15 = true;  // Simpan status sebelumnya M15
    static bool lastHasSellPosition_M15 = true; // Simpan status sebelumnya M15
    
    bool hasBuyPosition_M15 = false;
    bool hasSellPosition_M15 = false;
    
    for(int i = PositionsTotal()-1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket <= 0) continue;
        
        if(PositionGetInteger(POSITION_MAGIC) == MagicNumber_M15 && 
           PositionGetString(POSITION_SYMBOL) == _Symbol)
        {
            if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
                hasBuyPosition_M15 = true;
            else if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL)
                hasSellPosition_M15 = true;
        }
    }
    
    //--- Reset buy flags hanya jika status berubah dari ada menjadi tidak ada ---
    if(lastHasBuyPosition_M15 && !hasBuyPosition_M15) 
    {
        trailingActivatedBuy_M15 = false;
        Print("[TRAILING RESET M15] Buy flags reset");
    }
    
    //--- Reset sell flags hanya jika status berubah dari ada menjadi tidak ada ---
    if(lastHasSellPosition_M15 && !hasSellPosition_M15) 
    {
        trailingActivatedSell_M15 = false;
        Print("[TRAILING RESET M15] Sell flags reset");
    }
    
    //--- Update status terakhir ---
    lastHasBuyPosition_M15 = hasBuyPosition_M15;
    lastHasSellPosition_M15 = hasSellPosition_M15;
}

void CheckTradeClosure_M15(TradeRecord_M15 &tradeRec)
{
    if (tradeRec.ticket == 0) return;
    
    if (!PositionSelectByTicket(tradeRec.ticket))
    {
        double profit = 0;
        double exitPrice = 0;
        datetime exitTime = 0;
        bool found = false;
        
        // Cari di history deal
        HistorySelect(0, TimeCurrent());
        int totalDeals = HistoryDealsTotal();
        for(int i = totalDeals-1; i >= 0; i--)
        {
            ulong dealTicket = HistoryDealGetTicket(i);
            if(HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID) == tradeRec.ticket)
            {
                profit = HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
                exitPrice = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
                exitTime = (datetime)HistoryDealGetInteger(dealTicket, DEAL_TIME);
                found = true;
                break;
            }
        }
        
        if(found)
        {
            PrintFormat("💰 [%s CLOSED M15] Ticket: %I64u | Entry: %.5f | Exit: %.5f | Profit: %.2f | Duration: %s",
                        tradeRec.type,
                        tradeRec.ticket,
                        tradeRec.entry_price,
                        exitPrice,
                        profit,
                        TimeToString(exitTime - tradeRec.entry_time, TIME_MINUTES));
            
            // 💾 Simpan trade ke array untuk export CSV/DB
            double lotSize = 0.01; // Default lot size
            
            // Get current session saat trade entry
            string entrySession = GetCurrentSession();
            
            // Hitung spread cost dan commission dari history deals
            double spreadCost = 0;
            double commission = 0;
            HistorySelect(0, TimeCurrent());
            int totalDeals = HistoryDealsTotal();
            for(int j = totalDeals-1; j >= 0; j--)
            {
                ulong dealTicket = HistoryDealGetTicket(j);
                ENUM_DEAL_ENTRY dealEntry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
                if(HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID) == tradeRec.ticket)
                {
                    if(dealEntry == DEAL_ENTRY_IN)
                    {
                        // Estimasi spread cost untuk entry: ~2.5 pips untuk XAUUSD
                        double spreadPips = 2.5;
                        spreadCost += spreadPips * HistoryDealGetDouble(dealTicket, DEAL_VOLUME) * _Point * 100;
                    }
                    else if(dealEntry == DEAL_ENTRY_OUT)
                    {
                        // Estimasi spread cost untuk exit
                        double spreadPips = 2.5;
                        spreadCost += spreadPips * HistoryDealGetDouble(dealTicket, DEAL_VOLUME) * _Point * 100;
                    }
                    // Akumulasi commission
                    commission += MathAbs(HistoryDealGetDouble(dealTicket, DEAL_COMMISSION));
                }
            }
            
            SaveTradeToArray(tradeRec.ticket, _Symbol, tradeRec.type,
                             tradeRec.entry_price, exitPrice,
                             tradeRec.sl, tradeRec.tp, profit,
                             tradeRec.entry_time, exitTime,
                             lotSize, MagicNumber_M15, "M15",
                             spreadCost, commission, entrySession);
                        
            // Reset trade record
            tradeRec.ticket = 0;
        }
    }
}


//+------------------------------------------------------------------+
//| ENTRY FILTER HELPER FUNCTIONS - Module Level                     |
//+------------------------------------------------------------------+
// Get current H1 EMA200 value
double GetEMA200_H1()
{
    double emaH1 = 0;
    double emaBuffer_H1[];
    if (CopyBuffer(iMA(_Symbol, PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE), 0, 0, 1, emaBuffer_H1) > 0)
        emaH1 = emaBuffer_H1[0];
    return emaH1;
}

// Get current M15 EMA200 trend (True = Trending Up, False = Trending Down)
bool IsEMATrendingUp_M15()
{
    double emaCurrent = 0, emaPrevious = 0;
    double emaBuffer[];
    // Get current bar EMA
    if (CopyBuffer(iMA(_Symbol, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE), 0, 0, 1, emaBuffer) > 0)
        emaCurrent = emaBuffer[0];
    // Get previous bar EMA
    if (CopyBuffer(iMA(_Symbol, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE), 0, 1, 1, emaBuffer) > 0)
        emaPrevious = emaBuffer[0];
    
    bool trendingUp = (emaCurrent > emaPrevious);
    PrintFormat("📈 [EMA SLOPE M15] Current: %.5f vs Previous: %.5f → Trending: %s", 
                emaCurrent, emaPrevious, trendingUp ? "UP" : "DOWN");
    return trendingUp;
}

// Check if H1 is bullish (close > EMA200)
bool IsH1ConfirmedBullish()
{
    double emaH1 = GetEMA200_H1();
    MqlRates h1Rate[];
    ArraySetAsSeries(h1Rate, true);
    if (CopyRates(_Symbol, PERIOD_H1, 0, 1, h1Rate) < 1) return false;
    
    bool bullishConfirmed = (emaH1 > 0 && h1Rate[0].close > emaH1);
    if (!bullishConfirmed)
        PrintFormat("❌ [H1 FILTER REJECT] BUY Entry rejected: H1 Close (%.5f) NOT above H1 EMA200 (%.5f)", 
                    h1Rate[0].close, emaH1);
    return bullishConfirmed;
}

// Check if H1 is bearish (close < EMA200)
bool IsH1ConfirmedBearish()
{
    double emaH1 = GetEMA200_H1();
    MqlRates h1Rate[];
    ArraySetAsSeries(h1Rate, true);
    if (CopyRates(_Symbol, PERIOD_H1, 0, 1, h1Rate) < 1) return false;
    
    bool bearishConfirmed = (emaH1 > 0 && h1Rate[0].close < emaH1);
    if (!bearishConfirmed)
        PrintFormat("❌ [H1 FILTER REJECT] SELL Entry rejected: H1 Close (%.5f) NOT below H1 EMA200 (%.5f)", 
                    h1Rate[0].close, emaH1);
    return bearishConfirmed;
}

// FIX #3: Check if trade has held for minimum time
bool IsTradeHoldingMinimumTime(TradeRecord_M15 &tradeRec)
{
    if (tradeRec.ticket == 0 || tradeRec.entry_time == 0) return false;
    
    int holdHours = (int)((TimeCurrent() - tradeRec.entry_time) / 3600);
    bool canClose = holdHours >= MinHoldHours_M15;
    
    if (!canClose)
        PrintFormat("⏱️ [HOLD TIME] Trade %I64u held for %d hours (minimum required: %d)", 
                    tradeRec.ticket, holdHours, MinHoldHours_M15);
    return canClose;
}

// FIX #3: Force close trade if exceeding maximum hold time
bool ShouldForceCloseTrade(TradeRecord_M15 &tradeRec)
{
    if (tradeRec.ticket == 0 || tradeRec.entry_time == 0) return false;
    
    int holdHours = (int)((TimeCurrent() - tradeRec.entry_time) / 3600);
    bool shouldForceClose = holdHours >= MaxHoldHours_M15;
    
    if (shouldForceClose)
    {
        PrintFormat("⚠️ [FORCE CLOSE] Trade %I64u exceeded max hold time: %d hours >= %d hours max", 
                    tradeRec.ticket, holdHours, MaxHoldHours_M15);
        
        // Force close the position at market
        if (PositionSelectByTicket(tradeRec.ticket))
        {
            trade.PositionClose(tradeRec.ticket);
        }
    }
    return shouldForceClose;
}

//+------------------------------------------------------------------+
//| STRUCT: Untuk return SL/TP dynamic                                |
//+------------------------------------------------------------------+
struct SLTPResult
{
    double sl_points;      // SL dalam poin
    double tp_points;      // TP dalam poin
    double sl_price;       // SL dalam harga
    double tp_price;       // TP dalam harga
    string volatility;     // "HIGH", "NORMAL", "LOW"
    double atr_value;      // Nilai ATR saat itu
};

//+------------------------------------------------------------------+
//| FUNGSI: Hitung ATR M15                                             |
//+------------------------------------------------------------------+
double GetATR_M15(int period = 14)
{
    int atrHandle = iATR(_Symbol, PERIOD_M15, period);
    if (atrHandle == INVALID_HANDLE)
    {
        Print("❌ Gagal membuat handle ATR M15");
        return -1;
    }
    
    double atrBuffer[];
    if (CopyBuffer(atrHandle, 0, 0, 1, atrBuffer) <= 0)
    {
        Print("❌ Gagal copy buffer ATR M15");
        return -1;
    }
    
    // Convert dari harga ke poin
    double atr_points = atrBuffer[0] / _Point;
    
    IndicatorRelease(atrHandle);
    return atr_points;
}

//+------------------------------------------------------------------+
//| FUNGSI: Hitung Dynamic SL/TP berdasarkan ATR + Support/Resistance |
//+------------------------------------------------------------------+
SLTPResult CalculateDynamicSLTP_M15(double entry_price, bool isBuy, 
                                     double lastLL = -1, double lastHH = -1)
{
    SLTPResult result = {0};
    
    // 1. Hitung ATR
    double atr = GetATR_M15(ATR_Period);
    if (atr < 0) atr = 100; // Default fallback jika ATR gagal
    
    result.atr_value = atr;
    
    // 2. Tentukan multiplier berdasarkan volatilitas
    double sl_multiplier = SLMultiplierLow;
    double tp_multiplier = TPMultiplierLow;
    string volatility_level = "LOW";
    
    if (atr > ATRVolatilityHigh)
    {
        sl_multiplier = SLMultiplierHigh;
        tp_multiplier = TPMultiplierHigh;
        volatility_level = "HIGH";
    }
    else if (atr > ATRVolatilityNormal)
    {
        sl_multiplier = SLMultiplierNormal;
        tp_multiplier = TPMultiplierNormal;
        volatility_level = "NORMAL";
    }
    
    result.volatility = volatility_level;
    
    // 3. Hitung SL & TP dari ATR
    double sl_from_atr = sl_multiplier * atr;
    double tp_from_atr = tp_multiplier * atr;
    
    // 4. Hitung SL & TP dari Support/Resistance (jika ada)
    double sl_from_sr = 1000;  // default besar (jauh dari entry)
    double tp_from_sr = 1000;  // default besar (jauh dari entry)
    
    if (isBuy)
    {
        // Untuk BUY: SL dekat LL, TP dekat HH
        if (lastLL > 0)
        {
            double distance_to_ll = (entry_price - lastLL) / _Point;
            sl_from_sr = distance_to_ll * LLDistanceMultiplier;
        }
        if (lastHH > 0)
        {
            double distance_to_hh = (lastHH - entry_price) / _Point;
            tp_from_sr = distance_to_hh * HHDistanceMultiplier;
        }
    }
    else
    {
        // Untuk SELL: SL dekat HH, TP dekat LL
        if (lastHH > 0)
        {
            double distance_to_hh = (lastHH - entry_price) / _Point;
            sl_from_sr = distance_to_hh * HHDistanceMultiplier;
        }
        if (lastLL > 0)
        {
            double distance_to_ll = (entry_price - lastLL) / _Point;
            tp_from_sr = distance_to_ll * LLDistanceMultiplier;
        }
    }
    
    // 5. Gunakan yang LEBIH CONSERVATIVE (besar untuk SL, supaya tidak sering hit)
    result.sl_points = MathMax(sl_from_atr, sl_from_sr);
    result.tp_points = MathMax(tp_from_atr, tp_from_sr);
    
    // 🔄 OPSI 2 HYBRID: Apply minimum TP/SL untuk ensure profit yang cukup besar
    // TP tidak boleh lebih kecil dari minimum, tapi bisa lebih besar jika ATR/SR menghasilkan nilai lebih besar
    result.tp_points = MathMax(result.tp_points, MinimumTP_Points);
    result.sl_points = MathMax(result.sl_points, MinimumSL_Points);
    
    // 6. Convert ke harga
    if (isBuy)
    {
        result.sl_price = entry_price - result.sl_points * _Point;
        result.tp_price = entry_price + result.tp_points * _Point;
    }
    else
    {
        result.sl_price = entry_price + result.sl_points * _Point;
        result.tp_price = entry_price - result.tp_points * _Point;
    }
    
    return result;
}

void DetectAndDraw_M15(MqlRates &rates_M15[], bool backfillMode)
{
    //+----------------------------+
    //--- Loop Deteksi High/Low M15 ---| (Lines ~350-1500)
    //+----------------------------+
    for (int i = ArraySize(rates_M15) - WindowSize_M15 - 1; i >= WindowSize_M15; i--)
    {
        // --- Skip bars if they are within already processed CHoCH/BoS zones M15 ---
        if ((chochBullish_M15 && rates_M15[i].time < time_postChoCH_HH_M15) ||
            (isInTrendBullish_M15 && rates_M15[i].time < time_lastBoS_HH_M15) ||
            (chochBearish_M15 && rates_M15[i].time < time_postChoCH_LL_M15) ||
            (isInTrendBearish_M15 && rates_M15[i].time < time_lastBoS_LL_M15))
        {
            continue;
        }
        
        // --- Check if current bar is a local High or Low within the WindowSize M15 ---
        bool isHigh_M15 = true;
        bool isLow_M15  = true;
        for (int j = i - WindowSize_M15; j <= i + WindowSize_M15; j++)
        {
            if (j == i) continue;
            if (rates_M15[i].high < rates_M15[j].high) isHigh_M15 = false;  // Not highest high in window
            if (rates_M15[i].low > rates_M15[j].low) isLow_M15    = false;  // Not lowest low in window
        }
        //  PrintFormat("🧐 Cek Price M15: Time=%s | Open=%.2f | Close=%.2f | Low=%.2f |",
        //     TimeToString(rates_M15[1].time), rates_M15[1].open, rates_M15[1].close, rates_M15[1].low);
        // --- Process High (HH) M15 ---
        if (isHigh_M15)
        {   
            //----------------------------------------+
            // --- Basic Logging & Spam Prevention M15 ---|
            //----------------------------------------+
            if (rates_M15[i].time <= lastProcessedTime_HH_M15) continue; // Skip if already processed this bar
            lastProcessedTime_HH_M15 = rates_M15[i].time;
            if (rates_M15[i].high == lastLoggedValidHH_M15 && rates_M15[i].time == lastLoggedValidHHTime_M15) continue; // Skip if already logged
            
            PrintFormat("✅ HH VALID TERBENTUK M15     : %.2f | Time: %s", rates_M15[i].high, TimeToString(rates_M15[i].time));
            
            lastLoggedValidHH_M15     = rates_M15[i].high;  // Update spam prevention
            lastLoggedValidHHTime_M15 = rates_M15[i].time;
            
            // --- Visual Drawing (Zona HH) M15 ---
            datetime startTime_M15 = rates_M15[i].time;
            datetime endTime_M15   = startTime_M15 + PeriodSeconds(PERIOD_M15) * ZoneLength_M15;
            string   boxName_M15   = "zone_hh_M15_" + IntegerToString((int)rates_M15[i].time);
            
            ObjectDelete(0, boxName_M15);
            ObjectCreate(0, boxName_M15, OBJ_RECTANGLE, 0, startTime_M15, rates_M15[i].high, endTime_M15, rates_M15[i].high + 3 * _Point);
            ObjectSetInteger(0, boxName_M15, OBJPROP_COLOR, clrRed);
            ObjectSetInteger(0, boxName_M15, OBJPROP_BACK, true);
            
            //---------------------------------------------------------+
            //MODE MENUJU TREND BULLISH M15--------------------------------|
            //Khusus Pembentukan dan Penolakan HH M15----------------------|
            //---------------------------------------------------------+

            //----------------------------------------------------------------------+
            //CHoCH Bullish Confirmed, terbentuk HH valid sebagai target BoS Bullish M15|
            //----------------------------------------------------------------------|
            if (chochBullish_M15 && !isInTrendBullish_M15)
            {
                //------------------------------------------------------------------------------------------------+
                //START: Logika Reset lastAcceptedLL ke preChoch LL setelah CHoCH Bullish dan HH valid (MODE 1) M15 --|
                //------------------------------------------------------------------------------------------------+

                if (!hhAfterChochConfirmedFlag_M15) 
                {
                    lastAcceptedLL_M15            = preChochLL_M15;
                    lastAcceptedHH_M15            = rates_M15[i].high;  
                    UpdateAcceptedLevelVisuals_M15(lastAcceptedLL_M15, "LL", rates_M15[i].time);//Perubahan tadi di komen
                    // PrintFormat("DEBUG M15     : Checking HH After CHoCH Confirmed Flag trigger at HH %.2f @ %s", rates_M15[i].high, TimeToString(rates_M15[i].time));
                    UpdateAcceptedLevelVisuals_M15(lastAcceptedHH_M15, "HH", rates_M15[i].time);
                    // lastAcceptedLL_M15= -1; Perubahan
                    // lastLL_byTime_M15 = -1; Perubahan
                    postChoCH_HH_M15              = rates_M15[i].high;
                    time_postChoCH_HH_M15         = rates_M15[i].time;
                    chochBullishConfirmedFlag_M15 = true;
                    hhAfterChochConfirmedFlag_M15 = true;
                    bosBullishConfirmedFlag_M15   = false;
                    hhAfterBosConfirmedFlag_M15   = false;
                    
                    // SAVE CHoCH DATA
                    SaveLLHHBOSToArray("CHoCH", "Bullish", lastAcceptedHH_M15, rates_M15[i].time, "M15", "Confirmed", preChochLL_M15, 0);
                    SaveLLHHBOSToArray("LL", "Reference", preChochLL_M15, rates_M15[i].time, "M15", "PreChoCH", 0, 0);
                    
                    PrintFormat("✅ HH After ChoCH Confirmed on M15 = %.2f | Time: %s",lastAcceptedHH_M15,TimeToString(rates_M15[i].time));
                    PrintFormat("✅ [MODE 1 RESET M15] CHoCH Bullish dan HH After CHoCH terkonfirmasi. lastAcceptedLL direset ke PreChoCHLL=%.2f | Time: %s",
                            preChochLL_M15, TimeToString(rates_M15[i].time));
                    continue; // Lewati update HH ini
                }

                //------------------------------------------------+
                //Jika HH lebih rendah dari HH CHoCH maka di tolak M15|
                //------------------------------------------------+
                else if (rates_M15[i].high < lastAcceptedHH_M15) 
                {
                    PrintFormat("❌ [MODE 1.1 REJECTED M15] HH %.2f DITOLAK karena < Lebih rendah dari CHoCH+HH last Accepted HH %.2f | Time: %s",
                            rates_M15[i].high, lastAcceptedHH_M15, TimeToString(rates_M15[i].time));
                    if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);
                }
            }

            //----------------------------------------------------------------------+
            //CHoCH Bullish Confirmed, terbentuk HH valid sebagai target BoS Bullish M15|
            //----------------------------------------------------------------------|

            if (chochBullish_M15 && !isInTrendBullish_M15 && !hhAfterChochConfirmedFlag_M15 && rates_M15[i].high > lastAcceptedHH_M15) // <-- PENAMBAHAN KONDISI !hhAfterChochConfirmedFlag_M15
            {
                postChoCH_HH_M15      = rates_M15[i].high; // <-- Sekarang hanya di-set sekali
                time_postChoCH_HH_M15 = rates_M15[i].time; // <-- Sekarang hanya di-set sekali
                PrintFormat("🎯 [TARGET SET M15] BoS Bullish Target HH set ke: %.2f @ %s", postChoCH_HH_M15, TimeToString(time_postChoCH_HH_M15)); // Log tambahan untuk kejelasan
            }

            if (chochBullish_M15 && isInTrendBullish_M15 && rates_M15[i].high > lastAcceptedHH_M15) // <-- PENAMBAHAN KONDISI !hhAfterChochConfirmedFlag_M15
            {
                postChoCH_HH_M15      = rates_M15[i].high; // <-- Sekarang hanya di-set sekali
                time_postChoCH_HH_M15 = rates_M15[i].time; // <-- Sekarang hanya di-set sekali
                PrintFormat("🎯 [TARGET SET M15] BoS Bullish Target HH set ke: %.2f @ %s", postChoCH_HH_M15, TimeToString(time_postChoCH_HH_M15)); // Log tambahan untuk kejelasan
            }
            //------------------------------+
            // End logika target Bos Bullish M15|
            //------------------------------+
            
            //-------------------------------------------------------------+
            // --- START: Logika PEMBARUAN LASTACCEPTEDHH (DIREVISI) Part 2 M15|
            //-------------------------------------------------------------+
            if (bosBullishConfirmedFlag_M15 && isInTrendBullish_M15)
                {
                    //-------------------------------------------------------------------------------+
                    // Dalam tren bullish, hanya HH yang lebih tinggi dari last AcceptedHH yang valid M15|
                    //-------------------------------------------------------------------------------+
                    if (rates_M15[i].high > lastAcceptedHH_M15) // <-- Pembaruan utama dalam tren bullish
                        {
                            lastAcceptedHH_M15 = rates_M15[i].high;
                            PrintFormat("✅ [MODE 1 M15]Update last Accepted HH After Bos: %s | Time: %s", DoubleToString(lastAcceptedHH_M15, _Digits), TimeToString(rates_M15[i].time));
                            UpdateAcceptedLevelVisuals_M15(lastAcceptedHH_M15, "HH", rates_M15[i].time); // Update visual setelah semua kondisi
                            hhAfterBosConfirmedFlag_M15 = true;           // Tandai HH setelah BoS bullish terkonfirmasi
                            timeHHAfterBosConfirmed_M15 = TimeCurrent();  // Simpan waktu konfirmasi
                            postChoCH_HH_M15            = rates_M15[i].high;  // Update postChoCH_HH
                            
                            // PrintFormat("✅ Post CHoCH HH M15: %s | Time: %s", DoubleToString(postChoCH_HH_M15, _Digits), TimeToString(rates_M15[i].time));
                            PrintFormat("✅ HH After BoS Confirmed M15: %s | Time: %s", DoubleToString(lastAcceptedHH_M15, _Digits), TimeToString(rates_M15[i].time));
                            
                            // --- PERBAIKAN: Reset pelacak LL terendah absolut sejak HH terakhir M15 ---
                            // Saat HH baru terkonfirmasi setelah BoS, reset pencarian LL terendah.
                            lowestLLSinceLastHHAfterBos_M15 = -1;             // Atau bisa rates_M15[i].high + 1000*_Point untuk nilai awal yang sangat tinggi
                            time_lastHHAfterBos_M15         = rates_M15[i].time;  // Simpan waktu HH terakhir ini
                            PrintFormat("🔄 [HH After BoS Confirmed M15] Reset pencarian LL terendah. Waktu referensi HH: %s", TimeToString(time_lastHHAfterBos_M15));
                            // --- AKHIR PERBAIKAN ---
                        }
                }        
            else// Kondisi default atau netral (belum ada tren yang jelas)
                {
                    // Lanjutkan mencari Higher High secara default
                    if (rates_M15[i].high > lastAcceptedHH_M15) // <-- Pembaruan utama
                        {
                            lastAcceptedHH_M15 = rates_M15[i].high;
                            PrintFormat("✅ [MODE 1 M15] Update Last Accepted HH (Default): %s | Time: %s", DoubleToString(lastAcceptedHH_M15, _Digits), TimeToString(rates_M15[i].time));
                            UpdateAcceptedLevelVisuals_M15(lastAcceptedHH_M15, "HH", rates_M15[i].time); // Update visual setelah semua kondisi
                        }
                }  

                if (bosBullishConfirmedFlag_M15 && hhAfterBosConfirmedFlag_M15 && rates_M15[i].high < lastAcceptedHH_M15)
                    {
                        PrintFormat("❌ [MODE 2.1 REJECTED M15] HH %.2f DITOLAK karena < Lebih rendah dari BoS + HH %.2f | Time: %s",
                        rates_M15[i].high, lastAcceptedHH_M15, TimeToString(rates_M15[i].time));
                        if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);
                    }

            //----------------------------------------------------------------------+
            //BoS Bullish Confirmed, terbentuk HH valid sebagai target BoS Bullish M15  |
            //----------------------------------------------------------------------+
            if (hhAfterChochConfirmedFlag_M15 && bosBullishConfirmedFlag_M15 && isInTrendBullish_M15 && rates_M15[i].high > lastAcceptedHH_M15)
            {
                postChoCH_HH_M15      = rates_M15[i].high;
                time_postChoCH_HH_M15 = rates_M15[i].time;
                // PrintFormat("✅ BoS Bullish terkonfirmasi M15: postChoCH_HH=%.2f | Time: %s", postChoCH_HH_M15, TimeToString(rates_M15[i].time));
            }

            //-------------------------------------------------------+
            //HH After BoS Confirmed M15---------------------------------|
            //Logika penolakan HH yang lebih rendah dari HH Bos M15      |
            //Penolakan HH Pada saat Trend Bullish M15                   |
            //-------------------------------------------------------+
            if (hhAfterBosConfirmedFlag_M15 && postChoCH_HH_M15 > 0 && rates_M15[i].high < postChoCH_HH_M15)
            {
                if (rates_M15[i].high != lastLoggedDeniedHH_M15 || TimeCurrent() - lastLoggedDeniedHHLogTime_M15 > deniedLogIntervalSeconds_M15)
                {
                    PrintFormat("❌ [REJECTED M15] HH %.2f DITOLAK karena < Lebih rendah dari postCHoCH_HH %.2f | Time: %s",
                            rates_M15[i].high, postChoCH_HH_M15, TimeToString(rates_M15[i].time));
                    if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);
                    lastLoggedDeniedHH_M15        = rates_M15[i].high;
                    lastLoggedDeniedHHBarTime_M15 = rates_M15[i].time;
                    lastLoggedDeniedHHLogTime_M15 = TimeCurrent();
                }
                continue; // Lewati update
            }
            
            //---------------------------------------------------------+
            //END MODE MENUJU TREND BULLISH M15----------------------------|
            //Khusus Pembentukan dan Penolakan HH M15----------------------|
            //---------------------------------------------------------+

            //---------------------------------------------------------+
            //MODE MENUJU TREND BEARISH M15--------------------------------|
            // Penolakan HH M15--------------------------------------------|
            //---------------------------------------------------------+

            //-----------------------------------------------------------------------------------+
            // Setelah CHoCH Bearish, HH baru yang terbentuk SETELAH waktu CHoCH boleh menjadi HH baru M15| "✅"
            //-----------------------------------------------------------------------------------+
            if (chochBearish_M15 && !llAfterChochConfirmedFlag_M15 && !bosBearishConfirmedFlag_M15) 
            {
                // Jika HH ini terbentuk SETELAH CHoCH Bearish timestamp, izinkan update sebagai HH baru
                if (rates_M15[i].time > time_choch_bearish_M15 && rates_M15[i].high > 0 && !hhAfterChochConfirmedFlag_M15)
                {
                    // HH PERTAMA setelah CHoCH Bearish - jadikan sebagai lastAcceptedHH baru untuk tren bearish
                    lastAcceptedHH_M15 = rates_M15[i].high;
                    hhAfterChochConfirmedFlag_M15 = true;
                    PrintFormat("✅ [HH AFTER CHoCH BEARISH M15] HH baru setelah CHoCH Bearish: %.5f | Time: %s",
                                lastAcceptedHH_M15, TimeToString(rates_M15[i].time));
                    UpdateAcceptedLevelVisuals_M15(lastAcceptedHH_M15, "HH", rates_M15[i].time);
                }
                else if (rates_M15[i].high < lastAcceptedHH_M15 && hhAfterChochConfirmedFlag_M15) {
                    // HH yang lebih rendah dari HH setelah CHoCH DITOLAK
                    PrintFormat("❌ [MODE 2 BEARISH M15] HH %.2f DITOLAK karena < HH setelah CHoCH %.2f | Time: %s",
                                rates_M15[i].high, lastAcceptedHH_M15, TimeToString(rates_M15[i].time));
                    if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);
                }
                
                // JANGAN skip jika HH valid setelah CHoCH - hanya skip untuk HH yang ditolak
                if (rates_M15[i].time <= time_choch_bearish_M15 || (rates_M15[i].high < lastAcceptedHH_M15 && hhAfterChochConfirmedFlag_M15))
                    continue; // Lewati update HH ini HANYA jika HH sebelum CHoCH atau lebih rendah dari HH setelah CHoCH
            }

            //-----------------------------------------------------------------------------------------+
            // END: Jika CHoCH Bearish sudah terkonfirmasi, tolak HH yang lebih rendah dari preChoCHHH M15 | "✅"
            //-----------------------------------------------------------------------------------------+


        //     PrintFormat("DEBUG M15: time_postChoCH_LL_M15 = %s, current time = %s", 
        //    TimeToString(time_postChoCH_LL_M15), TimeToString(rates_M15[i].time));

            //-------------------------------------------------------------+
            // Pencarian HH tertinggi absolut setelah CHoCH Bearish dan LL M15 |
            // sebelum BoS Bearish M15                                         |
            //-------------------------------------------------------------+
            if (chochBearish_M15 && llAfterChochConfirmedFlag_M15 && !bosBearishConfirmedFlag_M15 && rates_M15[i].time > time_choch_bearish_M15)
            {
                PrintFormat("🔍 [MODE 2 BEARISH M15 - DEBUG ENTRY] Memasuki MODE 2 Bearish. chochBearish_M15=%s, llAfterChochConfirmedFlag_M15=%s, bosBearishConfirmedFlag_M15=%s",
                            chochBearish_M15 ? "true" : "false",
                            llAfterChochConfirmedFlag_M15 ? "true" : "false",
                            bosBearishConfirmedFlag_M15 ? "true" : "false");
                
                //-----------------------------------------------+
                // Jika belum ada pencarian HH tertinggi absolut M15 |
                // Mulai melakukan pencarian HH tertinggi absolut M15|
                //-----------------------------------------------+
                if (absoluteHighestHH_M15 == -1 || rates_M15[i].high > absoluteHighestHH_M15)
                {
                    Print("🔍 [MODE 2 BEARISH M15 - SEARCHING] Mencari HH tertinggi absolut...");

                    if (!absoluteHighFound_M15)
                    {

                        //-------------------------------+
                        // Inisialisasi dengan HH pertama M15|
                        //-------------------------------+

                        absoluteHighestHH_M15 = rates_M15[i].high;
                        timeAbsoluteHighestHH_M15 = rates_M15[i].time;
                        absoluteHighFound_M15 = true;
                        lastAcceptedHH_M15 = rates_M15[i].high;
                        PrintFormat("🎯 [MODE 2 BEARISH M15 - ABS HIGH INIT] HH Tertinggi Absolut Awal: %.2f | Time: %s", absoluteHighestHH_M15, TimeToString(timeAbsoluteHighestHH_M15));
                        UpdateAcceptedLevelVisuals_M15(lastAcceptedHH_M15, "HH", rates_M15[i].time);

                        //------------------------------------------+
                        //End Pencarian HH tertinggi absolut pertama M15|
                        //------------------------------------------+

                    }
                    else
                    {

                        //---------------------------------------------------------------------------+
                        // Jika sudah ada pencarian, periksa apakah HH baru lebih tinggi dari absolut M15|
                        // Jika ya, update absoluteHighestHH_M15                                         |
                        //---------------------------------------------------------------------------+

                        if (rates_M15[i].high > absoluteHighestHH_M15)
                        {
                            double previousHigh = absoluteHighestHH_M15;
                            absoluteHighestHH_M15 = rates_M15[i].high;
                            timeAbsoluteHighestHH_M15 = rates_M15[i].time;
                            lastAcceptedHH_M15 = rates_M15[i].high;

                            PrintFormat("📈 [MODE 2.1 BEARISH M15 - ABS HIGH UPDATE] HH Tertinggi Absolut Diperbarui: %.2f -> %.2f | Time: %s",
                                        previousHigh, absoluteHighestHH_M15, TimeToString(timeAbsoluteHighestHH_M15));
                            UpdateAcceptedLevelVisuals_M15(lastAcceptedHH_M15, "HH", rates_M15[i].time);
                        }

                        //-------------------------------------------------------------------------------+
                        // Jika HH baru lebih rendah dari absolut HH, tolak dan tandai pencarian selesai M15 |
                        //-------------------------------------------------------------------------------+

                        else if (rates_M15[i].high < absoluteHighestHH_M15)
                        {
                            bearishSearchCompleted_M15 = true;
                            PrintFormat("🏁 [MODE 2 BEARISH M15 - SEARCH COMPLETE] HH tertinggi absolut ditemukan: %.2f. Pencarian dihentikan.", absoluteHighestHH_M15);
                            PrintFormat("🔍 [MODE 2 BEARISH M15 - FOUND LOWER] HH %.2f < HH tertinggi (%.2f) ditemukan. Menolak dan menghentikan pencarian HH tertinggi.",
                                        rates_M15[i].high, absoluteHighestHH_M15);
                            if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);
                        }
                        else
                        {
                            PrintFormat("ℹ️ [MODE 2 BEARISH M15] HH %.2f sama dengan HH Tertinggi Absolut (%.2f) | Time: %s",
                                        rates_M15[i].high, absoluteHighestHH_M15, TimeToString(rates_M15[i].time));
                        }
                    }
                }
                else
                {
                    // Setelah pencarian selesai
                    if (rates_M15[i].high < absoluteHighestHH_M15)
                    {
                        PrintFormat("❌ [MODE 2 BEARISH M15 - POST SEARCH REJECTED] HH %.2f DITOLAK karena < HH Tertinggi Absolut (%.2f) setelah pencarian selesai | Time: %s",
                                    rates_M15[i].high, absoluteHighestHH_M15, TimeToString(rates_M15[i].time));
                        if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);            
                    }
                    else if (rates_M15[i].high > absoluteHighestHH_M15)
                    {
                        PrintFormat("⚠️ [MODE 2 BEARISH M15 - POST SEARCH] HH %.2f > HH Tertinggi Absolut (%.2f) setelah pencarian selesai. | Time: %s",
                                    rates_M15[i].high, absoluteHighestHH_M15, TimeToString(rates_M15[i].time));
                    }
                    else
                    {
                        PrintFormat("ℹ️ [MODE 2 BEARISH M15 - POST SEARCH] HH %.2f sama dengan HH Tertinggi Absolut (%.2f) | Time: %s",
                                    rates_M15[i].high, absoluteHighestHH_M15, TimeToString(rates_M15[i].time));
                    }
                }

                PrintFormat("🔧 [MODE 2 BEARISH STATE M15] absoluteHighestHH_M15=%.2f | bearishSearchCompleted_M15=%s | absoluteHighFound_M15=%s",
                            absoluteHighestHH_M15,
                            bearishSearchCompleted_M15 ? "true" : "false",
                            absoluteHighFound_M15 ? "true" : "false");
            }
            //------------------------------------------------------------------------------------+
            // END Pencarian HH tertinggi absolut setelah CHoCH Bearish dan LL sebelum BoS Bearish M15|
            //------------------------------------------------------------------------------------+

            //----------------------------------------------------------------------------
            //  --- MODE 3 BEARISH: Setelah BoS Bearish + SEBELUM LL After BoS Terkonfirmasi M15 --
            //    Tujuan: Temukan HH tertinggi sebagai target BoS Bearish berikutnya M15
            //----------------------------------------------------------------------------
            if (bosBearishConfirmedFlag_M15 && isInTrendBearish_M15 && !llAfterBosConfirmedFlag_M15)
            {
                // HH yang terbentuk SEBELUM BoS Bearish terpicu
                if (rates_M15[i].time <= timeBoSBearish_M15)
                {
                    double previousHH = lastAcceptedHH_M15;
                    lastAcceptedHH_M15 = rates_M15[i].high;
                    PrintFormat("✅ [MODE 3 M15] Update last Accepted HH sebelum Bos dan paling tinggi (Belum Ada LL After BoS): %.2f < HH_sebelumnya (%.2f) | Time: %s",
                                lastAcceptedHH_M15, previousHH, TimeToString(rates_M15[i].time));
                    UpdateAcceptedLevelVisuals_M15(lastAcceptedHH_M15, "HH", rates_M15[i].time);
                    continue;
                }
                
                // Update lastAcceptedHH_M15 jika HH lebih tinggi
                if (rates_M15[i].high > lastAcceptedHH_M15)
                {
                    double previousHH = lastAcceptedHH_M15;
                    lastAcceptedHH_M15 = rates_M15[i].high;
                    PrintFormat("✅ [MODE 3 M15] Update last Accepted HH After Bos (Belum Ada LL After BoS): %.2f > HH_sebelumnya (%.2f) | Time: %s",
                                lastAcceptedHH_M15, previousHH, TimeToString(rates_M15[i].time));
                    UpdateAcceptedLevelVisuals_M15(lastAcceptedHH_M15, "HH", rates_M15[i].time);
                    
                    // Update target BoS Bearish berikutnya
                    postChoCH_HH_M15 = rates_M15[i].high;
                    time_postChoCH_HH_M15 = rates_M15[i].time;
                    PrintFormat("🎯 [MODE 3 M15] BoS Bearish Target HH set ke: %.2f @ %s", 
                                postChoCH_HH_M15, TimeToString(time_postChoCH_HH_M15));
                }
                else
                {
                    // Tolak HH yang lebih rendah
                    PrintFormat("❌ [MODE 3 BEARISH M15 - REJECTED] HH %.2f DITOLAK karena <= HH terakhir (%.2f) | Time: %s",
                                rates_M15[i].high, lastAcceptedHH_M15, TimeToString(rates_M15[i].time));
                    if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);
                }
                continue;
            }
            //----------------------------------------------------------------------------+
            //  --- MODE 3 BEARISH: Setelah BoS Bearish + LL After BoS Terkonfirmasi M15 ----|
            //    Tujuan: Temukan HH yang lebih rendah (Lower High - LH) untuk konfirmasi M15 |
            //             tren bearish berkelanjutan.                                    |
            //----------------------------------------------------------------------------+
            // Syarat: Bos Bearish sudah terkonfirmasi DAN LL setelah BoS sudah terkonfirmasi.
            if (bosBearishConfirmedFlag_M15 && llAfterBosConfirmedFlag_M15)
            {
                // --- 1. Abaikan HH yang terbentuk SEBELUM BoS Bearish terpicu M15 ---
                if (rates_M15[i].time <= time_postChoCH_LL_M15) // Perubahan <= untuk memastikan inklusif
                {
                    PrintFormat("ℹ️ [MODE 3 BEARISH M15] HH diabaikan (terbentuk sebelum BoS Bearish terpicu @ %s): %.2f @ %s",
                                TimeToString(time_postChoCH_LL_M15), rates_M15[i].high, TimeToString(rates_M15[i].time));
                    string boxNameIgnored_M15 = "zone_hh_M15_" + IntegerToString((int)rates_M15[i].time);
                    if (ObjectFind(0, boxNameIgnored_M15) >= 0) ObjectDelete(0, boxNameIgnored_M15);
                    continue;
                }

                //--------------------------------------------------------------------+
                // --- 2. Lacak HH tertinggi absolut sejak LL terakhir setelah BoS M15 ---|
                //--------------------------------------------------------------------+

                if (rates_M15[i].time > time_lastAcceptedLLTime_M15)  // Asumsikan waktu LL terakhir disimpan di variabel ini
                {
                    if (absoluteHighestHH_M15 == -1 || rates_M15[i].high > absoluteHighestHH_M15)
                    {
                        double previousHH = absoluteHighestHH_M15;
                        absoluteHighestHH_M15 = rates_M15[i].high;
                        timeAbsoluteHighestHH_M15 = rates_M15[i].time;

                        if (previousHH == -1)
                        {
                            PrintFormat("📈 [MODE 3 BEARISH M15] Inisialisasi HH tertinggi sejak LL terakhir (%s): %.2f @ %s",
                                        TimeToString(time_lastAcceptedLLTime_M15), absoluteHighestHH_M15, TimeToString(rates_M15[i].time));
                        }
                        else
                        {
                            PrintFormat("📈 [MODE 3 BEARISH M15] Update HH tertinggi sejak LL terakhir (%s): %.2f -> %.2f @ %s",
                                        TimeToString(time_lastAcceptedLLTime_M15), previousHH, absoluteHighestHH_M15, TimeToString(rates_M15[i].time));
                        }
                    }
                }

                // --- 3. Periksa HH baru terhadap berbagai kriteria M15 ---
                bool   hhRejected_M15   = false;
                string rejectReason_M15 = "";

                //------------------------------------------+
                // 3a. Periksa terhadap HH tertinggi absolut M15|
                // Penolakan HH lebih rendah dari absolut HH M15|
                //------------------------------------------+
                if (absoluteHighestHH_M15 != -1 && rates_M15[i].time > time_lastAcceptedLLTime_M15)
                {
                    if (rates_M15[i].high < absoluteHighestHH_M15)
                    {
                        hhRejected_M15   = true;
                        rejectReason_M15 = "lebih rendah dari HH tertinggi sejak LL terakhir";
                    }
                }

                // 3b. Periksa terhadap LH terakhir (Logika SMC/ICT) M15
                bool isLowerHigh_M15 = false;
                if (rates_M15[i].high < lastAcceptedHH_M15)
                {
                    isLowerHigh_M15 = true;
                }

                // --- 4. Keputusan berdasarkan kriteria M15 ---
                if (hhRejected_M15)
                {
                    PrintFormat("❌ [MODE 3 BEARISH M15 - REJECTED by Abs High] HH %.2f DITOLAK karena %s (%.2f) | Time: %s",
                                rates_M15[i].high, rejectReason_M15, absoluteHighestHH_M15, TimeToString(rates_M15[i].time));
                    string boxNameRejected_M15 = "zone_hh_M15_" + IntegerToString((int)rates_M15[i].time);
                    if (ObjectFind(0, boxNameRejected_M15) >= 0) ObjectDelete(0, boxNameRejected_M15);
                }
                else if (isLowerHigh_M15)
                {
                    double previousHH = lastAcceptedHH_M15;
                    lastAcceptedHH_M15 = rates_M15[i].high;

                    PrintFormat("✅ [MODE 3 BEARISH M15] Init/Update LH After BoS + LL : %.2f < HH_sebelumnya (%.2f) | Time: %s",
                                lastAcceptedHH_M15, previousHH, TimeToString(rates_M15[i].time));

                    // Simpan nilai LH terbaru
                    hhBeforellAfterBos_M15       = lastAcceptedHH_M15;
                    timehhBeforellAfterBos_M15   = rates_M15[i].time;
                    llBeforeHHAfterBosSaved_M15  = true;

                    PrintFormat("💾 [MODE 3 BEARISH M15 - UPDATE] LH %.2f disimpan sebagai referensi baru (hhBeforellAfterBos) | Time: %s",
                                hhBeforellAfterBos_M15, TimeToString(timehhBeforellAfterBos_M15));

                    UpdateAcceptedLevelVisuals_M15(lastAcceptedHH_M15, "HH", rates_M15[i].time);
                }
                else if (rates_M15[i].high > lastAcceptedHH_M15)
                {
                    PrintFormat("❌ [MODE 3 BEARISH M15 - REJECTED by LH] HH %.2f DITOLAK karena lebih tinggi dari LH terakhir (%.2f) | Time: %s",
                                rates_M15[i].high, lastAcceptedHH_M15, TimeToString(rates_M15[i].time));
                    string boxNameRejected_M15 = "zone_hh_M15_" + IntegerToString((int)rates_M15[i].time);
                    if (ObjectFind(0, boxNameRejected_M15) >= 0) ObjectDelete(0, boxNameRejected_M15);
                }
                else // rates_M15[i].high == lastAcceptedHH_M15
                {
                    PrintFormat("ℹ️ [MODE 3 BEARISH M15] HH %.2f sama dengan LH terakhir (%.2f) | Time: %s",
                                rates_M15[i].high, lastAcceptedHH_M15, TimeToString(rates_M15[i].time));
                }

                continue;
            }

        }
        
        // --- Process Low (LL) M15 ---
        if (isLow_M15)
        {
            //----------------------------------------+
            // --- Basic Logging & Spam Prevention M15 ---|
            //----------------------------------------+
            if (rates_M15[i].time <= lastProcessedTime_LL_M15) continue; // Skip if already processed this bar
            lastProcessedTime_LL_M15 = rates_M15[i].time;
            if (rates_M15[i].low == lastLoggedValidLL_M15 && rates_M15[i].time == lastLoggedValidLLTime_M15) continue; // Skip if already logged
            
            PrintFormat("✅ LL VALID TERBENTUK M15: %.2f | Time : %s", rates_M15[i].low, TimeToString(rates_M15[i].time));
            
            lastLoggedValidLL_M15     = rates_M15[i].low;   // Update spam prevention
            lastLoggedValidLLTime_M15 = rates_M15[i].time;
            
            // --- Visual Drawing (Zona LL) M15 ---
            datetime startTime_M15 = rates_M15[i].time;
            datetime endTime_M15   = startTime_M15 + PeriodSeconds(PERIOD_M15) * ZoneLength_M15;
            string   boxName_M15   = "zone_ll_M15_" + IntegerToString((int)rates_M15[i].time);
            
            ObjectCreate(0, boxName_M15, OBJ_RECTANGLE, 0, startTime_M15, rates_M15[i].low - 3 * _Point, endTime_M15, rates_M15[i].low);
            ObjectSetInteger(0, boxName_M15, OBJPROP_COLOR, clrGreen);
            ObjectSetInteger(0, boxName_M15, OBJPROP_BACK, true);
            
            //----------------------------------------------------------------------+
            // ⚠️ [NO MAN'S LAND REJECTION] Tolak LL saat menunggu HH setelah BoS M15 |
            // Syarat: BoS Bullish sudah terkonfirmasi TETAPI HH After BoS BELUM      |
            // NAMUN: Terima LL yang terbentuk SEBELUM BoS dikonfirmasi (valid swing) |
            //----------------------------------------------------------------------+
            if (bosBullishConfirmedFlag_M15 && !hhAfterBosConfirmedFlag_M15 && rates_M15[i].time > timeBoSBullish_M15)
            {
                PrintFormat("❌ [WAITING FOR HH M15 - REJECTED] LL %.2f DITOLAK karena terbentuk SETELAH BoS dikonfirmasi dalam fase 'Waiting for HH' | Time: %s | Status: bosBullish=true, hhAfterBos=false, LL time > BoS time",
                            rates_M15[i].low, TimeToString(rates_M15[i].time));
                if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);
                continue; // Skip pemrosesan lebih lanjut untuk LL ini
            }
            
            //---------------------------------------------------------+
            //MODE MENUJU TREND BEARISH M15--------------------------------|
            //---------------------------------------------------------+

            //-------------------------------------------------------+
            //LOGIKA PEMBENTUKAN LL TERENDAH AFTER CHoCH BEARISH M15 ----|
            //-------------------------------------------------------+
            if (chochBearish_M15 && !isInTrendBearish_M15)
                {
                    //--------------------------------------------------------------------------------------+
                    // --- START: Logika Reset lastAcceptedLL setelah CHoCH Bearish dan LL valid (MODE 1) M15 --|
                    //--------------------------------------------------------------------------------------|
                    if (!llAfterChochConfirmedFlag_M15) 
                        {
                            // lastAcceptedHH_M15 = preChochHH_M15;
                            lastAcceptedLL_M15 = rates_M15[i].low;  // last AcceptedLL direset ke LL sebelum CHoCH Bullish
                            UpdateAcceptedLevelVisuals_M15(lastAcceptedHH_M15, "HH", rates_M15[i].time);//Perubahan tadi di komen
                            // PrintFormat("DEBUG M15     : Checking HH After CHoCH Confirmed Flag trigger at HH %.2f @ %s", rates_M15[i].high, TimeToString(rates_M15[i].time));
                            UpdateAcceptedLevelVisuals_M15(lastAcceptedLL_M15, "LL", rates_M15[i].time);
                            UpdateAcceptedLevelVisuals_M15(lastAcceptedHH_M15, "HH", rates_M15[i].time); // Update visual setelah semua kondisi
                            
                            // lastAcceptedLL_M15= -1; Perubahan
                            // lastLL_byTime_M15 = -1; Perubahan
                            postChoCH_LL_M15              = rates_M15[i].low; // LL terakhir setelah CHoCH Bearish
                            time_postChoCH_LL_M15         = rates_M15[i].time;
                            chochBearishConfirmedFlag_M15 = true;
                            llAfterChochConfirmedFlag_M15 = true;
                            bosBearishConfirmedFlag_M15   = false;
                            llAfterBosConfirmedFlag_M15   = false;
                            
                            // SAVE CHoCH DATA
                            SaveLLHHBOSToArray("CHoCH", "Bearish", lastAcceptedLL_M15, rates_M15[i].time, "M15", "Confirmed", preChochHH_M15, 0);
                            SaveLLHHBOSToArray("HH", "Reference", preChochHH_M15, rates_M15[i].time, "M15", "PreChoCH", 0, 0);
                            
                            PrintFormat("✅ [MODE 1 RESET M15] CHoCH Bearish dan LL After CHoCH terkonfirmasi. last Accepted HH direset ke Pre ChoCH HH=%.2f | HH Baru=%.2f @ %s", 
                            preChochHH_M15, rates_M15[i].high, TimeToString(rates_M15[i].time));
                            //--- Buat nama objek dan simpan untuk referensi berikutnya ---
                            previousLLBoxName_M15 = "zone_ll_M15_" + IntegerToString((int)rates_M15[i].time);

                            continue; // Lewati update HH ini
                        }
                    else if (rates_M15[i].low < lastAcceptedLL_M15) 
                        {
                            lastAcceptedLL_M15 = rates_M15[i].low; // Update lastAcceptedLL jika lebih rendah
                            PrintFormat("✅ [MODE 1.2 M15] Update Last Accepted LL Lebih Rendah: %.2f | Time: %s",
                                    lastAcceptedLL_M15, TimeToString(rates_M15[i].time));
                            // 🔥 HAPUS OBJEK RECTANGLE LL SEBELUMNYA ---
                            if (ObjectFind(0, previousLLBoxName_M15) >= 0)
                                ObjectDelete(0, previousLLBoxName_M15);

                            UpdateAcceptedLevelVisuals_M15(lastAcceptedLL_M15, "LL", rates_M15[i].time); // Update visual setelah semua kondisi
                        }
                    else if (rates_M15[i].low > lastAcceptedLL_M15) 
                        {
                            PrintFormat("❌ [REJECTED M15] LL %.2f DITOLAK karena > Lebih Tinggi dari CHoCH+LL last Accepted LL %.2f | Time: %s",
                                    rates_M15[i].low, lastAcceptedLL_M15, TimeToString(rates_M15[i].time));
                            if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);
                        }
                }

            if (chochBullish_M15 && !isInTrendBullish_M15 && !hhAfterChochConfirmedFlag_M15)
                {
                    if (rates_M15[i].low > preChochLL_M15)
                    {
                        PrintFormat("❌ [REJECTED M15] LL %.2f > preChochLL %.2f | Time: %s",
                                    rates_M15[i].low, preChochLL_M15, TimeToString(rates_M15[i].time));
                        ObjectDelete(0, boxName_M15);
                        continue;
                    }
                }

            //-----------------------------------------------------------+
            //  End Logika Penolakan LL dan Update LL pada ChoCh Bearish M15 |
            //-----------------------------------------------------------+

            //----------------------------------------------------------------------+
            //CHoCH Bearish Confirmed, terbentuk LL valid sebagai target BoS Bullish M15|
            //----------------------------------------------------------------------|

            // if (chochBearish_M15 && !isInTrendBearish_M15 && !llAfterChochConfirmedFlag_M15) // <-- PENAMBAHAN KONDISI !hhAfterChochConfirmedFlag_M15
            // {
            //     postChoCH_LL_M15      = rates_M15[i].low; // <-- Sekarang hanya di-set sekali
            //     time_postChoCH_LL_M15 = rates_M15[i].time; // <-- Sekarang hanya di-set sekali
            //     PrintFormat("🎯 [TARGET SET M15] BoS Bearish Target LL set ke: %.2f @ %s", postChoCH_LL_M15, TimeToString(time_postChoCH_LL_M15)); // Log tambahan untuk kejelasan
            // }
            // else if (rates_M15[i].low < postChoCH_LL_M15 && postChoCH_LL_M15 > 0)
            // {
            //     postChoCH_LL_M15      = rates_M15[i].low; // <-- Sekarang hanya di-set sekali
            //     time_postChoCH_LL_M15 = rates_M15[i].time; // <-- Sekarang hanya di-set sekali
            //     PrintFormat("🎯 [TARGET SET M15] BoS Bearish Target LL Lebih Rendah set ke: %.2f @ %s", postChoCH_LL_M15, TimeToString(time_postChoCH_LL_M15)); // Log tambahan untuk kejelasan
            // }
            
            if (chochBearish_M15 && !isInTrendBearish_M15 && !llAfterChochConfirmedFlag_M15 && rates_M15[i].low < lastAcceptedLL_M15) // <-- PENAMBAHAN KONDISI !hhAfterChochConfirmedFlag_M15
            {
                postChoCH_LL_M15      = rates_M15[i].low; // <-- Sekarang hanya di-set sekali
                time_postChoCH_LL_M15 = rates_M15[i].time; // <-- Sekarang hanya di-set sekali
                PrintFormat("🎯 [TARGET SET M15] BoS Bearish Target LL set ke: %.2f @ %s", postChoCH_LL_M15, TimeToString(time_postChoCH_LL_M15)); // Log tambahan untuk kejelasan
            } 

            if (chochBearish_M15 && isInTrendBearish_M15 && rates_M15[i].low < lastAcceptedLL_M15) // <-- PENAMBAHAN KONDISI !hhAfterChochConfirmedFlag_M15
            {
                postChoCH_LL_M15      = rates_M15[i].low; // <-- Sekarang hanya di-set sekali
                time_postChoCH_LL_M15 = rates_M15[i].time; // <-- Sekarang hanya di-set sekali
                PrintFormat("🎯 [TARGET SET M15] BoS Bearish Target LL set ke: %.2f @ %s", postChoCH_LL_M15, TimeToString(time_postChoCH_LL_M15)); // Log tambahan untuk kejelasan
            }

            //-----------------------------+
            //End Logika Target Bos Bearish M15|
            //-----------------------------+

            //----------------------------------------------------------------------+
            //Bos Bearish Confirmed, terbentuk LL valid sebagai target BoS Bearish M15|
            //----------------------------------------------------------------------+
            if (bosBearishConfirmedFlag_M15 && isInTrendBearish_M15)
            {
                //-------------------------------------------------------------------------------+
                // Dalam tren bearish, hanya LL yang lebih rendah setelah Bos valid M15|
                //-------------------------------------------------------------------------------+
                if (rates_M15[i].low < lastAcceptedLL_M15) // <-- Pembaruan utama dalam tren bullish
                {
                    lastAcceptedLL_M15 = rates_M15[i].low;
                    PrintFormat("✅ [MODE 2.2 M15]Update last Accepted LL After Bos: %s | Time: %s", DoubleToString(lastAcceptedLL_M15, _Digits), TimeToString(rates_M15[i].time));
                    UpdateAcceptedLevelVisuals_M15(lastAcceptedLL_M15, "LL", rates_M15[i].time); // Update visual setelah semua kondisi
                    llAfterBosConfirmedFlag_M15 = true;          // Tandai HH setelah BoS bullish terkonfirmasi
                    //timeLLAfterBosConfirmed_M15 = TimeCurrent(); // Simpan waktu konfirmasi
                    postChoCH_LL_M15            = rates_M15[i].low;  // Update postChoCH_HH
                    PrintFormat("✅ Post CHoCH LL M15: %s | Time: %s", DoubleToString(postChoCH_LL_M15, _Digits), TimeToString(rates_M15[i].time));
                    PrintFormat("✅ LL After BoS Confirmed M15: %s | Time: %s", DoubleToString(lastAcceptedLL_M15, _Digits), TimeToString(rates_M15[i].time));
                    //highestLLSinceLastHHAfterBos_M15 = -1; // Reset LL tertinggi sejak HH terakhir setelah BoS
                    //time_lastLLAfterBos_M15 = rates_M15[i].time; // Simpan waktu LL terakhir setelah BoS
                    //PrintFormat("🔄 [LL After BoS Confirmed M15] Reset pencarian HH tertinggi. Waktu referensi LL: %s",
                    //        TimeToString(time_lastLLAfterBos_M15));
                }
                else if (rates_M15[i].low < lastAcceptedLL_M15) 
                {
                    lastAcceptedLL_M15 = rates_M15[i].low; // Update lastAcceptedLL jika lebih rendah
                    PrintFormat("✅ [MODE 1.2 M15] Update Last Accepted LL Lebih Rendah: %.2f | Time: %s",
                            lastAcceptedLL_M15, TimeToString(rates_M15[i].time));
                    // 🔥 HAPUS OBJEK RECTANGLE LL SEBELUMNYA ---
                    if (ObjectFind(0, previousLLBoxName_M15) >= 0)
                        ObjectDelete(0, previousLLBoxName_M15);

                    UpdateAcceptedLevelVisuals_M15(lastAcceptedLL_M15, "LL", rates_M15[i].time); // Update visual setelah semua kondisi
                }
                else if (rates_M15[i].low > lastAcceptedLL_M15) 
                {
                    PrintFormat("❌ [REJECTED M15] LL %.2f DITOLAK karena > Lebih Tinggi dari BoS+LL last Accepted LL %.2f | Time: %s",
                            rates_M15[i].low, lastAcceptedLL_M15, TimeToString(rates_M15[i].time));
                    if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);
                }
            }  

            //----------------------------------------------------------------------+
            //END MODE MENUJU TREND BEARISH M15-----------------------------------------|
            //----------------------------------------------------------------------+

            //----------------------------------------------------------------------+
            //MODE MENUJU TREND BULLISH M15---------------------------------------------|
            //----------------------------------------------------------------------+
            //----------------------------------------------------------------------------+
            // --- Jika BELUM terjadi CHoCH Bullish + HH, cari LL terendah (pre-CHoCH) M15 ---|
            // Dan Penolakan LL jika lebih tinggi dari lastAcceptedLL (pre-CHoCH) M15 --------|
            //----------------------------------------------------------------------------+
            if (!hhAfterChochConfirmedFlag_M15 && !chochBullish_M15 && !llAfterChochConfirmedFlag_M15 && !chochBearish_M15) 
            {
                if (lastAcceptedLL_M15 == -1 || rates_M15[i].low < lastAcceptedLL_M15) 
                {
                    // ✅ Update LL jika lebih rendah
                    lastAcceptedLL_M15 = rates_M15[i].low;
                    Print("✅ [MODE 1 M15] Update LL (Pre-CHoCH): ", lastAcceptedLL_M15);
                    UpdateAcceptedLevelVisuals_M15(lastAcceptedLL_M15, "LL", rates_M15[i].time);
                }
            //---------------------------------------------------------------+
            // Sebelum Choch Bearish dan HH After CHoCH M15----------------------+
            // Penolakan LL jika lebih tinggi dari lastAcceptedLL (pre-CHoCH) M15|
            //---------------------------------------------------------------+
                else
                {
                    // ❌ Tolak LL yang lebih tinggi
                    Print("❌ [MODE 1 REJECTED M15] LL lebih tinggi dari PreChoCh LL: = ", lastAcceptedLL_M15);
                    if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);
                    lastLoggedDeniedLL_M15 = rates_M15[i].low;
                }
                continue; // Stop proses di baris ini
            }
            //----------------------------------------------------------------------+
            // Jika sudah ada CHoCH Bullish M15 ----------------------------------------+ 
            // Penolakan LL yang lebih tinggi dari lastAcceptedLL (pre-CHoCH) M15-------|
            //----------------------------------------------------------------------+
            if (!hhAfterChochConfirmedFlag_M15 && chochBullish_M15 && !llAfterChochConfirmedFlag_M15 && !chochBearish_M15) 
            {
                if (lastAcceptedLL_M15 == -1 || rates_M15[i].low < lastAcceptedLL_M15) 
                {
                    // ❌ Tolak LL yang lebih tinggi
                    Print("❌ [MODE 1 REJECTED M15] LL lebih tinggi dari PreChoCh LL: = ", lastAcceptedLL_M15);
                    if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);
                    lastLoggedDeniedLL_M15 = rates_M15[i].low;
                }
                continue; // Stop proses di baris ini
            }

            // if (chochBullish_M15 && hhAfterChochConfirmedFlag_M15 && bosBullishConfirmedFlag_M15)
            // {
            //     // Jika sudah ada CHoCH Bullish dan HH After CHoCH, tolak LL yang lebih tinggi dari lastAcceptedLL
            //     if (rates_M15[i].low > lastAcceptedLL_M15) 
            //     {
            //         PrintFormat("❌ [REJECTED M15] LL %.2f DITOLAK karena > Lebih Tinggi dari CHoCH+LL last Accepted LL %.2f | Time: %s",
            //                 rates_M15[i].low, lastAcceptedLL_M15, TimeToString(rates_M15[i].time));
            //         if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);
            //         continue; // Stop proses di baris ini
            //     }
            // }

            //-------------------------------------------------------------+
            // Setelah CHoCH dan HH, cari LL terendah sebelum BoS Bullish M15  |
            //-------------------------------------------------------------+
            if ((chochBullish_M15 || hhAfterChochConfirmedFlag_M15) && 
    (!bosBullishConfirmedFlag_M15 || rates_M15[i].time < timeBoSBullish_M15)) // Tambahkan !bosBullishConfirmedFlag_M15
            {
                PrintFormat("🔍 [MODE 2 M15 - DEBUG ENTRY] Memasuki MODE 2. chochBullish_M15=%s, hhAfterChochConfirmedFlag_M15=%s, bosBullishConfirmedFlag_M15=%s",
                            chochBullish_M15 ? "true" : "false",
                            hhAfterChochConfirmedFlag_M15 ? "true" : "false",
                            bosBullishConfirmedFlag_M15 ? "true" : "false");
                //--- Reset pencarian jika kondisi awal berubah (opsional, untuk keamanan) ---
                // Biasanya static variables akan reset otomatis jika blok ini tidak dijalankan,
                // tapi bisa ditambahkan reset manual jika diperlukan.

                //--- Fase Pencarian LL Terendah Absolut M15 ---
                if (!searchCompleted_M15)
                {
                    PrintFormat("🔍 [MODE 2 M15 - SEARCHING] Mencari LL terendah absolut...");

                    if (!absoluteLowFound_M15)
                    {
                        //--- Inisialisasi dengan LL pertama M15 ---
                        absoluteLowestLL_M15 = rates_M15[i].low;
                        timeAbsoluteLowestLL_M15 = rates_M15[i].time;
                        absoluteLowFound_M15 = true;
                        lastAcceptedLL_M15 = rates_M15[i].low; // Update lastAcceptedLL awal
                        //--- Buat nama objek dan simpan untuk referensi berikutnya ---
                            previousLLBoxName_M15 = "zone_ll_M15_" + IntegerToString((int)rates_M15[i].time);

                        PrintFormat("🎯 [MODE 2 M15 - ABS LOW INIT] LL Terendah Absolut Awal: %.2f | Time: %s", absoluteLowestLL_M15, TimeToString(timeAbsoluteLowestLL_M15));
                        UpdateAcceptedLevelVisuals_M15(lastAcceptedLL_M15, "LL", rates_M15[i].time);
                    }
                    else
                    {
                        //--- Perbarui jika menemukan LL lebih rendah M15 ---
                        if (rates_M15[i].low < absoluteLowestLL_M15)
                        {
                            // 🔥 HAPUS OBJEK RECTANGLE LL SEBELUMNYA ---
                            if (ObjectFind(0, previousLLBoxName_M15) >= 0)
                                ObjectDelete(0, previousLLBoxName_M15);

                            double previousLow = absoluteLowestLL_M15;
                            absoluteLowestLL_M15 = rates_M15[i].low;
                            timeAbsoluteLowestLL_M15 = rates_M15[i].time;
                            lastAcceptedLL_M15 = rates_M15[i].low; // Update lastAcceptedLL

                            PrintFormat("📉 [MODE 2.1 M15 - ABS LOW UPDATE] LL Terendah Absolut Diperbarui: %.2f -> %.2f | Time: %s",
                                        previousLow, absoluteLowestLL_M15, TimeToString(timeAbsoluteLowestLL_M15));
                            UpdateAcceptedLevelVisuals_M15(lastAcceptedLL_M15, "LL", rates_M15[i].time);
                        }
                        //--- Jika menemukan LL lebih tinggi dari terendah, hentikan pencarian M15 ---
                        else if (rates_M15[i].low > absoluteLowestLL_M15)
                        {
                             // LL yang lebih tinggi ditemukan setelah LL terendah.
                             // Hentikan pencarian untuk LL terendah.
                             searchCompleted_M15 = true;
                             // lastAcceptedLL_M15 tetap pada nilai terendah absolut.
                             PrintFormat("🏁 [MODE 2 M15 - SEARCH COMPLETE] LL terendah absolut ditemukan: %.2f. Pencarian dihentikan.", absoluteLowestLL_M15);
                             PrintFormat("🔍 [MODE 2 M15 - FOUND HIGHER] LL %.2f > LL terendah (%.2f) ditemukan. Menolak dan menghentikan pencarian LL terendah.", rates_M15[i].low, absoluteLowestLL_M15);
                             // Tidak perlu mengupdate lastAcceptedLL_M15 lagi di sini karena sudah diset ke nilai terendah.
                             // Bisa juga memilih untuk mengupdate lastAcceptedLL_M15 ke nilai ini jika diinginkan sebagai HL awal,
                             // tapi berdasarkan deskripsi, nampaknya lastAcceptedLL_M15 tetap pada nilai terendah absolut.
                             // Untuk sekarang, kita tolak LL ini.
                             string boxNameRejected_M15 = "zone_ll_M15_" + IntegerToString((int)rates_M15[i].time);
                             if (ObjectFind(0, boxNameRejected_M15) >= 0) ObjectDelete(0, boxNameRejected_M15);
                        }
                        else // rates_M15[i].low == absoluteLowestLL_M15
                        {
                             PrintFormat("ℹ️ [MODE 2 M15] LL %.2f sama dengan LL Terendah Absolut (%.2f) | Time: %s",
                                         rates_M15[i].low, absoluteLowestLL_M15, TimeToString(rates_M15[i].time));
                             // Bisa diputuskan apakah dianggap sebagai pembaruan atau tidak.
                             // Untuk konsistensi, biarkan saja.
                        }
                    }
                }
                else
                {
                    //--- Fase Setelah Pencarian Selesai M15 ---
                    // Pencarian LL terendah absolut sudah dihentikan karena ditemukan LL lebih tinggi.
                    // Semua LL baru yang muncul di sini harus dibandingkan dengan LL terendah absolut.
                    // Namun, deskripsi Anda tidak jelas apakah LL ini diterima sebagai HL berikutnya atau ditolak.
                    // Untuk sekarang, kita asumsikan LL baru yang lebih tinggi dari absolutLowestLL_M15
                    // ditolak dalam konteks mencari LL terendah, atau diterima sebagai HL potensial (tergantung logika MODE 3 nantinya).
                    // Untuk memenuhi permintaan "TOLAK", kita tolak.
                    if (rates_M15[i].low > absoluteLowestLL_M15)
                    {
                         PrintFormat("❌ [MODE 2 M15 - POST SEARCH REJECTED] LL %.2f DITOLAK karena > LL Terendah Absolut (%.2f) setelah pencarian selesai | Time: %s",
                                     rates_M15[i].low, absoluteLowestLL_M15, TimeToString(rates_M15[i].time));
                         string boxNameRejected_M15 = "zone_ll_M15_" + IntegerToString((int)rates_M15[i].time);
                         if (ObjectFind(0, boxNameRejected_M15) >= 0) ObjectDelete(0, boxNameRejected_M15);
                    }
                    else if (rates_M15[i].low < absoluteLowestLL_M15)
                    {
                        // Ini seharusnya tidak terjadi jika logika di atas benar, karena absoluteLowestLL_M15 adalah yang terendah.
                        // Tapi jika terjadi (misal karena market data baru), mungkin perlu dipertimbangkan.
                        // Untuk sekarang, abaikan atau log.
                         PrintFormat("⚠️ [MODE 2 M15 - POST SEARCH] LL %.2f < LL Terendah Absolut (%.2f) setelah pencarian selesai. Kemungkinan data baru atau error. | Time: %s",
                                     rates_M15[i].low, absoluteLowestLL_M15, TimeToString(rates_M15[i].time));
                    }
                    else // rates_M15[i].low == absoluteLowestLL_M15
                    {
                         PrintFormat("ℹ️ [MODE 2 M15 - POST SEARCH] LL %.2f sama dengan LL Terendah Absolut (%.2f) | Time: %s",
                                     rates_M15[i].low, absoluteLowestLL_M15, TimeToString(rates_M15[i].time));
                    }
                }
            PrintFormat("🔧 [MODE 2 STATE M15] absoluteLowestLL_M15=%.2f | searchCompleted_M15=%s | absoluteLowFound_M15=%s",
                        absoluteLowestLL_M15,
                        searchCompleted_M15 ? "true" : "false",
                        absoluteLowFound_M15 ? "true" : "false"
                       );
                
            }
            // Jika hhAfterChochConfirmedFlag_M15=false atau bosBullishConfirmedFlag_M15=true, blok ini tidak dijalankan.
            // Ini memastikan logika hanya berjalan saat kondisi tepat.

            
            //----------------------------------------------------------------------------+
            //  --- MODE 3: Setelah BoS Bullish + HH After BoS Terkonfirmasi M15 ---          |
            //    Tujuan: Temukan LL yang lebih tinggi (Higher Low - HL) untuk konfirmasi M15 |
            //             tren bullish berkelanjutan.                                    |
            //----------------------------------------------------------------------------+
            // Syarat: Bos Bullish sudah terkonfirmasi DAN HH setelah BoS sudah terkonfirmasi.
            // === PERBAIKAN: Menghapus penolakan awal yang salah berdasarkan absoluteLowestLL_M15 ===
            // Setelah BoS Bullish terkonfirmasi, kita mencari Higher Low relatif terhadap lastAcceptedLL_M15,
            // bukan berdasarkan absoluteLowestLL_M15 (yang merupakan data MODE 2).
            // Logika validasi yang benar ada di blok MODE 3 di bawah.
            if (bosBullishConfirmedFlag_M15 && hhAfterBosConfirmedFlag_M15)
            {
                // --- 1. Abaikan LL yang terbentuk SEBELUM BoS Bullish terpicu M15 ---
                // Ini mencegah LL lama mempengaruhi tren baru.
                // Asumsi: time_postChoCH_HH_M15 menyimpan waktu saat BoS Bullish terpicu.
                if (rates_M15[i].time <= time_postChoCH_HH_M15) // Perubahan <= untuk memastikan inklusif
                {
                    PrintFormat("ℹ️ [MODE 3 M15] LL diabaikan (terbentuk sebelum BoS Bullish terpicu @ %s): %.2f @ %s",
                                TimeToString(time_postChoCH_HH_M15), rates_M15[i].low, TimeToString(rates_M15[i].time));
                    string boxNameIgnored_M15 = "zone_ll_M15_" + IntegerToString((int)rates_M15[i].time);
                    if (ObjectFind(0, boxNameIgnored_M15) >= 0) ObjectDelete(0, boxNameIgnored_M15); // Hapus visual jika ada
                    continue; // Lanjut ke iterasi berikutnya, jangan proses LL ini
                }
                
                // --- 2. Lacak LL terendah absolut sejak HH terakhir setelah BoS M15 ---
                // Ini hanya berlaku untuk LL yang terbentuk SETELAH HH terakhir setelah BoS.
                if (rates_M15[i].time > time_lastHHAfterBos_M15)
                {
                    if (lowestLLSinceLastHHAfterBos_M15 == -1 || rates_M15[i].low < lowestLLSinceLastHHAfterBos_M15)
                    {
                        double previousLowest              = lowestLLSinceLastHHAfterBos_M15;
                        lowestLLSinceLastHHAfterBos_M15 = rates_M15[i].low;
                        
                        if(previousLowest == -1)
                        {
                            PrintFormat("📉 [MODE 3 M15] Inisialisasi LL terendah sejak HH terakhir (%s): %.2f @ %s",
                                        TimeToString(time_lastHHAfterBos_M15), lowestLLSinceLastHHAfterBos_M15, TimeToString(rates_M15[i].time));
                        } 
                        else 
                        {
                            PrintFormat("📉 [MODE 3 M15] Update LL terendah sejak HH terakhir (%s): %.2f -> %.2f @ %s",
                                        TimeToString(time_lastHHAfterBos_M15), previousLowest, lowestLLSinceLastHHAfterBos_M15, TimeToString(rates_M15[i].time));
                        }
                        // Opsional: Update visual untuk lowestLLSinceLastHHAfterBos_M15 jika diperlukan
                        // UpdateAcceptedLevelVisuals_M15(lowestLLSinceLastHHAfterBos_M15, "LowestLL", rates_M15[i].time);
                    }
                }
                
                // --- 3. Periksa LL baru terhadap berbagai kriteria M15 ---
                bool   llRejected_M15   = false;
                string rejectReason_M15 = "";
                
                // --- 3a. Periksa terhadap LL terendah absolut M15 ---
                if (lowestLLSinceLastHHAfterBos_M15 != -1 && rates_M15[i].time > time_lastHHAfterBos_M15)
                {
                    if (rates_M15[i].low > lowestLLSinceLastHHAfterBos_M15)
                    {
                        llRejected_M15   = true;
                        rejectReason_M15 = "lebih tinggi dari LL terendah absolut sejak HH terakhir";
                        // Catatan: LL ini mungkin masih merupakan HL terhadap lastAcceptedLL_M15,
                        // tetapi melanggar aturan LL terendah absolut Anda.
                    }
                }
                
                // --- 3b. Periksa terhadap HL terakhir (Logika SMC/ICT Standar) M15 ---
                bool isHigherLow_M15 = false;
                if (rates_M15[i].low > lastAcceptedLL_M15)
                {
                    isHigherLow_M15 = true;
                }
                
                // --- 4. Keputusan berdasarkan kriteria M15 ---
                if (llRejected_M15)
                {
                    // ❌ LL baru ditolak karena melanggar aturan LL terendah absolut
                    PrintFormat("❌ [MODE 3 M15 - REJECTED by Abs Low] LL %.2f DITOLAK karena %s (%.2f) | Time: %s",
                                rates_M15[i].low, rejectReason_M15, lowestLLSinceLastHHAfterBos_M15, TimeToString(rates_M15[i].time));
                    string boxNameRejected_M15 = "zone_ll_M15_" + IntegerToString((int)rates_M15[i].time);
                    if (ObjectFind(0, boxNameRejected_M15) >= 0) ObjectDelete(0, boxNameRejected_M15);
                }
                else if (isHigherLow_M15)
                {
                    // ✅ Higher Low (HL) ditemukan: LL baru lebih tinggi dari LL terakhir (lastAcceptedLL_M15)
                    // Terima sebagai HL untuk tren, meskipun mungkin bukan LL terendah absolut saat ini.
                    double previousLL     = lastAcceptedLL_M15;  // Simpan nilai lama untuk log
                    lastAcceptedLL_M15 = rates_M15[i].low;    // Perbarui lastAcceptedLL_M15 ke nilai HL yang baru
                    
                    PrintFormat("✅ [MODE 3 M15] Init/Update HL After BoS + HH : %.2f > LL_sebelumnya (%.2f) | Time: %s",
                                lastAcceptedLL_M15, previousLL, TimeToString(rates_M15[i].time));
                    
                    // --- PERBAIKAN UTAMA ---
                    // Simpan nilai HL yang baru saja diterima sebagai referencia untuk LL berikutnya
                    // dalam tren bullish ini.
                    llBeforeHHAfterBos_M15      = lastAcceptedLL_M15;  // llBeforeHHAfterBos_M15 menjadi HL terbaru
                    timeLLBeforeHHAfterBos_M15  = rates_M15[i].time;   // Simpan waktu HL terbaru
                    llBeforeHHAfterBosSaved_M15 = true;            // Tandai bahwa referensi sudah disimpan/diperbarui
                    
                    PrintFormat("💾 [MODE 3 M15 - UPDATE] HL %.2f disimpan sebagai referensi baru (llBeforeHHAfterBos) | Time: %s",
                                llBeforeHHAfterBos_M15, TimeToString(timeLLBeforeHHAfterBos_M15));
                    // --- AKHIR PERBAIKAN ---
                    
                    PrintFormat("bosBullishConfirmedFlag_M15: %s | hhAfterBosConfirmedFlag_M15: %s",
                                bosBullishConfirmedFlag_M15 ? "True": "False",
                                hhAfterBosConfirmedFlag_M15 ? "True": "False");
                    UpdateAcceptedLevelVisuals_M15(lastAcceptedLL_M15, "LL", rates_M15[i].time); // Update visualisasi
                }
                else if (rates_M15[i].low < lastAcceptedLL_M15)
                {
                    // ❌ Lower Low (LL) ditemukan: LL baru lebih rendah dari HL terakhir (lastAcceptedLL_M15)
                    // Ini menunjukkan potensi kelemahan tren bullish atau koreksi.
                    PrintFormat("❌ [MODE 3 M15 - REJECTED by HL] LL %.2f DITOLAK karena lebih rendah dari HL terakhir (%.2f) | Time: %s",
                                rates_M15[i].low, lastAcceptedLL_M15, TimeToString(rates_M15[i].time));
                    string boxNameRejected_M15 = "zone_ll_M15_" + IntegerToString((int)rates_M15[i].time);
                    if (ObjectFind(0, boxNameRejected_M15) >= 0) ObjectDelete(0, boxNameRejected_M15);
                }
                else // rates_M15[i].low == lastAcceptedLL_M15
                {
                    // LL sama dengan LL terakhir (kasus langka, mungkin abaikan atau log).
                    PrintFormat("ℹ️ [MODE 3 M15] LL %.2f sama dengan HL terakhir (%.2f) | Time: %s",
                                rates_M15[i].low, lastAcceptedLL_M15, TimeToString(rates_M15[i].time));
                }
                // Stop proses LL di baris ini untuk iterasi ini.
                continue;
            }
            //----------------------------------------------------------------------------+
            // --- AKHIR MODE 3 M15 ---
            //----------------------------------------------------------------------------+
            //--------------------------------------------------------------------+
            //END MENUJU TREND BULLISH M15--------------------------------------------|
            //--------------------------------------------------------------------+
        } // End of LL processing
    } // End of Low (LL) processing
    
    //--------------+
    // CHoCH Bullish M15|
    //--------------+
   
    if (!chochBullish_M15 && !isInTrendBullish_M15 &&
        (lastAcceptedHH_M15 > 0 && rates_M15[1].close > lastAcceptedHH_M15 + 50 * _Point))
        {
                double   tempHH_M15         = lastAcceptedHH_M15;
                datetime tempHHTime_M15     = lastLoggedValidHHTime_M15;
                         preChochLL_M15     = lastAcceptedLL_M15;
                UpdateAcceptedLevelVisuals_M15(preChochLL_M15, "LL", rates_M15[0].time); // Update visualisasi
                        //  lastAcceptedLL_M15 = -1;                     // Reset lastAcceptedLL_M15 untuk mode 1
                        //  lastAcceptedHH_M15 = -1;
                Print("🔔🔔🔔 === ⚡⚡⚡ [CHoCH BULLISH TRIGGERED M15] ⚡⚡⚡ === 🔔🔔🔔");
                Print("📈 Close Breaks HH (Target) M15: ", DoubleToString(lastAcceptedHH_M15, _Digits), " → CHoCH Bullish Confirmed! ", TimeToString(rates_M15[1].time));
                PrintFormat("✅ [MODE 1 RESET M15] CHoCH Bullish terkonfirmasi. last Accepted LL direset ke preChochLL: %.2f @ %s",
                                     preChochLL_M15, TimeToString(rates_M15[1].time));
                //=== Gambar garis CHoCH dari HH sebelum break ke candle ===//
                string chochName_M15 = "CHoCH_Bull_M15_" + IntegerToString((int)tempHHTime_M15);
                ObjectDelete(0, chochName_M15);
                ObjectCreate(0, chochName_M15, OBJ_TREND, 0, tempHHTime_M15, tempHH_M15, rates_M15[1].time, tempHH_M15);
                ObjectSetInteger(0, chochName_M15, OBJPROP_COLOR, clrGold);
                ObjectSetInteger(0, chochName_M15, OBJPROP_WIDTH, 1);
                ObjectSetInteger(0, chochName_M15, OBJPROP_STYLE, STYLE_SOLID);
                ObjectSetInteger(0, chochName_M15, OBJPROP_BACK, true);
                //=== Label CHoCH di tengah garis ===//
                string   chochLabel_M15 = chochName_M15 + "_label";
                int      shift1_M15     = iBarShift(_Symbol, PERIOD_M15, tempHHTime_M15, false);
                int      shift2_M15     = iBarShift(_Symbol, PERIOD_M15, rates_M15[1].time, false);
                int      midShift_M15   = (shift1_M15 + shift2_M15) / 2;
                datetime midTime_M15    = iTime(_Symbol, PERIOD_M15, midShift_M15);
                ObjectDelete(0, chochLabel_M15);
                ObjectCreate(0, chochLabel_M15, OBJ_TEXT, 0, midTime_M15, tempHH_M15 + 6 * _Point);
                ObjectSetInteger(0, chochLabel_M15, OBJPROP_COLOR, clrGold);
                ObjectSetInteger(0, chochLabel_M15, OBJPROP_FONTSIZE, 10);
                ObjectSetInteger(0, chochLabel_M15, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER); // 🔥 Kunci utama
                ObjectSetString(0, chochLabel_M15, OBJPROP_TEXT, "CHoCH_M15");
                chochBullish_M15              = true;
                hhAfterChochConfirmedFlag_M15 = false; // Reset flag HH setelah CHoCH (Bullish)
                isInTrendBearish_M15          = false;
                chochBearish_M15              = false;
                chochBearishConfirmedFlag_M15 = false;
                llAfterChochConfirmedFlag_M15 = false;
                bosBearishConfirmedFlag_M15   = false;
                llAfterBosConfirmedFlag_M15   = false;
                bosBullishJustLogged_M15      = false;  // 🔓 Reset log untuk trigger BoS baru
                entryCountBuy_M15             = 0;      // Reset entry counter untuk cycle baru (Bullish)
                time_postChoCH_HH_M15         = -1;     // Reset time_postChoCH_HH_M15
                time_postChoCH_LL_M15         = -1;     // Reset time_postChoCH_LL_M15
                time_choch_bullish_M15        = rates_M15[1].time;
                time_choch_bearish_M15        = -1;
                timeBoSBearish_M15            = -1;
                postChoCH_LL_M15              = -1;
                preChochHH_M15                = -1; // Simpan HH sebelum CHoCH Bullish
                ResetMode2_M15(); // Reset variabel MODE 2                   
                Print("🔄 [CHoCH RESET M15] Variabel MODE 2 di-reset untuk siklus baru.");
                UpdateAcceptedLevelVisuals_M15(-1, "LL", rates_M15[1].time);
        }

    //--------------+
    // CHoCH Bearish M15|
    //--------------+
    if  (!chochBearish_M15 && !isInTrendBearish_M15 && // Hanya trigger jika belum dalam keadaan CHoCH/ tren bearish
        (lastAcceptedLL_M15 > 0 && rates_M15[1].close < lastAcceptedLL_M15 - 5 * _Point)) // Cek apakah close menembus LL terakhir (dengan sedikit buffer)
        {
            double   tempLL_M15         = lastAcceptedLL_M15;        // Simpan nilai LL yang ditembus
            datetime tempLLTime_M15     = lastLoggedValidLLTime_M15; // Simpan waktu LL yang ditembus
                     preChochHH_M15     = lastAcceptedHH_M15;        // Simpan HH sebelum CHoCH Bearish (untuk referensi MODE 2)
            // === PERBAIKAN: Update lastAcceptedHH ke HH terdekat terakhir yang terbentuk sebelum CHoCH Bearish ===
            lastAcceptedHH_M15 = lastLoggedValidHH_M15;              // Update lastAcceptedHH ke HH terdekat terakhir
            UpdateAcceptedLevelVisuals_M15(lastAcceptedHH_M15, "HH", rates_M15[1].time); // Update visualisasi HH setelah update
                  // lastAcceptedHH_M15 = -1;                    // Reset lastAcceptedHH_M15 untuk mode transisi
                    //  lastAcceptedLL_M15 = -1;                    // Reset lastAcceptedLL_M15 untuk mode transisi (opsional, tergantung logika MODE 1 bearish)
            //--- Logging ---
            Print("🔔🔔🔔 === ⚡⚡⚡ [CHoCH BEARISH TRIGGERED M15] ⚡⚡⚡ === 🔔🔔🔔");
            PrintFormat("📉 Close Breaks LL (Target) M15: %.5f → CHoCH Bearish Confirmed! @ %s",
                        lastAcceptedLL_M15, TimeToString(rates_M15[1].time));
            PrintFormat("✅ [MODE X RESET M15] CHoCH Bearish terkonfirmasi. last Accepted HH diupdate ke lastLoggedValidHH: %.5f (preChochHH: %.5f) @ %s",
                        lastAcceptedHH_M15, preChochHH_M15, TimeToString(rates_M15[1].time)); // Log update HH yang diperbaiki

            //=== Gambar garis CHoCH Bearish dari LL sebelum break ke candle break ===//
            string chochName_M15 = "CHoCH_Bear_M15_" + IntegerToString((int)tempLLTime_M15); // Gunakan nama unik berdasarkan waktu LL
            ObjectDelete(0, chochName_M15); // Hapus objek lama dengan nama yang sama jika ada
            // Buap garis tren dari waktu dan level LL yang ditembus ke waktu candle saat ini (rates_M15[1])
            ObjectCreate(0, chochName_M15, OBJ_TREND, 0, tempLLTime_M15, tempLL_M15, rates_M15[1].time, tempLL_M15);
            ObjectSetInteger(0, chochName_M15, OBJPROP_COLOR, clrOrangeRed); // Warna merah oranye untuk bearish
            ObjectSetInteger(0, chochName_M15, OBJPROP_WIDTH, 1);
            ObjectSetInteger(0, chochName_M15, OBJPROP_STYLE, STYLE_SOLID);
            ObjectSetInteger(0, chochName_M15, OBJPROP_BACK, true);

            //=== Label CHoCH Bearish di tengah garis ===//
            string   chochLabel_M15 = chochName_M15 + "_label";

            // Hitung waktu tengah antara dua titik
            datetime midTime_M15 = (tempLLTime_M15 + rates_M15[1].time) / 2;

            // Hapus label lama jika ada
            ObjectDelete(0, chochLabel_M15);

            // Buat label teks di tengah garis, sedikit di bawah garis (karena arah bearish)
            ObjectCreate(0, chochLabel_M15, OBJ_TEXT, 0, midTime_M15, tempLL_M15 - 6 * _Point); // Posisi sedikit di bawah (-6 * _Point)
            ObjectSetInteger(0, chochLabel_M15, OBJPROP_COLOR, clrOrangeRed);
            ObjectSetInteger(0, chochLabel_M15, OBJPROP_FONTSIZE, 10);
            ObjectSetInteger(0, chochLabel_M15, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER); // Jangkar ke kiri atas teks
            ObjectSetString(0, chochLabel_M15, OBJPROP_TEXT, "CHoCH_M15");
            //--- Reset Flag dan Variabel terkait tren ---
            chochBearish_M15              = true;        // Tandai CHoCH Bearish terpicu
            isInTrendBullish_M15          = false;       // Keluar dari tren Bullish jika ada
            chochBullish_M15              = false; 
            hhAfterChochConfirmedFlag_M15 = false;       // Reset flag HH setelah CHoCH (Bullish)
            chochBullishConfirmedFlag_M15 = false;       // Reset flag konfirmasi CHoCH Bullish
            llAfterChochConfirmedFlag_M15 = false;       // Reset flag LL setelah CHoCH (Bearish)
            bosBullishConfirmedFlag_M15   = false;       // Reset flag BoS Bullish
            hhAfterBosConfirmedFlag_M15   = false; 
            postChoCH_HH_M15              = -1;      // Reset flag HH setelah BoS Bullish
            time_postChoCH_HH_M15         = -1;
            entryCountSell_M15            = 0;      // Reset entry counter untuk cycle baru (Bearish)
            // bosBearishJustLogged_M15      = false;       // 🔓 Reset log untuk trigger BoS baru (jika digunakan untuk Bearish)
            time_postChoCH_LL_M15         = -1;          // Reset waktu post-CHoCH LL (jika digunakan)
            postChoCH_LL_M15              = -1;          // Reset nilai post-CHoCH LL (jika digunakan)
            time_choch_bearish_M15        = rates_M15[1].time;  // SIMPAN WAKTU CHoCH
            time_choch_bullish_M15        = -1;
            timeBoSBullish_M15            = -1;
            preChochLL_M15                = -1; // Simpan LL sebelum CHoCH Bearish (untuk referensi MODE 2)
            ResetMode2Bearish_M15(); // Reset variabel MODE 2 untuk siklus baru
            Print("🔄 [CHoCH RESET M15] Variabel MODE 2 di-reset");
            // Optional: Hapus visual LL lama jika diperlukan
            // UpdateAcceptedLevelVisuals_M15(-1, "HH", rates_M15[1].time); // Contoh jika ingin menghapus garis HH
            // UpdateAcceptedLevelVisuals_M15(-1, "LL", rates_M15[1].time); // Contoh jika ingin menghapus garis LL sementara

            //--- Reset flag lain yang relevan jika perlu ---
            // Misalnya, jika ada logika MODE 1/2/3 untuk bearish, mungkin perlu reset variabel spesifik di sini
            // llBeforeLLAfterBosSaved_M15 = false; // Contoh reset kunci MODE 3 Bearish jika ada
        }


    //------------+
    // BoS Bullish M15|
    //------------+
    // PrintFormat("🧐 Cek Candle BoS Bullish M15 : Time=%s | Open=%.2f | Close=%.2f | Low=%.2f | lastAcceptedHH=%.2f | TargetBreak=%.2f", 
    //         TimeToString(rates_M15[1].time), rates_M15[1].open, rates_M15[1].close, rates_M15[1].low, postChoCH_HH_M15, postChoCH_HH_M15 + 50 * _Point);
    if (
    postChoCH_HH_M15 > 0 && time_postChoCH_HH_M15 > 0 && // ⛔ Tambahkan pengecekan ini!
    (
        (chochBullish_M15 && !isInTrendBullish_M15 && rates_M15[1].close > postChoCH_HH_M15 + 50 * _Point) ||
        (bosBullishConfirmedFlag_M15 && hhAfterBosConfirmedFlag_M15 &&
         isInTrendBullish_M15 > 0 && rates_M15[1].close > postChoCH_HH_M15 + 50 * _Point)
    ))
    {
        string bosLineName_M15  = "BoS_Bull_M15_" + IntegerToString((int)time_postChoCH_HH_M15);
        string bosLabelName_M15 = bosLineName_M15 + "_label";
        //=== Gambar garis dari postChoCH_HH_M15 ke candle dan label di tengah ===//
        string bosName_M15 = "BoS_Bull_M15_" + IntegerToString((int)time_postChoCH_HH_M15);
        ObjectDelete(0, bosName_M15);
        ObjectCreate(0, bosName_M15, OBJ_TREND, 0, time_postChoCH_HH_M15, postChoCH_HH_M15, rates_M15[1].time, postChoCH_HH_M15);
        ObjectSetInteger(0, bosName_M15, OBJPROP_COLOR, clrDeepSkyBlue);
        ObjectSetInteger(0, bosName_M15, OBJPROP_WIDTH, 1);
        ObjectSetInteger(0, bosName_M15, OBJPROP_STYLE, STYLE_SOLID);
        ObjectSetInteger(0, bosName_M15, OBJPROP_BACK, true);
        //=== Label BoS di tengah garis ===//
        string   bosLabel_M15 = bosName_M15 + "_label";
        datetime midTime_M15  = (time_postChoCH_HH_M15 + rates_M15[1].time) / 2;
        ObjectDelete(0, bosLabel_M15);
        ObjectCreate(0, bosLabel_M15, OBJ_TEXT, 0, midTime_M15, postChoCH_HH_M15 - 7 * _Point);
        ObjectSetInteger(0, bosLabel_M15, OBJPROP_COLOR, clrDeepSkyBlue);
        ObjectSetInteger(0, bosLabel_M15, OBJPROP_FONTSIZE, 10);
        ObjectSetInteger(0, bosLabel_M15, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER); // 🔥 Kunci utama
        ObjectSetString(0, bosLabel_M15, OBJPROP_TEXT, "BoS_M15");
        if (!bosBullishJustLogged_M15) // Cek apakah sudah pernah dilog
            {
            Print("🚀🚀🚀 === 💥💥💥 [BoS BULLISH TRIGGERED M15] 💥💥💥 === 🚀🚀🚀");
            Print("📊 Close > postChoCH_HH_M15: ", postChoCH_HH_M15, " → BOS Bullish Confirmed! ", TimeToString(rates_M15[1].time));
            lastBoSTimeLogged_M15 = rates_M15[1].time;  // Simpan waktu terakhir yang sudah dilog
            }
        // chochBullish_M15            = false;
        postChoCH_HH_M15            = -1;
        time_postChoCH_HH_M15       = 0;      // Reset waktu post-CHoCH HH
        bosBullishConfirmedFlag_M15 = true;
        isInTrendBullish_M15        = true;
        preChochLL_M15              = -1;
        // Di blok BoS Bullish:
        timeBoSBullish_M15 = rates_M15[1].time; // Disimpan saat BoS terpicu
        
        // SAVE BoS DATA
        SaveLLHHBOSToArray("BoS", "Bullish", lastAcceptedLL_M15, rates_M15[1].time, "M15", "Confirmed", lastAcceptedHH_M15, 0);
        
        // ... di dalam blok kondisi BoS Bullish ...
        if (bosBullishConfirmedFlag_M15)
        {
            // ... kode lain ...
            PrintFormat("🔍 [DEBUG BoS M15 %d] lastAcceptedLL_M15 saat ini: %.2f", bos_counter_M15, lastAcceptedLL_M15); // Tambahkan counter BoS jika perlu
            llBeforeHHAfterBos_M15      = lastAcceptedLL_M15;  // Simpan LL terakhir sebagai referensi
            timeLLBeforeHHAfterBos_M15  = rates_M15[1].time;   // Waktu saat BoS terkonfirmasi (atau TimeCurrent())
            llBeforeHHAfterBosSaved_M15 = true;            // Tandai bahwa nilai sudah disimpan untuk siklus ini
            PrintFormat("💾 [PERBAIKAN BoS Confirmed M15] LL referensi untuk Mode 3 disimpan: %.2f @ %s", llBeforeHHAfterBos_M15, TimeToString(timeLLBeforeHHAfterBos_M15));
            // ... kode lain ...
        }
        
        // --- ENTRY LOGIC ENABLED WITH FILTERS + BLACKOUT HOURS ---
        MqlDateTime currentTime;
        TimeToStruct(TimeCurrent(), currentTime);
        int currentHour = currentTime.hour;
        bool isBlackoutHour = (currentHour == 2 || currentHour == 14 || currentHour == 22);
        if (bosBullishConfirmedFlag_M15 && rates_M15[0].close > ema200_M15 && entryCountBuy_M15 < MaxEntriesPerCycle_M15 && IsH1ConfirmedBullish() && IsEMATrendingUp_M15() && !isBlackoutHour) 
        {
            if (rates_M15[1].time > lastEntryTime_M15 + PeriodSeconds(PERIOD_M15) * 3) { // Hindari entry berulang dalam waktu dekat
                double entryPrice_M15 = rates_M15[1].close + 3 * _Point; // Sedikit di atas close
                double sl_M15, tp_M15;
                
                // 🔄 MENGGUNAKAN ATR-BASED DYNAMIC SL/TP (OPSI 2: HYBRID)
                if (UseATRBasedSLTP_M15)
                {
                    SLTPResult dynamicResult = CalculateDynamicSLTP_M15(entryPrice_M15, true, lastAcceptedLL_M15, lastAcceptedHH_M15);
                    sl_M15 = dynamicResult.sl_price;
                    tp_M15 = dynamicResult.tp_price;
                    PrintFormat("🔄 [HYBRID BUY Entry %d/3] ATR: %.1f poin | Volatility: %s | SL: %.1f poin | TP: %.1f poin (MIN_TP: %.0f, MIN_SL: %.0f)",
                                entryCountBuy_M15 + 1, dynamicResult.atr_value, dynamicResult.volatility, dynamicResult.sl_points, dynamicResult.tp_points, MinimumTP_Points, MinimumSL_Points);
                }
                else
                {
                    // FALLBACK ke hardcoded values jika ATR disabled
                    if (entryCountBuy_M15 == 0) {
                        sl_M15 = entryPrice_M15 - DefaultSL_Buy_M15 * _Point;
                        tp_M15 = entryPrice_M15 + DefaultTP_Buy_M15 * _Point;
                        Print("📌 [BoS Entry 1/3] SL: ", DefaultSL_Buy_M15, " poin, TP: ", DefaultTP_Buy_M15, " poin");
                    } else if (entryCountBuy_M15 == 1) {
                        sl_M15 = entryPrice_M15 - Entry2SL_Buy_M15 * _Point;
                        tp_M15 = entryPrice_M15 + Entry2TP_Buy_M15 * _Point;
                        Print("📌 [BoS Entry 2/3] SL: ", Entry2SL_Buy_M15, " poin, TP: ", Entry2TP_Buy_M15, " poin");
                    } else {
                        sl_M15 = entryPrice_M15 - Entry3SL_Buy_M15 * _Point;
                        tp_M15 = entryPrice_M15 + Entry3TP_Buy_M15 * _Point;
                        Print("📌 [BoS Entry 3/3] SL: ", Entry3SL_Buy_M15, " poin, TP: ", Entry3TP_Buy_M15, " poin");
                    }
                }
                
                if (trade.Buy(0.05, NULL, entryPrice_M15, sl_M15, tp_M15, "BoS Buy M15")) 
                    {
                    Print("✅ ENTRY BUY di harga M15 ", entryPrice_M15);
                    Print("[TRAILING RESET M15] Buy flags reset"); // Log reset saat entry
                    Print("📊 Entry Count (Buy): ", ++entryCountBuy_M15, "/", MaxEntriesPerCycle_M15);
                    // hasEnteredTrade_M15 = true;  // ⚙️ DIHAPUS - Tidak perlu, gunakan counter saja
                    lastEntryTime_M15 = TimeCurrent();
                    buyEntryPrice_M15 = entryPrice_M15; // Simpan harga entry
                    trailingActivatedBuy_M15 = false; // Reset flag trailing
                    currentBuyTrade_M15.ticket = trade.ResultOrder();
                    currentBuyTrade_M15.entry_price = entryPrice_M15;
                    currentBuyTrade_M15.sl = sl_M15;
                    currentBuyTrade_M15.tp = tp_M15;
                    currentBuyTrade_M15.entry_time = TimeCurrent();
                    currentBuyTrade_M15.type = "BUY";
                    PrintFormat("🚀 [BUY ENTRY M15] Ticket: %I64u | Price: %.5f | SL: %.5f | TP: %.5f | Time: %s",
                    currentBuyTrade_M15.ticket,
                    currentBuyTrade_M15.entry_price,
                    currentBuyTrade_M15.sl,
                    currentBuyTrade_M15.tp,
                    TimeToString(currentBuyTrade_M15.entry_time, TIME_DATE|TIME_SECONDS));
                    } 
                else 
                    {
                        Print("❌ Gagal melakukan entry BUY M15");
                    }
            }
        }
    } 

    // ------------+
    // BoS Bearish M15|
    // ------------+
    if (
        postChoCH_LL_M15 > 0 && time_postChoCH_LL_M15 > 0 &&
        !bearishSearchCompleted_M15 &&
        (
            (chochBearish_M15 && !isInTrendBearish_M15 && rates_M15[1].close < postChoCH_LL_M15 - 50 * _Point) ||
            (bosBearishConfirmedFlag_M15 && isInTrendBearish_M15 && rates_M15[1].close < postChoCH_LL_M15 - 50 * _Point)
       )
    )
    {
        string bosLineName_M15 = "BoS_Bear_M15_" + IntegerToString((int)time_postChoCH_LL_M15) + "_at_" + IntegerToString((int)rates_M15[1].time);
        string bosLabelName_M15 = bosLineName_M15 + "_label";

        //=== Gambar garis dari postChoCH_LL_M15 ke candle dan label di tengah ===//
        ObjectDelete(0, bosLineName_M15);
        ObjectCreate(0, bosLineName_M15, OBJ_TREND, 0, time_postChoCH_LL_M15, postChoCH_LL_M15, rates_M15[1].time, postChoCH_LL_M15);
        ObjectSetInteger(0, bosLineName_M15, OBJPROP_COLOR, clrOrange);
        ObjectSetInteger(0, bosLineName_M15, OBJPROP_WIDTH, 1);
        ObjectSetInteger(0, bosLineName_M15, OBJPROP_STYLE, STYLE_SOLID);
        ObjectSetInteger(0, bosLineName_M15, OBJPROP_BACK, true);

        //=== Label BoS Bearish ===//
        datetime midTime_M15  = (time_postChoCH_LL_M15 + rates_M15[1].time) / 2;
        ObjectDelete(0, bosLabelName_M15);
        ObjectCreate(0, bosLabelName_M15, OBJ_TEXT, 0, midTime_M15, postChoCH_LL_M15 + 7 * _Point);
        ObjectSetInteger(0, bosLabelName_M15, OBJPROP_COLOR, clrOrange);
        ObjectSetInteger(0, bosLabelName_M15, OBJPROP_FONTSIZE, 10);
        ObjectSetInteger(0, bosLabelName_M15, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
        ObjectSetString(0, bosLabelName_M15, OBJPROP_TEXT, "BoS_M15");

        //=== Logging dan update flag ===//
        Print("🔥🔥🔥 === ⚡⚡⚡ [BoS BEARISH TRIGGERED M15] ⚡⚡⚡ === 🔥🔥🔥");
        Print("📉 Close < postChoCH_LL_M15: ", postChoCH_LL_M15, " → BoS Bearish Confirmed! ", TimeToString(rates_M15[1].time));
        
        lastBoSTimeLogged_M15         = rates_M15[1].time;
        // chochBearish_M15              = false;
        postChoCH_LL_M15              = -1;
        time_postChoCH_LL_M15         = -1;
        bosBearishConfirmedFlag_M15   = true;
        isInTrendBearish_M15          = true;
        
        // SAVE BoS BEARISH DATA
        SaveLLHHBOSToArray("BoS", "Bearish", lastAcceptedLL_M15, rates_M15[1].time, "M15", "Confirmed", lastAcceptedHH_M15, 0);
        // Di dalam blok BoS Bearish:
        timeBoSBearish_M15 = rates_M15[1].time;  // Simpan waktu BoS       
        ResetMode2Bearish_M15(); // Reset variabel MODE 2 untuk siklus baru
        // ... di dalam blok kondisi BoS Bullish ...
        if (bosBearishConfirmedFlag_M15)
        {
            // ... kode lain ...
            PrintFormat("🔍 [DEBUG BoS M15 %d] last Accepted HH saat ini: %.2f", bos_counter_M15, lastAcceptedHH_M15); // Tambahkan counter BoS jika perlu
            hhBeforellAfterBos_M15      = lastAcceptedHH_M15;  // Simpan LL terakhir sebagai referensi
            timehhBeforellAfterBos_M15  = rates_M15[1].time;   // Waktu saat BoS terkonfirmasi (atau TimeCurrent())
            llBeforeHHAfterBosSaved_M15 = true;            // Tandai bahwa nilai sudah disimpan untuk siklus ini
            PrintFormat("💾 [PERBAIKAN BoS Confirmed M15] HH referensi untuk Mode 3 disimpan: %.2f @ %s", hhBeforellAfterBos_M15, TimeToString(timehhBeforellAfterBos_M15));
            // ... kode lain ...
        }
        //=== ENTRY SELL SAAT BoS BEARISH M15 === //
        // --- ENTRY LOGIC WITH H1 & EMA FILTERS + BLACKOUT HOURS + LIQUIDITY FILTER ---
        MqlDateTime sellTime;
        TimeToStruct(TimeCurrent(), sellTime);
        int sellHour = sellTime.hour;
        bool isSellBlackoutHour = (sellHour == 2 || sellHour == 14 || sellHour == 22);
        bool isHighLiquidityHourSell = (sellHour >= 6 && sellHour <= 11); // SELL only during 06-11 UTC
        if (bosBearishConfirmedFlag_M15 && rates_M15[0].close < ema200_M15 && entryCountSell_M15 < MaxEntriesPerCycle_M15 && IsH1ConfirmedBearish() && !IsEMATrendingUp_M15() && !isSellBlackoutHour && isHighLiquidityHourSell)
        {
            if (rates_M15[1].time > lastSellEntryTime_M15 + PeriodSeconds(PERIOD_M15) * 3)  // Hindari entry berulang
            {
                double entryPrice_M15 = rates_M15[1].close - 3 * _Point;  // Sedikit di bawah close
                double sl_M15, tp_M15;
                
                // 🔄 MENGGUNAKAN ATR-BASED DYNAMIC SL/TP
                if (UseATRBasedSLTP_M15)
                {
                    SLTPResult dynamicResult = CalculateDynamicSLTP_M15(entryPrice_M15, false, lastAcceptedLL_M15, lastAcceptedHH_M15);
                    sl_M15 = dynamicResult.sl_price;
                    tp_M15 = dynamicResult.tp_price;
                    PrintFormat("🔄 [HYBRID SELL Entry %d/3] ATR: %.1f poin | Volatility: %s | SL: %.1f poin | TP: %.1f poin (MIN_TP: %.0f, MIN_SL: %.0f)",
                                entryCountSell_M15 + 1, dynamicResult.atr_value, dynamicResult.volatility, dynamicResult.sl_points, dynamicResult.tp_points, MinimumTP_Points, MinimumSL_Points);
                }
                else
                {
                    // FALLBACK ke hardcoded values jika ATR disabled
                    if (entryCountSell_M15 == 0) {
                        sl_M15 = entryPrice_M15 + DefaultSL_Sell_M15 * _Point;
                        tp_M15 = entryPrice_M15 - DefaultTP_Sell_M15 * _Point;
                        Print("📌 [BoS Entry 1/3] SL: ", DefaultSL_Sell_M15, " poin, TP: ", DefaultTP_Sell_M15, " poin");
                    } else if (entryCountSell_M15 == 1) {
                        sl_M15 = entryPrice_M15 + Entry2SL_Sell_M15 * _Point;
                        tp_M15 = entryPrice_M15 - Entry2TP_Sell_M15 * _Point;
                        Print("📌 [BoS Entry 2/3] SL: ", Entry2SL_Sell_M15, " poin, TP: ", Entry2TP_Sell_M15, " poin");
                    } else {
                        sl_M15 = entryPrice_M15 + Entry3SL_Sell_M15 * _Point;
                        tp_M15 = entryPrice_M15 - Entry3TP_Sell_M15 * _Point;
                        Print("📌 [BoS Entry 3/3] SL: ", Entry3SL_Sell_M15, " poin, TP: ", Entry3TP_Sell_M15, " poin");
                    }
                }

                if (trade.Sell(0.05, NULL, entryPrice_M15, sl_M15, tp_M15))
                    {
                        Print("✅ ENTRY SELL dilakukan di harga M15 ", entryPrice_M15);
                        Print("[TRAILING RESET M15] Sell flags reset"); // Log reset saat entry
                        Print("📊 Entry Count (Sell): ", ++entryCountSell_M15, "/", MaxEntriesPerCycle_M15);
                        // hasEnteredSellTrade_M15 = true;  // ⚙️ DIHAPUS - Tidak perlu, gunakan counter saja
                        lastSellEntryTime_M15 = TimeCurrent();
                        sellEntryPrice_M15 = entryPrice_M15; // Simpan harga entry
                        trailingActivatedSell_M15 = false; // Reset flag trailing
                        currentSellTrade_M15.ticket = trade.ResultOrder();
                        currentSellTrade_M15.entry_price = entryPrice_M15;
                        currentSellTrade_M15.sl = sl_M15;
                        currentSellTrade_M15.tp = tp_M15;
                        currentSellTrade_M15.entry_time = TimeCurrent();
                        currentSellTrade_M15.type = "SELL";
                        PrintFormat("🚀 [SELL ENTRY M15] Ticket: %I64u | Price: %.5f | SL: %.5f | TP: %.5f | Time: %s",
                        currentSellTrade_M15.ticket,
                        currentSellTrade_M15.entry_price,
                        currentSellTrade_M15.sl,
                        currentSellTrade_M15.tp,
                        TimeToString(currentSellTrade_M15.entry_time, TIME_DATE|TIME_SECONDS));
                    }
                else
                    {
                        Print("❌ Gagal melakukan entry SELL M15");
                    }
            }
        }

    }

    // === RESET ENTRY FLAGS M15 === //
    if (!bosBullishConfirmedFlag_M15)
    {
        hasEnteredTrade_M15 = false;
    }
    if (!bosBearishConfirmedFlag_M15)
    {
        hasEnteredSellTrade_M15 = false;
    }
    // ApplyTrailingStop_M15();  // ⚙️ [DISABLED] Trailing stop M15 dinonaktifkan
    // CheckTrailingReset_M15();  // ⚙️ [DISABLED] Trailing reset M15 dinonaktifkan
    //+------------------------------------------------------------------+
    //| Tambahkan di akhir fungsi OnTick(), sebelum penutup akhir } M15      |
    //+------------------------------------------------------------------+

    //--- Log status flag hanya ketika ada perubahan M15 ---
    static string lastFlagStatusBullish_M15 = "";
    static string lastFlagStatusBearish_M15 = "";
    static datetime lastFlagLogTime_M15 = 0;
    
    string currentFlagStatusBullish_M15 = StringFormat(
        "BULLISH FLAGS M15 => chochBullish_M15=%s | hhAfterChoch_M15=%s | bosBullish_M15=%s | inTrendBullish_M15=%s | hhAfterBos_M15=%s",
        chochBullish_M15 ? "true" : "false",
        hhAfterChochConfirmedFlag_M15 ? "true" : "false",
        bosBullishConfirmedFlag_M15 ? "true" : "false",
        isInTrendBullish_M15 ? "true" : "false",
        hhAfterBosConfirmedFlag_M15 ? "true" : "false");
    
    string currentFlagStatusBearish_M15 = StringFormat(
        "BEARISH FLAGS M15 => chochBearish_M15=%s | llAfterChoch_M15=%s | bosBearish_M15=%s | inTrendBearish_M15=%s | llAfterBos_M15=%s",
        chochBearish_M15 ? "true" : "false",
        llAfterChochConfirmedFlag_M15 ? "true" : "false",
        bosBearishConfirmedFlag_M15 ? "true" : "false",
        isInTrendBearish_M15 ? "true" : "false",
        llAfterBosConfirmedFlag_M15 ? "true" : "false");
    
    // Cek apakah status flag berubah atau sudah lebih dari 1 detik sejak log terakhir
    if ((currentFlagStatusBullish_M15 != lastFlagStatusBullish_M15 || 
         currentFlagStatusBearish_M15 != lastFlagStatusBearish_M15) && 
        (TimeCurrent() - lastFlagLogTime_M15 >= 1))
    {
        Print("-------------------------------------------------------------------------------------------------------------------");
        Print(currentFlagStatusBullish_M15);
        Print(currentFlagStatusBearish_M15);
        Print("-------------------------------------------------------------------------------------------------------------------");
        
        // Update status terakhir
        lastFlagStatusBullish_M15 = currentFlagStatusBullish_M15;
        lastFlagStatusBearish_M15 = currentFlagStatusBearish_M15;
        lastFlagLogTime_M15 = TimeCurrent();
    }

    //+------------------------------------------------------------------+
    //| Log perubahan variabel kunci sistem (3 bagian terpisah) M15          |
    //+------------------------------------------------------------------+
    static string lastLoggedPart1_M15 = "", lastLoggedPart2_M15 = "", lastLoggedPart3_M15 = "", lastLoggedPart4_M15 = "";
    datetime current_time_M15 = TimeCurrent();

    // Bagian 1: Level-level harga penting
    string part1_M15 = StringFormat(
        "KEY VARS M15 [1/4] : lastAcceptedHH_M15=%.5f | lastAcceptedLL_M15=%.5f | postChoCH_HH_M15=%.5f | postChoCH_LL_M15=%.5f",
        lastAcceptedHH_M15,
        lastAcceptedLL_M15,
        postChoCH_HH_M15,
        postChoCH_LL_M15
    );

    // Bagian 2: Timestamp event penting
    string part2_M15 = StringFormat(
        "KEY VARS M15 [2/4] : time_postChoCH_HH_M15=%s | time_postChoCH_LL_M15=%s | timeBoSBullish_M15=%s | timeBoSBearish_M15=%s",
        time_postChoCH_HH_M15 > 0 ? TimeToString(time_postChoCH_HH_M15, TIME_DATE|TIME_MINUTES) : "N/A",
        time_postChoCH_LL_M15 > 0 ? TimeToString(time_postChoCH_LL_M15, TIME_DATE|TIME_MINUTES) : "N/A",
        timeBoSBullish_M15 > 0 ? TimeToString(timeBoSBullish_M15, TIME_DATE|TIME_MINUTES) : "N/A",
        timeBoSBearish_M15 > 0 ? TimeToString(timeBoSBearish_M15, TIME_DATE|TIME_MINUTES) : "N/A"
    );

    // Bagian 3: Timestamp event penting
    string part3_M15 = StringFormat(
        "KEY VARS M15 [3/4] : time_choch_bearish_M15=%s time_choch_bullish_M15=%s",
        time_choch_bearish_M15 > 0 ? TimeToString(time_choch_bearish_M15, TIME_DATE|TIME_MINUTES) : "N/A",
        time_choch_bullish_M15 > 0 ? TimeToString(time_choch_bullish_M15, TIME_DATE|TIME_MINUTES) : "N/A"
    );

    // Bagian 3: Level referensi sebelum CHoCH
    string part4_M15 = StringFormat(
        "KEY VARS M15 [4/4] : preChochHH_M15=%.5f | preChochLL_M15=%.5f",
        preChochHH_M15,
        preChochLL_M15
    );

    // Hanya log jika salah satu bagian berubah dan minimal 1 detik telah berlalu
    if ((part1_M15 != lastLoggedPart1_M15 || part2_M15 != lastLoggedPart2_M15 || part3_M15 != lastLoggedPart3_M15 || part4_M15 != lastLoggedPart4_M15) &&
        (current_time_M15 - lastFlagLogTime_M15 >= 1))
    {
        Print("-------------------------------------------------------------------------------------------------------------------");
        Print("📊📊📊 [KEY SYSTEM VARIABLES M15 - UPDATED] 📊📊📊");
        Print(part1_M15);
        Print(part2_M15);
        Print(part3_M15);
        Print(part4_M15);
        Print("-------------------------------------------------------------------------------------------------------------------");

        // Update status terakhir
        lastLoggedPart1_M15 = part1_M15;
        lastLoggedPart2_M15 = part2_M15;
        lastLoggedPart3_M15 = part3_M15;
        lastLoggedPart4_M15 = part4_M15;
        lastFlagLogTime_M15 = current_time_M15;
    }
}

void WarmUp_H1(int bars)
{
    MqlRates rates[];
    ArraySetAsSeries(rates, true);

    int need = MathMax(bars, WindowSize_H1*2 + 50);
    int copied = CopyRates(_Symbol, PERIOD_H1, 0, need, rates);
    if (copied <= 0)
    {
        Print("❌ WarmUp_H1 gagal CopyRates");
        return;
    }

    g_BackfillMode_H1 = true;
    DetectAndDraw_H1(rates, /*backfillMode=*/true);
    g_BackfillMode_H1 = false;

    // Optional: set lastBarTime ke bar terakhir, agar OnTick nanti fokus ke bar berikutnya
    lastBarTime_H1 = rates[0].time;

    ChartRedraw();
    PrintFormat("✅ WarmUp_H1 selesai. Bars=%d | lastBar=%s",
                copied, TimeToString(lastBarTime_H1, TIME_DATE|TIME_MINUTES));
}

void WarmUp_M15(int bars)
{
    MqlRates rates[];
    ArraySetAsSeries(rates, true);

    int need = MathMax(bars, WindowSize_M15*2 + 50);
    int copied = CopyRates(_Symbol, PERIOD_M15, 0, need, rates);
    if (copied <= 0)
    {
        Print("❌ WarmUp_M15 gagal CopyRates");
        return;
    }

    g_BackfillMode_M15 = true;
    DetectAndDraw_M15(rates, /*backfillMode=*/true);
    g_BackfillMode_M15 = false;

    // Optional: set lastBarTime ke bar terakhir, agar OnTick nanti fokus ke bar berikutnya
    lastBarTime_M15 = rates[0].time;

    ChartRedraw();
    PrintFormat("✅ WarmUp_M15 selesai. Bars=%d | lastBar=%s",
                copied, TimeToString(lastBarTime_M15, TIME_DATE|TIME_MINUTES));
}

//-----------------------------------------------------------------------------+
// Process H1
//-----------------------------------------------------------------------------+

void DetectAndDraw_H1(MqlRates &rates_H1[], bool backfillMode)
{
    //--------------------------------+
    //--- Loop Deteksi High/Low H1 ---|
    //--------------------------------+
    for (int i = ArraySize(rates_H1) - WindowSize_H1 - 1; i >= WindowSize_H1; i--)
    {
        // --- Skip bars if they are within already processed CHoCH/BoS zones H1 ---
        if ((chochBullish_H1 && rates_H1[i].time < time_postChoCH_HH_H1) ||
            (isInTrendBullish_H1 && rates_H1[i].time < time_lastBoS_HH_H1) ||
            (chochBearish_H1 && rates_H1[i].time < time_postChoCH_LL_H1) ||
            (isInTrendBearish_H1 && rates_H1[i].time < time_lastBoS_LL_H1))
        {
            continue;
        }
        
        // --- Check if current bar is a local High or Low within the WindowSize H1 ---
        bool isHigh_H1 = true;
        bool isLow_H1  = true;
        for (int j = i - WindowSize_H1; j <= i + WindowSize_H1; j++)
        {
            if (j == i) continue;
            if (rates_H1[i].high < rates_H1[j].high) isHigh_H1 = false;
            if (rates_H1[i].low > rates_H1[j].low) isLow_H1    = false;
        }
        
        // --- Process High (HH) H1 ---
        if (isHigh_H1)
        {   
            // --- Basic Logging & Spam Prevention H1 ---
            if (rates_H1[i].time <= lastProcessedTime_HH_H1) continue;
            lastProcessedTime_HH_H1 = rates_H1[i].time;
            if (rates_H1[i].high == lastLoggedValidHH_H1 && rates_H1[i].time == lastLoggedValidHHTime_H1) continue;
            
            PrintFormat("✅ H1: HH VALID TERBENTUK: %.2f | Time: %s", rates_H1[i].high, TimeToString(rates_H1[i].time));
            
            lastLoggedValidHH_H1     = rates_H1[i].high;
            lastLoggedValidHHTime_H1 = rates_H1[i].time;
            
            // --- Visual Drawing (Zona HH) H1 ---
            datetime startTime_H1 = rates_H1[i].time;
            datetime endTime_H1   = startTime_H1 + PeriodSeconds() * ZoneLength_H1;
            string   boxName_H1   = "H1_zone_hh_" + IntegerToString((int)rates_H1[i].time);
            
            ObjectDelete(0, boxName_H1);
            ObjectCreate(0, boxName_H1, OBJ_RECTANGLE, 0, startTime_H1, rates_H1[i].high, endTime_H1, rates_H1[i].high + 3 * _Point);
            ObjectSetInteger(0, boxName_H1, OBJPROP_COLOR, clrRed);
            ObjectSetInteger(0, boxName_H1, OBJPROP_BACK, true);
            
            // --- MODE MENUJU TREND BULLISH H1 ---
            // --- CHoCH Bullish Confirmed, terbentuk HH valid sebagai target BoS Bullish H1 ---
            if (chochBullish_H1 && !isInTrendBullish_H1)
            {
                if (!hhAfterChochConfirmedFlag_H1) 
                {
                    lastAcceptedLL_H1            = preChochLL_H1;
                    lastAcceptedHH_H1            = rates_H1[i].high;  
                    UpdateAcceptedLevelVisuals_H1(lastAcceptedLL_H1, "LL", rates_H1[i].time);
                    UpdateAcceptedLevelVisuals_H1(lastAcceptedHH_H1, "HH", rates_H1[i].time);
                    
                    postChoCH_HH_H1              = rates_H1[i].high;
                    time_postChoCH_HH_H1         = rates_H1[i].time;
                    chochBullishConfirmedFlag_H1 = true;
                    hhAfterChochConfirmedFlag_H1 = true;
                    bosBullishConfirmedFlag_H1   = false;
                    hhAfterBosConfirmedFlag_H1   = false;
                    
                    // SAVE CHoCH DATA
                    SaveLLHHBOSToArray("CHoCH", "Bullish", lastAcceptedHH_H1, rates_H1[i].time, "H1", "Confirmed", preChochLL_H1, 0);
                    SaveLLHHBOSToArray("LL", "Reference", preChochLL_H1, rates_H1[i].time, "H1", "PreChoCH", 0, 0);
                    
                    PrintFormat("✅ H1: HH After ChoCH Confirmed on = %.2f | Time: %s", lastAcceptedHH_H1, TimeToString(rates_H1[i].time));
                    PrintFormat("✅ H1: [MODE 1 RESET] CHoCH Bullish dan HH After CHoCH terkonfirmasi. lastAcceptedLL direset ke PreChoCHLL=%.2f | Time: %s",
                            preChochLL_H1, TimeToString(rates_H1[i].time));
                    continue;
                }
                else if (rates_H1[i].high < lastAcceptedHH_H1) 
                {
                    PrintFormat("❌ H1: [MODE 1.1 REJECTED] HH %.2f DITOLAK karena < Lebih rendah dari CHoCH+HH last Accepted HH %.2f | Time: %s",
                            rates_H1[i].high, lastAcceptedHH_H1, TimeToString(rates_H1[i].time));
                    if (ObjectFind(0, boxName_H1) >= 0) ObjectDelete(0, boxName_H1);
                }
            }

            // --- CHoCH Bullish Confirmed, terbentuk HH valid sebagai target BoS Bullish H1 ---
            if (chochBullish_H1 && !isInTrendBullish_H1 && !hhAfterChochConfirmedFlag_H1 && rates_H1[i].high > lastAcceptedHH_H1)
            {
                postChoCH_HH_H1      = rates_H1[i].high;
                time_postChoCH_HH_H1 = rates_H1[i].time;
                PrintFormat("🎯 H1: [TARGET SET] BoS Bullish Target HH set ke: %.2f @ %s", postChoCH_HH_H1, TimeToString(time_postChoCH_HH_H1));
            }

            if (chochBullish_H1 && isInTrendBullish_H1 && rates_H1[i].high > lastAcceptedHH_H1)
            {
                postChoCH_HH_H1      = rates_H1[i].high;
                time_postChoCH_HH_H1 = rates_H1[i].time;
                PrintFormat("🎯 H1: [TARGET SET] BoS Bullish Target HH set ke: %.2f @ %s", postChoCH_HH_H1, TimeToString(time_postChoCH_HH_H1));
            }
            
            // --- START: Logika PEMBARUAN LASTACCEPTEDHH (DIREVISI) Part 2 H1 ---
            if (bosBullishConfirmedFlag_H1 && isInTrendBullish_H1)
            {
                if (rates_H1[i].high > lastAcceptedHH_H1)
                {
                    double oldHH = lastAcceptedHH_H1;
                    lastAcceptedHH_H1 = rates_H1[i].high;
                    PrintFormat("✅ H1: [MODE 1]Update last Accepted HH After Bos: %s | Time: %s", DoubleToString(lastAcceptedHH_H1, _Digits), TimeToString(rates_H1[i].time));
                    UpdateAcceptedLevelVisuals_H1(lastAcceptedHH_H1, "HH", rates_H1[i].time);
                    hhAfterBosConfirmedFlag_H1 = true;
                    timeHHAfterBosConfirmed_H1 = TimeCurrent();
                    postChoCH_HH_H1            = rates_H1[i].high;
                    
                    // SAVE HH UPDATE
                    SaveLLHHBOSToArray("HH", "Bullish", lastAcceptedHH_H1, rates_H1[i].time, "H1", "Updated", oldHH, 0);
                    
                    PrintFormat("✅ H1: HH After BoS Confirmed: %s | Time: %s", DoubleToString(lastAcceptedHH_H1, _Digits), TimeToString(rates_H1[i].time));
                    
                    lowestLLSinceLastHHAfterBos_H1 = -1;
                    time_lastHHAfterBos_H1         = rates_H1[i].time;
                    PrintFormat("🔄 H1: [HH After BoS Confirmed] Reset pencarian LL terendah. Waktu referensi HH: %s", TimeToString(time_lastHHAfterBos_H1));
                }
            }        
            else
            {
                if (rates_H1[i].high > lastAcceptedHH_H1)
                {
                    double oldHH = lastAcceptedHH_H1;
                    lastAcceptedHH_H1 = rates_H1[i].high;
                    PrintFormat("✅ H1: [MODE 1] Update Last Accepted HH (Default): %s | Time: %s", DoubleToString(lastAcceptedHH_H1, _Digits), TimeToString(rates_H1[i].time));
                    UpdateAcceptedLevelVisuals_H1(lastAcceptedHH_H1, "HH", rates_H1[i].time);
                    
                    // SAVE HH UPDATE
                    SaveLLHHBOSToArray("HH", "Bullish", lastAcceptedHH_H1, rates_H1[i].time, "H1", "Updated", oldHH, 0);
                }
            }  

            if (bosBullishConfirmedFlag_H1 && hhAfterBosConfirmedFlag_H1 && rates_H1[i].high < lastAcceptedHH_H1)
            {
                PrintFormat("❌ H1: [MODE 2.1 REJECTED] HH %.2f DITOLAK karena < Lebih rendah dari BoS + HH %.2f | Time: %s",
                        rates_H1[i].high, lastAcceptedHH_H1, TimeToString(rates_H1[i].time));
                if (ObjectFind(0, boxName_H1) >= 0) ObjectDelete(0, boxName_H1);
            }

            // --- BoS Bullish Confirmed, terbentuk HH valid sebagai target BoS Bullish H1 ---
            if (hhAfterChochConfirmedFlag_H1 && bosBullishConfirmedFlag_H1 && isInTrendBullish_H1 && rates_H1[i].high > lastAcceptedHH_H1)
            {
                postChoCH_HH_H1      = rates_H1[i].high;
                time_postChoCH_HH_H1 = rates_H1[i].time;
            }

            // --- HH After BoS Confirmed H1 ---
            if (hhAfterBosConfirmedFlag_H1 && postChoCH_HH_H1 > 0 && rates_H1[i].high < postChoCH_HH_H1)
            {
                if (rates_H1[i].high != lastLoggedDeniedHH_H1 || TimeCurrent() - lastLoggedDeniedHHLogTime_H1 > deniedLogIntervalSeconds_H1)
                {
                    PrintFormat("❌ H1: [REJECTED] HH %.2f DITOLAK karena < Lebih rendah dari postCHoCH_HH %.2f | Time: %s",
                            rates_H1[i].high, postChoCH_HH_H1, TimeToString(rates_H1[i].time));
                    if (ObjectFind(0, boxName_H1) >= 0) ObjectDelete(0, boxName_H1);
                    lastLoggedDeniedHH_H1        = rates_H1[i].high;
                    lastLoggedDeniedHHBarTime_H1 = rates_H1[i].time;
                    lastLoggedDeniedHHLogTime_H1 = TimeCurrent();
                }
                continue;
            }
            
            // --- MODE MENUJU TREND BEARISH H1 ---
            // Setelah CHoCH Bearish, HH baru yang terbentuk SETELAH waktu CHoCH boleh menjadi HH baru
            if (chochBearish_H1 && !llAfterChochConfirmedFlag_H1 && !bosBearishConfirmedFlag_H1) 
            {
                // Jika HH ini terbentuk SETELAH CHoCH Bearish timestamp, izinkan update sebagai HH baru
                if (rates_H1[i].time > time_choch_bearish_H1 && rates_H1[i].high > 0 && !hhAfterChochConfirmedFlag_H1)
                {
                    // HH PERTAMA setelah CHoCH Bearish - jadikan sebagai lastAcceptedHH baru untuk tren bearish
                    lastAcceptedHH_H1 = rates_H1[i].high;
                    hhAfterChochConfirmedFlag_H1 = true;
                    PrintFormat("✅ H1: [HH AFTER CHoCH BEARISH] HH baru setelah CHoCH Bearish: %.5f | Time: %s",
                                lastAcceptedHH_H1, TimeToString(rates_H1[i].time));
                    UpdateAcceptedLevelVisuals_H1(lastAcceptedHH_H1, "HH", rates_H1[i].time);
                }
                else if (rates_H1[i].high < lastAcceptedHH_H1 && hhAfterChochConfirmedFlag_H1) {
                    // HH yang lebih rendah dari HH setelah CHoCH DITOLAK
                    PrintFormat("❌ H1: [MODE 2 BEARISH] HH %.2f DITOLAK karena < HH setelah CHoCH %.2f | Time: %s",
                                rates_H1[i].high, lastAcceptedHH_H1, TimeToString(rates_H1[i].time));
                    if (ObjectFind(0, boxName_H1) >= 0) ObjectDelete(0, boxName_H1);
                }
                
                // JANGAN skip jika HH valid setelah CHoCH - hanya skip untuk HH yang ditolak
                if (rates_H1[i].time <= time_choch_bearish_H1 || (rates_H1[i].high < lastAcceptedHH_H1 && hhAfterChochConfirmedFlag_H1))
                    continue; // Lewati update HH ini HANYA jika HH sebelum CHoCH atau lebih rendah dari HH setelah CHoCH
            }

            // --- Pencarian HH tertinggi absolut setelah CHoCH Bearish dan LL sebelum BoS Bearish H1 ---
            if (chochBearish_H1 && llAfterChochConfirmedFlag_H1 && !bosBearishConfirmedFlag_H1 && rates_H1[i].time > time_choch_bearish_H1)
            {
                PrintFormat("🔍 H1: [MODE 2 BEARISH - DEBUG ENTRY] Memasuki MODE 2 Bearish. chochBearish=%s, llAfterChochConfirmedFlag=%s, bosBearishConfirmedFlag=%s",
                            chochBearish_H1 ? "true" : "false",
                            llAfterChochConfirmedFlag_H1 ? "true" : "false",
                            bosBearishConfirmedFlag_H1 ? "true" : "false");
                
                if (absoluteHighestHH_H1 == -1 || rates_H1[i].high > absoluteHighestHH_H1)
                {
                    Print("🔍 H1: [MODE 2 BEARISH - SEARCHING] Mencari HH tertinggi absolut...");

                    if (!absoluteHighFound_H1)
                    {
                        absoluteHighestHH_H1 = rates_H1[i].high;
                        timeAbsoluteHighestHH_H1 = rates_H1[i].time;
                        absoluteHighFound_H1 = true;
                        lastAcceptedHH_H1 = rates_H1[i].high;
                        PrintFormat("🎯 H1: [MODE 2 BEARISH - ABS HIGH INIT] HH Tertinggi Absolut Awal: %.2f | Time: %s", absoluteHighestHH_H1, TimeToString(timeAbsoluteHighestHH_H1));
                        UpdateAcceptedLevelVisuals_H1(lastAcceptedHH_H1, "HH", rates_H1[i].time);
                    }
                    else
                    {
                        if (rates_H1[i].high > absoluteHighestHH_H1)
                        {
                            double previousHigh = absoluteHighestHH_H1;
                            absoluteHighestHH_H1 = rates_H1[i].high;
                            timeAbsoluteHighestHH_H1 = rates_H1[i].time;
                            lastAcceptedHH_H1 = rates_H1[i].high;

                            PrintFormat("📈 H1: [MODE 2.1 BEARISH - ABS HIGH UPDATE] HH Tertinggi Absolut Diperbarui: %.2f -> %.2f | Time: %s",
                                        previousHigh, absoluteHighestHH_H1, TimeToString(timeAbsoluteHighestHH_H1));
                            UpdateAcceptedLevelVisuals_H1(lastAcceptedHH_H1, "HH", rates_H1[i].time);
                        }
                        else if (rates_H1[i].high < absoluteHighestHH_H1)
                        {
                            bearishSearchCompleted_H1 = true;
                            PrintFormat("🏁 H1: [MODE 2 BEARISH - SEARCH COMPLETE] HH tertinggi absolut ditemukan: %.2f. Pencarian dihentikan.", absoluteHighestHH_H1);
                            PrintFormat("🔍 H1: [MODE 2 BEARISH - FOUND LOWER] HH %.2f < HH tertinggi (%.2f) ditemukan. Menolak dan menghentikan pencarian HH tertinggi.",
                                        rates_H1[i].high, absoluteHighestHH_H1);
                            if (ObjectFind(0, boxName_H1) >= 0) ObjectDelete(0, boxName_H1);
                        }
                        else
                        {
                            PrintFormat("ℹ️ H1: [MODE 2 BEARISH] HH %.2f sama dengan HH Tertinggi Absolut (%.2f) | Time: %s",
                                        rates_H1[i].high, absoluteHighestHH_H1, TimeToString(rates_H1[i].time));
                        }
                    }
                }
                else
                {
                    if (rates_H1[i].high < absoluteHighestHH_H1)
                    {
                        PrintFormat("❌ H1: [MODE 2 BEARISH - POST SEARCH REJECTED] HH %.2f DITOLAK karena < HH Tertinggi Absolut (%.2f) setelah pencarian selesai | Time: %s",
                                    rates_H1[i].high, absoluteHighestHH_H1, TimeToString(rates_H1[i].time));
                        if (ObjectFind(0, boxName_H1) >= 0) ObjectDelete(0, boxName_H1);            
                    }
                    else if (rates_H1[i].high > absoluteHighestHH_H1)
                    {
                        PrintFormat("⚠️ H1: [MODE 2 BEARISH - POST SEARCH] HH %.2f > HH Tertinggi Absolut (%.2f) setelah pencarian selesai. | Time: %s",
                                    rates_H1[i].high, absoluteHighestHH_H1, TimeToString(rates_H1[i].time));
                    }
                    else
                    {
                        PrintFormat("ℹ️ H1: [MODE 2 BEARISH - POST SEARCH] HH %.2f sama dengan HH Tertinggi Absolut (%.2f) | Time: %s",
                                    rates_H1[i].high, absoluteHighestHH_H1, TimeToString(rates_H1[i].time));
                    }
                }

                PrintFormat("🔧 H1: [MODE 2 BEARISH STATE] absoluteHighestHH=%.2f | bearishSearchCompleted=%s | absoluteHighFound=%s",
                            absoluteHighestHH_H1,
                            bearishSearchCompleted_H1 ? "true" : "false",
                            absoluteHighFound_H1 ? "true" : "false");
            }
            
            // --- MODE 3 BEARISH: Setelah BoS Bearish + SEBELUM LL After BoS Terkonfirmasi H1 ---
            if (bosBearishConfirmedFlag_H1 && isInTrendBearish_H1 && !llAfterBosConfirmedFlag_H1)
            {
                if (rates_H1[i].time <= timeBoSBearish_H1)
                {
                    double previousHH = lastAcceptedHH_H1;
                    lastAcceptedHH_H1 = rates_H1[i].high;
                    PrintFormat("✅ H1: [MODE 3] Update last Accepted HH sebelum Bos dan paling tinggi (Belum Ada LL After BoS): %.2f < HH_sebelumnya (%.2f) | Time: %s",
                                lastAcceptedHH_H1, previousHH, TimeToString(rates_H1[i].time));
                    UpdateAcceptedLevelVisuals_H1(lastAcceptedHH_H1, "HH", rates_H1[i].time);
                    continue;
                }
                
                if (rates_H1[i].high > lastAcceptedHH_H1)
                {
                    double previousHH = lastAcceptedHH_H1;
                    lastAcceptedHH_H1 = rates_H1[i].high;
                    PrintFormat("✅ H1: [MODE 3] Update last Accepted HH After Bos (Belum Ada LL After BoS): %.2f > HH_sebelumnya (%.2f) | Time: %s",
                                lastAcceptedHH_H1, previousHH, TimeToString(rates_H1[i].time));
                    UpdateAcceptedLevelVisuals_H1(lastAcceptedHH_H1, "HH", rates_H1[i].time);
                    
                    postChoCH_HH_H1 = rates_H1[i].high;
                    time_postChoCH_HH_H1 = rates_H1[i].time;
                    PrintFormat("🎯 H1: [MODE 3] BoS Bearish Target HH set ke: %.2f @ %s", 
                                postChoCH_HH_H1, TimeToString(time_postChoCH_HH_H1));
                }
                else
                {
                    PrintFormat("❌ H1: [MODE 3 BEARISH - REJECTED] HH %.2f DITOLAK karena <= HH terakhir (%.2f) | Time: %s",
                                rates_H1[i].high, lastAcceptedHH_H1, TimeToString(rates_H1[i].time));
                    if (ObjectFind(0, boxName_H1) >= 0) ObjectDelete(0, boxName_H1);
                }
                continue;
            }
            
            // --- MODE 3 BEARISH: Setelah BoS Bearish + LL After BoS Terkonfirmasi H1 ---
            if (bosBearishConfirmedFlag_H1 && llAfterBosConfirmedFlag_H1)
            {
                if (rates_H1[i].time <= time_postChoCH_LL_H1)
                {
                    PrintFormat("ℹ️ H1: [MODE 3 BEARISH] HH diabaikan (terbentuk sebelum BoS Bearish terpicu @ %s): %.2f @ %s",
                                TimeToString(time_postChoCH_LL_H1), rates_H1[i].high, TimeToString(rates_H1[i].time));
                    string boxNameIgnored = "H1_zone_hh_" + IntegerToString((int)rates_H1[i].time);
                    if (ObjectFind(0, boxNameIgnored) >= 0) ObjectDelete(0, boxNameIgnored);
                    continue;
                }

                if (rates_H1[i].time > time_lastAcceptedLLTime_H1)
                {
                    if (absoluteHighestHH_H1 == -1 || rates_H1[i].high > absoluteHighestHH_H1)
                    {
                        double previousHH = absoluteHighestHH_H1;
                        absoluteHighestHH_H1 = rates_H1[i].high;
                        timeAbsoluteHighestHH_H1 = rates_H1[i].time;

                        if (previousHH == -1)
                        {
                            PrintFormat("📈 H1: [MODE 3 BEARISH] Inisialisasi HH tertinggi sejak LL terakhir (%s): %.2f @ %s",
                                        TimeToString(time_lastAcceptedLLTime_H1), absoluteHighestHH_H1, TimeToString(rates_H1[i].time));
                        }
                        else
                        {
                            PrintFormat("📈 H1: [MODE 3 BEARISH] Update HH tertinggi sejak LL terakhir (%s): %.2f -> %.2f @ %s",
                                        TimeToString(time_lastAcceptedLLTime_H1), previousHH, absoluteHighestHH_H1, TimeToString(rates_H1[i].time));
                        }
                    }
                }

                bool   hhRejected_H1   = false;
                string rejectReason_H1 = "";

                if (absoluteHighestHH_H1 != -1 && rates_H1[i].time > time_lastAcceptedLLTime_H1)
                {
                    if (rates_H1[i].high < absoluteHighestHH_H1)
                    {
                        hhRejected_H1   = true;
                        rejectReason_H1 = "lebih rendah dari HH tertinggi sejak LL terakhir";
                    }
                }

                bool isLowerHigh_H1 = false;
                if (rates_H1[i].high < lastAcceptedHH_H1)
                {
                    isLowerHigh_H1 = true;
                }

                if (hhRejected_H1)
                {
                    PrintFormat("❌ H1: [MODE 3 BEARISH - REJECTED by Abs High] HH %.2f DITOLAK karena %s (%.2f) | Time: %s",
                                rates_H1[i].high, rejectReason_H1, absoluteHighestHH_H1, TimeToString(rates_H1[i].time));
                    string boxNameRejected = "H1_zone_hh_" + IntegerToString((int)rates_H1[i].time);
                    if (ObjectFind(0, boxNameRejected) >= 0) ObjectDelete(0, boxNameRejected);
                }
                else if (isLowerHigh_H1)
                {
                    double previousHH = lastAcceptedHH_H1;
                    lastAcceptedHH_H1 = rates_H1[i].high;

                    PrintFormat("✅ H1: [MODE 3 BEARISH] Init/Update LH After BoS + LL : %.2f < HH_sebelumnya (%.2f) | Time: %s",
                                lastAcceptedHH_H1, previousHH, TimeToString(rates_H1[i].time));

                    hhBeforellAfterBos_H1       = lastAcceptedHH_H1;
                    timehhBeforellAfterBos_H1   = rates_H1[i].time;
                    llBeforeHHAfterBosSaved_H1  = true;

                    PrintFormat("💾 H1: [MODE 3 BEARISH - UPDATE] LH %.2f disimpan sebagai referensi baru (hhBeforellAfterBos) | Time: %s",
                                hhBeforellAfterBos_H1, TimeToString(timehhBeforellAfterBos_H1));

                    UpdateAcceptedLevelVisuals_H1(lastAcceptedHH_H1, "HH", rates_H1[i].time);
                }
                else if (rates_H1[i].high > lastAcceptedHH_H1)
                {
                    PrintFormat("❌ H1: [MODE 3 BEARISH - REJECTED by LH] HH %.2f DITOLAK karena lebih tinggi dari LH terakhir (%.2f) | Time: %s",
                                rates_H1[i].high, lastAcceptedHH_H1, TimeToString(rates_H1[i].time));
                    string boxNameRejected = "H1_zone_hh_" + IntegerToString((int)rates_H1[i].time);
                    if (ObjectFind(0, boxNameRejected) >= 0) ObjectDelete(0, boxNameRejected);
                }
                else
                {
                    PrintFormat("ℹ️ H1: [MODE 3 BEARISH] HH %.2f sama dengan LH terakhir (%.2f) | Time: %s",
                                rates_H1[i].high, lastAcceptedHH_H1, TimeToString(rates_H1[i].time));
                }

                continue;
            }

        }
        
        // --- Process Low (LL) H1 ---
        if (isLow_H1)
        {
            // --- Basic Logging & Spam Prevention H1 ---
            if (rates_H1[i].time <= lastProcessedTime_LL_H1) continue;
            lastProcessedTime_LL_H1 = rates_H1[i].time;
            if (rates_H1[i].low == lastLoggedValidLL_H1 && rates_H1[i].time == lastLoggedValidLLTime_H1) continue;
            
            PrintFormat("✅ H1: LL VALID TERBENTUK: %.2f | Time: %s", rates_H1[i].low, TimeToString(rates_H1[i].time));
            
            lastLoggedValidLL_H1     = rates_H1[i].low;
            lastLoggedValidLLTime_H1 = rates_H1[i].time;
            
            // --- Visual Drawing (Zona LL) H1 ---
            datetime startTime_H1 = rates_H1[i].time;
            datetime endTime_H1   = startTime_H1 + PeriodSeconds() * ZoneLength_H1;
            string   boxName_H1   = "H1_zone_ll_" + IntegerToString((int)rates_H1[i].time);
            
            ObjectCreate(0, boxName_H1, OBJ_RECTANGLE, 0, startTime_H1, rates_H1[i].low - 3 * _Point, endTime_H1, rates_H1[i].low);
            ObjectSetInteger(0, boxName_H1, OBJPROP_COLOR, clrGreen);
            ObjectSetInteger(0, boxName_H1, OBJPROP_BACK, true);
            
            //----------------------------------------------------------------------+
            // ⚠️ [NO MAN'S LAND REJECTION] Tolak LL saat menunggu HH setelah BoS H1  |
            // Syarat: BoS Bullish sudah terkonfirmasi TETAPI HH After BoS BELUM      |
            // NAMUN: Terima LL yang terbentuk SEBELUM BoS dikonfirmasi (valid swing) |
            //----------------------------------------------------------------------+
            if (bosBullishConfirmedFlag_H1 && !hhAfterBosConfirmedFlag_H1 && rates_H1[i].time > timeBoSBullish_H1)
            {
                PrintFormat("❌ H1: [WAITING FOR HH - REJECTED] LL %.2f DITOLAK karena terbentuk SETELAH BoS dikonfirmasi dalam fase 'Waiting for HH' | Time: %s | Status: bosBullish=true, hhAfterBos=false, LL time > BoS time",
                            rates_H1[i].low, TimeToString(rates_H1[i].time));
                if (ObjectFind(0, boxName_H1) >= 0) ObjectDelete(0, boxName_H1);
                continue; // Skip pemrosesan lebih lanjut untuk LL ini
            }
            
            // --- MODE MENUJU TREND BEARISH H1 ---
            if (chochBearish_H1 && !isInTrendBearish_H1)
            {
                if (!llAfterChochConfirmedFlag_H1) 
                {
                    lastAcceptedLL_H1 = rates_H1[i].low;
                    UpdateAcceptedLevelVisuals_H1(lastAcceptedHH_H1, "HH", rates_H1[i].time);
                    UpdateAcceptedLevelVisuals_H1(lastAcceptedLL_H1, "LL", rates_H1[i].time);
                    
                    postChoCH_LL_H1              = rates_H1[i].low;
                    time_postChoCH_LL_H1         = rates_H1[i].time;
                    chochBearishConfirmedFlag_H1 = true;
                    llAfterChochConfirmedFlag_H1 = true;
                    bosBearishConfirmedFlag_H1   = false;
                    llAfterBosConfirmedFlag_H1   = false;
                    
                    // SAVE CHoCH DATA
                    SaveLLHHBOSToArray("CHoCH", "Bearish", lastAcceptedLL_H1, rates_H1[i].time, "H1", "Confirmed", preChochHH_H1, 0);
                    SaveLLHHBOSToArray("HH", "Reference", preChochHH_H1, rates_H1[i].time, "H1", "PreChoCH", 0, 0);
                    
                    PrintFormat("✅ H1: [MODE 1 RESET] CHoCH Bearish dan LL After CHoCH terkonfirmasi. last Accepted HH direset ke Pre ChoCH HH=%.2f | HH Baru=%.2f @ %s", 
                            preChochHH_H1, rates_H1[i].high, TimeToString(rates_H1[i].time));
                    
                    previousLLBoxName_H1 = "H1_zone_ll_" + IntegerToString((int)rates_H1[i].time);

                    continue;
                }
                else if (rates_H1[i].low < lastAcceptedLL_H1) 
                {
                    lastAcceptedLL_H1 = rates_H1[i].low;
                    PrintFormat("✅ H1: [MODE 1.2] Update Last Accepted LL Lebih Rendah: %.2f | Time: %s",
                            lastAcceptedLL_H1, TimeToString(rates_H1[i].time));
                    if (ObjectFind(0, previousLLBoxName_H1) >= 0)
                        ObjectDelete(0, previousLLBoxName_H1);

                    UpdateAcceptedLevelVisuals_H1(lastAcceptedLL_H1, "LL", rates_H1[i].time);
                }
                else if (rates_H1[i].low > lastAcceptedLL_H1) 
                {
                    PrintFormat("❌ H1: [REJECTED] LL %.2f DITOLAK karena > Lebih Tinggi dari CHoCH+LL last Accepted LL %.2f | Time: %s",
                            rates_H1[i].low, lastAcceptedLL_H1, TimeToString(rates_H1[i].time));
                    if (ObjectFind(0, boxName_H1) >= 0) ObjectDelete(0, boxName_H1);
                }
            }

            if (chochBullish_H1 && !isInTrendBullish_H1 && !hhAfterChochConfirmedFlag_H1)
            {
                if (rates_H1[i].low > preChochLL_H1)
                {
                    PrintFormat("❌ H1: [REJECTED] LL %.2f > preChochLL %.2f | Time: %s",
                                rates_H1[i].low, preChochLL_H1, TimeToString(rates_H1[i].time));
                    ObjectDelete(0, boxName_H1);
                    continue;
                }
            }

            // --- CHoCH Bearish Confirmed, terbentuk LL valid sebagai target BoS Bearish H1 ---
            if (chochBearish_H1 && !isInTrendBearish_H1 && !llAfterChochConfirmedFlag_H1 && rates_H1[i].low < lastAcceptedLL_H1)
            {
                postChoCH_LL_H1      = rates_H1[i].low;
                time_postChoCH_LL_H1 = rates_H1[i].time;
                PrintFormat("🎯 H1: [TARGET SET] BoS Bearish Target LL set ke: %.2f @ %s", postChoCH_LL_H1, TimeToString(time_postChoCH_LL_H1));
            } 

            if (chochBearish_H1 && isInTrendBearish_H1 && rates_H1[i].low < lastAcceptedLL_H1)
            {
                postChoCH_LL_H1      = rates_H1[i].low;
                time_postChoCH_LL_H1 = rates_H1[i].time;
                PrintFormat("🎯 H1: [TARGET SET] BoS Bearish Target LL set ke: %.2f @ %s", postChoCH_LL_H1, TimeToString(time_postChoCH_LL_H1));
            }

            // --- Bos Bearish Confirmed, terbentuk LL valid sebagai target BoS Bearish H1 ---
            if (bosBearishConfirmedFlag_H1 && isInTrendBearish_H1)
            {
                if (rates_H1[i].low < lastAcceptedLL_H1)
                {
                    double oldLL = lastAcceptedLL_H1;
                    lastAcceptedLL_H1 = rates_H1[i].low;
                    PrintFormat("✅ H1: [MODE 2.2]Update last Accepted LL After Bos: %s | Time: %s", DoubleToString(lastAcceptedLL_H1, _Digits), TimeToString(rates_H1[i].time));
                    UpdateAcceptedLevelVisuals_H1(lastAcceptedLL_H1, "LL", rates_H1[i].time);
                    llAfterBosConfirmedFlag_H1 = true;
                    postChoCH_LL_H1            = rates_H1[i].low;
                    
                    // SAVE LL UPDATE
                    SaveLLHHBOSToArray("LL", "Bearish", lastAcceptedLL_H1, rates_H1[i].time, "H1", "Updated", oldLL, 0);
                    
                    PrintFormat("✅ H1: Post CHoCH LL: %s | Time: %s", DoubleToString(postChoCH_LL_H1, _Digits), TimeToString(rates_H1[i].time));
                    PrintFormat("✅ H1: LL After BoS Confirmed: %s | Time: %s", DoubleToString(lastAcceptedLL_H1, _Digits), TimeToString(rates_H1[i].time));
                }
                else if (rates_H1[i].low < lastAcceptedLL_H1) 
                {
                    double oldLL = lastAcceptedLL_H1;
                    lastAcceptedLL_H1 = rates_H1[i].low;
                    PrintFormat("✅ H1: [MODE 1.2] Update Last Accepted LL Lebih Rendah: %.2f | Time: %s",
                            lastAcceptedLL_H1, TimeToString(rates_H1[i].time));
                    if (ObjectFind(0, previousLLBoxName_H1) >= 0)
                        ObjectDelete(0, previousLLBoxName_H1);

                    // SAVE LL UPDATE
                    SaveLLHHBOSToArray("LL", "Bearish", lastAcceptedLL_H1, rates_H1[i].time, "H1", "Updated", oldLL, 0);
                    
                    UpdateAcceptedLevelVisuals_H1(lastAcceptedLL_H1, "LL", rates_H1[i].time);
                }
                else if (rates_H1[i].low > lastAcceptedLL_H1) 
                {
                    PrintFormat("❌ H1: [REJECTED] LL %.2f DITOLAK karena > Lebih Tinggi dari BoS+LL last Accepted LL %.2f | Time: %s",
                            rates_H1[i].low, lastAcceptedLL_H1, TimeToString(rates_H1[i].time));
                    if (ObjectFind(0, boxName_H1) >= 0) ObjectDelete(0, boxName_H1);
                }
            }  

            // --- MODE MENUJU TREND BULLISH H1 ---
            if (!hhAfterChochConfirmedFlag_H1 && !chochBullish_H1 && !llAfterChochConfirmedFlag_H1 && !chochBearish_H1) 
            {
                if (lastAcceptedLL_H1 == -1 || rates_H1[i].low < lastAcceptedLL_H1) 
                {
                    double oldLL = lastAcceptedLL_H1;
                    lastAcceptedLL_H1 = rates_H1[i].low;
                    Print("✅ H1: [MODE 1] Update LL (Pre-CHoCH): ", lastAcceptedLL_H1);
                    UpdateAcceptedLevelVisuals_H1(lastAcceptedLL_H1, "LL", rates_H1[i].time);
                    
                    // SAVE LL UPDATE
                    if (oldLL != -1) 
                        SaveLLHHBOSToArray("LL", "Bearish", lastAcceptedLL_H1, rates_H1[i].time, "H1", "Updated", oldLL, 0);
                }
                else
                {
                    Print("❌ H1: [MODE 1 REJECTED] LL lebih tinggi dari PreChoCh LL: = ", lastAcceptedLL_H1);
                    if (ObjectFind(0, boxName_H1) >= 0) ObjectDelete(0, boxName_H1);
                    lastLoggedDeniedLL_H1 = rates_H1[i].low;
                }
                continue;
            }

            if (!hhAfterChochConfirmedFlag_H1 && chochBullish_H1 && !llAfterChochConfirmedFlag_H1 && !chochBearish_H1) 
            {
                if (lastAcceptedLL_H1 == -1 || rates_H1[i].low < lastAcceptedLL_H1) 
                {
                    Print("❌ H1: [MODE 1 REJECTED] LL lebih tinggi dari PreChoCh LL: = ", lastAcceptedLL_H1);
                    if (ObjectFind(0, boxName_H1) >= 0) ObjectDelete(0, boxName_H1);
                    lastLoggedDeniedLL_H1 = rates_H1[i].low;
                }
                continue;
            }

            // --- Setelah CHoCH dan HH, cari LL terendah sebelum BoS Bullish H1 ---
            if ((chochBullish_H1 || hhAfterChochConfirmedFlag_H1) && 
                (!bosBullishConfirmedFlag_H1 || rates_H1[i].time < timeBoSBullish_H1))
            {
                PrintFormat("🔍 H1: [MODE 2 - DEBUG ENTRY] Memasuki MODE 2. chochBullish=%s, hhAfterChochConfirmedFlag=%s, bosBullishConfirmedFlag=%s",
                            chochBullish_H1 ? "true" : "false",
                            hhAfterChochConfirmedFlag_H1 ? "true" : "false",
                            bosBullishConfirmedFlag_H1 ? "true" : "false");

                if (!searchCompleted_H1)
                {
                    PrintFormat("🔍 H1: [MODE 2 - SEARCHING] Mencari LL terendah absolut...");

                    if (!absoluteLowFound_H1)
                    {
                        absoluteLowestLL_H1 = rates_H1[i].low;
                        timeAbsoluteLowestLL_H1 = rates_H1[i].time;
                        absoluteLowFound_H1 = true;
                        lastAcceptedLL_H1 = rates_H1[i].low;
                        previousLLBoxName_H1 = "H1_zone_ll_" + IntegerToString((int)rates_H1[i].time);

                        PrintFormat("🎯 H1: [MODE 2 - ABS LOW INIT] LL Terendah Absolut Awal: %.2f | Time: %s", absoluteLowestLL_H1, TimeToString(timeAbsoluteLowestLL_H1));
                        UpdateAcceptedLevelVisuals_H1(lastAcceptedLL_H1, "LL", rates_H1[i].time);
                    }
                    else
                    {
                        if (rates_H1[i].low < absoluteLowestLL_H1)
                        {
                            if (ObjectFind(0, previousLLBoxName_H1) >= 0)
                                ObjectDelete(0, previousLLBoxName_H1);

                            double previousLow = absoluteLowestLL_H1;
                            absoluteLowestLL_H1 = rates_H1[i].low;
                            timeAbsoluteLowestLL_H1 = rates_H1[i].time;
                            lastAcceptedLL_H1 = rates_H1[i].low;

                            PrintFormat("📉 H1: [MODE 2.1 - ABS LOW UPDATE] LL Terendah Absolut Diperbarui: %.2f -> %.2f | Time: %s",
                                        previousLow, absoluteLowestLL_H1, TimeToString(timeAbsoluteLowestLL_H1));
                            UpdateAcceptedLevelVisuals_H1(lastAcceptedLL_H1, "LL", rates_H1[i].time);
                        }
                        else if (rates_H1[i].low > absoluteLowestLL_H1)
                        {
                            searchCompleted_H1 = true;
                            PrintFormat("🏁 H1: [MODE 2 - SEARCH COMPLETE] LL terendah absolut ditemukan: %.2f. Pencarian dihentikan.", absoluteLowestLL_H1);
                            PrintFormat("🔍 H1: [MODE 2 - FOUND HIGHER] LL %.2f > LL terendah (%.2f) ditemukan. Menolak dan menghentikan pencarian LL terendah.", rates_H1[i].low, absoluteLowestLL_H1);
                            string boxNameRejected = "H1_zone_ll_" + IntegerToString((int)rates_H1[i].time);
                            if (ObjectFind(0, boxNameRejected) >= 0) ObjectDelete(0, boxNameRejected);
                        }
                        else
                        {
                            PrintFormat("ℹ️ H1: [MODE 2] LL %.2f sama dengan LL Terendah Absolut (%.2f) | Time: %s",
                                        rates_H1[i].low, absoluteLowestLL_H1, TimeToString(rates_H1[i].time));
                        }
                    }
                }
                else
                {
                    if (rates_H1[i].low > absoluteLowestLL_H1)
                    {
                         PrintFormat("❌ H1: [MODE 2 - POST SEARCH REJECTED] LL %.2f DITOLAK karena > LL Terendah Absolut (%.2f) setelah pencarian selesai | Time: %s",
                                     rates_H1[i].low, absoluteLowestLL_H1, TimeToString(rates_H1[i].time));
                         string boxNameRejected = "H1_zone_ll_" + IntegerToString((int)rates_H1[i].time);
                         if (ObjectFind(0, boxNameRejected) >= 0) ObjectDelete(0, boxNameRejected);
                    }
                    else if (rates_H1[i].low < absoluteLowestLL_H1)
                    {
                         PrintFormat("⚠️ H1: [MODE 2 - POST SEARCH] LL %.2f < LL Terendah Absolut (%.2f) setelah pencarian selesai. Kemungkinan data baru atau error. | Time: %s",
                                     rates_H1[i].low, absoluteLowestLL_H1, TimeToString(rates_H1[i].time));
                    }
                    else
                    {
                         PrintFormat("ℹ️ H1: [MODE 2 - POST SEARCH] LL %.2f sama dengan LL Terendah Absolut (%.2f) | Time: %s",
                                     rates_H1[i].low, absoluteLowestLL_H1, TimeToString(rates_H1[i].time));
                    }
                }
                
                PrintFormat("🔧 H1: [MODE 2 STATE] absoluteLowestLL=%.2f | searchCompleted=%s | absoluteLowFound=%s",
                            absoluteLowestLL_H1,
                            searchCompleted_H1 ? "true" : "false",
                            absoluteLowFound_H1 ? "true" : "false"
                           );
            }
            
            // === PERBAIKAN H1: Menghapus penolakan awal yang salah berdasarkan absoluteLowestLL_H1 ===
            // Setelah BoS Bullish terkonfirmasi, kita mencari Higher Low relatif terhadap lastAcceptedLL_H1,
            // bukan berdasarkan absoluteLowestLL_H1 (yang merupakan data MODE 2).
            // Logika validasi yang benar ada di blok MODE 3 di bawah.
            
            // --- MODE 3: Setelah BoS Bullish + HH After BoS Terkonfirmasi H1 ---
            if (bosBullishConfirmedFlag_H1 && hhAfterBosConfirmedFlag_H1)
            {
                if (rates_H1[i].time <= time_postChoCH_HH_H1)
                {
                    PrintFormat("ℹ️ H1: [MODE 3] LL diabaikan (terbentuk sebelum BoS Bullish terpicu @ %s): %.2f @ %s",
                                TimeToString(time_postChoCH_HH_H1), rates_H1[i].low, TimeToString(rates_H1[i].time));
                    string boxNameIgnored = "H1_zone_ll_" + IntegerToString((int)rates_H1[i].time);
                    if (ObjectFind(0, boxNameIgnored) >= 0) ObjectDelete(0, boxNameIgnored);
                    continue;
                }
                
                if (rates_H1[i].time > time_lastHHAfterBos_H1)
                {
                    if (lowestLLSinceLastHHAfterBos_H1 == -1 || rates_H1[i].low < lowestLLSinceLastHHAfterBos_H1)
                    {
                        double previousLowest = lowestLLSinceLastHHAfterBos_H1;
                        lowestLLSinceLastHHAfterBos_H1 = rates_H1[i].low;
                        
                        if(previousLowest == -1)
                        {
                            PrintFormat("📉 H1: [MODE 3] Inisialisasi LL terendah sejak HH terakhir (%s): %.2f @ %s",
                                        TimeToString(time_lastHHAfterBos_H1), lowestLLSinceLastHHAfterBos_H1, TimeToString(rates_H1[i].time));
                        } 
                        else 
                        {
                            PrintFormat("📉 H1: [MODE 3] Update LL terendah sejak HH terakhir (%s): %.2f -> %.2f @ %s",
                                        TimeToString(time_lastHHAfterBos_H1), previousLowest, lowestLLSinceLastHHAfterBos_H1, TimeToString(rates_H1[i].time));
                        }
                    }
                }
                
                bool   llRejected_H1   = false;
                string rejectReason_H1 = "";
                
                if (lowestLLSinceLastHHAfterBos_H1 != -1 && rates_H1[i].time > time_lastHHAfterBos_H1)
                {
                    if (rates_H1[i].low > lowestLLSinceLastHHAfterBos_H1)
                    {
                        llRejected_H1   = true;
                        rejectReason_H1 = "lebih tinggi dari LL terendah absolut sejak HH terakhir";
                    }
                }
                
                bool isHigherLow_H1 = false;
                if (rates_H1[i].low > lastAcceptedLL_H1)
                {
                    isHigherLow_H1 = true;
                }
                
                if (llRejected_H1)
                {
                    PrintFormat("❌ H1: [MODE 3 - REJECTED by Abs Low] LL %.2f DITOLAK karena %s (%.2f) | Time: %s",
                                rates_H1[i].low, rejectReason_H1, lowestLLSinceLastHHAfterBos_H1, TimeToString(rates_H1[i].time));
                    string boxNameRejected = "H1_zone_ll_" + IntegerToString((int)rates_H1[i].time);
                    if (ObjectFind(0, boxNameRejected) >= 0) ObjectDelete(0, boxNameRejected);
                }
                else if (isHigherLow_H1)
                {
                    double previousLL = lastAcceptedLL_H1;
                    lastAcceptedLL_H1 = rates_H1[i].low;
                    
                    PrintFormat("✅ H1: [MODE 3] Init/Update HL After BoS + HH : %.2f > LL_sebelumnya (%.2f) | Time: %s",
                                lastAcceptedLL_H1, previousLL, TimeToString(rates_H1[i].time));
                    
                    llBeforeHHAfterBos_H1      = lastAcceptedLL_H1;
                    timeLLBeforeHHAfterBos_H1  = rates_H1[i].time;
                    llBeforeHHAfterBosSaved_H1 = true;
                    
                    PrintFormat("💾 H1: [MODE 3 - UPDATE] HL %.2f disimpan sebagai referensi baru (llBeforeHHAfterBos) | Time: %s",
                                llBeforeHHAfterBos_H1, TimeToString(timeLLBeforeHHAfterBos_H1));
                    
                    PrintFormat("bosBullishConfirmedFlag: %s | hhAfterBosConfirmedFlag: %s",
                                bosBullishConfirmedFlag_H1 ? "True": "False",
                                hhAfterBosConfirmedFlag_H1 ? "True": "False");
                    UpdateAcceptedLevelVisuals_H1(lastAcceptedLL_H1, "LL", rates_H1[i].time);
                }
                else if (rates_H1[i].low < lastAcceptedLL_H1)
                {
                    PrintFormat("❌ H1: [MODE 3 - REJECTED by HL] LL %.2f DITOLAK karena lebih rendah dari HL terakhir (%.2f) | Time: %s",
                                rates_H1[i].low, lastAcceptedLL_H1, TimeToString(rates_H1[i].time));
                    string boxNameRejected = "H1_zone_ll_" + IntegerToString((int)rates_H1[i].time);
                    if (ObjectFind(0, boxNameRejected) >= 0) ObjectDelete(0, boxNameRejected);
                }
                else
                {
                    PrintFormat("ℹ️ H1: [MODE 3] LL %.2f sama dengan HL terakhir (%.2f) | Time: %s",
                                rates_H1[i].low, lastAcceptedLL_H1, TimeToString(rates_H1[i].time));
                }
                continue;
            }
        }
    }
    
    // --- CHoCH Bullish H1 ---
    if (!chochBullish_H1 && !isInTrendBullish_H1 &&
        (lastAcceptedHH_H1 > 0 && rates_H1[1].close > lastAcceptedHH_H1 + 50 * _Point))
    {
        double   tempHH_H1     = lastAcceptedHH_H1;
        datetime tempHHTime_H1 = lastLoggedValidHHTime_H1;
        preChochLL_H1          = lastAcceptedLL_H1;
        UpdateAcceptedLevelVisuals_H1(preChochLL_H1, "LL", rates_H1[0].time);
        
        Print("🔔🔔🔔 H1: === ⚡⚡⚡ [CHoCH BULLISH TRIGGERED] ⚡⚡⚡ === 🔔🔔🔔");
        Print("📈 H1: Close Breaks HH (Target): ", DoubleToString(lastAcceptedHH_H1, _Digits), " → CHoCH Bullish Confirmed! ", TimeToString(rates_H1[1].time));
        PrintFormat("✅ H1: [MODE 1 RESET] CHoCH Bullish terkonfirmasi. last Accepted LL direset ke preChochLL: %.2f @ %s",
                             preChochLL_H1, TimeToString(rates_H1[1].time));
        
        // Gambar garis CHoCH dari HH sebelum break ke candle H1
        string chochName_H1 = "H1_CHoCH_Bull_" + IntegerToString((int)tempHHTime_H1);
        ObjectDelete(0, chochName_H1);
        ObjectCreate(0, chochName_H1, OBJ_TREND, 0, tempHHTime_H1, tempHH_H1, rates_H1[1].time, tempHH_H1);
        ObjectSetInteger(0, chochName_H1, OBJPROP_COLOR, clrGold);
        ObjectSetInteger(0, chochName_H1, OBJPROP_WIDTH, 1);
        ObjectSetInteger(0, chochName_H1, OBJPROP_STYLE, STYLE_SOLID);
        ObjectSetInteger(0, chochName_H1, OBJPROP_BACK, true);
        
        // Label CHoCH di tengah garis H1
        string   chochLabel_H1 = chochName_H1 + "_label";
        int      shift1_H1     = iBarShift(_Symbol, PERIOD_H1, tempHHTime_H1, false);
        int      shift2_H1     = iBarShift(_Symbol, PERIOD_H1, rates_H1[1].time, false);
        int      midShift_H1   = (shift1_H1 + shift2_H1) / 2;
        datetime midTime_H1    = iTime(_Symbol, PERIOD_H1, midShift_H1);
        ObjectDelete(0, chochLabel_H1);
        ObjectCreate(0, chochLabel_H1, OBJ_TEXT, 0, midTime_H1, tempHH_H1 + 6 * _Point);
        ObjectSetInteger(0, chochLabel_H1, OBJPROP_COLOR, clrGold);
        ObjectSetInteger(0, chochLabel_H1, OBJPROP_FONTSIZE, 10);
        ObjectSetInteger(0, chochLabel_H1, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);
        ObjectSetString(0, chochLabel_H1, OBJPROP_TEXT, "H1_CHoCH");
        
        chochBullish_H1              = true;
        hhAfterChochConfirmedFlag_H1 = false;
        isInTrendBearish_H1          = false;
        chochBearish_H1              = false;
        chochBearishConfirmedFlag_H1 = false;
        llAfterChochConfirmedFlag_H1 = false;
        bosBearishConfirmedFlag_H1   = false;
        llAfterBosConfirmedFlag_H1   = false;
        bosBullishJustLogged_H1      = false;
        entryCountBuy_H1             = 0;      // Reset entry counter untuk cycle baru (Bullish)
        time_postChoCH_HH_H1         = -1;
        time_postChoCH_LL_H1         = -1;
        time_choch_bullish_H1        = rates_H1[1].time;
        time_choch_bearish_H1        = -1;
        timeBoSBearish_H1            = -1;
        postChoCH_LL_H1              = -1;
        preChochHH_H1                = -1;
        ResetMode2_H1();
        Print("🔄 H1: [CHoCH RESET] Variabel MODE 2 di-reset untuk siklus baru.");
        UpdateAcceptedLevelVisuals_H1(-1, "LL", rates_H1[1].time);
    }

    // --- CHoCH Bearish H1 ---
    if  (!chochBearish_H1 && !isInTrendBearish_H1 &&
        (lastAcceptedLL_H1 > 0 && rates_H1[1].close < lastAcceptedLL_H1 - 5 * _Point))
    {
        double   tempLL_H1     = lastAcceptedLL_H1;
        datetime tempLLTime_H1 = lastLoggedValidLLTime_H1;
        preChochHH_H1          = lastAcceptedHH_H1;
        // === PERBAIKAN: Update lastAcceptedHH_H1 ke HH terdekat terakhir yang terbentuk sebelum CHoCH Bearish ===
        lastAcceptedHH_H1 = lastLoggedValidHH_H1;                    // Update lastAcceptedHH ke HH terdekat terakhir
        UpdateAcceptedLevelVisuals_H1(lastAcceptedHH_H1, "HH", rates_H1[1].time); // Update visualisasi HH setelah update
        
        Print("🔔🔔🔔 H1: === ⚡⚡⚡ [CHoCH BEARISH TRIGGERED] ⚡⚡⚡ === 🔔🔔🔔");
        PrintFormat("📉 H1: Close Breaks LL (Target): %.5f → CHoCH Bearish Confirmed! @ %s",
                    lastAcceptedLL_H1, TimeToString(rates_H1[1].time));
        PrintFormat("✅ H1: [MODE X RESET] CHoCH Bearish terkonfirmasi. last Accepted HH diupdate ke lastLoggedValidHH: %.5f (preChochHH: %.5f) @ %s",
                    lastAcceptedHH_H1, preChochHH_H1, TimeToString(rates_H1[1].time));
        
        // Gambar garis CHoCH Bearish H1
        string chochName_H1 = "H1_CHoCH_Bear_" + IntegerToString((int)tempLLTime_H1);
        ObjectDelete(0, chochName_H1);
        ObjectCreate(0, chochName_H1, OBJ_TREND, 0, tempLLTime_H1, tempLL_H1, rates_H1[1].time, tempLL_H1);
        ObjectSetInteger(0, chochName_H1, OBJPROP_COLOR, clrOrangeRed);
        ObjectSetInteger(0, chochName_H1, OBJPROP_WIDTH, 1);
        ObjectSetInteger(0, chochName_H1, OBJPROP_STYLE, STYLE_SOLID);
        ObjectSetInteger(0, chochName_H1, OBJPROP_BACK, true);
        
        // Label CHoCH Bearish H1
        string   chochLabel_H1 = chochName_H1 + "_label";
        datetime midTime_H1 = (tempLLTime_H1 + rates_H1[1].time) / 2;
        ObjectDelete(0, chochLabel_H1);
        ObjectCreate(0, chochLabel_H1, OBJ_TEXT, 0, midTime_H1, tempLL_H1 - 6 * _Point);
        ObjectSetInteger(0, chochLabel_H1, OBJPROP_COLOR, clrOrangeRed);
        ObjectSetInteger(0, chochLabel_H1, OBJPROP_FONTSIZE, 10);
        ObjectSetInteger(0, chochLabel_H1, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
        ObjectSetString(0, chochLabel_H1, OBJPROP_TEXT, "H1_CHoCH");
        
        // Reset Flag dan Variabel terkait tren H1
        chochBearish_H1              = true;
        isInTrendBullish_H1          = false;
        chochBullish_H1              = false; 
        hhAfterChochConfirmedFlag_H1 = false;
        chochBullishConfirmedFlag_H1 = false;
        llAfterChochConfirmedFlag_H1 = false;
        bosBullishConfirmedFlag_H1   = false;
        hhAfterBosConfirmedFlag_H1   = false; 
        postChoCH_HH_H1              = -1;
        entryCountSell_H1            = 0;      // Reset entry counter untuk cycle baru (Bearish)
        time_postChoCH_HH_H1         = -1;
        time_postChoCH_LL_H1         = -1;
        postChoCH_LL_H1              = -1;
        time_choch_bearish_H1        = rates_H1[1].time;
        time_choch_bullish_H1        = -1;
        timeBoSBullish_H1            = -1;
        preChochLL_H1                = -1;
        ResetMode2Bearish_H1();
        Print("🔄 H1: [CHoCH RESET] Variabel MODE 2 di-reset");
    }

    // --- BoS Bullish H1 ---
    if (
        postChoCH_HH_H1 > 0 && time_postChoCH_HH_H1 > 0 &&
        (
            (chochBullish_H1 && !isInTrendBullish_H1 && rates_H1[1].close > postChoCH_HH_H1 + 50 * _Point) ||
            (bosBullishConfirmedFlag_H1 && hhAfterBosConfirmedFlag_H1 &&
             isInTrendBullish_H1 > 0 && rates_H1[1].close > postChoCH_HH_H1 + 50 * _Point)
        )
    )
    {
        string bosLineName_H1  = "H1_BoS_Bull_" + IntegerToString((int)time_postChoCH_HH_H1);
        string bosLabelName_H1 = bosLineName_H1 + "_label";
        
        // Gambar garis dari postChoCH_HH ke candle dan label di tengah H1
        string bosName_H1 = "H1_BoS_Bull_" + IntegerToString((int)time_postChoCH_HH_H1);
        ObjectDelete(0, bosName_H1);
        ObjectCreate(0, bosName_H1, OBJ_TREND, 0, time_postChoCH_HH_H1, postChoCH_HH_H1, rates_H1[1].time, postChoCH_HH_H1);
        ObjectSetInteger(0, bosName_H1, OBJPROP_COLOR, clrDeepSkyBlue);
        ObjectSetInteger(0, bosName_H1, OBJPROP_WIDTH, 1);
        ObjectSetInteger(0, bosName_H1, OBJPROP_STYLE, STYLE_SOLID);
        ObjectSetInteger(0, bosName_H1, OBJPROP_BACK, true);
        
        // Label BoS di tengah garis H1
        string   bosLabel_H1 = bosName_H1 + "_label";
        datetime midTime_H1  = (time_postChoCH_HH_H1 + rates_H1[1].time) / 2;
        ObjectDelete(0, bosLabel_H1);
        ObjectCreate(0, bosLabel_H1, OBJ_TEXT, 0, midTime_H1, postChoCH_HH_H1 - 7 * _Point);
        ObjectSetInteger(0, bosLabel_H1, OBJPROP_COLOR, clrDeepSkyBlue);
        ObjectSetInteger(0, bosLabel_H1, OBJPROP_FONTSIZE, 10);
        ObjectSetInteger(0, bosLabel_H1, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);
        ObjectSetString(0, bosLabel_H1, OBJPROP_TEXT, "H1_BoS");
        
        if (!bosBullishJustLogged_H1)
        {
            Print("🚀🚀🚀 H1: === 💥💥💥 [BoS BULLISH TRIGGERED] 💥💥💥 === 🚀🚀🚀");
            Print("📊 H1: Close > postChoCH_HH: ", postChoCH_HH_H1, " → BOS Bullish Confirmed! ", TimeToString(rates_H1[1].time));
            lastBoSTimeLogged_H1 = rates_H1[1].time;
        }
        
        postChoCH_HH_H1            = -1;
        time_postChoCH_HH_H1       = 0;
        bosBullishConfirmedFlag_H1 = true;
        isInTrendBullish_H1        = true;
        preChochLL_H1              = -1;
        timeBoSBullish_H1 = rates_H1[1].time;
        
        // SAVE BoS DATA
        SaveLLHHBOSToArray("BoS", "Bullish", lastAcceptedLL_H1, rates_H1[1].time, "H1", "Confirmed", lastAcceptedHH_H1, 0);
        
        if (bosBullishConfirmedFlag_H1)
        {
            PrintFormat("🔍 H1: [DEBUG BoS %d] lastAcceptedLL saat ini: %.2f", bos_counter_H1, lastAcceptedLL_H1);
            llBeforeHHAfterBos_H1      = lastAcceptedLL_H1;
            timeLLBeforeHHAfterBos_H1  = rates_H1[1].time;
            llBeforeHHAfterBosSaved_H1 = true;
            PrintFormat("💾 H1: [PERBAIKAN BoS Confirmed] LL referensi untuk Mode 3 disimpan: %.2f @ %s", llBeforeHHAfterBos_H1, TimeToString(timeLLBeforeHHAfterBos_H1));
        }
        

    } 

    // --- BoS Bearish H1 ---
    if (
        postChoCH_LL_H1 > 0 && time_postChoCH_LL_H1 > 0 &&
        !bearishSearchCompleted_H1 &&
        (
            (chochBearish_H1 && !isInTrendBearish_H1 && rates_H1[1].close < postChoCH_LL_H1 - 50 * _Point) ||
            (bosBearishConfirmedFlag_H1 && isInTrendBearish_H1 && rates_H1[1].close < postChoCH_LL_H1 - 50 * _Point)
        )
    )
    {
        string bosLineName_H1 = "H1_BoS_Bear_" + IntegerToString((int)time_postChoCH_LL_H1) + "_at_" + IntegerToString((int)rates_H1[1].time);
        string bosLabelName_H1 = bosLineName_H1 + "_label";

        // Gambar garis dari postChoCH_LL ke candle dan label di tengah H1
        ObjectDelete(0, bosLineName_H1);
        ObjectCreate(0, bosLineName_H1, OBJ_TREND, 0, time_postChoCH_LL_H1, postChoCH_LL_H1, rates_H1[1].time, postChoCH_LL_H1);
        ObjectSetInteger(0, bosLineName_H1, OBJPROP_COLOR, clrOrange);
        ObjectSetInteger(0, bosLineName_H1, OBJPROP_WIDTH, 1);
        ObjectSetInteger(0, bosLineName_H1, OBJPROP_STYLE, STYLE_SOLID);
        ObjectSetInteger(0, bosLineName_H1, OBJPROP_BACK, true);

        // Label BoS Bearish H1
        datetime midTime_H1  = (time_postChoCH_LL_H1 + rates_H1[1].time) / 2;
        ObjectDelete(0, bosLabelName_H1);
        ObjectCreate(0, bosLabelName_H1, OBJ_TEXT, 0, midTime_H1, postChoCH_LL_H1 + 7 * _Point);
        ObjectSetInteger(0, bosLabelName_H1, OBJPROP_COLOR, clrOrange);
        ObjectSetInteger(0, bosLabelName_H1, OBJPROP_FONTSIZE, 10);
        ObjectSetInteger(0, bosLabelName_H1, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
        ObjectSetString(0, bosLabelName_H1, OBJPROP_TEXT, "H1_BoS");

        // Logging dan update flag H1
        Print("🔥🔥🔥 H1: === ⚡⚡⚡ [BoS BEARISH TRIGGERED] ⚡⚡⚡ === 🔥🔥🔥");
        Print("📉 H1: Close < postChoCH_LL: ", postChoCH_LL_H1, " → BoS Bearish Confirmed! ", TimeToString(rates_H1[1].time));
        
        lastBoSTimeLogged_H1         = rates_H1[1].time;
        postChoCH_LL_H1              = -1;
        time_postChoCH_LL_H1         = -1;
        bosBearishConfirmedFlag_H1   = true;
        isInTrendBearish_H1          = true;
        
        // SAVE BoS BEARISH DATA
        SaveLLHHBOSToArray("BoS", "Bearish", lastAcceptedLL_H1, rates_H1[1].time, "H1", "Confirmed", lastAcceptedHH_H1, 0);
        timeBoSBearish_H1 = rates_H1[1].time;
        ResetMode2Bearish_H1();
        
        if (bosBearishConfirmedFlag_H1)
        {
            PrintFormat("🔍 H1: [DEBUG BoS %d] last Accepted HH saat ini: %.2f", bos_counter_H1, lastAcceptedHH_H1);
            hhBeforellAfterBos_H1      = lastAcceptedHH_H1;
            timehhBeforellAfterBos_H1  = rates_H1[1].time;
            llBeforeHHAfterBosSaved_H1 = true;
            PrintFormat("💾 H1: [PERBAIKAN BoS Confirmed] HH referensi untuk Mode 3 disimpan: %.2f @ %s", hhBeforellAfterBos_H1, TimeToString(timehhBeforellAfterBos_H1));
        }
        

    }

    // === RESET ENTRY FLAGS H1 ===
    if (!bosBullishConfirmedFlag_H1)
    {
        hasEnteredTrade_H1 = false;
    }
    if (!bosBearishConfirmedFlag_H1)
    {
        hasEnteredSellTrade_H1 = false;
    }
        
    // --- Log status flag hanya ketika ada perubahan H1 ---
    static string lastFlagStatusBullish_H1 = "";
    static string lastFlagStatusBearish_H1 = "";
    static datetime lastFlagLogTime_H1 = 0;
    
    string currentFlagStatusBullish_H1 = StringFormat(
        "H1 BULLISH FLAGS => chochBullish=%s | hhAfterChoch=%s | bosBullish=%s | inTrendBullish=%s | hhAfterBos=%s",
        chochBullish_H1 ? "true" : "false",
        hhAfterChochConfirmedFlag_H1 ? "true" : "false",
        bosBullishConfirmedFlag_H1 ? "true" : "false",
        isInTrendBullish_H1 ? "true" : "false",
        hhAfterBosConfirmedFlag_H1 ? "true" : "false");
    
    string currentFlagStatusBearish_H1 = StringFormat(
        "H1 BEARISH FLAGS => chochBearish=%s | llAfterChoch=%s | bosBearish=%s | inTrendBearish=%s | llAfterBos=%s",
        chochBearish_H1 ? "true" : "false",
        llAfterChochConfirmedFlag_H1 ? "true" : "false",
        bosBearishConfirmedFlag_H1 ? "true" : "false",
        isInTrendBearish_H1 ? "true" : "false",
        llAfterBosConfirmedFlag_H1 ? "true" : "false");
    
    if ((currentFlagStatusBullish_H1 != lastFlagStatusBullish_H1 || 
         currentFlagStatusBearish_H1 != lastFlagStatusBearish_H1) && 
        (TimeCurrent() - lastFlagLogTime_H1 >= 1))
    {
        Print("-------------------------------------------------------------------------------------------------------------------");
        Print(currentFlagStatusBullish_H1);
        Print(currentFlagStatusBearish_H1);
        Print("-------------------------------------------------------------------------------------------------------------------");
        
        lastFlagStatusBullish_H1 = currentFlagStatusBullish_H1;
        lastFlagStatusBearish_H1 = currentFlagStatusBearish_H1;
        lastFlagLogTime_H1 = TimeCurrent();
    }

    // --- Log perubahan variabel kunci sistem H1 ---
    static string lastLoggedPart1_H1 = "", lastLoggedPart2_H1 = "", lastLoggedPart3_H1 = "", lastLoggedPart4_H1 = "";
    datetime current_time_H1 = TimeCurrent();

    string part1_H1 = StringFormat(
        "H1 KEY VARS [1/4] : lastAcceptedHH=%.5f | lastAcceptedLL=%.5f | postChoCH_HH=%.5f | postChoCH_LL=%.5f",
        lastAcceptedHH_H1,
        lastAcceptedLL_H1,
        postChoCH_HH_H1,
        postChoCH_LL_H1
    );

    string part2_H1 = StringFormat(
        "H1 KEY VARS [2/4] : time_postChoCH_HH=%s | time_postChoCH_LL=%s | timeBoSBullish=%s | timeBoSBearish=%s",
        time_postChoCH_HH_H1 > 0 ? TimeToString(time_postChoCH_HH_H1, TIME_DATE|TIME_MINUTES) : "N/A",
        time_postChoCH_LL_H1 > 0 ? TimeToString(time_postChoCH_LL_H1, TIME_DATE|TIME_MINUTES) : "N/A",
        timeBoSBullish_H1 > 0 ? TimeToString(timeBoSBullish_H1, TIME_DATE|TIME_MINUTES) : "N/A",
        timeBoSBearish_H1 > 0 ? TimeToString(timeBoSBearish_H1, TIME_DATE|TIME_MINUTES) : "N/A"
    );

    string part3_H1 = StringFormat(
        "H1 KEY VARS [3/4] : time_choch_bearish=%s time_choch_bullish=%s",
        time_choch_bearish_H1 > 0 ? TimeToString(time_choch_bearish_H1, TIME_DATE|TIME_MINUTES) : "N/A",
        time_choch_bullish_H1 > 0 ? TimeToString(time_choch_bullish_H1, TIME_DATE|TIME_MINUTES) : "N/A"
    );

    string part4_H1 = StringFormat(
        "H1 KEY VARS [4/4] : preChochHH=%.5f | preChochLL=%.5f",
        preChochHH_H1,
        preChochLL_H1
    );

    if ((part1_H1 != lastLoggedPart1_H1 || part2_H1 != lastLoggedPart2_H1 || part3_H1 != lastLoggedPart3_H1 || part4_H1 != lastLoggedPart4_H1) &&
        (current_time_H1 - lastFlagLogTime_H1 >= 1))
    {
        Print("-------------------------------------------------------------------------------------------------------------------");
        Print("📊📊📊 H1: [KEY SYSTEM VARIABLES - UPDATED] 📊📊📊");
        Print(part1_H1);
        Print(part2_H1);
        Print(part3_H1);
        Print(part4_H1);
        Print("-------------------------------------------------------------------------------------------------------------------");

        lastLoggedPart1_H1 = part1_H1;
        lastLoggedPart2_H1 = part2_H1;
        lastLoggedPart3_H1 = part3_H1;
        lastLoggedPart4_H1 = part4_H1;
        lastFlagLogTime_H1 = current_time_H1;
    }
}
//+------------------------------------------------------------------+
//| Fungsi OnTick: Dieksekusi pada setiap tick harga baru M15        |
//+------------------------------------------------------------------+
void OnTick()
{
    static bool isScriptLoadedLogged_M15 = false; // Variabel statis untuk memastikan log hanya sekali
    if (!isScriptLoadedLogged_M15)
    {
        Print("✅ Script 'HH_LL_Extraction_M15.mq5' BERHASIL DIMUAT dan sedang berjalan pada timeframe M15.");
        isScriptLoadedLogged_M15 = true; // Set flag ke true agar tidak diprint lagi
    }
    //--- Ambil Data Harga M15 ---
    MqlRates rates_M15[];
    ArraySetAsSeries(rates_M15, true);
    int copied = CopyRates(_Symbol, PERIOD_M15, 0, MathMax(200, WindowSize_M15*2 + 10), rates_M15);
    if (rates_M15[0].time == lastBarTime_M15) return;
    if (copied < WindowSize_M15*2 + 1) return;
    lastBarTime_M15 = rates_M15[0].time;

    //+------------------------------------+
    //--- Pembacaan EMA200 dan Logging M15 ----|
    //+------------------------------------+
    double bufferEMA_M15[];
    if (CopyBuffer(handleEMA_M15, 0, 0, 1, bufferEMA_M15) == 1)
    {
        ema200_M15 = bufferEMA_M15[0];
        
        MqlDateTime currentBarTime_M15;
        TimeToStruct(rates_M15[0].time, currentBarTime_M15);
        
        // if (currentBarTime_M15.hour != lastLogHour_M15 && currentBarTime_M15.min == 0)
        // {
        //     PrintFormat("📈 EMA200 M15 (%s): %.5f", TimeToString(rates_M15[0].time, TIME_DATE | TIME_MINUTES), ema200_M15);
        //     lastLogHour_M15 = currentBarTime_M15.hour;
        // }
    }
    else
    {
        Print("❌ Gagal ambil nilai EMA200 untuk M15");
    }


    static bool isScriptLoadedLogged_H1 = false;
    if (!isScriptLoadedLogged_H1)
    {
        Print("✅ H1: Script 'HH_LL_Extraction_H1.mq5' BERHASIL DIMUAT dan sedang berjalan.");
        isScriptLoadedLogged_H1 = true;
    }
    
    //--- Ambil Data Harga H1 ---
    MqlRates rates_H1[];
    ArraySetAsSeries(rates_H1, true);
    if (CopyRates(_Symbol, PERIOD_H1, 0, 60, rates_H1) < WindowSize_H1 * 2 + 1) return;
    if (rates_H1[0].time == lastBarTime_H1) return;
    lastBarTime_H1 = rates_H1[0].time;

    // --- Pembacaan EMA200 dan Logging H1 ----
    double bufferEMA_H1[];
    if (CopyBuffer(handleEMA_H1, 0, 0, 1, bufferEMA_H1) == 1)
    {
        ema200_H1 = bufferEMA_H1[0];
        
        MqlDateTime currentBarTime_H1;
        TimeToStruct(rates_H1[0].time, currentBarTime_H1);

        // if (currentBarTime_H1.hour != lastLogHour_H1 && currentBarTime_H1.min == 0)
        // {
        //     PrintFormat("📈 EMA200 H1 (%s): %.5f", TimeToString(rates_H1[0].time, TIME_DATE | TIME_MINUTES), ema200_H1);
        //     lastLogHour_H1 = currentBarTime_H1.hour;
        // }
    }
    else
    {
        Print("❌ Gagal ambil nilai EMA200 untuk H1");
    }

    // FIX #3: Check for hold time constraints - force close if exceeding max hold
    ShouldForceCloseTrade(currentBuyTrade_M15);
    ShouldForceCloseTrade(currentSellTrade_M15);
    
    CheckTradeClosure_M15(currentBuyTrade_M15);
    CheckTradeClosure_M15(currentSellTrade_M15);
    
    if(Period() == PERIOD_M15)
    {
        DetectAndDraw_M15(rates_M15, /*backfillMode=*/false);
    }
    else if(Period() == PERIOD_H1)
    {
        DetectAndDraw_H1(rates_H1, /*backfillMode=*/false);
    }
    lastBarTime_M15 = rates_M15[0].time;
    lastBarTime_H1 = rates_H1[0].time;
    
    //+------------------------------------------------------------------+
    //| SESSION ZONE TRACKING - Dipanggil setiap tick                     |
    //+------------------------------------------------------------------+
    UpdateSessionZoneTracking();    // Update tracking sesi
    DrawSessionRangeShadows();      // Gambar shadow range untuk setiap session (BARU!)
    DisplaySessionInfo();           // Tampilkan info sesi di chart

}