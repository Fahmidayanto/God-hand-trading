# 📊 MATRIKS PERUBAHAN FITUR DAN PERBEDAAN SOURCE CODE (v5 s/d v11)

Dokumen ini berisi analisis detail mengenai evolusi fitur, perbandingan parameter input, ketersediaan fungsi kustom, serta perbedaan logika trading (entry condition dan Stop Loss/Take Profit) di antara versi **v5** hingga **v11** berdasarkan kode sumber berikut:
1. `Dev_Bot_v5_Statis.cs` (v5 - Statis)
2. `Dev_Bot_v6_Dynamic.cs` (v6 - Dinamis)
3. `Dev_Bot_v7_Hybrid.cs` (v7 - Hybrid)
4. `Dev_Bot_v8_H+Body_Ratio.cs` (v8 - Hybrid + Body Ratio)
5. `Dev_Bot_v9_H+H4.cs` (v9 - Hybrid + H4 EMA)
6. `Dev_Bot_v10_H+BR+H4.cs` (v10 - Hybrid + Body Ratio + H4 EMA + Session Filter)
7. `Dev_Bot_v11.cs` (v11 - v10 + H4 EMA Stretch-Aware BR Override)

> [!NOTE]
> **Klarifikasi Naming Swap:**
> Terdapat sedikit perbedaan penamaan versi antara file source code di workspace dengan dokumen `ringkasan_komparatif_v5_v10.md`:
> - Di **Source Code**: `v8` adalah versi dengan **Body Ratio Filter**, sedangkan `v9` adalah versi dengan **H4 EMA Filter**.
> - Di **Laporan Ringkasan**: `v8` dirujuk sebagai versi **H4**, sedangkan `v9` dirujuk sebagai versi **Body Ratio**.
> 
> Matriks di bawah ini disesuaikan berdasarkan implementasi **aktual** yang ada pada masing-masing file source code.

---

## 1. Matriks Perubahan Fitur (Aktual Source Code)

| Fitur / Versi | v5 | v6 | v7 | v8 (Body_Ratio) | v9 (H+H4) | v10 (BR+H4) | v11 (BR+H4+Override) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Static SL (per entry)** | ✅ (Hingga 3 Entry) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Dynamic SL (last LL/HH)** | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Hybrid SL Cap (max SL)** | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Buffer 1000 poin di LL/HH** | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Filter H1 EMA200** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Filter H4 EMA200** | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| **Filter Body Ratio Candle** | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ |
| **H4 EMA Stretch-Aware BR Override** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Adaptive BR Threshold (Forensic 2023)** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Session Tracking** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Session Filter (Asia Jam 01:00)** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Penyimpanan Open Trades di Akhir** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Pencatatan Signal Ditolak (Reject)| ✅ (EMA H1 Filter) | ✅ (EMA H1 Filter) | ✅ (EMA H1 Filter) | ✅ (Dinamis: H1, Slope, BR) | ✅ (Dinamis: H1, H4, Slope) | ✅ (Dinamis: H1, H4, Slope, BR, Sesi) | ✅ (Dinamis + BR Override) |
| **Visualisasi Level Terbatas (Ray)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |


---

## 2. Perbandingan Parameter Input (Global Scope Variables)

Berikut adalah daftar parameter input yang ada atau tidak ada pada setiap versi:

| Parameter Input / Deklarasi | Deskripsi | v5 | v6 | v7 | v8 | v9 | v10 | v11 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `input bool EnableBodyRatioFilter = true;` | Mengaktifkan filter Body Ratio | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ |
| `input double MinBodyRatio = 0.40;` | Threshold minimum ratio body/range | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ |
| `input bool BodyRatio_LogOnly = false;` | Mode log saja tanpa memblokir entry | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ |
| `input bool EnableH4EMAFilter = true;` | Mengaktifkan filter EMA H4 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| `input int EMA_H4_Period = 200;` | Periode EMA untuk chart H4 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| `input bool H4EMA_LogOnly = false;` | Mode log saja tanpa memblokir entry H4 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| `input bool Enable_H4_BR_Override = true;` | H4 EMA stretch-aware adaptive BR | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `input double H4_MaxStretch_Pct = 1.8;` | Max gap% sebelum enforce strict BR | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `input double H4_MinTrend_Pct = 0.5;` | Min gap% untuk zona trending | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `input double H4_TrendMinBody = 0.15;` | MinBodyRatio saat zona trending | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `input int H4_Momentum_Bars = 4;` | Bar H4 untuk hitung momentum | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## 3. Ketersediaan Fungsi Kustom (Custom Functions)

Fungsi-fungsi kustom baru yang diimplementasikan di masing-masing versi untuk mendukung fitur baru:

| Fungsi Kustom | Kegunaan | v5 | v6 | v7 | v8 | v9 | v10 | v11 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `bool IsCandleStrong(...)` | Menghitung body ratio candle pemicu entry | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ (Adaptive) |
| `bool IsH4ConfirmedBullish()` | Memeriksa apakah close H4 > EMA200 H4 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| `bool IsH4ConfirmedBearish()` | Memeriksa apakah close H4 < EMA200 H4 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| `double GetEMA_H4()` | Mengambil nilai indikator EMA200 pada H4 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| `bool IsSessionAllowedForEntry()` | Menyaring sesi & jam spesifik (Asia jam 01:00) | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| `void CaptureOpenTrades()` | Menyimpan open positions di akhir backtest | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `RecordRejectedToBacktestTrades(...)`| Mencatat sinyal entry yang ditolak oleh filter (dinamis di v8, v9, v10 & v11) | ✅ | ✅ | ✅ | ✅ (Dinamis) | ✅ (Dinamis) | ✅ (Dinamis) | ✅ (Dinamis) |
| **H4 EMA Stretch Analysis (v11 NEW)** | **Forensic-based adaptive BR threshold** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |


---

## 4. Perbedaan Logika Pemicu Entry (BUY Execution)

Berikut adalah perbandingan logika kondisi `if` utama sebelum trade dieksekusi di chart M15:

### 🔴 v5 s/d v7 (Tanpa Filter Tambahan)
Hanya menggunakan konfirmasi BoS, EMA200 M15, dan Filter H1:
```mql5
if (bosBullishConfirmedFlag_M15 &&
    rates_M15[0].close > ema200_M15 &&
    entryCountBuy_M15 < MaxEntriesPerCycle_M15 &&
    IsH1ConfirmedBullish() &&
    IsEMATrendingUp_M15()
)
```

### 🔵 v8 (Ditambahkan Candle Body Ratio Filter - Logika Sekuensial & Dinamis)
Mengecek kekuatan candle pemicu agar terhindar dari candle indecision (Doji/Shadow panjang), dengan mengevaluasi kondisi secara sekuensial (berurutan) menggunakan rantai `if / else if` agar dapat mengidentifikasi alasan penolakan sinyal secara presisi (dinamis):
```mql5
// --- ENTRY LOGIC ENABLED WITH FILTERS (v8 Terbaru - Evaluasi Sekuensial) ---
if (bosBullishConfirmedFlag_M15 &&
    rates_M15[0].close > ema200_M15 &&
    entryCountBuy_M15 < MaxEntriesPerCycle_M15)
{
    bool isFiltered = false;
    string rejectReason = "N/A";
    
    // Evaluasi sekuensial untuk mencari filter pertama yang memicu penolakan
    if (!IsH1ConfirmedBullish())
    {
        isFiltered = true;
        rejectReason = "H1 EMA200 Filter";
    }
    else if (!IsEMATrendingUp_M15())
    {
        isFiltered = true;
        rejectReason = "EMA Slope Filter";
    }
    else if (!IsCandleStrong(rates_M15))
    {
        isFiltered = true;
        rejectReason = "Body Ratio Filter";
    }
    
    if (!isFiltered)
    {
        // Eksekusi entry BUY ...
    }
    else
    {
        // Catat ke array backtest dengan alasan penolakan dinamis yang sesuai
        double estimatedEntry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
        if (estimatedEntry <= 0) {
            MqlTick lastTick;
            if (SymbolInfoTick(_Symbol, lastTick)) estimatedEntry = lastTick.ask;
        }
        RecordRejectedToBacktestTrades("BUY", estimatedEntry, rejectReason);
    }
}
```

### 🟢 v9 (Ditambahkan H4 EMA Filter - Logika Sekuensial & Dinamis)
Memastikan tren jangka lebih panjang (Higher Timeframe H4) sejalan dengan arah entry, dengan mengevaluasi kondisi secara sekuensial (berurutan) menggunakan rantai `if / else if` agar dapat mengidentifikasi alasan penolakan sinyal secara presisi (dinamis):
```mql5
// --- ENTRY LOGIC ENABLED WITH FILTERS (v9 Terbaru - Evaluasi Sekuensial) ---
if (bosBullishConfirmedFlag_M15 &&
    rates_M15[0].close > ema200_M15 &&
    entryCountBuy_M15 < MaxEntriesPerCycle_M15)
{
    bool isFiltered = false;
    string rejectReason = "N/A";
    
    // Evaluasi sekuensial untuk mencari filter pertama yang memicu penolakan
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
    
    if (!isFiltered)
    {
        // Eksekusi entry BUY ...
    }
    else
    {
        // Catat ke array backtest dengan alasan penolakan dinamis yang sesuai
        double estimatedEntry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
        if (estimatedEntry <= 0) {
            MqlTick lastTick;
            if (SymbolInfoTick(_Symbol, lastTick)) estimatedEntry = lastTick.ask;
        }
        RecordRejectedToBacktestTrades("BUY", estimatedEntry, rejectReason);
    }
}
```

