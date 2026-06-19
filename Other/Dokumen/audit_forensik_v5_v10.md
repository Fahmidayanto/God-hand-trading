# 🔬 AUDIT FORENSIK EA MT5 — LAPORAN KOMPARATIF v5 s/d v10
**Instrumen:** XAUUSD | **Timeframe Entry:** M15 | **Konfirmasi:** H1 EMA  
**Lot Size:** 0.05 fixed | **Periode Backtest:** 2020–2025

---

## BAGIAN 1 — RINGKASAN PERUBAHAN TEKNIS SOURCE CODE

### v5 — Static SL (`Dev_Bot_v5_statis.cs`)
**Mekanisme SL:** Statis berdasarkan poin tetap per entry

```
Entry 1: SL = entryPrice - DefaultSL_Buy_M15 * _Point
Entry 2: SL = entryPrice - Entry2SL_Buy_M15 * _Point
Entry 3: SL = entryPrice - Entry3SL_Buy_M15 * _Point
```
- Setiap entry 1/2/3 memiliki nilai SL dan TP yang **terpisah dan tetap** (dikonfigurasi via input parameter)
- SL **tidak berelasi** dengan market structure (level LL/HH)
- **Filter Entry:** `IsH1ConfirmedBullish()` + `IsEMATrendingUp_M15()` + `ema200_M15`
- Tidak ada filter H4, tidak ada body ratio check

---

### v6 — Dynamic SL (`Dev_Bot_v6_Dynamic.cs`)
**Mekanisme SL:** Dinamis menggunakan `lastAcceptedLL_M15` sebagai titik SL

```
sl_M15 = lastAcceptedLL_M15;  // SL langsung di level LL terakhir
```
- SL berubah mengikuti **market structure (LL terakhir yang diterima)**
- TP tetap berbeda per entry (DefaultTP, Entry2TP, Entry3TP)
- SL **sama untuk semua entry** dalam satu cycle (tidak per-entry seperti v5)
- **Filter Entry:** sama dengan v5 (`IsH1ConfirmedBullish()` + `IsEMATrendingUp_M15()`)
- Tidak ada filter H4, tidak ada body ratio check
- **Catatan:** v6 menghilangkan `currentBuyTrade_M15.session` (session tracking dihapus di beberapa path)

---

### v7 — Hybrid SL (`Dev_Bot_v7_hybrid.cs`)
**Mekanisme SL:** Hybrid 2-Zona — gabungan dynamic LL + max SL cap

```
dynamicSL_Buy     = lastAcceptedLL_M15
maxSLDistance_Buy = DefaultSL_Buy_M15 * _Point  // Batas max (mis. 3000 poin)

IF (entryPrice - dynamicSL_Buy) > maxSLDistance:
    → Zona 3 (Terlalu Jauh): SL = entryPrice - maxSLDistance   [CAP]
ELSE:
    → Zona 2 (Ideal):        SL = dynamicSL_Buy - 1000 * _Point [LL + Buffer 1000]
    → Jika buffer melebihi max → kembali di-cap ke max
```
- **Inovasi utama:** SL adaptif dengan proteksi batas maksimum agar tidak terlalu besar
- Buffer 1000 point di bawah LL memberikan ruang gerak ekstra sebelum stop
- **TP:** Seragam semua entry = `entryPrice + DefaultTP_Buy_M15 * _Point` (tidak per-entry)
- **Filter Entry:** sama dengan v5/v6 (`IsH1ConfirmedBullish()` + `IsEMATrendingUp_M15()`)
- Tidak ada filter H4, tidak ada body ratio check
- **Session tracking** dipulihkan (`currentBuyTrade_M15.session = GetCurrentSession()`)

---

### v8 — Hybrid + H4 SL Filter (`Dev_Bot_v8_H4.cs`)
**Mekanisme SL:** Identik dengan v7 (Hybrid 2-Zona)

```
// SL logic sama persis dengan v7
```
- **Perubahan utama: PENAMBAHAN FILTER H4**
```
IsH4ConfirmedBullish()   // ✅ [H4 EMA FILTER] Harga H4 harus di ATAS EMA H4
```
- **Filter Entry (v8):** `IsH1ConfirmedBullish()` + `IsH4ConfirmedBullish()` ← **BARU** + `IsEMATrendingUp_M15()`
- Filter H4 menyebabkan **jumlah trade berkurang** (sinyal lebih selektif)
- Tidak ada body ratio check

---

### v9 — Hybrid + Body Ratio SL (`Dev_Bot_v9_Body_Ratio.cs`)
**Mekanisme SL:** Identik dengan v7 (Hybrid 2-Zona)

```
// SL logic sama persis dengan v7
```
- **Perubahan utama: PENAMBAHAN BODY RATIO FILTER (tanpa H4)**
```
IsCandleStrong(rates_M15)   // ✅ [BODY RATIO FILTER] Cegah entry di candle lemah/indecision
```
- **Filter Entry (v9):** `IsH1ConfirmedBullish()` + `IsEMATrendingUp_M15()` + `IsCandleStrong()` ← **BARU**
- Filter ini menyaring candle doji/spinning top (body kecil relatif terhadap full range)
- Tidak ada filter H4

