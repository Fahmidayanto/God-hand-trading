//+------------------------------------------------------------------+
//| File: HH_LL_Extraction_M15.mq5                                  |
//| Purpose: Isolate HH/LL Detection and Horizontal Zone Drawing     |
//| Timeframe: M15 (15-minute) specific implementation              |
//| Note: This version is specifically optimized for M15 timeframe  |
//+------------------------------------------------------------------+
#include <Trade/Trade.mqh>  // Untuk fungsi trading
#include <Tools/datetime.mqh>  // Untuk manipulasi waktu
CTrade trade;  // Objek untuk eksekusi trading

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

int handleEMA_H1;  // Handle untuk EMA200 di timeframe H1
double ema200_H1;  // Nilai EMA200 di timeframe H1
double lastClose_H1; // Harga close terakhir di H1

// Parameter input untuk SL dan TP M15
input int DefaultSL_Buy_M15  = 2000;   // Stop Loss untuk Buy (dalam poin) M15
input int DefaultTP_Buy_M15  = 1500;   // Take Profit untuk Buy (dalam poin) M15
input int DefaultSL_Sell_M15 = 1000;   // Stop Loss untuk Sell (dalam poin) M15
input int DefaultTP_Sell_M15 = 1500;   // Take Profit untuk Sell (dalam poin) M15
input ulong MagicNumber_M15 = 12345; // Magic number untuk EA M15

// --- Variabel untuk trailing stop ---
double buyEntryPrice_M15 = 0.0;    // Harga entry posisi buy M15
double sellEntryPrice_M15 = 0.0;   // Harga entry posisi sell M15
bool trailingActivatedBuy_M15 = false; // Flag trailing aktif untuk buy M15
bool trailingActivatedSell_M15 = false; // Flag trailing aktif untuk sell M15

