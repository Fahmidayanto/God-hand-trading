//+------------------------------------------------------------------+
//| File: HH_LL_Extraction_M15.mq5                                  |
//| Purpose: Isolate HH/LL Detection and Horizontal Zone Drawing     |
//| Timeframe: M15 (15-minute) specific implementation              |
//| Note: This version is specifically optimized for M15 timeframe  |
//+------------------------------------------------------------------+
#include <Trade/Trade.mqh>  // Untuk fungsi trading
#include <Tools/datetime.mqh>  // Untuk manipulasi waktu

#import "kernel32.dll"
bool CopyFileW(string lpExistingFileName, string lpNewFileName, bool bFailIfExists);
bool DeleteFileW(string lpFileName);
#import

CTrade trade;  // Objek untuk eksekusi trading

//+------------------------------------------------------------------+
//| BACKTEST DATA EXPORT - Struct & Global Variables                  |
//+------------------------------------------------------------------+
struct BacktestTrade
{
    ulong     ticket;
    string    symbol;
    string    type;
    string    session;          // "BUY" atau "SELL"
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
    double    swap;          // Swap fee (dalam currency)
    string    session_name;  // Trading session (Sydney, Sydney_Tokyo_Overlap, Asia,
                             //                  Tokyo_London_Overlap, London,
                             //                  London_NewYork_Overlap, NewYork)
    bool      is_dst;        // true = trade entry saat broker dalam mode DST (GMT+3)
    string    status;        // "EXECUTED" atau "REJECTED"
    string    reject_reason; // Alasan jika ditolak, "N/A" jika dieksekusi
};

BacktestTrade g_BacktestTrades[];   // Array dinamis untuk menyimpan semua trade
int           g_TradeCount = 0;     // Jumlah trade yang tersimpan
string        g_ExportDateStr = ""; // Tanggal export (di-set sekali di OnInit)
datetime      g_LastExportDate = 0; // Tracking tanggal terakhir export untuk rolling file

//+------------------------------------------------------------------+
//| RESUME STATE - Global Variables                                  |
//+------------------------------------------------------------------+
bool     g_StateResumed = false;           // Flag apakah state berhasil di-resume
datetime g_LastProcessedBarTime_M15 = 0;   // Last processed bar time M15 (untuk skip duplicate)
datetime g_LastProcessedBarTime_H1 = 0;    // Last processed bar time H1 (untuk skip duplicate)
string   g_StateFilePath = "";             // Path ke state file

//+------------------------------------------------------------------+
//| STRUKTUR DATA UNTUK LL, HH, BOS, CHoCH                             |
//+------------------------------------------------------------------+
struct LLHHBOSData
{
    string    type;
    string    session;           // "LL", "HH", "BoS", "CHoCH"
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
    string    type;
    string    session;           // "HH" atau "LL"
    double    price;          // Harga level
    datetime  time;           // Waktu terdeteksi
    string    timeframe;      // "M15" atau "H1"
};

AcceptedLevelHistory g_AcceptedLevelHistory[];  // Array untuk menyimpan semua update HH & LL
int                  g_AcceptedLevelHistoryCount = 0; // Jumlah history yang tersimpan

// Forward declarations
void WarmUp_M15(int bars);
void WarmUp_H1(int bars);

//+------------------------------------------------------------------+
//| STRUKTUR DATA UNIFIED EVENT (untuk sorting berdasarkan waktu)      |
//+------------------------------------------------------------------+
struct UnifiedEvent
{
    datetime  time;           // Waktu untuk sorting
    string    type;
    string    session;           // "CHoCH", "BoS", "HH", "LL"
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
    // ✅ DUPLICATE CHECK: Cegah duplikasi event (type + time + timeframe)
    for (int i = 0; i < g_LLHHBOSCount; i++)
    {
        if (g_LLHHBOSData[i].type == type && 
            g_LLHHBOSData[i].time == time && 
            g_LLHHBOSData[i].timeframe == timeframe)
        {
            return; // Already exists, skip
        }
    }
    
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
}

//+------------------------------------------------------------------+
//| Simpan accepted level (HH/LL) ke history array                    |
//+------------------------------------------------------------------+
void SaveAcceptedLevelToHistory(string type, double price, datetime time, string timeframe)
{
    // ✅ DUPLICATE CHECK: Cegah duplikasi level (type + time + timeframe)
    for (int i = 0; i < g_AcceptedLevelHistoryCount; i++)
    {
        if (g_AcceptedLevelHistory[i].type == type && 
            g_AcceptedLevelHistory[i].time == time && 
            g_AcceptedLevelHistory[i].timeframe == timeframe)
        {
            return; // Already exists, skip
        }
    }
    
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
                      double spread_cost = 0, double commission = 0, double swap = 0, string session = "")
{
    for (int i = 0; i < g_TradeCount; i++)
    {
        if (g_BacktestTrades[i].ticket == ticket)
        {
            Print("[SKIP] Trade ticket sudah tersimpan, tidak disimpan ulang: ", ticket);
            return;
        }
    }

    int newSize = g_TradeCount + 1;
    ArrayResize(g_BacktestTrades, newSize);
    
    g_BacktestTrades[g_TradeCount].ticket       = ticket;
    g_BacktestTrades[g_TradeCount].symbol       = symbol;
    g_BacktestTrades[g_TradeCount].type         = type;
    g_BacktestTrades[g_TradeCount].session      = type; // "BUY" atau "SELL"
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
    g_BacktestTrades[g_TradeCount].swap         = swap;
    g_BacktestTrades[g_TradeCount].session_name = session;
    g_BacktestTrades[g_TradeCount].is_dst       = IsServerInDST(entry_time);
    g_BacktestTrades[g_TradeCount].status       = "EXECUTED";
    g_BacktestTrades[g_TradeCount].reject_reason = "N/A";
    
    g_TradeCount = newSize;
    // MT5 commission & swap are already negative numbers representing costs, so we add them.
    double net_profit = profit + commission + swap;
    PrintFormat("💾 [SAVED] Trade #%d: %s %s [%s] | Entry: %.5f | Exit: %.5f | Profit: %.2f | Commission: %.2f | Swap: %.2f | Net: %.2f",
                g_TradeCount, type, tf, session, entry_price, exit_price, profit, commission, swap, net_profit);
}

//+------------------------------------------------------------------+
//| Rekam entry yang ditolak filter ke array BacktestTrades          |
//+------------------------------------------------------------------+
void RecordRejectedToBacktestTrades(string type, double price, string reason)
{
    int newSize = g_TradeCount + 1;
    ArrayResize(g_BacktestTrades, newSize);
    
    g_BacktestTrades[g_TradeCount].ticket        = 0;
    g_BacktestTrades[g_TradeCount].symbol        = _Symbol;
    g_BacktestTrades[g_TradeCount].type          = type;
    g_BacktestTrades[g_TradeCount].session       = type; // "BUY" atau "SELL"
    g_BacktestTrades[g_TradeCount].entry_price   = price;
    g_BacktestTrades[g_TradeCount].exit_price    = 0;
    g_BacktestTrades[g_TradeCount].sl            = 0;
    g_BacktestTrades[g_TradeCount].tp            = 0;
    g_BacktestTrades[g_TradeCount].profit        = 0;
    g_BacktestTrades[g_TradeCount].entry_time    = TimeCurrent();
    g_BacktestTrades[g_TradeCount].exit_time     = 0;
    g_BacktestTrades[g_TradeCount].lot_size      = 0;
    g_BacktestTrades[g_TradeCount].magic_number  = MagicNumber_M15;
    g_BacktestTrades[g_TradeCount].timeframe     = "M15";
    g_BacktestTrades[g_TradeCount].spread_cost   = 0;
    g_BacktestTrades[g_TradeCount].commission    = 0;
    g_BacktestTrades[g_TradeCount].swap          = 0;
    g_BacktestTrades[g_TradeCount].session_name  = GetCurrentSession();
    g_BacktestTrades[g_TradeCount].is_dst        = IsServerInDST(TimeCurrent());
    g_BacktestTrades[g_TradeCount].status        = "REJECTED";
    g_BacktestTrades[g_TradeCount].reject_reason = reason;
    
    g_TradeCount = newSize;
    PrintFormat("💾 [SAVED REJECT] Recorded reject signal #%d: %s | Price: %.5f | Reason: %s",
                g_TradeCount, type, price, reason);
}

//+------------------------------------------------------------------+
//| Helper: Cek apakah reject logs boleh dicetak                     |
//| - Hormati input EnableRejectLogs                                 |
//| - Auto-block saat Optimization (mencegah log spam ribuan pass)   |
//+------------------------------------------------------------------+
bool CanPrintRejectLogs()
{
    if(!EnableRejectLogs) return false;
    if(MQLInfoInteger(MQL_OPTIMIZATION)) return false;
    return true;
}

//+------------------------------------------------------------------+
//| Capture dan simpan OPEN trades yang tidak ditutup sampai akhir    |
//+------------------------------------------------------------------+
void CaptureOpenTrades()
{
    // 🔧 FIX: Capture OPEN trades dari PositionSelect() 
    int openPositions = PositionsTotal();
    
    if (openPositions == 0)
    {
        PrintFormat("ℹ️ [CAPTURE OPEN] Tidak ada open positions untuk di-capture");
        return;
    }
    
    PrintFormat("🔍 [CAPTURE OPEN] Menemukan %d open positions", openPositions);
    
    for (int i = 0; i < openPositions; i++)
    {
        ulong ticket = PositionGetTicket(i);
        if (ticket <= 0) continue;
        
        // Select position properly
        if (!PositionSelectByTicket(ticket))
        {
            PrintFormat("   ❌ Failed to select position with ticket %I64u", ticket);
            continue;
        }
        
        // Get position details
        ENUM_POSITION_TYPE pos_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
        string type = (pos_type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
        double entry_price = PositionGetDouble(POSITION_PRICE_OPEN);
        double sl = PositionGetDouble(POSITION_SL);
        double tp = PositionGetDouble(POSITION_TP);
        datetime entry_time = (datetime)PositionGetInteger(POSITION_TIME);
        datetime exit_time = TimeCurrent();  // Use current time as exit time for open positions
        double lot_size = PositionGetDouble(POSITION_VOLUME);
        double unrealized_profit = PositionGetDouble(POSITION_PROFIT);
        double current_price = PositionGetDouble(POSITION_PRICE_CURRENT);
        
        // ℹ️ Hitung estimasi current P&L untuk open position
        double estimated_profit = unrealized_profit;
        
        // Cek apakah trade sudah ada di array
        bool already_saved = false;
        for (int j = 0; j < g_TradeCount; j++)
        {
            if (g_BacktestTrades[j].ticket == ticket)
            {
                already_saved = true;
                PrintFormat("   [SKIP OPEN] Ticket %I64u sudah tersimpan sebelumnya", ticket);
                break;
            }
        }
        
        if (already_saved) continue;
        
        // 💾 Simpan open position dengan exit_price = current_price
        PrintFormat("💾 [OPEN TRADE CAPTURED] Ticket: %I64u | Type: %s | Entry: %.5f | Current: %.5f | Unrealized P&L: %.2f",
                    ticket, type, entry_price, current_price, estimated_profit);
        
        SaveTradeToArray(ticket, _Symbol, type,
                        entry_price, current_price,  // Use current price as exit
                        sl, tp, estimated_profit,
                        entry_time, exit_time,
                        lot_size, MagicNumber_M15, "M15",
                        0, 0, 0, GetCurrentSession());  // Assume no spread/commission/swap for open trades at capture time
    }
}

//+------------------------------------------------------------------+
//| Export hasil backtest ke file CSV                                  |
//| LIVE TRADING: Append mode + deduplication                          |
//+------------------------------------------------------------------+
void ExportBacktestToCSV()
{
    if (g_TradeCount == 0)
    {
        return;
    }
    
    string filename = "Backtest_Results_" + _Symbol + "_" + g_ExportDateStr + ".csv";
    
    // ✅ LIVE TRADING: Load existing tickets untuk deduplication
    ulong existingTickets[];
    int existingCount = 0;
    bool fileExists = false;
    
    // Check apakah mode LIVE TRADING (bukan backtest)
    bool isLiveTrading = !(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION));
    
    if (isLiveTrading && FileIsExist(filename))
    {
        fileExists = true;
        
        // Load existing tickets dari file
        int handleRead = FileOpen(filename, FILE_READ|FILE_CSV|FILE_ANSI, ",");
        if (handleRead != INVALID_HANDLE)
        {
            // Skip header
            string line = FileReadString(handleRead);
            
            // Read all tickets
            while (!FileIsEnding(handleRead))
            {
                string ticketStr = FileReadString(handleRead);
                if (ticketStr != "")
                {
                    ulong ticket = (ulong)StringToInteger(ticketStr);
                    if (ticket > 0)
                    {
                        ArrayResize(existingTickets, existingCount + 1);
                        existingTickets[existingCount] = ticket;
                        existingCount++;
                    }
                    
                    // Skip sisa kolom di baris ini (20 kolom total, sudah baca 1)
                    for (int col = 1; col < 20; col++)
                    {
                        FileReadString(handleRead);
                    }
                }
            }
            FileClose(handleRead);
            
            Print("📂 Loaded ", existingCount, " existing tickets from ", filename);
        }
    }
    
    // ✅ Open file dengan mode APPEND jika file exists (LIVE TRADING)
    int fileMode = FILE_WRITE|FILE_CSV|FILE_ANSI;
    if (fileExists && isLiveTrading)
    {
        fileMode = FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI;
    }
    
    int handle = FileOpen(filename, fileMode, ",");
    if (handle == INVALID_HANDLE)
    {
        Print("❌ Failed to open file: ", filename, " Error: ", GetLastError());
        return;
    }
    
    // ✅ Write header hanya jika file baru (BACKTEST atau file belum ada)
    if (!fileExists || !isLiveTrading)
    {
        // Header — schema v2: kolom Session_IsDST ditambahkan setelah Session
        FileWrite(handle, "Ticket", "Symbol", "Type", "EntryPrice", "ExitPrice",
                  "SL", "TP", "Profit", "Spread_Cost", "Commission", "Swap", "Net_Profit",
                  "Session", "Session_IsDST",
                  "EntryTime", "ExitTime", "LotSize", "MagicNumber", "Timeframe",
                  "Status", "Reject_Reason");
    }
    else
    {
        // File exists + LIVE TRADING: Pindah ke akhir file untuk append
        FileSeek(handle, 0, SEEK_END);
    }

    // ✅ Write data rows dengan deduplication (LIVE TRADING)
    int newTradesAdded = 0;
    
    for (int i = 0; i < g_TradeCount; i++)
    {
        ulong currentTicket = g_BacktestTrades[i].ticket;
        
        // Check apakah ticket sudah ada di file (hanya untuk LIVE TRADING)
        bool isDuplicate = false;
        if (isLiveTrading)
        {
            for (int j = 0; j < existingCount; j++)
            {
                if (existingTickets[j] == currentTicket)
                {
                    isDuplicate = true;
                    break;
                }
            }
        }
        
        // Skip duplicate ticket (hanya untuk LIVE TRADING)
        if (isDuplicate)
        {
            continue;
        }
        
        // Write trade ke file
        double net_profit = g_BacktestTrades[i].profit + g_BacktestTrades[i].commission + g_BacktestTrades[i].swap;

        FileWrite(handle,
                  IntegerToString(currentTicket),
                  g_BacktestTrades[i].symbol,
                  g_BacktestTrades[i].type,
                  DoubleToString(g_BacktestTrades[i].entry_price, _Digits),
                  DoubleToString(g_BacktestTrades[i].exit_price, _Digits),
                  DoubleToString(g_BacktestTrades[i].sl, _Digits),
                  DoubleToString(g_BacktestTrades[i].tp, _Digits),
                  DoubleToString(g_BacktestTrades[i].profit, 2),
                  DoubleToString(g_BacktestTrades[i].spread_cost, 2),
                  DoubleToString(g_BacktestTrades[i].commission, 2),
                  DoubleToString(g_BacktestTrades[i].swap, 2),
                  DoubleToString(net_profit, 2),
                  g_BacktestTrades[i].session_name,
                  g_BacktestTrades[i].is_dst ? "YES" : "NO",
                  TimeToString(g_BacktestTrades[i].entry_time, TIME_DATE|TIME_SECONDS),
                  TimeToString(g_BacktestTrades[i].exit_time, TIME_DATE|TIME_SECONDS),
                  DoubleToString(g_BacktestTrades[i].lot_size, 2),
                  IntegerToString(g_BacktestTrades[i].magic_number),
                  g_BacktestTrades[i].timeframe,
                  g_BacktestTrades[i].status,
                  g_BacktestTrades[i].reject_reason);
        
        newTradesAdded++;
    }
    
    FileClose(handle);
    
    if (isLiveTrading)
    {
        Print("✅ APPEND MODE: Added ", newTradesAdded, " new trades to ", filename, 
              " (Skipped ", (g_TradeCount - newTradesAdded), " duplicates)");
    }
}

//+------------------------------------------------------------------+
//| Export summary backtest ke file CSV                                |
//| LIVE TRADING: Summary always overwritten (aggregate statistics)    |
//+------------------------------------------------------------------+
void ExportBacktestSummaryToCSV()
{
    if (g_TradeCount == 0) return;
    
    string filename = "Backtest_Summary_" + _Symbol + "_" + g_ExportDateStr + ".csv";
    
    // Hitung statistik (Hanya untuk trades EXECUTED)
    int    executedTradeCount = 0;
    int    winCount    = 0;
    int    loseCount   = 0;
    double totalProfit = 0;
    double maxDrawdown = 0;
    double runningPnL  = 0;
    double peakPnL     = 0;
    double grossProfit = 0;
    double grossLoss   = 0;
    
    datetime startDate = 0;
    datetime endDate   = 0;
    
    // Temukan startDate pertama dari trade EXECUTED
    for (int i = 0; i < g_TradeCount; i++)
    {
        if (g_BacktestTrades[i].status == "EXECUTED")
        {
            startDate = g_BacktestTrades[i].entry_time;
            break;
        }
    }
    
    // Temukan endDate terakhir dari trade EXECUTED
    for (int i = g_TradeCount - 1; i >= 0; i--)
    {
        if (g_BacktestTrades[i].status == "EXECUTED")
        {
            endDate = g_BacktestTrades[i].exit_time;
            break;
        }
    }
    
    // Fallback jika tidak ada trade EXECUTED
    if (startDate == 0) startDate = g_BacktestTrades[0].entry_time;
    if (endDate == 0) endDate = g_BacktestTrades[g_TradeCount-1].exit_time;
    
    for (int i = 0; i < g_TradeCount; i++)
    {
        if (g_BacktestTrades[i].status != "EXECUTED") continue;
        
        executedTradeCount++;
        // Use true net profit (gross profit + commission + swap)
        double p = g_BacktestTrades[i].profit + g_BacktestTrades[i].commission + g_BacktestTrades[i].swap;
        totalProfit += p;
        runningPnL  += p;
        
        if (p > 0) { winCount++; grossProfit += p; }
        else       { loseCount++; grossLoss += MathAbs(p); }
        
        if (runningPnL > peakPnL) peakPnL = runningPnL;
        double dd = peakPnL - runningPnL;
        if (dd > maxDrawdown) maxDrawdown = dd;
    }
    
    double winRate      = (executedTradeCount > 0) ? (double)winCount / executedTradeCount * 100.0 : 0;
    double profitFactor = (grossLoss > 0) ? grossProfit / grossLoss : 0;
    
    int handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ",");
    if (handle == INVALID_HANDLE)
    {
        return;
    }
    
    FileWrite(handle, "Symbol", "TotalTrades", "WinningTrades", "LosingTrades", 
              "WinRate", "TotalProfit", "MaxDrawdown", "ProfitFactor", 
              "StartDate", "EndDate");
    FileWrite(handle, 
              _Symbol,
              IntegerToString(executedTradeCount),
              IntegerToString(winCount),
              IntegerToString(loseCount),
              DoubleToString(winRate, 2),
              DoubleToString(totalProfit, 2),
              DoubleToString(maxDrawdown, 2),
              DoubleToString(profitFactor, 2),
              TimeToString(startDate, TIME_DATE|TIME_SECONDS),
              TimeToString(endDate, TIME_DATE|TIME_SECONDS));
    
    FileClose(handle);
}

//+------------------------------------------------------------------+
//| Export market data (OHLCV + EMA200) ke file CSV                    |
//+------------------------------------------------------------------+
void ExportMarketDataToCSV(ENUM_TIMEFRAMES tf, int barsToExport)
{
    string tfStr = (tf == PERIOD_M15) ? "M15" : ((tf == PERIOD_H4) ? "H4" : "H1");
    string filename = "MarketData_" + _Symbol + "_" + tfStr + "_" + g_ExportDateStr + ".csv";
    
    MqlRates rates[];
    ArraySetAsSeries(rates, true);
    int copied = CopyRates(_Symbol, tf, 0, barsToExport, rates);
    if (copied <= 0)
    {
        return;
    }
    
    // Ambil EMA200
    int emaHandle = (tf == PERIOD_M15) ? handleEMA_M15 : ((tf == PERIOD_H4) ? handleEMA_H4 : handleEMA_H1);
    double emaBuffer[];
    ArraySetAsSeries(emaBuffer, true);
    int emaCopied = CopyBuffer(emaHandle, 0, 0, barsToExport, emaBuffer);
    
    int handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ",");
    if (handle == INVALID_HANDLE)
    {
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
}

//+------------------------------------------------------------------+
//| Export LL, HH, BOS, CHoCH data ke file CSV (sorted by time)        |
//+------------------------------------------------------------------+
void ExportLLHHBOSToCSV()
{
    // ✅ SAFETY GUARD: Jangan overwrite file jika arrays kosong
    // Mencegah data loss saat EA start dan data belum ter-load
    if (g_LLHHBOSCount == 0 && g_AcceptedLevelHistoryCount == 0)
    {
        return;
    }
    
    string filename = "LLHHBOSData_" + _Symbol + "_" + g_ExportDateStr + ".csv";
    
    // ✅ Determine mode: BACKTEST (overwrite) vs LIVE TRADING (append+dedup)
    bool isLiveTrading = !(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION));
    bool fileExists = FileIsExist(filename);
    
    // ✅ LIVE TRADING: Load existing events dari file untuk deduplication
    // Key = type + time + timeframe
    string existingKeys[];
    int existingKeyCount = 0;
    
    if (isLiveTrading && fileExists)
    {
        int handleRead = FileOpen(filename, FILE_READ|FILE_CSV|FILE_ANSI, ",");
        if (handleRead != INVALID_HANDLE)
        {
            // Skip rows until header row (starting with "Type") is found
            for (int skipI = 0; skipI < 100; skipI++)
            {
                string hdr = FileReadString(handleRead);
                if (hdr == "Type")
                {
                    for (int j = 0; j < 7; j++) FileReadString(handleRead);
                    break;
                }
                if (FileIsEnding(handleRead)) break;
            }
            
            // Read all existing event keys
            while (!FileIsEnding(handleRead))
            {
                string evType = FileReadString(handleRead);
                if (evType == "" || FileIsEnding(handleRead)) continue; // ponytail: blank line? skip, NOT break
                
                string evDir   = FileReadString(handleRead);
                string evPrice = FileReadString(handleRead);
                string evTime  = FileReadString(handleRead);
                string evTF    = FileReadString(handleRead);
                // Skip sisa kolom: status, prevPrice, prevTime
                FileReadString(handleRead);
                FileReadString(handleRead);
                FileReadString(handleRead);
                
                if (evType != "" && evTime != "" && evTF != "")
                {
                    string key = evType + "|" + evTime + "|" + evTF;
                    ArrayResize(existingKeys, existingKeyCount + 1);
                    existingKeys[existingKeyCount] = key;
                    existingKeyCount++;
                }
            }
            FileClose(handleRead);
            Print("📂 Loaded ", existingKeyCount, " existing event keys from ", filename);
        }
    }
    
    // ✅ Open file: BACKTEST = FILE_WRITE (overwrite), LIVE + file exists = FILE_READ|FILE_WRITE (append)
    int fileMode = FILE_WRITE|FILE_CSV|FILE_ANSI;
    if (isLiveTrading && fileExists)
    {
        fileMode = FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI;
    }
    
    int handle = FileOpen(filename, fileMode, ",");
    if (handle == INVALID_HANDLE)
    {
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
    // Write header only for BACKTEST or new file (LIVE)
    if (!fileExists || !isLiveTrading)
    {
        FileWrite(handle, "=== Market Structure Events (Sorted by Time) ===", "", "", "", "", "", "");
        FileWrite(handle, "Type", "Direction/Action", "Price", "Time", "Timeframe", 
                  "Status", "PreviousPrice", "PreviousTime");
    }
    else
    {
        // LIVE TRADING + file exists: Seek ke akhir file untuk append
        FileSeek(handle, 0, SEEK_END);
    }
    
    // Write sorted events dengan deduplication (LIVE TRADING)
    int newEventsAdded = 0;
    
    for (int i = 0; i < g_UnifiedEventCount; i++)
    {
        // Dedup check: hanya untuk LIVE TRADING
        bool isDuplicate = false;
        if (isLiveTrading)
        {
            string currentKey = g_UnifiedEvents[i].type + "|" + 
                                TimeToString(g_UnifiedEvents[i].time, TIME_DATE|TIME_SECONDS) + "|" + 
                                g_UnifiedEvents[i].timeframe;
            
            for (int j = 0; j < existingKeyCount; j++)
            {
                if (existingKeys[j] == currentKey)
                {
                    isDuplicate = true;
                    break;
                }
            }
        }
        
        // Skip duplicate event (hanya untuk LIVE TRADING)
        if (isDuplicate)
        {
            continue;
        }
        
        FileWrite(handle,
                  g_UnifiedEvents[i].type,
                  g_UnifiedEvents[i].direction,
                  DoubleToString(g_UnifiedEvents[i].price, _Digits),
                  TimeToString(g_UnifiedEvents[i].time, TIME_DATE|TIME_SECONDS),
                  g_UnifiedEvents[i].timeframe,
                  g_UnifiedEvents[i].status,
                  (g_UnifiedEvents[i].previousPrice > 0) ? DoubleToString(g_UnifiedEvents[i].previousPrice, _Digits) : "",
                  g_UnifiedEvents[i].previousTime);
        
        newEventsAdded++;
    }
    
    FileClose(handle);
    
    if (isLiveTrading)
    {
        Print("✅ APPEND MODE: Added ", newEventsAdded, " new events to ", filename,
              " (Skipped ", (g_UnifiedEventCount - newEventsAdded), " duplicates)");
    }
}

//+------------------------------------------------------------------+
//| Export Market Structure Records ke file CSV                       |
//+------------------------------------------------------------------+
void ExportMarketStructureToCSV()
{
    if (g_StructureRecordsCount == 0)
    {
        return;
    }
    
    string filename = "MarketStructure_" + _Symbol + "_" + g_ExportDateStr + ".csv";
    
    int handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ",");
    if (handle == INVALID_HANDLE)
    {
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
}

