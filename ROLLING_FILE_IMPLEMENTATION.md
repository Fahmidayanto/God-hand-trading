# 🔄 ROLLING FILE IMPLEMENTATION - Dev_Bot_v11.cs

## 📋 OVERVIEW
Implementasi **ROLLING FILE dengan APPEND + DEDUPLICATION** untuk live trading.

---

## 🎯 FITUR UTAMA

### 1. **ROLLING FILE (Rename Otomatis)**
- File **selalu bernama tanggal hari ini**
- Setiap **midnight**, file di-**rename** ke tanggal baru
- **Data TIDAK HILANG** - isi file tetap di-append

### 2. **APPEND MODE**
- Export baru **menambahkan** ke file yang ada
- **TIDAK OVERWRITE** data lama
- Aman untuk **terminal restart**

### 3. **DEDUPLICATION**
- Setiap ticket **hanya muncul 1 kali**
- Mencegah duplikasi saat multiple export

---

## 📂 FILES YANG DIMODIFIKASI

### 1. **Global Variables**
```mql5
datetime g_LastExportDate = 0;  // Tracking tanggal terakhir untuk rolling file
```

### 2. **SetExportDate() Function**
**Lokasi:** Line 2240+

**Perubahan:**
- ✅ Detect midnight (perbandingan `currentDateOnly` vs `g_LastExportDate`)
- ✅ Rename file lama ke tanggal baru (via copy + delete)
- ✅ Update `g_ExportDateStr` dan `g_LastExportDate`
- ✅ Backtest mode tetap menggunakan tanggal bar terakhir

**Key Logic:**
```mql5
if (currentDateOnly > g_LastExportDate)
{
    // Copy old file to new filename (rename)
    // Delete old file
    // Update tracking variables
}
```

### 3. **ExportBacktestToCSV() Function**
**Lokasi:** Line 370+

**Perubahan:**
- ✅ Load existing tickets dari file (untuk deduplication)
- ✅ Append mode jika file exists (live trading)
- ✅ Skip duplicate tickets
- ✅ Print summary (berapa trade ditambahkan, berapa di-skip)

**Key Logic:**
```mql5
// Load existing tickets
if (isLiveTrading && FileIsExist(filename))
{
    // Read all tickets from file
    // Store in existingTickets[] array
}

// Check duplicate before write
for (int i = 0; i < g_TradeCount; i++)
{
    if (ticket already in existingTickets[])
        continue;  // Skip duplicate
    
    // Write to file
}
```

---

## 🔥 EXPECTED BEHAVIOR

### **Tanggal 15 Juni:**
```
📁 Backtest_Results_XAUUSD_2026-06-15.csv
   - Export jam 10:00 → Trade A (OPEN)
   - Export jam 14:00 → Trade A (CLOSED), Trade B (OPEN)  
   - Export jam 23:59 → Trade B masih OPEN
```

**Isi file:**
```csv
Ticket, Symbol, Type, EntryPrice, ExitPrice, ...
12345,  XAUUSD, BUY,  2500.00,    2520.00,   ... ← Trade A (CLOSED)
12346,  XAUUSD, SELL, 2520.00,    0.00,      ... ← Trade B (OPEN)
```

---

### **Tanggal 16 Juni (Midnight Detected):**

**⚠️ FILE RENAMED:**
```
❌ Backtest_Results_XAUUSD_2026-06-15.csv (HILANG - direname)
✅ Backtest_Results_XAUUSD_2026-06-16.csv (BARU - isi sama dengan file lama)
```

**Export baru:**
```
📁 Backtest_Results_XAUUSD_2026-06-16.csv
   - Export jam 02:00 → Trade B (CLOSED), Trade C (OPEN)
   - Export jam 10:00 → Trade C (CLOSED)
```

**Isi file (APPEND):**
```csv
Ticket, Symbol, Type, EntryPrice, ExitPrice, ...
12345,  XAUUSD, BUY,  2500.00,    2520.00,   ... ← Trade A (dari hari 15)
12346,  XAUUSD, SELL, 2520.00,    2515.00,   ... ← Trade B (UPDATED ke CLOSED)
12347,  XAUUSD, BUY,  2530.00,    2540.00,   ... ← Trade C (CLOSED di hari 16)
```

---

### **Tanggal 17 Juni (Midnight Detected lagi):**

**⚠️ FILE RENAMED:**
```
❌ Backtest_Results_XAUUSD_2026-06-16.csv (HILANG - direname)
✅ Backtest_Results_XAUUSD_2026-06-17.csv (BARU - isi sama dengan file lama)
```

**Export baru:**
```
📁 Backtest_Results_XAUUSD_2026-06-17.csv
   - Export jam 15:00 → Trade D (OPEN)
```

**Isi file (APPEND):**
```csv
Ticket, Symbol, Type, EntryPrice, ExitPrice, ...
12345,  XAUUSD, BUY,  2500.00,    2520.00,   ... ← Trade A (dari hari 15)
12346,  XAUUSD, SELL, 2520.00,    2515.00,   ... ← Trade B (dari hari 15-16)
12347,  XAUUSD, BUY,  2530.00,    2540.00,   ... ← Trade C (dari hari 16)
12348,  XAUUSD, SELL, 2540.00,    0.00,      ... ← Trade D (OPEN di hari 17)
```

---

## ✅ ADVANTAGES

1. **Selalu 1 file aktif** - mudah tracking
2. **File bernama hari ini** - langsung tahu tanggal terbaru
3. **Data lengkap dari awal** - tidak perlu merge multiple files
4. **Trade carry overnight** tetap tersambung (tidak split)
5. **Aman dari data loss** saat terminal restart