### 🏆 v10 (Kombinasi Semua Filter + Sesi/Jam Khusus - Logika Sekuensial & Dinamis)
Menggabungkan seluruh filter di atas dengan mengevaluasi kondisi secara sekuensial (berurutan) menggunakan rantai `if / else if` agar dapat mengidentifikasi dan mencatat alasan penolakan sinyal secara presisi (dinamis):
```mql5
// --- ENTRY LOGIC ENABLED WITH FILTERS (v10 Terbaru - Evaluasi Sekuensial) ---
if (bosBullishConfirmedFlag_M15 &&
    rates_M15[0].close > ema200_M15 &&
    entryCountBuy_M15 < MaxEntriesPerCycle_M15)
{
    bool isFiltered = false;
    string rejectReason = "N/A";
    
    // Evaluasi sekuensial untuk mencari filter pertama yang memicu penolakan
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
    else if (!IsCandleStrong(rates_M15))
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
        // Eksekusi entry BUY ...
        // (SL/TP menggunakan sistem Hybrid SL 3 Zones)
    }
    else
    {
        // Catat ke array backtest dengan alasan penolakan dinamis yang sesuai
        double estimatedEntry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
        if (estimatedEntry <= 0) {
            MqlTick lastTick;
            if (SymbolInfoTick(_Symbol, lastTick)) estimatedEntry = lastTick.ask;
        }
        RecordRejectedToBacktestTrades("BUY", estimatedEntry, rejectReason);
    }
}
```

### 🌟 v11 (v10 + H4 EMA Stretch-Aware BR Override - Adaptive & Forensic-Based)
**FITUR BARU**: `IsCandleStrong()` sekarang **adaptif** dengan threshold BR yang dinamis (15%-40%) berdasarkan analisis H4 EMA stretch dan momentum 16-jam:
```mql5
// --- ENTRY LOGIC ENABLED WITH FILTERS (v11 Terbaru - Adaptive BR Threshold) ---
if (bosBullishConfirmedFlag_M15 &&
    rates_M15[0].close > ema200_M15 &&
    entryCountBuy_M15 < MaxEntriesPerCycle_M15)
{
    bool isFiltered = false;
    string rejectReason = "N/A";
    
    // Evaluasi sekuensial untuk mencari filter pertama yang memicu penolakan
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
    else if (!IsCandleStrong(rates_M15))  // ✨ NOW WITH ADAPTIVE THRESHOLD (15%-40%)
    {
        isFiltered = true;
        rejectReason = "Body Ratio Filter (Adaptive)";  // v11: Mencatat zona (A/B/C) di log
    }
    else if (!IsSessionAllowedForEntry())
    {
        isFiltered = true;
        rejectReason = "Session Filter";
    }
    
    if (!isFiltered)
    {
        // Eksekusi entry BUY ...
        // (SL/TP menggunakan sistem Hybrid SL 3 Zones)
    }
    else
    {
        // Catat ke array backtest dengan alasan penolakan dinamis yang sesuai
        double estimatedEntry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
        if (estimatedEntry <= 0) {
            MqlTick lastTick;
            if (SymbolInfoTick(_Symbol, lastTick)) estimatedEntry = lastTick.ask;
        }
        RecordRejectedToBacktestTrades("BUY", estimatedEntry, rejectReason);
    }
}
```

**🔍 Perbedaan Kunci v11 vs v10**:
1. **`IsCandleStrong()` v10**: Fixed threshold 40% untuk semua kondisi pasar
2. **`IsCandleStrong()` v11**: Adaptive threshold 15%-40% based on:
   - H4 EMA gap% (distance to EMA200 H4)
   - H4 momentum 16-jam (4 bar close change)
   - 3-zone classification (Stretched/Trending/Sideways)
3. **Reject Reason v11**: Lebih detail dengan mencatat zona H4 dan alasan override di log

---

## 5. Perbedaan Logika Perhitungan Stop Loss (SL) & Take Profit (TP)

Evolusi metode proteksi modal (Stop Loss) dari versi statis hingga hybrid dinamis:

### 1️⃣ v5 (Static SL dengan Multiple Entries)
Menggunakan jarak poin tetap yang didefinisikan dari parameter input sejak awal entry. Versi terbaru v5 mendukung hingga **3 entry berurutan per siklus** dengan parameter Stop Loss dan Take Profit yang terpisah untuk setiap tingkatan entry.
*   **Entry 1 (Default):** Menggunakan `DefaultSL` dan `DefaultTP` M15.
*   **Entry 2:** Menggunakan `Entry2SL` dan `Entry2TP` M15.
*   **Entry 3:** Menggunakan `Entry3SL` dan `Entry3TP` M15.
```mql5
// Logika v5 Buy Entry (3 Tingkatan Entry Dinamis)
if (entryCountBuy_M15 == 0) {
    // Entry 1
    sl_M15 = entryPrice_M15 - DefaultSL_Buy_M15 * _Point;
    tp_M15 = entryPrice_M15 + DefaultTP_Buy_M15 * _Point;
} else if (entryCountBuy_M15 == 1) {
    // Entry 2
    sl_M15 = entryPrice_M15 - Entry2SL_Buy_M15 * _Point;
    tp_M15 = entryPrice_M15 + Entry2TP_Buy_M15 * _Point;
} else {
    // Entry 3
    sl_M15 = entryPrice_M15 - Entry3SL_Buy_M15 * _Point;
    tp_M15 = entryPrice_M15 + Entry3TP_Buy_M15 * _Point;
}
```