//+------------------------------------------------------------------+
//| Export semua data (dipanggil dari OnDeinit/OnTester)               |
//+------------------------------------------------------------------+
void ExportAllData()
{
    // 🔧 FIX: Capture OPEN trades sebelum export (PENTING!)
    // Ini memastikan trades yang masih open sampai akhir backtest tetap tercatat
    CaptureOpenTrades();
    
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
    
    // 8. Export market data H4
    ExportMarketDataToCSV(PERIOD_H4, 10000000);
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

//+------------------------------------------------------------------+
//| AUTO EXPORT REALTIME - Input Parameters                          |
//+------------------------------------------------------------------+
input bool EnableAutoExportRealtime = false;   // ✅ Aktifkan auto export berkala (live trading)
input int  AutoExportIntervalMinutes = 60;     // Interval export (menit) - default 60 menit
input bool EnableAutoExportLogs = false;       // Tampilkan log detail auto export
input string BacktestResultPath = "D:\\Project\\Project MT5\\Backtest_result";  // Path folder backtest result

//+------------------------------------------------------------------+
//| AUTO EXPORT REALTIME - Global Variables (legacy, timer dihapus)   |
//+------------------------------------------------------------------+
// ponytail: timer dihapus — export per M15 candle close di OnTick.
// Input vars tetap ada supaya template/preset EA tidak rusak.

// Struct untuk Session Zone
struct SessionZoneRecord
{
    datetime  time;            // Waktu MULAI sesi (start time)
    datetime  endTime;          // Waktu BERAKHIR sesi (end time) — NEW
    string    sessionName;      // Nama sesi: "Sydney", "Sydney_Tokyo_Overlap", "Asia",
                                //            "Tokyo_London_Overlap", "London",
                                //            "London_NewYork_Overlap", "NewYork"
    bool      isSessionActive;  // legacy, selalu false saat record disave (sesi sudah closed)
    bool      isDST;            // true jika sesi berlangsung saat DST aktif — NEW
    double    sessionOpenPrice; // Harga open saat sesi dimulai
    double    sessionHighPrice; // Harga high dalam sesi
    double    sessionLowPrice;  // Harga low dalam sesi
    double    sessionClosePrice;// Harga close dalam sesi
    int       sessionBarsCount; // Jumlah bar M15 dalam sesi
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
//| DST HANDLING - Input Parameters                                  |
//+------------------------------------------------------------------+
// Aktifkan auto-shift saat broker masuk Daylight Saving Time (DST).
// EU DST: Last Sunday of March → Last Sunday of October.
// Saat DST aktif, broker GMT+2 menjadi GMT+3, jadi semua jam server
// terlihat maju 1 jam. Helper di bawah akan menormalisasinya kembali
// agar window jam sesi tetap konsisten di winter & summer.
input bool EnableDSTHandling = true;   // true = auto-handle EU DST

//+------------------------------------------------------------------+
//| Last Sunday of given month (Maret atau Oktober)                  |
//| Return: hari (1-31) ketika last Sunday jatuh.                    |
//+------------------------------------------------------------------+
int LastSundayOfMonth(int year, int month)
{
    MqlDateTime dt;
    dt.year       = year;
    dt.mon        = month;
    dt.day        = 31;          // Mar & Oct keduanya selalu punya 31 hari
    dt.hour       = 12;          // tengah hari, hindari edge DST jam 00:00
    dt.min        = 0;
    dt.sec        = 0;
    dt.day_of_week = 0;          // diisi otomatis oleh TimeToStruct
    dt.day_of_year = 0;

    datetime t = StructToTime(dt);
    TimeToStruct(t, dt);

    // dt.day_of_week : 0 = Sunday, 1 = Monday, ... 6 = Saturday
    // Jika tanggal 31 jatuh hari Minggu → return 31
    // Jika tanggal 31 jatuh hari Senin → return 30, dst.
    return dt.day - dt.day_of_week;
}

//+------------------------------------------------------------------+
//| Apakah waktu server berada dalam periode DST (EU rules)?         |
//| EU DST window: Last Sun of March 03:00 server → Last Sun of Oct  |
//|                04:00 server (saat masih GMT+3 sebelum jadi GMT+2)|
//+------------------------------------------------------------------+
bool IsServerInDST(datetime serverTime)
{
    if (!EnableDSTHandling) return false;

    MqlDateTime dt;
    TimeToStruct(serverTime, dt);

    int year  = dt.year;
    int month = dt.mon;
    int day   = dt.day;
    int hour  = dt.hour;

    // Cepat: di luar window Mar–Oct → pasti winter
    if (month < 3 || month > 10) return false;
    if (month > 3 && month < 10) return true;

    // Bulan Mar atau Oct → cek tanggal vs last Sunday
    int lastSunday = LastSundayOfMonth(year, month);

    if (month == 3) {
        // DST mulai pada last Sunday Maret jam 03:00 server
        if (day  < lastSunday) return false;
        if (day  > lastSunday) return true;
        return (hour >= 3);
    } else {
        // Oktober — DST berakhir pada last Sunday Oct jam 04:00 server (GMT+3)
        if (day  < lastSunday) return true;
        if (day  > lastSunday) return false;
        return (hour < 4);
    }
}

//+------------------------------------------------------------------+
//| Effective hour: hour server yang sudah dinormalisasi DST         |
//| Saat DST aktif (server GMT+3), kurangi 1 jam supaya window       |
//| selalu konsisten dengan winter (server GMT+2).                   |
//+------------------------------------------------------------------+
int GetEffectiveHour(datetime serverTime)
{
    MqlDateTime dt;
    TimeToStruct(serverTime, dt);
    int hour = dt.hour;
    if (IsServerInDST(serverTime))
        hour = (hour - 1 + 24) % 24;
    return hour;
}

//+------------------------------------------------------------------+
//| Deteksi sesi trading - FIXED OFFSET untuk broker GMT+2           |
//| (MetaQuotes-Demo winter, IC Markets, Exness, FBS, dll.)          |
//|                                                                  |
//| Window dipetakan dari standar pasar forex (GMT) ke server GMT+2: |
//|   Sesi (GMT)         → Server (GMT+2)                            |
//|   Sydney  21:00-06:00 → 23:00-08:00                              |
//|   Tokyo   23:00-08:00 → 01:00-10:00                              |
//|   London  07:00-16:00 → 09:00-18:00                              |
//|   NewYork 12:00-21:00 → 14:00-23:00                              |
//|   Overlap London-NY   → 14:00-18:00 server                       |
//|                                                                  |
//| ✅ DST sekarang DI-HANDLE OTOMATIS: lihat IsServerInDST() &        |
//|    GetEffectiveHour() di atas. Saat DST aktif, hour dinormalisasi |
//|    -1 jam supaya window di bawah TETAP VALID di winter & summer. |
//+------------------------------------------------------------------+
string GetCurrentSession()
{
    datetime currentTime = TimeCurrent();   // server time (GMT+2 winter / GMT+3 summer)
    MqlDateTime dtStruct;
    TimeToStruct(currentTime, dtStruct);

    int dayOfWeek = dtStruct.day_of_week;

    // Weekend = Sabtu (6) / Minggu (0)
    if (dayOfWeek == 0 || dayOfWeek == 6)
        return "Weekend";

    // Hour yang sudah dinormalisasi DST → window di bawah selalu valid.
    int hour = GetEffectiveHour(currentTime);

    // === Window berdasarkan SERVER TIME GMT+2 (effective) ===
    //
    //  23:00 – 00:59  : Sydney only (sebelum Tokyo open jam 01:00 server)
    //  01:00 – 07:59  : Sydney_Tokyo_Overlap (Sydney + Tokyo barengan)
    //  08:00 – 08:59  : Asia (Tokyo only; Sydney close jam 08:00 server)
    //  09:00 – 09:59  : Tokyo_London_Overlap (Tokyo wrap-up + London open)
    //  10:00 – 13:59  : London     (London murni; Tokyo sudah close)
    //  14:00 – 17:59  : London_NewYork_Overlap (London + NY barengan)
    //  18:00 – 22:59  : NewYork    (London close jam 18:00 server)
    //
    if ((hour >= 23) || (hour < 1))
        return "Sydney";
    else if ((hour >= 1) && (hour < 8))
        return "Sydney_Tokyo_Overlap";
    else if ((hour >= 8) && (hour < 9))
        return "Asia";
    else if ((hour >= 9) && (hour < 10))
        return "Tokyo_London_Overlap";
    else if ((hour >= 10) && (hour < 14))
        return "London";
    else if ((hour >= 14) && (hour < 18))
        return "London_NewYork_Overlap";
    else if ((hour >= 18) && (hour < 23))
        return "NewYork";
    else
        return "NoSession";
}

//+------------------------------------------------------------------+
//| Simpan Session Zone Record ke array global                       |
//+------------------------------------------------------------------+
void SaveSessionZoneRecord(datetime startTime, datetime endTime, string sessionName,
                           bool isActive, bool isDST,
                           double openPrice, double highPrice, double lowPrice,
                           double closePrice, int barsCount)
{
    int newSize = g_SessionZoneRecordsCount + 1;
    ArrayResize(g_SessionZoneRecords, newSize);

    g_SessionZoneRecords[g_SessionZoneRecordsCount].time              = startTime;
    g_SessionZoneRecords[g_SessionZoneRecordsCount].endTime           = endTime;
    g_SessionZoneRecords[g_SessionZoneRecordsCount].sessionName       = sessionName;
    g_SessionZoneRecords[g_SessionZoneRecordsCount].isSessionActive   = isActive;
    g_SessionZoneRecords[g_SessionZoneRecordsCount].isDST             = isDST;
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
    
    // Define session times — server GMT+2 (sinkron dengan GetCurrentSession)
    struct SessionTime {
        string name;
        int startHour;
        int endHour;
        color shadowColor;
    };

    SessionTime sessions[] = {
        {"Sydney",  23,  8, SessionSydneyColor},   // 23:00 – 08:00 server (cross midnight)
        {"Asia",     1, 10, SessionAsiaColor},     // 01:00 – 10:00 server (Tokyo, overlap Sydney 01:00-08:00)
        {"London",   9, 18, SessionLondonColor},   // 09:00 – 18:00 server
        {"NewYork", 14, 23, SessionNewYorkColor}   // 14:00 – 23:00 server
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
        
        // Untuk session yang cross midnight (mis. Sydney 23-08)
        if (sessions[i].startHour > sessions[i].endHour)
        {
            // Hari ini: start hour sampai tengah malam
            // Besok: jam 0 sampai end hour
            MqlDateTime startDt = currentDt;
            startDt.hour = sessions[i].startHour;
            startDt.min = 0;
            startDt.sec = 0;
            shadowStartTime = StructToTime(startDt);

            // FIX: jangan pakai endDt.day = day + 1 (bisa jadi 32, invalid).
            // Hitung end via seconds arithmetic — datetime aman lewati akhir bulan.
            MqlDateTime baseDt = currentDt;
            baseDt.hour = sessions[i].endHour;
            baseDt.min  = 0;
            baseDt.sec  = 0;
            datetime endSameDay = StructToTime(baseDt);
            shadowEndTime = endSameDay + 86400;   // +1 hari penuh dalam detik
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
//| Update Session Zone tracking setiap bar M15 baru                |
//| FIX: counter sekarang menghitung jumlah BAR M15 (bukan tick).    |
//|      High/low tracking pakai bar.high / bar.low yang sebenarnya. |
//+------------------------------------------------------------------+
void UpdateSessionZoneTracking()
{
    if (!EnableSessionZone) return;

    // Patokan ini = waktu OPEN bar M15 saat ini.
    // Selama tick masih dalam bar yang sama, nilainya tidak berubah,
    // jadi counter hanya akan naik saat bar M15 BARU terbentuk.
    static datetime lastBarTime = 0;
    datetime currentBarTime = (datetime)SeriesInfoInteger(_Symbol, PERIOD_M15, SERIES_LASTBAR_DATE);
    if (currentBarTime == 0)
        currentBarTime = iTime(_Symbol, PERIOD_M15, 0);
    if (currentBarTime == 0)
        return;

    bool isNewBar = (currentBarTime != lastBarTime);
    if (!isNewBar)
        return;                          // skip tick yang masih di bar yang sama

    lastBarTime = currentBarTime;

    // Ambil OHLC bar M15 yang baru saja terbentuk (index 0 = bar berjalan).
    MqlRates currentRate[];
    ArraySetAsSeries(currentRate, true);
    if (CopyRates(_Symbol, PERIOD_M15, 0, 1, currentRate) < 1)
        return;

    double barOpen  = currentRate[0].open;
    double barHigh  = currentRate[0].high;
    double barLow   = currentRate[0].low;
    double barClose = currentRate[0].close;

    string session = GetCurrentSession();

    // ---- Deteksi perubahan sesi ----
    if (session != currentActiveSession)
    {
        // Tutup sesi sebelumnya (kecuali "NoSession" / belum pernah set)
        if (currentActiveSession != "" && currentActiveSession != "NoSession")
        {
            //PrintFormat("📊 [SESSION] Sesi %s berakhir | Duration: %d bars | High: %.5f | Low: %.5f",
            //           currentActiveSession, sessionBarsCount, sessionHighPrice, sessionLowPrice);

            // currentBarTime di sini = waktu bar pertama dari sesi berikutnya = end time sesi yg ditutup.
            bool sessionWasDST = IsServerInDST(lastSessionChangeTime);
            SaveSessionZoneRecord(lastSessionChangeTime, currentBarTime, currentActiveSession,
                                  false, sessionWasDST,
                                  sessionOpenPrice, sessionHighPrice, sessionLowPrice,
                                  barClose, sessionBarsCount);
        }

        // Buka sesi baru — bar pertama dihitung 1.
        currentActiveSession  = session;
        lastSessionChangeTime = currentBarTime;
        sessionOpenPrice      = barOpen;
        sessionHighPrice      = barHigh;
        sessionLowPrice       = barLow;
        sessionBarsCount      = 1;

        if (session != "NoSession" && session != "Weekend")
        {
            //PrintFormat("🔔 [SESSION] Sesi %s dimulai | Open: %.5f | Time: %s",
            //           session, sessionOpenPrice,
            //           TimeToString(currentBarTime, TIME_DATE|TIME_MINUTES));
        }
    }
    else
    {
        // Masih dalam sesi yang sama → tambahkan bar baru.
        if (barHigh > sessionHighPrice) sessionHighPrice = barHigh;
        if (barLow  < sessionLowPrice)  sessionLowPrice  = barLow;
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
        return;
    }
    
    string filename = "SessionZone_" + _Symbol + "_" + g_ExportDateStr + ".csv";
    
    int handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ",");
    if (handle == INVALID_HANDLE)
    {
        return;
    }
    
    // Header — schema v2:
    //   StartTime, EndTime, DurationBars, Session, Status, IsDST,
    //   OpenPrice, HighPrice, LowPrice, ClosePrice, RangePoints
    FileWrite(handle, "StartTime", "EndTime", "DurationBars", "Session", "Status", "IsDST",
              "OpenPrice", "HighPrice", "LowPrice", "ClosePrice", "RangePoints");

    // Data rows
    for (int i = 0; i < g_SessionZoneRecordsCount; i++)
    {
        double rangePoints = (g_SessionZoneRecords[i].sessionHighPrice - g_SessionZoneRecords[i].sessionLowPrice) / _Point;
        FileWrite(handle,
                  TimeToString(g_SessionZoneRecords[i].time,    TIME_DATE|TIME_SECONDS),
                  TimeToString(g_SessionZoneRecords[i].endTime, TIME_DATE|TIME_SECONDS),
                  IntegerToString(g_SessionZoneRecords[i].sessionBarsCount),
                  g_SessionZoneRecords[i].sessionName,
                  "CLOSED",
                  g_SessionZoneRecords[i].isDST ? "YES" : "NO",
                  DoubleToString(g_SessionZoneRecords[i].sessionOpenPrice,  _Digits),
                  DoubleToString(g_SessionZoneRecords[i].sessionHighPrice,  _Digits),
                  DoubleToString(g_SessionZoneRecords[i].sessionLowPrice,   _Digits),
                  DoubleToString(g_SessionZoneRecords[i].sessionClosePrice, _Digits),
                  DoubleToString(rangePoints, 0));
    }
    
    FileClose(handle);
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
    string    session;
};

TradeRecord_H1 currentBuyTrade_H1;   // Untuk posisi buy aktif H1
TradeRecord_H1 currentSellTrade_H1;  // Untuk posisi sell aktif H1

// Array untuk menyimpan multiple active trades H1
TradeRecord_H1 activeBuyTrades_H1[3];   // Array untuk multiple buy entries H1
TradeRecord_H1 activeSellTrades_H1[3];  // Array untuk multiple sell entries H1
int activeBuyCount_H1 = 0;               // Counter untuk active buy trades H1
int activeSellCount_H1 = 0;              // Counter untuk active sell trades H1

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

    // ✅ SKIP semua gambar line H1 bila EnableDrawLines_H1 dimatikan
    if (!EnableDrawLines_H1)
        return;

    string lineName  = "line_lastAccepted" + type + "_H1";
    string labelName = "label_lastAccepted" + type + "_H1";
    color lineColor  = (type == "HH") ? clrOrange : clrAqua;
    int   labelOffset = (type == "HH") ? 20 : -20;

    ObjectDelete(0, lineName);
    ObjectDelete(0, labelName);

    if (level != -1) {
        // Gunakan OBJ_TREND dengan OBJPROP_RAY_RIGHT untuk membuat garis hanya ke depan
        // Titik 1 = waktu HH/LL muncul, Titik 2 = waktu yang sama (akan dipanjang ke kanan)
        ObjectCreate(0, lineName, OBJ_TREND, 0, time, level, time + PeriodSeconds(PERIOD_H1), level);
        ObjectSetInteger(0, lineName, OBJPROP_COLOR, lineColor);
        ObjectSetInteger(0, lineName, OBJPROP_WIDTH, 1);
        ObjectSetInteger(0, lineName, OBJPROP_STYLE, STYLE_DASHDOT);
        ObjectSetInteger(0, lineName, OBJPROP_RAY_RIGHT, true); // ✅ Panjang hanya ke kanan
        ObjectSetInteger(0, lineName, OBJPROP_RAY_LEFT, false);  // ✅ Jangan panjang ke kiri
        ObjectSetInteger(0, lineName, OBJPROP_BACK, true);       // Gambar di latar belakang

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
datetime lastTrailingBarTime_M15 = 0;
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

// Parameter input untuk SL dan TP M15
//--- Entry 1 parameters M15
input int DefaultSL_Buy_M15  = 3000;   // Stop Loss untuk Buy Entry 1 (dalam poin) M15
input int DefaultTP_Buy_M15  = 3000;   // Take Profit untuk Buy Entry 1 (dalam poin) M15
input int DefaultSL_Sell_M15 = 3000;   // Stop Loss untuk Sell Entry 1 (dalam poin) M15
input int DefaultTP_Sell_M15 = 3000;   // Take Profit untuk Sell Entry 1 (dalam poin) M15
//--- Entry 2 parameters M15
input int Entry2SL_Buy_M15  = 2000;   // Stop Loss untuk Buy Entry 2 (dalam poin) M15
input int Entry2TP_Buy_M15  = 2500;   // Take Profit untuk Buy Entry 2 (dalam poin) M15
input int Entry2SL_Sell_M15 = 2000;  // Stop Loss untuk Sell Entry 2 (dalam poin) M15
input int Entry2TP_Sell_M15 = 2500;  // Take Profit untuk Sell Entry 2 (dalam poin) M15
//--- Entry 3 parameters M15
input int Entry3SL_Buy_M15  = 3500;   // Stop Loss untuk Buy Entry 3 (dalam poin) M15
input int Entry3TP_Buy_M15  = 3000;   // Take Profit untuk Buy Entry 3 (dalam poin) M15
input int Entry3SL_Sell_M15 = 3500;  // Stop Loss untuk Sell Entry 3 (dalam poin) M15
input int Entry3TP_Sell_M15 = 3000;  // Take Profit untuk Sell Entry 3 (dalam poin) M15
input ulong MagicNumber_M15 = 12345; // Magic number untuk EA M15
input int MaxEntriesPerCycle_M15 = 2; // Max entries per CHoCH cycle M15 // FIX #4: Changed from 3 to 1

// FIX #3: Hold time constraints
input int MinHoldHours_M15 = 4;  // Minimum hold time before allowing TP exit (hours)
input int MaxHoldHours_M15 = 24; // Maximum hold time, force close after this (hours)

// --- Trailing Stop Parameters M15 ---
input bool EnableTrailingStop_M15   = true;  // Aktifkan Trailing Stop M15
input bool EnableTrailingLogs_M15   = false; // Aktifkan log verbose Trailing Stop M15 (per tick)

//+------------------------------------------------------------------+
//| H4 EMA FILTER - Input Parameters                                 |
//+------------------------------------------------------------------+
input bool   EnableH4EMAFilter  = true;   // Aktifkan filter EMA H4 sebagai konfirmasi trend
input int    EMA_H4_Period      = 200;    // Periode EMA untuk H4 (default 200)
input bool   H4EMA_LogOnly      = false; // true=LOG ONLY (tidak blokir), false=ACTIVE

//+------------------------------------------------------------------+
//| BAR BODY RATIO FILTER - Input Parameters                         |
//+------------------------------------------------------------------+
// Filter candle lemah (doji/indecision) sebelum entry.
// Body < MinBodyRatio * TotalRange → candle dianggap tidak valid untuk entry.
input bool   EnableBodyRatioFilter      = true;   // Aktifkan filter body ratio candle
input double MinBodyRatio               = 0.40;   // Minimum ratio body/range (default 40%)
input bool   BodyRatio_LogOnly          = false;  // true=LOG ONLY (tidak blokir), false=ACTIVE
// --- H4 EMA Stretch-Aware BR Override (Forensic Analysis 2023 - Section 12.5.1) ---
// Analisis forensik menunjukkan filter BR < 40% salah blokir 5 dari 8 trade WIN di 2023
// ketika harga berada di zona trending moderat (0.5%-1.9% dari EMA200 H4).
// Rule A: Jika |H4 gap%| > H4_MaxStretch_Pct → enforce strict BR (MinBodyRatio)
// Rule B: Jika H4 gap 0.5%-MaxStretch% + momentum H4 searah trade → MinBR = H4_TrendMinBody
input bool   Enable_H4_BR_Override      = true;   // Aktifkan H4 EMA stretch-aware BR override
input double H4_MaxStretch_Pct          = 1.8;    // Max H4 gap% sebelum enforce strict BR (default 1.8%)
input double H4_MinTrend_Pct            = 0.5;    // Min H4 gap% untuk zona trending (default 0.5%)
input double H4_TrendMinBody            = 0.15;   // MinBodyRatio saat zona trending (default 15%)
input int    H4_Momentum_Bars           = 4;      // Jumlah bar H4 untuk hitung momentum (4 bar = 16 jam)

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
input int  WarmupBars_M15     = 200;    // jumlah bar history untuk backfill

input bool BackfillOnLoad_H1 = true;   // langsung scan & gambar dari history saat attach
input int  WarmupBars_H1    = 200;    // jumlah bar history untuk backfill

input bool EnableDrawLines_H1 = false; // ✅ ON/OFF gambar line/zone H1. true=TAMPILKAN, false=sembunyikan (logic tetap jalan). Default false biar backtest bersih.

input int MaxLineLengthBars = 50; // Panjang MAKSIMAL garis HH/LL (candle dari formasi) — broken maupun belum

input bool EnableRejectLogs = false; // ✅ Aktifkan log HH/LL yang direject untuk tracking backtest. Auto-disabled saat Optimization.

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
    string    session;
    int       trailing_step; // Langkah trailing stop aktif (0 = belum aktif, 1, 2, 3)
};

TradeRecord_M15 currentBuyTrade_M15;   // Untuk posisi buy aktif M15
TradeRecord_M15 currentSellTrade_M15;  // Untuk posisi sell aktif M15

// Array untuk menyimpan multiple active trades M15
TradeRecord_M15 activeBuyTrades_M15[10];   // Array untuk multiple buy entries M15
TradeRecord_M15 activeSellTrades_M15[10];  // Array untuk multiple sell entries M15
int activeBuyCount_M15 = 0;                // Counter untuk active buy trades M15
int activeSellCount_M15 = 0;               // Counter untuk active sell trades M15

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
        // --- Gambar Garis Horizontal dengan OBJ_TREND + RAY_RIGHT ---
        // Titik 1 = waktu HH/LL muncul, Titik 2 = waktu yang sama (akan dipanjang ke depan)
        ObjectCreate(0, lineName, OBJ_TREND, 0, time, level, time + PeriodSeconds(PERIOD_M15), level); // Buat objek trend line
        ObjectSetInteger(0, lineName, OBJPROP_COLOR, lineColor); // Set warna
        ObjectSetInteger(0, lineName, OBJPROP_WIDTH, 1); // Set ketebalan
        ObjectSetInteger(0, lineName, OBJPROP_STYLE, STYLE_DASHDOT); // *** SET PUTUS-PUTUS (DOT/LINE) ***
        ObjectSetInteger(0, lineName, OBJPROP_RAY_RIGHT, true);  // ✅ Panjang HANYA ke kanan (depan)
        ObjectSetInteger(0, lineName, OBJPROP_RAY_LEFT, false);  // ✅ JANGAN panjang ke kiri (belakang)
        ObjectSetInteger(0, lineName, OBJPROP_BACK, true);       // Gambar di latar belakang
        
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
    // Buat garis tren yang hanya membentang ke depan (dari t2)
    // Gunakan t2 sebagai titik awal dan t2 + 1 bar sebagai referensi
    ObjectCreate(0, name, OBJ_TREND, 0, t2, p2, t2 + PeriodSeconds(PERIOD_M15), p2);
    ObjectSetInteger(0, name, OBJPROP_COLOR, col);
    ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
    ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
    ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, true);  // ✅ Panjang HANYA ke kanan (depan)
    ObjectSetInteger(0, name, OBJPROP_RAY_LEFT, false);  // ✅ JANGAN panjang ke kiri (belakang)
    ObjectSetInteger(0, name, OBJPROP_BACK, true); // Gambar di latar belakang
    
    // Buat label teks
    string labelName = name + "_label_M15";
    // Hitung posisi label → Geser ke kanan 1 bar dan naik sedikit untuk visibilitas
    datetime labelTime  = t2 + PeriodSeconds(PERIOD_M15);                                                   // Geser ke kanan 1 candle M15
    double   labelPrice = p2 + (label == "CHoCH" || label == "BoS" ? 8 * _Point : -10 * _Point);  // Naikkan/geser sesuai label
    
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

//+------------------------------------------------------------------+
//| SYNC LAST SESSION CSV - Find and copy last session CSV files     |
//| from Backtest_result\ to MQL5 sandbox (same-month resume)         |
//+------------------------------------------------------------------+
void SyncLastSessionCSV()
{
    bool isLiveTrading = !(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION));
    if (!isLiveTrading) return;
    if (BacktestResultPath == "") return;
    
    datetime currentTime = TimeCurrent();
    MqlDateTime dt;
    TimeToStruct(currentTime, dt);
    
    string todayDateStr = TimeToString(currentTime, TIME_DATE);
    StringReplace(todayDateStr, ".", "-");
    
    // Jika file hari ini sudah ada di sandbox (artinya sudah berhasil di-sync dari restart),
    // maka kita TIDAK boleh mencari dan me-rename file hari sebelumnya.
    string todayFilename = "LLHHBOSData_" + _Symbol + "_" + todayDateStr + ".csv";
    if (FileIsExist(todayFilename))
    {
        Print("ℹ️ [SYNC LAST SESSION] Today's file already exists in sandbox. Skipping previous session sync.");
        return;
    }
    
    // Ambil prefix "YYYY-MM" dari tanggal hari ini (misal "2026-06")
    string yearMonth = StringSubstr(todayDateStr, 0, 7);
    int todayDay = dt.day;
    
    string prevDateStr = "";
    
    // Scan mundur dari kemarin sampai tanggal 1 di bulan yang sama
    for (int d = todayDay - 1; d >= 1; d--)
    {
        string checkDateStr = StringFormat("%s-%02d", yearMonth, d);
        string csvFilename = "LLHHBOSData_" + _Symbol + "_" + checkDateStr + ".csv";
        string srcPath = BacktestResultPath + "\\" + csvFilename;
        string dstPath = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + csvFilename;
        
        if (CopyFileW(srcPath, dstPath, false))
        {
            prevDateStr = checkDateStr;
            PrintFormat("🔍 [SYNC LAST SESSION] Found previous session file from date: %s", prevDateStr);
            break;
        }
    }
    
    // Jika tidak ditemukan LLHHBOSData, coba scan Backtest_Results
    if (prevDateStr == "")
    {
        for (int d = todayDay - 1; d >= 1; d--)
        {
            string checkDateStr = StringFormat("%s-%02d", yearMonth, d);
            string csvFilename = "Backtest_Results_" + _Symbol + "_" + checkDateStr + ".csv";
            string srcPath = BacktestResultPath + "\\" + csvFilename;
            string dstPath = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + csvFilename;
            
            if (CopyFileW(srcPath, dstPath, false))
            {
                prevDateStr = checkDateStr;
                PrintFormat("🔍 [SYNC LAST SESSION] Found previous session results file from date: %s", prevDateStr);
                break;
            }
        }
    }
    
    // Jika ditemukan, copy file lainnya dari tanggal tersebut (jika ada)
    if (prevDateStr != "")
    {
        // 1. Copy LLHHBOSData (jika tadi belum tercopy)
        string fileLLHH = "LLHHBOSData_" + _Symbol + "_" + prevDateStr + ".csv";
        string srcLLHH = BacktestResultPath + "\\" + fileLLHH;
        string dstLLHH = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + fileLLHH;
        if (!FileIsExist(fileLLHH))
        {
            CopyFileW(srcLLHH, dstLLHH, false);
        }
        
        // 2. Copy Backtest_Results
        string fileResults = "Backtest_Results_" + _Symbol + "_" + prevDateStr + ".csv";
        string srcResults = BacktestResultPath + "\\" + fileResults;
        string dstResults = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + fileResults;
        if (CopyFileW(srcResults, dstResults, false))
        {
            PrintFormat("   ✅ Synced results: %s", fileResults);
        }
        
        // 3. Copy Backtest_Summary
        string fileSummary = "Backtest_Summary_" + _Symbol + "_" + prevDateStr + ".csv";
        string srcSummary = BacktestResultPath + "\\" + fileSummary;
        string dstSummary = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + fileSummary;
        if (CopyFileW(srcSummary, dstSummary, false))
        {
            PrintFormat("   ✅ Synced summary: %s", fileSummary);
        }
        
        // 4. Copy MarketStructure_State
        string fileState = "MarketStructure_State_" + _Symbol + "_" + prevDateStr + ".txt";
        string srcState = BacktestResultPath + "\\" + fileState;
        string dstState = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + fileState;
        if (CopyFileW(srcState, dstState, false))
        {
            PrintFormat("   ✅ Synced state: %s", fileState);
        }

        // ponytail: was missing — MarketData & SessionZone not synced on restart-resume,
        // so after a restart the sandbox kept stale-date files.
        string tfs[] = {"M15", "H1", "H4"};
        for (int t = 0; t < 3; t++)
        {
            string fileMD = "MarketData_" + _Symbol + "_" + tfs[t] + "_" + prevDateStr + ".csv";
            string srcMD = BacktestResultPath + "\\" + fileMD;
            string dstMD = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + fileMD;
            if (CopyFileW(srcMD, dstMD, false))
                PrintFormat("   ✅ Synced MarketData: %s", fileMD);
        }

        string fileSZ = "SessionZone_" + _Symbol + "_" + prevDateStr + ".csv";
        string srcSZ = BacktestResultPath + "\\" + fileSZ;
        string dstSZ = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + fileSZ;
        if (CopyFileW(srcSZ, dstSZ, false))
            PrintFormat("   ✅ Synced SessionZone: %s", fileSZ);
    }
    else
    {
        // [FIX] Fallback ke bulan sebelumnya — kasus EA mati akhir bulan, restart awal bulan baru.
        int prevMonth = dt.mon - 1;
        int prevYear  = dt.year;
        if (prevMonth < 1) { prevMonth = 12; prevYear--; }
        string prevYearMonth = StringFormat("%d-%02d", prevYear, prevMonth);
        
        for (int d = 31; d >= 1; d--)
        {
            string checkDateStr = StringFormat("%s-%02d", prevYearMonth, d);
            string csvFilename  = "LLHHBOSData_" + _Symbol + "_" + checkDateStr + ".csv";
            string srcPath = BacktestResultPath + "\\" + csvFilename;
            string dstPath = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + csvFilename;
            if (CopyFileW(srcPath, dstPath, false))
            {
                prevDateStr = checkDateStr;
                PrintFormat("🔍 [SYNC LAST SESSION] Bulan ini kosong → pakai session bulan lalu: %s", prevDateStr);
                break;
            }
        }
        
        if (prevDateStr != "")
        {
            // Copy file pendamping dari tanggal yang sama
            string fileState = "MarketStructure_State_" + _Symbol + "_" + prevDateStr + ".txt";
            string srcState  = BacktestResultPath + "\\" + fileState;
            string dstState  = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + fileState;
            if (CopyFileW(srcState, dstState, false))
                PrintFormat("   ✅ Synced state (prev month): %s", fileState);
            
            string fileResults = "Backtest_Results_" + _Symbol + "_" + prevDateStr + ".csv";
            string srcResults  = BacktestResultPath + "\\" + fileResults;
            string dstResults  = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + fileResults;
            CopyFileW(srcResults, dstResults, false);
            
            string fileSummary = "Backtest_Summary_" + _Symbol + "_" + prevDateStr + ".csv";
            string srcSummary  = BacktestResultPath + "\\" + fileSummary;
            string dstSummary  = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + fileSummary;
            CopyFileW(srcSummary, dstSummary, false);
        }
        else
        {
            Print("ℹ️ [SYNC LAST SESSION] No previous session files found in BacktestResultPath for this month.");
        }
    }
}

//+------------------------------------------------------------------+
//| SYNC BACKTEST CSV - Copy backtest CSV ke MQL5 sandbox              |
//| Memastikan EA live trading punya full history dari backtest        |
//| Menggunakan WinAPI CopyFileW (butuh "Allow DLL Imports")           |
//+------------------------------------------------------------------+
void SyncBacktestCSV()
{
    bool isLiveTrading = !(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION));
    if (!isLiveTrading) return;
    if (BacktestResultPath == "") return;
    
    datetime currentTime = TimeCurrent();
    MqlDateTime dt;
    TimeToStruct(currentTime, dt);
    
    string todayDateStr = TimeToString(currentTime, TIME_DATE);
    StringReplace(todayDateStr, ".", "-");
    string csvFilename = "LLHHBOSData_" + _Symbol + "_" + todayDateStr + ".csv";
    
    string srcPath = BacktestResultPath + "\\" + csvFilename;
    string dstPath = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + csvFilename;
    
    // Copy file dari backtest result ke MQL5 sandbox
    if (CopyFileW(srcPath, dstPath, false))
    {
        Print("✅ [SYNC CSV] Backtest data synced to sandbox: ", csvFilename);
        return;
    }
    
    // [FIX] Fallback ke bulan sebelumnya jika file hari ini belum ada di BacktestResultPath
    int prevMonth = dt.mon - 1;
    int prevYear  = dt.year;
    if (prevMonth < 1) { prevMonth = 12; prevYear--; }
    string prevYearMonth = StringFormat("%d-%02d", prevYear, prevMonth);
    
    string fallbackFile = "";
    for (int d = 31; d >= 1; d--)
    {
        string checkDateStr = StringFormat("%s-%02d", prevYearMonth, d);
        string checkFilename = "LLHHBOSData_" + _Symbol + "_" + checkDateStr + ".csv";
        string checkSrcPath = BacktestResultPath + "\\" + checkFilename;
        string checkDstPath = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + checkFilename;
        
        if (CopyFileW(checkSrcPath, checkDstPath, false))
        {
            fallbackFile = checkFilename;
            Print("✅ [SYNC CSV] Bulan ini kosong → sync backtest bulan lalu ke sandbox: ", fallbackFile);
            break;
        }
    }
    
    if (fallbackFile == "")
    {
        int err = GetLastError();
        if (err == 5019) // ERR_DLL_CALLS_PROHIBITED
            Print("❌ [SYNC CSV] Gagal sync. Harap centang 'Allow DLL imports' di setelan EA.");
        else
            Print("ℹ️ [SYNC CSV] Tidak ada file backtest baru untuk disinkronkan.");
    }
}

//+------------------------------------------------------------------+
//| REVERSE SYNC CSV - Copy MQL5\Files\ ke Backtest_result\            |
//| Memastikan Backtest_result selalu berisi data terbaru (overwrite)  |
//| Menggunakan WinAPI CopyFileW (butuh "Allow DLL Imports")           |
//+------------------------------------------------------------------+
void ReverseSyncCSV()
{
    bool isLiveTrading = !(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION));
    if (!isLiveTrading) return;
    if (BacktestResultPath == "") return;
    if (g_ExportDateStr == "") return;
    
    // 1. Sync LLHHBOSData
    string csvFilename = "LLHHBOSData_" + _Symbol + "_" + g_ExportDateStr + ".csv";
    string srcPath = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + csvFilename;
    string dstPath = BacktestResultPath + "\\" + csvFilename;
    if (!CopyFileW(srcPath, dstPath, false))
    {
        int err = GetLastError();
        if (err != 2) // Don't log FILE_NOT_FOUND
            Print("❌ [REVERSE SYNC] Failed LLHHBOSData: error ", err);
    }
    
    // 2. Sync Backtest_Results
    string resultsFilename = "Backtest_Results_" + _Symbol + "_" + g_ExportDateStr + ".csv";
    string srcResults = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + resultsFilename;
    string dstResults = BacktestResultPath + "\\" + resultsFilename;
    if (FileIsExist(resultsFilename))
    {
        if (!CopyFileW(srcResults, dstResults, false))
        {
            int err = GetLastError();
            Print("❌ [REVERSE SYNC] Failed Backtest_Results: error ", err);
        }
    }
    
    // 3. Sync Backtest_Summary
    string summaryFilename = "Backtest_Summary_" + _Symbol + "_" + g_ExportDateStr + ".csv";
    string srcSummary = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + summaryFilename;
    string dstSummary = BacktestResultPath + "\\" + summaryFilename;
    if (FileIsExist(summaryFilename))
    {
        if (!CopyFileW(srcSummary, dstSummary, false))
        {
            int err = GetLastError();
            Print("❌ [REVERSE SYNC] Failed Backtest_Summary: error ", err);
        }
    }
    
    // 4. Sync MarketStructure_State
    string stateFilename = "MarketStructure_State_" + _Symbol + "_" + g_ExportDateStr + ".txt";
    string srcState = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + stateFilename;
    string dstState = BacktestResultPath + "\\" + stateFilename;
    if (FileIsExist(stateFilename))
    {
        if (!CopyFileW(srcState, dstState, false))
        {
            int err = GetLastError();
            Print("❌ [REVERSE SYNC] Failed MarketStructure_State: error ", err);
        }
    }

    // ponytail: was missing — MarketData & SessionZone never synced back to Backtest_result,
    // so the folder kept stale dates while sandbox advanced.
    string tfs[] = {"M15", "H1", "H4"};
    for (int t = 0; t < 3; t++)
    {
        string mdFilename = "MarketData_" + _Symbol + "_" + tfs[t] + "_" + g_ExportDateStr + ".csv";
        string srcMD = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + mdFilename;
        string dstMD = BacktestResultPath + "\\" + mdFilename;
        if (FileIsExist(mdFilename))
        {
            if (!CopyFileW(srcMD, dstMD, false))
            {
                int err = GetLastError();
                if (err != 2)
                    PrintFormat("❌ [REVERSE SYNC] Failed MarketData %s: error %d", tfs[t], err);
            }
        }
    }

    string szFilename = "SessionZone_" + _Symbol + "_" + g_ExportDateStr + ".csv";
    string srcSZ = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + szFilename;
    string dstSZ = BacktestResultPath + "\\" + szFilename;
    if (FileIsExist(szFilename))
    {
        if (!CopyFileW(srcSZ, dstSZ, false))
        {
            int err = GetLastError();
            if (err != 2)
                Print("❌ [REVERSE SYNC] Failed SessionZone: error ", err);
        }
    }
}

//+------------------------------------------------------------------+
//| Helper dedup visual: waktu formasi TERTUA harga-sama (window)     |
//| Dipakai HANYA di RedrawVisualsFromCSV (jalur visual live, bukan   |
//| trade/backtest) untuk menarik garis LL/HH duplikat ke waktu       |
//| candle formasi asli. Window cegah merge level sah harga-sama jauh.|
//+------------------------------------------------------------------+
int g_AcceptedDedupWindowSec = 1209600; // 14 hari: window dedup harga-sama LL/HH (cover konsolidasi panjang sebelum CHoCH)