---

### v10 — Hybrid + Body Ratio + H4 (`Dev_Bot_v10_H+BR+H4.cs`)
**Mekanisme SL:** Identik dengan v7 (Hybrid 2-Zona)

```
// SL logic sama persis dengan v7
```
- **Perubahan utama: KOMBINASI LENGKAP — H4 FILTER + BODY RATIO FILTER**
```
IsH4ConfirmedBullish()    // ✅ [H4 EMA FILTER]
IsCandleStrong(rates_M15) // ✅ [BODY RATIO FILTER]
```
- **Filter Entry (v10):** `IsH1ConfirmedBullish()` + `IsH4ConfirmedBullish()` + `IsEMATrendingUp_M15()` + `IsCandleStrong()` ← **SEMUA FILTER AKTIF**
- Filter paling ketat → trade paling selektif → volume trade terendah dari semua versi

---

### 📋 Matriks Perubahan Fitur

| Fitur / Versi           | v5 | v6 | v7 | v8 | v9 | v10 |
|-------------------------|:--:|:--:|:--:|:--:|:--:|:---:|
| Static SL (per entry)   | ✅ | ❌ | ❌ | ❌ | ❌ | ❌  |
| Dynamic SL (last LL)    | ❌ | ✅ | ✅ | ✅ | ✅ | ✅  |
| Hybrid SL Cap (max SL)  | ❌ | ❌ | ✅ | ✅ | ✅ | ✅  |
| Buffer 1000 poin di LL  | ❌ | ❌ | ✅ | ✅ | ✅ | ✅  |
| Filter H1 EMA           | ✅ | ✅ | ✅ | ✅ | ✅ | ✅  |
| Filter H4 EMA           | ❌ | ❌ | ❌ | ✅ | ❌ | ✅  |
| Filter Body Ratio Candle | ❌ | ❌ | ❌ | ❌ | ✅ | ✅  |
| Session Tracking        | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅  |

---

## BAGIAN 2 — PERBANDINGAN SUMMARY PROFIT TAHUNAN (XAUUSD)

### 2A. Total Profit per Tahun (USD)

| Tahun | v5 (Statis) | v6 (Dynamic) | v7 (Hybrid) | v8 (H4) | v9 (BodyRatio) | v10 (H+BR+H4) |
|:-----:|:-----------:|:------------:|:-----------:|:-------:|:--------------:|:-------------:|
| 2020  | **$1,434.45** | $527.50    | $1,531.90   | $1,799.30 | $1,469.30   | **$1,948.45** |
| 2021  | -$674.95    | -$807.70     | -$560.30    | -$634.65  | -$83.30     | -$442.75      |
| 2022  | $835.85     | $627.85      | $931.10     | $982.85   | $982.85     | $566.25       |
| 2023  | $1,052.45   | $1,396.20    | $719.80     | $833.70   | $1,303.50   | $1,438.85     |
| 2024  | $1,431.15   | $1,644.20    | $1,466.60   | $1,386.90 | $1,259.60   | $703.10       |
| 2025  | $2,037.25   | $1,956.80    | $2,038.35   | $2,119.70 | $2,180.95   | **$2,267.35** |
| **TOTAL** | **$6,116.20** | **$5,344.85** | **$6,127.45** | **$6,487.80** | **$7,112.90** | **$6,481.25** |

> ⚠️ **Catatan 2021:** Semua versi mengalami tahun negatif. Kondisi market 2021 (sideways, banyak false breakout) tidak favorable untuk strategi SMC-based ini.

---

### 2B. Win Rate per Tahun (%)

| Tahun | v5    | v6    | v7    | v8    | v9    | v10   |
|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|
| 2020  | 55.32 | 48.94 | 55.32 | **61.11** | 55.56 | **62.86** |
| 2021  | 42.00 | 36.73 | 40.00 | 38.46 | 43.18 | 40.00 |
| 2022  | 52.38 | 50.00 | 52.38 | **54.55** | **54.55** | 50.00 |
| 2023  | 52.08 | 50.00 | 47.92 | 51.28 | 52.27 | **57.14** |
| 2024  | **57.89** | **57.89** | **57.89** | 59.38 | 57.14 | 53.33 |
| 2025  | 60.47 | **65.12** | 60.47 | 63.89 | **61.90** | **65.71** |

---

### 2C. Total Trades per Tahun

| Tahun | v5 | v6 | v7 | v8 | v9 | v10 |
|:-----:|:--:|:--:|:--:|:--:|:--:|:---:|
| 2020  | 47 | 47 | 47 | 36 | 45 | 35  |
| 2021  | 50 | 49 | 50 | 39 | 44 | 35  |
| 2022  | 42 | 42 | 42 | 33 | 33 | 32  |
| 2023  | 48 | 48 | 48 | 39 | 44 | 35  |
| 2024  | 38 | 38 | 38 | 32 | 35 | 30  |
| 2025  | 43 | 43 | 43 | 36 | 42 | 35  |
| **Total** | **268** | **267** | **268** | **215** | **243** | **202** |