input bool BackfillOnLoad_M15 = true;   // langsung scan & gambar dari history saat attach
input int  WarmupBars_M15     = 500;    // jumlah bar history untuk backfill
bool g_BackfillMode_M15 = false; // true saat proses backfill (gambar saja, tanpa entry)


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
    handleEMA_H1 = iMA(_Symbol, PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE);
    if (handleEMA_H1 == INVALID_HANDLE)
    {
        Print("❌ Gagal membuat handle EMA200 untuk H1");
        return INIT_FAILED;
    }
    ChartIndicatorAdd(0, 0, handleEMA_M15);
    ChartIndicatorAdd(0, 0, handleEMA_H1);

        // ====== NEW: langsung backfill ======
    if (BackfillOnLoad_M15)
        WarmUp_M15(WarmupBars_M15);

    trade.SetExpertMagicNumber(MagicNumber_M15);
    Print("✅ EMA200 handle berhasil dibuat untuk M15 & H1");
    return INIT_SUCCEEDED;
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
                        
            // Reset trade record
            tradeRec.ticket = 0;
        }
    }
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
            // Jika CHoCH Bearish sudah terkonfirmasi, tolak HH yang lebih rendah dari preChoCHHH M15| "✅"
            //-----------------------------------------------------------------------------------+
            if (chochBearish_M15 && !llAfterChochConfirmedFlag_M15 && !bosBearishConfirmedFlag_M15) 
            {
                if (rates_M15[i].high < lastAcceptedHH_M15) {
                    PrintFormat("❌ [MODE 2 BEARISH M15] HH %.2f DITOLAK karena < preChochHH %.2f | Time: %s",
                                rates_M15[i].high, lastAcceptedHH_M15, TimeToString(rates_M15[i].time));
                    // Tambahkan visual jika perlu
                    if (ObjectFind(0, boxName_M15) >= 0) ObjectDelete(0, boxName_M15);
                }
                continue; // Lewati update HH ini
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
            if (bosBullishConfirmedFlag_M15 && isInTrendBullish_M15 && rates_M15[i].low > absoluteLowestLL_M15)
                {
                     PrintFormat("❌ [MODE 3 M15 - REJECTED] LL %.2f DITOLAK karena > LL Terendah Absolut (%.2f) | Time: %s",
                                     rates_M15[i].low, absoluteLowestLL_M15, TimeToString(rates_M15[i].time));
                         string boxNameRejected_M15 = "zone_ll_M15_" + IntegerToString((int)rates_M15[i].time);
                         if (ObjectFind(0, boxNameRejected_M15) >= 0) ObjectDelete(0, boxNameRejected_M15);
                }
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
            UpdateAcceptedLevelVisuals_M15(preChochHH_M15, "HH", rates_M15[1].time); // Update visualisasi HH sebelum CHoCH Bearish
                  // lastAcceptedHH_M15 = -1;                    // Reset lastAcceptedHH_M15 untuk mode transisi
                    //  lastAcceptedLL_M15 = -1;                    // Reset lastAcceptedLL_M15 untuk mode transisi (opsional, tergantung logika MODE 1 bearish)
            //--- Logging ---
            Print("🔔🔔🔔 === ⚡⚡⚡ [CHoCH BEARISH TRIGGERED M15] ⚡⚡⚡ === 🔔🔔🔔");
            PrintFormat("📉 Close Breaks LL (Target) M15: %.5f → CHoCH Bearish Confirmed! @ %s",
                        lastAcceptedLL_M15, TimeToString(rates_M15[1].time));
            PrintFormat("✅ [MODE X RESET M15] CHoCH Bearish terkonfirmasi. last Accepted HH direset ke preChochHH: %.5f @ %s",
                        preChochHH_M15, TimeToString(rates_M15[1].time)); // Log reset HH jika digunakan

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
        if (bosBullishConfirmedFlag_M15 && rates_M15[0].close > ema200_M15 && !hasEnteredTrade_M15) 
        {
            if (rates_M15[1].time > lastEntryTime_M15 + PeriodSeconds(PERIOD_M15) * 3) { // Hindari entry berulang dalam waktu dekat
                double entryPrice_M15 = rates_M15[1].close + 3 * _Point; // Sedikit di atas close
                double sl_M15 = entryPrice_M15 - DefaultSL_Buy_M15 * _Point;
                double tp_M15 = entryPrice_M15 + DefaultTP_Buy_M15 * _Point;
                
                if (trade.Buy(0.01, NULL, entryPrice_M15, sl_M15, tp_M15, "BoS Buy M15")) 
                    {
                    Print("✅ ENTRY BUY di harga M15 ", entryPrice_M15);
                    Print("[TRAILING RESET M15] Buy flags reset"); // Log reset saat entry
                    hasEnteredTrade_M15 = true;
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
        if (bosBearishConfirmedFlag_M15 && rates_M15[0].close < ema200_M15 && !hasEnteredSellTrade_M15)
        {
            if (rates_M15[1].time > lastSellEntryTime_M15 + PeriodSeconds(PERIOD_M15) * 3)  // Hindari entry berulang
            {
                double entryPrice_M15 = rates_M15[1].close - 3 * _Point;  // Sedikit di bawah close
                double sl_M15 = entryPrice_M15 + DefaultSL_Sell_M15 * _Point;           // SL di atas entry
                double tp_M15 = entryPrice_M15 - DefaultTP_Sell_M15 * _Point;           // TP di bawah entry

                if (trade.Sell(0.01, NULL, entryPrice_M15, sl_M15, tp_M15))
                    {
                        Print("✅ ENTRY SELL dilakukan di harga M15 ", entryPrice_M15);
                        Print("[TRAILING RESET M15] Sell flags reset"); // Log reset saat entry
                        hasEnteredSellTrade_M15 = true;
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
    ApplyTrailingStop_M15();
    CheckTrailingReset_M15();
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
    // GetH1Data();
    CheckTradeClosure_M15(currentBuyTrade_M15);
    CheckTradeClosure_M15(currentSellTrade_M15);
    DetectAndDraw_M15(rates_M15, /*backfillMode=*/false);
    
    lastBarTime_M15 = rates_M15[0].time;
    
}