### 2️⃣ v6 (Dynamic SL - Last LL/HH)
Menggunakan level struktur pasar riil (Lower Low terakhir untuk Buy, Higher High terakhir untuk Sell).
*   **BUY SL:** Ditempatkan tepat pada level Lower Low Terakhir (`lastAcceptedLL_M15`).
```mql5
// Logika v6 Buy Entry
sl_M15 = lastAcceptedLL_M15;  // Dinamis berdasarkan struktur pasar
tp_M15 = entryPrice_M15 + DefaultTP_Buy_M15 * _Point;
```
> [!NOTE]
> **Update Perbaikan:**
> Masalah di mana posisi **SELL** di v6 tidak sengaja menggunakan *Static SL* telah diperbaiki sepenuhnya. Logika entry **SELL** sekarang telah selaras menggunakan *Dynamic Stop Loss* yang diletakkan pada level **last accepted HH** (`lastAcceptedHH_M15`).

### 3️⃣ v7 s/d v10 (Hybrid SL - 3 Zones dengan Buffer & Cap)
Perbaikan dari dynamic SL murni untuk membatasi risiko ekstrim ketika Lower Low (LL) terlalu jauh, dan memberi napas tambahan bagi market dengan buffer 1000 poin ketika LL ideal.
*   **BUY SL:**
    *   Jika jarak ke LL > 3000 poin (Max Cap), gunakan **Static Max Cap**.
    *   Jika jarak ke LL <= 3000 poin, gunakan **LL - 1000 poin Buffer** (ideal).
```mql5
// Logika v7 - v10 Buy Entry
double dynamicSL_Buy     = lastAcceptedLL_M15;
double maxSLDistance_Buy = DefaultSL_Buy_M15 * _Point; // Batas Max Toleransi (3000 poin)

double distanceToLL_Buy  = entryPrice_M15 - dynamicSL_Buy;

if (distanceToLL_Buy > maxSLDistance_Buy)
{
    // Zona 3: Terlalu Jauh (> Max), batasi ke Max Cap
    sl_M15 = entryPrice_M15 - maxSLDistance_Buy;
}
else
{
    // Zona 2: Ideal (< Max), gunakan LL + buffer 1000 poin
    sl_M15 = dynamicSL_Buy - 1000 * _Point;
    
    // Proteksi: Pastikan setelah ditambah buffer tidak melebihi batas Max
    if (entryPrice_M15 - sl_M15 > maxSLDistance_Buy)
    {
        sl_M15 = entryPrice_M15 - maxSLDistance_Buy;
    }
}
tp_M15 = entryPrice_M15 + DefaultTP_Buy_M15 * _Point;
```

*   **SELL SL:**
    *   Jika jarak ke HH > 3000 poin (Max Cap), gunakan **Static Max Cap**.
    *   Jika jarak ke HH <= 3000 poin, gunakan **HH + 1000 poin Buffer** (ideal).
```mql5
// Logika v7 - v10 Sell Entry
double dynamicSL_Sell     = lastAcceptedHH_M15;
double maxSLDistance_Sell = DefaultSL_Sell_M15 * _Point; // Batas Max Toleransi (3000 poin)

double distanceToHH_Sell  = dynamicSL_Sell - entryPrice_M15;

if (distanceToHH_Sell > maxSLDistance_Sell)
{
    // Zona 3: Terlalu Jauh (> Max), batasi ke Max Cap
    sl_M15 = entryPrice_M15 + maxSLDistance_Sell;
}
else
{
    // Zona 2: Ideal (< Max), gunakan HH + buffer 1000 poin
    sl_M15 = dynamicSL_Sell + 1000 * _Point;
    
    // Proteksi: Pastikan setelah ditambah buffer tidak melebihi batas Max
    if (sl_M15 - entryPrice_M15 > maxSLDistance_Sell)
    {
        sl_M15 = entryPrice_M15 + maxSLDistance_Sell;
    }
}
```

---

## 6. Detail Source Code Spesifik dari Setiap Fitur Penyaring (Filters)

Berikut adalah cuplikan kode lengkap fungsi filter kustom yang membedakan versi v8, v9, dan v10 dari versi dasar:

### 📊 Filter Kekuatan Candle (Body Ratio) — Terpasang di v8 & v10
Fungsi kustom untuk menghitung rasio ukuran body lilin pemicu dibandingkan total range lilin.
```mql5
bool IsCandleStrong(MqlRates &rates[])
{
    if (!EnableBodyRatioFilter) return true;
    
    // Ambil candle indeks ke-1 (candle pemicu yang baru saja selesai terbentuk)
    double body  = MathAbs(rates[1].close - rates[1].open);
    double range = rates[1].high - rates[1].low;
    
    if (range <= 0) return false;
    
    double bodyRatio = body / range;
    bool   isStrong  = (bodyRatio >= MinBodyRatio);
    
    if (!isStrong)
    {
        static datetime lastLogTime = 0;
        if (TimeCurrent() - lastLogTime >= 300) // Batasi log maks sekali per 5 menit
        {
            PrintFormat(" [BODY RATIO REJECT]%s Candle pemicu lemah: Body Ratio %.1f%% (Min Required %.1f%%)%s",
                        BodyRatio_LogOnly ? " [LOG ONLY]" : " [REJECT]",
                        bodyRatio * 100, MinBodyRatio * 100,
                        BodyRatio_LogOnly ? " (entry TETAP DIIZINKAN - mode log)" : " (entry ditolak)");
            lastLogTime = TimeCurrent();
        }
    }
    else
    {
        PrintFormat(" [BODY RATIO OK] Candle pemicu kuat: Body Ratio %.1f%% >= %.1f%%",
                    bodyRatio * 100, MinBodyRatio * 100);
    }
    
    if (BodyRatio_LogOnly) return true;
    return isStrong;
}
```

