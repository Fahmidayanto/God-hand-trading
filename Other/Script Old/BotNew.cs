//+------------------------------------------------------------------+
//| File: HH_LL_Extraction.mq5 (Conceptual Snippet)                 |
//| Purpose: Isolate HH/LL Detection and Horizontal Zone Drawing     |
//| Note: This is a conceptual representation based on botnew.txt.   |
//|       It requires the full context of the original script to run.|
//+------------------------------------------------------------------+
#include <Trade/Trade.mqh>  // Untuk fungsi trading
#include <Tools/datetime.mqh>  // Untuk manipulasi waktu
CTrade trade;  // Objek untuk eksekusi trading

// Parameter input yang bisa diubah user
input int WindowSize = 25;    // Ukuran window untuk deteksi high/low
input int ZoneLength = 100;  // Panjang zona yang digambar
input int MovingPeriod = 200;  // Periode moving average
input int MovingShift = 0;  // Shift moving average

// --- Assume these variables are declared globally in the original script ---
// --- Variabel high/low ---
double   lastHH_byTime = -1;  // Last higher high (nilai harga)
datetime lastTimeHH    = 0;   // Waktu last HH
double   lastLL_byTime = -1;  // Last lower low (nilai harga)
datetime lastTimeLL    = 0;   // Waktu last LL
int lastLogHour = -1;  // Jam terakhir log EMA

// --- Variabel konfirmasi ---
static double lastAcceptedHH      = -1;  // Last HH yang diterima (valid)
static double lastAcceptedLL      = -1;  // Last LL yang diterima (valid)
static double lastAcceptedLL_Bear = -1;  // Last LL bearish yang diterima (valid) - Unused?

// --- Variabel penolakan ---
static   double lastLoggedDeniedHH          = -1;  // Last HH yang ditolak
static   datetime lastLoggedDeniedHHBarTime = 0;   // Waktu bar HH ditolak
static   datetime lastLoggedDeniedHHLogTime = 0;   // Waktu log penolakan HH
static   double lastLoggedDeniedLL          = -1;  // Last LL yang ditolak
static   datetime lastLoggedDeniedLLBarTime = 0;   // Waktu bar LL ditolak
static   datetime lastLoggedDeniedLLLogTime = 0;   // Waktu log penolakan LL
datetime lastDeniedBarTime_HH               = 0;   // Waktu bar terakhir HH ditolak - Unused?

// --- Variabel pencegahan spam log HH ---
static double lastLoggedValidHH       = -1;  // Last valid HH yang dilog
static datetime lastLoggedValidHHTime = 0;   // Waktu log valid HH
static double lastLoggedValidLL       = -1;  // Last valid LL yang dilog
static datetime lastLoggedValidLLTime = 0;   // Waktu log valid LL

// Interval log penolakan
static int deniedLogIntervalSeconds  = 30;  // Interval log penolakan (detik)
static datetime lastProcessedTime_HH = 0;   // Waktu terakhir proses HH
static datetime lastProcessedTime_LL = 0;   // Waktu terakhir proses LL

// --- Variabel aktif ---
double activeCHoCH_HH = -1;  // CHoCH HH aktif - Unused in pure detection?
double activeBoS_HH   = -1;  // BoS HH aktif - Unused in pure detection?
double activeCHoCH_LL = -1;  // CHoCH LL aktif - Unused in pure detection?
double activeBoS_LL   = -1;  // BoS LL aktif - Unused in pure detection?

// --- Variabel post-CHoCH ---
double   postChoCH_HH      = -1;  // HH setelah CHoCH - Unused in pure detection?
datetime time_postChoCH_HH = 0;   // Waktu post-CHoCH HH - Unused in pure detection?
double   postChoCH_LL      = -1;  // LL setelah CHoCH - Unused in pure detection?
datetime time_postChoCH_LL = 0;   // Waktu post-CHoCH LL - Unused in pure detection?

// --- Variabel BoS ---
double   lastBoS_HH      = -1;  // Last BoS HH - Unused in pure detection?
datetime time_lastBoS_HH = 0;   // Waktu last BoS HH - Unused in pure detection?
double   lastBoS_LL      = -1;  // Last BoS LL - Unused in pure detection?
datetime time_lastBoS_LL = 0;   // Waktu last BoS LL - Unused in pure detection?

// --- Flags konfirmasi bullish ---
static bool chochBullishConfirmedFlag = false;  // Flag konfirmasi CHoCH bullish - Influences logic
static bool hhAfterChochConfirmedFlag = false;  // Flag HH setelah CHoCH - Influences logic
static bool bosBullishConfirmedFlag   = false;  // Flag konfirmasi BoS bullish - Influences logic
static bool hhAfterBosConfirmedFlag   = false;  // Flag HH setelah BoS - Influences logic

// --- Flags konfirmasi bearish ---
static bool chochBearishConfirmedFlag = false;  // Flag konfirmasi CHoCH bearish - Influences logic
static bool llAfterChochConfirmedFlag = false;  // Flag LL setelah CHoCH - Influences logic
static bool bosBearishConfirmedFlag   = false;  // Flag konfirmasi BoS bearish - Influences logic
static bool llAfterBosConfirmedFlag   = false;  // Flag LL setelah BoS - Influences logic

// --- Flags tren ---
bool chochBullish     = false;  // Flag CHoCH bullish - Influences logic
bool chochBearish     = false;  // Flag CHoCH bearish - Influences logic
bool isInTrendBullish = false;  // Flag dalam tren bullish - Influences logic
bool isInTrendBearish = false;  // Flag dalam tren bearish - Influences logic

// --- Variabel target CHoCH ---
static double targetChoCHBullishHH    = -1;  // Target HH untuk CHoCH bullish - Influences logic
static double targetChoCHBearishLL    = -1;  // Target LL untuk CHoCH bearish - Influences logic
static double targetChoCHBearishLowLL = -1;  // Target LL terendah untuk CHoCH bearish - Influences logic
static double targetBoSBearishLL      = -1;  // Target LL untuk BoS bearish - Influences logic
static double targetBoSBearishLowLL   = -1;  // Target HH untuk BoS bullish - Influences logic
double preChochHH                     = -1;  // HH sebelum CHoCH - Influences logic
double preChochLL                     = -1;  // LL sebelum CHoCH - Influences logic

// --- Variabel lainnya ---
static bool hlAfterHHChochSaved = false;  // 🔒 Kunci agar MODE 1 hanya aktif 1x - Influences logic
static bool isSearchingForNewHL = false;  // Flag untuk mencari Higher Low baru - Influences logic

// --- Variabel untuk pelacakan perubahan flag ---
static string lastLoggedFlagStatusBullish = "";  // Status bullish flag terakhir yang dilog
static string lastLoggedFlagStatusBearish = "";  // Status bearish flag terakhir yang dilog

// --- Penyimpanan status log sebelumnya ---
static datetime lastBoSTimeLogged = 0;

// Waktu bar terakhir diproses
datetime lastBarTime = 0;
static bool bosBullishJustLogged = false;

// Variabel indikator
int handleEMA = 0;  // Handle untuk EMA
double ema200 = 0;  // Nilai EMA200

// Waktu terakhir bar HH/LL diproses
datetime lastAcceptedLLTime = 0;
double   lastConfirmedHL      = -1;  // HL valid yang sudah dikunci
datetime time_lastConfirmedHL = 0;   // waktu HL valid
datetime timeBoSBullish = 0;
datetime timeBoSBearish = 0;

// --- Variabel untuk pelacakan LL sebelum HHAfterBoS ---
static double llBeforeHHAfterBos       = -1;     // LL sebelum HHAfterBoS terkonfirmasi
static datetime timeLLBeforeHHAfterBos = 0;      // Waktu LL sebelum HHAfterBoS terkonfirmasi
static bool llBeforeHHAfterBosSaved    = false;  // Flag apakah LL sebelum HHAfterBoS sudah disimpan
int    bos_counter                     = 0;      // 0 adalah nilai awal


// --- Variabel tambahan untuk pelacakan LL terendah absolut sejak HH terakhir setelah BoS ---
static double lowestLLSinceLastHHAfterBos = -1;  // LL terendah absolut sejak HH terakhir setelah BoS
static datetime time_lastHHAfterBos       = 0;   // Waktu HH terakhir setelah BoS

static double hhBeforellAfterBos       = -1;     // LL sebelum HHAfterBoS terkonfirmasi
static datetime timehhBeforellAfterBos = 0;      // Waktu LL sebelum HHAfterBoS terkonfirmasi


static datetime time_lastAcceptedLLTime = 0;  // Last LL bearish yang diterima (valid) - Unused?
// --- Akhir variabel tambahan ---
// --- Tambahkan deklarasi global di sini ---
datetime timeHHAfterBosConfirmed = 0;  // Inisialisasi dengan 0 (atau waktu default lainnya)


double   absoluteLowestLL       = -1;
datetime timeAbsoluteLowestLL   = 0;
bool     absoluteLowFound       = false;
bool     searchCompleted        = false;
// --- Akhir deklarasi global ---

double   absoluteHighestHH       = -1;
datetime timeAbsoluteHighestHH   = 0;
bool     absoluteHighFound       = false;
bool     bearishSearchCompleted  = false;

datetime time_choch_bearish = 0;  // Waktu CHoCH Bearish
datetime time_choch_bullish = 0;  // Waktu CHoCH Bull

// Di bagian deklarasi variabel global (di luar fungsi)
string previousLLBoxName = "";

bool hasEnteredTrade = false;

datetime lastEntryTime = 0;

bool hasEnteredSellTrade = false;
datetime lastSellEntryTime = 0;

// Parameter input yang bisa diubah user


// Parameter input untuk SL dan TP
input int DefaultSL_Buy  = 2000;   // Stop Loss untuk Buy (dalam poin)
input int DefaultTP_Buy  = 3000;   // Take Profit untuk Buy (dalam poin)
input int DefaultSL_Sell = 2000;   // Stop Loss untuk Sell (dalam poin)
input int DefaultTP_Sell = 3000;   // Take Profit untuk Sell (dalam poin)
input ulong MagicNumber = 12345; // Magic number untuk EA

// --- Variabel untuk trailing stop ---
double buyEntryPrice = 0.0;    // Harga entry posisi buy
double sellEntryPrice = 0.0;   // Harga entry posisi sell
bool trailingActivatedBuy = false; // Flag trailing aktif untuk buy
bool trailingActivatedSell = false; // Flag trailing aktif untuk sell

int handleEMA_H1;  // Handle untuk EMA200 di timeframe H1
double ema200_H1;  // Nilai EMA200 di timeframe H1
double lastClose_H1; // Harga close terakhir di H1

struct TradeRecord
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

TradeRecord currentBuyTrade;   // Untuk posisi buy aktif
TradeRecord currentSellTrade;  // Untuk posisi sell aktif

//+------------------------------------------------------------------+
//| FUNGSI BARU: Mengelola objek visual lastAcceptedHH dan lastAcceptedLL |
//+------------------------------------------------------------------+
void UpdateAcceptedLevelVisuals(double level, string type, datetime time) 
{
    string lineName    = "line_lastAccepted" + type;             // Nama objek garis, misal: "line_lastAcceptedHH"
    string labelName   = "label_lastAccepted" + type;            // Nama objek label, misal: "label_lastAcceptedHH"
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
                                     "lastAccepted" + type + ": " + DoubleToString(level, _Digits)); // Set teks label
    }
}

//+---------------------------------------------------------------+
//| Fungsi utilitas untuk menggambar garis tren pendek dengan label|
//+---------------------------------------------------------------+
void DrawLineShort(string name, datetime t1, double p1, datetime t2, double p2, color col, string label)
{
    // Buat garis tren
    ObjectCreate(0, name, OBJ_TREND, 0, t1, p1, t2, p2);
    ObjectSetInteger(0, name, OBJPROP_COLOR, col);
    ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
    ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
    ObjectSetInteger(0, name, OBJPROP_BACK, true); // Gambar di latar belakang
    
    // Buat label teks
    string labelName = name + "_label";
    // Hitung posisi label → Geser ke kanan 1 bar dan naik sedikit untuk visibilitas
    datetime labelTime  = t2 + PeriodSeconds();                                                   // Geser ke kanan 1 candle
    double   labelPrice = p1 + (label == "CHoCH" || label == "BoS" ? 8 * _Point : -10 * _Point);  // Naikkan/geser sesuai label
    
    ObjectCreate(0, labelName, OBJ_TEXT, 0, labelTime, labelPrice);
    ObjectSetInteger(0, labelName, OBJPROP_COLOR, col);
    ObjectSetInteger(0, labelName, OBJPROP_FONTSIZE, 9);  // Font lebih jelas
    ObjectSetInteger(0, labelName, OBJPROP_CORNER, CORNER_LEFT_UPPER); // Sudut kiri atas
    ObjectSetString(0, labelName, OBJPROP_TEXT, label);
}

void ResetMode2()
{
                absoluteLowestLL = -1; // -1 berarti belum ditemukan
                timeAbsoluteLowestLL = 0;
                absoluteLowFound = false; // Flag untuk menandai apakah LL terendah absolut sudah ditemukan
                searchCompleted = false; // Flag untuk menandai apakah pencarian selesai (setelah menemukan LL > terendah)

}

void ResetMode2Bearish()
{
    absoluteHighestHH      = -1;
    timeAbsoluteHighestHH  = 0;
    absoluteHighFound      = false;
    bearishSearchCompleted = false;
}

int OnInit()
{
    handleEMA = iMA(_Symbol, _Period, MovingPeriod, MovingShift, MODE_EMA, PRICE_CLOSE);
    if (handleEMA == INVALID_HANDLE)
    {
        Print("❌ Gagal membuat handle EMA200");
        return INIT_FAILED;
    }
    handleEMA_H1 = iMA(_Symbol, PERIOD_H1, MovingPeriod, MovingShift, MODE_EMA, PRICE_CLOSE);
    if (handleEMA_H1 == INVALID_HANDLE)
    {
        Print("❌ Gagal membuat handle EMA200 di H1");
        return INIT_FAILED;
    }
    trade.SetExpertMagicNumber(MagicNumber); // Set magic number
    Print("✅ EMA200 handle berhasil dibuat");
    Print("✅ EA CHoCH + BoS + Fibo Logging LOADED");
    return INIT_SUCCEEDED;
}