// Waktu formasi TERTUA untuk harga tertentu DALAM window dari refTime. 0 jika tak ada.
// Match harga EXACT-cent (< _Point) — duplikat MODE1 selalu copy harga persis, jadi exact
// match cegah merge level sah beda-cent walau window besar.
datetime OldestTimeForPrice(double &priceArr[], datetime &timeArr[], int cnt, double price, datetime refTime)
{
    datetime oldest = 0;
    for (int i = 0; i < cnt; i++)
    {
        if (MathAbs(priceArr[i] - price) >= _Point) continue; // beda cent → bukan duplikat
        long dt = (long)timeArr[i] - (long)refTime; if (dt < 0) dt = -dt;
        if (dt > g_AcceptedDedupWindowSec) continue;
        if (oldest == 0 || timeArr[i] < oldest) oldest = timeArr[i];
    }
    return oldest;
}

//+------------------------------------------------------------------+
//| LOAD CSV TO ARRAYS - Load LLHHBOSData CSV ke memory arrays       |
//| Mencegah ExportLLHHBOSToCSV overwrite file dengan data kosong    |
//| Dipanggil saat EA di-attach (live trading) SEBELUM export        |
//+------------------------------------------------------------------+
void LoadLLHHBOSDataToArrays()
{
    // Cari CSV file — scan mundur dari hari ini sampai tanggal 1 di bulan yang sama.
    // ponytail: was only today/yesterday; EA sering off >2 hari (mis. weekend/long gap),
    // sehingga file history tertua terlewat. Scan mundur konsisten dengan LoadMarketStructureState.
    datetime currentTime = TimeCurrent();
    MqlDateTime dt;
    TimeToStruct(currentTime, dt);

    string yearMonth = StringSubstr(TimeToString(currentTime, TIME_DATE), 0, 7);
    StringReplace(yearMonth, ".", "-");
    int todayDay = dt.day;

    string csvFile = "";
    for (int d = todayDay; d >= 1; d--)
    {
        string checkDateStr = StringFormat("%s-%02d", yearMonth, d);
        string candidate = "LLHHBOSData_" + _Symbol + "_" + checkDateStr + ".csv";
        if (FileIsExist(candidate))
        {
            csvFile = candidate;
            break;
        }
    }

    if (csvFile == "")
    {
        // [FIX] Fallback ke bulan sebelumnya — kasus EA mati akhir bulan, restart awal bulan baru.
        int prevMonth2 = dt.mon - 1;
        int prevYear2  = dt.year;
        if (prevMonth2 < 1) { prevMonth2 = 12; prevYear2--; }
        string prevYearMonth2 = StringFormat("%d-%02d", prevYear2, prevMonth2);
        
        for (int d = 31; d >= 1; d--)
        {
            string checkDateStr = StringFormat("%s-%02d", prevYearMonth2, d);
            string candidate    = "LLHHBOSData_" + _Symbol + "_" + checkDateStr + ".csv";
            if (FileIsExist(candidate))
            {
                csvFile = candidate;
                PrintFormat("📂 [LOAD DATA] Bulan ini kosong → load history bulan lalu: %s", csvFile);
                break;
            }
        }
    }

    if (csvFile == "")
    {
        Print("ℹ️ [LOAD DATA] No LLHHBOSData CSV found to load into arrays");
        return;
    }
    
    Print("📂 [LOAD DATA] Loading history from: ", csvFile);
    
    int handle = FileOpen(csvFile, FILE_READ|FILE_CSV|FILE_ANSI, ",");
    if (handle == INVALID_HANDLE)
    {
        Print("❌ [LOAD DATA] Failed to open CSV: ", csvFile);
        return;
    }
    
    // Skip rows until header row (starting with "Type") is found
    for (int skipI = 0; skipI < 100; skipI++)
    {
        string hdr = FileReadString(handle);
        if (hdr == "Type")
        {
            for (int j = 0; j < 7; j++) FileReadString(handle);
            break;
        }
        if (FileIsEnding(handle)) break;
    }
    
    int loadedCount = 0;
    
    while (!FileIsEnding(handle))
    {
        string type = FileReadString(handle);
        if (type == "" || FileIsEnding(handle)) continue; // ponytail: blank line? skip, NOT break
        
        string direction = FileReadString(handle);
        string priceStr  = FileReadString(handle);
        string timeStr   = FileReadString(handle);
        string tf        = FileReadString(handle);
        string status    = FileReadString(handle);
        string prevPriceStr = FileReadString(handle);
        string prevTimeStr  = FileReadString(handle);
        
        double price = StringToDouble(priceStr);
        datetime time = StringToTime(timeStr);
        double prevPrice = StringToDouble(prevPriceStr);
        datetime prevTime = StringToTime(prevTimeStr);
        
        if (price <= 0 || time == 0) continue;
        
        // Load CHoCH/BoS ke g_LLHHBOSData
        if ((type == "CHoCH" || type == "BoS") && status == "Confirmed")
        {
            SaveLLHHBOSToArray(type, direction, price, time, tf, status, prevPrice, prevTime);
            loadedCount++;
        }
        // Load HH/LL Accepted ke g_AcceptedLevelHistory
        else if ((type == "HH" || type == "LL") && status == "Accepted")
        {
            SaveAcceptedLevelToHistory(type, price, time, tf);
            loadedCount++;
        }
    }
    
    FileClose(handle);
    PrintFormat("✅ [LOAD DATA] Loaded %d events into arrays (CHoCH/BoS: %d, HH/LL: %d)",
                loadedCount, g_LLHHBOSCount, g_AcceptedLevelHistoryCount);
}

//+------------------------------------------------------------------+
//| REDRAW VISUALS FROM CSV - Baca LLHHBOSData CSV & gambar ulang    |
//| Dipanggil saat EA di-attach (live trading) untuk redraw history   |
//| Visual only: TIDAK mengubah state logic atau history arrays       |
//| Line berhenti saat candle M15 close menembus level (break)        |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Helper: cek apakah suatu level sudah di-supersede (ditembus break) |
//| MQL5 tidak support array assignment, jadi array dilewatkan by-ref  |
//+------------------------------------------------------------------+
bool IsLevelSuperseded(double &breakArr[], int breakCnt, double price, double tolerance)
{
    for (int b = 0; b < breakCnt; b++)
    {
        if (MathAbs(breakArr[b] - price) <= tolerance)
            return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| Helper: cari formation time dari HH/LL array berdasarkan price      |
//| Return: time formation jika ketemu (price match), 0 jika tidak     |
//| Digunakan untuk CHoCH/BoS line start point (kiri = HH/LL formation)|
//+------------------------------------------------------------------+
datetime FindFormationTime(double &formPriceArr[], datetime &formTimeArr[], int formCnt, double price, double tolerance, datetime eventTime)
{
    // 1. Cari formasi TERBARU yang cocok harga & sebelum eventTime (ujung cluster).
    datetime latest = 0;
    for (int i = 0; i < formCnt; i++)
        if (MathAbs(formPriceArr[i] - price) <= tolerance && formTimeArr[i] < eventTime)
            if (formTimeArr[i] > latest) latest = formTimeArr[i];
    if (latest == 0) return 0;

    // 2. Dari cluster (formasi dalam window SEBELUM 'latest'), ambil yang TERTUA.
    //    Tujuan: titik formasi ASLI (mis. HH 06.29 20:00), bukan duplikat stale yang
    //    ter-stamp di waktu candle lain (mis. 06.30 04:00). Match EXACT-cent + window
    //    cegah ikut-sertanya formasi harga beda-cent / periode jauh.
    datetime found = latest;
    for (int i = 0; i < formCnt; i++)
    {
        if (MathAbs(formPriceArr[i] - price) >= _Point) continue; // exact-cent only
        if (formTimeArr[i] >= eventTime) continue;
        long gap = (long)latest - (long)formTimeArr[i];
        if (gap >= 0 && gap <= g_AcceptedDedupWindowSec && formTimeArr[i] < found)
            found = formTimeArr[i];
    }
    return found;
}

void RedrawVisualsFromCSV()
{
    // ponytail: hapus semua objek redraw_* lama dulu → clean slate. Tanpa ini, garis
    // yang sekarang di-skip dedup (mis. LL dup di waktu salah) nyangkut dari attach
    // sebelumnya karena redraw cuma hapus-per-nama untuk garis yang DIA gambar.
    for (int c = ObjectsTotal(0) - 1; c >= 0; c--)
    {
        string nmDel = ObjectName(0, c);
        if (StringFind(nmDel, "redraw_") == 0)
            ObjectDelete(0, nmDel);
    }

    // ponytail: scan mundur dari hari ini sampai tanggal 1 di bulan yang sama.
    // sama seperti LoadLLHHBOSDataToArrays — konsisten untuk EA off >2 hari.
    datetime currentTime = TimeCurrent();
    MqlDateTime dt;
    TimeToStruct(currentTime, dt);

    string yearMonth = StringSubstr(TimeToString(currentTime, TIME_DATE), 0, 7);
    StringReplace(yearMonth, ".", "-");
    int todayDay = dt.day;

    string csvFile = "";
    for (int d = todayDay; d >= 1; d--)
    {
        string checkDateStr = StringFormat("%s-%02d", yearMonth, d);
        string candidate = "LLHHBOSData_" + _Symbol + "_" + checkDateStr + ".csv";
        if (FileIsExist(candidate))
        {
            csvFile = candidate;
            break;
        }
    }

    if (csvFile == "")
    {
        Print("ℹ️ [REDRAW] No LLHHBOSData CSV found for visual redraw");
        return;
    }
    
    Print("📂 [REDRAW] Reading visual data from: ", csvFile);
    
    int handle = FileOpen(csvFile, FILE_READ|FILE_CSV|FILE_ANSI, ",");
    if (handle == INVALID_HANDLE)
    {
        Print("❌ [REDRAW] Failed to open CSV: ", csvFile);
        return;
    }
    
    // ===== PASS 1: Kumpulkan harga break (CHoCH/BoS Confirmed) per arah + timeframe =====
    // Tujuan: HH/LL yang levelnya sudah ditembus CHoCH/BoS di-skip dari gambar
    // karena break event lebih signifikan daripada swing formation.
    // Aturan market structure:
    //   - CHoCH/BoS Bullish break HH → HH di-supersede
    //   - CHoCH/BoS Bearish break LL → LL di-supersede
    
    double breakUpM15[],   breakDownM15[];   // breakUp = Bullish (break HH), breakDown = Bearish (break LL)
    double breakUpH1[],    breakDownH1[];
    int    breakUpCntM15=0, breakDownCntM15=0;
    int    breakUpCntH1=0,  breakDownCntH1=0;
    
    // Collection HH/LL formation time per price (untuk CHoCH/BoS line start point)
    // CHoCH/BoS Bullish cari HH formation time, CHoCH/BoS Bearish cari LL formation time
    double hhFormPriceM15[],  hhFormPriceH1[];
    datetime hhFormTimeM15[], hhFormTimeH1[];
    double llFormPriceM15[],  llFormPriceH1[];
    datetime llFormTimeM15[], llFormTimeH1[];
    int hhFormCntM15=0, hhFormCntH1=0;
    int llFormCntM15=0, llFormCntH1=0;
    
    // Skip rows until header row (starting with "Type") is found
    for (int skipI = 0; skipI < 100; skipI++)
    {
        string hdr = FileReadString(handle);
        if (hdr == "Type")
        {
            for (int j = 0; j < 7; j++) FileReadString(handle);
            break;
        }
        if (FileIsEnding(handle)) break;
    }
    
    while (!FileIsEnding(handle))
    {
        string p1_type   = FileReadString(handle);
        if (p1_type == "" || FileIsEnding(handle)) continue; // ponytail: blank line? skip, NOT break — don't lose events after blanks
        
        string p1_dir    = FileReadString(handle);
        string p1_priceS = FileReadString(handle);
        string p1_timeS  = FileReadString(handle);  // BACA time (bukan skip)
        string p1_tf     = FileReadString(handle);
        string p1_stat   = FileReadString(handle);
        string p1_pP     = FileReadString(handle);  // prevPrice
        string p1_pT     = FileReadString(handle);  // prevTime
        
        double   p1_price = StringToDouble(p1_priceS);
        datetime p1_time  = StringToTime(p1_timeS);
        bool     isM15tf  = (p1_tf == "M15");
        
        // Collect break levels (CHoCH/BoS Confirmed) untuk supersede filter
        if ((p1_type == "CHoCH" || p1_type == "BoS") && p1_stat == "Confirmed")
        {
            if (p1_price <= 0) continue;
            
            bool isUp = (p1_dir == "Bullish");
            
            if      (isM15tf &&  isUp) { ArrayResize(breakUpM15,   breakUpCntM15+1);   breakUpM15[breakUpCntM15]   = p1_price; breakUpCntM15++; }
            else if (isM15tf && !isUp) { ArrayResize(breakDownM15, breakDownCntM15+1); breakDownM15[breakDownCntM15] = p1_price; breakDownCntM15++; }
            else if (!isM15tf &&  isUp){ ArrayResize(breakUpH1,    breakUpCntH1+1);    breakUpH1[breakUpCntH1]    = p1_price; breakUpCntH1++; }
            else                        { ArrayResize(breakDownH1,  breakDownCntH1+1);  breakDownH1[breakDownCntH1]  = p1_price; breakDownCntH1++; }
        }
        // Collect HH/LL formation times untuk CHoCH/BoS line start point
        else if ((p1_type == "HH" || p1_type == "LL") && p1_stat == "Accepted")
        {
            if (p1_price <= 0 || p1_time == 0) continue;
            
            bool isHH = (p1_type == "HH");
            
            if (isHH)
            {
                if (isM15tf) { ArrayResize(hhFormPriceM15, hhFormCntM15+1); hhFormPriceM15[hhFormCntM15] = p1_price; ArrayResize(hhFormTimeM15, hhFormCntM15+1); hhFormTimeM15[hhFormCntM15] = p1_time; hhFormCntM15++; }
                else        { ArrayResize(hhFormPriceH1,  hhFormCntH1+1);  hhFormPriceH1[hhFormCntH1]  = p1_price; ArrayResize(hhFormTimeH1,  hhFormCntH1+1);  hhFormTimeH1[hhFormCntH1]  = p1_time; hhFormCntH1++; }
            }
            else
            {
                if (isM15tf) { ArrayResize(llFormPriceM15, llFormCntM15+1); llFormPriceM15[llFormCntM15] = p1_price; ArrayResize(llFormTimeM15, llFormCntM15+1); llFormTimeM15[llFormCntM15] = p1_time; llFormCntM15++; }
                else        { ArrayResize(llFormPriceH1,  llFormCntH1+1);  llFormPriceH1[llFormCntH1]  = p1_price; ArrayResize(llFormTimeH1,  llFormCntH1+1);  llFormTimeH1[llFormCntH1]  = p1_time; llFormCntH1++; }
            }
        }
    }
    FileClose(handle);
    
    PrintFormat("📊 [REDRAW] Pass 1 - Break levels M15 up:%d down:%d | H1 up:%d down:%d",
                breakUpCntM15, breakDownCntM15, breakUpCntH1, breakDownCntH1);
    PrintFormat("📊 [REDRAW] Pass 1 - Formation times M15 HH:%d LL:%d | H1 HH:%d LL:%d",
                hhFormCntM15, llFormCntM15, hhFormCntH1, llFormCntH1);
    
    // ===== PASS 2: Baca ulang + gambar dengan filter overlap =====
    handle = FileOpen(csvFile, FILE_READ|FILE_CSV|FILE_ANSI, ",");
    if (handle == INVALID_HANDLE)
    {
        Print("❌ [REDRAW] Failed to reopen CSV: ", csvFile);
        return;
    }
    
    // Load M15 candle data for break detection (~104 days of history)
    MqlRates rates_M15[];
    ArraySetAsSeries(rates_M15, true);
    int copied_M15 = CopyRates(_Symbol, PERIOD_M15, 0, 10000, rates_M15);
    int m15PeriodSec = PeriodSeconds(PERIOD_M15);
    
    // Skip rows until header row (starting with "Type") is found
    for (int skipI = 0; skipI < 100; skipI++)
    {
        string hdr = FileReadString(handle);
        if (hdr == "Type")
        {
            for (int j = 0; j < 7; j++) FileReadString(handle);
            break;
        }
        if (FileIsEnding(handle)) break;
    }
    
    int hhCount = 0, llCount = 0, chochCount = 0, bosCount = 0;
    int hhSuperseded = 0, llSuperseded = 0;
    
    // HH/LL validation filter: track last accepted level per timeframe
    // Replikasi perilaku live detection — hanya accept HH > lastAcceptedHH, LL < lastAcceptedLL
    // Init = 0 (process full CSV from start). CHoCH/BoS events reset tracker ke -1 (allow next HH/LL).
    double redrawLastHH_M15 = 0;
    double redrawLastLL_M15 = 0;
    double redrawLastHH_H1  = 0;
    double redrawLastLL_H1  = 0;
    
    while (!FileIsEnding(handle))
    {
        string type = FileReadString(handle);
        if (type == "" || FileIsEnding(handle)) continue; // ponytail: blank line? skip, NOT break
        
        string direction  = FileReadString(handle);
        string priceStr   = FileReadString(handle);
        string timeStr    = FileReadString(handle);
        string tf         = FileReadString(handle);
        string status     = FileReadString(handle);
        string prevPriceStr = FileReadString(handle);
        string prevTimeStr  = FileReadString(handle);
        
        double price = StringToDouble(priceStr);
        datetime time = StringToTime(timeStr);
        
        if (price <= 0 || time == 0) continue;
        
        // Determine visual properties
        bool isM15 = (tf == "M15");
        string tfSuffix = isM15 ? "_M15" : "_H1";

        // ✅ Skip draw H1 bila EnableDrawLines_H1 dimatikan (M15 tetap digambar)
        if (!EnableDrawLines_H1 && !isM15)
            continue;

        // ponytail: REMAP waktu HH/LL Accepted ke formasi TERTUA harga-sama (dedup keep oldest).
        // Duplikat lama (mis. LL ter-stamp di waktu candle HH setelah CHoCH) di-tarik ke waktu
        // candle low/high asli → garis & nama objek canonical. Filter redrawLastLL tetap jalan;
        // occurrence yang lolos filter menggambar di waktu tertua ini (nama objek sama → 1 garis).
        if (status == "Accepted")
        {
            datetime oldT = 0;
            if (type == "HH")
                oldT = isM15 ? OldestTimeForPrice(hhFormPriceM15, hhFormTimeM15, hhFormCntM15, price, time)
                             : OldestTimeForPrice(hhFormPriceH1,  hhFormTimeH1,  hhFormCntH1,  price, time);
            else if (type == "LL")
                oldT = isM15 ? OldestTimeForPrice(llFormPriceM15, llFormTimeM15, llFormCntM15, price, time)
                             : OldestTimeForPrice(llFormPriceH1,  llFormTimeH1,  llFormCntH1,  price, time);
            if (oldT > 0) time = oldT;
        }
        
        // Find break point: first M15 candle after event whose close penetrates the level
        datetime lineEndTime = 0;
        if (copied_M15 > 0)
        {
            for (int k = copied_M15 - 1; k >= 0; k--)
            {
                if (rates_M15[k].time <= time) continue;
                
                bool broken = false;
                if (type == "HH" || (type == "CHoCH" && direction == "Bullish") || (type == "BoS" && direction == "Bullish"))
                    broken = (rates_M15[k].close > price);
                else if (type == "LL" || (type == "CHoCH" && direction == "Bearish") || (type == "BoS" && direction == "Bearish"))
                    broken = (rates_M15[k].close < price);
                
                if (broken)
                {
                    lineEndTime = rates_M15[k].time;
                    break;
                }
            }
        }
        
        // CHoCH/BoS Confirmed: reset HH/LL tracker untuk timeframe yang sama
        // Setelah structural change, HH/LL berikutnya boleh menjadi referensi baru
        if ((type == "CHoCH" || type == "BoS") && status == "Confirmed")
        {
            if (isM15) { redrawLastHH_M15 = -1; redrawLastLL_M15 = -1; }
            else       { redrawLastHH_H1  = -1; redrawLastLL_H1  = -1; }
        }
        
        // 🔧 CHoCH/BoS: break sudah terjadi SAAT event, jadi jangan cari break point lanjutan.
        // Paksa extend ke currentTime + buffer supaya garis terlihat (sebelumnya cuma 1 bar = invisible).
        // HH/LL tetap pakai lineEndTime dari break detection di atas.
        if (type == "CHoCH" || type == "BoS")
        {
            lineEndTime = 0;  // reset, biarkan logic di bawah yang extend
        }
        
        // No break found: garis HH/LL belum-break dibatasi panjang MaxLineLengthBars candle.
        if (lineEndTime == 0)
            lineEndTime = time + MaxLineLengthBars * m15PeriodSec;
        
        // Minimum 1 bar width
        if (lineEndTime <= time)
            lineEndTime = time + m15PeriodSec;

        // Cap panjang garis HH/LL maksimal MaxLineLengthBars candle dari formasi — termasuk
        // yang SUDAH di-break tapi break-nya jauh (mis. LL 4121) → garis tidak terlalu panjang.
        // CHoCH/BoS tidak terpengaruh (pakai 'time' sebagai endpoint, bukan lineEndTime).
        if (type == "HH" || type == "LL")
        {
            datetime lenCap = time + MaxLineLengthBars * m15PeriodSec;
            if (lineEndTime > lenCap) lineEndTime = lenCap;
        }
        
        // === Draw HH Accepted ===
        if (type == "HH" && status == "Accepted")
        {
            // ponytail: filter monotonic "HH harus > lastHH" DIHAPUS — dulu menolak Lower-High (LH)
            // yang valid di fase bearish (mis. HH 4144.9 = LH referensi BoS Bearish). CSV hanya berisi
            // level Accepted (sudah divalidasi live) → gambar semua, kecuali yang superseded di bawah.
            
            // 🔧 FILTER OVERLAP: Skip HH yang sudah ditembus CHoCH/BoS Bullish di level sama
            // Break event (CHoCH/BoS Bullish) lebih signifikan → HH formation di-hide
            double levelTolerance = 5 * _Point;  // toleransi floating point
            bool isHhSuperseded = isM15
                ? IsLevelSuperseded(breakUpM15, breakUpCntM15, price, levelTolerance)
                : IsLevelSuperseded(breakUpH1,  breakUpCntH1,  price, levelTolerance);
            
            if (isHhSuperseded)
            {
                hhSuperseded++;  // counter untuk log
                continue;
            }
            
            color hhColor = isM15 ? clrBlue : clrOrange;
            string lineName = "redraw_HH" + tfSuffix + "_" + IntegerToString((int)time);
            
            ObjectDelete(0, lineName);
            ObjectCreate(0, lineName, OBJ_TREND, 0, time, price, lineEndTime, price);
            ObjectSetInteger(0, lineName, OBJPROP_COLOR, hhColor);
            ObjectSetInteger(0, lineName, OBJPROP_WIDTH, 1);
            ObjectSetInteger(0, lineName, OBJPROP_STYLE, STYLE_DASHDOT);
            ObjectSetInteger(0, lineName, OBJPROP_RAY_RIGHT, false);
            ObjectSetInteger(0, lineName, OBJPROP_RAY_LEFT, false);
            ObjectSetInteger(0, lineName, OBJPROP_BACK, true);
            hhCount++;
        }
        // === Draw LL Accepted ===
        else if (type == "LL" && status == "Accepted")
        {
            // ponytail: filter monotonic "LL harus < lastLL" DIHAPUS — dulu menolak Higher-Low (HL)
            // yang valid di fase bullish. CSV hanya berisi level Accepted → gambar semua, kecuali
            // yang superseded di bawah.
            
            // 🔧 FILTER OVERLAP: Skip LL yang sudah ditembus CHoCH/BoS Bearish di level sama
            // Break event (CHoCH/BoS Bearish) lebih signifikan → LL formation di-hide
            double levelTolerance = 5 * _Point;  // toleransi floating point
            bool isLlSuperseded = isM15
                ? IsLevelSuperseded(breakDownM15, breakDownCntM15, price, levelTolerance)
                : IsLevelSuperseded(breakDownH1,  breakDownCntH1,  price, levelTolerance);
            
            if (isLlSuperseded)
            {
                llSuperseded++;  // counter untuk log
                continue;
            }
            
            color llColor = isM15 ? clrMagenta : clrAqua;
            string lineName = "redraw_LL" + tfSuffix + "_" + IntegerToString((int)time);
            
            ObjectDelete(0, lineName);
            ObjectCreate(0, lineName, OBJ_TREND, 0, time, price, lineEndTime, price);
            ObjectSetInteger(0, lineName, OBJPROP_COLOR, llColor);
            ObjectSetInteger(0, lineName, OBJPROP_WIDTH, 1);
            ObjectSetInteger(0, lineName, OBJPROP_STYLE, STYLE_DASHDOT);
            ObjectSetInteger(0, lineName, OBJPROP_RAY_RIGHT, false);
            ObjectSetInteger(0, lineName, OBJPROP_RAY_LEFT, false);
            ObjectSetInteger(0, lineName, OBJPROP_BACK, true);
            llCount++;
        }
        // === Draw CHoCH Confirmed ===
        // 🔧 Line dari HH/LL formation (kiri) ke break candle (kanan), bukan extend ke kanan
        else if (type == "CHoCH" && status == "Confirmed")
        {
            color chochColor = (direction == "Bullish") ? clrLime : clrRed;
            string lineName = "redraw_CHoCH" + tfSuffix + "_" + IntegerToString((int)time);
            string labelName = lineName + "_label";
            
            // Cari formation time: CHoCH Bullish cari HH, CHoCH Bearish cari LL
            double levelTolerance = 5 * _Point;
            datetime lineStartTime = 0;
            if (direction == "Bullish")
            {
                lineStartTime = isM15
                    ? FindFormationTime(hhFormPriceM15, hhFormTimeM15, hhFormCntM15, price, levelTolerance, time)
                    : FindFormationTime(hhFormPriceH1,  hhFormTimeH1,  hhFormCntH1,  price, levelTolerance, time);
            }
            else
            {
                lineStartTime = isM15
                    ? FindFormationTime(llFormPriceM15, llFormTimeM15, llFormCntM15, price, levelTolerance, time)
                    : FindFormationTime(llFormPriceH1,  llFormTimeH1,  llFormCntH1,  price, levelTolerance, time);
            }
            
            // Fallback: jika formation time tidak ketemu, estimasi mundur 24 bar dari break
            if (lineStartTime == 0)
                lineStartTime = time - 24 * m15PeriodSec;
            
            // Minimum 1 bar width
            if (lineStartTime >= time)
                lineStartTime = time - m15PeriodSec;
            
            ObjectDelete(0, lineName);
            ObjectDelete(0, labelName);
            
            // Line: dari formation (kiri) ke break candle (kanan)
            ObjectCreate(0, lineName, OBJ_TREND, 0, lineStartTime, price, time, price);
            ObjectSetInteger(0, lineName, OBJPROP_COLOR, chochColor);
            ObjectSetInteger(0, lineName, OBJPROP_WIDTH, 1);
            ObjectSetInteger(0, lineName, OBJPROP_STYLE, STYLE_SOLID);
            ObjectSetInteger(0, lineName, OBJPROP_RAY_RIGHT, false);
            ObjectSetInteger(0, lineName, OBJPROP_RAY_LEFT, false);
            ObjectSetInteger(0, lineName, OBJPROP_BACK, true);
            
            // Label: di tengah garis (antara formation dan break)
            datetime labelTimeMid = (lineStartTime + time) / 2;
            ObjectCreate(0, labelName, OBJ_TEXT, 0, labelTimeMid, price + 8 * _Point);
            ObjectSetInteger(0, labelName, OBJPROP_COLOR, chochColor);
            ObjectSetInteger(0, labelName, OBJPROP_FONTSIZE, 9);
            ObjectSetString(0, labelName, OBJPROP_TEXT, "CHoCH" + tfSuffix);
            chochCount++;
        }
        // === Draw BoS Confirmed ===
        // 🔧 Line dari HH/LL formation (kiri) ke break candle (kanan), bukan extend ke kanan
        else if (type == "BoS" && status == "Confirmed")
        {
            color bosColor = (direction == "Bullish") ? clrDodgerBlue : clrOrangeRed;
            string lineName = "redraw_BoS" + tfSuffix + "_" + IntegerToString((int)time);
            string labelName = lineName + "_label";
            
            // Cari formation time: BoS Bullish cari HH, BoS Bearish cari LL
            double levelTolerance = 5 * _Point;
            datetime lineStartTime = 0;
            if (direction == "Bullish")
            {
                lineStartTime = isM15
                    ? FindFormationTime(hhFormPriceM15, hhFormTimeM15, hhFormCntM15, price, levelTolerance, time)
                    : FindFormationTime(hhFormPriceH1,  hhFormTimeH1,  hhFormCntH1,  price, levelTolerance, time);
            }
            else
            {
                lineStartTime = isM15
                    ? FindFormationTime(llFormPriceM15, llFormTimeM15, llFormCntM15, price, levelTolerance, time)
                    : FindFormationTime(llFormPriceH1,  llFormTimeH1,  llFormCntH1,  price, levelTolerance, time);
            }
            
            // Fallback: jika formation time tidak ketemu, estimasi mundur 24 bar dari break
            if (lineStartTime == 0)
                lineStartTime = time - 24 * m15PeriodSec;
            
            // Minimum 1 bar width
            if (lineStartTime >= time)
                lineStartTime = time - m15PeriodSec;
            
            ObjectDelete(0, lineName);
            ObjectDelete(0, labelName);
            
            // Line: dari formation (kiri) ke break candle (kanan)
            ObjectCreate(0, lineName, OBJ_TREND, 0, lineStartTime, price, time, price);
            ObjectSetInteger(0, lineName, OBJPROP_COLOR, bosColor);
            ObjectSetInteger(0, lineName, OBJPROP_WIDTH, 1);
            ObjectSetInteger(0, lineName, OBJPROP_STYLE, STYLE_SOLID);
            ObjectSetInteger(0, lineName, OBJPROP_RAY_RIGHT, false);
            ObjectSetInteger(0, lineName, OBJPROP_RAY_LEFT, false);
            ObjectSetInteger(0, lineName, OBJPROP_BACK, true);
            
            // Label: di tengah garis (antara formation dan break)
            datetime labelTimeMid = (lineStartTime + time) / 2;
            ObjectCreate(0, labelName, OBJ_TEXT, 0, labelTimeMid, price - 10 * _Point);
            ObjectSetInteger(0, labelName, OBJPROP_COLOR, bosColor);
            ObjectSetInteger(0, labelName, OBJPROP_FONTSIZE, 9);
            ObjectSetString(0, labelName, OBJPROP_TEXT, "BoS" + tfSuffix);
            bosCount++;
        }
    }
    
    FileClose(handle);
    
    // === REDRAW lastAcceptedHH/LL dari state file (level kunci trading) ===
    // Gambar garis horizontal paling tebal & jelas untuk level terakhir yang aktif.
    // 🔧 FIX: Gunakan FindFormationTime dari CSV (bukan lastTimeHH/LL dari state file).
    // lastTimeHH/LL bisa STALE jika WarmUp mengupdate lastAcceptedHH/LL tapi tidak lastTimeHH/LL.
    // FindFormationTime mencari waktu formation dari CSV (collected di Pass 1) → akurat.
    // Pass D'2099.01.01' sebagai eventTime agar semua formations valid (kita tidak punya eventTime untuk lastAccepted).

    datetime noTimeLimit = D'2099.01.01 00:00:00';

    // M15 - lastAcceptedHH
    if (lastAcceptedHH_M15 > 0)
    {
        double levelTol = 5 * _Point;
        bool isHhSuperseded = IsLevelSuperseded(breakUpM15, breakUpCntM15, lastAcceptedHH_M15, levelTol);
        if (!isHhSuperseded)
        {
            datetime foundTime = FindFormationTime(hhFormPriceM15, hhFormTimeM15, hhFormCntM15, lastAcceptedHH_M15, levelTol, noTimeLimit);
            if (foundTime == 0) foundTime = lastTimeHH_M15; // fallback ke state file
            if (foundTime == 0) foundTime = TimeCurrent(); // fallback terakhir

            string name = "redraw_lastHH_M15";
            ObjectDelete(0, name);
            ObjectCreate(0, name, OBJ_TREND, 0, foundTime, lastAcceptedHH_M15, foundTime + PeriodSeconds(PERIOD_M15), lastAcceptedHH_M15);
            ObjectSetInteger(0, name, OBJPROP_COLOR, clrBlue);
            ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
            ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASHDOT);
            ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, true);
            ObjectSetInteger(0, name, OBJPROP_RAY_LEFT, false);
            ObjectSetInteger(0, name, OBJPROP_BACK, true);
            
            string lblName = "redraw_lastHH_M15_label";
            ObjectDelete(0, lblName);
            ObjectCreate(0, lblName, OBJ_TEXT, 0, foundTime, lastAcceptedHH_M15 + 10 * _Point);
            ObjectSetInteger(0, lblName, OBJPROP_COLOR, clrBlue);
            ObjectSetInteger(0, lblName, OBJPROP_FONTSIZE, 9);
            ObjectSetString(0, lblName, OBJPROP_TEXT, "lastAcceptedHH_M15: " + DoubleToString(lastAcceptedHH_M15, _Digits));
        }
        else
        {
            ObjectDelete(0, "redraw_lastHH_M15");
            ObjectDelete(0, "redraw_lastHH_M15_label");
        }
    }
    
    // M15 - lastAcceptedLL
    if (lastAcceptedLL_M15 > 0)
    {
        double levelTol = 5 * _Point;
        bool isLlSuperseded = IsLevelSuperseded(breakDownM15, breakDownCntM15, lastAcceptedLL_M15, levelTol);
        if (!isLlSuperseded)
        {
            datetime foundTime = FindFormationTime(llFormPriceM15, llFormTimeM15, llFormCntM15, lastAcceptedLL_M15, levelTol, noTimeLimit);
            if (foundTime == 0) foundTime = lastTimeLL_M15; // fallback ke state file
            if (foundTime == 0) foundTime = TimeCurrent(); // fallback terakhir

            string name = "redraw_lastLL_M15";
            ObjectDelete(0, name);
            ObjectCreate(0, name, OBJ_TREND, 0, foundTime, lastAcceptedLL_M15, foundTime + PeriodSeconds(PERIOD_M15), lastAcceptedLL_M15);
            ObjectSetInteger(0, name, OBJPROP_COLOR, clrMagenta);
            ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
            ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASHDOT);
            ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, true);
            ObjectSetInteger(0, name, OBJPROP_RAY_LEFT, false);
            ObjectSetInteger(0, name, OBJPROP_BACK, true);
            
            string lblName = "redraw_lastLL_M15_label";
            ObjectDelete(0, lblName);
            ObjectCreate(0, lblName, OBJ_TEXT, 0, foundTime, lastAcceptedLL_M15 - 10 * _Point);
            ObjectSetInteger(0, lblName, OBJPROP_COLOR, clrMagenta);
            ObjectSetInteger(0, lblName, OBJPROP_FONTSIZE, 9);
            ObjectSetString(0, lblName, OBJPROP_TEXT, "lastAcceptedLL_M15: " + DoubleToString(lastAcceptedLL_M15, _Digits));
        }
        else
        {
            ObjectDelete(0, "redraw_lastLL_M15");
            ObjectDelete(0, "redraw_lastLL_M15_label");
        }
    }
    
    // H1 - lastAcceptedHH
    if (EnableDrawLines_H1 && lastAcceptedHH_H1 > 0)
    {
        double levelTol = 5 * _Point;
        bool isHhSuperseded = IsLevelSuperseded(breakUpH1, breakUpCntH1, lastAcceptedHH_H1, levelTol);
        if (!isHhSuperseded)
        {
            datetime foundTime = FindFormationTime(hhFormPriceH1, hhFormTimeH1, hhFormCntH1, lastAcceptedHH_H1, levelTol, noTimeLimit);
            if (foundTime == 0) foundTime = lastTimeHH_H1;
            if (foundTime == 0) foundTime = TimeCurrent();

            string name = "redraw_lastHH_H1";
            ObjectDelete(0, name);
            ObjectCreate(0, name, OBJ_TREND, 0, foundTime, lastAcceptedHH_H1, foundTime + PeriodSeconds(PERIOD_H1), lastAcceptedHH_H1);
            ObjectSetInteger(0, name, OBJPROP_COLOR, clrOrange);
            ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
            ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASHDOT);
            ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, true);
            ObjectSetInteger(0, name, OBJPROP_RAY_LEFT, false);
            ObjectSetInteger(0, name, OBJPROP_BACK, true);

            string lblName = "redraw_lastHH_H1_label";
            ObjectDelete(0, lblName);
            ObjectCreate(0, lblName, OBJ_TEXT, 0, foundTime, lastAcceptedHH_H1 + 20 * _Point);
            ObjectSetInteger(0, lblName, OBJPROP_COLOR, clrOrange);
            ObjectSetInteger(0, lblName, OBJPROP_FONTSIZE, 9);
            ObjectSetString(0, lblName, OBJPROP_TEXT, "lastAcceptedHH_H1: " + DoubleToString(lastAcceptedHH_H1, _Digits));
        }
        else
        {
            ObjectDelete(0, "redraw_lastHH_H1");
            ObjectDelete(0, "redraw_lastHH_H1_label");
        }
    }

    // H1 - lastAcceptedLL
    if (EnableDrawLines_H1 && lastAcceptedLL_H1 > 0)
    {
        double levelTol = 5 * _Point;
        bool isLlSuperseded = IsLevelSuperseded(breakDownH1, breakDownCntH1, lastAcceptedLL_H1, levelTol);
        if (!isLlSuperseded)
        {
            datetime foundTime = FindFormationTime(llFormPriceH1, llFormTimeH1, llFormCntH1, lastAcceptedLL_H1, levelTol, noTimeLimit);
            if (foundTime == 0) foundTime = lastTimeLL_H1;
            if (foundTime == 0) foundTime = TimeCurrent();

            string name = "redraw_lastLL_H1";
            ObjectDelete(0, name);
            ObjectCreate(0, name, OBJ_TREND, 0, foundTime, lastAcceptedLL_H1, foundTime + PeriodSeconds(PERIOD_H1), lastAcceptedLL_H1);
            ObjectSetInteger(0, name, OBJPROP_COLOR, clrAqua);
            ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
            ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASHDOT);
            ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, true);
            ObjectSetInteger(0, name, OBJPROP_RAY_LEFT, false);
            ObjectSetInteger(0, name, OBJPROP_BACK, true);

            string lblName = "redraw_lastLL_H1_label";
            ObjectDelete(0, lblName);
            ObjectCreate(0, lblName, OBJ_TEXT, 0, foundTime, lastAcceptedLL_H1 - 20 * _Point);
            ObjectSetInteger(0, lblName, OBJPROP_COLOR, clrAqua);
            ObjectSetInteger(0, lblName, OBJPROP_FONTSIZE, 9);
            ObjectSetString(0, lblName, OBJPROP_TEXT, "lastAcceptedLL_H1: " + DoubleToString(lastAcceptedLL_H1, _Digits));
        }
        else
        {
            ObjectDelete(0, "redraw_lastLL_H1");
            ObjectDelete(0, "redraw_lastLL_H1_label");
        }
    }
    
    ChartRedraw();
    
    PrintFormat("✅ [REDRAW] Visual redraw complete from CSV:");
    PrintFormat("   📊 HH lines:  %d (superseded: %d)", hhCount, hhSuperseded);
    PrintFormat("   📊 LL lines:  %d (superseded: %d)", llCount, llSuperseded);
    PrintFormat("   📊 CHoCH lines: %d", chochCount);
    PrintFormat("   📊 BoS lines: %d", bosCount);
    PrintFormat("   📊 lastAcceptedHH/LL: 4 (from state file)");
    PrintFormat("   📊 Total: %d visual objects", hhCount + llCount + chochCount + bosCount + 4);
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

    // Tambahkan ini untuk EMA H4
    handleEMA_H4 = iMA(_Symbol, PERIOD_H4, EMA_H4_Period, 0, MODE_EMA, PRICE_CLOSE);
    if (handleEMA_H4 == INVALID_HANDLE)
    {
        Print("❌ Gagal membuat handle EMA H4");
        return INIT_FAILED;
    }

    ChartIndicatorAdd(0, 0, handleEMA_M15);
    ChartIndicatorAdd(0, 0, handleEMA_H1);
    ChartIndicatorAdd(0, 0, handleEMA_H4);

    trade.SetExpertMagicNumber(MagicNumber_M15);
    Print("✅ EMA200 handle berhasil dibuat untuk M15 & H1");

    // ✅ SYNC BACKTEST CSV: Copy backtest history ke MQL5 sandbox SEBELUM load
    if (!MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_OPTIMIZATION))
    {
        // SyncLastSessionCSV();
        // SyncBacktestCSV();
    }
    
    // ✅ SET EXPORT DATE AWAL: Tentukan g_ExportDateStr & rename file lama (jika ada)
    // WAJIB dipanggil SEBELUM LoadLLHHBOSDataToArrays() agar g_ExportDateStr sudah diset
    // sehingga Load membaca file dengan nama tanggal yang benar (hari ini).
    if (!MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_OPTIMIZATION))
    {
        SetExportDate();
    }

    // ✅ RESUME STATE: Load market structure state dari file (LIVE TRADING ONLY)
    // WAJIB dipanggil SETELAH SyncLastSessionCSV/SyncBacktestCSV/SetExportDate
    // agar state file hasil sync dari BacktestResultPath sudah tersedia di sandbox.
    // Sebelumnya dipanggil terlalu awal (sebelum sync) → state tidak ketemu → fresh session.
    if (!MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_OPTIMIZATION))
    {
        if (LoadMarketStructureState())
        {
            Print("✅ [INIT] Market structure state successfully restored!");
        }
        else
        {
            Print("ℹ️ [INIT] Starting fresh session (no previous state)");
        }
    }
    
    // ✅ LOAD LLHHBOS DATA TO ARRAYS: Load existing CSV ke memory SEBELUM WarmUp
    // Mencegah ExportLLHHBOSToCSV overwrite file dengan data kosong
    // Dipanggil HANYA saat live trading (bukan backtest)
    if (!MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_OPTIMIZATION))
    {
        LoadLLHHBOSDataToArrays();
    }

    // ====== NEW: langsung backfill (dengan skip logic jika state resumed) ======
    if (BackfillOnLoad_M15)
        WarmUp_M15(WarmupBars_M15);

    // ⚠️ H1 LOGIC DISABLED: Only EMA 200 H1 remains active for filtering
    // if (BackfillOnLoad_H1)
    //     WarmUp_H1(WarmupBars_H1);

    // ✅ BUG #3 FIX: Flush memory array (termasuk BoS continuation backfill dari WarmUp) ke CSV
    // WAJIB sebelum RedrawVisualsFromCSV() karena Redraw membaca dari CSV di disk, bukan memory.
    // Tanpa ini, BoS yang terdeteksi di backfill gap (mis. 4121.68) tidak akan tergambar.
    // Dipanggil HANYA saat live trading (bukan backtest). Dedup internal mencegah duplikasi.
    if (!MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_OPTIMIZATION))
    {
        ExportLLHHBOSToCSV();
    }

    // ✅ REDRAW VISUALS FROM CSV: Gambar ulang semua history HH/LL/CHoCH/BoS dari CSV
    // Dipanggil HANYA saat live trading (bukan backtest)
    if (!MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_OPTIMIZATION))
    {
        // 🔧 CLEANUP: Hapus objek live-draw yang dibuat selama WarmUp SEBELUM Redraw.
        // RedrawVisualsFromCSV() akan membuat versi otoritatifnya dari CSV+state.
        // Tanpa cleanup ini, garis live & redraw overlap di level yang sama (terlihat double).
        // 1) Hapus lastAccepted lines (dibuat oleh UpdateAcceptedLevelVisuals_M15/H1 saat WarmUp)
        ObjectDelete(0, "line_lastAcceptedHH_M15"); ObjectDelete(0, "label_lastAcceptedHH_M15");
        ObjectDelete(0, "line_lastAcceptedLL_M15"); ObjectDelete(0, "label_lastAcceptedLL_M15");
        // ⚠️ H1 LOGIC DISABLED: H1 object cleanup commented out
        // ObjectDelete(0, "line_lastAcceptedHH_H1");  ObjectDelete(0, "label_lastAcceptedHH_H1");
        // ObjectDelete(0, "line_lastAcceptedLL_H1");  ObjectDelete(0, "label_lastAcceptedLL_H1");
        // 2) Hapus BoS backfill lines (dibuat oleh BUG #3 BF block saat WarmUp)
        //    Nama: BoS_Bear_M15_BF_*, BoS_Bull_M15_BF_*, H1_BoS_Bear_BF_*, H1_BoS_Bull_BF_*
        //    Redraw akan membuat versi redraw_BoS_* dari CSV yang sama.
        int totalObj = ObjectsTotal(0, 0, OBJ_TREND);
        for (int c = totalObj - 1; c >= 0; c--)
        {
            string objName = ObjectName(0, c, 0, OBJ_TREND);
            if (StringFind(objName, "_BF_") >= 0)
                ObjectDelete(0, objName);
        }

        RedrawVisualsFromCSV();
    }

    // ponytail: timer 60 menit dihapus — export sekarang per M15 candle close di OnTick.
    // Input vars (EnableAutoExportRealtime, dll) tetap ada supaya template/preset EA tidak rusak.
    if (!MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_OPTIMIZATION))
    {
        Print("");
        Print("╔════════════════════════════════════════════════════════════════╗");
        Print("║   EXPORT PER M15 CANDLE CLOSE - ACTIVE (OnTimer dihapus)       ║");
        Print("╚════════════════════════════════════════════════════════════════╝");
        Print("   📂 Export semua file setiap M15 candle close (OnTick)");
        Print("   💾 + final export saat EA dihentikan (OnDeinit)");
        PrintFormat("   ⚠️ Attach WAJIB di chart M15 — TF lain hanya export saat OnDeinit");
        Print("════════════════════════════════════════════════════════════════");
        Print("");
    }

    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnTimer: Export berkala saat live trading (opsional)              |