### 📈 Filter Trend Jangka Panjang H4 (H4 EMA200) — Terpasang di v9 & v10
Fungsi untuk mengecek keselarasan arah trend utama menggunakan Moving Average Exponential periode 200 di timeframe H4.

#### A. Inisialisasi Handle pada `OnInit()`
```mql5
// MQL5 handle dibuat sekali saat EA dijalankan pertama kali
handleEMA_H4 = iMA(_Symbol, PERIOD_H4, EMA_H4_Period, 0, MODE_EMA, PRICE_CLOSE);
if (handleEMA_H4 == INVALID_HANDLE)
{
    Print(" Gagal membuat handle EMA H4");
    return INIT_FAILED;
}
ChartIndicatorAdd(0, 0, handleEMA_H4); // Tampilkan indikator ke grafik
```

#### B. Logika Validasi Trend
```mql5
// Mendapatkan nilai indikator ter-update
double GetEMA_H4()
{
    double buffer[1];
    if (CopyBuffer(handleEMA_H4, 0, 0, 1, buffer) < 1) return 0;
    return buffer[0];
}

bool IsH4ConfirmedBullish()
{
    if (!EnableH4EMAFilter) return true;
    
    double emaH4 = GetEMA_H4();
    MqlRates h4Rates[];
    ArraySetAsSeries(h4Rates, true);
    if (CopyRates(_Symbol, PERIOD_H4, 0, 1, h4Rates) < 1) return false;
    
    bool confirmed = (emaH4 > 0 && h4Rates[0].close > emaH4);
    if (!confirmed)
    {
        static datetime lastLogTime = 0;
        if (TimeCurrent() - lastLogTime >= 300)
        {
            PrintFormat(" [H4 FILTER REJECT]%s BUY ditolak: H4 Close (%.5f) di BAWAH EMA H4 (%.5f)",
                        H4EMA_LogOnly ? " [LOG ONLY]" : " [REJECT]",
                        h4Rates[0].close, emaH4);
            lastLogTime = TimeCurrent();
        }
    }
    if (H4EMA_LogOnly) return true;
    return confirmed;
}

bool IsH4ConfirmedBearish()
{
    if (!EnableH4EMAFilter) return true;
    
    double emaH4 = GetEMA_H4();
    MqlRates h4Rates[];
    ArraySetAsSeries(h4Rates, true);
    if (CopyRates(_Symbol, PERIOD_H4, 0, 1, h4Rates) < 1) return false;
    
    bool confirmed = (emaH4 > 0 && h4Rates[0].close < emaH4);
    if (!confirmed)
    {
        static datetime lastLogTime = 0;
        if (TimeCurrent() - lastLogTime >= 300)
        {
            PrintFormat(" [H4 FILTER REJECT]%s SELL ditolak: H4 Close (%.5f) di ATAS EMA H4 (%.5f)",
                        H4EMA_LogOnly ? " [LOG ONLY]" : " [REJECT]",
                        h4Rates[0].close, emaH4);
            lastLogTime = TimeCurrent();
        }
    }
    if (H4EMA_LogOnly) return true;
    return confirmed;
}
```

### 🕒 Filter Sesi Asia Kritis (Session Reject) — Terpasang Eksklusif di v10
Penyaringan tambahan yang mendeteksi jam 01:00 GMT pada sesi Asia karena secara historis sering menghasilkan false breakout atau volatilitas rendah dengan spread tinggi di awal hari.
```mql5
bool IsSessionAllowedForEntry()
{
    string currentSession = GetCurrentSession();
    MqlDateTime dt;
    TimeToStruct(TimeCurrent(), dt);
    
    // Jika sesi saat ini adalah Asia, blokir khusus untuk jam 01:00
    if (currentSession == "Asia" && dt.hour == 1)
    {
        static datetime lastLogTime = 0;
        if (TimeCurrent() - lastLogTime >= 300) // Log maksimal setiap 5 menit
        {
            PrintFormat(" [SESSION REJECT] Entry ditolak: Sesi %s, jam %02d:00 (entry diblokir khusus jam ini)", currentSession, dt.hour);
            lastLogTime = TimeCurrent();
        }
        return false;
    }
    
    return true;
}
```

---

## 7. Fitur Eksklusif v11: H4 EMA Stretch-Aware BR Override (Forensic Analysis 2023)

### 🎯 Latar Belakang Masalah
Analisis forensik mendalam pada performa backtest tahun 2023 mengungkapkan **fenomena kritis**:
- Filter Body Ratio < 40% **salah memblokir 5 dari 8 trade WIN**
- Trade yang diblokir berada di zona trending moderat (0.5%-1.9% dari EMA200 H4)
- Candle pemicu terlihat seperti doji/indecision, padahal merupakan **reaccumulation pattern**

### 📊 Solusi: Adaptive Body Ratio Threshold
v11 memperkenalkan sistem **3-zone adaptive threshold** yang menganalisis kondisi makro H4 sebelum menerapkan filter BR:

#### **Zone Classification (berdasarkan jarak harga ke EMA200 H4)**

```
┌──────────────────────────────────────────────────────────────────┐
│ ZONE A: STRETCHED (|gap%| > 1.8%)                                │
│ ├─ Karakteristik: Harga terlalu jauh dari EMA                   │
│ ├─ Risiko: Mean-reversion tinggi                                │
│ └─ Threshold BR: STRICT 40% (tetap ketat)                       │
├──────────────────────────────────────────────────────────────────┤
│ ZONE B: MODERATE TRENDING (0.5% ≤ |gap%| ≤ 1.8%)               │
│ ├─ Karakteristik: Tren moderat searah trade                     │
│ ├─ Kondisi Tambahan: Momentum H4 searah (4 bar = 16 jam)       │
│ └─ Threshold BR: RELAXED 15% (longgar untuk reaccumulation)    │
├──────────────────────────────────────────────────────────────────┤
│ ZONE C: SIDEWAYS (|gap%| < 0.5%)                                │
│ ├─ Karakteristik: Konsolidasi dekat EMA                         │
│ ├─ Risiko: Arah tren tidak jelas                                │
│ └─ Threshold BR: STRICT 40% (tetap ketat)                       │
└──────────────────────────────────────────────────────────────────┘
```

### 🔬 Implementasi Kode

#### A. Parameter Input Baru (v11)
```mql5
//+------------------------------------------------------------------+
//| H4 EMA STRETCH-AWARE BR OVERRIDE - Input Parameters              |
//+------------------------------------------------------------------+
// Analisis forensik menunjukkan filter BR < 40% salah blokir 5 dari 8 trade WIN di 2023
// ketika harga berada di zona trending moderat (0.5%-1.9% dari EMA200 H4).
// Rule A: Jika |H4 gap%| > H4_MaxStretch_Pct → enforce strict BR (MinBodyRatio)
// Rule B: Jika H4 gap 0.5%-MaxStretch% + momentum H4 searah trade → MinBR = H4_TrendMinBody
input bool   Enable_H4_BR_Override      = true;   // Aktifkan H4 EMA stretch-aware BR override
input double H4_MaxStretch_Pct          = 1.8;    // Max H4 gap% sebelum enforce strict BR (default 1.8%)
input double H4_MinTrend_Pct            = 0.5;    // Min H4 gap% untuk zona trending (default 0.5%)
input double H4_TrendMinBody            = 0.15;   // MinBodyRatio saat zona trending (default 15%)
input int    H4_Momentum_Bars           = 4;      // Jumlah bar H4 untuk hitung momentum (4 bar = 16 jam)
```

#### B. Logika Adaptif dalam `IsCandleStrong()` (v11)
```mql5
bool IsCandleStrong(MqlRates &rates[])
{
    if (!EnableBodyRatioFilter) return true;
    
    // [1] HITUNG BODY RATIO STANDAR (BAR INDEX 1 = PEMICU)
    double body  = MathAbs(rates[1].close - rates[1].open);
    double range = rates[1].high - rates[1].low;
    if (range <= 0) return false;
    double bodyRatio = body / range;
    
    // [2] ADAPTIVE THRESHOLD BASED ON H4 EMA STRETCH
    double effectiveMinBR = MinBodyRatio; // Default: 40% (strict)
    string overrideReason = "";
    
    if (Enable_H4_BR_Override)
    {
        // Ambil data H4
        double emaH4 = GetEMA_H4();
        MqlRates h4Rates[];
        ArraySetAsSeries(h4Rates, true);
        if (CopyRates(_Symbol, PERIOD_H4, 0, H4_Momentum_Bars + 1, h4Rates) > H4_Momentum_Bars)
        {
            double h4Close = h4Rates[0].close;
            
            // Hitung gap% dan momentum
            double h4GapPct = ((h4Close - emaH4) / emaH4) * 100.0;
            double absGapPct = MathAbs(h4GapPct);
            
            // Momentum 16 jam (perubahan close 4 bar terakhir H4)
            double h4Mom16h = ((h4Rates[0].close - h4Rates[H4_Momentum_Bars].close) / 
                              h4Rates[H4_Momentum_Bars].close) * 100.0;
            
            // Apakah H4 dan momentum searah dengan trade?
            bool h4AlignedWithTrade = (h4Close > emaH4);  // Bullish untuk BUY
            bool momAlignedWithTrade = (h4Mom16h > 0);     // Momentum naik
            
            // ----- RULE A: STRETCHED ZONE (|gap%| > H4_MaxStretch_Pct) -----
            if (absGapPct > H4_MaxStretch_Pct)
            {
                effectiveMinBR = MinBodyRatio; // Tetap strict 40%
                overrideReason = StringFormat("RULE_A: H4 Gap=%.2f%% > %.1f%% (stretched) → strict BR %.0f%%",
                                              h4GapPct, H4_MaxStretch_Pct, effectiveMinBR * 100);
            }
            // ----- RULE B: MODERATE TRENDING ZONE (H4_MinTrend_Pct <= |gap%| <= H4_MaxStretch_Pct) -----
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
                    effectiveMinBR = MinBodyRatio; // Momentum tidak searah → strict
                    overrideReason = StringFormat("RULE_B_FAIL: H4 Gap=%.2f%% moderate BUT mom=%.1f misaligned → strict BR %.0f%%",
                                                  h4GapPct, h4Mom16h, effectiveMinBR * 100);
                }
            }
            // ----- RULE C: SIDEWAYS ZONE (|gap%| < H4_MinTrend_Pct) -----
            else
            {
                effectiveMinBR = MinBodyRatio; // Tetap strict 40%
                overrideReason = StringFormat("RULE_C: H4 Gap=%.2f%% < %.1f%% (sideways) → strict BR %.0f%%",
                                              h4GapPct, H4_MinTrend_Pct, effectiveMinBR * 100);
            }
        }
    }
    
    // [3] EVALUASI AKHIR
    bool isStrong = (bodyRatio >= effectiveMinBR);
    
    if (!isStrong)
    {
        PrintFormat("❌ [BODY RATIO REJECT]%s Candle pemicu lemah: BR %.1f%% < %.1f%% | %s",
                    BodyRatio_LogOnly ? " [LOG ONLY]" : "",
                    bodyRatio * 100, effectiveMinBR * 100,
                    overrideReason != "" ? overrideReason : "Standard threshold");
    }
    else if (overrideReason != "")
    {
        PrintFormat("✅ [ADAPTIVE BR PASS] BR %.1f%% >= %.1f%% (adaptive) | %s",
                    bodyRatio * 100, effectiveMinBR * 100, overrideReason);
    }
    
    if (BodyRatio_LogOnly) return true;
    return isStrong;
}
```