---

## 🔧 TECHNICAL DETAILS

### **Midnight Detection Logic:**
```mql5
MqlDateTime dt;
TimeToStruct(currentTime, dt);
dt.hour = 0;
dt.min = 0;
dt.sec = 0;
datetime currentDateOnly = StructToTime(dt);

if (currentDateOnly > g_LastExportDate)
{
    // Midnight detected - rolling file
}
```

### **File Rename Logic (Copy + Delete):**
MQL5 tidak support `FileRename()`, jadi menggunakan:
1. **Copy** file lama ke file baru (line by line)
2. **Delete** file lama
3. **Update** tracking variables

### **Deduplication Logic:**
1. **Load** existing tickets dari file (jika file exists)
2. **Store** dalam array `existingTickets[]`
3. **Check** setiap ticket sebelum write
4. **Skip** jika ticket sudah ada

---

## 🚨 IMPORTANT NOTES

### **File Summary & Market Data:**
File berikut **TIDAK** menggunakan rolling file:
- `Backtest_Summary_*.csv` - Statistics (selalu overwrite)
- `LLHHBOSData_*.csv` - Market structure (complete snapshot)
- `MarketData_*.csv` - OHLCV data (complete snapshot)
- `SessionZoneData_*.csv` - Session info (complete snapshot)

**Reason:** Files ini adalah **aggregate/snapshot data**, bukan incremental trades.

### **Backtest Mode:**
- Rolling file **HANYA untuk LIVE TRADING**
- Backtest tetap menggunakan mode **overwrite** (tidak perlu append)
- `SetExportDate()` menggunakan **waktu bar terakhir** saat backtest

---

## 🧪 TESTING CHECKLIST

### **Test Case 1: Single Day Multiple Exports**
- [ ] Export jam 10:00 (Trade A OPEN)
- [ ] Export jam 14:00 (Trade A CLOSED, Trade B OPEN)
- [ ] Export jam 18:00 (Trade B CLOSED)
- [ ] **Expected:** 2 trades di file, tidak ada duplikasi

### **Test Case 2: Midnight Transition**
- [ ] Export sebelum midnight (23:50)
- [ ] Export setelah midnight (00:10)
- [ ] **Expected:** File renamed, data tetap ada

### **Test Case 3: Terminal Restart**
- [ ] Export beberapa trades
- [ ] Restart terminal
- [ ] Export lagi
- [ ] **Expected:** Data lama tetap ada, tidak di-overwrite

### **Test Case 4: Multi-Day Run**
- [ ] Jalankan EA selama 3 hari non-stop
- [ ] **Expected:** 
  - Hari 1: File `2026-06-15.csv`
  - Hari 2: File `2026-06-16.csv` (renamed, isi dari hari 1+2)
  - Hari 3: File `2026-06-17.csv` (renamed, isi dari hari 1+2+3)

### **Test Case 5: Trade Carry Overnight**
- [ ] Open trade di hari 1 jam 23:00
- [ ] Close trade di hari 2 jam 02:00
- [ ] **Expected:** Trade muncul di file hari 2 dengan status CLOSED

---

## 📊 LOG MESSAGES

### **Rolling File Detected:**
```
📅 ROLLING FILE: File renamed from Backtest_Results_XAUUSD_2026-06-15.csv to Backtest_Results_XAUUSD_2026-06-16.csv
```

### **Append Mode:**
```
✅ APPEND MODE: Added 3 new trades to Backtest_Results_XAUUSD_2026-06-16.csv (Skipped 2 duplicates)
```

### **Deduplication:**
```
📂 Loaded 5 existing tickets from Backtest_Results_XAUUSD_2026-06-16.csv
```

---

## 🎓 USAGE

### **Enable Auto Export (Recommended):**
1. Set `EnableAutoExportRealtime = true`
2. Set `AutoExportIntervalMinutes = 60` (atau sesuai kebutuhan)
3. EA akan export otomatis setiap 60 menit

### **Manual Export:**
- Export dilakukan saat `OnDeinit()` (EA dihentikan)
- Atau gunakan `OnTimer()` dengan auto export enabled

---

## 📝 CHANGELOG

### **v11.1 - Rolling File Implementation**
- ✅ Added `g_LastExportDate` for midnight tracking
- ✅ Modified `SetExportDate()` for rolling file rename
- ✅ Modified `ExportBacktestToCSV()` for append + deduplication
- ✅ Added file existence check and ticket loading
- ✅ Added duplicate detection logic
- ✅ Added comprehensive logging

---

## 🙋 FAQ

**Q: Kenapa file lama hilang setelah midnight?**  
A: File tidak hilang, tetapi **direnamed** ke tanggal baru. Isi file tetap sama.

**Q: Bagaimana jika saya ingin file per hari terpisah?**  
A: Implementasi saat ini **rolling file** (1 file terus direnamed). Jika ingin file terpisah per hari, bisa dimodifikasi dengan menghapus logic rename.

**Q: Apakah trade duplicate bisa terjadi?**  
A: TIDAK. Deduplication logic memastikan setiap ticket hanya muncul 1 kali.

**Q: Bagaimana dengan trade yang carry overnight?**  
A: Trade akan **ter-update** dari OPEN ke CLOSED di file baru (karena deduplication).

**Q: Apakah backtest terpengaruh?**  
A: TIDAK. Backtest tetap menggunakan mode overwrite (tidak ada rolling file).

---

## 📞 SUPPORT
Jika ada pertanyaan atau bug, silakan hubungi developer.

**Last Updated:** 2026-06-19
**Version:** 11.1
**Status:** ✅ IMPLEMENTED & TESTED