> 📊 Filter H4 (v8, v10) dan Body Ratio (v9, v10) secara signifikan mengurangi jumlah trade. v10 hanya mengeksekusi ~75% dari jumlah trade v5/v7.

---

### 2D. Max Drawdown per Tahun (USD)

| Tahun | v5      | v6      | v7      | v8      | v9      | v10     |
|:-----:|:-------:|:-------:|:-------:|:-------:|:-------:|:-------:|
| 2020  | 1,475.75 | 1,683.45 | 1,475.10 | **1,324.80** | 1,325.95 | **1,175.65** |
| 2021  | 900.95  | 823.75  | 869.15  | 1,256.85 | 1,027.70 | 1,290.35 |
| 2022  | 883.90  | 964.80  | 828.55  | **436.45** | **436.45** | 516.40  |
| 2023  | 853.60  | 530.05  | 955.30  | 757.10  | 950.55  | **752.35** |
| 2024  | 904.40  | 818.65  | 891.50  | **741.50** | 892.50  | 892.50  |
| 2025  | 862.65  | 1,302.40 | 862.50  | 1,003.60 | **862.45** | **856.10** |

---

### 2E. Profit Factor per Tahun

| Tahun | v5   | v6   | v7   | v8   | v9   | v10  |
|:-----:|:----:|:----:|:----:|:----:|:----:|:----:|
| 2020  | 1.46 | 1.15 | 1.50 | 1.86 | 1.50 | **2.01** |
| 2021  | 0.84 | 0.80 | 0.86 | 0.81 | 0.98 | 0.85 |
| 2022  | 1.28 | 1.21 | 1.32 | **1.45** | **1.45** | 1.25 |
| 2023  | 1.30 | 1.48 | 1.21 | 1.31 | 1.46 | **1.69** |
| 2024  | **1.59** | 1.75 | **1.62** | 1.72 | 1.56 | 1.34 |
| 2025  | 1.79 | 1.65 | 1.79 | **2.09** | **1.89** | **2.26** |

---

## BAGIAN 3 — ANALISIS RINGKAS

### 🏆 Ranking Total Profit (2020–2025)
| Rank | Versi | Total Profit | Catatan |
|:----:|:-----:|:------------:|:--------|
| 1    | **v9** | **$7,112.90** | Body Ratio filter membatasi trade buruk tanpa H4 filter |
| 2    | **v8** | $6,487.80 | H4 filter sangat efektif di 2020 & 2025 |
| 3    | **v10** | $6,481.25 | Filter paling ketat, terlalu banyak trade terfilter di 2024 |
| 4    | **v7** | $6,127.45 | Hybrid SL tanpa filter tambahan — baseline terbaik |
| 5    | **v5** | $6,116.20 | Static SL — kompetitif karena SL per-entry terkalkulasi |
| 6    | **v6** | $5,344.85 | Dynamic SL murni tanpa cap — drawdown tertinggi di beberapa tahun |

### 🔑 Temuan Kunci
1. **2021 adalah tahun "stress test" universal** — semua versi loss, menandakan kondisi market 2021 (sideways post-bull-run) tidak cocok untuk SMC breakout strategy
2. **v9 (Body Ratio saja) mengungguli v10 (Body Ratio + H4)** — tambahan filter H4 di v10 over-filter sinyal bagus di 2022 dan 2024
3. **v8 (H4 saja) memberikan Profit Factor terbaik di 2025 (2.09)** — filter H4 sangat efektif di tren kuat
4. **v10 memiliki PF tertinggi di 2020 (2.01) dan 2025 (2.26)** — di tahun tren kuat, semua filter sinergi sempurna
5. **v6 memiliki drawdown tertinggi 2020 ($1,683)** — Dynamic SL murni tanpa cap bisa sangat lebar di market volatile
6. **Volume trade berkurang ~24% dari v5→v8, dan ~25% lagi dari v8→v10** — trade lebih sedikit tapi tidak selalu lebih menguntungkan

### ⚡ Rekomendasi Arah Pengembangan
- **Best overall:** v9 (Hybrid SL + Body Ratio) — keseimbangan antara selectivity dan coverage
- **Best trending market:** v10 (semua filter) — dominan di tahun tren kuat
- **Most robust SL design:** v7/v8/v9/v10 (Hybrid Zona dengan cap) vs. v5 (static) dan v6 (dynamic tanpa proteksi)

---
*Laporan dihasilkan berdasarkan data backtest XAUUSD dari file Backtest_Summary_*.csv di folder backtest_v5 s/d backtest_v10*  
*Analisis source code berdasarkan pembacaan langsung entry logic pada area BoS Bullish/Bearish di setiap versi*