//+------------------------------------------------------------------+
void OnTimer()
{
    // ponytail: Timer dihapus — export sekarang per M15 candle close di OnTick.
    // Body dikosongkan. EventSetTimer tidak pernah dipanggil → OnTimer tidak fires.
    // Fungsi tetap ada supaya tidak ada compile error (signature OnTimer diharapkan MQL5).
}

//+------------------------------------------------------------------+
//| Set export date di akhir backtest (pakai TimeCurrent di OnTester/OnDeinit) |
//| LIVE TRADING: Rolling file - rename file setiap midnight           |
//+------------------------------------------------------------------+
void SetExportDate()
{
    datetime currentTime = TimeCurrent();
    MqlDateTime dt;
    TimeToStruct(currentTime, dt);
    
    // Reset waktu ke midnight untuk perbandingan tanggal
    dt.hour = 0;
    dt.min = 0;
    dt.sec = 0;
    datetime currentDateOnly = StructToTime(dt);
    
    // ✅ BACKTEST MODE: Selalu update ke bar terakhir (bukan lock di first call)
    if (MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
    {
        // Saat backtest: selalu pakai waktu bar terakhir yang tersedia
        MqlRates rates[];
        ArraySetAsSeries(rates, true);
        datetime lastBarTime;
        
        if (CopyRates(_Symbol, PERIOD_M15, 0, 1, rates) > 0)
            lastBarTime = rates[0].time;
        else
            lastBarTime = currentTime;  // Fallback jika gagal copy rates
        
        g_ExportDateStr = TimeToString(lastBarTime, TIME_DATE);
        StringReplace(g_ExportDateStr, ".", "-");
        g_LastExportDate = currentDateOnly;
        return;
    }
    
    // ✅ LIVE TRADING MODE: Rolling file dengan rename setiap midnight
    
    // ✅ FIRST TIME INITIALIZATION — Extended Same-Month Resume Logic
    // Cari file lama dari bulan yang sama (berapapun selisih harinya) untuk di-resume.
    // Ini menangani kasus EA off beberapa hari (mis. Sabtu→Senin, atau off 3+ hari).
    if (g_ExportDateStr == "")
    {
        string todayDateStr = TimeToString(currentTime, TIME_DATE);
        StringReplace(todayDateStr, ".", "-");
        
        // Ambil prefix "YYYY-MM" dari tanggal hari ini (misal "2026-06")
        string yearMonth = StringSubstr(todayDateStr, 0, 7);
        
        string prevDateStr = "";  // Tanggal file lama yang ditemukan di bulan yang sama
        
        // ✅ STEP 1: Scan file lama di bulan yang sama (prioritas: Backtest_Results > LLHHBOSData > MarketStructure_State)
        // ponytail: was Backtest_Results only — jika tidak ada file itu, rename tidak pernah jalan.
        string searchPatterns[];
        ArrayResize(searchPatterns, 3);
        searchPatterns[0] = "Backtest_Results_" + _Symbol + "_" + yearMonth + "-*.csv";
        searchPatterns[1] = "LLHHBOSData_" + _Symbol + "_" + yearMonth + "-*.csv";
        searchPatterns[2] = "MarketStructure_State_" + _Symbol + "_" + yearMonth + "-*.txt";

        for (int p = 0; p < 3 && prevDateStr == ""; p++)
        {
            string foundFilename  = "";
            long   searchHandle   = FileFindFirst(searchPatterns[p], foundFilename);

            if (searchHandle != INVALID_HANDLE)
            {
                do
                {
                    int prefixLen = StringLen("LLHHBOSData_" + _Symbol + "_");
                    if (p == 0) prefixLen = StringLen("Backtest_Results_" + _Symbol + "_");
                    else if (p == 2) prefixLen = StringLen("MarketStructure_State_" + _Symbol + "_");

                    string datePart  = StringSubstr(foundFilename, prefixLen, 10);

                    if (StringSubstr(datePart, 0, 7) == yearMonth && datePart != todayDateStr)
                    {
                        prevDateStr = datePart;
                        PrintFormat("🔍 [RESUME] File lama ditemukan: %s (tanggal %s → akan di-rename ke %s)",
                                    foundFilename, prevDateStr, todayDateStr);
                        break;
                    }
                } while (FileFindNext(searchHandle, foundFilename));

                FileFindClose(searchHandle);
            }
        }
        
        // [FIX] Fallback ke bulan sebelumnya jika tidak ada file lama di bulan berjalan.
        // Kasus: Ganti bulan dari Juni ke Juli.
        if (prevDateStr == "")
        {
            int prevMonth = dt.mon - 1;
            int prevYear  = dt.year;
            if (prevMonth < 1) { prevMonth = 12; prevYear--; }
            string prevYearMonth = StringFormat("%d-%02d", prevYear, prevMonth);
            
            searchPatterns[0] = "Backtest_Results_" + _Symbol + "_" + prevYearMonth + "-*.csv";
            searchPatterns[1] = "LLHHBOSData_" + _Symbol + "_" + prevYearMonth + "-*.csv";
            searchPatterns[2] = "MarketStructure_State_" + _Symbol + "_" + prevYearMonth + "-*.txt";
            
            for (int p = 0; p < 3 && prevDateStr == ""; p++)
            {
                string foundFilename  = "";
                long   searchHandle   = FileFindFirst(searchPatterns[p], foundFilename);

                if (searchHandle != INVALID_HANDLE)
                {
                    do
                    {
                        int prefixLen = StringLen("LLHHBOSData_" + _Symbol + "_");
                        if (p == 0) prefixLen = StringLen("Backtest_Results_" + _Symbol + "_");
                        else if (p == 2) prefixLen = StringLen("MarketStructure_State_" + _Symbol + "_");

                        string datePart  = StringSubstr(foundFilename, prefixLen, 10);
                        
                        // Validasi: Berada di bulan sebelumnya
                        if (StringSubstr(datePart, 0, 7) == prevYearMonth)
                        {
                            prevDateStr = datePart;
                            PrintFormat("🔍 [RESUME] File lama bulan lalu ditemukan: %s (tanggal %s → akan di-rename ke %s)",
                                        foundFilename, prevDateStr, todayDateStr);
                            break;
                        }
                    } while (FileFindNext(searchHandle, foundFilename));

                    FileFindClose(searchHandle);
                }
            }
        }
        
        // ✅ STEP 2: Rename semua file terkait dari prevDate → todayDate
        // Isi file TIDAK berubah — append + deduplication tetap berjalan seperti biasa.
        if (prevDateStr != "")
        {
            PrintFormat("📅 [RESUME] Rolling files: %s → %s (same-month resume)", prevDateStr, todayDateStr);
            
            // Backtest_Results
            string oldResults = "Backtest_Results_" + _Symbol + "_" + prevDateStr + ".csv";
            string newResults = "Backtest_Results_" + _Symbol + "_" + todayDateStr + ".csv";
            if (FileIsExist(oldResults))
            {
                if (RenameFileViaCopy(oldResults, newResults))
                {
                    PrintFormat("   ✅ Renamed: %s → %s", oldResults, newResults);
                    DeleteFileW(BacktestResultPath + "\\" + oldResults);
                }
                else
                    PrintFormat("   ❌ Gagal rename: %s", oldResults);
            }
            
            // LLHHBOSData
            string oldLLHH = "LLHHBOSData_" + _Symbol + "_" + prevDateStr + ".csv";
            string newLLHH = "LLHHBOSData_" + _Symbol + "_" + todayDateStr + ".csv";
            if (FileIsExist(oldLLHH))
            {
                if (RenameFileViaCopy(oldLLHH, newLLHH))
                {
                    PrintFormat("   ✅ Renamed: %s → %s", oldLLHH, newLLHH);
                    DeleteFileW(BacktestResultPath + "\\" + oldLLHH);
                }
                else
                    PrintFormat("   ❌ Gagal rename: %s", oldLLHH);
            }
            
            // Backtest_Summary
            string oldSummary = "Backtest_Summary_" + _Symbol + "_" + prevDateStr + ".csv";
            string newSummary = "Backtest_Summary_" + _Symbol + "_" + todayDateStr + ".csv";
            if (FileIsExist(oldSummary))
            {
                if (RenameFileViaCopy(oldSummary, newSummary))
                {
                    PrintFormat("   ✅ Renamed: %s → %s", oldSummary, newSummary);
                    DeleteFileW(BacktestResultPath + "\\" + oldSummary);
                }
                else
                    PrintFormat("   ❌ Gagal rename: %s", oldSummary);
            }
            
            // MarketStructure_State
            string oldState = "MarketStructure_State_" + _Symbol + "_" + prevDateStr + ".txt";
            string newState = "MarketStructure_State_" + _Symbol + "_" + todayDateStr + ".txt";
            if (FileIsExist(oldState))
            {
                if (RenameFileViaCopy(oldState, newState))
                {
                    PrintFormat("   ✅ Renamed: %s → %s", oldState, newState);
                    DeleteFileW(BacktestResultPath + "\\" + oldState);
                }
                else
                    PrintFormat("   ❌ Gagal rename: %s", oldState);
            }

            // ponytail: rename MarketData files (M15, H1, H4)
            string tfs[] = {"M15", "H1", "H4"};
            for (int t = 0; t < 3; t++)
            {
                string oldMD = "MarketData_" + _Symbol + "_" + tfs[t] + "_" + prevDateStr + ".csv";
                string newMD = "MarketData_" + _Symbol + "_" + tfs[t] + "_" + todayDateStr + ".csv";
                if (FileIsExist(oldMD))
                {
                    if (RenameFileViaCopy(oldMD, newMD))
                        PrintFormat("   ✅ Renamed: %s → %s", oldMD, newMD);
                    else
                        PrintFormat("   ❌ Gagal rename: %s", oldMD);
                }
            }

            // ponytail: rename SessionZone (prefix "SessionZone_" — match ExportSessionZoneToCSV)
            string oldSZ = "SessionZone_" + _Symbol + "_" + prevDateStr + ".csv";
            string newSZ = "SessionZone_" + _Symbol + "_" + todayDateStr + ".csv";
            if (FileIsExist(oldSZ))
            {
                if (RenameFileViaCopy(oldSZ, newSZ))
                    PrintFormat("   ✅ Renamed: %s → %s", oldSZ, newSZ);
                else
                    PrintFormat("   ❌ Gagal rename: %s", oldSZ);
            }
            
            PrintFormat("✅ [RESUME] Same-month rolling selesai: %s → %s", prevDateStr, todayDateStr);
        }
        else
        {
            Print("ℹ️ [RESUME] Tidak ada file lama di bulan yang sama. Mulai sesi baru.");
        }
        
        g_ExportDateStr = todayDateStr;
        g_LastExportDate = currentDateOnly;
        return;
    }
    
    // Detect midnight (ganti hari)
    if (currentDateOnly > g_LastExportDate)
    {
        // 🔄 ROLLING FILE: Rename file lama ke tanggal baru
        string oldFilename = "Backtest_Results_" + _Symbol + "_" + g_ExportDateStr + ".csv";
        string newDateStr = TimeToString(currentTime, TIME_DATE);
        StringReplace(newDateStr, ".", "-");
        string newFilename = "Backtest_Results_" + _Symbol + "_" + newDateStr + ".csv";
        
        // MQL5 tidak support rename, jadi kita pakai copy + delete
        if (FileIsExist(oldFilename))
        {
            if (RenameFileViaCopy(oldFilename, newFilename))
            {
                Print("📅 ROLLING FILE: File renamed from ", oldFilename, " to ", newFilename);
                DeleteFileW(BacktestResultPath + "\\" + oldFilename);
                
                // Rename file lainnya juga
                string oldLLHHFile = "LLHHBOSData_" + _Symbol + "_" + g_ExportDateStr + ".csv";
                string newLLHHFile = "LLHHBOSData_" + _Symbol + "_" + newDateStr + ".csv";
                if (FileIsExist(oldLLHHFile))
                {
                    if (RenameFileViaCopy(oldLLHHFile, newLLHHFile))
                    {
                        DeleteFileW(BacktestResultPath + "\\" + oldLLHHFile);
                    }
                }
                
                string oldSummaryFile = "Backtest_Summary_" + _Symbol + "_" + g_ExportDateStr + ".csv";
                string newSummaryFile = "Backtest_Summary_" + _Symbol + "_" + newDateStr + ".csv";
                if (FileIsExist(oldSummaryFile))
                {
                    if (RenameFileViaCopy(oldSummaryFile, newSummaryFile))
                    {
                        DeleteFileW(BacktestResultPath + "\\" + oldSummaryFile);
                    }
                }
                
                string oldStateFile = "MarketStructure_State_" + _Symbol + "_" + g_ExportDateStr + ".txt";
                string newStateFile = "MarketStructure_State_" + _Symbol + "_" + newDateStr + ".txt";
                if (FileIsExist(oldStateFile))
                {
                    if (RenameFileViaCopy(oldStateFile, newStateFile))
                    {
                        DeleteFileW(BacktestResultPath + "\\" + oldStateFile);
                    }
                }

                // ponytail: was missing — MarketData & SessionZone not rolled at midnight,
                // causing stale-date files (e.g. 06-19) to persist while sibling files advanced.
                string tfs[] = {"M15", "H1", "H4"};
                for (int t = 0; t < 3; t++)
                {
                    string oldMD = "MarketData_" + _Symbol + "_" + tfs[t] + "_" + g_ExportDateStr + ".csv";
                    string newMD = "MarketData_" + _Symbol + "_" + tfs[t] + "_" + newDateStr + ".csv";
                    if (FileIsExist(oldMD))
                    {
                        if (RenameFileViaCopy(oldMD, newMD))
                            DeleteFileW(BacktestResultPath + "\\" + oldMD);
                    }
                }

                string oldSZFile = "SessionZone_" + _Symbol + "_" + g_ExportDateStr + ".csv";
                string newSZFile = "SessionZone_" + _Symbol + "_" + newDateStr + ".csv";
                if (FileIsExist(oldSZFile))
                {
                    if (RenameFileViaCopy(oldSZFile, newSZFile))
                        DeleteFileW(BacktestResultPath + "\\" + oldSZFile);
                }
            }
        }
        
        // Update tracking variables
        g_ExportDateStr = newDateStr;
        g_LastExportDate = currentDateOnly;
    }
}

//+------------------------------------------------------------------+
//| Helper: Rename file via copy + delete (MQL5 workaround)         |
//+------------------------------------------------------------------+
bool RenameFileViaCopy(string oldFile, string newFile)
{
    // ponytail: was MQL5 byte-loop 1KB chunk — gagal untuk file besar (6.5MB MarketData).
    // WinAPI CopyFileW handle file besar native + jauh lebih cepat. Sama persis pola
    // yang sudah dipakai SyncLastSessionCSV/SyncBacktestCSV/ReverseSyncCSV.
    string sandboxPath = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\";
    string srcPath = sandboxPath + oldFile;
    string dstPath = sandboxPath + newFile;

    if (!CopyFileW(srcPath, dstPath, false))
    {
        PrintFormat("❌ RenameFileViaCopy: CopyFileW gagal. old=%s err=%d", oldFile, GetLastError());
        return false;
    }

    if (!DeleteFileW(srcPath))
    {
        PrintFormat("⚠️ RenameFileViaCopy: Copy OK tapi DeleteFileW gagal. old=%s err=%d", oldFile, GetLastError());
        // Copy sudah berhasil — bukan fatal. Lanjut.
    }

    return true;
}

//+------------------------------------------------------------------+
//| RESUME STATE: Load Market Structure State dari file              |
//+------------------------------------------------------------------+
bool LoadMarketStructureState()
{
    Print("🔍 [RESUME] Checking for previous session state...");
    
    // Check apakah mode backtest (skip resume di backtest)
    if (MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
    {
        Print("ℹ️ [RESUME] Backtest mode - skip resume");
        return false;
    }
    
    // Cari state file terakhir — scan mundur dari hari ini ke tanggal 1 bulan ini
    datetime currentTime = TimeCurrent();
    MqlDateTime dt;
    TimeToStruct(currentTime, dt);
    
    string todayDateStr = TimeToString(currentTime, TIME_DATE);
    StringReplace(todayDateStr, ".", "-");
    string yearMonth = StringSubstr(todayDateStr, 0, 7); // "YYYY-MM"
    int todayDay = dt.day;
    
    string stateFile = "";
    for (int d = todayDay; d >= 1; d--)
    {
        string checkDateStr = StringFormat("%s-%02d", yearMonth, d);
        string candidate = "MarketStructure_State_" + _Symbol + "_" + checkDateStr + ".txt";
        if (FileIsExist(candidate))
        {
            stateFile = candidate;
            break;
        }
    }
    
    // [FIX] Fallback ke bulan sebelumnya jika bulan ini tidak ada state file.
    // Kasus: EA mati di akhir bulan, restart di awal bulan baru.
    // Day 31→1 aman: FileIsExist() return false untuk tanggal tidak valid (mis. 31 Feb).
    if (stateFile == "")
    {
        int prevMonth = dt.mon - 1;
        int prevYear  = dt.year;
        if (prevMonth < 1) { prevMonth = 12; prevYear--; } // Januari → Desember tahun lalu
        string prevYearMonth = StringFormat("%d-%02d", prevYear, prevMonth);
        
        for (int d = 31; d >= 1; d--)
        {
            string checkDateStr = StringFormat("%s-%02d", prevYearMonth, d);
            string candidate = "MarketStructure_State_" + _Symbol + "_" + checkDateStr + ".txt";
            if (FileIsExist(candidate))
            {
                stateFile = candidate;
                PrintFormat("📂 [RESUME] Bulan ini kosong → pakai state bulan lalu: %s", stateFile);
                break;
            }
        }
    }
    
    if (stateFile == "")
    {
        Print("ℹ️ [RESUME] No previous state file found");
        return false;
    }
    
    Print("📂 [RESUME] Found state file: ", stateFile);
    
    // Load state file
    int handle = FileOpen(stateFile, FILE_READ|FILE_TXT|FILE_ANSI);
    if (handle == INVALID_HANDLE)
    {
        Print("❌ [RESUME] Failed to open state file");
        return false;
    }
    
    // Parse state file (format: KEY=VALUE)
    while (!FileIsEnding(handle))
    {
        string line = FileReadString(handle);
        if (line == "" || StringFind(line, "=") < 0)
            continue;
        
        string parts[];
        int split = StringSplit(line, '=', parts);
        if (split != 2)
            continue;
        
        string key = parts[0];
        string value = parts[1];
        
        // Parse M15 state
        if (key == "M15_lastAcceptedHH") lastAcceptedHH_M15 = StringToDouble(value);
        else if (key == "M15_lastTimeHH") lastTimeHH_M15 = StringToTime(value);
        else if (key == "M15_lastAcceptedLL") lastAcceptedLL_M15 = StringToDouble(value);
        else if (key == "M15_lastTimeLL") lastTimeLL_M15 = StringToTime(value);
        else if (key == "M15_chochBullishConfirmed") chochBullishConfirmedFlag_M15 = (value == "true");
        else if (key == "M15_time_choch_bullish") time_choch_bullish_M15 = StringToTime(value);
        else if (key == "M15_chochBearishConfirmed") chochBearishConfirmedFlag_M15 = (value == "true");
        else if (key == "M15_time_choch_bearish") time_choch_bearish_M15 = StringToTime(value);
        // [FIX] Restore flag aktif chochBullish/Bearish yang sebelumnya tidak tersimpan
        else if (key == "M15_chochBullish") chochBullish_M15 = (value == "true");
        else if (key == "M15_chochBearish") chochBearish_M15 = (value == "true");
        else if (key == "M15_bosBullishConfirmed") bosBullishConfirmedFlag_M15 = (value == "true");
        else if (key == "M15_timeBoSBullish") timeBoSBullish_M15 = StringToTime(value);
        else if (key == "M15_bosBearishConfirmed") bosBearishConfirmedFlag_M15 = (value == "true");
        else if (key == "M15_timeBoSBearish") timeBoSBearish_M15 = StringToTime(value);
        else if (key == "M15_isInTrendBullish") isInTrendBullish_M15 = (value == "true");
        else if (key == "M15_isInTrendBearish") isInTrendBearish_M15 = (value == "true");
        else if (key == "M15_hhAfterChoch") hhAfterChochConfirmedFlag_M15 = (value == "true");
        else if (key == "M15_llAfterChoch") llAfterChochConfirmedFlag_M15 = (value == "true");
        else if (key == "M15_hhAfterBos") hhAfterBosConfirmedFlag_M15 = (value == "true");
        else if (key == "M15_llAfterBos") llAfterBosConfirmedFlag_M15 = (value == "true");
        else if (key == "M15_postChoCH_HH") postChoCH_HH_M15 = StringToDouble(value);
        else if (key == "M15_time_postChoCH_HH") time_postChoCH_HH_M15 = StringToTime(value);
        else if (key == "M15_absoluteHighestHH") absoluteHighestHH_M15 = StringToDouble(value);
        else if (key == "M15_timeAbsoluteHighestHH") timeAbsoluteHighestHH_M15 = StringToTime(value);
        else if (key == "M15_postChoCH_LL") postChoCH_LL_M15 = StringToDouble(value);
        else if (key == "M15_time_postChoCH_LL") time_postChoCH_LL_M15 = StringToTime(value);
        else if (key == "M15_entryCountBuy") entryCountBuy_M15 = (int)StringToInteger(value);
        else if (key == "M15_entryCountSell") entryCountSell_M15 = (int)StringToInteger(value);
        else if (key == "M15_lastEntryTime") lastEntryTime_M15 = StringToTime(value);
        else if (key == "M15_lastBarTime") g_LastProcessedBarTime_M15 = StringToTime(value);
        
        // Parse H1 state
        else if (key == "H1_lastAcceptedHH") lastAcceptedHH_H1 = StringToDouble(value);
        else if (key == "H1_lastTimeHH") lastTimeHH_H1 = StringToTime(value);
        else if (key == "H1_lastAcceptedLL") lastAcceptedLL_H1 = StringToDouble(value);
        else if (key == "H1_lastTimeLL") lastTimeLL_H1 = StringToTime(value);
        else if (key == "H1_chochBullishConfirmed") chochBullishConfirmedFlag_H1 = (value == "true");
        else if (key == "H1_chochBearishConfirmed") chochBearishConfirmedFlag_H1 = (value == "true");
        // [FIX] Restore flag aktif chochBullish/Bearish H1 yang sebelumnya tidak tersimpan
        else if (key == "H1_chochBullish") chochBullish_H1 = (value == "true");
        else if (key == "H1_chochBearish") chochBearish_H1 = (value == "true");
        else if (key == "H1_bosBullishConfirmed") bosBullishConfirmedFlag_H1 = (value == "true");
        else if (key == "H1_bosBearishConfirmed") bosBearishConfirmedFlag_H1 = (value == "true");
        else if (key == "H1_isInTrendBullish") isInTrendBullish_H1 = (value == "true");
        else if (key == "H1_isInTrendBearish") isInTrendBearish_H1 = (value == "true");
        else if (key == "H1_hhAfterChoch") hhAfterChochConfirmedFlag_H1 = (value == "true");
        else if (key == "H1_llAfterChoch") llAfterChochConfirmedFlag_H1 = (value == "true");
        else if (key == "H1_hhAfterBos") hhAfterBosConfirmedFlag_H1 = (value == "true");
        else if (key == "H1_llAfterBos") llAfterBosConfirmedFlag_H1 = (value == "true");
        else if (key == "H1_postChoCH_HH") postChoCH_HH_H1 = StringToDouble(value);
        else if (key == "H1_time_postChoCH_HH") time_postChoCH_HH_H1 = StringToTime(value);
        else if (key == "H1_absoluteHighestHH") absoluteHighestHH_H1 = StringToDouble(value);
        else if (key == "H1_timeAbsoluteHighestHH") timeAbsoluteHighestHH_H1 = StringToTime(value);
        else if (key == "H1_postChoCH_LL") postChoCH_LL_H1 = StringToDouble(value);
        else if (key == "H1_time_postChoCH_LL") time_postChoCH_LL_H1 = StringToTime(value);
        else if (key == "H1_lastBarTime") g_LastProcessedBarTime_H1 = StringToTime(value);
    }
    
    FileClose(handle);
    
    // ponytail: fallback untuk state lama yang belum menyimpan waktu BoS
    if (bosBullishConfirmedFlag_M15 && timeBoSBullish_M15 <= 0 && lastTimeHH_M15 > 0)
    {
        timeBoSBullish_M15 = lastTimeHH_M15;
        PrintFormat("🔄 [RESUME FALLBACK M15] timeBoSBullish tidak tersimpan, di-set ke lastTimeHH: %s", TimeToString(timeBoSBullish_M15));
    }
    if (bosBearishConfirmedFlag_M15 && timeBoSBearish_M15 <= 0 && lastTimeLL_M15 > 0)
    {
        timeBoSBearish_M15 = lastTimeLL_M15;
        PrintFormat("🔄 [RESUME FALLBACK M15] timeBoSBearish tidak tersimpan, di-set ke lastTimeLL: %s", TimeToString(timeBoSBearish_M15));
    }
    
    // [FIX] Backward compat: state file lama tidak menyimpan M15_chochBullish / M15_chochBearish.
    // Reconstruct dari flags Confirmed + kondisi siklus yang masih aktif.
    // Kondisi chochBullish aktif = CHoCH Bullish sudah confirmed TAPI BoS belum (atau sudah BoS
    // tapi masih dalam tren bullish). Ini mencegah break HH yang seharusnya BoS → malah CHoCH baru.
    if (!chochBullish_M15 && chochBullishConfirmedFlag_M15 && !bosBullishConfirmedFlag_M15)
    {
        chochBullish_M15 = true;
        PrintFormat("🔄 [RESUME FALLBACK M15] chochBullish_M15 direkonstruksi: chochBullishConfirmed=true + belum BoS");
    }
    else if (!chochBullish_M15 && bosBullishConfirmedFlag_M15 && isInTrendBullish_M15)
    {
        // Dalam tren bullish aktif (BoS sudah confirmed, masih dalam tren)
        chochBullish_M15 = true;
        PrintFormat("🔄 [RESUME FALLBACK M15] chochBullish_M15 direkonstruksi: bosBullishConfirmed + isInTrendBullish");
    }
    if (!chochBearish_M15 && chochBearishConfirmedFlag_M15 && !bosBearishConfirmedFlag_M15)
    {
        chochBearish_M15 = true;
        PrintFormat("🔄 [RESUME FALLBACK M15] chochBearish_M15 direkonstruksi: chochBearishConfirmed=true + belum BoS");
    }
    else if (!chochBearish_M15 && bosBearishConfirmedFlag_M15 && isInTrendBearish_M15)
    {
        // Dalam tren bearish aktif (BoS sudah confirmed, masih dalam tren)
        chochBearish_M15 = true;
        PrintFormat("🔄 [RESUME FALLBACK M15] chochBearish_M15 direkonstruksi: bosBearishConfirmed + isInTrendBearish");
    }
    
    // Log diagnostik postChoCH_HH setelah restore (membantu debug state resume)
    if (postChoCH_HH_M15 > 0)
        PrintFormat("🔍 [RESUME DIAG M15] postChoCH_HH_M15=%.2f @ %s | chochBullish=%s | hhAfterChoch=%s",
                    postChoCH_HH_M15, TimeToString(time_postChoCH_HH_M15),
                    chochBullish_M15 ? "true" : "false",
                    hhAfterChochConfirmedFlag_M15 ? "true" : "false");
    
    Print("✅ [RESUME] Previous session state restored!");
    Print("");
    Print("📊 [RESUME] Restored Market Structure State (M15):");
    PrintFormat("   lastAcceptedHH_M15        = %.5f (Time: %s)", 
                lastAcceptedHH_M15, TimeToString(lastTimeHH_M15));
    PrintFormat("   lastAcceptedLL_M15        = %.5f (Time: %s)", 
                lastAcceptedLL_M15, TimeToString(lastTimeLL_M15));
    PrintFormat("   chochBullishConfirmed     = %s", chochBullishConfirmedFlag_M15 ? "true" : "false");
    PrintFormat("   chochBearishConfirmed     = %s", chochBearishConfirmedFlag_M15 ? "true" : "false");
    PrintFormat("   bosBullishConfirmed       = %s", bosBullishConfirmedFlag_M15 ? "true" : "false");
    PrintFormat("   bosBearishConfirmed       = %s", bosBearishConfirmedFlag_M15 ? "true" : "false");
    PrintFormat("   isInTrendBullish          = %s", isInTrendBullish_M15 ? "true" : "false");
    PrintFormat("   isInTrendBearish          = %s", isInTrendBearish_M15 ? "true" : "false");
    PrintFormat("   hhAfterChoch              = %s", hhAfterChochConfirmedFlag_M15 ? "true" : "false");
    PrintFormat("   llAfterChoch              = %s", llAfterChochConfirmedFlag_M15 ? "true" : "false");
    PrintFormat("   hhAfterBos                = %s", hhAfterBosConfirmedFlag_M15 ? "true" : "false");
    PrintFormat("   llAfterBos                = %s", llAfterBosConfirmedFlag_M15 ? "true" : "false");
    PrintFormat("   entryCountBuy_M15         = %d", entryCountBuy_M15);
    PrintFormat("   entryCountSell_M15        = %d", entryCountSell_M15);
    PrintFormat("   lastProcessedBarTime      = %s", TimeToString(g_LastProcessedBarTime_M15));
    Print("");
    
    // ✅ FIX: Reset absoluteHighestHH_M15 jika resume dalam MODE 3 BEARISH
    // MODE 3 BEARISH Part 2: BoS Bearish + LL After BoS sudah terkonfirmasi
    // Tujuan: Tracking HH tertinggi sejak LL terakhir untuk Lower High detection
    if (bosBearishConfirmedFlag_M15 && llAfterBosConfirmedFlag_M15)
    {
        absoluteHighestHH_M15 = -1;
        timeAbsoluteHighestHH_M15 = 0;
        PrintFormat("🔄 [RESUME MODE 3 BEARISH M15] Reset absoluteHighestHH_M15 untuk tracking HH sejak LL @ %s", 
                    TimeToString(lastTimeLL_M15));
    }
    
    // ✅ FIX: Reset absoluteLowestLL_M15 jika resume dalam MODE 3 BULLISH
    // MODE 3 BULLISH Part 2: BoS Bullish + HH After BoS sudah terkonfirmasi
    // Tujuan: Tracking LL terendah sejak HH terakhir untuk Higher Low detection
    if (bosBullishConfirmedFlag_M15 && hhAfterBosConfirmedFlag_M15)
    {
        absoluteLowestLL_M15 = -1;
        timeAbsoluteLowestLL_M15 = 0;
        PrintFormat("🔄 [RESUME MODE 3 BULLISH M15] Reset absoluteLowestLL_M15 untuk tracking LL sejak HH @ %s", 
                    TimeToString(lastTimeHH_M15));
    }
    
    // [FIX] Backward compat H1: reconstruct chochBullish_H1/chochBearish_H1 dari flags Confirmed
    if (!chochBullish_H1 && chochBullishConfirmedFlag_H1 && !bosBullishConfirmedFlag_H1)
    {
        chochBullish_H1 = true;
        PrintFormat("🔄 [RESUME FALLBACK H1] chochBullish_H1 direkonstruksi: chochBullishConfirmed=true + belum BoS");
    }
    else if (!chochBullish_H1 && bosBullishConfirmedFlag_H1 && isInTrendBullish_H1)
    {
        chochBullish_H1 = true;
        PrintFormat("🔄 [RESUME FALLBACK H1] chochBullish_H1 direkonstruksi: bosBullishConfirmed + isInTrendBullish");
    }
    if (!chochBearish_H1 && chochBearishConfirmedFlag_H1 && !bosBearishConfirmedFlag_H1)
    {
        chochBearish_H1 = true;
        PrintFormat("🔄 [RESUME FALLBACK H1] chochBearish_H1 direkonstruksi: chochBearishConfirmed=true + belum BoS");
    }
    else if (!chochBearish_H1 && bosBearishConfirmedFlag_H1 && isInTrendBearish_H1)
    {
        chochBearish_H1 = true;
        PrintFormat("🔄 [RESUME FALLBACK H1] chochBearish_H1 direkonstruksi: bosBearishConfirmed + isInTrendBearish");
    }
    
    g_StateResumed = true;
    g_StateFilePath = stateFile;
    
    return true;
}

//+------------------------------------------------------------------+
//| RESUME STATE: Save Market Structure State ke file                |
//+------------------------------------------------------------------+
void SaveMarketStructureState()
{
    // Skip di backtest mode
    if (MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
        return;
    
    string stateFile = "MarketStructure_State_" + _Symbol + "_" + g_ExportDateStr + ".txt";
    
    int handle = FileOpen(stateFile, FILE_WRITE|FILE_TXT|FILE_ANSI);
    if (handle == INVALID_HANDLE)
    {
        Print("❌ [STATE] Failed to save state file");
        return;
    }
    
    // Write M15 state
    FileWrite(handle, "M15_lastAcceptedHH=" + DoubleToString(lastAcceptedHH_M15, _Digits));
    FileWrite(handle, "M15_lastTimeHH=" + TimeToString(lastTimeHH_M15, TIME_DATE|TIME_SECONDS));
    FileWrite(handle, "M15_lastAcceptedLL=" + DoubleToString(lastAcceptedLL_M15, _Digits));
    FileWrite(handle, "M15_lastTimeLL=" + TimeToString(lastTimeLL_M15, TIME_DATE|TIME_SECONDS));
    FileWrite(handle, "M15_chochBullishConfirmed=" + (chochBullishConfirmedFlag_M15 ? "true" : "false"));
    FileWrite(handle, "M15_time_choch_bullish=" + TimeToString(time_choch_bullish_M15, TIME_DATE|TIME_SECONDS));
    FileWrite(handle, "M15_chochBearishConfirmed=" + (chochBearishConfirmedFlag_M15 ? "true" : "false"));
    FileWrite(handle, "M15_time_choch_bearish=" + TimeToString(time_choch_bearish_M15, TIME_DATE|TIME_SECONDS));
    // [FIX] Simpan flag aktif chochBullish/Bearish (bukan hanya Confirmed).
    // Tanpa ini, setelah restart EA selalu mulai false → break HH yang seharusnya
    // BoS terpicu sebagai CHoCH baru karena chochBullish_M15 tidak pernah direstorasi.
    FileWrite(handle, "M15_chochBullish=" + (chochBullish_M15 ? "true" : "false"));
    FileWrite(handle, "M15_chochBearish=" + (chochBearish_M15 ? "true" : "false"));
    FileWrite(handle, "M15_bosBullishConfirmed=" + (bosBullishConfirmedFlag_M15 ? "true" : "false"));
    FileWrite(handle, "M15_timeBoSBullish=" + TimeToString(timeBoSBullish_M15, TIME_DATE|TIME_SECONDS));
    FileWrite(handle, "M15_bosBearishConfirmed=" + (bosBearishConfirmedFlag_M15 ? "true" : "false"));
    FileWrite(handle, "M15_timeBoSBearish=" + TimeToString(timeBoSBearish_M15, TIME_DATE|TIME_SECONDS));
    FileWrite(handle, "M15_isInTrendBullish=" + (isInTrendBullish_M15 ? "true" : "false"));
    FileWrite(handle, "M15_isInTrendBearish=" + (isInTrendBearish_M15 ? "true" : "false"));
    FileWrite(handle, "M15_hhAfterChoch=" + (hhAfterChochConfirmedFlag_M15 ? "true" : "false"));
    FileWrite(handle, "M15_llAfterChoch=" + (llAfterChochConfirmedFlag_M15 ? "true" : "false"));
    FileWrite(handle, "M15_hhAfterBos=" + (hhAfterBosConfirmedFlag_M15 ? "true" : "false"));
    FileWrite(handle, "M15_llAfterBos=" + (llAfterBosConfirmedFlag_M15 ? "true" : "false"));
    FileWrite(handle, "M15_postChoCH_HH=" + DoubleToString(postChoCH_HH_M15, _Digits));
    FileWrite(handle, "M15_time_postChoCH_HH=" + TimeToString(time_postChoCH_HH_M15, TIME_DATE|TIME_SECONDS));
    FileWrite(handle, "M15_absoluteHighestHH=" + DoubleToString(absoluteHighestHH_M15, _Digits));
    FileWrite(handle, "M15_timeAbsoluteHighestHH=" + TimeToString(timeAbsoluteHighestHH_M15, TIME_DATE|TIME_SECONDS));
    FileWrite(handle, "M15_postChoCH_LL=" + DoubleToString(postChoCH_LL_M15, _Digits));
    FileWrite(handle, "M15_time_postChoCH_LL=" + TimeToString(time_postChoCH_LL_M15, TIME_DATE|TIME_SECONDS));
    FileWrite(handle, "M15_entryCountBuy=" + IntegerToString(entryCountBuy_M15));
    FileWrite(handle, "M15_entryCountSell=" + IntegerToString(entryCountSell_M15));
    FileWrite(handle, "M15_lastEntryTime=" + TimeToString(lastEntryTime_M15, TIME_DATE|TIME_SECONDS));
    FileWrite(handle, "M15_lastBarTime=" + TimeToString(lastBarTime_M15, TIME_DATE|TIME_SECONDS));
    
    // Write H1 state
    FileWrite(handle, "H1_lastAcceptedHH=" + DoubleToString(lastAcceptedHH_H1, _Digits));
    FileWrite(handle, "H1_lastTimeHH=" + TimeToString(lastTimeHH_H1, TIME_DATE|TIME_SECONDS));
    FileWrite(handle, "H1_lastAcceptedLL=" + DoubleToString(lastAcceptedLL_H1, _Digits));
    FileWrite(handle, "H1_lastTimeLL=" + TimeToString(lastTimeLL_H1, TIME_DATE|TIME_SECONDS));
    FileWrite(handle, "H1_chochBullishConfirmed=" + (chochBullishConfirmedFlag_H1 ? "true" : "false"));
    FileWrite(handle, "H1_chochBearishConfirmed=" + (chochBearishConfirmedFlag_H1 ? "true" : "false"));
    // [FIX] Simpan flag aktif chochBullish/Bearish H1 (analog M15)
    FileWrite(handle, "H1_chochBullish=" + (chochBullish_H1 ? "true" : "false"));
    FileWrite(handle, "H1_chochBearish=" + (chochBearish_H1 ? "true" : "false"));
    FileWrite(handle, "H1_bosBullishConfirmed=" + (bosBullishConfirmedFlag_H1 ? "true" : "false"));
    FileWrite(handle, "H1_bosBearishConfirmed=" + (bosBearishConfirmedFlag_H1 ? "true" : "false"));
    FileWrite(handle, "H1_isInTrendBullish=" + (isInTrendBullish_H1 ? "true" : "false"));
    FileWrite(handle, "H1_isInTrendBearish=" + (isInTrendBearish_H1 ? "true" : "false"));
    FileWrite(handle, "H1_hhAfterChoch=" + (hhAfterChochConfirmedFlag_H1 ? "true" : "false"));
    FileWrite(handle, "H1_llAfterChoch=" + (llAfterChochConfirmedFlag_H1 ? "true" : "false"));
    FileWrite(handle, "H1_hhAfterBos=" + (hhAfterBosConfirmedFlag_H1 ? "true" : "false"));
    FileWrite(handle, "H1_llAfterBos=" + (llAfterBosConfirmedFlag_H1 ? "true" : "false"));
    FileWrite(handle, "H1_postChoCH_HH=" + DoubleToString(postChoCH_HH_H1, _Digits));
    FileWrite(handle, "H1_time_postChoCH_HH=" + TimeToString(time_postChoCH_HH_H1, TIME_DATE|TIME_SECONDS));
    FileWrite(handle, "H1_absoluteHighestHH=" + DoubleToString(absoluteHighestHH_H1, _Digits));
    FileWrite(handle, "H1_timeAbsoluteHighestHH=" + TimeToString(timeAbsoluteHighestHH_H1, TIME_DATE|TIME_SECONDS));
    FileWrite(handle, "H1_postChoCH_LL=" + DoubleToString(postChoCH_LL_H1, _Digits));
    FileWrite(handle, "H1_time_postChoCH_LL=" + TimeToString(time_postChoCH_LL_H1, TIME_DATE|TIME_SECONDS));
    FileWrite(handle, "H1_lastBarTime=" + TimeToString(lastBarTime_H1, TIME_DATE|TIME_SECONDS));
    
    FileClose(handle);
}

//+------------------------------------------------------------------+
//| Fungsi OnDeinit: Dipanggil saat EA dihapus dari chart             |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("════════════════════════════════════════════════════════════════");
    PrintFormat("🔄 [DEINIT] EA dihentikan. Reason: %d", reason);
    
    // Decode reason
    string reasonText = "";
    switch(reason)
    {
        case REASON_PROGRAM:     reasonText = "EA dihentikan oleh user (manual remove)"; break;
        case REASON_REMOVE:      reasonText = "EA dihapus dari chart"; break;
        case REASON_RECOMPILE:   reasonText = "EA dikompilasi ulang"; break;
        case REASON_CHARTCHANGE: reasonText = "Perubahan symbol/timeframe chart"; break;
        case REASON_CHARTCLOSE:  reasonText = "Chart ditutup"; break;
        case REASON_PARAMETERS:  reasonText = "Input parameter diubah"; break;
        case REASON_ACCOUNT:     reasonText = "Akun berubah"; break;
        case REASON_TEMPLATE:    reasonText = "Template baru diterapkan"; break;
        case REASON_INITFAILED:  reasonText = "Inisialisasi gagal"; break;
        case REASON_CLOSE:       reasonText = "Terminal ditutup"; break;
        default:                 reasonText = "Alasan tidak diketahui"; break;
    }
    PrintFormat("   📝 Alasan: %s", reasonText);

    // ponytail: timer dihapus (export per M15 candle close di OnTick) — tidak ada timer untuk di-kill.

    // Tampilkan statistik sebelum export
    Print("   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    PrintFormat("   📊 STATISTIK SEBELUM EXPORT:");
    PrintFormat("      📝 Total trades recorded: %d", g_TradeCount);
    PrintFormat("      📈 Market structure events: %d", g_LLHHBOSCount);
    PrintFormat("      🕐 Session records: %d", g_SessionZoneRecordsCount);
    PrintFormat("      💼 Open positions saat ini: %d", PositionsTotal());
    
    // ✅ Capture open trades sebelum export
    Print("   🔍 Mencari open positions untuk di-capture...");
    int capturedTrades = PositionsTotal();
    if (capturedTrades > 0)
        PrintFormat("   💼 Menemukan %d open position(s), akan di-capture...", capturedTrades);
    
    // ✅ FIX: Export di semua mode (optimization, backtest, dan LIVE)
    Print("   🚀 Memulai final export...");
    datetime exportStartTime = GetTickCount();
    
    SetExportDate();
    ExportAllData();
    // ReverseSyncCSV();  // Final sync ke Backtest_result\ setelah export
    
    // ✅ AUTO-SAVE STATE sebelum exit (LIVE TRADING ONLY)
    if (!MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_OPTIMIZATION))
    {
        Print("   💾 Saving market structure state...");
        SaveMarketStructureState();
        Print("   ✅ Market structure state saved successfully");
    }
    
    datetime exportEndTime = GetTickCount();
    int exportDurationMs = (int)(exportEndTime - exportStartTime);
    
    Print("   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    Print("   ✅ FINAL EXPORT SELESAI!");
    PrintFormat("   ⏱️ Durasi export: %d ms", exportDurationMs);
    PrintFormat("   📁 File tersimpan di: Terminal\\MQL5\\Files\\");
    PrintFormat("   📅 Export date: %s", g_ExportDateStr);
    Print("   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    
    // Tampilkan lokasi file lengkap
    string terminalPath = TerminalInfoString(TERMINAL_DATA_PATH);
    PrintFormat("   📂 Folder lengkap: %s\\MQL5\\Files\\", terminalPath);
    Print("   📋 File yang dibuat:");
    Print("      1. Backtest_Results_*.csv");
    Print("      2. Backtest_Summary_*.csv");
    Print("      3. LLHHBOSData_*.csv");
    Print("      4. MarketStructure_*.csv");
    Print("      5. SessionZone_*.csv");
    Print("      6. MarketData_*_M15_*.csv");
    Print("      7. MarketData_*_H1_*.csv");
    Print("      8. MarketData_*_H4_*.csv");
    
    Print("════════════════════════════════════════════════════════════════");
    Print("✅ EA berhasil dihentikan. Semua data telah tersimpan.");
    Print("════════════════════════════════════════════════════════════════");
}

//+------------------------------------------------------------------+
//| Fungsi OnTester: Dipanggil saat backtest selesai di Strategy Tester|
//+------------------------------------------------------------------+
double OnTester()
{
    Print("📊 [TESTER] Backtest selesai. Mengexport data...");
    
    // Export HANYA di single backtest (bukan optimasi)
    // Di mode optimasi, OnTester dipanggil tiap pass -> export di OnDeinit saja
    if (!MQLInfoInteger(MQL_OPTIMIZATION))
    {
        SetExportDate();
        ExportAllData();
    }
    
    // Return net profit sebagai custom optimization criterion
    double totalNetProfit = 0;
    for (int i = 0; i < g_TradeCount; i++)
    {
        if (g_BacktestTrades[i].status == "EXECUTED")
        {
            totalNetProfit += g_BacktestTrades[i].profit + g_BacktestTrades[i].commission + g_BacktestTrades[i].swap;
        }
    }
    
    PrintFormat("📊 [TESTER] Total Net Profit: %.2f | Total Trades: %d", totalNetProfit, g_TradeCount);
    return totalNetProfit;
}

//+------------------------------------------------------------------+
//| Fungsi trailing stop 3 tahap (REAL-TIME + LOGGING DETAIL) M15    |
//+------------------------------------------------------------------+
void ApplyTrailingStop_M15()
{
    // Cek apakah ini candle baru di M15
    datetime currentBarTime = iTime(_Symbol, PERIOD_M15, 0);
    if(currentBarTime == lastTrailingBarTime_M15)
    {
        return; // Hanya eksekusi 1 kali pada penutupan/pembukaan bar M15
    }

    // Periode internal untuk ATR (menggunakan standar 14 bar) untuk ekspansi TP
    const int atrPeriod = 14;
    
    // Ambil rates M15 terupdate
    MqlRates rates[];
    ArraySetAsSeries(rates, true);
    int copied = CopyRates(_Symbol, PERIOD_M15, 0, atrPeriod + 2, rates);
    if(copied < atrPeriod + 2)
    {
        if(EnableTrailingLogs_M15)
            Print("⚠️ [DYNAMIC TRAILING M15] Gagal menyalin data rates, jumlah tersalin kurang dari kebutuhan.");
        return;
    }

    // Hitung rata-rata ATR dari lilin yang sudah closed (indeks 1 s/d atrPeriod) untuk ekspansi TP
    double sumTR = 0;
    for(int i = 1; i <= atrPeriod; i++)
    {
        double high = rates[i].high;
        double low = rates[i].low;
        double prevClose = rates[i+1].close;
        double tr = MathMax(high - low, MathMax(MathAbs(high - prevClose), MathAbs(low - prevClose)));
        sumTR += tr;
    }
    double avgATR = sumTR / (double)atrPeriod;

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

        // Skip posisi yang baru saja dibuka pada candle berjalan (menjaga SL awal tetap utuh)
        datetime positionOpenTime = (datetime)PositionGetInteger(POSITION_TIME);
        if(positionOpenTime >= currentBarTime)
        {
            continue;
        }

        double positionOpen = PositionGetDouble(POSITION_PRICE_OPEN);
        double sl = PositionGetDouble(POSITION_SL);
        double tp = PositionGetDouble(POSITION_TP);
        ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

        if(posType == POSITION_TYPE_BUY)
        {
            // 1. Perhitungan SL Tetap 3000 Poin (Bisa Naik & Turun)
            double trailingDistance = 3000 * _Point;
            double targetSL = NormalizeDouble(currentBid - trailingDistance, _Digits);
            
            // Batas maksimal SL: maksimal 3000 pips (3000 poin) di bawah harga entry (positionOpen)
            double minSL = NormalizeDouble(positionOpen - 3000 * _Point, _Digits);
            // Dan jangan sampai lebih dekat dari 150 poin ke harga Bid saat ini (agar tidak invalid stop)
            double maxSL = NormalizeDouble(currentBid - 150 * _Point, _Digits);
            
            targetSL = MathMax(minSL, MathMin(maxSL, targetSL));

            // 2. Perhitungan TP Dinamis (TP awal 3500 poin, melebar ke atas saat didekati, tidak boleh menyempit)
            double targetTP = tp;
            if(targetTP == 0)
            {
                targetTP = NormalizeDouble(positionOpen + 3500 * _Point, _Digits);
            }
            
            // Cek apakah harga sudah mendekati TP (jarak <= 1000 poin)
            if(targetTP - currentBid <= 1000 * _Point)
            {
                // Jika mendekati, perluas TP ke atas (tambahkan ekspansi dinamis berdasarkan ATR atau minimal 2000 poin)
                double tpExpansion = MathMax(2000 * _Point, avgATR * 3.0);
                targetTP = NormalizeDouble(currentBid + tpExpansion, _Digits);
            }
            
            // Pastikan TP hanya boleh bertambah besar (ke atas) dan tidak boleh menyempit (turun)
            if(tp > 0)
            {
                targetTP = MathMax(tp, targetTP);
            }

            // Modifikasi posisi jika target SL atau TP berbeda cukup signifikan (misal >= 10 poin)
            if(MathAbs(targetSL - sl) >= 10 * _Point || MathAbs(targetTP - tp) >= 10 * _Point)
            {
                if(trade.PositionModify(ticket, targetSL, targetTP))
                {
                    PrintFormat("🚀 [BAR DYNAMIC MODIFY BUY M15] Ticket %I64u: SL disesuaikan ke %.5f (Limit=%.5f), TP disesuaikan ke %.5f (TP awal/lama=%.5f)",
                                ticket, targetSL, minSL, targetTP, tp);
                }
                else
                {
                    PrintFormat("❌ [BAR DYNAMIC MODIFY BUY M15] Gagal modify ticket %I64u: %d", ticket, GetLastError());
                }
            }
            
            if(EnableTrailingLogs_M15)
            {
                PrintFormat("📊 [TRAILING BUY M15] Ticket=%I64u | Bid=%.5f | SL=%.5f -> TargetSL=%.5f | TP=%.5f -> TargetTP=%.5f",
                            ticket, currentBid, sl, targetSL, tp, targetTP);
            }
        }
        else if(posType == POSITION_TYPE_SELL)
        {
            // 1. Perhitungan SL Tetap 3000 Poin (Bisa Naik & Turun)
            double trailingDistance = 3000 * _Point;
            double targetSL = NormalizeDouble(currentAsk + trailingDistance, _Digits);
            
            // Batas maksimal SL: maksimal 3000 pips (3000 poin) di atas harga entry (positionOpen)
            double minSL = NormalizeDouble(positionOpen + 3000 * _Point, _Digits);
            // Dan jangan sampai lebih dekat dari 150 poin ke harga Ask saat ini
            double maxSL = NormalizeDouble(currentAsk + 150 * _Point, _Digits);
            
            targetSL = MathMin(minSL, MathMax(maxSL, targetSL));

            // 2. Perhitungan TP Dinamis (TP awal 3500 poin, melebar ke bawah saat didekati, tidak boleh menyempit)
            double targetTP = tp;
            if(targetTP == 0)
            {
                targetTP = NormalizeDouble(positionOpen - 3500 * _Point, _Digits);
            }
            
            // Cek apakah harga sudah mendekati TP (jarak <= 1000 poin)
            if(currentAsk - targetTP <= 1000 * _Point)
            {
                // Jika mendekati, perluas TP ke bawah (kurangi ekspansi dinamis berdasarkan ATR atau minimal 2000 poin)
                double tpExpansion = MathMax(2000 * _Point, avgATR * 3.0);
                targetTP = NormalizeDouble(currentAsk - tpExpansion, _Digits);
            }
            
            // Pastikan TP hanya boleh bertambah besar (ke bawah) dan tidak boleh menyempit (naik)
            if(tp > 0)
            {
                targetTP = MathMin(tp, targetTP);
            }

            if(MathAbs(targetSL - sl) >= 10 * _Point || MathAbs(targetTP - tp) >= 10 * _Point)
            {
                if(trade.PositionModify(ticket, targetSL, targetTP))
                {
                    PrintFormat("🚀 [BAR DYNAMIC MODIFY SELL M15] Ticket %I64u: SL disesuaikan ke %.5f (Limit=%.5f), TP disesuaikan ke %.5f (TP awal/lama=%.5f)",
                                ticket, targetSL, minSL, targetTP, tp);
                }
                else
                {
                    PrintFormat("❌ [BAR DYNAMIC MODIFY SELL M15] Gagal modify ticket %I64u: %d", ticket, GetLastError());
                }
            }
            
            if(EnableTrailingLogs_M15)
            {
                PrintFormat("📊 [TRAILING SELL M15] Ticket=%I64u | Ask=%.5f | SL=%.5f -> TargetSL=%.5f | TP=%.5f -> TargetTP=%.5f",
                            ticket, currentAsk, sl, targetSL, tp, targetTP);
            }
        }
    }

    // Set waktu pemrosesan terakhir agar tidak dieksekusi lagi pada candle yang sama
    lastTrailingBarTime_M15 = currentBarTime;
}

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
    
    //--- Reset legacy global buy flags hanya jika status berubah dari ada menjadi tidak ada ---
    if(lastHasBuyPosition_M15 && !hasBuyPosition_M15) 
    {
        trailingActivatedBuy_M15 = false;
        Print("[TRAILING RESET M15] Legacy Buy flags reset");
    }
    
    //--- Reset legacy global sell flags hanya jika status berubah dari ada menjadi tidak ada ---
    if(lastHasSellPosition_M15 && !hasSellPosition_M15) 
    {
        trailingActivatedSell_M15 = false;
        Print("[TRAILING RESET M15] Legacy Sell flags reset");
    }
    
    //--- Update status terakhir ---
    lastHasBuyPosition_M15 = hasBuyPosition_M15;
    lastHasSellPosition_M15 = hasSellPosition_M15;
}

void CheckTradeClosure_M15(TradeRecord_M15 &tradeRec)
{
    if (tradeRec.ticket == 0) return;
    
    // Check if the position is still open to evaluate active exit rules
    if (PositionSelectByTicket(tradeRec.ticket))
    {
        double positionProfit = PositionGetDouble(POSITION_PROFIT);
        datetime positionOpenTime = (datetime)PositionGetInteger(POSITION_TIME);
        
        bool shouldClose = false;
        string closeReason = "";
        
        // 1. Exit Rule: Profit >= 300 USD
        if (positionProfit >= 300.0)
        {
            shouldClose = true;
            closeReason = StringFormat("Profit >= 300 USD (Running: %.2f USD)", positionProfit);
        }
        
        // 2. Exit Rule: 3 BOS confirmed in the direction of the trend (including triggering BoS)
        if (!shouldClose)
        {
            int bosCount = 0;
            string expectedDirection = (tradeRec.type == "BUY") ? "Bullish" : "Bearish";
            // Use a buffer of 1 M15 bar (900 seconds) + 30 seconds execution buffer to include the triggering BoS
            datetime limitTime = positionOpenTime - PeriodSeconds(PERIOD_M15) - 30;
            
            for(int j = 0; j < g_LLHHBOSCount; j++)
            {
                if(g_LLHHBOSData[j].timeframe == "M15" && 
                   g_LLHHBOSData[j].type == "BoS" && 
                   g_LLHHBOSData[j].direction == expectedDirection &&
                   g_LLHHBOSData[j].time > limitTime)
                {
                    bosCount++;
                }
            }
            
            if (bosCount >= 3)
            {
                shouldClose = true;
                closeReason = StringFormat("Telah terjadi %d BoS %s terkonfirmasi sejak awal tren", bosCount, expectedDirection);
            }
        }
        
        if (shouldClose)
        {
            PrintFormat("🚨 [ACTIVE EXIT TRIGGERED] Ticket %I64u: Menutup posisi secara aktif karena %s", 
                        tradeRec.ticket, closeReason);
            if (trade.PositionClose(tradeRec.ticket))
            {
                PrintFormat("✅ [ACTIVE EXIT SUCCESS] Ticket %I64u ditutup aktif.", tradeRec.ticket);
            }
            else
            {
                PrintFormat("❌ [ACTIVE EXIT FAILED] Gagal menutup aktif ticket %I64u: %d", 
                            tradeRec.ticket, GetLastError());
            }
        }
    }
    
    // 🔍 DIAGNOSTIC: Log setiap check
    // PrintFormat("🔍 [CHECK] Ticket: %I64u | Type: %s | Entry Price: %.5f", 
    //             tradeRec.ticket, tradeRec.type, tradeRec.entry_price);
    
    if (!PositionSelectByTicket(tradeRec.ticket))
    {
        // Position CLOSED - found in history
        PrintFormat("✅ [CLOSED DETECTED] Ticket: %I64u is CLOSED", tradeRec.ticket);
        
        double profit = 0;
        double exitPrice = 0;
        datetime exitTime = 0;
        bool found = false;
        
        // Cari di history deal
        HistorySelect(0, TimeCurrent());
        int totalDeals = HistoryDealsTotal();
        PrintFormat("   Finding deals... Total deals in history: %d", totalDeals);
        
        string exitType = "UNKNOWN";
        for(int i = totalDeals-1; i >= 0; i--)
        {
            ulong dealTicket = HistoryDealGetTicket(i);
            if(HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID) == tradeRec.ticket)
            {
                profit = HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
                exitPrice = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
                exitTime = (datetime)HistoryDealGetInteger(dealTicket, DEAL_TIME);
                found = true;
                
                long dealReason = HistoryDealGetInteger(dealTicket, DEAL_REASON);
                if (dealReason == DEAL_REASON_SL)
                    exitType = "STOP_LOSS";
                else if (dealReason == DEAL_REASON_TP)
                    exitType = "TAKE_PROFIT";
                else if (dealReason == DEAL_REASON_EXPERT)
                {
                    exitType = "EXPERT_CLOSE";
                }
                else if (dealReason == DEAL_REASON_CLIENT)
                    exitType = "MANUAL_CLOSE";
                else
                    exitType = "REASON_" + IntegerToString(dealReason);
                
                PrintFormat("   ✅ Found deal for Ticket %I64u: Exit Price=%.5f, Profit=%.2f, Reason=%s (%d)", 
                            tradeRec.ticket, exitPrice, profit, exitType, dealReason);
                break;
            }
        }
        
        if(found)
        {
            PrintFormat("💰 [%s CLOSED M15] Ticket: %I64u | Entry: %.5f | Exit: %.5f | Profit: %.2f | Duration: %s | Exit Type: %s",
                        tradeRec.type,
                        tradeRec.ticket,
                        tradeRec.entry_price,
                        exitPrice,
                        profit,
                        TimeToString(exitTime - tradeRec.entry_time, TIME_MINUTES),
                        exitType);
            
            // 💾 Simpan trade ke array untuk export CSV/DB
            double lotSize = 0.01; // Default lot size
            
            // Get current session saat trade entry
            string entrySession = (tradeRec.session != "") ? tradeRec.session : GetCurrentSession();
            
            // Hitung spread cost dan commission dari history deals
            double spreadCost = 0;
            double commission = 0;
            double swapVal = 0;
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
                    // Akumulasi commission & swap (signed values from MT5)
                    commission += HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);
                    swapVal += HistoryDealGetDouble(dealTicket, DEAL_SWAP);
                }
            }
            
            SaveTradeToArray(tradeRec.ticket, _Symbol, tradeRec.type,
                             tradeRec.entry_price, exitPrice,
                             tradeRec.sl, tradeRec.tp, profit,
                             tradeRec.entry_time, exitTime,
                             lotSize, MagicNumber_M15, "M15",
                             spreadCost, commission, swapVal, entrySession);
                        
            // Reset trade record
            tradeRec.ticket = 0;
        }
        else
        {
            // ❌ Position closed tapi deal tidak ditemukan
            PrintFormat("❌ [WARNING] Ticket %I64u CLOSED tapi deal tidak ditemukan di history!", tradeRec.ticket);
        }
    }
    else
    {
        // Position MASIH OPEN
        // PrintFormat("⏳ [STILL OPEN] Ticket: %I64u still OPEN", tradeRec.ticket);
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
    if (CopyBuffer(handleEMA_H1, 0, 0, 1, emaBuffer_H1) > 0)
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
    {
        PrintFormat("❌ [H1 FILTER REJECT] BUY Entry rejected: H1 Close (%.5f) NOT above H1 EMA200 (%.5f)", 
                    h1Rate[0].close, emaH1);
    }
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
    {
        PrintFormat("❌ [H1 FILTER REJECT] SELL Entry rejected: H1 Close (%.5f) NOT below H1 EMA200 (%.5f)", 
                    h1Rate[0].close, emaH1);
    }
    return bearishConfirmed;
}