### 📈 Dampak Strategis

| Aspek | Sebelum v11 (Static BR 40%) | Setelah v11 (Adaptive BR) |
|:------|:---------------------------|:-------------------------|
| **False Rejection** | 5 dari 8 trade WIN diblokir (62.5%) | Trade reaccumulation diizinkan masuk |
| **Zone Detection** | ❌ Tidak ada analisis konteks makro | ✅ 3-zone classification (A/B/C) |
| **Momentum Check** | ❌ Tidak diperhitungkan | ✅ 16-jam H4 momentum validation |
| **Adaptability** | 🔒 Fixed threshold (rigid) | 🔄 Dynamic 15%-40% (context-aware) |
| **Risk Control** | ⚠️ Over-conservative di trending | ✅ Balanced: strict saat stretched, relaxed saat trending |

### 🎯 Kesimpulan v11
Versi 11 menjadi **puncak evolusi filter** dengan:
1. **Intelligence Upgrade**: Filter tidak lagi blind, mempertimbangkan konteks makro H4
2. **Forensic-Driven**: Berdasarkan analisis empiris performa 2023 (data-driven)
3. **Backward Compatible**: Parameter override dapat di-disable untuk kembali ke behavior v10
4. **Production Ready**: Tetap menjaga risk control ketat di zona stretched/sideways

---

## 8. Fitur Utilitas Diagnostik & Optimasi Baru (v5 s/d v11 Terbaru)

Untuk meningkatkan keandalan sistem backtest dan kualitas visualisasi pada chart, seluruh versi (v5 hingga v10) telah diperbarui dengan beberapa fitur penunjang penting berikut:

### 1️⃣ Kapasitas Array Transaksi yang Diperbesar (Kapasitas 10 Slot)
Kapasitas penyimpanan data transaksi aktif ditingkatkan dari 3 slot menjadi **10 slot** (`activeBuyTrades_M15[10]` & `activeSellTrades_M15[10]`). Slot kosong dicari secara dinamis menggunakan iterasi pencarian slot dengan `ticket == 0` untuk menghindari *overwrite* transaksi ketika siklus BoS terpicu ulang.

### 2️⃣ Penyimpanan Transaksi Terbuka (Capture Open Trades)
Fungsi `CaptureOpenTrades()` dijalankan sebelum mengekspor data hasil uji. Fungsi ini menyisir seluruh posisi trading yang masih aktif di MT5 ketika backtest berakhir, menghitung unrealized P&L, dan menyimpannya ke dalam file CSV agar performa bot terhitung secara akurat di akhir pengujian.
```mql5
void CaptureOpenTrades()
{
    int openPositions = PositionsTotal();
    if (openPositions == 0) return;
    
    for (int i = 0; i < openPositions; i++)
    {
        ulong ticket = PositionGetTicket(i);
        if (ticket <= 0) continue;
        if (!PositionSelectByTicket(ticket)) continue;
        
        ENUM_POSITION_TYPE pos_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
        string type = (pos_type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
        double entry_price = PositionGetDouble(POSITION_PRICE_OPEN);
        double sl = PositionGetDouble(POSITION_SL);
        double tp = PositionGetDouble(POSITION_TP);
        datetime entry_time = (datetime)PositionGetInteger(POSITION_TIME);
        double lot_size = PositionGetDouble(POSITION_VOLUME);
        double unrealized_profit = PositionGetDouble(POSITION_PROFIT);
        double current_price = PositionGetDouble(POSITION_PRICE_CURRENT);
        
        SaveTradeToArray(ticket, _Symbol, type, entry_price, current_price, sl, tp, 
                         unrealized_profit, entry_time, TimeCurrent(), lot_size, MagicNumber_M15, "M15", 
                         0, 0, GetCurrentSession());
    }
}
```