void GetH1Data()
{
    MqlRates h1Rates[];
    if (CopyRates(_Symbol, PERIOD_H1, 0, 1, h1Rates) == 1)
    {
        lastClose_H1 = h1Rates[0].close;
    }
    else
    {
        Print("❌ Gagal ambil data H1");
    }

    double bufferEMA_H1[];
    if (CopyBuffer(handleEMA_H1, 0, 0, 1, bufferEMA_H1) == 1)
    {
        ema200_H1 = bufferEMA_H1[0];
    }
    else
    {
        Print("❌ Gagal ambil EMA200 H1");
    }
}
//+------------------------------------------------------------------+
//| Fungsi trailing stop 3 tahap (REAL-TIME + LOGGING DETAIL)        |
//+------------------------------------------------------------------+
void ApplyTrailingStop()
{
    double currentBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double currentAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    for(int i = PositionsTotal()-1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket <= 0) continue;
        // Pastikan posisi milik EA ini
        if(PositionGetInteger(POSITION_MAGIC) != MagicNumber || 
           PositionGetString(POSITION_SYMBOL) != _Symbol)
            continue;

        double positionOpen = PositionGetDouble(POSITION_PRICE_OPEN);
        double sl = PositionGetDouble(POSITION_SL);
        ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

        if(posType == POSITION_TYPE_BUY)
        {
            double profitPoints = (currentBid - positionOpen) / _Point;
            // 🔍 LOG DETAIL UNTUK BUY TRAILING
            PrintFormat("📊 [TRAILING BUY] Time=%s | Bid=%.5f | Entry=%.5f | SL=%.5f | TP=%.5f | Profit=%.1f poin | Status: %s",
                        TimeToString(TimeCurrent(), TIME_MINUTES),
                        currentBid,
                        positionOpen,
                        sl,
                        PositionGetDouble(POSITION_TP),
                        profitPoints,
                        !trailingActivatedBuy ? "Step 0" :
                        trailingActivatedBuy == 1 ? "Step 1 Aktif" :
                        trailingActivatedBuy == 2 ? "Step 2 Aktif" : "Step 3 Aktif");

            // --- TAHAP 1: Aktifkan saat profit >= 800 poin ---
            if(profitPoints >= 800 && !trailingActivatedBuy)
            {
                double newSL = DefaultSL_Buy; // Set SL ke harga entry + 500 poin
                double newTP = DefaultTP_Buy;
                PrintFormat("✅ [TRAILING STEP 1] BUY: Profit %.1f poin >= 800 | Akan set SL=%.5f, TP=%.5f",
                            profitPoints, newSL, newTP);
                if(trade.PositionModify(ticket, newSL, newTP))
                {
                    Print("[TRAILING STEP 1] BUY: SL & TP berhasil diatur.");
                    trailingActivatedBuy = true;
                }
                else
                {
                    Print("❌ [TRAILING STEP 1] Gagal modify posisi BUY: ", GetLastError());
                }
            }
            // --- TAHAP 2: Aktifkan saat profit >= 2500 poin ---
            else if(profitPoints >= 3500 && trailingActivatedBuy == true && sl <= positionOpen + DefaultSL_Buy * _Point)
            {
                double newSL = positionOpen +  2000 * _Point;
                double newTP = positionOpen + (DefaultTP_Buy + 4500) * _Point;
                PrintFormat("✅ [TRAILING STEP 2] BUY: Profit %.1f poin >= 2500 | Akan set SL=%.5f",
                            profitPoints, newSL);
                if(trade.PositionModify(ticket, newSL, newTP))
                {
                    Print("[TRAILING STEP 2] BUY: SL & TP dinaikkan.");
                    trailingActivatedBuy = 2;
                }
                else
                {
                    Print("❌ [TRAILING STEP 2] Gagal modify posisi BUY: ", GetLastError());
                }
            }
            // --- TAHAP 3: Aktifkan saat profit >= 3000 poin ---
            else if(profitPoints >= 4000 && trailingActivatedBuy == 2 && sl <= positionOpen + (DefaultSL_Buy + 500) * _Point)
            {
                double newSL = positionOpen +  3000 * _Point;
                double newTP = positionOpen + 6000 * _Point;
                PrintFormat("✅ [TRAILING STEP 3] BUY: Profit %.1f poin >= 3000 | Akan set SL=%.5f",
                            profitPoints, newSL);
                if(trade.PositionModify(ticket, newSL, newTP))
                {
                    Print("[TRAILING STEP 3] BUY: SL & TP dinaikkan ke level tertinggi.");
                    trailingActivatedBuy = 3;
                }
                else
                {
                    Print("❌ [TRAILING STEP 3] Gagal modify posisi BUY: ", GetLastError());
                }
            }
        }
        else if(posType == POSITION_TYPE_SELL)
        {
            double profitPoints = (positionOpen - currentAsk) / _Point;
            // 🔍 LOG DETAIL UNTUK SELL TRAILING
            PrintFormat("📊 [TRAILING SELL] Time=%s | Ask=%.5f | Entry=%.5f | SL=%.5f | TP=%.5f | Profit=%.1f poin | Status: %s",
                        TimeToString(TimeCurrent(), TIME_MINUTES),
                        currentAsk,
                        positionOpen,
                        sl,
                        PositionGetDouble(POSITION_TP),
                        profitPoints,
                        !trailingActivatedSell ? "Step 0" :
                        trailingActivatedSell == 1 ? "Step 1 Aktif" :
                        trailingActivatedSell == 2 ? "Step 2 Aktif" : "Step 3 Aktif");

            // --- TAHAP 1: Aktifkan saat profit >= 800 poin ---
            if(profitPoints >= 800 && !trailingActivatedSell)
            {
                double newSL = positionOpen - 500 * _Point; // Set SL ke harga entry + 500 poin
                double newTP = positionOpen - (DefaultTP_Sell + 1000) * _Point;
                PrintFormat("✅ [TRAILING STEP 1] SELL: Profit %.1f poin >= 800 | Akan set SL=%.5f, TP=%.5f",
                            profitPoints, newSL, newTP);
                if(trade.PositionModify(ticket, newSL, newTP))
                {
                    Print("[TRAILING STEP 1] SELL: SL & TP berhasil diatur.");
                    trailingActivatedSell = true;
                }
                else
                {
                    Print("❌ [TRAILING STEP 1] Gagal modify posisi SELL: ", GetLastError());
                }
            }
            // --- TAHAP 2: Aktifkan saat profit >= 1800 poin ---
            else if(profitPoints >= 2000 && trailingActivatedSell == true && sl >= positionOpen - DefaultSL_Sell * _Point)
            {
                double newSL = positionOpen - (DefaultSL_Sell + 1500) * _Point;
                double newTP = positionOpen - (DefaultTP_Sell + 2500) * _Point;
                PrintFormat("✅ [TRAILING STEP 2] SELL: Profit %.1f poin >= 1800 | Akan set SL=%.5f",
                            profitPoints, newSL);
                if(trade.PositionModify(ticket, newSL, newTP))
                {
                    Print("[TRAILING STEP 2] SELL: SL & TP diturunkan.");
                    trailingActivatedSell = 2;
                }
                else
                {
                    Print("❌ [TRAILING STEP 2] Gagal modify posisi SELL: ", GetLastError());
                }
            }
            // --- TAHAP 3: Aktifkan saat profit >= 2500 poin ---
            else if(profitPoints >= 2500 && trailingActivatedSell == 2 && sl >= positionOpen - (DefaultSL_Sell + 500) * _Point)
            {
                double newSL = positionOpen - (DefaultSL_Sell + 1000) * _Point;
                double newTP = positionOpen - (DefaultTP_Sell + 1000) * _Point;
                PrintFormat("✅ [TRAILING STEP 3] SELL: Profit %.1f poin >= 2500 | Akan set SL=%.5f",
                            profitPoints, newSL);
                if(trade.PositionModify(ticket, newSL, newTP))
                {
                    Print("[TRAILING STEP 3] SELL: SL & TP diturunkan lebih jauh.");
                    trailingActivatedSell = 3;
                }
                else
                {
                    Print("❌ [TRAILING STEP 3] Gagal modify posisi SELL: ", GetLastError());
                }
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Reset trailing flags saat tidak ada posisi                       |
//+------------------------------------------------------------------+
void CheckTrailingReset()
{
    static bool lastHasBuyPosition = true;  // Simpan status sebelumnya
    static bool lastHasSellPosition = true; // Simpan status sebelumnya
    
    bool hasBuyPosition = false;
    bool hasSellPosition = false;
    
    for(int i = PositionsTotal()-1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket <= 0) continue;
        
        if(PositionGetInteger(POSITION_MAGIC) == MagicNumber && 
           PositionGetString(POSITION_SYMBOL) == _Symbol)
        {
            if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
                hasBuyPosition = true;
            else if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL)
                hasSellPosition = true;
        }
    }
    
    //--- Reset buy flags hanya jika status berubah dari ada menjadi tidak ada ---
    if(lastHasBuyPosition && !hasBuyPosition) 
    {
        trailingActivatedBuy = false;
        Print("[TRAILING RESET] Buy flags reset");
    }
    
    //--- Reset sell flags hanya jika status berubah dari ada menjadi tidak ada ---
    if(lastHasSellPosition && !hasSellPosition) 
    {
        trailingActivatedSell = false;
        Print("[TRAILING RESET] Sell flags reset");
    }
    
    //--- Update status terakhir ---
    lastHasBuyPosition = hasBuyPosition;
    lastHasSellPosition = hasSellPosition;
}

void CheckTradeClosure(TradeRecord &tradeRec)
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
            PrintFormat("💰 [%s CLOSED] Ticket: %I64u | Entry: %.5f | Exit: %.5f | Profit: %.2f | Duration: %s",
                        tradeRec.type,
                        tradeRec.ticket,
                        tradeRec.entry_price,
                        exitPrice,
                        profit,
                        TimeToString(exitTime - tradeRec.entry_time, TIME_MINUTES));
                        
            // Reset trade record
            tradeRec.ticket = 0;
        }
    }
}
//+------------------------------------------------------------------+
//| Fungsi OnTick: Dieksekusi pada setiap tick harga baru            |
//+------------------------------------------------------------------+
void OnTick()
{
    static bool isScriptLoadedLogged = false; // Variabel statis untuk memastikan log hanya sekali
    if (!isScriptLoadedLogged)
    {
        Print("✅ Script 'HH_LL_Extraction.mq5' BERHASIL DIMUAT dan sedang berjalan.");
        isScriptLoadedLogged = true; // Set flag ke true agar tidak diprint lagi
    }
    //--- Ambil Data Harga ---
    MqlRates rates[];
    ArraySetAsSeries(rates, true);
    if (CopyRates(_Symbol, PERIOD_M15, 0, 60, rates) < WindowSize * 2 + 1) return;
    if (rates[0].time == lastBarTime) return;
    lastBarTime = rates[0].time;

    //+------------------------------------+
    //--- Pembacaan EMA200 dan Logging ----|
    //+------------------------------------+
    double bufferEMA[];
    if (CopyBuffer(handleEMA, 0, 0, 1, bufferEMA) == 1)
    {
        ema200 = bufferEMA[0];
        
        MqlDateTime currentBarTime;
        TimeToStruct(rates[0].time, currentBarTime);
        
        // if (currentBarTime.hour != lastLogHour && currentBarTime.min == 0)
        // {
        //     PrintFormat("📈 EMA200 (%s): %.5f", TimeToString(rates[0].time, TIME_DATE | TIME_MINUTES), ema200);
        //     lastLogHour = currentBarTime.hour;
        // }
    }
    else
    {
        Print("❌ Gagal ambil nilai EMA200");
    }

    GetH1Data();

    CheckTradeClosure(currentBuyTrade);
    CheckTradeClosure(currentSellTrade);
    
    //+----------------------------+
    //--- Loop Deteksi High/Low ---| (Lines ~350-1500)
    //+----------------------------+
    for (int i = ArraySize(rates) - WindowSize - 1; i >= WindowSize; i--)
    {
        // --- Skip bars if they are within already processed CHoCH/BoS zones ---
        if ((chochBullish && rates[i].time < time_postChoCH_HH) ||
            (isInTrendBullish && rates[i].time < time_lastBoS_HH) ||
            (chochBearish && rates[i].time < time_postChoCH_LL) ||
            (isInTrendBearish && rates[i].time < time_lastBoS_LL))
        {
            continue;
        }
        
        // --- Check if current bar is a local High or Low within the WindowSize ---
        bool isHigh = true;
        bool isLow  = true;
        for (int j = i - WindowSize; j <= i + WindowSize; j++)
        {
            if (j == i) continue;
            if (rates[i].high < rates[j].high) isHigh = false;  // Not highest high in window
            if (rates[i].low > rates[j].low) isLow    = false;  // Not lowest low in window
        }
        //  PrintFormat("🧐 Cek Price: Time=%s | Open=%.2f | Close=%.2f | Low=%.2f |",
        //     TimeToString(rates[1].time), rates[1].open, rates[1].close, rates[1].low);
        // --- Process High (HH) ---
        if (isHigh)
        {   
            //----------------------------------------+
            // --- Basic Logging & Spam Prevention ---|
            //----------------------------------------+
            if (rates[i].time <= lastProcessedTime_HH) continue; // Skip if already processed this bar
            lastProcessedTime_HH = rates[i].time;
            if (rates[i].high == lastLoggedValidHH && rates[i].time == lastLoggedValidHHTime) continue; // Skip if already logged
            
            PrintFormat("✅ HH VALID TERBENTUK     : %.2f | Time: %s", rates[i].high, TimeToString(rates[i].time));
            
            lastLoggedValidHH     = rates[i].high;  // Update spam prevention
            lastLoggedValidHHTime = rates[i].time;
            
            // --- Visual Drawing (Zona HH) ---
            datetime startTime = rates[i].time;
            datetime endTime   = startTime + PeriodSeconds() * ZoneLength;
            string   boxName   = "zone_hh_" + IntegerToString((int)rates[i].time);
            
            ObjectDelete(0, boxName);
            ObjectCreate(0, boxName, OBJ_RECTANGLE, 0, startTime, rates[i].high, endTime, rates[i].high + 3 * _Point);
            ObjectSetInteger(0, boxName, OBJPROP_COLOR, clrRed);
            ObjectSetInteger(0, boxName, OBJPROP_BACK, true);
            
            //---------------------------------------------------------+
            //MODE MENUJU TREND BULLISH--------------------------------|
            //Khusus Pembentukan dan Penolakan HH----------------------|
            //---------------------------------------------------------+

            //----------------------------------------------------------------------+
            //CHoCH Bullish Confirmed, terbentuk HH valid sebagai target BoS Bullish|
            //----------------------------------------------------------------------|
            if (chochBullish && !isInTrendBullish)
            {
                //------------------------------------------------------------------------------------------------+
                //START: Logika Reset lastAcceptedLL ke preChoch LL setelah CHoCH Bullish dan HH valid (MODE 1) --|
                //------------------------------------------------------------------------------------------------+

                if (!hhAfterChochConfirmedFlag) 
                {
                    lastAcceptedLL            = preChochLL;
                    lastAcceptedHH            = rates[i].high;  
                    UpdateAcceptedLevelVisuals(lastAcceptedLL, "LL", rates[i].time);//Perubahan tadi di komen
                    // PrintFormat("DEBUG     : Checking HH After CHoCH Confirmed Flag trigger at HH %.2f @ %s", rates[i].high, TimeToString(rates[i].time));
                    UpdateAcceptedLevelVisuals(lastAcceptedHH, "HH", rates[i].time);
                    // lastAcceptedLL= -1; Perubahan
                    // lastLL_byTime = -1; Perubahan
                    postChoCH_HH              = rates[i].high;
                    time_postChoCH_HH         = rates[i].time;
                    chochBullishConfirmedFlag = true;
                    hhAfterChochConfirmedFlag = true;
                    bosBullishConfirmedFlag   = false;
                    hhAfterBosConfirmedFlag   = false;
                    PrintFormat("✅ HH After ChoCH Confirmed on = %.2f | Time: %s",lastAcceptedHH,TimeToString(rates[i].time));
                    PrintFormat("✅ [MODE 1 RESET] CHoCH Bullish dan HH After CHoCH terkonfirmasi. lastAcceptedLL direset ke PreChoCHLL=%.2f | Time: %s",
                            preChochLL, TimeToString(rates[i].time));
                    continue; // Lewati update HH ini
                }

                //------------------------------------------------+
                //Jika HH lebih rendah dari HH CHoCH maka di tolak|
                //------------------------------------------------+
                else if (rates[i].high < lastAcceptedHH) 
                {
                    PrintFormat("❌ [MODE 1.1 REJECTED] HH %.2f DITOLAK karena < Lebih rendah dari CHoCH+HH last Accepted HH %.2f | Time: %s",
                            rates[i].high, lastAcceptedHH, TimeToString(rates[i].time));
                    if (ObjectFind(0, boxName) >= 0) ObjectDelete(0, boxName);
                }
            }

            //----------------------------------------------------------------------+
            //CHoCH Bullish Confirmed, terbentuk HH valid sebagai target BoS Bullish|
            //----------------------------------------------------------------------|

            if (chochBullish && !isInTrendBullish && !hhAfterChochConfirmedFlag && rates[i].high > lastAcceptedHH) // <-- PENAMBAHAN KONDISI !hhAfterChochConfirmedFlag
            {
                postChoCH_HH      = rates[i].high; // <-- Sekarang hanya di-set sekali
                time_postChoCH_HH = rates[i].time; // <-- Sekarang hanya di-set sekali
                PrintFormat("🎯 [TARGET SET] BoS Bullish Target HH set ke: %.2f @ %s", postChoCH_HH, TimeToString(time_postChoCH_HH)); // Log tambahan untuk kejelasan
            }

            if (chochBullish && isInTrendBullish && rates[i].high > lastAcceptedHH) // <-- PENAMBAHAN KONDISI !hhAfterChochConfirmedFlag
            {
                postChoCH_HH      = rates[i].high; // <-- Sekarang hanya di-set sekali
                time_postChoCH_HH = rates[i].time; // <-- Sekarang hanya di-set sekali
                PrintFormat("🎯 [TARGET SET] BoS Bullish Target HH set ke: %.2f @ %s", postChoCH_HH, TimeToString(time_postChoCH_HH)); // Log tambahan untuk kejelasan
            }
            //------------------------------+
            // End logika target Bos Bullish|
            //------------------------------+
            
            //-------------------------------------------------------------+
            // --- START: Logika PEMBARUAN LASTACCEPTEDHH (DIREVISI) Part 2|
            //-------------------------------------------------------------+
            if (bosBullishConfirmedFlag && isInTrendBullish)
                {
                    //-------------------------------------------------------------------------------+
                    // Dalam tren bullish, hanya HH yang lebih tinggi dari last AcceptedHH yang valid|
                    //-------------------------------------------------------------------------------+
                    if (rates[i].high > lastAcceptedHH) // <-- Pembaruan utama dalam tren bullish
                        {
                            lastAcceptedHH = rates[i].high;
                            PrintFormat("✅ [MODE 1]Update last Accepted HH After Bos: %s | Time: %s", DoubleToString(lastAcceptedHH, _Digits), TimeToString(rates[i].time));
                            UpdateAcceptedLevelVisuals(lastAcceptedHH, "HH", rates[i].time); // Update visual setelah semua kondisi
                            hhAfterBosConfirmedFlag = true;           // Tandai HH setelah BoS bullish terkonfirmasi
                            timeHHAfterBosConfirmed = TimeCurrent();  // Simpan waktu konfirmasi
                            postChoCH_HH            = rates[i].high;  // Update postChoCH_HH
                            
                            // PrintFormat("✅ Post CHoCH HH: %s | Time: %s", DoubleToString(postChoCH_HH, _Digits), TimeToString(rates[i].time));
                            PrintFormat("✅ HH After BoS Confirmed: %s | Time: %s", DoubleToString(lastAcceptedHH, _Digits), TimeToString(rates[i].time));
                            
                            // --- PERBAIKAN: Reset pelacak LL terendah absolut sejak HH terakhir ---
                            // Saat HH baru terkonfirmasi setelah BoS, reset pencarian LL terendah.
                            lowestLLSinceLastHHAfterBos = -1;             // Atau bisa rates[i].high + 1000*_Point untuk nilai awal yang sangat tinggi
                            time_lastHHAfterBos         = rates[i].time;  // Simpan waktu HH terakhir ini
                            PrintFormat("🔄 [HH After BoS Confirmed] Reset pencarian LL terendah. Waktu referensi HH: %s", TimeToString(time_lastHHAfterBos));
                            // --- AKHIR PERBAIKAN ---
                        }
                }        
            else// Kondisi default atau netral (belum ada tren yang jelas)
                {
                    // Lanjutkan mencari Higher High secara default
                    if (rates[i].high > lastAcceptedHH) // <-- Pembaruan utama
                        {
                            lastAcceptedHH = rates[i].high;
                            PrintFormat("✅ [MODE 1] Update Last Accepted HH (Default): %s | Time: %s", DoubleToString(lastAcceptedHH, _Digits), TimeToString(rates[i].time));
                            UpdateAcceptedLevelVisuals(lastAcceptedHH, "HH", rates[i].time); // Update visual setelah semua kondisi
                        }
                }  

                if (bosBullishConfirmedFlag && hhAfterBosConfirmedFlag && rates[i].high < lastAcceptedHH)
                    {
                        PrintFormat("❌ [MODE 2.1 REJECTED] HH %.2f DITOLAK karena < Lebih rendah dari BoS + HH %.2f | Time: %s",
                        rates[i].high, lastAcceptedHH, TimeToString(rates[i].time));
                        if (ObjectFind(0, boxName) >= 0) ObjectDelete(0, boxName);
                    }

            //----------------------------------------------------------------------+
            //BoS Bullish Confirmed, terbentuk HH valid sebagai target BoS Bullish  |
            //----------------------------------------------------------------------+
            if (hhAfterChochConfirmedFlag && bosBullishConfirmedFlag && isInTrendBullish && rates[i].high > lastAcceptedHH)
            {
                postChoCH_HH      = rates[i].high;
                time_postChoCH_HH = rates[i].time;
                // PrintFormat("✅ BoS Bullish terkonfirmasi: postChoCH_HH=%.2f | Time: %s", postChoCH_HH, TimeToString(rates[i].time));
            }

            //-------------------------------------------------------+
            //HH After BoS Confirmed---------------------------------|
            //Logika penolakan HH yang lebih rendah dari HH Bos      |
            //Penolakan HH Pada saat Trend Bullish                   |
            //-------------------------------------------------------+
            if (hhAfterBosConfirmedFlag && postChoCH_HH > 0 && rates[i].high < postChoCH_HH)
            {
                if (rates[i].high != lastLoggedDeniedHH || TimeCurrent() - lastLoggedDeniedHHLogTime > deniedLogIntervalSeconds)
                {
                    PrintFormat("❌ [REJECTED] HH %.2f DITOLAK karena < Lebih rendah dari postCHoCH_HH %.2f | Time: %s",
                            rates[i].high, postChoCH_HH, TimeToString(rates[i].time));
                    if (ObjectFind(0, boxName) >= 0) ObjectDelete(0, boxName);
                    lastLoggedDeniedHH        = rates[i].high;
                    lastLoggedDeniedHHBarTime = rates[i].time;
                    lastLoggedDeniedHHLogTime = TimeCurrent();
                }
                continue; // Lewati update
            }
            
            //---------------------------------------------------------+
            //END MODE MENUJU TREND BULLISH----------------------------|
            //Khusus Pembentukan dan Penolakan HH----------------------|
            //---------------------------------------------------------+

            //---------------------------------------------------------+
            //MODE MENUJU TREND BEARISH--------------------------------|
            // Penolakan HH--------------------------------------------|
            //---------------------------------------------------------+

            //-----------------------------------------------------------------------------------+
            // Jika CHoCH Bearish sudah terkonfirmasi, tolak HH yang lebih rendah dari preChoCHHH| "✅"
            //-----------------------------------------------------------------------------------+
            if (chochBearish && !llAfterChochConfirmedFlag && !bosBearishConfirmedFlag) 
            {
                if (rates[i].high < lastAcceptedHH) {
                    PrintFormat("❌ [MODE 2 BEARISH] HH %.2f DITOLAK karena < preChochHH %.2f | Time: %s",
                                rates[i].high, lastAcceptedHH, TimeToString(rates[i].time));
                    // Tambahkan visual jika perlu
                    if (ObjectFind(0, boxName) >= 0) ObjectDelete(0, boxName);
                }
                continue; // Lewati update HH ini
            }

            //-----------------------------------------------------------------------------------------+
            // END: Jika CHoCH Bearish sudah terkonfirmasi, tolak HH yang lebih rendah dari preChoCHHH | "✅"
            //-----------------------------------------------------------------------------------------+


        //     PrintFormat("DEBUG: time_postChoCH_LL = %s, current time = %s", 
        //    TimeToString(time_postChoCH_LL), TimeToString(rates[i].time));

            //-------------------------------------------------------------+
            // Pencarian HH tertinggi absolut setelah CHoCH Bearish dan LL |
            // sebelum BoS Bearish                                         |
            //-------------------------------------------------------------+
            if (chochBearish && llAfterChochConfirmedFlag && !bosBearishConfirmedFlag && rates[i].time > time_choch_bearish)
            {
                PrintFormat("🔍 [MODE 2 BEARISH - DEBUG ENTRY] Memasuki MODE 2 Bearish. chochBearish=%s, llAfterChochConfirmedFlag=%s, bosBearishConfirmedFlag=%s",
                            chochBearish ? "true" : "false",
                            llAfterChochConfirmedFlag ? "true" : "false",
                            bosBearishConfirmedFlag ? "true" : "false");
                
                //-----------------------------------------------+
                // Jika belum ada pencarian HH tertinggi absolut |
                // Mulai melakukan pencarian HH tertinggi absolut|
                //-----------------------------------------------+
                if (absoluteHighestHH == -1 || rates[i].high > absoluteHighestHH)
                {
                    Print("🔍 [MODE 2 BEARISH - SEARCHING] Mencari HH tertinggi absolut...");

                    if (!absoluteHighFound)
                    {

                        //-------------------------------+
                        // Inisialisasi dengan HH pertama|
                        //-------------------------------+

                        absoluteHighestHH = rates[i].high;
                        timeAbsoluteHighestHH = rates[i].time;
                        absoluteHighFound = true;
                        lastAcceptedHH = rates[i].high;
                        PrintFormat("🎯 [MODE 2 BEARISH - ABS HIGH INIT] HH Tertinggi Absolut Awal: %.2f | Time: %s", absoluteHighestHH, TimeToString(timeAbsoluteHighestHH));
                        UpdateAcceptedLevelVisuals(lastAcceptedHH, "HH", rates[i].time);

                        //------------------------------------------+
                        //End Pencarian HH tertinggi absolut pertama|
                        //------------------------------------------+

                    }
                    else
                    {

                        //---------------------------------------------------------------------------+
                        // Jika sudah ada pencarian, periksa apakah HH baru lebih tinggi dari absolut|
                        // Jika ya, update absoluteHighestHH                                         |
                        //---------------------------------------------------------------------------+

                        if (rates[i].high > absoluteHighestHH)
                        {
                            double previousHigh = absoluteHighestHH;
                            absoluteHighestHH = rates[i].high;
                            timeAbsoluteHighestHH = rates[i].time;
                            lastAcceptedHH = rates[i].high;

                            PrintFormat("📈 [MODE 2.1 BEARISH - ABS HIGH UPDATE] HH Tertinggi Absolut Diperbarui: %.2f -> %.2f | Time: %s",
                                        previousHigh, absoluteHighestHH, TimeToString(timeAbsoluteHighestHH));
                            UpdateAcceptedLevelVisuals(lastAcceptedHH, "HH", rates[i].time);
                        }

                        //-------------------------------------------------------------------------------+
                        // Jika HH baru lebih rendah dari absolut HH, tolak dan tandai pencarian selesai |
                        //-------------------------------------------------------------------------------+

                        else if (rates[i].high < absoluteHighestHH)
                        {
                            bearishSearchCompleted = true;
                            PrintFormat("🏁 [MODE 2 BEARISH - SEARCH COMPLETE] HH tertinggi absolut ditemukan: %.2f. Pencarian dihentikan.", absoluteHighestHH);
                            PrintFormat("🔍 [MODE 2 BEARISH - FOUND LOWER] HH %.2f < HH tertinggi (%.2f) ditemukan. Menolak dan menghentikan pencarian HH tertinggi.",
                                        rates[i].high, absoluteHighestHH);
                            if (ObjectFind(0, boxName) >= 0) ObjectDelete(0, boxName);
                        }
                        else
                        {
                            PrintFormat("ℹ️ [MODE 2 BEARISH] HH %.2f sama dengan HH Tertinggi Absolut (%.2f) | Time: %s",
                                        rates[i].high, absoluteHighestHH, TimeToString(rates[i].time));
                        }
                    }
                }
                else
                {
                    // Setelah pencarian selesai
                    if (rates[i].high < absoluteHighestHH)
                    {
                        PrintFormat("❌ [MODE 2 BEARISH - POST SEARCH REJECTED] HH %.2f DITOLAK karena < HH Tertinggi Absolut (%.2f) setelah pencarian selesai | Time: %s",
                                    rates[i].high, absoluteHighestHH, TimeToString(rates[i].time));
                        if (ObjectFind(0, boxName) >= 0) ObjectDelete(0, boxName);            
                    }
                    else if (rates[i].high > absoluteHighestHH)
                    {
                        PrintFormat("⚠️ [MODE 2 BEARISH - POST SEARCH] HH %.2f > HH Tertinggi Absolut (%.2f) setelah pencarian selesai. | Time: %s",
                                    rates[i].high, absoluteHighestHH, TimeToString(rates[i].time));
                    }
                    else
                    {
                        PrintFormat("ℹ️ [MODE 2 BEARISH - POST SEARCH] HH %.2f sama dengan HH Tertinggi Absolut (%.2f) | Time: %s",
                                    rates[i].high, absoluteHighestHH, TimeToString(rates[i].time));
                    }
                }

                PrintFormat("🔧 [MODE 2 BEARISH STATE] absoluteHighestHH=%.2f | bearishSearchCompleted=%s | absoluteHighFound=%s",
                            absoluteHighestHH,
                            bearishSearchCompleted ? "true" : "false",
                            absoluteHighFound ? "true" : "false");
            }
            //------------------------------------------------------------------------------------+
            // END Pencarian HH tertinggi absolut setelah CHoCH Bearish dan LL sebelum BoS Bearish|
            //------------------------------------------------------------------------------------+

            //----------------------------------------------------------------------------
            //  --- MODE 3 BEARISH: Setelah BoS Bearish + SEBELUM LL After BoS Terkonfirmasi --
            //    Tujuan: Temukan HH tertinggi sebagai target BoS Bearish berikutnya
            //----------------------------------------------------------------------------
            if (bosBearishConfirmedFlag && isInTrendBearish && !llAfterBosConfirmedFlag)
            {
                // HH yang terbentuk SEBELUM BoS Bearish terpicu
                if (rates[i].time <= timeBoSBearish)
                {
                    double previousHH = lastAcceptedHH;
                    lastAcceptedHH = rates[i].high;
                    PrintFormat("✅ [MODE 3] Update last Accepted HH sebelum Bos dan paling tinggi (Belum Ada LL After BoS): %.2f < HH_sebelumnya (%.2f) | Time: %s",
                                lastAcceptedHH, previousHH, TimeToString(rates[i].time));
                    UpdateAcceptedLevelVisuals(lastAcceptedHH, "HH", rates[i].time);
                    continue;
                }
                
                // Update lastAcceptedHH jika HH lebih tinggi
                if (rates[i].high > lastAcceptedHH)
                {
                    double previousHH = lastAcceptedHH;
                    lastAcceptedHH = rates[i].high;
                    PrintFormat("✅ [MODE 3] Update last Accepted HH After Bos (Belum Ada LL After BoS): %.2f > HH_sebelumnya (%.2f) | Time: %s",
                                lastAcceptedHH, previousHH, TimeToString(rates[i].time));
                    UpdateAcceptedLevelVisuals(lastAcceptedHH, "HH", rates[i].time);
                    
                    // Update target BoS Bearish berikutnya
                    postChoCH_HH = rates[i].high;
                    time_postChoCH_HH = rates[i].time;
                    PrintFormat("🎯 [MODE 3] BoS Bearish Target HH set ke: %.2f @ %s", 
                                postChoCH_HH, TimeToString(time_postChoCH_HH));
                }
                else
                {
                    // Tolak HH yang lebih rendah
                    PrintFormat("❌ [MODE 3 BEARISH - REJECTED] HH %.2f DITOLAK karena <= HH terakhir (%.2f) | Time: %s",
                                rates[i].high, lastAcceptedHH, TimeToString(rates[i].time));
                    if (ObjectFind(0, boxName) >= 0) ObjectDelete(0, boxName);
                }
                continue;
            }
            //----------------------------------------------------------------------------+
            //  --- MODE 3 BEARISH: Setelah BoS Bearish + LL After BoS Terkonfirmasi ----|
            //    Tujuan: Temukan HH yang lebih rendah (Lower High - LH) untuk konfirmasi |
            //             tren bearish berkelanjutan.                                    |
            //----------------------------------------------------------------------------+
            // Syarat: Bos Bearish sudah terkonfirmasi DAN LL setelah BoS sudah terkonfirmasi.
            if (bosBearishConfirmedFlag && llAfterBosConfirmedFlag)
            {
                // --- 1. Abaikan HH yang terbentuk SEBELUM BoS Bearish terpicu ---
                if (rates[i].time <= time_postChoCH_LL) // Perubahan <= untuk memastikan inklusif
                {
                    PrintFormat("ℹ️ [MODE 3 BEARISH] HH diabaikan (terbentuk sebelum BoS Bearish terpicu @ %s): %.2f @ %s",
                                TimeToString(time_postChoCH_LL), rates[i].high, TimeToString(rates[i].time));
                    string boxNameIgnored = "zone_hh_" + IntegerToString((int)rates[i].time);
                    if (ObjectFind(0, boxNameIgnored) >= 0) ObjectDelete(0, boxNameIgnored);
                    continue;
                }

                //--------------------------------------------------------------------+
                // --- 2. Lacak HH tertinggi absolut sejak LL terakhir setelah BoS ---|
                //--------------------------------------------------------------------+

                if (rates[i].time > time_lastAcceptedLLTime)  // Asumsikan waktu LL terakhir disimpan di variabel ini
                {
                    if (absoluteHighestHH == -1 || rates[i].high > absoluteHighestHH)
                    {
                        double previousHH = absoluteHighestHH;
                        absoluteHighestHH = rates[i].high;
                        timeAbsoluteHighestHH = rates[i].time;

                        if (previousHH == -1)
                        {
                            PrintFormat("📈 [MODE 3 BEARISH] Inisialisasi HH tertinggi sejak LL terakhir (%s): %.2f @ %s",
                                        TimeToString(time_lastAcceptedLLTime), absoluteHighestHH, TimeToString(rates[i].time));
                        }
                        else
                        {
                            PrintFormat("📈 [MODE 3 BEARISH] Update HH tertinggi sejak LL terakhir (%s): %.2f -> %.2f @ %s",
                                        TimeToString(time_lastAcceptedLLTime), previousHH, absoluteHighestHH, TimeToString(rates[i].time));
                        }
                    }
                }

                // --- 3. Periksa HH baru terhadap berbagai kriteria ---
                bool   hhRejected   = false;
                string rejectReason = "";

                //------------------------------------------+
                // 3a. Periksa terhadap HH tertinggi absolut|
                // Penolakan HH lebih rendah dari absolut HH|
                //------------------------------------------+
                if (absoluteHighestHH != -1 && rates[i].time > time_lastAcceptedLLTime)
                {
                    if (rates[i].high < absoluteHighestHH)
                    {
                        hhRejected   = true;
                        rejectReason = "lebih rendah dari HH tertinggi sejak LL terakhir";
                    }
                }

                // 3b. Periksa terhadap LH terakhir (Logika SMC/ICT)
                bool isLowerHigh = false;
                if (rates[i].high < lastAcceptedHH)
                {
                    isLowerHigh = true;
                }

                // --- 4. Keputusan berdasarkan kriteria ---
                if (hhRejected)
                {
                    PrintFormat("❌ [MODE 3 BEARISH - REJECTED by Abs High] HH %.2f DITOLAK karena %s (%.2f) | Time: %s",
                                rates[i].high, rejectReason, absoluteHighestHH, TimeToString(rates[i].time));
                    string boxNameRejected = "zone_hh_" + IntegerToString((int)rates[i].time);
                    if (ObjectFind(0, boxNameRejected) >= 0) ObjectDelete(0, boxNameRejected);
                }
                else if (isLowerHigh)
                {
                    double previousHH = lastAcceptedHH;
                    lastAcceptedHH = rates[i].high;

                    PrintFormat("✅ [MODE 3 BEARISH] Init/Update LH After BoS + LL : %.2f < HH_sebelumnya (%.2f) | Time: %s",
                                lastAcceptedHH, previousHH, TimeToString(rates[i].time));

                    // Simpan nilai LH terbaru
                    hhBeforellAfterBos       = lastAcceptedHH;
                    timehhBeforellAfterBos   = rates[i].time;
                    llBeforeHHAfterBosSaved  = true;

                    PrintFormat("💾 [MODE 3 BEARISH - UPDATE] LH %.2f disimpan sebagai referensi baru (hhBeforellAfterBos) | Time: %s",
                                hhBeforellAfterBos, TimeToString(timehhBeforellAfterBos));

                    UpdateAcceptedLevelVisuals(lastAcceptedHH, "HH", rates[i].time);
                }
                else if (rates[i].high > lastAcceptedHH)
                {
                    PrintFormat("❌ [MODE 3 BEARISH - REJECTED by LH] HH %.2f DITOLAK karena lebih tinggi dari LH terakhir (%.2f) | Time: %s",
                                rates[i].high, lastAcceptedHH, TimeToString(rates[i].time));
                    string boxNameRejected = "zone_hh_" + IntegerToString((int)rates[i].time);
                    if (ObjectFind(0, boxNameRejected) >= 0) ObjectDelete(0, boxNameRejected);
                }
                else // rates[i].high == lastAcceptedHH
                {
                    PrintFormat("ℹ️ [MODE 3 BEARISH] HH %.2f sama dengan LH terakhir (%.2f) | Time: %s",
                                rates[i].high, lastAcceptedHH, TimeToString(rates[i].time));
                }

                continue;
            }

        }
        
        // --- Process Low (LL) ---
        if (isLow)
        {
            //----------------------------------------+
            // --- Basic Logging & Spam Prevention ---|
            //----------------------------------------+
            if (rates[i].time <= lastProcessedTime_LL) continue; // Skip if already processed this bar
            lastProcessedTime_LL = rates[i].time;
            if (rates[i].low == lastLoggedValidLL && rates[i].time == lastLoggedValidLLTime) continue; // Skip if already logged
            
            PrintFormat("✅ LL VALID TERBENTUK: %.2f | Time : %s", rates[i].low, TimeToString(rates[i].time));
            
            lastLoggedValidLL     = rates[i].low;   // Update spam prevention
            lastLoggedValidLLTime = rates[i].time;
            
            // --- Visual Drawing (Zona LL) ---
            datetime startTime = rates[i].time;
            datetime endTime   = startTime + PeriodSeconds() * ZoneLength;
            string   boxName   = "zone_ll_" + IntegerToString((int)rates[i].time);
            
            ObjectCreate(0, boxName, OBJ_RECTANGLE, 0, startTime, rates[i].low - 3 * _Point, endTime, rates[i].low);
            ObjectSetInteger(0, boxName, OBJPROP_COLOR, clrGreen);
            ObjectSetInteger(0, boxName, OBJPROP_BACK, true);
            
            //---------------------------------------------------------+
            //MODE MENUJU TREND BEARISH--------------------------------|
            //---------------------------------------------------------+

            //-------------------------------------------------------+
            //LOGIKA PEMBENTUKAN LL TERENDAH AFTER CHoCH BEARISH ----|
            //-------------------------------------------------------+
            if (chochBearish && !isInTrendBearish)
                {
                    //--------------------------------------------------------------------------------------+
                    // --- START: Logika Reset lastAcceptedLL setelah CHoCH Bearish dan LL valid (MODE 1) --|
                    //--------------------------------------------------------------------------------------|
                    if (!llAfterChochConfirmedFlag) 
                        {
                            // lastAcceptedHH = preChochHH;
                            lastAcceptedLL = rates[i].low;  // last AcceptedLL direset ke LL sebelum CHoCH Bullish
                            UpdateAcceptedLevelVisuals(lastAcceptedHH, "HH", rates[i].time);//Perubahan tadi di komen
                            // PrintFormat("DEBUG     : Checking HH After CHoCH Confirmed Flag trigger at HH %.2f @ %s", rates[i].high, TimeToString(rates[i].time));
                            UpdateAcceptedLevelVisuals(lastAcceptedLL, "LL", rates[i].time);
                            UpdateAcceptedLevelVisuals(lastAcceptedHH, "HH", rates[i].time); // Update visual setelah semua kondisi
                            
                            // lastAcceptedLL= -1; Perubahan
                            // lastLL_byTime = -1; Perubahan
                            postChoCH_LL              = rates[i].low; // LL terakhir setelah CHoCH Bearish
                            time_postChoCH_LL         = rates[i].time;
                            chochBearishConfirmedFlag = true;
                            llAfterChochConfirmedFlag = true;
                            bosBearishConfirmedFlag   = false;
                            llAfterBosConfirmedFlag   = false;
                            PrintFormat("✅ [MODE 1 RESET] CHoCH Bearish dan LL After CHoCH terkonfirmasi. last Accepted HH direset ke Pre ChoCH HH=%.2f | HH Baru=%.2f @ %s", 
                            preChochHH, rates[i].high, TimeToString(rates[i].time));
                            //--- Buat nama objek dan simpan untuk referensi berikutnya ---
                            previousLLBoxName = "zone_ll_" + IntegerToString((int)rates[i].time);

                            continue; // Lewati update HH ini
                        }
                    else if (rates[i].low < lastAcceptedLL) 
                        {
                            lastAcceptedLL = rates[i].low; // Update lastAcceptedLL jika lebih rendah
                            PrintFormat("✅ [MODE 1.2] Update Last Accepted LL Lebih Rendah: %.2f | Time: %s",
                                    lastAcceptedLL, TimeToString(rates[i].time));
                            // 🔥 HAPUS OBJEK RECTANGLE LL SEBELUMNYA ---
                            if (ObjectFind(0, previousLLBoxName) >= 0)
                                ObjectDelete(0, previousLLBoxName);

                            UpdateAcceptedLevelVisuals(lastAcceptedLL, "LL", rates[i].time); // Update visual setelah semua kondisi
                        }
                    else if (rates[i].low > lastAcceptedLL) 
                        {
                            PrintFormat("❌ [REJECTED] LL %.2f DITOLAK karena > Lebih Tinggi dari CHoCH+LL last Accepted LL %.2f | Time: %s",
                                    rates[i].low, lastAcceptedLL, TimeToString(rates[i].time));
                            if (ObjectFind(0, boxName) >= 0) ObjectDelete(0, boxName);
                        }
                }

            if (chochBullish && !isInTrendBullish && !hhAfterChochConfirmedFlag)
                {
                    if (rates[i].low > preChochLL)
                    {
                        PrintFormat("❌ [REJECTED] LL %.2f > preChochLL %.2f | Time: %s",
                                    rates[i].low, preChochLL, TimeToString(rates[i].time));
                        ObjectDelete(0, boxName);
                        continue;
                    }
                }

            //-----------------------------------------------------------+
            //  End Logika Penolakan LL dan Update LL pada ChoCh Bearish |
            //-----------------------------------------------------------+

            //----------------------------------------------------------------------+
            //CHoCH Bearish Confirmed, terbentuk LL valid sebagai target BoS Bullish|
            //----------------------------------------------------------------------|

            // if (chochBearish && !isInTrendBearish && !llAfterChochConfirmedFlag) // <-- PENAMBAHAN KONDISI !hhAfterChochConfirmedFlag
            // {
            //     postChoCH_LL      = rates[i].low; // <-- Sekarang hanya di-set sekali
            //     time_postChoCH_LL = rates[i].time; // <-- Sekarang hanya di-set sekali
            //     PrintFormat("🎯 [TARGET SET] BoS Bearish Target LL set ke: %.2f @ %s", postChoCH_LL, TimeToString(time_postChoCH_LL)); // Log tambahan untuk kejelasan
            // }
            // else if (rates[i].low < postChoCH_LL && postChoCH_LL > 0)
            // {
            //     postChoCH_LL      = rates[i].low; // <-- Sekarang hanya di-set sekali
            //     time_postChoCH_LL = rates[i].time; // <-- Sekarang hanya di-set sekali
            //     PrintFormat("🎯 [TARGET SET] BoS Bearish Target LL Lebih Rendah set ke: %.2f @ %s", postChoCH_LL, TimeToString(time_postChoCH_LL)); // Log tambahan untuk kejelasan
            // }
            
            if (chochBearish && !isInTrendBearish && !llAfterChochConfirmedFlag && rates[i].low < lastAcceptedLL) // <-- PENAMBAHAN KONDISI !hhAfterChochConfirmedFlag
            {
                postChoCH_LL      = rates[i].low; // <-- Sekarang hanya di-set sekali
                time_postChoCH_LL = rates[i].time; // <-- Sekarang hanya di-set sekali
                PrintFormat("🎯 [TARGET SET] BoS Bearish Target LL set ke: %.2f @ %s", postChoCH_LL, TimeToString(time_postChoCH_LL)); // Log tambahan untuk kejelasan
            } 

            if (chochBearish && isInTrendBearish && rates[i].low < lastAcceptedLL) // <-- PENAMBAHAN KONDISI !hhAfterChochConfirmedFlag
            {
                postChoCH_LL      = rates[i].low; // <-- Sekarang hanya di-set sekali
                time_postChoCH_LL = rates[i].time; // <-- Sekarang hanya di-set sekali
                PrintFormat("🎯 [TARGET SET] BoS Bearish Target LL set ke: %.2f @ %s", postChoCH_LL, TimeToString(time_postChoCH_LL)); // Log tambahan untuk kejelasan
            }

            //-----------------------------+
            //End Logika Target Bos Bearish|
            //-----------------------------+

            //----------------------------------------------------------------------+
            //Bos Bearish Confirmed, terbentuk LL valid sebagai target BoS Bearish|
            //----------------------------------------------------------------------+
            if (bosBearishConfirmedFlag && isInTrendBearish)
            {
                //-------------------------------------------------------------------------------+
                // Dalam tren bearish, hanya LL yang lebih rendah setelah Bos valid|
                //-------------------------------------------------------------------------------+
                if (rates[i].low < lastAcceptedLL) // <-- Pembaruan utama dalam tren bullish
                {
                    lastAcceptedLL = rates[i].low;
                    PrintFormat("✅ [MODE 2.2]Update last Accepted LL After Bos: %s | Time: %s", DoubleToString(lastAcceptedLL, _Digits), TimeToString(rates[i].time));
                    UpdateAcceptedLevelVisuals(lastAcceptedLL, "LL", rates[i].time); // Update visual setelah semua kondisi
                    llAfterBosConfirmedFlag = true;          // Tandai HH setelah BoS bullish terkonfirmasi
                    //timeLLAfterBosConfirmed = TimeCurrent(); // Simpan waktu konfirmasi
                    postChoCH_LL            = rates[i].low;  // Update postChoCH_HH
                    PrintFormat("✅ Post CHoCH LL: %s | Time: %s", DoubleToString(postChoCH_LL, _Digits), TimeToString(rates[i].time));
                    PrintFormat("✅ LL After BoS Confirmed: %s | Time: %s", DoubleToString(lastAcceptedLL, _Digits), TimeToString(rates[i].time));
                    //highestLLSinceLastHHAfterBos = -1; // Reset LL tertinggi sejak HH terakhir setelah BoS
                    //time_lastLLAfterBos = rates[i].time; // Simpan waktu LL terakhir setelah BoS
                    //PrintFormat("🔄 [LL After BoS Confirmed] Reset pencarian HH tertinggi. Waktu referensi LL: %s",
                    //        TimeToString(time_lastLLAfterBos));
                }
                else if (rates[i].low < lastAcceptedLL) 
                {
                    lastAcceptedLL = rates[i].low; // Update lastAcceptedLL jika lebih rendah
                    PrintFormat("✅ [MODE 1.2] Update Last Accepted LL Lebih Rendah: %.2f | Time: %s",
                            lastAcceptedLL, TimeToString(rates[i].time));
                    // 🔥 HAPUS OBJEK RECTANGLE LL SEBELUMNYA ---
                    if (ObjectFind(0, previousLLBoxName) >= 0)
                        ObjectDelete(0, previousLLBoxName);

                    UpdateAcceptedLevelVisuals(lastAcceptedLL, "LL", rates[i].time); // Update visual setelah semua kondisi
                }
                else if (rates[i].low > lastAcceptedLL) 
                {
                    PrintFormat("❌ [REJECTED] LL %.2f DITOLAK karena > Lebih Tinggi dari BoS+LL last Accepted LL %.2f | Time: %s",
                            rates[i].low, lastAcceptedLL, TimeToString(rates[i].time));
                    if (ObjectFind(0, boxName) >= 0) ObjectDelete(0, boxName);
                }
            }  

            //----------------------------------------------------------------------+
            //END MODE MENUJU TREND BEARISH-----------------------------------------|
            //----------------------------------------------------------------------+

            //----------------------------------------------------------------------+
            //MODE MENUJU TREND BULLISH---------------------------------------------|
            //----------------------------------------------------------------------+
            //----------------------------------------------------------------------------+
            // --- Jika BELUM terjadi CHoCH Bullish + HH, cari LL terendah (pre-CHoCH) ---|
            // Dan Penolakan LL jika lebih tinggi dari lastAcceptedLL (pre-CHoCH) --------|
            //----------------------------------------------------------------------------+
            if (!hhAfterChochConfirmedFlag && !chochBullish && !llAfterChochConfirmedFlag && !chochBearish) 
            {
                if (lastAcceptedLL == -1 || rates[i].low < lastAcceptedLL) 
                {
                    // ✅ Update LL jika lebih rendah
                    lastAcceptedLL = rates[i].low;
                    Print("✅ [MODE 1] Update LL (Pre-CHoCH): ", lastAcceptedLL);
                    UpdateAcceptedLevelVisuals(lastAcceptedLL, "LL", rates[i].time);
                }
            //---------------------------------------------------------------+
            // Sebelum Choch Bearish dan HH After CHoCH----------------------+
            // Penolakan LL jika lebih tinggi dari lastAcceptedLL (pre-CHoCH)|
            //---------------------------------------------------------------+
                else
                {
                    // ❌ Tolak LL yang lebih tinggi
                    Print("❌ [MODE 1 REJECTED] LL lebih tinggi dari PreChoCh LL: = ", lastAcceptedLL);
                    if (ObjectFind(0, boxName) >= 0) ObjectDelete(0, boxName);
                    lastLoggedDeniedLL = rates[i].low;
                }
                continue; // Stop proses di baris ini
            }
            //----------------------------------------------------------------------+
            // Jika sudah ada CHoCH Bullish ----------------------------------------+ 
            // Penolakan LL yang lebih tinggi dari lastAcceptedLL (pre-CHoCH)-------|
            //----------------------------------------------------------------------+
            if (!hhAfterChochConfirmedFlag && chochBullish && !llAfterChochConfirmedFlag && !chochBearish) 
            {
                if (lastAcceptedLL == -1 || rates[i].low < lastAcceptedLL) 
                {
                    // ❌ Tolak LL yang lebih tinggi
                    Print("❌ [MODE 1 REJECTED] LL lebih tinggi dari PreChoCh LL: = ", lastAcceptedLL);
                    if (ObjectFind(0, boxName) >= 0) ObjectDelete(0, boxName);
                    lastLoggedDeniedLL = rates[i].low;
                }
                continue; // Stop proses di baris ini
            }

            // if (chochBullish && hhAfterChochConfirmedFlag && bosBullishConfirmedFlag)
            // {
            //     // Jika sudah ada CHoCH Bullish dan HH After CHoCH, tolak LL yang lebih tinggi dari lastAcceptedLL
            //     if (rates[i].low > lastAcceptedLL) 
            //     {
            //         PrintFormat("❌ [REJECTED] LL %.2f DITOLAK karena > Lebih Tinggi dari CHoCH+LL last Accepted LL %.2f | Time: %s",
            //                 rates[i].low, lastAcceptedLL, TimeToString(rates[i].time));
            //         if (ObjectFind(0, boxName) >= 0) ObjectDelete(0, boxName);
            //         continue; // Stop proses di baris ini
            //     }
            // }

            //-------------------------------------------------------------+
            // Setelah CHoCH dan HH, cari LL terendah sebelum BoS Bullish  |
            //-------------------------------------------------------------+
            if ((chochBullish || hhAfterChochConfirmedFlag) && 
    (!bosBullishConfirmedFlag || rates[i].time < timeBoSBullish)) // Tambahkan !bosBullishConfirmedFlag
            {
                PrintFormat("🔍 [MODE 2 - DEBUG ENTRY] Memasuki MODE 2. chochBullish=%s, hhAfterChochConfirmedFlag=%s, bosBullishConfirmedFlag=%s",
                            chochBullish ? "true" : "false",
                            hhAfterChochConfirmedFlag ? "true" : "false",
                            bosBullishConfirmedFlag ? "true" : "false");
                //--- Reset pencarian jika kondisi awal berubah (opsional, untuk keamanan) ---
                // Biasanya static variables akan reset otomatis jika blok ini tidak dijalankan,
                // tapi bisa ditambahkan reset manual jika diperlukan.

                //--- Fase Pencarian LL Terendah Absolut ---
                if (!searchCompleted)
                {
                    PrintFormat("🔍 [MODE 2 - SEARCHING] Mencari LL terendah absolut...");

                    if (!absoluteLowFound)
                    {
                        //--- Inisialisasi dengan LL pertama ---
                        absoluteLowestLL = rates[i].low;
                        timeAbsoluteLowestLL = rates[i].time;
                        absoluteLowFound = true;
                        lastAcceptedLL = rates[i].low; // Update lastAcceptedLL awal
                        //--- Buat nama objek dan simpan untuk referensi berikutnya ---
                            previousLLBoxName = "zone_ll_" + IntegerToString((int)rates[i].time);

                        PrintFormat("🎯 [MODE 2 - ABS LOW INIT] LL Terendah Absolut Awal: %.2f | Time: %s", absoluteLowestLL, TimeToString(timeAbsoluteLowestLL));
                        UpdateAcceptedLevelVisuals(lastAcceptedLL, "LL", rates[i].time);
                    }
                    else
                    {
                        //--- Perbarui jika menemukan LL lebih rendah ---
                        if (rates[i].low < absoluteLowestLL)
                        {
                            // 🔥 HAPUS OBJEK RECTANGLE LL SEBELUMNYA ---
                            if (ObjectFind(0, previousLLBoxName) >= 0)
                                ObjectDelete(0, previousLLBoxName);

                            double previousLow = absoluteLowestLL;
                            absoluteLowestLL = rates[i].low;
                            timeAbsoluteLowestLL = rates[i].time;
                            lastAcceptedLL = rates[i].low; // Update lastAcceptedLL

                            PrintFormat("📉 [MODE 2.1 - ABS LOW UPDATE] LL Terendah Absolut Diperbarui: %.2f -> %.2f | Time: %s",
                                        previousLow, absoluteLowestLL, TimeToString(timeAbsoluteLowestLL));
                            UpdateAcceptedLevelVisuals(lastAcceptedLL, "LL", rates[i].time);
                        }
                        //--- Jika menemukan LL lebih tinggi dari terendah, hentikan pencarian ---
                        else if (rates[i].low > absoluteLowestLL)
                        {
                             // LL yang lebih tinggi ditemukan setelah LL terendah.
                             // Hentikan pencarian untuk LL terendah.
                             searchCompleted = true;
                             // lastAcceptedLL tetap pada nilai terendah absolut.
                             PrintFormat("🏁 [MODE 2 - SEARCH COMPLETE] LL terendah absolut ditemukan: %.2f. Pencarian dihentikan.", absoluteLowestLL);
                             PrintFormat("🔍 [MODE 2 - FOUND HIGHER] LL %.2f > LL terendah (%.2f) ditemukan. Menolak dan menghentikan pencarian LL terendah.", rates[i].low, absoluteLowestLL);
                             // Tidak perlu mengupdate lastAcceptedLL lagi di sini karena sudah diset ke nilai terendah.
                             // Bisa juga memilih untuk mengupdate lastAcceptedLL ke nilai ini jika diinginkan sebagai HL awal,
                             // tapi berdasarkan deskripsi, nampaknya lastAcceptedLL tetap pada nilai terendah absolut.
                             // Untuk sekarang, kita tolak LL ini.
                             string boxNameRejected = "zone_ll_" + IntegerToString((int)rates[i].time);
                             if (ObjectFind(0, boxNameRejected) >= 0) ObjectDelete(0, boxNameRejected);
                        }
                        else // rates[i].low == absoluteLowestLL
                        {
                             PrintFormat("ℹ️ [MODE 2] LL %.2f sama dengan LL Terendah Absolut (%.2f) | Time: %s",
                                         rates[i].low, absoluteLowestLL, TimeToString(rates[i].time));
                             // Bisa diputuskan apakah dianggap sebagai pembaruan atau tidak.
                             // Untuk konsistensi, biarkan saja.
                        }
                    }
                }
                else
                {
                    //--- Fase Setelah Pencarian Selesai ---
                    // Pencarian LL terendah absolut sudah dihentikan karena ditemukan LL lebih tinggi.
                    // Semua LL baru yang muncul di sini harus dibandingkan dengan LL terendah absolut.
                    // Namun, deskripsi Anda tidak jelas apakah LL ini diterima sebagai HL berikutnya atau ditolak.
                    // Untuk sekarang, kita asumsikan LL baru yang lebih tinggi dari absolutLowestLL
                    // ditolak dalam konteks mencari LL terendah, atau diterima sebagai HL potensial (tergantung logika MODE 3 nantinya).
                    // Untuk memenuhi permintaan "TOLAK", kita tolak.
                    if (rates[i].low > absoluteLowestLL)
                    {
                         PrintFormat("❌ [MODE 2 - POST SEARCH REJECTED] LL %.2f DITOLAK karena > LL Terendah Absolut (%.2f) setelah pencarian selesai | Time: %s",
                                     rates[i].low, absoluteLowestLL, TimeToString(rates[i].time));
                         string boxNameRejected = "zone_ll_" + IntegerToString((int)rates[i].time);
                         if (ObjectFind(0, boxNameRejected) >= 0) ObjectDelete(0, boxNameRejected);
                    }
                    else if (rates[i].low < absoluteLowestLL)
                    {
                        // Ini seharusnya tidak terjadi jika logika di atas benar, karena absoluteLowestLL adalah yang terendah.
                        // Tapi jika terjadi (misal karena market data baru), mungkin perlu dipertimbangkan.
                        // Untuk sekarang, abaikan atau log.
                         PrintFormat("⚠️ [MODE 2 - POST SEARCH] LL %.2f < LL Terendah Absolut (%.2f) setelah pencarian selesai. Kemungkinan data baru atau error. | Time: %s",
                                     rates[i].low, absoluteLowestLL, TimeToString(rates[i].time));
                    }
                    else // rates[i].low == absoluteLowestLL
                    {
                         PrintFormat("ℹ️ [MODE 2 - POST SEARCH] LL %.2f sama dengan LL Terendah Absolut (%.2f) | Time: %s",
                                     rates[i].low, absoluteLowestLL, TimeToString(rates[i].time));
                    }
                }
            PrintFormat("🔧 [MODE 2 STATE] absoluteLowestLL=%.2f | searchCompleted=%s | absoluteLowFound=%s",
                        absoluteLowestLL,
                        searchCompleted ? "true" : "false",
                        absoluteLowFound ? "true" : "false"
                       );
                
            }
            // Jika hhAfterChochConfirmedFlag=false atau bosBullishConfirmedFlag=true, blok ini tidak dijalankan.
            // Ini memastikan logika hanya berjalan saat kondisi tepat.

            
            //----------------------------------------------------------------------------+
            //  --- MODE 3: Setelah BoS Bullish + HH After BoS Terkonfirmasi ---          |
            //    Tujuan: Temukan LL yang lebih tinggi (Higher Low - HL) untuk konfirmasi |
            //             tren bullish berkelanjutan.                                    |
            //----------------------------------------------------------------------------+
            // Syarat: Bos Bullish sudah terkonfirmasi DAN HH setelah BoS sudah terkonfirmasi.
            if (bosBullishConfirmedFlag && isInTrendBullish && rates[i].low > absoluteLowestLL)
                {
                     PrintFormat("❌ [MODE 3 - REJECTED] LL %.2f DITOLAK karena > LL Terendah Absolut (%.2f) | Time: %s",
                                     rates[i].low, absoluteLowestLL, TimeToString(rates[i].time));
                         string boxNameRejected = "zone_ll_" + IntegerToString((int)rates[i].time);
                         if (ObjectFind(0, boxNameRejected) >= 0) ObjectDelete(0, boxNameRejected);
                }
            if (bosBullishConfirmedFlag && hhAfterBosConfirmedFlag)
            {
                // --- 1. Abaikan LL yang terbentuk SEBELUM BoS Bullish terpicu ---
                // Ini mencegah LL lama mempengaruhi tren baru.
                // Asumsi: time_postChoCH_HH menyimpan waktu saat BoS Bullish terpicu.
                if (rates[i].time <= time_postChoCH_HH) // Perubahan <= untuk memastikan inklusif
                {
                    PrintFormat("ℹ️ [MODE 3] LL diabaikan (terbentuk sebelum BoS Bullish terpicu @ %s): %.2f @ %s",
                                TimeToString(time_postChoCH_HH), rates[i].low, TimeToString(rates[i].time));
                    string boxNameIgnored = "zone_ll_" + IntegerToString((int)rates[i].time);
                    if (ObjectFind(0, boxNameIgnored) >= 0) ObjectDelete(0, boxNameIgnored); // Hapus visual jika ada
                    continue; // Lanjut ke iterasi berikutnya, jangan proses LL ini
                }
                
                // --- 2. Lacak LL terendah absolut sejak HH terakhir setelah BoS ---
                // Ini hanya berlaku untuk LL yang terbentuk SETELAH HH terakhir setelah BoS.
                if (rates[i].time > time_lastHHAfterBos)
                {
                    if (lowestLLSinceLastHHAfterBos == -1 || rates[i].low < lowestLLSinceLastHHAfterBos)
                    {
                        double previousLowest              = lowestLLSinceLastHHAfterBos;
                        lowestLLSinceLastHHAfterBos = rates[i].low;
                        
                        if(previousLowest == -1)
                        {
                            PrintFormat("📉 [MODE 3] Inisialisasi LL terendah sejak HH terakhir (%s): %.2f @ %s",
                                        TimeToString(time_lastHHAfterBos), lowestLLSinceLastHHAfterBos, TimeToString(rates[i].time));
                        } 
                        else 
                        {
                            PrintFormat("📉 [MODE 3] Update LL terendah sejak HH terakhir (%s): %.2f -> %.2f @ %s",
                                        TimeToString(time_lastHHAfterBos), previousLowest, lowestLLSinceLastHHAfterBos, TimeToString(rates[i].time));
                        }
                        // Opsional: Update visual untuk lowestLLSinceLastHHAfterBos jika diperlukan
                        // UpdateAcceptedLevelVisuals(lowestLLSinceLastHHAfterBos, "LowestLL", rates[i].time);
                    }
                }
                
                // --- 3. Periksa LL baru terhadap berbagai kriteria ---
                bool   llRejected   = false;
                string rejectReason = "";
                
                // --- 3a. Periksa terhadap LL terendah absolut ---
                if (lowestLLSinceLastHHAfterBos != -1 && rates[i].time > time_lastHHAfterBos)
                {
                    if (rates[i].low > lowestLLSinceLastHHAfterBos)
                    {
                        llRejected   = true;
                        rejectReason = "lebih tinggi dari LL terendah absolut sejak HH terakhir";
                        // Catatan: LL ini mungkin masih merupakan HL terhadap lastAcceptedLL,
                        // tetapi melanggar aturan LL terendah absolut Anda.
                    }
                }
                
                // --- 3b. Periksa terhadap HL terakhir (Logika SMC/ICT Standar) ---
                bool isHigherLow = false;
                if (rates[i].low > lastAcceptedLL)
                {
                    isHigherLow = true;
                }
                
                // --- 4. Keputusan berdasarkan kriteria ---
                if (llRejected)
                {
                    // ❌ LL baru ditolak karena melanggar aturan LL terendah absolut
                    PrintFormat("❌ [MODE 3 - REJECTED by Abs Low] LL %.2f DITOLAK karena %s (%.2f) | Time: %s",
                                rates[i].low, rejectReason, lowestLLSinceLastHHAfterBos, TimeToString(rates[i].time));
                    string boxNameRejected = "zone_ll_" + IntegerToString((int)rates[i].time);
                    if (ObjectFind(0, boxNameRejected) >= 0) ObjectDelete(0, boxNameRejected);
                }
                else if (isHigherLow)
                {
                    // ✅ Higher Low (HL) ditemukan: LL baru lebih tinggi dari LL terakhir (lastAcceptedLL)
                    // Terima sebagai HL untuk tren, meskipun mungkin bukan LL terendah absolut saat ini.
                    double previousLL     = lastAcceptedLL;  // Simpan nilai lama untuk log
                    lastAcceptedLL = rates[i].low;    // Perbarui lastAcceptedLL ke nilai HL yang baru
                    
                    PrintFormat("✅ [MODE 3] Init/Update HL After BoS + HH : %.2f > LL_sebelumnya (%.2f) | Time: %s",
                                lastAcceptedLL, previousLL, TimeToString(rates[i].time));
                    
                    // --- PERBAIKAN UTAMA ---
                    // Simpan nilai HL yang baru saja diterima sebagai referensi untuk LL berikutnya
                    // dalam tren bullish ini.
                    llBeforeHHAfterBos      = lastAcceptedLL;  // llBeforeHHAfterBos menjadi HL terbaru
                    timeLLBeforeHHAfterBos  = rates[i].time;   // Simpan waktu HL terbaru
                    llBeforeHHAfterBosSaved = true;            // Tandai bahwa referensi sudah disimpan/diperbarui
                    
                    PrintFormat("💾 [MODE 3 - UPDATE] HL %.2f disimpan sebagai referensi baru (llBeforeHHAfterBos) | Time: %s",
                                llBeforeHHAfterBos, TimeToString(timeLLBeforeHHAfterBos));
                    // --- AKHIR PERBAIKAN ---
                    
                    PrintFormat("bosBullishConfirmedFlag: %s | hhAfterBosConfirmedFlag: %s",
                                bosBullishConfirmedFlag ? "True": "False",
                                hhAfterBosConfirmedFlag ? "True": "False");
                    UpdateAcceptedLevelVisuals(lastAcceptedLL, "LL", rates[i].time); // Update visualisasi
                }
                else if (rates[i].low < lastAcceptedLL)
                {
                    // ❌ Lower Low (LL) ditemukan: LL baru lebih rendah dari HL terakhir (lastAcceptedLL)
                    // Ini menunjukkan potensi kelemahan tren bullish atau koreksi.
                    PrintFormat("❌ [MODE 3 - REJECTED by HL] LL %.2f DITOLAK karena lebih rendah dari HL terakhir (%.2f) | Time: %s",
                                rates[i].low, lastAcceptedLL, TimeToString(rates[i].time));
                    string boxNameRejected = "zone_ll_" + IntegerToString((int)rates[i].time);
                    if (ObjectFind(0, boxNameRejected) >= 0) ObjectDelete(0, boxNameRejected);
                }
                else // rates[i].low == lastAcceptedLL
                {
                    // LL sama dengan LL terakhir (kasus langka, mungkin abaikan atau log).
                    PrintFormat("ℹ️ [MODE 3] LL %.2f sama dengan HL terakhir (%.2f) | Time: %s",
                                rates[i].low, lastAcceptedLL, TimeToString(rates[i].time));
                }
                // Stop proses LL di baris ini untuk iterasi ini.
                continue;
            }
            //----------------------------------------------------------------------------+
            // --- AKHIR MODE 3 ---
            //----------------------------------------------------------------------------+
            //--------------------------------------------------------------------+
            //END MENUJU TREND BULLISH--------------------------------------------|
            //--------------------------------------------------------------------+
        } // End of LL processing
    } // End of Low (LL) processing
    
    //--------------+
    // CHoCH Bullish|
    //--------------+
   
    if (!chochBullish && !isInTrendBullish &&
        (lastAcceptedHH > 0 && rates[1].close > lastAcceptedHH + 50 * _Point))
        {
                double   tempHH         = lastAcceptedHH;
                datetime tempHHTime     = lastLoggedValidHHTime;
                         preChochLL     = lastAcceptedLL;
                UpdateAcceptedLevelVisuals(preChochLL, "LL", rates[0].time); // Update visualisasi
                        //  lastAcceptedLL = -1;                     // Reset lastAcceptedLL untuk mode 1
                        //  lastAcceptedHH = -1;
                Print("🔔🔔🔔 === ⚡⚡⚡ [CHoCH BULLISH TRIGGERED] ⚡⚡⚡ === 🔔🔔🔔");
                Print("📈 Close Breaks HH (Target): ", DoubleToString(lastAcceptedHH, _Digits), " → CHoCH Bullish Confirmed! ", TimeToString(rates[1].time));
                PrintFormat("✅ [MODE 1 RESET] CHoCH Bullish terkonfirmasi. last Accepted LL direset ke preChochLL: %.2f @ %s",
                                     preChochLL, TimeToString(rates[1].time));
                //=== Gambar garis CHoCH dari HH sebelum break ke candle ===//
                string chochName = "CHoCH_Bull_" + IntegerToString((int)tempHHTime);
                ObjectDelete(0, chochName);
                ObjectCreate(0, chochName, OBJ_TREND, 0, tempHHTime, tempHH, rates[1].time, tempHH);
                ObjectSetInteger(0, chochName, OBJPROP_COLOR, clrGold);
                ObjectSetInteger(0, chochName, OBJPROP_WIDTH, 1);
                ObjectSetInteger(0, chochName, OBJPROP_STYLE, STYLE_SOLID);
                ObjectSetInteger(0, chochName, OBJPROP_BACK, true);
                //=== Label CHoCH di tengah garis ===//
                string   chochLabel = chochName + "_label";
                int      shift1     = iBarShift(_Symbol, PERIOD_M15, tempHHTime, false);
                int      shift2     = iBarShift(_Symbol, PERIOD_M15, rates[1].time, false);
                int      midShift   = (shift1 + shift2) / 2;
                datetime midTime    = iTime(_Symbol, PERIOD_M15, midShift);
                ObjectDelete(0, chochLabel);
                ObjectCreate(0, chochLabel, OBJ_TEXT, 0, midTime, tempHH + 6 * _Point);
                ObjectSetInteger(0, chochLabel, OBJPROP_COLOR, clrGold);
                ObjectSetInteger(0, chochLabel, OBJPROP_FONTSIZE, 10);
                ObjectSetInteger(0, chochLabel, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER); // 🔥 Kunci utama
                ObjectSetString(0, chochLabel, OBJPROP_TEXT, "CHoCH");
                chochBullish              = true;
                hhAfterChochConfirmedFlag = false; // Reset flag HH setelah CHoCH (Bullish)
                isInTrendBearish          = false;
                chochBearish              = false;
                chochBearishConfirmedFlag = false;
                llAfterChochConfirmedFlag = false;
                bosBearishConfirmedFlag   = false;
                llAfterBosConfirmedFlag   = false;
                bosBullishJustLogged      = false;  // 🔓 Reset log untuk trigger BoS baru
                time_postChoCH_HH         = -1;     // Reset time_postChoCH_HH
                time_postChoCH_LL         = -1;     // Reset time_postChoCH_LL
                time_choch_bullish        = rates[1].time;
                time_choch_bearish        = -1;
                timeBoSBearish            = -1;
                postChoCH_LL              = -1;
                preChochHH                = -1; // Simpan HH sebelum CHoCH Bullish
                ResetMode2(); // Reset variabel MODE 2                   
                Print("🔄 [CHoCH RESET] Variabel MODE 2 di-reset untuk siklus baru.");
                UpdateAcceptedLevelVisuals(-1, "LL", rates[1].time);
        }

    //--------------+
    // CHoCH Bearish|
    //--------------+
    if  (!chochBearish && !isInTrendBearish && // Hanya trigger jika belum dalam keadaan CHoCH/ tren bearish
        (lastAcceptedLL > 0 && rates[1].close < lastAcceptedLL - 5 * _Point)) // Cek apakah close menembus LL terakhir (dengan sedikit buffer)
        {
            double   tempLL         = lastAcceptedLL;        // Simpan nilai LL yang ditembus
            datetime tempLLTime     = lastLoggedValidLLTime; // Simpan waktu LL yang ditembus
                     preChochHH     = lastAcceptedHH;        // Simpan HH sebelum CHoCH Bearish (untuk referensi MODE 2)
            UpdateAcceptedLevelVisuals(preChochHH, "HH", rates[1].time); // Update visualisasi HH sebelum CHoCH Bearish
                  // lastAcceptedHH = -1;                    // Reset lastAcceptedHH untuk mode transisi
                    //  lastAcceptedLL = -1;                    // Reset lastAcceptedLL untuk mode transisi (opsional, tergantung logika MODE 1 bearish)
            //--- Logging ---
            Print("🔔🔔🔔 === ⚡⚡⚡ [CHoCH BEARISH TRIGGERED] ⚡⚡⚡ === 🔔🔔🔔");
            PrintFormat("📉 Close Breaks LL (Target): %.5f → CHoCH Bearish Confirmed! @ %s",
                        lastAcceptedLL, TimeToString(rates[1].time));
            PrintFormat("✅ [MODE X RESET] CHoCH Bearish terkonfirmasi. last Accepted HH direset ke preChochHH: %.5f @ %s",
                        preChochHH, TimeToString(rates[1].time)); // Log reset HH jika digunakan

            //=== Gambar garis CHoCH Bearish dari LL sebelum break ke candle break ===//
            string chochName = "CHoCH_Bear_" + IntegerToString((int)tempLLTime); // Gunakan nama unik berdasarkan waktu LL
            ObjectDelete(0, chochName); // Hapus objek lama dengan nama yang sama jika ada
            // Buat garis tren dari waktu dan level LL yang ditembus ke waktu candle saat ini (rates[1])
            ObjectCreate(0, chochName, OBJ_TREND, 0, tempLLTime, tempLL, rates[1].time, tempLL);
            ObjectSetInteger(0, chochName, OBJPROP_COLOR, clrOrangeRed); // Warna merah oranye untuk bearish
            ObjectSetInteger(0, chochName, OBJPROP_WIDTH, 1);
            ObjectSetInteger(0, chochName, OBJPROP_STYLE, STYLE_SOLID);
            ObjectSetInteger(0, chochName, OBJPROP_BACK, true);

            //=== Label CHoCH Bearish di tengah garis ===//
            string   chochLabel = chochName + "_label";

            // Hitung waktu tengah antara dua titik
            datetime midTime = (tempLLTime + rates[1].time) / 2;

            // Hapus label lama jika ada
            ObjectDelete(0, chochLabel);

            // Buat label teks di tengah garis, sedikit di bawah garis (karena arah bearish)
            ObjectCreate(0, chochLabel, OBJ_TEXT, 0, midTime, tempLL - 6 * _Point); // Posisi sedikit di bawah (-6 * _Point)
            ObjectSetInteger(0, chochLabel, OBJPROP_COLOR, clrOrangeRed);
            ObjectSetInteger(0, chochLabel, OBJPROP_FONTSIZE, 10);
            ObjectSetInteger(0, chochLabel, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER); // Jangkar ke kiri atas teks
            ObjectSetString(0, chochLabel, OBJPROP_TEXT, "CHoCH");
            //--- Reset Flag dan Variabel terkait tren ---
            chochBearish              = true;        // Tandai CHoCH Bearish terpicu
            isInTrendBullish          = false;       // Keluar dari tren Bullish jika ada
            chochBullish              = false; 
            hhAfterChochConfirmedFlag = false;       // Reset flag HH setelah CHoCH (Bullish)
            chochBullishConfirmedFlag = false;       // Reset flag konfirmasi CHoCH Bullish
            llAfterChochConfirmedFlag = false;       // Reset flag LL setelah CHoCH (Bearish)
            bosBullishConfirmedFlag   = false;       // Reset flag BoS Bullish
            hhAfterBosConfirmedFlag   = false; 
            postChoCH_HH              = -1;      // Reset flag HH setelah BoS Bullish
            time_postChoCH_HH         = -1;
            // bosBearishJustLogged      = false;       // 🔓 Reset log untuk trigger BoS baru (jika digunakan untuk Bearish)
            time_postChoCH_LL         = -1;          // Reset waktu post-CHoCH LL (jika digunakan)
            postChoCH_LL              = -1;          // Reset nilai post-CHoCH LL (jika digunakan)
            time_choch_bearish        = rates[1].time;  // SIMPAN WAKTU CHoCH
            time_choch_bullish        = -1;
            timeBoSBullish            = -1;
            preChochLL                = -1; // Simpan LL sebelum CHoCH Bearish (untuk referensi MODE 2)
            ResetMode2Bearish(); // Reset variabel MODE 2 untuk siklus baru
            Print("🔄 [CHoCH RESET] Variabel MODE 2 di-reset");
            // Optional: Hapus visual LL lama jika diperlukan
            // UpdateAcceptedLevelVisuals(-1, "HH", rates[1].time); // Contoh jika ingin menghapus garis HH
            // UpdateAcceptedLevelVisuals(-1, "LL", rates[1].time); // Contoh jika ingin menghapus garis LL sementara

            //--- Reset flag lain yang relevan jika perlu ---
            // Misalnya, jika ada logika MODE 1/2/3 untuk bearish, mungkin perlu reset variabel spesifik di sini
            // llBeforeLLAfterBosSaved = false; // Contoh reset kunci MODE 3 Bearish jika ada
        }


    //------------+
    // BoS Bullish|
    //------------+
    // PrintFormat("🧐 Cek Candle BoS Bullish : Time=%s | Open=%.2f | Close=%.2f | Low=%.2f | lastAcceptedHH=%.2f | TargetBreak=%.2f", 
    //         TimeToString(rates[1].time), rates[1].open, rates[1].close, rates[1].low, postChoCH_HH, postChoCH_HH + 50 * _Point);
    if (
    postChoCH_HH > 0 && time_postChoCH_HH > 0 && // ⛔ Tambahkan pengecekan ini!
    (
        (chochBullish && !isInTrendBullish && rates[1].close > postChoCH_HH + 50 * _Point) ||
        (bosBullishConfirmedFlag && hhAfterBosConfirmedFlag &&
         isInTrendBullish > 0 && rates[1].close > postChoCH_HH + 50 * _Point)
    ))
    {
        string bosLineName  = "BoS_Bull_" + IntegerToString((int)time_postChoCH_HH);
        string bosLabelName = bosLineName + "_label";
        //=== Gambar garis dari postChoCH_HH ke candle dan label di tengah ===//
        string bosName = "BoS_Bull_" + IntegerToString((int)time_postChoCH_HH);
        ObjectDelete(0, bosName);
        ObjectCreate(0, bosName, OBJ_TREND, 0, time_postChoCH_HH, postChoCH_HH, rates[1].time, postChoCH_HH);
        ObjectSetInteger(0, bosName, OBJPROP_COLOR, clrDeepSkyBlue);
        ObjectSetInteger(0, bosName, OBJPROP_WIDTH, 1);
        ObjectSetInteger(0, bosName, OBJPROP_STYLE, STYLE_SOLID);
        ObjectSetInteger(0, bosName, OBJPROP_BACK, true);
        //=== Label BoS di tengah garis ===//
        string   bosLabel = bosName + "_label";
        datetime midTime  = (time_postChoCH_HH + rates[1].time) / 2;
        ObjectDelete(0, bosLabel);
        ObjectCreate(0, bosLabel, OBJ_TEXT, 0, midTime, postChoCH_HH - 7 * _Point);
        ObjectSetInteger(0, bosLabel, OBJPROP_COLOR, clrDeepSkyBlue);
        ObjectSetInteger(0, bosLabel, OBJPROP_FONTSIZE, 10);
        ObjectSetInteger(0, bosLabel, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER); // 🔥 Kunci utama
        ObjectSetString(0, bosLabel, OBJPROP_TEXT, "BoS");
        if (!bosBullishJustLogged) // Cek apakah sudah pernah dilog
            {
            Print("🚀🚀🚀 === 💥💥💥 [BoS BULLISH TRIGGERED] 💥💥💥 === 🚀🚀🚀");
            Print("📊 Close > postChoCH_HH: ", postChoCH_HH, " → BOS Bullish Confirmed! ", TimeToString(rates[1].time));
            lastBoSTimeLogged = rates[1].time;  // Simpan waktu terakhir yang sudah dilog
            }
        // chochBullish            = false;
        postChoCH_HH            = -1;
        time_postChoCH_HH       = 0;      // Reset waktu post-CHoCH HH
        bosBullishConfirmedFlag = true;
        isInTrendBullish        = true;
        preChochLL              = -1;
        // Di blok BoS Bullish:
        timeBoSBullish = rates[1].time; // Disimpan saat BoS terpicu
        // ... di dalam blok kondisi BoS Bullish ...
        if (bosBullishConfirmedFlag)
        {
            // ... kode lain ...
            PrintFormat("🔍 [DEBUG BoS %d] lastAcceptedLL saat ini: %.2f", bos_counter, lastAcceptedLL); // Tambahkan counter BoS jika perlu
            llBeforeHHAfterBos      = lastAcceptedLL;  // Simpan LL terakhir sebagai referensi
            timeLLBeforeHHAfterBos  = rates[1].time;   // Waktu saat BoS terkonfirmasi (atau TimeCurrent())
            llBeforeHHAfterBosSaved = true;            // Tandai bahwa nilai sudah disimpan untuk siklus ini
            PrintFormat("💾 [PERBAIKAN BoS Confirmed] LL referensi untuk Mode 3 disimpan: %.2f @ %s", llBeforeHHAfterBos, TimeToString(timeLLBeforeHHAfterBos));
            // ... kode lain ...
        }
        if (bosBullishConfirmedFlag && rates[0].close > ema200 && !hasEnteredTrade) 
        {
            if (rates[1].time > lastEntryTime + PeriodSeconds() * 3)
            { // Hindari entry berulang dalam waktu dekat
                double entryPrice = rates[1].close + 3 * _Point; // Sedikit di atas close
                double sl = entryPrice - DefaultSL_Buy * _Point;
                double tp = entryPrice + DefaultTP_Buy * _Point;
                
                if (lastClose_H1 > ema200_H1)
                    {
                        if (trade.Buy(0.01, NULL, entryPrice, sl, tp, "BoS Buy")) 
                            {
                            Print("✅ ENTRY BUY di harga ", entryPrice);
                            Print("[TRAILING RESET] Buy flags reset"); // Log reset saat entry
                            hasEnteredTrade = true;
                            lastEntryTime = TimeCurrent();
                            buyEntryPrice = entryPrice; // Simpan harga entry
                            trailingActivatedBuy = false; // Reset flag trailing
                            currentBuyTrade.ticket = trade.ResultOrder();
                            currentBuyTrade.entry_price = entryPrice;
                            currentBuyTrade.sl = sl;
                            currentBuyTrade.tp = tp;
                            currentBuyTrade.entry_time = TimeCurrent();
                            currentBuyTrade.type = "BUY";
                            PrintFormat("🚀 [BUY ENTRY] Ticket: %I64u | Price: %.5f | SL: %.5f | TP: %.5f | Time: %s",
                            currentBuyTrade.ticket,
                            currentBuyTrade.entry_price,
                            currentBuyTrade.sl,
                            currentBuyTrade.tp,
                            TimeToString(currentBuyTrade.entry_time, TIME_DATE|TIME_SECONDS));
                            } 
                        else 
                            {
                                Print("❌ Gagal melakukan entry BUY");
                            }
                    }
                    else
                    {
                        Print("Entry Buy ditolak: H1 di bawah EMA200");
                    }
            }
        }
        if (bosBullishConfirmedFlag && lastClose_H1 < ema200_H1)
        {
            Print("❌ Tolak Buy: Kondisi bullish M15 tapi H1 bearish");
        }
    } 

    // ------------+
    // BoS Bearish|
    // ------------+
    if (
        postChoCH_LL > 0 && time_postChoCH_LL > 0 &&
        !bearishSearchCompleted &&
        (
            (chochBearish && !isInTrendBearish && rates[1].close < postChoCH_LL - 50 * _Point) ||
            (bosBearishConfirmedFlag && isInTrendBearish && rates[1].close < postChoCH_LL - 50 * _Point)
       )
    )
    {
        string bosLineName = "BoS_Bear_" + IntegerToString((int)time_postChoCH_LL) + "_at_" + IntegerToString((int)rates[1].time);
        string bosLabelName = bosLineName + "_label";

        //=== Gambar garis dari postChoCH_LL ke candle dan label di tengah ===//
        ObjectDelete(0, bosLineName);
        ObjectCreate(0, bosLineName, OBJ_TREND, 0, time_postChoCH_LL, postChoCH_LL, rates[1].time, postChoCH_LL);
        ObjectSetInteger(0, bosLineName, OBJPROP_COLOR, clrOrange);
        ObjectSetInteger(0, bosLineName, OBJPROP_WIDTH, 1);
        ObjectSetInteger(0, bosLineName, OBJPROP_STYLE, STYLE_SOLID);
        ObjectSetInteger(0, bosLineName, OBJPROP_BACK, true);

        //=== Label BoS Bearish ===//
        datetime midTime  = (time_postChoCH_LL + rates[1].time) / 2;
        ObjectDelete(0, bosLabelName);
        ObjectCreate(0, bosLabelName, OBJ_TEXT, 0, midTime, postChoCH_LL + 7 * _Point);
        ObjectSetInteger(0, bosLabelName, OBJPROP_COLOR, clrOrange);
        ObjectSetInteger(0, bosLabelName, OBJPROP_FONTSIZE, 10);
        ObjectSetInteger(0, bosLabelName, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
        ObjectSetString(0, bosLabelName, OBJPROP_TEXT, "BoS");

        //=== Logging dan update flag ===//
        Print("🔥🔥🔥 === ⚡⚡⚡ [BoS BEARISH TRIGGERED] ⚡⚡⚡ === 🔥🔥🔥");
        Print("📉 Close < postChoCH_LL: ", postChoCH_LL, " → BoS Bearish Confirmed! ", TimeToString(rates[1].time));
        
        lastBoSTimeLogged         = rates[1].time;
        // chochBearish              = false;
        postChoCH_LL              = -1;
        time_postChoCH_LL         = -1;
        bosBearishConfirmedFlag   = true;
        isInTrendBearish          = true;
        // Di dalam blok BoS Bearish:
        timeBoSBearish = rates[1].time;  // Simpan waktu BoS       
        ResetMode2Bearish(); // Reset variabel MODE 2 untuk siklus baru
        // ... di dalam blok kondisi BoS Bullish ...
        if (bosBearishConfirmedFlag)
        {
            // ... kode lain ...
            PrintFormat("🔍 [DEBUG BoS %d] last Accepted HH saat ini: %.2f", bos_counter, lastAcceptedHH); // Tambahkan counter BoS jika perlu
            hhBeforellAfterBos      = lastAcceptedHH;  // Simpan LL terakhir sebagai referensi
            timehhBeforellAfterBos  = rates[1].time;   // Waktu saat BoS terkonfirmasi (atau TimeCurrent())
            llBeforeHHAfterBosSaved = true;            // Tandai bahwa nilai sudah disimpan untuk siklus ini
            PrintFormat("💾 [PERBAIKAN BoS Confirmed] HH referensi untuk Mode 3 disimpan: %.2f @ %s", hhBeforellAfterBos, TimeToString(timehhBeforellAfterBos));
            // ... kode lain ...
        }
        //=== ENTRY SELL SAAT BoS BEARISH === //
        if (bosBearishConfirmedFlag && rates[0].close < ema200 && !hasEnteredSellTrade)
        {
            if (rates[1].time > lastSellEntryTime + PeriodSeconds() * 3)  // Hindari entry berulang
            {
                double entryPrice = rates[1].close - 3 * _Point;  // Sedikit di bawah close
                double sl = entryPrice + DefaultSL_Sell * _Point;           // SL di atas entry
                double tp = entryPrice - DefaultTP_Sell * _Point;           // TP di bawah entry

                if (lastClose_H1 < ema200_H1) // Filter tambahan: H1 di bawah EMA200
                    {
                        if (trade.Sell(0.01, NULL, entryPrice, sl, tp))
                            {
                                Print("✅ ENTRY SELL dilakukan di harga ", entryPrice);
                                Print("[TRAILING RESET] Sell flags reset"); // Log reset saat entry
                                hasEnteredSellTrade = true;
                                lastSellEntryTime = TimeCurrent();
                                sellEntryPrice = entryPrice; // Simpan harga entry
                                trailingActivatedSell = false; // Reset flag trailing
                                currentSellTrade.ticket = trade.ResultOrder();
                                currentSellTrade.entry_price = entryPrice;
                                currentSellTrade.sl = sl;
                                currentSellTrade.tp = tp;
                                currentSellTrade.entry_time = TimeCurrent();
                                currentSellTrade.type = "SELL";
                                PrintFormat("🚀 [SELL ENTRY] Ticket: %I64u | Price: %.5f | SL: %.5f | TP: %.5f | Time: %s",
                                currentSellTrade.ticket,
                                currentSellTrade.entry_price,
                                currentSellTrade.sl,
                                currentSellTrade.tp,
                                TimeToString(currentSellTrade.entry_time, TIME_DATE|TIME_SECONDS));
                            }
                        else
                            {
                                Print("❌ Gagal melakukan entry SELL");
                            }
                    }
                    else
                    {
                        Print("Entry Sell ditolak: H1 di atas EMA200");
                    }
            }
        }
        if (bosBearishConfirmedFlag && lastClose_H1 > ema200_H1)
        {
            Print("❌ Tolak Sell: Kondisi bearish M15 tapi H1 bullish");
        }

    }

    // === RESET ENTRY FLAGS === //
    if (!bosBullishConfirmedFlag)
    {
        hasEnteredTrade = false;
    }
    if (!bosBearishConfirmedFlag)
    {
        hasEnteredSellTrade = false;
    }
    ApplyTrailingStop();
    CheckTrailingReset();
    //+------------------------------------------------------------------+
    //| Tambahkan di akhir fungsi OnTick(), sebelum penutup akhir }      |
    //+------------------------------------------------------------------+

    //--- Log status flag hanya ketika ada perubahan ---
    static string lastFlagStatusBullish = "";
    static string lastFlagStatusBearish = "";
    static datetime lastFlagLogTime = 0;
    
    string currentFlagStatusBullish = StringFormat(
        "BULLISH FLAGS => chochBullish=%s | hhAfterChoch=%s | bosBullish=%s | inTrendBullish=%s | hhAfterBos=%s",
        chochBullish ? "true" : "false",
        hhAfterChochConfirmedFlag ? "true" : "false",
        bosBullishConfirmedFlag ? "true" : "false",
        isInTrendBullish ? "true" : "false",
        hhAfterBosConfirmedFlag ? "true" : "false");
    
    string currentFlagStatusBearish = StringFormat(
        "BEARISH FLAGS => chochBearish=%s | llAfterChoch=%s | bosBearish=%s | inTrendBearish=%s | llAfterBos=%s",
        chochBearish ? "true" : "false",
        llAfterChochConfirmedFlag ? "true" : "false",
        bosBearishConfirmedFlag ? "true" : "false",
        isInTrendBearish ? "true" : "false",
        llAfterBosConfirmedFlag ? "true" : "false");
    
    // Cek apakah status flag berubah atau sudah lebih dari 1 detik sejak log terakhir
    if ((currentFlagStatusBullish != lastFlagStatusBullish || 
         currentFlagStatusBearish != lastFlagStatusBearish) && 
        (TimeCurrent() - lastFlagLogTime >= 1))
    {
        Print("-------------------------------------------------------------------------------------------------------------------");
        Print(currentFlagStatusBullish);
        Print(currentFlagStatusBearish);
        Print("-------------------------------------------------------------------------------------------------------------------");
        
        // Update status terakhir
        lastFlagStatusBullish = currentFlagStatusBullish;
        lastFlagStatusBearish = currentFlagStatusBearish;
        lastFlagLogTime = TimeCurrent();
    }

    //+------------------------------------------------------------------+
    //| Log perubahan variabel kunci sistem (3 bagian terpisah)          |
    //+------------------------------------------------------------------+
    static string lastLoggedPart1 = "", lastLoggedPart2 = "", lastLoggedPart3 = "", lastLoggedPart4 = "";
    datetime current_time = TimeCurrent();

    // Bagian 1: Level-level harga penting
    string part1 = StringFormat(
        "KEY VARS [1/4] : lastAcceptedHH=%.5f | lastAcceptedLL=%.5f | postChoCH_HH=%.5f | postChoCH_LL=%.5f",
        lastAcceptedHH,
        lastAcceptedLL,
        postChoCH_HH,
        postChoCH_LL
    );

    // Bagian 2: Timestamp event penting
    string part2 = StringFormat(
        "KEY VARS [2/4] : time_postChoCH_HH=%s | time_postChoCH_LL=%s | timeBoSBullish=%s | timeBoSBearish=%s",
        time_postChoCH_HH > 0 ? TimeToString(time_postChoCH_HH, TIME_DATE|TIME_MINUTES) : "N/A",
        time_postChoCH_LL > 0 ? TimeToString(time_postChoCH_LL, TIME_DATE|TIME_MINUTES) : "N/A",
        timeBoSBullish > 0 ? TimeToString(timeBoSBullish, TIME_DATE|TIME_MINUTES) : "N/A",
        timeBoSBearish > 0 ? TimeToString(timeBoSBearish, TIME_DATE|TIME_MINUTES) : "N/A"
    );

    // Bagian 3: Timestamp event penting
    string part3 = StringFormat(
        "KEY VARS [3/4] : time_choch_bearish=%s time_choch_bullish=%s",
        time_choch_bearish > 0 ? TimeToString(time_choch_bearish, TIME_DATE|TIME_MINUTES) : "N/A",
        time_choch_bullish > 0 ? TimeToString(time_choch_bullish, TIME_DATE|TIME_MINUTES) : "N/A"
    );

    // Bagian 3: Level referensi sebelum CHoCH
    string part4 = StringFormat(
        "KEY VARS [4/4] : preChochHH=%.5f | preChochLL=%.5f",
        preChochHH,
        preChochLL
    );

    // Hanya log jika salah satu bagian berubah dan minimal 1 detik telah berlalu
    if ((part1 != lastLoggedPart1 || part2 != lastLoggedPart2 || part3 != lastLoggedPart3 || part4 != lastLoggedPart4) &&
        (current_time - lastFlagLogTime >= 1))
    {
        Print("-------------------------------------------------------------------------------------------------------------------");
        Print("📊📊📊 [KEY SYSTEM VARIABLES - UPDATED] 📊📊📊");
        Print(part1);
        Print(part2);
        Print(part3);
        Print(part4);
        Print("-------------------------------------------------------------------------------------------------------------------");

        // Update status terakhir
        lastLoggedPart1 = part1;
        lastLoggedPart2 = part2;
        lastLoggedPart3 = part3;
        lastLoggedPart4 = part4;
        lastFlagLogTime = current_time;
    }
        //+------------------------------------------------------------------+
        //| Akhir fungsi OnTick()                                            |
        //+------------------------------------------------------------------+
} 