//+------------------------------------------------------------------+
//| H4 EMA FILTER - Konfirmasi Trend Higher Timeframe                |
//+------------------------------------------------------------------+
// Logika: Jika harga H4 masih di ATAS EMA H4 → JANGAN SELL (trend masih bullish)
//         Jika harga H4 masih di BAWAH EMA H4 → JANGAN BUY (trend masih bearish)

// Mendapatkan nilai EMA H4 saat ini
double GetEMA_H4()
{
    double emaBuffer[];
    if (CopyBuffer(handleEMA_H4, 0, 0, 1, emaBuffer) > 0)
        return emaBuffer[0];
    return 0;
}

// BUY: H4 close harus di ATAS EMA H4 (trend H4 bullish)
bool IsH4ConfirmedBullish()
{
    if (!EnableH4EMAFilter) return true; // Jika filter dinonaktifkan, selalu izinkan

    double emaH4 = GetEMA_H4();
    if (emaH4 <= 0)
    {
        Print("⚠️ [H4 EMA] Tidak bisa membaca nilai EMA H4 — entry diizinkan (fallback)");
        return true;
    }

    MqlRates h4Rate[];
    ArraySetAsSeries(h4Rate, true);
    if (CopyRates(_Symbol, PERIOD_H4, 0, 1, h4Rate) < 1) return true;

    double gapThreshold = MathMax(emaH4 * 0.0025, 500 * _Point);
    bool bullishH4 = (h4Rate[0].close > (emaH4 + gapThreshold));

    if (bullishH4)
        PrintFormat("🟢 [H4 EMA FILTER] BUY OK: H4 Close (%.5f) > EMA%d H4 (%.5f) + Gap Threshold (%.5f) - Trend H4 Bullish",
                    h4Rate[0].close, EMA_H4_Period, emaH4, gapThreshold);
    else
        PrintFormat("%s [H4 EMA FILTER] BUY DITOLAK: H4 Close (%.5f) <= EMA%d H4 (%.5f) + Gap Threshold (%.5f) - Trend H4 masih Bearish atau belum break gap%s",
                    H4EMA_LogOnly ? "⚠️ [LOG ONLY]" : "⛔",
                    h4Rate[0].close, EMA_H4_Period, emaH4, gapThreshold,
                    H4EMA_LogOnly ? " (entry tetap diizinkan)" : " (entry ditolak)");

    if (H4EMA_LogOnly) return true;
    return bullishH4;
}