### 3️⃣ Pencatatan Sinyal Terblokir Filter (Reject Recording - Dinamis pada v8, v9 & v10)
Fungsi `RecordRejectedToBacktestTrades()` digunakan untuk mencatat sinyal entry potensial yang dibatalkan/dibatasi oleh filter. Pada versi **v5 s/d v7**, alasan penolakan dicatat secara statis sebagai `"H1 EMA200 Filter"`. Namun pada versi **v8, v9 & v10**, fungsi ini ditingkatkan untuk mencatat alasan penolakan secara dinamis sesuai filter spesifik yang memicu pemblokiran (`"H1 EMA200 Filter"`, `"EMA Slope Filter"`, `"Body Ratio Filter"`, `"H4 EMA Filter"`, atau `"Session Filter"`), serta menginisialisasi field terstruktur lainnya.
```mql5
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
    g_BacktestTrades[g_TradeCount].status        = "REJECTED";
    g_BacktestTrades[g_TradeCount].reject_reason = reason;
    
    g_TradeCount = newSize;
    PrintFormat("💾 [SAVED REJECT] Recorded reject signal #%d: %s | Price: %.5f | Reason: %s",
                g_TradeCount, type, price, reason);
}
```

### 4️⃣ Visualisasi Level Dinamis yang Lebih Bersih (Trend Ray Right)
Garis penanda level accepted HH/LL tidak lagi menggunakan `OBJ_HLINE` (garis tanpa ujung kiri-kanan), melainkan `OBJ_TREND` dengan parameter `OBJPROP_RAY_RIGHT = true` dan `OBJPROP_RAY_LEFT = false`. Dengan metode ini, garis level hanya akan digambar memanjang ke arah kanan (ke depan) sejak waktu level tersebut resmi terbentuk, sehingga tidak mengotori grafik history di sebelah kiri.
```mql5
ObjectCreate(0, lineName, OBJ_TREND, 0, time, level, time + PeriodSeconds(PERIOD_M15), level);
ObjectSetInteger(0, lineName, OBJPROP_RAY_RIGHT, true);
ObjectSetInteger(0, lineName, OBJPROP_RAY_LEFT, false);
ObjectSetInteger(0, lineName, OBJPROP_BACK, true);
```

### 5️⃣ Integrasi Biaya Swap, Komisi, dan Koreksi Net Profit (v8, v9 & v10)
Untuk menyelaraskan antara kalkulasi log internal robot, file ekspor CSV hasil backtest, dan hasil Strategy Tester MT5, versi **v8, v9 & v10** memperkenalkan integrasi biaya transaksi secara dinamis:
*   **Pencatatan Biaya Riil**: Mengambil data `DEAL_SWAP` dan `DEAL_COMMISSION` langsung dari riwayat transaksi MT5 menggunakan `HistoryDealGetDouble` untuk setiap tiket yang ditutup (menggantikan kalkulasi spread statis yang redundan).
*   **Formula Net Profit Akurat**: Net Profit dihitung dengan formula yang tepat:
    $$\text{Net Profit} = \text{Gross Profit} + \text{Commission} + \text{Swap}$$
    *(Catatan: Nilai komisi dan swap dari MT5 sudah bertanda negatif sebagai biaya, sehingga dijumlahkan langsung).*
*   **Penyesuaian Kriteria Optimasi**: Fungsi `OnTester()` diubah agar mengembalikan total Net Profit riil (bukan gross profit) as kriteria optimasi kustom.
```mql5
// Akumulasi biaya transaksi dari deals history di v8, v9 & v10
double spreadCost = 0;
double commission = 0;
double swapVal = 0;
HistorySelect(0, TimeCurrent());
int totalDeals = HistoryDealsTotal();
for(int j = totalDeals-1; j >= 0; j--)
{
    ulong dealTicket = HistoryDealGetTicket(j);
    if(HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID) == tradeRec.ticket)
    {
        // Ambil komisi dan swap riil dari broker
        commission += HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);
        swapVal += HistoryDealGetDouble(dealTicket, DEAL_SWAP);
    }
}
```

### 6️⃣ Penyelesaian Error Kompilasi & Forward Declarations (v8, v9 & v10)
Untuk memastikan kepatuhan terhadap aturan compiler MQL5 yang ketat pada versi **v8, v9 & v10**:
*   **Forward Declarations**: Menambahkan deklarasi prototipe untuk fungsi kustom `WarmUp_M15()` and `WarmUp_H1()` di baris paling atas agar fungsi tersebut dapat dipanggil di dalam `OnInit()` tanpa menimbulkan error *undeclared identifier*.
*   **Perbaikan Syntax**: Memperbaiki tanda kutip string yang tidak tertutup (*closing quote expected*) dan tanda kurung kurawal yang tidak seimbang (*unbalanced parentheses*) pada file source code.
```mql5
// Forward declarations di awal file v8, v9 & v10
void WarmUp_M15(int bars);
void WarmUp_H1(int bars);
```