// SELL: H4 close harus di BAWAH EMA H4 (trend H4 bearish)
bool IsH4ConfirmedBearish()
{
    if (!EnableH4EMAFilter) return true; // Jika filter dinonaktifkan, selalu izinkan

    double emaH4 = GetEMA_H4();
    if (emaH4 <= 0)
    {
        Print("⚠️ [H4 EMA] Tidak bisa membaca nilai EMA H4 — entry diizinkan (fallback)");
        return true;
    }

    MqlRates h4Rate[];
    ArraySetAsSeries(h4Rate, true);
    if (CopyRates(_Symbol, PERIOD_H4, 0, 1, h4Rate) < 1) return true;

    double gapThreshold = MathMax(emaH4 * 0.0025, 500 * _Point);
    bool bearishH4 = (h4Rate[0].close < (emaH4 - gapThreshold));

    if (bearishH4)
        PrintFormat("🔴 [H4 EMA FILTER] SELL OK: H4 Close (%.5f) < EMA%d H4 (%.5f) - Gap Threshold (%.5f) - Trend H4 Bearish",
                    h4Rate[0].close, EMA_H4_Period, emaH4, gapThreshold);
    else
        PrintFormat("%s [H4 EMA FILTER] SELL DITOLAK: H4 Close (%.5f) >= EMA%d H4 (%.5f) - Gap Threshold (%.5f) - Trend H4 masih Bullish atau belum break gap%s",
                    H4EMA_LogOnly ? "⚠️ [LOG ONLY]" : "⛔",
                    h4Rate[0].close, EMA_H4_Period, emaH4, gapThreshold,
                    H4EMA_LogOnly ? " (entry tetap diizinkan)" : " (entry ditolak)");

    if (H4EMA_LogOnly) return true;
    return bearishH4;
}

//+------------------------------------------------------------------+
//| BAR BODY RATIO FILTER - Candle Quality Check                     |
//+------------------------------------------------------------------+
// Cek apakah candle entry cukup kuat (body dominan, bukan doji/indecision).
// Candle lemah = body kecil relatif terhadap total range (high-low).
// Terbukti dari forensic data: hampir semua whipsaw loss terjadi saat
// candle entry memiliki body ratio rendah → pasar tidak berkomitmen arah.
//
// [UPDATE - Forensic Analysis 2023, Section 12.5.1]:
// H4 EMA Stretch-Aware Override:
//   Rule A: Jika |H4 Gap%| > H4_MaxStretch_Pct (1.9%) → enforce strict BR (MinBodyRatio 40%)
//            Candle indecision di area stretched = sinyal mean-reversion, TETAP blokir.
//   Rule B: Jika H4 Gap 0.5%-1.9% DAN momentum H4 searah trade → MinBR = H4_TrendMinBody (15%)
//            Candle doji di zona trending moderat = reaccumulation, IZINKAN entry.
//   Zone C: Jika |H4 Gap%| < 0.5% (sideways dekat EMA) → gunakan strict BR normal.
bool IsCandleStrong(MqlRates &rates[], bool isBuyTrade)
{
    // Jika filter dinonaktifkan total, selalu izinkan entry
    if (!EnableBodyRatioFilter) return true;

    double bodySize   = MathAbs(rates[1].close - rates[1].open); // bar[1] = confirmed closed bar
    double totalRange = rates[1].high - rates[1].low;
    double bodyRatio  = 0;

    // Hindari division by zero (flat bar / weekend gap)
    if (totalRange <= 0)
    {
        Print("⚠️ [BODY RATIO] Total range = 0, filter dilewati (flat bar)");
        return true;
    }
    bodyRatio = bodySize / totalRange;

    // ================================================================
    // H4 EMA STRETCH-AWARE ADAPTIVE THRESHOLD
    // (Aktif jika Enable_H4_BR_Override = true)
    // ================================================================
    double effectiveMinBR = MinBodyRatio; // Default: threshold ketat (40%)
    string overrideReason = "";

    if (Enable_H4_BR_Override)
    {
        double emaH4 = GetEMA_H4();

        if (emaH4 > 0)
        {
            // Ambil H4 close terkini
            MqlRates h4Rates[];
            ArraySetAsSeries(h4Rates, true);
            int h4Copied = CopyRates(_Symbol, PERIOD_H4, 0, H4_Momentum_Bars + 1, h4Rates);

            if (h4Copied >= H4_Momentum_Bars + 1)
            {
                double h4Close    = h4Rates[0].close;
                double h4GapPts   = h4Close - emaH4;          // + = di atas EMA (bullish)
                double h4GapPct   = (h4GapPts / emaH4) * 100; // persen dari EMA
                double absGapPct  = MathAbs(h4GapPct);

                // Momentum H4: perbandingan close sekarang vs N bar lalu
                double h4ClosePrev   = h4Rates[H4_Momentum_Bars].close;
                double h4Mom16h      = h4Close - h4ClosePrev;  // + = naik, - = turun

                // Apakah H4 gap searah dengan sinyal trade?
                // BUY: butuh H4 di ATAS EMA (h4GapPts > 0 = bullish)
                // SELL: butuh H4 di BAWAH EMA (h4GapPts < 0 = bearish)
                bool h4AlignedWithTrade = isBuyTrade ? (h4GapPts > 0) : (h4GapPts < 0);

                // Apakah momentum H4 (16h terakhir) searah trade?
                // BUY: butuh harga naik (h4Mom16h > 2)
                // SELL: butuh harga turun (h4Mom16h < -2)
                bool momAlignedWithTrade = isBuyTrade ? (h4Mom16h > 2.0) : (h4Mom16h < -2.0);

                string tradeDir = isBuyTrade ? "BUY" : "SELL";
                PrintFormat("📐 [BR ADAPTIVE] Konteks: %s | H4 Gap=%.2f%% | H4 Mom 16h=%.2f | Aligned=%s | MomOK=%s",
                            tradeDir, h4GapPct, h4Mom16h,
                            h4AlignedWithTrade ? "YES" : "NO",
                            momAlignedWithTrade ? "YES" : "NO");

                // ----- RULE A: STRETCHED ZONE (|gap%| > H4_MaxStretch_Pct) -----
                // Harga terlalu jauh dari EMA → risiko mean-reversion tinggi
                // → tetap gunakan strict BR (MinBodyRatio 40%)
                if (absGapPct > H4_MaxStretch_Pct)
                {
                    effectiveMinBR = MinBodyRatio;
                    overrideReason = StringFormat("RULE_A: H4 Gap=%.2f%% > %.1f%% (stretched) → strict BR %.0f%%",
                                                  h4GapPct, H4_MaxStretch_Pct, effectiveMinBR * 100);
                }
                // ----- RULE B: MODERATE TRENDING ZONE (H4_MinTrend_Pct <= |gap%| <= H4_MaxStretch_Pct) -----
                // Harga dalam tren moderat searah trade + momentum aktif
                // → longgarkan threshold ke H4_TrendMinBody (15%)
                else if (absGapPct >= H4_MinTrend_Pct)
                {
                    if (h4AlignedWithTrade && momAlignedWithTrade)
                    {
                        effectiveMinBR = H4_TrendMinBody; // Longgarkan ke 15%
                        overrideReason = StringFormat("RULE_B: H4 Gap=%.2f%% moderate+mom=%.1f aligned → override BR min %.0f%%",
                                                      h4GapPct, h4Mom16h, effectiveMinBR * 100);
                    }
                    else
                    {
                        effectiveMinBR = MinBodyRatio;
                        overrideReason = StringFormat("RULE_B: H4 Gap=%.2f%% moderate tapi mom/direction tidak aligned → strict BR %.0f%%",
                                                      h4GapPct, effectiveMinBR * 100);
                    }
                }
                // ----- ZONE C: SIDEWAYS NEAR EMA (|gap%| < H4_MinTrend_Pct) -----
                // Harga terlalu dekat EMA → tidak ada tren kuat, pakai strict BR
                else
                {
                    effectiveMinBR = MinBodyRatio;
                    overrideReason = StringFormat("ZONE_C: H4 Gap=%.2f%% near EMA (sideways) → strict BR %.0f%%",
                                                  h4GapPct, effectiveMinBR * 100);
                }

                PrintFormat("📐 [BR ADAPTIVE] %s | Body=%.2f%% vs MinBR=%.0f%%",
                            overrideReason, bodyRatio * 100, effectiveMinBR * 100);
            }
            else
            {
                // Fallback: tidak cukup data H4
                PrintFormat("⚠️ [BR ADAPTIVE] Data H4 tidak cukup (%d bar) → gunakan strict BR %.0f%%",
                            h4Copied, effectiveMinBR * 100);
            }
        }
        else
        {
            Print("⚠️ [BR ADAPTIVE] EMA H4 tidak tersedia → gunakan strict BR default");
        }
    }

    // ================================================================
    // KEPUTUSAN FINAL BERDASARKAN EFFECTIVE THRESHOLD
    // ================================================================
    bool isStrong = (bodyRatio >= effectiveMinBR);

    if (!isStrong)
    {
        PrintFormat("%s [BODY RATIO] Ratio=%.2f%% < EffMin=%.2f%% (orig=%.0f%%) → Candle LEMAH/INDECISION%s",
                    BodyRatio_LogOnly ? "📊 [LOG ONLY]" : "❌ [REJECT]",
                    bodyRatio * 100, effectiveMinBR * 100, MinBodyRatio * 100,
                    BodyRatio_LogOnly ? " (entry TETAP DIIZINKAN - mode log)" : " (entry ditolak)");
    }
    else
    {
        PrintFormat("✅ [BODY RATIO] Ratio=%.2f%% >= EffMin=%.2f%% → Candle VALID untuk entry",
                    bodyRatio * 100, effectiveMinBR * 100);
    }

    // LOG ONLY mode: selalu izinkan meski candle lemah
    if (BodyRatio_LogOnly) return true;

    return isStrong;
}

//+------------------------------------------------------------------+
//| SESSION FILTER - Bloking Jam Asia Khusus Entry Jam 01:00         |
//+------------------------------------------------------------------+
bool IsSessionAllowedForEntry()
{
    string currentSession = GetCurrentSession();
    MqlDateTime dt;
    TimeToStruct(TimeCurrent(), dt);
    
    // Jika sesi adalah Asia, blokir khusus untuk jam 01:00
    if (currentSession == "Asia" && dt.hour == 1)
    {
        static datetime lastLogTime = 0;
        if (TimeCurrent() - lastLogTime >= 300) // Log tiap 5 menit max untuk hindari spam
        {
            //PrintFormat("❌ [SESSION REJECT] Entry ditolak: Sesi %s, jam %02d:00 (entry diblokir khusus jam ini)", currentSession, dt.hour);
            lastLogTime = TimeCurrent();
        }
        return false;
    }
    
    return true;
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

void DetectAndDraw_M15(MqlRates &rates_M15[], bool backfillMode)
{
    //+----------------------------+
    //--- Loop Deteksi High/Low M15 ---| (Lines ~350-1500)
    //+----------------------------+

    int ratesSize_M15 = ArraySize(rates_M15);

    for (int i = ArraySize(rates_M15) - WindowSize_M15 - 1; i >= WindowSize_M15; i--)
    {
        // ✅ Skip bars yang sudah diproses pada sesi sebelumnya untuk menghindari overwrite/reset state
        if (backfillMode && g_LastProcessedBarTime_M15 > 0 && rates_M15[i].time <= g_LastProcessedBarTime_M15)
        {
            continue;
        }

        //-----------------------------------------------------------------------------------+
        // BACKFILL-ONLY CHoCH DETECTION (gap setelah EA restart)                              |
        // Live CHoCH trigger (akhir fungsi) hanya evaluasi rates_M15[1] → break yang terjadi  |
        // LALU PULIH di dalam gap warmup tidak terdeteksi (mis. LL break 04:00 lalu recover    |
        // sebelum bar terakhir warmup). Di sini cek SETIAP bar baru dalam gap supaya transisi  |
        // trend tercatat. Mirror cascade flag STRUKTUR dari live, TAPI OMIT semua mutasi trade |
        // (entry/closure/counter) — konsisten precedent BoS-continuation-backfill.             |
        // Guard g_LastProcessedBarTime_M15 > 0 → HANYA jalan saat resume; fresh start & live   |
        // path (backfillMode=false) tidak terpengaruh sama sekali.                             |
        //-----------------------------------------------------------------------------------+
        if (backfillMode && g_LastProcessedBarTime_M15 > 0 && rates_M15[i].time > g_LastProcessedBarTime_M15)
        {
            // --- Backfill CHoCH Bullish: close break HH terakhir ---
            if (!chochBullish_M15 && !isInTrendBullish_M15 &&
                lastAcceptedHH_M15 > 0 && rates_M15[i].close > lastAcceptedHH_M15 + 50 * _Point)
            {
                double   tempHH_BF     = lastAcceptedHH_M15;
                datetime tempHHTime_BF = lastLoggedValidHHTime_M15;
                         preChochLL_M15 = lastAcceptedLL_M15;

                // Cari LOW TERENDAH MURNI window (HH break → candle break) = HL leg bullish
                if (tempHHTime_BF > 0)
                {
                    double   lowestLL_BF     = -1;
                    datetime lowestLLTime_BF = 0;
                    for (int k = 1; k < ratesSize_M15; k++)
                    {
                        if (rates_M15[k].time <= tempHHTime_BF) break;
                        if (rates_M15[k].time > rates_M15[i].time) continue;
                        if (lowestLL_BF < 0 || rates_M15[k].low < lowestLL_BF)
                        {
                            lowestLL_BF     = rates_M15[k].low;
                            lowestLLTime_BF = rates_M15[k].time;
                        }
                    }
                    if (lowestLL_BF < 0) { lowestLL_BF = lastAcceptedLL_M15; lowestLLTime_BF = lastTimeLL_M15; }
                    lastAcceptedLL_M15 = lowestLL_BF;
                    lastTimeLL_M15     = lowestLLTime_BF;
                    preChochLL_M15     = lowestLL_BF;
                }
                UpdateAcceptedLevelVisuals_M15(preChochLL_M15, "LL", lastTimeLL_M15);

                Print("🔔 [CHoCH BULLISH M15 - BACKFILL] Break HH di gap: ",
                      DoubleToString(tempHH_BF, _Digits), " @ ", TimeToString(rates_M15[i].time));

                string chochName_BF = "CHoCH_Bull_M15_BF_" + IntegerToString((int)tempHHTime_BF) + "_at_" + IntegerToString((int)rates_M15[i].time);
                ObjectDelete(0, chochName_BF);
                ObjectCreate(0, chochName_BF, OBJ_TREND, 0, tempHHTime_BF, tempHH_BF, rates_M15[i].time, tempHH_BF);
                ObjectSetInteger(0, chochName_BF, OBJPROP_COLOR, clrGold);
                ObjectSetInteger(0, chochName_BF, OBJPROP_WIDTH, 1);
                ObjectSetInteger(0, chochName_BF, OBJPROP_STYLE, STYLE_SOLID);
                ObjectSetInteger(0, chochName_BF, OBJPROP_BACK, true);

                // --- Flag cascade STRUKTUR (mirror live CHoCH Bullish, OMIT mutasi trade) ---
                chochBullish_M15              = true;
                hhAfterChochConfirmedFlag_M15 = false;
                isInTrendBearish_M15          = false;
                chochBearish_M15              = false;
                chochBearishConfirmedFlag_M15 = false;
                llAfterChochConfirmedFlag_M15 = false;
                bosBearishConfirmedFlag_M15   = false;
                llAfterBosConfirmedFlag_M15   = false;
                bosBullishJustLogged_M15      = false;
                time_postChoCH_HH_M15         = -1;
                time_postChoCH_LL_M15         = -1;
                time_choch_bullish_M15        = rates_M15[i].time;
                time_choch_bearish_M15        = -1;
                timeBoSBearish_M15            = -1;
                postChoCH_LL_M15              = -1;
                preChochHH_M15                = -1;
                // ponytail: OMIT entryCountBuy/activeBuyCount/CheckTradeClosure — backfill struktur saja (posisi nyata direkonsiliasi terpisah)
                SaveLLHHBOSToArray("CHoCH", "Bullish", tempHH_BF, rates_M15[i].time, "M15", "Confirmed", preChochLL_M15, 0);
                SaveLLHHBOSToArray("LL", "Reference", preChochLL_M15, lastTimeLL_M15, "M15", "PreChoCH", 0, 0);
                ResetMode2_M15();
                UpdateAcceptedLevelVisuals_M15(-1, "LL", rates_M15[i].time);
                continue;
            }

            // --- Backfill CHoCH Bearish: close break LL terakhir ---
            if (!chochBearish_M15 && !isInTrendBearish_M15 &&
                lastAcceptedLL_M15 > 0 && rates_M15[i].close < lastAcceptedLL_M15 - 5 * _Point)
            {
                double   tempLL_BF     = lastAcceptedLL_M15;
                datetime tempLLTime_BF = lastLoggedValidLLTime_M15;
                         preChochHH_M15 = lastAcceptedHH_M15;
                datetime preChochHHTime_BF = lastLoggedValidHHTime_M15;

                // Cari HIGH TERTINGGI MURNI window (LL break → candle break) = LH leg bearish
                {
                    double   highestHH_BF     = -1;
                    datetime highestHHTime_BF = 0;
                    if (tempLLTime_BF > 0)
                    {
                        for (int k = 1; k < ratesSize_M15; k++)
                        {
                            if (rates_M15[k].time <= tempLLTime_BF) break;
                            if (rates_M15[k].time > rates_M15[i].time) continue;
                            if (highestHH_BF < 0 || rates_M15[k].high > highestHH_BF)
                            {
                                highestHH_BF     = rates_M15[k].high;
                                highestHHTime_BF = rates_M15[k].time;
                            }
                        }
                    }
                    if (highestHH_BF > 0)
                    {
                        preChochHH_M15     = highestHH_BF;
                        lastAcceptedHH_M15 = highestHH_BF;
                        preChochHHTime_BF  = highestHHTime_BF;
                    }
                    else
                    {
                        lastAcceptedHH_M15 = lastLoggedValidHH_M15;
                    }
                }
                UpdateAcceptedLevelVisuals_M15(lastAcceptedHH_M15, "HH", preChochHHTime_BF);

                Print("🔔 [CHoCH BEARISH M15 - BACKFILL] Break LL di gap: ",
                      DoubleToString(tempLL_BF, _Digits), " @ ", TimeToString(rates_M15[i].time));

                string chochName_BF = "CHoCH_Bear_M15_BF_" + IntegerToString((int)tempLLTime_BF) + "_at_" + IntegerToString((int)rates_M15[i].time);
                ObjectDelete(0, chochName_BF);
                ObjectCreate(0, chochName_BF, OBJ_TREND, 0, tempLLTime_BF, tempLL_BF, rates_M15[i].time, tempLL_BF);
                ObjectSetInteger(0, chochName_BF, OBJPROP_COLOR, clrOrangeRed);
                ObjectSetInteger(0, chochName_BF, OBJPROP_WIDTH, 1);
                ObjectSetInteger(0, chochName_BF, OBJPROP_STYLE, STYLE_SOLID);
                ObjectSetInteger(0, chochName_BF, OBJPROP_BACK, true);

                // --- Flag cascade STRUKTUR (mirror live CHoCH Bearish, OMIT mutasi trade) ---
                chochBearish_M15              = true;
                isInTrendBullish_M15          = false;
                chochBullish_M15              = false;
                hhAfterChochConfirmedFlag_M15 = false;
                chochBullishConfirmedFlag_M15 = false;
                llAfterChochConfirmedFlag_M15 = false;
                bosBullishConfirmedFlag_M15   = false;
                hhAfterBosConfirmedFlag_M15   = false;
                postChoCH_HH_M15              = -1;
                time_postChoCH_HH_M15         = -1;
                // ponytail: OMIT entryCountSell/activeSellCount/CheckTradeClosure — backfill struktur saja (posisi nyata direkonsiliasi terpisah)
                time_postChoCH_LL_M15         = -1;
                postChoCH_LL_M15              = -1;
                time_choch_bearish_M15        = rates_M15[i].time;
                time_choch_bullish_M15        = -1;
                timeBoSBullish_M15            = -1;
                preChochLL_M15                = -1;
                llBeforeHHAfterBos_M15        = -1;
                timeLLBeforeHHAfterBos_M15    = 0;
                llBeforeHHAfterBosSaved_M15   = false;
                SaveLLHHBOSToArray("CHoCH", "Bearish", tempLL_BF, rates_M15[i].time, "M15", "Confirmed", preChochHH_M15, 0);
                SaveLLHHBOSToArray("HH", "Reference", preChochHH_M15, preChochHHTime_BF, "M15", "PreChoCH", 0, 0);
                ResetMode2Bearish_M15();
                continue;
            }

            // --- Backfill BoS Bullish PERTAMA (transisi CHoCH→trend): close break postChoCH_HH ---
            // Continuation sudah ditangani blok BUG #3 (di dalam pivot processing). Ini melengkapi
            // first-BoS yang break-lalu-pulih di gap → kelas bug yang sama dgn CHoCH.
            if (chochBullish_M15 && !isInTrendBullish_M15 &&
                postChoCH_HH_M15 > 0 && time_postChoCH_HH_M15 > 0 &&
                rates_M15[i].time > time_postChoCH_HH_M15 &&
                rates_M15[i].close > postChoCH_HH_M15 + 50 * _Point)
            {
                // Window-low search untuk HL leg (mirror live first-BoS bullish)
                {
                    double   lowestLL_BF2     = -1;
                    datetime lowestLLTime_BF2 = 0;
                    for (int k = 1; k < ratesSize_M15; k++)
                    {
                        if (rates_M15[k].time <= time_postChoCH_HH_M15) break;
                        if (rates_M15[k].time > rates_M15[i].time) continue;
                        if (lowestLL_BF2 < 0 || rates_M15[k].low < lowestLL_BF2)
                        {
                            lowestLL_BF2     = rates_M15[k].low;
                            lowestLLTime_BF2 = rates_M15[k].time;
                        }
                    }
                    if (lowestLL_BF2 > 0)
                    {
                        lastAcceptedLL_M15 = lowestLL_BF2;
                        lastTimeLL_M15     = lowestLLTime_BF2;
                        UpdateAcceptedLevelVisuals_M15(lastAcceptedLL_M15, "LL", lastTimeLL_M15);
                    }
                }

                double   bosBullBreakLevel_BF2 = postChoCH_HH_M15;
                datetime bosBullBreakTime_BF2  = time_postChoCH_HH_M15;
                Print("🚀 [BoS BULLISH PERTAMA M15 - BACKFILL] Break postChoCH_HH di gap: ",
                      DoubleToString(bosBullBreakLevel_BF2, _Digits), " @ ", TimeToString(rates_M15[i].time));

                string bosName_BF2b = "BoS_Bull_M15_BF1_" + IntegerToString((int)bosBullBreakTime_BF2) + "_at_" + IntegerToString((int)rates_M15[i].time);
                ObjectDelete(0, bosName_BF2b);
                ObjectCreate(0, bosName_BF2b, OBJ_TREND, 0, bosBullBreakTime_BF2, bosBullBreakLevel_BF2, rates_M15[i].time, bosBullBreakLevel_BF2);
                ObjectSetInteger(0, bosName_BF2b, OBJPROP_COLOR, clrDeepSkyBlue);
                ObjectSetInteger(0, bosName_BF2b, OBJPROP_WIDTH, 1);
                ObjectSetInteger(0, bosName_BF2b, OBJPROP_STYLE, STYLE_SOLID);
                ObjectSetInteger(0, bosName_BF2b, OBJPROP_BACK, true);

                // --- Flag cascade STRUKTUR (mirror live first-BoS bullish, OMIT entry) ---
                postChoCH_HH_M15            = -1;
                time_postChoCH_HH_M15       = 0;
                bosBullishConfirmedFlag_M15 = true;
                isInTrendBullish_M15        = true;
                preChochLL_M15              = -1;
                timeBoSBullish_M15          = rates_M15[i].time;
                // ponytail: OMIT trade.Buy/entryCount/closure — backfill struktur saja
                SaveLLHHBOSToArray("BoS", "Bullish", bosBullBreakLevel_BF2, rates_M15[i].time, "M15", "Confirmed", lastAcceptedLL_M15, 0);
                // MODE3 ref (mirror live)
                llBeforeHHAfterBos_M15      = lastAcceptedLL_M15;
                timeLLBeforeHHAfterBos_M15  = rates_M15[i].time;
                llBeforeHHAfterBosSaved_M15 = true;
                continue;
            }

            // --- Backfill BoS Bearish PERTAMA (transisi CHoCH→trend): close break postChoCH_LL ---
            if (chochBearish_M15 && !isInTrendBearish_M15 && !bearishSearchCompleted_M15 &&
                postChoCH_LL_M15 > 0 && time_postChoCH_LL_M15 > 0 &&
                rates_M15[i].time > time_postChoCH_LL_M15 &&
                rates_M15[i].close < postChoCH_LL_M15 - 50 * _Point)
            {
                double   bosBearBreakLevel_BF2 = postChoCH_LL_M15;
                datetime bosBearBreakTime_BF2  = time_postChoCH_LL_M15;
                Print("🔥 [BoS BEARISH PERTAMA M15 - BACKFILL] Break postChoCH_LL di gap: ",
                      DoubleToString(bosBearBreakLevel_BF2, _Digits), " @ ", TimeToString(rates_M15[i].time));

                string bosName_BF2s = "BoS_Bear_M15_BF1_" + IntegerToString((int)bosBearBreakTime_BF2) + "_at_" + IntegerToString((int)rates_M15[i].time);
                ObjectDelete(0, bosName_BF2s);
                ObjectCreate(0, bosName_BF2s, OBJ_TREND, 0, bosBearBreakTime_BF2, bosBearBreakLevel_BF2, rates_M15[i].time, bosBearBreakLevel_BF2);
                ObjectSetInteger(0, bosName_BF2s, OBJPROP_COLOR, clrOrange);
                ObjectSetInteger(0, bosName_BF2s, OBJPROP_WIDTH, 1);
                ObjectSetInteger(0, bosName_BF2s, OBJPROP_STYLE, STYLE_SOLID);
                ObjectSetInteger(0, bosName_BF2s, OBJPROP_BACK, true);

                // --- Flag cascade STRUKTUR (mirror live first-BoS bearish, OMIT entry) ---
                postChoCH_LL_M15            = -1;
                time_postChoCH_LL_M15       = -1;
                bosBearishConfirmedFlag_M15 = true;
                isInTrendBearish_M15        = true;
                timeBoSBearish_M15          = rates_M15[i].time;
                absoluteHighFound_M15       = false;
                bearishSearchCompleted_M15  = false;
                // ponytail: OMIT trade.Sell/entryCount/closure — backfill struktur saja
                SaveLLHHBOSToArray("BoS", "Bearish", bosBearBreakLevel_BF2, rates_M15[i].time, "M15", "Confirmed", lastAcceptedHH_M15, 0);
                // MODE3 ref (mirror live)
                hhBeforellAfterBos_M15      = lastAcceptedHH_M15;
                timehhBeforellAfterBos_M15  = rates_M15[i].time;
                llBeforeHHAfterBosSaved_M15 = true;
                continue;
            }
        }

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

        // ✅ Asymmetric window for Lower High detection after LL after BoS
        // Kiri: mulai dari LL terakhir (bukan 25 bar mutlak)
        // Kanan: tetap 25 bar ke depan
        bool isLHCandidate_M15 = false;
        if (!isHigh_M15 && bosBearishConfirmedFlag_M15 && llAfterBosConfirmedFlag_M15 &&
            lastTimeLL_M15 > 0 && rates_M15[i].time > lastTimeLL_M15)
        {
            isLHCandidate_M15 = true;

            // Right side: full WindowSize bars into the future (newer bars -> lower index)
            int rightEnd_M15 = i - WindowSize_M15;
            if (rightEnd_M15 < 0) rightEnd_M15 = 0;
            for (int j = i - 1; j >= rightEnd_M15; j--)
            {
                if (rates_M15[i].high < rates_M15[j].high) { isLHCandidate_M15 = false; break; }
            }

            // Left side: from previous bar back until we hit the last accepted LL (older bars -> higher index)
            if (isLHCandidate_M15)
            {
                for (int j = i + 1; j < ratesSize_M15; j++)
                {
                    if (rates_M15[j].time <= lastTimeLL_M15) break; // reached LL or older
                    if (rates_M15[i].high < rates_M15[j].high) { isLHCandidate_M15 = false; break; }
                }
            }
        }

        // ✅ Asymmetric window for Higher Low detection after HH after BoS (bullish)
        // Mirror dari LH bearish. Kiri: mulai dari HH terakhir (time_lastHHAfterBos_M15),
        // bukan WindowSize bar mutlak. Kanan: tetap WindowSize bar ke depan.
        // Catatan: pakai time_lastHHAfterBos_M15 (bukan lastTimeHH_M15 yang tidak
        // pernah di-update saat runtime). Tujuan: HL valid tidak salah-tolak karena
        // lookback kiri melewati HH terakhir → pencarian LL terendah bullish lebih akurat.
        bool isHLCandidate_M15 = false;
        if (!isLow_M15 && bosBullishConfirmedFlag_M15 && hhAfterBosConfirmedFlag_M15 &&
            time_lastHHAfterBos_M15 > 0 && rates_M15[i].time > time_lastHHAfterBos_M15)
        {
            isHLCandidate_M15 = true;

            // Right side: full WindowSize bars into the future (newer bars -> lower index)
            int rightEndLL_M15 = i - WindowSize_M15;
            if (rightEndLL_M15 < 0) rightEndLL_M15 = 0;
            for (int j = i - 1; j >= rightEndLL_M15; j--)
            {
                if (rates_M15[i].low > rates_M15[j].low) { isHLCandidate_M15 = false; break; }
            }

            // Left side: from previous bar back until we hit the last HH after BoS (older bars -> higher index)
            if (isHLCandidate_M15)
            {
                for (int j = i + 1; j < ratesSize_M15; j++)
                {
                    if (rates_M15[j].time <= time_lastHHAfterBos_M15) break; // reached HH or older
                    if (rates_M15[i].low > rates_M15[j].low) { isHLCandidate_M15 = false; break; }
                }
            }
        }

        //  PrintFormat("🧐 Cek Price M15: Time=%s | Open=%.2f | Close=%.2f | Low=%.2f |",
        //     TimeToString(rates_M15[1].time), rates_M15[1].open, rates_M15[1].close, rates_M15[1].low);
        // --- Process High (HH) M15 ---
        if (isHigh_M15 || isLHCandidate_M15)
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
                    // FIX: LL (preChochLL) di-stamp pakai lastTimeLL_M15 (waktu low asli, mis. 05:00),
                    // BUKAN rates_M15[i].time (= waktu candle HH, mis. 21:15) → cegah duplikat LL
                    // di waktu salah. Konsisten dgn fix window-search di CHoCH trigger.
                    UpdateAcceptedLevelVisuals_M15(lastAcceptedLL_M15, "LL", lastTimeLL_M15);
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
                    
                    // SAVE CHoCH DATA akan dipanggil di trigger (pakai tempHH_M15 = HH yang di-break)
                    
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ [MODE 1.1 REJECTED M15] HH %.2f DITOLAK karena < Lebih rendah dari CHoCH+HH last Accepted HH %.2f | Time: %s",
                            rates_M15[i].high, lastAcceptedHH_M15, TimeToString(rates_M15[i].time));
                    if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);
                    continue; // Skip further processing for this rejected HH
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
                    //-----------------------------------------------------------------------------------+
                    // BUG #3 FIX: Deteksi BoS continuation bullish di backfill (gap break) sebelum overwrite  |
                    // Saat EA restart di tengah tren, bar gap yang menembus postChoCH_HH harus tercatat.      |
                    // Hanya deteksi+save+visual, entry tetap di OnTick (backfillMode=true → skip entry).       |
                    //-----------------------------------------------------------------------------------+
                    if (backfillMode &&
                        postChoCH_HH_M15 > 0 && time_postChoCH_HH_M15 > 0 &&
                        rates_M15[i].time > time_postChoCH_HH_M15 &&
                        rates_M15[i].close > postChoCH_HH_M15 + 50 * _Point)
                    {
                        double bosBullBreakLevel_M15 = postChoCH_HH_M15;
                        Print("🚀🚀🚀 [BoS BULLISH CONTINUATION M15 - BACKFILL] ⚡ Break di gap terdeteksi: ",
                              DoubleToString(bosBullBreakLevel_M15, _Digits), " @ ", TimeToString(rates_M15[i].time));

                        string bosLineName_BF = "BoS_Bull_M15_BF_" + IntegerToString((int)time_postChoCH_HH_M15) + "_at_" + IntegerToString((int)rates_M15[i].time);
                        ObjectDelete(0, bosLineName_BF);
                        ObjectCreate(0, bosLineName_BF, OBJ_TREND, 0, time_postChoCH_HH_M15, bosBullBreakLevel_M15, rates_M15[i].time, bosBullBreakLevel_M15);
                        ObjectSetInteger(0, bosLineName_BF, OBJPROP_COLOR, clrDeepSkyBlue);
                        ObjectSetInteger(0, bosLineName_BF, OBJPROP_WIDTH, 1);
                        ObjectSetInteger(0, bosLineName_BF, OBJPROP_STYLE, STYLE_SOLID);
                        ObjectSetInteger(0, bosLineName_BF, OBJPROP_BACK, true);

                        SaveLLHHBOSToArray("BoS", "Bullish", bosBullBreakLevel_M15, rates_M15[i].time, "M15", "Confirmed", lastAcceptedLL_M15, 0);

                        // Reset target setelah break tercatat
                        postChoCH_HH_M15      = -1;
                        time_postChoCH_HH_M15 = -1;
                    }
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
                            time_postChoCH_HH_M15       = rates_M15[i].time; // Update time postChoCH_HH
                            
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
                        if(CanPrintRejectLogs()) PrintFormat("❌ [MODE 2.1 REJECTED M15] HH %.2f DITOLAK karena < Lebih rendah dari BoS + HH %.2f | Time: %s",
                        rates_M15[i].high, lastAcceptedHH_M15, TimeToString(rates_M15[i].time));
                        if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);
                        continue; // Skip further processing for this rejected HH
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ [REJECTED M15] HH %.2f DITOLAK karena < Lebih rendah dari postCHoCH_HH %.2f | Time: %s",
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
                // Validasi: HH harus lebih tinggi dari lastAcceptedHH (mencegah HH palsu masuk CSV)
                if (rates_M15[i].time > time_choch_bearish_M15 && rates_M15[i].high > lastAcceptedHH_M15 && !hhAfterChochConfirmedFlag_M15)
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
                        if(CanPrintRejectLogs()) PrintFormat("❌ [MODE 2 BEARISH M15 - POST SEARCH REJECTED] HH %.2f DITOLAK karena < HH Tertinggi Absolut (%.2f) setelah pencarian selesai | Time: %s",
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ [MODE 3 BEARISH M15 - REJECTED] HH %.2f DITOLAK karena <= HH terakhir (%.2f) | Time: %s",
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

                if (rates_M15[i].time > lastTimeLL_M15)  // Gunakan lastTimeLL_M15 yang sudah disimpan di state
                {
                    if (absoluteHighestHH_M15 == -1 || rates_M15[i].high > absoluteHighestHH_M15)
                    {
                        double previousHH = absoluteHighestHH_M15;
                        absoluteHighestHH_M15 = rates_M15[i].high;
                        timeAbsoluteHighestHH_M15 = rates_M15[i].time;

                        if (previousHH == -1)
                        {
                            PrintFormat("📈 [MODE 3 BEARISH M15] Inisialisasi HH tertinggi sejak LL terakhir (%s): %.2f @ %s",
                                        TimeToString(lastTimeLL_M15), absoluteHighestHH_M15, TimeToString(rates_M15[i].time));
                        }
                        else
                        {
                            PrintFormat("📈 [MODE 3 BEARISH M15] Update HH tertinggi sejak LL terakhir (%s): %.2f -> %.2f @ %s",
                                        TimeToString(lastTimeLL_M15), previousHH, absoluteHighestHH_M15, TimeToString(rates_M15[i].time));
                        }
                        
                        // ✅ FIX: Simpan HH tertinggi ke accepted history & export ke CSV
                        lastAcceptedHH_M15 = absoluteHighestHH_M15;
                        UpdateAcceptedLevelVisuals_M15(lastAcceptedHH_M15, "HH", rates_M15[i].time);
                    }
                }

                // --- 3. Periksa HH baru terhadap berbagai kriteria M15 ---
                bool   hhRejected_M15   = false;
                string rejectReason_M15 = "";

                //------------------------------------------+
                // 3a. Periksa terhadap HH tertinggi absolut M15|
                // Penolakan HH lebih rendah dari absolut HH M15|
                //------------------------------------------+
                if (absoluteHighestHH_M15 != -1 && rates_M15[i].time > lastTimeLL_M15)
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ [MODE 3 BEARISH M15 - REJECTED by Abs High] HH %.2f DITOLAK karena %s (%.2f) | Time: %s",
                                rates_M15[i].high, rejectReason_M15, absoluteHighestHH_M15, TimeToString(rates_M15[i].time));
                    string boxNameRejected_M15 = "zone_hh_M15_" + IntegerToString((int)rates_M15[i].time);
                    if (ObjectFind(0, boxNameRejected_M15) >= 0) ObjectDelete(0, boxNameRejected_M15);
                    continue; // ✅ FIX: Skip ke HH berikutnya setelah reject
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ [MODE 3 BEARISH M15 - REJECTED by LH] HH %.2f DITOLAK karena lebih tinggi dari LH terakhir (%.2f) | Time: %s",
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
        if (isLow_M15 || isHLCandidate_M15)
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
                if(CanPrintRejectLogs()) PrintFormat("❌ [WAITING FOR HH M15 - REJECTED] LL %.2f DITOLAK karena terbentuk SETELAH BoS dikonfirmasi dalam fase 'Waiting for HH' | Time: %s | Status: bosBullish=true, hhAfterBos=false, LL time > BoS time",
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
                            
                            // SAVE CHoCH DATA akan dipanggil di trigger (pakai tempLL_M15 = LL yang di-break)
                            // SaveLLHHBOSToArray dipindah ke blok CHoCH Bearish trigger
                            
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
                            if(CanPrintRejectLogs()) PrintFormat("❌ [REJECTED M15] LL %.2f DITOLAK karena > Lebih Tinggi dari CHoCH+LL last Accepted LL %.2f | Time: %s",
                                    rates_M15[i].low, lastAcceptedLL_M15, TimeToString(rates_M15[i].time));
                            if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);
                        }
                }

            if (chochBullish_M15 && !isInTrendBullish_M15 && !hhAfterChochConfirmedFlag_M15)
                {
                    if (rates_M15[i].low > preChochLL_M15)
                    {
                        if(CanPrintRejectLogs()) PrintFormat("❌ [REJECTED M15] LL %.2f > preChochLL %.2f | Time: %s",
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
                //-----------------------------------------------------------------------------------+
                // BUG #3 FIX: Deteksi BoS continuation di backfill (gap break) sebelum target di-overwrite|
                // Saat EA restart di tengah tren, bar gap yang menembus postChoCH_LL harus tercatat.    |
                // Hanya deteksi+save+visual, entry tetap di OnTick (backfillMode=true → skip entry).     |
                //-----------------------------------------------------------------------------------+
                if (backfillMode &&
                    postChoCH_LL_M15 > 0 && time_postChoCH_LL_M15 > 0 &&
                    rates_M15[i].time > time_postChoCH_LL_M15 &&
                    rates_M15[i].close < postChoCH_LL_M15 - 50 * _Point)
                {
                    double bosBearBreakLevel_M15 = postChoCH_LL_M15;
                    Print("🔥🔥🔥 [BoS BEARISH CONTINUATION M15 - BACKFILL] ⚡ Break di gap terdeteksi: ",
                          DoubleToString(bosBearBreakLevel_M15, _Digits), " @ ", TimeToString(rates_M15[i].time));

                    string bosLineName_BF = "BoS_Bear_M15_BF_" + IntegerToString((int)time_postChoCH_LL_M15) + "_at_" + IntegerToString((int)rates_M15[i].time);
                    ObjectDelete(0, bosLineName_BF);
                    ObjectCreate(0, bosLineName_BF, OBJ_TREND, 0, time_postChoCH_LL_M15, bosBearBreakLevel_M15, rates_M15[i].time, bosBearBreakLevel_M15);
                    ObjectSetInteger(0, bosLineName_BF, OBJPROP_COLOR, clrOrange);
                    ObjectSetInteger(0, bosLineName_BF, OBJPROP_WIDTH, 1);
                    ObjectSetInteger(0, bosLineName_BF, OBJPROP_STYLE, STYLE_SOLID);
                    ObjectSetInteger(0, bosLineName_BF, OBJPROP_BACK, true);

                    SaveLLHHBOSToArray("BoS", "Bearish", bosBearBreakLevel_M15, rates_M15[i].time, "M15", "Confirmed", lastAcceptedHH_M15, 0);

                    // Reset target setelah break tercatat
                    postChoCH_LL_M15        = -1;
                    time_postChoCH_LL_M15   = -1;
                }
                //-------------------------------------------------------------------------------+
                // Dalam tren bearish, hanya LL yang lebih rendah setelah Bos valid M15|
                //-------------------------------------------------------------------------------+
                if (rates_M15[i].low < lastAcceptedLL_M15) // <-- Pembaruan utama dalam tren bullish
                {
                    lastAcceptedLL_M15 = rates_M15[i].low;
                    lastTimeLL_M15 = rates_M15[i].time; // Update time LL terakhir
                    PrintFormat("✅ [MODE 2.2 M15]Update last Accepted LL After Bos: %s | Time: %s", DoubleToString(lastAcceptedLL_M15, _Digits), TimeToString(rates_M15[i].time));
                    UpdateAcceptedLevelVisuals_M15(lastAcceptedLL_M15, "LL", rates_M15[i].time); // Update visual setelah semua kondisi
                    llAfterBosConfirmedFlag_M15 = true;          // Tandai HH setelah BoS bullish terkonfirmasi
                    //timeLLAfterBosConfirmed_M15 = TimeCurrent(); // Simpan waktu konfirmasi
                    postChoCH_LL_M15            = rates_M15[i].low;  // Update postChoCH_LL
                    time_postChoCH_LL_M15       = rates_M15[i].time; // Update time postChoCH_LL
                    
                    // ✅ Reset absoluteHighestHH untuk mulai tracking HH tertinggi sejak LL baru ini
                    // Ini penting untuk MODE 3 BEARISH Part 2: setiap LL baru = tracking HH baru dimulai
                    absoluteHighestHH_M15 = -1;
                    timeAbsoluteHighestHH_M15 = 0;
                    
                    PrintFormat("✅ Post CHoCH LL M15: %s | Time: %s", DoubleToString(postChoCH_LL_M15, _Digits), TimeToString(rates_M15[i].time));
                    PrintFormat("✅ LL After BoS Confirmed M15: %s | Time: %s", DoubleToString(lastAcceptedLL_M15, _Digits), TimeToString(rates_M15[i].time));
                    PrintFormat("🔄 [LL After BoS M15] Reset absoluteHighestHH_M15 untuk tracking HH sejak LL baru @ %s", TimeToString(rates_M15[i].time));
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ [REJECTED M15] LL %.2f DITOLAK karena > Lebih Tinggi dari BoS+LL last Accepted LL %.2f | Time: %s",
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
                    if(CanPrintRejectLogs()) Print("❌ [MODE 1 REJECTED M15] LL lebih tinggi dari PreChoCh LL: = ", lastAcceptedLL_M15);
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
                    if(CanPrintRejectLogs()) Print("❌ [MODE 1 REJECTED M15] LL lebih tinggi dari PreChoCh LL: = ", lastAcceptedLL_M15);
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
    (!bosBullishConfirmedFlag_M15 || rates_M15[i].time < timeBoSBullish_M15) && // Tambahkan !bosBullishConfirmedFlag_M15
    rates_M15[i].time > time_choch_bullish_M15)
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
                         if(CanPrintRejectLogs()) PrintFormat("❌ [MODE 2 M15 - POST SEARCH REJECTED] LL %.2f DITOLAK karena > LL Terendah Absolut (%.2f) setelah pencarian selesai | Time: %s",
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
                        
                        // ✅ FIX: Simpan LL terendah ke accepted history & export ke CSV
                        lastAcceptedLL_M15 = lowestLLSinceLastHHAfterBos_M15;
                        UpdateAcceptedLevelVisuals_M15(lastAcceptedLL_M15, "LL", rates_M15[i].time);
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ [MODE 3 M15 - REJECTED by Abs Low] LL %.2f DITOLAK karena %s (%.2f) | Time: %s",
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ [MODE 3 M15 - REJECTED by HL] LL %.2f DITOLAK karena lebih rendah dari HL terakhir (%.2f) | Time: %s",
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

                // ✅ FIX: Cari LOW TERENDAH MURNI dalam window (HH yang di-break → candle CHoCH).
                // Seed pakai sentinel (-1), BUKAN lastAcceptedLL_M15. Sebelumnya seed = LL lama
                // (mis. 1400 yang terbentuk SEBELUM HH) → swing low pullback di dalam window yang
                // lebih tinggi (mis. 1425) selalu ter-mask & tidak pernah terpilih.
                // Window: time > tempHHTime_M15 (setelah HH) DAN time <= candle break.
                // 1400 otomatis excluded (loop break saat time <= tempHHTime_M15), jadi LL referensi
                // CHoCH Bullish = titik terendah retracement sebelum breakout (basis HL & SL buy).
                if (tempHHTime_M15 > 0)
                {
                    double   lowestLLBeforeChoCH     = -1;   // sentinel: belum ada low di window
                    datetime lowestLLBeforeChoCHTime = 0;
                    for (int k = 1; k < ratesSize_M15; k++)
                    {
                        if (rates_M15[k].time <= tempHHTime_M15) break;      // sudah melewati HH yang di-break
                        if (rates_M15[k].time > rates_M15[1].time) continue; // lebih baru dari candle break
                        if (lowestLLBeforeChoCH < 0 || rates_M15[k].low < lowestLLBeforeChoCH)
                        {
                            lowestLLBeforeChoCH     = rates_M15[k].low;
                            lowestLLBeforeChoCHTime = rates_M15[k].time;
                        }
                    }
                    // Fallback (defensif): window kosong → pertahankan LL lama.
                    if (lowestLLBeforeChoCH < 0)
                    {
                        lowestLLBeforeChoCH     = lastAcceptedLL_M15;
                        lowestLLBeforeChoCHTime = lastTimeLL_M15;
                    }
                    lastAcceptedLL_M15 = lowestLLBeforeChoCH;
                    lastTimeLL_M15     = lowestLLBeforeChoCHTime;
                    preChochLL_M15     = lowestLLBeforeChoCH;
                }

                // Pakai lastTimeLL_M15 (= waktu low hasil loop window), BUKAN rates_M15[0].time.
                // rates_M15[0] = candle yang sedang terbentuk (candle berikutnya setelah break),
                // sehingga LL ter-stamp di waktu salah (mis. 16:15) padahal low sebenarnya 05:00.
                UpdateAcceptedLevelVisuals_M15(preChochLL_M15, "LL", lastTimeLL_M15); // Update visualisasi
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
                // 🔧 FIX: SAVE & Clear array entries - Check ALL open positions, reset only if closed
                PrintFormat("🔄 [CHoCH BULLISH RESET] Checking %d active BUY trades before reset...", activeBuyCount_M15);
                for(int j = 0; j < 10; j++) {
                    if(activeBuyTrades_M15[j].ticket > 0) {
                        PrintFormat("   Slot[%d]: Checking Ticket %I64u before reset", j, activeBuyTrades_M15[j].ticket);
                        CheckTradeClosure_M15(activeBuyTrades_M15[j]);
                        if(activeBuyTrades_M15[j].ticket > 0) {
                            PrintFormat("   Slot[%d]: Ticket %I64u STILL OPEN after check - keeping in array", j, activeBuyTrades_M15[j].ticket);
                        } else {
                            PrintFormat("   Slot[%d]: Ticket was CLOSED and saved - slot cleared", j);
                        }
                    }
                }
                activeBuyCount_M15            = 0;      // Reset active buy count
                time_postChoCH_HH_M15         = -1;     // Reset time_postChoCH_HH_M15
                time_postChoCH_LL_M15         = -1;     // Reset time_postChoCH_LL_M15
                time_choch_bullish_M15        = rates_M15[1].time;
                time_choch_bearish_M15        = -1;
                timeBoSBearish_M15            = -1;
                postChoCH_LL_M15              = -1;
                preChochHH_M15                = -1; // Simpan HH sebelum CHoCH Bullish
                // SAVE CHoCH BULLISH DATA - price = HH yang di-break (tempHH_M15), previousPrice = LL referensi
                SaveLLHHBOSToArray("CHoCH", "Bullish", tempHH_M15, rates_M15[1].time, "M15", "Confirmed", preChochLL_M15, 0);
                SaveLLHHBOSToArray("LL", "Reference", preChochLL_M15, lastTimeLL_M15, "M15", "PreChoCH", 0, 0);
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
            // ✅ KONSISTENSI dgn CHoCH Bullish (mirror): cari HIGH TERTINGGI MURNI di window
            // (LL yang di-break → candle break CHoCH) sebagai referensi HH = lower-high leg bearish.
            // Tanpa ini hanya pakai lastLoggedValidHH yang bisa nyangkut di HH lama (mis. 1200
            // sebelum LL) padahal lower-high antara LL & break (mis. 1150) yang relevan utk SL sell.
            // Window: time > tempLLTime_M15 (setelah LL di-break) DAN time <= candle break.
            datetime preChochHHTime_M15 = lastLoggedValidHHTime_M15; // fallback waktu
            {
                double   highestHHInWindow_M15     = -1;  // sentinel
                datetime highestHHInWindowTime_M15 = 0;
                if (tempLLTime_M15 > 0)
                {
                    for (int k = 1; k < ratesSize_M15; k++)
                    {
                        if (rates_M15[k].time <= tempLLTime_M15) break;      // sudah melewati LL yang di-break
                        if (rates_M15[k].time > rates_M15[1].time) continue; // lebih baru dari candle break
                        if (highestHHInWindow_M15 < 0 || rates_M15[k].high > highestHHInWindow_M15)
                        {
                            highestHHInWindow_M15     = rates_M15[k].high;
                            highestHHInWindowTime_M15 = rates_M15[k].time;
                        }
                    }
                }
                if (highestHHInWindow_M15 > 0)
                {
                    preChochHH_M15     = highestHHInWindow_M15;
                    lastAcceptedHH_M15 = highestHHInWindow_M15;
                    preChochHHTime_M15 = highestHHInWindowTime_M15;
                    PrintFormat("🔧 [CHoCH BEARISH M15] HH referensi (LH) = high tertinggi window LL→break: %.2f @ %s",
                                preChochHH_M15, TimeToString(preChochHHTime_M15));
                }
                else
                {
                    // Fallback (window kosong): perilaku lama — HH terdekat terakhir yang ter-log.
                    lastAcceptedHH_M15 = lastLoggedValidHH_M15;
                }
            }
            UpdateAcceptedLevelVisuals_M15(lastAcceptedHH_M15, "HH", preChochHHTime_M15); // waktu high asli (bukan candle break)
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
            // 🔧 FIX: SAVE & Clear array entries - Check ALL open positions, reset only if closed
            PrintFormat("🔄 [CHoCH BEARISH RESET] Checking %d active SELL trades before reset...", activeSellCount_M15);
            for(int j = 0; j < 10; j++) {
                if(activeSellTrades_M15[j].ticket > 0) {
                    PrintFormat("   Slot[%d]: Checking Ticket %I64u before reset", j, activeSellTrades_M15[j].ticket);
                    CheckTradeClosure_M15(activeSellTrades_M15[j]);
                    if(activeSellTrades_M15[j].ticket > 0) {
                        PrintFormat("   Slot[%d]: Ticket %I64u STILL OPEN after check - keeping in array", j, activeSellTrades_M15[j].ticket);
                    } else {
                        PrintFormat("   Slot[%d]: Ticket was CLOSED and saved - slot cleared", j);
                    }
                }
            }
            activeSellCount_M15           = 0;      // Reset active sell count
            // bosBearishJustLogged_M15      = false;       // 🔓 Reset log untuk trigger BoS baru (jika digunakan untuk Bearish)
            time_postChoCH_LL_M15         = -1;          // Reset waktu post-CHoCH LL (jika digunakan)
            postChoCH_LL_M15              = -1;          // Reset nilai post-CHoCH LL (jika digunakan)
            time_choch_bearish_M15        = rates_M15[1].time;  // SIMPAN WAKTU CHoCH
            time_choch_bullish_M15        = -1;
            timeBoSBullish_M15            = -1;
            preChochLL_M15                = -1; // Simpan LL sebelum CHoCH Bearish (untuk referensi MODE 2)
            // ponytail: reset referensi HL/BoS agar tidak tertinggal ke siklus berikutnya
            llBeforeHHAfterBos_M15        = -1;
            timeLLBeforeHHAfterBos_M15    = 0;
            llBeforeHHAfterBosSaved_M15   = false;
            // SAVE CHoCH BEARISH DATA - price = LL yang di-break (tempLL_M15), previousPrice = HH referensi (preChochHH_M15)
            SaveLLHHBOSToArray("CHoCH", "Bearish", tempLL_M15, rates_M15[1].time, "M15", "Confirmed", preChochHH_M15, 0);
            SaveLLHHBOSToArray("HH", "Reference", preChochHH_M15, preChochHHTime_M15, "M15", "PreChoCH", 0, 0);
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
        // ✅ KONSISTENSI dgn CHoCH Bullish: cari LOW TERENDAH MURNI di window
        // (HH yang di-break → candle break BoS) sebagai referensi LL (HL leg bullish).
        // Tanpa ini, lastAcceptedLL bisa nyangkut di LL lama pra-CHoCH yang lebih dalam
        // (mis. 4424) padahal pullback low antara HH & break (mis. 4458) adalah HL yang
        // relevan untuk SL buy. Window: time > time_postChoCH_HH_M15 (setelah HH) DAN
        // time <= candle break. Seed sentinel (-1); window kosong → LL lama dipertahankan.
        if (time_postChoCH_HH_M15 > 0)
        {
            double   lowestLLBeforeBoS_M15     = -1;
            datetime lowestLLBeforeBoSTime_M15 = 0;
            for (int k = 1; k < ratesSize_M15; k++)
            {
                if (rates_M15[k].time <= time_postChoCH_HH_M15) break;   // sudah melewati HH yang di-break
                if (rates_M15[k].time > rates_M15[1].time) continue;     // lebih baru dari candle break
                if (lowestLLBeforeBoS_M15 < 0 || rates_M15[k].low < lowestLLBeforeBoS_M15)
                {
                    lowestLLBeforeBoS_M15     = rates_M15[k].low;
                    lowestLLBeforeBoSTime_M15 = rates_M15[k].time;
                }
            }
            if (lowestLLBeforeBoS_M15 > 0)
            {
                PrintFormat("🔧 [BoS BULLISH M15] LL referensi (HL) = low terendah window HH→break: %.2f @ %s (LL lama %.2f)",
                            lowestLLBeforeBoS_M15, TimeToString(lowestLLBeforeBoSTime_M15), lastAcceptedLL_M15);
                lastAcceptedLL_M15 = lowestLLBeforeBoS_M15;
                lastTimeLL_M15     = lowestLLBeforeBoSTime_M15;
                // Simpan HL ke history SEKARANG (sebelum reset lastAcceptedLL=-1 di akhir blok),
                // dgn waktu low asli (lastTimeLL_M15) → ter-export ke CSV & tampil di chart.
                UpdateAcceptedLevelVisuals_M15(lastAcceptedLL_M15, "LL", lastTimeLL_M15);
            }
        }

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
        double bosBullishBreakLevel_M15 = postChoCH_HH_M15; // Capture HH yang di-break SEBELUM reset
        postChoCH_HH_M15            = -1;
        time_postChoCH_HH_M15       = 0;      // Reset waktu post-CHoCH HH
        bosBullishConfirmedFlag_M15 = true;
        isInTrendBullish_M15        = true;
        preChochLL_M15              = -1;
        // Di blok BoS Bullish:
        timeBoSBullish_M15 = rates_M15[1].time; // Disimpan saat BoS terpicu
        
        // SAVE BoS DATA - price = HH yang di-break (bosBullishBreakLevel_M15), previousPrice = LL referensi
        SaveLLHHBOSToArray("BoS", "Bullish", bosBullishBreakLevel_M15, rates_M15[1].time, "M15", "Confirmed", lastAcceptedLL_M15, 0);
        // Bersihkan HH line — level udah ke-sweep oleh BoS Bullish M15
        ObjectDelete(0, "line_lastAcceptedHH_M15");
        ObjectDelete(0, "label_lastAcceptedHH_M15");

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
        
        // --- ENTRY LOGIC ENABLED WITH FILTERS ---
        if (bosBullishConfirmedFlag_M15 &&
            rates_M15[0].close > ema200_M15 &&
            entryCountBuy_M15 < MaxEntriesPerCycle_M15)
        {
            bool isFiltered = false;
            string rejectReason = "N/A";
            
            if (!IsH1ConfirmedBullish())
            {
                isFiltered = true;
                rejectReason = "H1 EMA200 Filter";
            }
            else if (!IsH4ConfirmedBullish())
            {
                isFiltered = true;
                rejectReason = "H4 EMA Filter";
            }
            else if (!IsEMATrendingUp_M15())
            {
                isFiltered = true;
                rejectReason = "EMA Slope Filter";
            }
            else if (!IsCandleStrong(rates_M15, true))  // true = BUY context
            {
                isFiltered = true;
                rejectReason = "Body Ratio Filter";
            }
            else if (!IsSessionAllowedForEntry())
            {
                isFiltered = true;
                rejectReason = "Session Filter";
            }
            
            if (!isFiltered)
            {
                // ✅ REMOVED: Time gap requirement - Entry 2/3 dapat trigger immediate
                double entryPrice_M15 = rates_M15[1].close + 3 * _Point; // Sedikit di atas close
                double sl_M15, tp_M15;
                
                // Tentukan SL/TP berdasarkan entry ke berapa
                // ✅ Hybrid SL 3 Zones:
                double dynamicSL_Buy     = lastAcceptedLL_M15;
                double maxSLDistance_Buy = DefaultSL_Buy_M15 * _Point; // Batas Max Toleransi (3000)
                double minSLDistance_Buy = 1500 * _Point;              // Batas Transisi / Terlalu Dekat (1500)
                
                double distanceToLL_Buy  = entryPrice_M15 - dynamicSL_Buy;
                
                if (distanceToLL_Buy > maxSLDistance_Buy)
                {
                    // Zona 3: Terlalu Jauh (> Max), batasi ke Max
                    sl_M15 = entryPrice_M15 - maxSLDistance_Buy;
                    PrintFormat("📌 [Hybrid SL Buy Entry %d] ZONA 3 (Terlalu Jauh: %.0f poin). SL dibatasi ke Max: %.5f", entryCountBuy_M15 + 1, distanceToLL_Buy / _Point, sl_M15);
                }
                else
                {
                    // Zona 2: Ideal (< Max), gunakan LL + buffer 1000 point
                    sl_M15 = dynamicSL_Buy - 1000 * _Point;
                    
                    // Pastikan SL dengan tambahan buffer tidak melebihi Max SL
                    if (entryPrice_M15 - sl_M15 > maxSLDistance_Buy)
                    {
                        sl_M15 = entryPrice_M15 - maxSLDistance_Buy;
                        PrintFormat("📌 [Hybrid SL Buy Entry %d] ZONA 2 (Ideal: %.0f poin). SL + Buffer melebihi Max, dibatasi ke Max SL: %.5f", entryCountBuy_M15 + 1, distanceToLL_Buy / _Point, sl_M15);
                    }
                    else
                    {
                        PrintFormat("📌 [Hybrid SL Buy Entry %d] ZONA 2 (Ideal: %.0f poin). SL menggunakan LL + 1000 poin buffer: %.5f", entryCountBuy_M15 + 1, distanceToLL_Buy / _Point, sl_M15);
                    }
                }
                
                tp_M15 = entryPrice_M15 + DefaultTP_Buy_M15 * _Point;
                
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
                    currentBuyTrade_M15.session = GetCurrentSession();
                    currentBuyTrade_M15.trailing_step = 0;
                    
                    // 🔧 FIX: Find empty slot instead of using counter (prevent overwrite of open positions)
                    int buyTradeIndex = -1;
                    for(int k = 0; k < 10; k++) {
                        if(activeBuyTrades_M15[k].ticket == 0) {
                            buyTradeIndex = k;
                            break;
                        } else {
                            // Check if slot has a closed position
                            PrintFormat("   Slot[%d] occupied by Ticket %I64u", k, activeBuyTrades_M15[k].ticket);
                        }
                    }
                    
                    if(buyTradeIndex >= 0) {
                        PrintFormat("📝 [SAVING TO ARRAY] Slot[%d] = Ticket %I64u (Entry #%d)", buyTradeIndex, currentBuyTrade_M15.ticket, entryCountBuy_M15);
                        activeBuyTrades_M15[buyTradeIndex] = currentBuyTrade_M15;
                        activeBuyCount_M15 = entryCountBuy_M15;
                    } else {
                        PrintFormat("❌ [CRITICAL] No empty slots in BUY array! Cannot save Ticket %I64u. Occupied slots:", currentBuyTrade_M15.ticket);
                        for(int k = 0; k < 10; k++) {
                            if(activeBuyTrades_M15[k].ticket > 0) {
                                PrintFormat("   Slot[%d] has Ticket %I64u", k, activeBuyTrades_M15[k].ticket);
                            }
                        }
                    }
                    
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
            else
            {
                // Catat penolakan entry ke database backtest_result dengan alasan spesifik
                double estimatedEntry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
                if (estimatedEntry <= 0) {
                    MqlTick lastTick;
                    if (SymbolInfoTick(_Symbol, lastTick)) estimatedEntry = lastTick.ask;
                }
                RecordRejectedToBacktestTrades("BUY", estimatedEntry, rejectReason);
            }
        }
        // ✅ FULL FIX: LL udah ke-sweep oleh BoS Bullish M15 — reset supaya visual & state bersih
        lastAcceptedLL_M15 = -1;
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
        double bosBearishBreakLevel_M15 = postChoCH_LL_M15; // Capture LL yang di-break SEBELUM reset
        // chochBearish_M15              = false;
        postChoCH_LL_M15              = -1;
        time_postChoCH_LL_M15         = -1;
        bosBearishConfirmedFlag_M15   = true;
        isInTrendBearish_M15          = true;
        
        // SAVE BoS BEARISH DATA - price = LL yang di-break (bosBearishBreakLevel_M15), previousPrice = HH referensi
        SaveLLHHBOSToArray("BoS", "Bearish", bosBearishBreakLevel_M15, rates_M15[1].time, "M15", "Confirmed", lastAcceptedHH_M15, 0);
        // Bersihkan LL line — level udah ke-sweep oleh BoS Bearish M15
        ObjectDelete(0, "line_lastAcceptedLL_M15");
        ObjectDelete(0, "label_lastAcceptedLL_M15");
        // Di dalam blok BoS Bearish:
        timeBoSBearish_M15 = rates_M15[1].time;  // Simpan waktu BoS       
        // ⚠️ JANGAN reset absoluteHighestHH_M15 di sini! Nilai ini masih dibutuhkan untuk MODE 3 BEARISH Part 2
        // ResetMode2Bearish_M15(); // DIHAPUS: Reset akan menghapus absoluteHighestHH_M15 yang masih dibutuhkan
        
        // Reset hanya flag pencarian MODE 2 yang tidak dibutuhkan lagi:
        absoluteHighFound_M15 = false;
        bearishSearchCompleted_M15 = false;
        
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
        // --- ENTRY LOGIC WITH H1 & EMA FILTERS ---
        if (bosBearishConfirmedFlag_M15 &&
            rates_M15[0].close < ema200_M15 &&
            entryCountSell_M15 < MaxEntriesPerCycle_M15)
        {
            bool isFiltered = false;
            string rejectReason = "N/A";
            
            if (!IsH1ConfirmedBearish())
            {
                isFiltered = true;
                rejectReason = "H1 EMA200 Filter";
            }
            else if (!IsH4ConfirmedBearish())
            {
                isFiltered = true;
                rejectReason = "H4 EMA Filter";
            }
            else if (IsEMATrendingUp_M15())
            {
                isFiltered = true;
                rejectReason = "EMA Slope Filter";
            }
            else if (!IsCandleStrong(rates_M15, false)) // false = SELL context
            {
                isFiltered = true;
                rejectReason = "Body Ratio Filter";
            }
            else if (!IsSessionAllowedForEntry())
            {
                isFiltered = true;
                rejectReason = "Session Filter";
            }
            
            if (!isFiltered)
            {
                // ✅ REMOVED: Time gap requirement - Entry 2/3 dapat trigger immediate
                double entryPrice_M15 = rates_M15[1].close - 5 * _Point;  // Sedikit di bawah close
                double sl_M15, tp_M15;
                
                // Tentukan SL/TP berdasarkan entry ke berapa
                // ✅ Hybrid SL 3 Zones:
                double dynamicSL_Sell     = lastAcceptedHH_M15;
                double maxSLDistance_Sell = DefaultSL_Sell_M15 * _Point; // Batas Max Toleransi (3000)
                double distanceToHH_Sell  = dynamicSL_Sell - entryPrice_M15;
                
                if (distanceToHH_Sell > maxSLDistance_Sell)
                {
                    // Zona 3: Terlalu Jauh (> Max), batasi ke Max
                    sl_M15 = entryPrice_M15 + maxSLDistance_Sell;
                    PrintFormat("📌 [Hybrid SL Sell Entry %d] ZONA 3 (Terlalu Jauh: %.0f poin). SL dibatasi ke Max: %.5f", entryCountSell_M15 + 1, distanceToHH_Sell / _Point, sl_M15);
                }
                else
                {
                    // Zona 2: Ideal (< Max), gunakan HH + buffer 1000 point
                    sl_M15 = dynamicSL_Sell + 1000 * _Point;
                    
                    // Pastikan SL dengan tambahan buffer tidak melebihi Max SL
                    if (sl_M15 - entryPrice_M15 > maxSLDistance_Sell)
                    {
                        sl_M15 = entryPrice_M15 + maxSLDistance_Sell;
                        PrintFormat("📌 [Hybrid SL Sell Entry %d] ZONA 2 (Ideal: %.0f poin). SL + Buffer melebihi Max, dibatasi ke Max SL: %.5f", entryCountSell_M15 + 1, distanceToHH_Sell / _Point, sl_M15);
                    }
                    else
                    {
                        PrintFormat("📌 [Hybrid SL Sell Entry %d] ZONA 2 (Ideal: %.0f poin). SL menggunakan HH + 1000 poin buffer: %.5f", entryCountSell_M15 + 1, distanceToHH_Sell / _Point, sl_M15);
                    }
                }

                // TP bervariasi sesuai entry
                if (entryCountSell_M15 == 0) {
                    tp_M15 = entryPrice_M15 - DefaultTP_Sell_M15 * _Point;
                    Print("📌 [BoS Sell Entry 1] TP: ", DefaultTP_Sell_M15, " poin");
                } else if (entryCountSell_M15 == 1) {
                    tp_M15 = entryPrice_M15 - Entry2TP_Sell_M15 * _Point;
                    Print("📌 [BoS Sell Entry 2] TP: ", Entry2TP_Sell_M15, " poin");
                } else {
                    tp_M15 = entryPrice_M15 - Entry3TP_Sell_M15 * _Point;
                    Print("📌 [BoS Sell Entry 3] TP: ", Entry3TP_Sell_M15, " poin");
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
                    currentSellTrade_M15.session = GetCurrentSession();
                    currentSellTrade_M15.trailing_step = 0;
                    
                    // 🔧 FIX: Find empty slot instead of using counter (prevent overwrite of open positions)
                    int sellTradeIndex = -1;
                    for(int k = 0; k < 10; k++) {
                        if(activeSellTrades_M15[k].ticket == 0) {
                            sellTradeIndex = k;
                            break;
                        } else {
                            // Check if slot has a closed position
                            PrintFormat("   Slot[%d] occupied by Ticket %I64u", k, activeSellTrades_M15[k].ticket);
                        }
                    }
                    
                    if(sellTradeIndex >= 0) {
                        PrintFormat("📝 [SAVING TO ARRAY] Slot[%d] = Ticket %I64u (Entry #%d)", sellTradeIndex, currentSellTrade_M15.ticket, entryCountSell_M15);
                        activeSellTrades_M15[sellTradeIndex] = currentSellTrade_M15;
                        activeSellCount_M15 = entryCountSell_M15;
                    } else {
                        PrintFormat("❌ [CRITICAL] No empty slots in SELL array! Cannot save Ticket %I64u. Occupied slots:", currentSellTrade_M15.ticket);
                        for(int k = 0; k < 10; k++) {
                            if(activeSellTrades_M15[k].ticket > 0) {
                                PrintFormat("   Slot[%d] has Ticket %I64u", k, activeSellTrades_M15[k].ticket);
                            }
                        }
                    }
                    
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
            else
            {
                // Catat penolakan entry ke database backtest_result dengan alasan spesifik
                double estimatedEntry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
                if (estimatedEntry <= 0) {
                    MqlTick lastTick;
                    if (SymbolInfoTick(_Symbol, lastTick)) estimatedEntry = lastTick.bid;
                }
                RecordRejectedToBacktestTrades("SELL", estimatedEntry, rejectReason);
            }
        }
        // 💾 [FIX] Retain lastAcceptedHH_M15 untuk Mode 3 Bearish (validasi Lower High)
        // Visual cleanup untuk HH line dilakukan di UpdateAcceptedLevelVisuals_M15() saat HH baru ditemukan
        PrintFormat("💾 [BoS BEARISH M15] Retain lastAcceptedHH_M15 untuk Mode 3: %.5f", lastAcceptedHH_M15);

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
    Print("🔄 [WARMUP H1] Starting backfill scan...");
    
    MqlRates rates[];
    ArraySetAsSeries(rates, true);

    int need = MathMax(bars, WindowSize_H1*2 + 50);
    int copied = CopyRates(_Symbol, PERIOD_H1, 0, need, rates);
    if (copied <= 0)
    {
        Print("❌ WarmUp_H1 gagal CopyRates");
        return;
    }

    // ✅ Get last processed bar time dari resumed state
    datetime skipBefore = g_LastProcessedBarTime_H1;
    
    if (skipBefore > 0)
    {
        Print("📌 [WARMUP H1] Resume mode active");
        PrintFormat("   Last processed bar: %s", TimeToString(skipBefore));
    }
    else
    {
        Print("ℹ️ [WARMUP H1] No previous state, scanning all bars");
    }
    
    int skippedBars = 0;
    int processedBars = 0;

    g_BackfillMode_H1 = true;
    
    // Count skipped/processed bars
    for (int i = copied - 1; i >= 0; i--)
    {
        if (skipBefore > 0 && rates[i].time <= skipBefore)
            skippedBars++;
        else
            processedBars++;
    }
    
    // Process with DetectAndDraw_H1
    if (processedBars > 0 || skipBefore == 0)
    {
        DetectAndDraw_H1(rates, /*backfillMode=*/true);
    }
    
    g_BackfillMode_H1 = false;

    // Optional: set lastBarTime ke bar terakhir, agar OnTick nanti fokus ke bar berikutnya
    lastBarTime_H1 = rates[0].time;

    ChartRedraw();
    
    Print("✅ [WARMUP H1] Backfill completed:");
    PrintFormat("   📊 Total bars scanned: %d", copied);
    PrintFormat("   ⏭️  Skipped (already processed): %d", skippedBars);
    PrintFormat("   ✅ Processed (new bars): %d", processedBars);
    PrintFormat("   🕐 Last bar time: %s", TimeToString(lastBarTime_H1, TIME_DATE|TIME_MINUTES));
}

void WarmUp_M15(int bars)
{
    Print("🔄 [WARMUP M15] Starting backfill scan...");
    
    MqlRates rates[];
    ArraySetAsSeries(rates, true);

    int need = MathMax(bars, WindowSize_M15*2 + 50);
    int copied = CopyRates(_Symbol, PERIOD_M15, 0, need, rates);
    if (copied <= 0)
    {
        Print("❌ WarmUp_M15 gagal CopyRates");
        return;
    }

    // ✅ Get last processed bar time dari resumed state
    datetime skipBefore = g_LastProcessedBarTime_M15;
    
    if (skipBefore > 0)
    {
        Print("📌 [WARMUP M15] Resume mode active");
        PrintFormat("   Last processed bar: %s", TimeToString(skipBefore));
        PrintFormat("   Will skip bars before: %s", TimeToString(skipBefore));
    }
    else
    {
        Print("ℹ️ [WARMUP M15] No previous state, scanning all bars");
    }
    
    int skippedBars = 0;
    int processedBars = 0;

    g_BackfillMode_M15 = true;
    
    // ✅ SKIP DUPLICATE DETECTION: Hanya process bar SETELAH last processed time
    for (int i = copied - 1; i >= 0; i--)
    {
        // ✅ Skip bars yang sudah diproses sebelumnya
        if (skipBefore > 0 && rates[i].time <= skipBefore)
        {
            skippedBars++;
            continue;  // ← LANGSUNG SKIP, TIDAK DETECT ULANG!
        }
        
        // Process bar baru (atau semua bar jika no resume)
        // Note: DetectAndDraw_M15 akan dipanggil per bar di sini
        // Karena struktur code existing menggunakan DetectAndDraw_M15 untuk batch,
        // kita tetap panggil tapi dengan filtered rates
        processedBars++;
    }
    
    // Jika ada bars yang perlu diprocess, jalankan DetectAndDraw_M15
    if (processedBars > 0 || skipBefore == 0)
    {
        DetectAndDraw_M15(rates, /*backfillMode=*/true);
    }
    
    g_BackfillMode_M15 = false;

    // Optional: set lastBarTime ke bar terakhir, agar OnTick nanti fokus ke bar berikutnya
    lastBarTime_M15 = rates[0].time;

    ChartRedraw();
    
    Print("✅ [WARMUP M15] Backfill completed:");
    PrintFormat("   📊 Total bars scanned: %d", copied);
    PrintFormat("   ⏭️  Skipped (already processed): %d", skippedBars);
    PrintFormat("   ✅ Processed (new bars): %d", processedBars);
    PrintFormat("   🕐 Last bar time: %s", TimeToString(lastBarTime_M15, TIME_DATE|TIME_MINUTES));
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
        // ✅ Skip bars yang sudah diproses pada sesi sebelumnya untuk menghindari overwrite/reset state
        if (backfillMode && g_LastProcessedBarTime_H1 > 0 && rates_H1[i].time <= g_LastProcessedBarTime_H1)
        {
            continue;
        }

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

            if (EnableDrawLines_H1)
            {
                ObjectDelete(0, boxName_H1);
                ObjectCreate(0, boxName_H1, OBJ_RECTANGLE, 0, startTime_H1, rates_H1[i].high, endTime_H1, rates_H1[i].high + 3 * _Point);
                ObjectSetInteger(0, boxName_H1, OBJPROP_COLOR, clrRed);
                ObjectSetInteger(0, boxName_H1, OBJPROP_BACK, true);
            }
            
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ H1: [MODE 1.1 REJECTED] HH %.2f DITOLAK karena < Lebih rendah dari CHoCH+HH last Accepted HH %.2f | Time: %s",
                            rates_H1[i].high, lastAcceptedHH_H1, TimeToString(rates_H1[i].time));
                    if (ObjectFind(0, boxName_H1) >= 0) ObjectDelete(0, boxName_H1);
                    continue; // Skip further processing for this rejected HH
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
                //-----------------------------------------------------------------------------------+
                // BUG #3 FIX: Deteksi BoS continuation bullish H1 di backfill (gap break)                  |
                //-----------------------------------------------------------------------------------+
                if (backfillMode &&
                    postChoCH_HH_H1 > 0 && time_postChoCH_HH_H1 > 0 &&
                    rates_H1[i].time > time_postChoCH_HH_H1 &&
                    rates_H1[i].close > postChoCH_HH_H1 + 50 * _Point)
                {
                    double bosBullBreakLevel_H1 = postChoCH_HH_H1;
                    Print("🚀🚀🚀 H1: [BoS BULLISH CONTINUATION - BACKFILL] ⚡ Break di gap terdeteksi: ",
                          DoubleToString(bosBullBreakLevel_H1, _Digits), " @ ", TimeToString(rates_H1[i].time));

                    string bosLineName_BF = "H1_BoS_Bull_BF_" + IntegerToString((int)time_postChoCH_HH_H1) + "_at_" + IntegerToString((int)rates_H1[i].time);
                    ObjectDelete(0, bosLineName_BF);
                    ObjectCreate(0, bosLineName_BF, OBJ_TREND, 0, time_postChoCH_HH_H1, bosBullBreakLevel_H1, rates_H1[i].time, bosBullBreakLevel_H1);
                    ObjectSetInteger(0, bosLineName_BF, OBJPROP_COLOR, clrDeepSkyBlue);
                    ObjectSetInteger(0, bosLineName_BF, OBJPROP_WIDTH, 1);
                    ObjectSetInteger(0, bosLineName_BF, OBJPROP_STYLE, STYLE_SOLID);
                    ObjectSetInteger(0, bosLineName_BF, OBJPROP_BACK, true);

                    SaveLLHHBOSToArray("BoS", "Bullish", bosBullBreakLevel_H1, rates_H1[i].time, "H1", "Confirmed", lastAcceptedLL_H1, 0);

                    postChoCH_HH_H1      = -1;
                    time_postChoCH_HH_H1 = -1;
                }
                if (rates_H1[i].high > lastAcceptedHH_H1)
                {
                    double oldHH = lastAcceptedHH_H1;
                    lastAcceptedHH_H1 = rates_H1[i].high;
                    PrintFormat("✅ H1: [MODE 1]Update last Accepted HH After Bos: %s | Time: %s", DoubleToString(lastAcceptedHH_H1, _Digits), TimeToString(rates_H1[i].time));
                    UpdateAcceptedLevelVisuals_H1(lastAcceptedHH_H1, "HH", rates_H1[i].time);
                    hhAfterBosConfirmedFlag_H1 = true;
                    timeHHAfterBosConfirmed_H1 = TimeCurrent();
                    postChoCH_HH_H1            = rates_H1[i].high;
                    time_postChoCH_HH_H1       = rates_H1[i].time; // Update time postChoCH_HH
                    
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
                if(CanPrintRejectLogs()) PrintFormat("❌ H1: [MODE 2.1 REJECTED] HH %.2f DITOLAK karena < Lebih rendah dari BoS + HH %.2f | Time: %s",
                        rates_H1[i].high, lastAcceptedHH_H1, TimeToString(rates_H1[i].time));
                if (ObjectFind(0, boxName_H1) >= 0) ObjectDelete(0, boxName_H1);
                continue; // Skip further processing for this rejected HH
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ H1: [REJECTED] HH %.2f DITOLAK karena < Lebih rendah dari postCHoCH_HH %.2f | Time: %s",
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
                // Validasi: HH harus lebih tinggi dari lastAcceptedHH (mencegah HH palsu masuk CSV)
                if (rates_H1[i].time > time_choch_bearish_H1 && rates_H1[i].high > lastAcceptedHH_H1 && !hhAfterChochConfirmedFlag_H1)
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
                        if(CanPrintRejectLogs()) PrintFormat("❌ H1: [MODE 2 BEARISH - POST SEARCH REJECTED] HH %.2f DITOLAK karena < HH Tertinggi Absolut (%.2f) setelah pencarian selesai | Time: %s",
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ H1: [MODE 3 BEARISH - REJECTED] HH %.2f DITOLAK karena <= HH terakhir (%.2f) | Time: %s",
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

                if (rates_H1[i].time > lastTimeLL_H1)
                {
                    if (absoluteHighestHH_H1 == -1 || rates_H1[i].high > absoluteHighestHH_H1)
                    {
                        double previousHH = absoluteHighestHH_H1;
                        absoluteHighestHH_H1 = rates_H1[i].high;
                        timeAbsoluteHighestHH_H1 = rates_H1[i].time;

                        if (previousHH == -1)
                        {
                            PrintFormat("📈 H1: [MODE 3 BEARISH] Inisialisasi HH tertinggi sejak LL terakhir (%s): %.2f @ %s",
                                        TimeToString(lastTimeLL_H1), absoluteHighestHH_H1, TimeToString(rates_H1[i].time));
                        }
                        else
                        {
                            PrintFormat("📈 H1: [MODE 3 BEARISH] Update HH tertinggi sejak LL terakhir (%s): %.2f -> %.2f @ %s",
                                        TimeToString(lastTimeLL_H1), previousHH, absoluteHighestHH_H1, TimeToString(rates_H1[i].time));
                        }
                    }
                }

                bool   hhRejected_H1   = false;
                string rejectReason_H1 = "";

                if (absoluteHighestHH_H1 != -1 && rates_H1[i].time > lastTimeLL_H1)
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ H1: [MODE 3 BEARISH - REJECTED by Abs High] HH %.2f DITOLAK karena %s (%.2f) | Time: %s",
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ H1: [MODE 3 BEARISH - REJECTED by LH] HH %.2f DITOLAK karena lebih tinggi dari LH terakhir (%.2f) | Time: %s",
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

            if (EnableDrawLines_H1)
            {
                ObjectCreate(0, boxName_H1, OBJ_RECTANGLE, 0, startTime_H1, rates_H1[i].low - 3 * _Point, endTime_H1, rates_H1[i].low);
                ObjectSetInteger(0, boxName_H1, OBJPROP_COLOR, clrGreen);
                ObjectSetInteger(0, boxName_H1, OBJPROP_BACK, true);
            }
            
            //----------------------------------------------------------------------+
            // ⚠️ [NO MAN'S LAND REJECTION] Tolak LL saat menunggu HH setelah BoS H1  |
            // Syarat: BoS Bullish sudah terkonfirmasi TETAPI HH After BoS BELUM      |
            // NAMUN: Terima LL yang terbentuk SEBELUM BoS dikonfirmasi (valid swing) |
            //----------------------------------------------------------------------+
            if (bosBullishConfirmedFlag_H1 && !hhAfterBosConfirmedFlag_H1 && rates_H1[i].time > timeBoSBullish_H1)
            {
                if(CanPrintRejectLogs()) PrintFormat("❌ H1: [WAITING FOR HH - REJECTED] LL %.2f DITOLAK karena terbentuk SETELAH BoS dikonfirmasi dalam fase 'Waiting for HH' | Time: %s | Status: bosBullish=true, hhAfterBos=false, LL time > BoS time",
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
                    
                    // SAVE CHoCH DATA - price = LL yang di-break (preChochLL), BUKAN LL baru
                    SaveLLHHBOSToArray("CHoCH", "Bearish", preChochLL_H1, time_choch_bearish_H1, "H1", "Confirmed", preChochHH_H1, 0);
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ H1: [REJECTED] LL %.2f DITOLAK karena > Lebih Tinggi dari CHoCH+LL last Accepted LL %.2f | Time: %s",
                            rates_H1[i].low, lastAcceptedLL_H1, TimeToString(rates_H1[i].time));
                    if (ObjectFind(0, boxName_H1) >= 0) ObjectDelete(0, boxName_H1);
                }
            }

            if (chochBullish_H1 && !isInTrendBullish_H1 && !hhAfterChochConfirmedFlag_H1)
            {
                if (rates_H1[i].low > preChochLL_H1)
                {
                    if(CanPrintRejectLogs()) PrintFormat("❌ H1: [REJECTED] LL %.2f > preChochLL %.2f | Time: %s",
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
                //-----------------------------------------------------------------------------------+
                // BUG #3 FIX: Deteksi BoS continuation bearish H1 di backfill (gap break)                  |
                //-----------------------------------------------------------------------------------+
                if (backfillMode &&
                    postChoCH_LL_H1 > 0 && time_postChoCH_LL_H1 > 0 &&
                    rates_H1[i].time > time_postChoCH_LL_H1 &&
                    rates_H1[i].close < postChoCH_LL_H1 - 50 * _Point)
                {
                    double bosBearBreakLevel_H1 = postChoCH_LL_H1;
                    Print("🔥🔥🔥 H1: [BoS BEARISH CONTINUATION - BACKFILL] ⚡ Break di gap terdeteksi: ",
                          DoubleToString(bosBearBreakLevel_H1, _Digits), " @ ", TimeToString(rates_H1[i].time));

                    string bosLineName_BF = "H1_BoS_Bear_BF_" + IntegerToString((int)time_postChoCH_LL_H1) + "_at_" + IntegerToString((int)rates_H1[i].time);
                    ObjectDelete(0, bosLineName_BF);
                    ObjectCreate(0, bosLineName_BF, OBJ_TREND, 0, time_postChoCH_LL_H1, bosBearBreakLevel_H1, rates_H1[i].time, bosBearBreakLevel_H1);
                    ObjectSetInteger(0, bosLineName_BF, OBJPROP_COLOR, clrOrange);
                    ObjectSetInteger(0, bosLineName_BF, OBJPROP_WIDTH, 1);
                    ObjectSetInteger(0, bosLineName_BF, OBJPROP_STYLE, STYLE_SOLID);
                    ObjectSetInteger(0, bosLineName_BF, OBJPROP_BACK, true);

                    SaveLLHHBOSToArray("BoS", "Bearish", bosBearBreakLevel_H1, rates_H1[i].time, "H1", "Confirmed", lastAcceptedHH_H1, 0);

                    postChoCH_LL_H1      = -1;
                    time_postChoCH_LL_H1 = -1;
                }
                if (rates_H1[i].low < lastAcceptedLL_H1)
                {
                    double oldLL = lastAcceptedLL_H1;
                    lastAcceptedLL_H1 = rates_H1[i].low;
                    PrintFormat("✅ H1: [MODE 2.2]Update last Accepted LL After Bos: %s | Time: %s", DoubleToString(lastAcceptedLL_H1, _Digits), TimeToString(rates_H1[i].time));
                    UpdateAcceptedLevelVisuals_H1(lastAcceptedLL_H1, "LL", rates_H1[i].time);
                    llAfterBosConfirmedFlag_H1 = true;
                    postChoCH_LL_H1            = rates_H1[i].low;
                    time_postChoCH_LL_H1       = rates_H1[i].time; // Update time postChoCH_LL
                    
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ H1: [REJECTED] LL %.2f DITOLAK karena > Lebih Tinggi dari BoS+LL last Accepted LL %.2f | Time: %s",
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
                    if(CanPrintRejectLogs()) Print("❌ H1: [MODE 1 REJECTED] LL lebih tinggi dari PreChoCh LL: = ", lastAcceptedLL_H1);
                    if (ObjectFind(0, boxName_H1) >= 0) ObjectDelete(0, boxName_H1);
                    lastLoggedDeniedLL_H1 = rates_H1[i].low;
                }
                continue;
            }

            if (!hhAfterChochConfirmedFlag_H1 && chochBullish_H1 && !llAfterChochConfirmedFlag_H1 && !chochBearish_H1) 
            {
                if (lastAcceptedLL_H1 == -1 || rates_H1[i].low < lastAcceptedLL_H1) 
                {
                    if(CanPrintRejectLogs()) Print("❌ H1: [MODE 1 REJECTED] LL lebih tinggi dari PreChoCh LL: = ", lastAcceptedLL_H1);
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
                         if(CanPrintRejectLogs()) PrintFormat("❌ H1: [MODE 2 - POST SEARCH REJECTED] LL %.2f DITOLAK karena > LL Terendah Absolut (%.2f) setelah pencarian selesai | Time: %s",
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ H1: [MODE 3 - REJECTED by Abs Low] LL %.2f DITOLAK karena %s (%.2f) | Time: %s",
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
                    if(CanPrintRejectLogs()) PrintFormat("❌ H1: [MODE 3 - REJECTED by HL] LL %.2f DITOLAK karena lebih rendah dari HL terakhir (%.2f) | Time: %s",
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
        if (EnableDrawLines_H1)
        {
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
        }
        
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
        if (EnableDrawLines_H1)
        {
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
        }
        
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
        if (EnableDrawLines_H1)
        {
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
        }
        
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
        // Bersihkan HH line — level udah ke-sweep oleh BoS Bullish H1
        if (EnableDrawLines_H1)
        {
            ObjectDelete(0, "line_lastAcceptedHH_H1");
            ObjectDelete(0, "label_lastAcceptedHH_H1");
        }
        
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
        if (EnableDrawLines_H1)
        {
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
        }

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
        // Bersihkan LL line — level udah ke-sweep oleh BoS Bearish H1
        if (EnableDrawLines_H1)
        {
            ObjectDelete(0, "line_lastAcceptedLL_H1");
            ObjectDelete(0, "label_lastAcceptedLL_H1");
        }
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
    //+------------------------------------------------------------------+
    //| SESSION ZONE TRACKING - Dipanggil setiap tick                     |
    //+------------------------------------------------------------------+
    UpdateSessionZoneTracking();    // Update tracking sesi
    
    // 🔧 FIX: Rate-limit Visual Updates ke 1 menit sekali (Mencegah Lag Parah Saat Backtest)
    static datetime lastVisualUpdate = 0;
    datetime currentM1Time = iTime(_Symbol, PERIOD_M1, 0);
    if (currentM1Time != lastVisualUpdate)
    {
        lastVisualUpdate = currentM1Time;
        DrawSessionRangeShadows();      // Gambar shadow range untuk setiap session
        DisplaySessionInfo();           // Tampilkan info sesi di chart
    }

    if(Period() == PERIOD_M15)
    {
        // --- 1. Check Trade Closures (Real-time on every tick) ---
        CheckTradeClosure_M15(currentBuyTrade_M15);
        CheckTradeClosure_M15(currentSellTrade_M15);
        
        for(int i = 0; i < 10; i++)
        {
            if(activeBuyTrades_M15[i].ticket > 0)
                CheckTradeClosure_M15(activeBuyTrades_M15[i]);
            if(activeSellTrades_M15[i].ticket > 0)
                CheckTradeClosure_M15(activeSellTrades_M15[i]);
        }

        // --- 2. Apply Trailing Stop (Real-time on every tick) ---
        if(EnableTrailingStop_M15)
        {
            ApplyTrailingStop_M15();
            CheckTrailingReset_M15();
        }

        //--- Ambil Data Harga M15 (Bar-limited logic below) ---
        MqlRates rates_M15[];
        ArraySetAsSeries(rates_M15, true);
        int copied = CopyRates(_Symbol, PERIOD_M15, 0, MathMax(200, WindowSize_M15*2 + 10), rates_M15);
        if (copied < WindowSize_M15*2 + 1) return;
        if (rates_M15[0].time == lastBarTime_M15) return;
        lastBarTime_M15 = rates_M15[0].time;

        //+------------------------------------------------------------------+
        //| M15 BAR CLOSE: Export semua data + Save State + Reverse Sync      |
        //| Setiap M15 candle close, export semua file lalu sync ke project  |
        //| ✅ HANYA live trading — backtest export di OnTester/OnDeinit      |
        //+------------------------------------------------------------------+
        if (!MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_OPTIMIZATION))
        {
            SetExportDate();            // Handle date rollover
            ExportAllData();            // Export semua CSV per candle close
            SaveMarketStructureState(); // ponytail: state selalu fresh tiap candle
            // ReverseSyncCSV();           // Sync ke Backtest_result\
        }
        //+------------------------------------------------------------------+

        static bool isScriptLoadedLogged_M15 = false; // Variabel statis untuk memastikan log hanya sekali
        if (!isScriptLoadedLogged_M15)
        {
            Print("✅ Script 'HH_LL_Extraction_M15.mq5' BERHASIL DIMUAT dan sedang berjalan pada timeframe M15.");
            isScriptLoadedLogged_M15 = true; // Set flag ke true agar tidak diprint lagi
        }

        //+------------------------------------+
        //--- Pembacaan EMA200 dan Logging M15 ----|
        //+------------------------------------+
        double bufferEMA_M15[];
        if (CopyBuffer(handleEMA_M15, 0, 0, 1, bufferEMA_M15) == 1)
        {
            ema200_M15 = bufferEMA_M15[0];
        }
        else
        {
            Print("❌ Gagal ambil nilai EMA200 untuk M15");
        }

        DetectAndDraw_M15(rates_M15, /*backfillMode=*/false);
    }
    else if(Period() == PERIOD_H1)
    {
        //--- Ambil Data Harga H1 ---
        MqlRates rates_H1[];
        ArraySetAsSeries(rates_H1, true);
        if (CopyRates(_Symbol, PERIOD_H1, 0, 60, rates_H1) < WindowSize_H1 * 2 + 1) return;
        if (rates_H1[0].time == lastBarTime_H1) return;
        lastBarTime_H1 = rates_H1[0].time;

        static bool isScriptLoadedLogged_H1 = false;
        if (!isScriptLoadedLogged_H1)
        {
            Print("✅ H1: Script 'HH_LL_Extraction_H1.mq5' BERHASIL DIMUAT dan sedang berjalan.");
            isScriptLoadedLogged_H1 = true;
        }

        // --- Pembacaan EMA200 dan Logging H1 ----
        double bufferEMA_H1[];
        if (CopyBuffer(handleEMA_H1, 0, 0, 1, bufferEMA_H1) == 1)
        {
            ema200_H1 = bufferEMA_H1[0];
        }
        else
        {
            Print("❌ Gagal ambil nilai EMA200 untuk H1");
        }

        // ⚠️ H1 LOGIC DISABLED: DetectAndDraw_H1 is commented out, only EMA 200 H1 remains active
        // DetectAndDraw_H1(rates_H1, /*backfillMode=*/false);
    }
}

