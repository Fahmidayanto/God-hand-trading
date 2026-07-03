## 📐 ARCHITECTURE OVERVIEW (HYBRID APPROACH)```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MT5 ECOSYSTEM (SINGLE-TRACK SYSTEM)                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │         MetaTrader 5 Terminal (Live Market Data)                │    │
│  │  • OHLCV bars forming (M15/H1/H4)                              │    │
│  │  • Price updates every tick                                     │    │
│  └────────────────────────────────┬───────────────────────────────┘    │
│                                   │                                    │
│                                   ▼                                    │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  Dev_Bot_v11.cs (MQL5 EA)                                       │    │
│  │  (Active - Deteksi + Trading)                                   │    │
│  │  TRACK 2 SOURCE                                                 │    │
│  │                                                                 │    │
│  │  • HH/LL/CHoCH/BoS detection                                   │    │
│  │  • Export 8 CSV per M15 close                                   │    │
│  │  • Visual markers on chart                                      │    │
│  │  • Trading execution (Buy/Sell)                                 │    │
│  └────────────────────────────────┬───────────────────────────────┘    │
│                                   │                                    │
│                                   ▼ CSV Files (Backup)                 │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  Backtest_result/                                               │    │
│  │  ├── Backtest_Results_*.csv     ├── MarketData_M15_*.csv        │    │
│  │  ├── Backtest_Summary_*.csv     ├── MarketData_H1_*.csv         │    │
│  │  ├── LLHHBOSData_*.csv          ├── MarketData_H4_*.csv         │    │
│  │  ├── MarketStructure_*.csv      └── SessionZone_*.csv           │    │
│  └────────────────────────────────┬───────────────────────────────┘    │
│                                   │                                    │
│                                   ▼                                    │
│                     CSV Watcher Service (ON) 📁                        │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                 KNOWLEDGE BASE (Storage)                        │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │  LanceDB Collections:                                     │  │   │
│  │  │  • historical_structures (pattern similarity search)     │  │   │
│  │  │  • market_conditions (OHLCV + indicators)                │  │   │
│  │  │  • session_patterns (session behaviors)                  │  │   │
│  │  │  • trade_outcomes (ML training data)                     │  │   │
│  │  │                                                           │  │   │
│  │  │  Neon PostgreSQL Tables:                                  │  │   │
│  │  │  └─ Audit Trail (from TRACK 2 - [ACTIVE]):                │  │   │
│  │  │     • marketdata_xauusd_m15 / h1 / h4                     │  │   │
│  │  │     • llhhbosdata_xauusd                                  │  │   │
│  │  │     • backtest_results_xauusd                             │  │   │
│  │  │     • sessionzone_xauusd                                  │  │   │
│  │  │     • csv_load_log (tracking)                            │  │   │
│  │  │     • cross_validation (Track 1 vs Track 2)             │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                              ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                    ORCHESTRATOR AGENT                          │   │
│  │  (Coordinator - receives market data & triggers discussion)    │   │
│  └────────────────┬──────────────────────────┬────────────────────┘   │
│                   │                          │                        │
│         ┌─────────┴─────────┬────────────────┴────────┬──────────┐    │
│         ▼                   ▼                         ▼          ▼    │
│  ┏━━━━━━━━━━━━━┓    ┏━━━━━━━━━━━━━┓    ┏━━━━━━━━━━━━━┓  ┏━━━━━━━┓  │
│  ┃  MARKET     ┃    ┃  ML MODEL   ┃    ┃   RISK      ┃  ┃ SENT. ┃  │
│  ┃ STRUCTURE   ┃    ┃ PREDICTION  ┃    ┃ MANAGEMENT  ┃  ┃ AGENT ┃  │
│  ┃   AGENT     ┃    ┃   AGENT     ┃    ┃   AGENT     ┃  ┃       ┃  │
│  ┗━━━━━━━━━━━━━┛    ┗━━━━━━━━━━━━━┛    ┗━━━━━━━━━━━━━┛  ┗━━━━━━━┛  │
│         │                   │                         │          │    │
│         └─────────┬─────────┴────────────────┬────────┴──────────┘    │
│                   ▼                          ▼                        │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                    CONSENSUS ENGINE                            │   │
│  │  • Weighted voting system                                      │   │
│  │  • Conflict resolution logic                                   │   │
│  │  • Confidence aggregation                                      │   │
│  └────────────────────────────────┬───────────────────────────────┘   │
│                                   ▼                                   │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                   EXECUTION AGENT                              │   │
│  │  • Order monitoring / logging                                  │   │
│  │  • Position management                                         │   │
│  │  • Risk controls (max position size, daily loss limit)         │   │
│  └────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 DETAILED FLOW: DUAL-TRACK EXECUTION

### **OVERVIEW: HYBRID APPROACH**

```
PRIMARY PATH (Real-time Trading - Fast ⚡):
MT5 Python API → Structure Detector → LangGraph → Agents → Execute
└─> Store: realtime_ohlcv, realtime_structures, trades (PostgreSQL)

SECONDARY PATH (Backup & Audit - Safe 📁):
Dev_Bot_v11.cs → CSV Export → Daily Batch Load → Audit Tables (PostgreSQL)
└─> Store: historical_*_audit tables, cross_validation

BENEFITS:
✅ Ultra-fast trading (no file I/O latency)
✅ Independent audit trail (compliance, debugging)
✅ Cross-validation capability (compare Track 1 vs Track 2)
✅ Visual monitoring on MT5 chart (Dev_Bot_v11.cs)
```

---

## 🚀 **PENJELASAN MUDAH: Ketika Anda Menjalankan Backend dan Frontend**

### **LANGKAH 1: Anda Menjalankan Backend**

Anda membuka terminal dan jalankan:
```bash
cd .\backend\
python -m uvicorn valuecell.server.main:app --host 0.0.0.0 --port 8000
```

**Yang Terjadi:**
- Backend Python dimulai dan siap menerima request
- Backend bersiap untuk berkomunikasi dengan sistem trading

---

### **LANGKAH 2: Otomatis - MetaTrader5.exe Membuka**

Begitu backend dimulai, **MetaTrader5.exe secara otomatis terbuka**.

**Kenapa?** Karena kode backend ditulis sedemikian rupa sehingga saat startup, dia langsung membuka koneksi ke MetaTrader5.

**Apa yang terjadi di MetaTrader5?**
- MetaTrader5 terminal membuka
- Di dalam MT5, ada sebuah program kecil (disebut Expert Advisor atau EA) yang bernama `Dev_Bot_v11.cs` yang **sudah di-compile** (seperti halnya Anda mengubah resep dari bahasa Inggris ke bahasa Indonesia - sudah jadi dan siap digunakan)
- Program kecil ini **otomatis mulai berjalan**

---

### **LANGKAH 3: Dev_Bot Mulai Mendeteksi Struktur Pasar**

Program `Dev_Bot_v11.cs` yang sudah running di MT5 sekarang:

**Setiap detik:**
- Mengamati harga XAUUSD (emas) yang berubah-ubah
- Mendeteksi pola-pola tertentu dalam pergerakan harga
- Mencari pola-pola seperti: "harga naik lebih tinggi dari sebelumnya" atau "harga turun lebih rendah dari sebelumnya"

**Setiap 15 menit (saat candle M15 menutup):**
- Program membuat catatan/export data ke file CSV
- File-file ini berisi:
  - Data pola-pola yang ditemukan (HH/LL/CHoCH/BoS)
  - Data harga-harga yang direkam
- File disimpan di folder `Backtest_result/`

---

### **LANGKAH 4: Anda Menjalankan Frontend**

Anda membuka terminal lain dan jalankan:
```bash
cd .\frontend\
npm run dev
```

**Yang Terjadi:**
- Frontend (dashboard/aplikasi web) dimulai
- Frontend berjalan di port 3000 (alamat: `http://localhost:3000`)
- Frontend siap menampilkan informasi di layar

---

### **LANGKAH 5: Frontend Berkomunikasi dengan Backend**

Ketika Anda membuka dashboard (`http://localhost:3000`) di browser:

**Frontend akan bertanya ke Backend:**
- "Backend, apa signal terbaru?"
- "Backend, berapa harga sekarang?"
- "Backend, apa status akun saya?"

**Backend akan menjawab:**
- Membaca data dari MetaTrader5 yang sedang berjalan
- Atau membaca file CSV yang di-export oleh Dev_Bot
- Mengirimkan jawaban ke Frontend

**Frontend menampilkan:**
- Harga terkini
- Sinyal trading (BUY/SELL)
- Status akun
- Grafik-grafik

---

## 📊 **Alur Singkat:**

```
Anda jalankan Backend
    ↓
MetaTrader5.exe terbuka (otomatis)
    ↓
Dev_Bot_v11.cs mulai bekerja
    ├─ Pantau harga setiap detik
    └─ Export data setiap 15 menit
    ↓
Anda jalankan Frontend
    ↓
Dashboard terbuka di http://localhost:3000
    ↓
Frontend tanya Backend untuk data
    ↓
Backend ambil data dari MT5 atau CSV
    ↓
Frontend tampilkan data di dashboard
```

---

## 🎯 **Apa yang Penting Diingat:**

| Komponen | Fungsi | Status |
|----------|--------|--------|
| **Backend** | Jembatan antara MetaTrader5 dan Dashboard | Running di port 8000 |
| **MetaTrader5** | Program trading yang membaca harga real-time | Terbuka otomatis |
| **Dev_Bot_v11.cs** | Program yang mendeteksi pola pasar & export CSV | Berjalan di MT5 |
| **Frontend** | Tampilan dashboard yang cantik | Running di port 3000 |
| **CSV Files** | Catatan data yang di-export Dev_Bot (TRACK 2) | Di folder `Backtest_result/` |

---

## ✅ **Kesimpulannya:**

1. ✅ Anda jalankan **Backend** (Port 8000)
2. ✅ **MetaTrader5** otomatis terbuka
3. ✅ **Dev_Bot** mulai bekerja dan export data ke CSV (TRACK 2 - Backup)
4. ✅ Anda jalankan **Frontend** (Port 3000)
5. ✅ **Dashboard** tampil dan menampilkan data dari Backend

**Semuanya bekerja bersama untuk menunjukkan info trading kepada Anda!** 😊

---

## 💡 **Catatan Penting:**

- **TRACK 1 (Real-time)**: Backend menggunakan MT5 Python API untuk akses data real-time (lebih cepat)
- **TRACK 2 (Backup)**: Dev_Bot export ke CSV setiap 15 menit untuk audit & backup
- **DUAL-TRACK**: Kedua jalur berjalan independen sehingga sistem lebih stabil
- **Tanpa AI_Trading_Server**: Sistem ini bekerja sempurna tanpa memerlukan AI_Trading_Server

---

## 📌 **TRACK 1 vs TRACK 2 - Penjelasan Mudah**

### **🚀 TRACK 1 (Real-time Trading - Jalur Cepat)**

**Ibarat seperti:**
- Anda melihat harga emas **langsung di layar MT5**
- Melihat grafik live yang berubah **setiap detik**
- Langsung ngambil keputusan **"Ayo beli!" atau "Ayo jual!"**
- Eksekusi order **langsung tanpa delay**

**Yang terjadi:**
- Backend Python terhubung ke MT5
- Ambil data harga **real-time** (setiap saat)
- Analisis pola pasar **langsung**
- Buat keputusan trading **cepat**
- Eksekusi order **langsung**

**Kecepatan:** ⚡ SUPER CEPAT (detik-detikan)

---

### **📁 TRACK 2 (Backup & Catatan - Jalur Backup)**

**Ibarat seperti:**
- Seperti **menyimpan catatan harian** (diary) tentang apa yang terjadi di trading
- Setiap 15 menit, Anda tulis: "Harga naik, aku lihat pola HH"
- Menyimpan catatan di **file folder** (bukan real-time)
- Catatan digunakan untuk **audit dan check-ulang**

**Yang terjadi:**
- Dev_Bot (sudah jadi program di MT5) **memantau harga**
- Setiap 15 menit sekali, **mencatat pola-pola** yang dilihat
- Menyimpan catatan ke **file CSV** di folder `Backtest_result/`
- Catatan ini digunakan untuk **cross-check** apakah keputusan benar

**Kecepatan:** 📁 ADA DELAY (setiap 15 menit)

---

## 🔄 **Bedanya Dimana?**

| Aspek | TRACK 1 | TRACK 2 |
|-------|---------|---------|
| **Kecepatan** | ⚡ Real-time (setiap detik) | 📁 Batch (setiap 15 menit) |
| **Dari mana data** | Langsung dari MT5 Python API | File CSV yang di-export |
| **Tujuan** | Ambil keputusan & eksekusi trading | Backup & audit trail |
| **Kapan dipakai** | Untuk trading sehari-hari | Untuk verifikasi & laporan |
| **Delay** | Tidak ada | Ada (15 menit) |
| **Analoginya** | Seperti melihat monitor live | Seperti membaca laporan |


## 🎯 **Kapan Backend Aktif:**

Ketika backend dijalankan:

```
Backend dijalankan
    ↓
mt5.initialize() → MetaTrader5.exe TERBUKA
    ↓
┌─────────────────────────────────────────┐
│                                         │
├─ TRACK 1 AKTIF ⚡                      │
│  └─ Backend ambil data dari MT5 API     │
│     Real-time setiap detik              │
│                                         │
├─ TRACK 2 AKTIF 📁                      │
│  └─ Dev_Bot di MT5 export CSV           │
│     Setiap M15 close                    │
│                                         │
└─────────────────────────────────────────┘
```

**Jadi saat backend aktif, KEDUANYA berjalan BERSAMAAN! 🎯**

---

## 🔍 **DETAIL TRACK 1 - Dari Architecture Overview ke MT5 Data Adapter**

### **Step 1: Backend Terhubung ke MetaTrader5**

```
Backend Python (Port 8000)
    ↓
mt5.initialize()
    ↓
MetaTrader5.exe
    ↓
Live Market Data (Harga real-time)
```

Backend membuka koneksi **langsung** ke MetaTrader5 saat startup. Bukan lewat file CSV, tapi **langsung API**.

---

### **Step 2: Data Harga Mengalir ke MT5 Data Adapter**

```
MetaTrader5 Terminal
├─ Real-time tick data streaming
├─ OHLCV bars forming (M15/H1/H4)
└─ Price updates every tick
    ↓
TRACK 1: Real-time ⚡
    ↓
MT5 Python API
├─ copy_rates_from_pos()  ← Ambil data bars
├─ copy_rates_range()      ← Ambil range harga
└─ ...
    ↓
MT5 DATA ADAPTER (di Python)
```

---

### **Step 3: MT5 Data Adapter Melakukan 4 Hal Penting**

**MT5 DATA ADAPTER adalah "jembatan" antara MetaTrader5 dan sistem AI. Dia melakukan:**

#### **1️⃣ Ambil Data Harga Real-time**
```
MT5 Python API (copy_rates_from_pos)
    ↓
Dapatkan: OHLCV (Open, High, Low, Close, Volume)
```
- Ambil data bars terbaru
- Format: [1400.50, 1401.20, 1399.80, 1400.75, 1000]
- Update: Setiap detik (real-time)

#### **2️⃣ Deteksi Pola Pasar (In-Memory)**
```
Market Structure Detector (in-memory)
    ↓
Cari pola-pola:
├─ HH (Higher High) = Harga baru naik lebih tinggi
├─ LL (Lower Low) = Harga baru turun lebih rendah
├─ CHoCH = Change of Character (balik arah)
└─ BoS = Break of Structure (tembus support/resistance)
```

#### **3️⃣ Deteksi Event Real-time**
```
Real-time event detection
    ↓
Deteksi saat terjadi:
├─ Harga menembus resistance → EVENT!
├─ Harga membentuk HH baru → EVENT!
├─ Trend berubah arah → EVENT!
└─ ...
```

#### **4️⃣ Normalisasi Data**
```
Data normalization (MT5 → internal format)
    ↓
Ubah format MT5 menjadi format internal system
├─ Standardisasi satuan
├─ Tambah timestamp
├─ Tambah metadata
└─ Siap untuk agents
```

---

### **Step 4: Karakteristik TRACK 1**

```
✅ NO CSV DEPENDENCY (Pure API)
   ├─ Tidak perlu tunggu file CSV
   ├─ Data langsung dari terminal
   └─ SUPER CEPAT

✅ IN-MEMORY PROCESSING
   ├─ Semua di RAM
   ├─ Tidak ada file I/O delay
   └─ Instant detection

✅ NO FILE I/O
   ├─ Tidak baca file
   ├─ Tidak tulis file
   └─ Murni real-time streaming
```

---

### **Ibarat Dunia Nyata:**

```
TRACK 1 seperti PEMANDU LALU LINTAS yang STAND-BY:
├─ Berdiri di tepi jalan
├─ Lihat lampu traffic LANGSUNG
├─ Lihat kendaraan LANGSUNG
├─ Buat keputusan LANGSUNG
└─ NO DELAY!

Bukan seperti pemandu yang baca laporan tua:
├─ Laporan 15 menit yang lalu
├─ Sudah expired
├─ Keputusan bisa salah
└─ Ada delay
```

---

### **Flow Lengkap TRACK 1:**

```
MetaTrader5.exe (Real-time)
    ↓
MT5 Python API
    ├─ get_rates()
    ├─ get_ticks()
    └─ streaming
    ↓
MT5 DATA ADAPTER
    ├─ 1. Ambil harga real-time
    ├─ 2. Deteksi pola (HH/LL/CHoCH/BoS)
    ├─ 3. Deteksi event real-time
    └─ 4. Normalisasi data
    ↓
KNOWLEDGE BASE (PostgreSQL)
    ├─ realtime_ohlcv
    ├─ realtime_structures
    └─ realtime events
    ↓
ORCHESTRATOR AGENT
    ├─ Terima data real-time
    └─ Trigger 4 agents
    ↓
4 AGENTS (Parallel)
    ├─ Market Structure Agent (25%)
    ├─ ML Prediction Agent (40%)
    ├─ Risk Management Agent (15%)
    └─ Sentiment Agent (20%)
    ↓
CONSENSUS ENGINE
    ├─ Weighted voting
    └─ Buat keputusan
    ↓
EXECUTION AGENT
    ├─ order_send()
    └─ Eksekusi trading
    ↓
MetaTrader5.exe (Place Orders)
```

---

### **Perbedaan TRACK 1 vs TRACK 2 di Tahap Adapter:**

| Tahap | TRACK 1 (Real-time) | TRACK 2 (Backup) |
|-------|-----------------|-----------|
| **Data Source** | MT5 Python API (direct) | CSV file dari Dev_Bot |
| **Update Interval** | Setiap detik (real-time) | Setiap M15 close |
| **Delay** | ❌ Tidak ada | ✅ Ada (15 menit) |
| **Processing** | In-memory (instant) | Batch load (scheduled) |
| **File I/O** | ❌ Tidak ada | ✅ Ada (baca CSV) |
| **Tujuan** | ✅ Trading execution | ✅ Audit & backup |

---

## ✅ **Kesimpulan TRACK 1:**

**TRACK 1 adalah:**
- Data **langsung dari terminal** → **Tidak lewat file**
- Deteksi pola **instant** → **Tidak tunggu 15 menit**
- Execution **cepat** → **Realtime order**
- **Pure API** → **Tanpa CSV**

**MT5 Data Adapter adalah "otak" yang:**
1. Ambil data harga
2. Cari pola
3. Deteksi event
4. Siapkan untuk agents

**Keseluruhan TRACK 1 dari MT5 sampai Execution berjalan REAL-TIME dan INDEPENDEN dari TRACK 2! ⚡**

---

## 🔌 **ALUR LENGKAP TRACK 1: Data Ke Penyimpanan**

```
MT5 Python API
    ↓
MT5 DATA ADAPTER (Process Data):
├─ 1. Ambil data harga real-time
├─ 2. Deteksi pola (HH/LL/CHoCH/BoS)
├─ 3. Deteksi event real-time
└─ 4. Normalisasi data
    ↓ SAVE TO
KNOWLEDGE BASE:
├─ LanceDB Collections
│  ├─ historical_structures (pattern similarity search)
│  ├─ market_conditions (OHLCV + indicators)
│  ├─ session_patterns (session behaviors)
│  └─ trade_outcomes (ML training data)
│
└─ Neon PostgreSQL (realtime_* tables)
   ├─ realtime_ohlcv (data harga terkini)
   ├─ realtime_structures (pola yang terdeteksi)
   ├─ trades (record eksekusi order)
   ├─ agent_decisions (keputusan dari 4 agents)
   ├─ state_machine (state sistem saat ini)
   └─ agent_performance (performa agents)
```

**Hasil:** Data sudah siap disimpan ke database untuk digunakan Orchestrator Agent dan 4 Agents dalam milliseconds! ⚡

---

## ✅ **Ringkasan TRACK 1:**

| Tahap | Apa yang Terjadi | Kecepatan |
|-------|-----------------|----------|
| **MT5 Python API** | Ambil data dari terminal | Real-time |
| **MT5 DATA ADAPTER** | Proses & deteksi pola | Milliseconds |
| **KNOWLEDGE BASE** | Simpan ke LanceDB + PostgreSQL | Real-time |
| **Orchestrator Agent** | Terima data & koordinasi agents | Milliseconds |
| **4 Agents** | Analisis & buat keputusan | Milliseconds |
| **Execution Agent** | Eksekusi order di MT5 | Milliseconds |

**TOTAL**: Dari data harga sampai order eksekusi = **KURANG DARI 1 DETIK! ⚡⚡⚡**

---

## 📊 **TRACK 1: Tabel dan Kolom yang Diinsert Saat Deteksi (Dari Kode)**

### **1️⃣ TABLE: `realtime_ohlcv` - Data Harga Real-time**

**Sumber:** MT5 Python API
**Fungsi:** Menyimpan data harga (OHLCV) dari MT5

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | SERIAL PRIMARY KEY | ID unik |
| timestamp | TIMESTAMP NOT NULL | Waktu data |
| symbol | VARCHAR(10) | XAUUSD |
| timeframe | VARCHAR(10) | M15, H1, H4 |
| open | DECIMAL(10,2) | Harga buka |
| high | DECIMAL(10,2) | Harga tertinggi |
| low | DECIMAL(10,2) | Harga terendah |
| close | DECIMAL(10,2) | Harga tutup |
| volume | BIGINT | Volume |
| ema200 | DECIMAL(10,2) | EMA 200 periode |
| source | VARCHAR(20) | 'mt5_api' |
| created_at | TIMESTAMP | Waktu insert (auto) |

**Constraint:** UNIQUE(timestamp, symbol, timeframe, source)

---

### **2️⃣ TABLE: `realtime_structures` - Pola Pasar Terdeteksi**

**Sumber:** MT5 Data Adapter (Market Structure Detector)
**Fungsi:** Menyimpan event deteksi pola (HH/LL/CHoCH/BoS)

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | SERIAL PRIMARY KEY | ID unik |
| timestamp | TIMESTAMP NOT NULL | Waktu deteksi |
| symbol | VARCHAR(10) | XAUUSD |
| timeframe | VARCHAR(10) | M15, H1, H4 |
| event_type | VARCHAR(20) | BoS, CHoCH, HH, LL |
| direction | VARCHAR(10) | Bullish atau Bearish |
| price | DECIMAL(10,2) | Harga saat event |
| phase | VARCHAR(50) | BOS_CONFIRMED, CHOCH_DETECTED |
| session | VARCHAR(20) | London, New York, Asia |
| source | VARCHAR(20) | 'python_detector' |
| triggered_trade | BOOLEAN | Apakah trigger trade? |
| created_at | TIMESTAMP | Waktu insert (auto) |

---

### **3️⃣ TABLE: `agent_decisions` - Keputusan 4 Agents**

**Sumber:** Orchestrator Agent (output dari 4 agents)
**Fungsi:** Menyimpan analisis dari MarketStructure, ML, RiskManagement, Sentiment

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | SERIAL PRIMARY KEY | ID unik |
| timestamp | TIMESTAMP NOT NULL | Waktu keputusan |
| symbol | VARCHAR(10) | XAUUSD |
| timeframe | VARCHAR(10) | M15 |
| market_structure | JSONB | Output MarketStructureAgent |
| ml_prediction | JSONB | Output MLPredictionAgent |
| risk_analysis | JSONB | Output RiskManagementAgent |
| sentiment | JSONB | Output SentimentAgent |
| consensus_score | DECIMAL(5,4) | Skor (0-1), default 0.6 |
| final_decision | VARCHAR(20) | BUY, SELL, HOLD |
| trade_executed | BOOLEAN | Order sudah dieksekusi? |
| ticket | BIGINT | MT5 ticket number |
| error | TEXT | Pesan error jika ada |

---

### **4️⃣ TABLE: `trades` - Record Eksekusi Order**

**Sumber:** Execution Agent
**Fungsi:** Menyimpan semua order yang dieksekusi

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| ticket | BIGINT PRIMARY KEY | MT5 ticket number |
| timestamp | TIMESTAMP NOT NULL | Waktu entry |
| symbol | VARCHAR(10) | XAUUSD |
| type | VARCHAR(10) | BUY atau SELL |
| entry_price | DECIMAL(10,2) | Harga entry |
| stop_loss | DECIMAL(10,2) | SL dari RiskManagementAgent |
| take_profit | DECIMAL(10,2) | TP dari RiskManagementAgent |
| lot_size | DECIMAL(10,2) | Ukuran lot |
| consensus_score | DECIMAL(5,4) | Skor agreement 4 agents |
| agent_votes | JSONB | Vote dari setiap agent |
| close_time | TIMESTAMP | Waktu order ditutup |
| close_price | DECIMAL(10,2) | Harga close |
| profit | DECIMAL(10,2) | Profit/Loss |
| outcome | VARCHAR(20) | WIN, LOSS, BREAKEVEN |

---

### **5️⃣ TABLE: `state_machine` - State Sistem Saat Ini**

**Sumber:** Market Structure Detector
**Fungsi:** Tracking state struktur pasar (HH/LL progression)

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | SERIAL PRIMARY KEY | ID unik |
| timestamp | TIMESTAMP NOT NULL | Waktu update |
| timeframe | VARCHAR(10) | M15 |
| phase | VARCHAR(50) | Current phase (BOS_CONFIRMED, CHOCH_DETECTED) |
| last_hh | DECIMAL(10,2) | Harga HH terakhir |
| last_ll | DECIMAL(10,2) | Harga LL terakhir |
| choch_detected | BOOLEAN | CHoCH sudah terdeteksi? |
| bos_detected | BOOLEAN | BoS sudah terdeteksi? |
| metadata | JSONB | Informasi tambahan |

---

### **6️⃣ TABLE: `agent_performance` - Performa Agents**

**Sumber:** Scheduled job (daily calculation)
**Fungsi:** Tracking akurasi dan performa agents per hari

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | SERIAL PRIMARY KEY | ID unik |
| date | DATE NOT NULL | Tanggal |
| agent_name | VARCHAR(50) NOT NULL | MarketStructureAgent, MLPredictionAgent, dll |
| correct_predictions | INT | Prediksi yang tepat |
| total_predictions | INT | Total prediksi |
| accuracy | DECIMAL(5,4) | Akurasi (0-1) |
| avg_confidence | DECIMAL(5,4) | Rata-rata confidence |

**Constraint:** UNIQUE(date, agent_name)

---

## 🔄 **Alur Insertion (Kapan Data Diinsert):**

```
STEP 1: MT5 Python API ambil data harga
    ↓ INSERT → realtime_ohlcv

STEP 2: MT5 DATA ADAPTER deteksi pola (HH/LL/CHoCH/BoS)
    ↓ INSERT → realtime_structures
    ↓ INSERT → state_machine (update state)

STEP 3: Orchestrator Agent trigger 4 agents
    ↓ INSERT → agent_decisions

STEP 4: Consensus score tinggi (≥ 0.6)?
    ├─ YES → Execution Agent eksekusi order
    │   ↓ INSERT → trades
    │
    └─ NO → Skip execution

STEP 5: Saat order ditutup (hit SL atau TP)
    ↓ UPDATE → trades (close_time, close_price, profit, outcome)

STEP 6: Setiap hari (scheduled job)
    ↓ Hitung performa 4 agents
    ↓ INSERT → agent_performance
```

---

## ✅ **Ringkasan TRACK 1 Database:**

- ✅ 6 tabel real-time (realtime_ohlcv, realtime_structures, agent_decisions, trades, state_machine, agent_performance)
- ✅ Semua data dari TRACK 1 (MT5 API) tersimpan ke Neon PostgreSQL
- ✅ Data real-time, update setiap detik/millisecond
- ✅ Tidak ada file I/O, pure database operations
- ✅ Independen dari TRACK 2 (CSV batch load)

**Data dari TRACK 1 ini kemudian digunakan untuk Orchestrator Agent → 4 Agents → Execution → Trading! 🎯**

---

## 📁 **TRACK 2: Tabel dan Kolom yang Diload dari CSV (Dari Kode)**

### **7️⃣ TABLE: `llhhbosdata_xauusd` - Pola Swing dari CSV**

**Sumber:** CSV Export dari Dev_Bot (LLHHBOSData_*.csv)
**Fungsi:** Menyimpan event pola (HH/LL/CHoCH/BoS) dari CSV untuk audit trail

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | SERIAL PRIMARY KEY | ID unik |
| type | VARCHAR(20) NOT NULL | Tipe event (HH, LL, CHoCH, BoS) |
| direction_action | VARCHAR(50) | Arah/Aksi (Bullish, Bearish, Update, Confirmed) |
| price | DECIMAL(10, 2) | Harga saat event terbentuk |
| time | TIMESTAMP NOT NULL | Waktu kejadian event |
| timeframe | VARCHAR(10) NOT NULL | M15, H1, H4 |
| status | VARCHAR(20) | Status (Accepted, Denied, PreChoCH, dll.) |
| previous_price | DECIMAL(10, 2) | Harga referensi sebelumnya |
| previous_time | TIMESTAMP | Waktu referensi sebelumnya |
| csv_filename | VARCHAR(255) | Nama file CSV asal (tracking) |
| loaded_at | TIMESTAMP | Waktu di-load ke database |

**Constraint:** UNIQUE(time, timeframe, type, price) ON CONFLICT DO NOTHING

---

### **8️⃣ TABLE: `backtest_results_xauusd` - Hasil Eksekusi Trade dari CSV**

**Sumber:** CSV Export dari Dev_Bot (Backtest_Results_*.csv)
**Fungsi:** Menyimpan data eksekusi order/posisi trading untuk audit performa

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | SERIAL PRIMARY KEY | ID unik |
| ticket | BIGINT | Nomor tiket order MT5 |
| symbol | VARCHAR(10) NOT NULL | Simbol instrumen (XAUUSD) |
| type | VARCHAR(10) NOT NULL | Tipe posisi (BUY, SELL) |
| entry_price | DECIMAL(10, 2) | Harga entry |
| exit_price | DECIMAL(10, 2) | Harga exit |
| sl | DECIMAL(10, 2) | Stop Loss |
| tp | DECIMAL(10, 2) | Take Profit |
| profit | DECIMAL(10, 2) | Profit kotor |
| spread_cost | DECIMAL(10, 2) | Biaya spread |
| commission | DECIMAL(10, 2) | Komisi broker |
| swap | DECIMAL(10, 2) | Biaya swap inap |
| net_profit | DECIMAL(10, 2) | Profit bersih |
| session | VARCHAR(50) | Sesi pasar saat entry (London, New York, Asia, dll.) |
| session_isdst | VARCHAR(10) | Status DST sesi (YES/NO) |
| entry_time | TIMESTAMP NOT NULL | Waktu entry |
| exit_time | TIMESTAMP | Waktu exit |
| lot_size | DECIMAL(10, 2) | Ukuran lot posisi |
| magic_number | INT | ID unik robot (Magic Number) |
| timeframe | VARCHAR(10) NOT NULL | Timeframe running (M15, H1, H4) |
| status | VARCHAR(20) | Status trade (EXECUTED, REJECTED) |
| reject_reason | VARCHAR(100) | Alasan penolakan jika status REJECTED |
| csv_filename | VARCHAR(255) | Nama file CSV asal (tracking) |
| loaded_at | TIMESTAMP | Waktu di-load ke database |

**Constraint:** UNIQUE(entry_time, ticket, type) ON CONFLICT DO NOTHING

---

### **9️⃣ TABLE: `marketdata_xauusd_m15` / `_h1` / `_h4` - Data OHLCV & Indikator**

**Sumber:** CSV Export dari Dev_Bot (MarketData_M15_*, MarketData_H1_*, MarketData_H4_*)
**Fungsi:** Menyimpan data candlestick (OHLCV) dan indikator (EMA200) untuk audit & visualisasi

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | SERIAL PRIMARY KEY | ID unik |
| time | TIMESTAMP NOT NULL | Waktu bar candlestick |
| open | DECIMAL(10, 2) | Harga Open |
| high | DECIMAL(10, 2) | Harga High |
| low | DECIMAL(10, 2) | Harga Low |
| close | DECIMAL(10, 2) | Harga Close |
| volume | BIGINT | Volume transaksi (Tick Volume) |
| spread | INT | Spread instrumen dalam points |
| ema200 | DECIMAL(10, 2) | Nilai indikator EMA 200 |
| csv_filename | VARCHAR(255) | Nama file CSV asal (tracking) |
| loaded_at | TIMESTAMP | Waktu di-load ke database |

**Constraint:** UNIQUE(time) ON CONFLICT DO NOTHING

---

### **🔟 TABLE: `sessionzone_xauusd` - Data Sesi Pasar**

**Sumber:** CSV Export dari Dev_Bot (SessionZone_*.csv)
**Fungsi:** Menyimpan data range harga dan statistik untuk setiap sesi trading (Sydney, Tokyo, London, New York)

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | SERIAL PRIMARY KEY | ID unik |
| start_time | TIMESTAMP NOT NULL | Waktu awal sesi |
| end_time | TIMESTAMP | Waktu akhir sesi |
| duration_bars | INT | Durasi sesi dalam jumlah bar |
| session | VARCHAR(50) | Nama sesi trading (Sydney_Tokyo, London_NewYork, dll.) |
| status | VARCHAR(20) | Status sesi |
| is_dst | VARCHAR(10) | Status DST (YES/NO) |
| open_price | DECIMAL(10, 2) | Harga pembukaan sesi |
| high_price | DECIMAL(10, 2) | Harga tertinggi selama sesi |
| low_price | DECIMAL(10, 2) | Harga terendah selama sesi |
| close_price | DECIMAL(10, 2) | Harga penutupan sesi |
| range_points | INT | Range harga dalam points (High - Low) |
| csv_filename | VARCHAR(255) | Nama file CSV asal (tracking) |
| loaded_at | TIMESTAMP | Waktu di-load ke database |

**Constraint:** UNIQUE(start_time, session) ON CONFLICT DO NOTHING

---

### **1️⃣1️⃣ TABLE: `csv_load_log` - Log Proses Load CSV**

**Sumber:** Watcher Daemon (CSVWatcherService memantau folder setiap 5 detik)
**Fungsi:** Melacak file CSV mana saja yang sudah di-load secara incremental, jumlah baris, dan statusnya

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | SERIAL PRIMARY KEY | ID unik |
| filename | VARCHAR(255) NOT NULL | Nama file CSV |
| file_date | DATE | Tanggal file di-load |
| rows_loaded | INT | Jumlah baris/lines yang sudah berhasil di-import |
| loaded_at | TIMESTAMP | Waktu terakhir pembaruan data load |
| status | VARCHAR(20) | Status load ('success', 'error') |
| error_message | TEXT | Detail pesan error jika proses load gagal |

**Constraint:** UNIQUE(filename)

---

### **1️⃣2️⃣ TABLE: `cross_validation` - Hasil Rekonsiliasi Real-time vs CSV**

**Sumber:** Perbandingan berkala antara data realtime_* (Track 1) vs data historical (Track 2)
**Fungsi:** Menyimpan skor akurasi dan rekonsiliasi antara Track 1 dan Track 2

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | SERIAL PRIMARY KEY | ID unik |
| validation_date | DATE NOT NULL | Tanggal validasi |
| timeframe | VARCHAR(10) | M15, H1, H4 |
| event_type | VARCHAR(20) | BoS, CHoCH, HH, LL |
| total_realtime | INT | Jumlah data di tabel realtime |
| total_csv | INT | Jumlah data di tabel audit (CSV) |
| matches | INT | Jumlah data yang cocok |
| mismatches | INT | Jumlah data tidak cocok |
| missing_in_realtime | INT | Data hanya ada di CSV |
| missing_in_csv | INT | Data hanya ada di realtime |
| match_rate | DECIMAL(5, 4) | Persentase kecocokan (0.0 - 1.0) |
| avg_price_diff | DECIMAL(10, 2) | Rata-rata selisih harga data |
| created_at | TIMESTAMP | Waktu analisis |

**Constraint:** UNIQUE(validation_date, timeframe)

---

## 🔄 **Alur Load CSV ke Database (TRACK 2):**

```
SETIAP 15 MENIT (saat M15 candle close):
Dev_Bot_v11.cs export CSV
    ├─ LLHHBOSData_XAUUSD_2026-06-14.csv (pola)
    ├─ MarketData_M15_XAUUSD_2026-06-14.csv (harga M15)
    ├─ MarketData_H1_XAUUSD_2026-06-14.csv (harga H1)
    └─ MarketData_H4_XAUUSD_2026-06-14.csv (harga H4)
        ↓ Simpan ke Backtest_result/


SETIAP HARI JAM 00:00 (Scheduled Job):
CSV to DB Loader jalankan
    ↓
STEP 1: Baca CSV kemarin (2026-06-13)
    ├─ LLHHBOSData_XAUUSD_2026-06-13.csv
    └─ MarketData_*_XAUUSD_2026-06-13.csv
    
STEP 2: Parse CSV dan INSERT ke tabel audit
    ├─ INSERT → historical_ohlcv_audit (dari MarketData_*.csv)
    ├─ INSERT → historical_structures_audit (dari LLHHBOSData_*.csv)
    └─ INSERT → csv_load_log (track file yang di-load)

STEP 3: Cross-validation
    ├─ Bandingkan realtime_structures vs historical_structures_audit
    ├─ Bandingkan realtime_ohlcv vs historical_ohlcv_audit
    └─ INSERT → cross_validation (hasil perbandingan)
        ↓ Tampilkan match_rate (kecocokan %)
```

---

## 📊 **Contoh Data TRACK 2:**

### **historical_ohlcv_audit (dari CSV MarketData_*):**
```
id  | timestamp           | symbol | timeframe | open    | high    | low     | close   | volume | source     | csv_filename
1   | 2026-06-13 06:00:00 | XAUUSD | M15       | 2350.50 | 2351.80 | 2349.20 | 2350.80 | 1523   | csv_export | MarketData_M15_XAUUSD_2026-06-13.csv
2   | 2026-06-13 06:15:00 | XAUUSD | M15       | 2350.80 | 2352.10 | 2350.40 | 2351.50 | 1687   | csv_export | MarketData_M15_XAUUSD_2026-06-13.csv
```

### **historical_structures_audit (dari CSV LLHHBOSData_*):**
```
id  | timestamp           | symbol | timeframe | event_type | direction | price   | status          | source     | csv_filename
1   | 2026-06-13 06:00:00 | XAUUSD | M15       | HH         | Bullish   | 2351.80 | CONFIRMED       | csv_export | LLHHBOSData_XAUUSD_2026-06-13.csv
2   | 2026-06-13 06:30:00 | XAUUSD | M15       | BoS        | Bullish   | 2351.50 | TRIGGERED_TRADE | csv_export | LLHHBOSData_XAUUSD_2026-06-13.csv
```

### **csv_load_log (tracking file yang di-load):**
```
id | filename                                      | file_date  | rows_loaded | loaded_at           | status  | error_message
1  | LLHHBOSData_XAUUSD_2026-06-13.csv            | 2026-06-13 | 156         | 2026-06-14 00:05:00 | SUCCESS | NULL
2  | MarketData_M15_XAUUSD_2026-06-13.csv         | 2026-06-13 | 96          | 2026-06-14 00:05:30 | SUCCESS | NULL
3  | MarketData_H1_XAUUSD_2026-06-13.csv          | 2026-06-13 | 24          | 2026-06-14 00:06:00 | SUCCESS | NULL
```

### **cross_validation (perbandingan TRACK 1 vs TRACK 2):**
```
id | validation_date | timeframe | event_type | total_realtime | total_csv | matches | mismatches | missing_in_realtime | missing_in_csv | match_rate | avg_price_diff
1  | 2026-06-13      | M15       | BoS        | 12             | 12        | 12      | 0          | 0                   | 0              | 1.0000     | 0.25
2  | 2026-06-13      | M15       | HH         | 8              | 8         | 7       | 1          | 0                   | 1              | 0.8750     | 0.50
```

---

## ✅ **Ringkasan TRACK 2 Database:**

- ✅ 4 tabel audit (historical_ohlcv_audit, historical_structures_audit, csv_load_log, cross_validation)
- ✅ Data dari Dev_Bot CSV di-load setiap hari jam 00:00
- ✅ Untuk audit trail dan compliance checking
- ✅ Cross-validation membandingkan TRACK 1 (realtime) vs TRACK 2 (CSV)
- ✅ Jika match_rate < 0.95 berarti ada masalah!

**TRACK 2 adalah untuk memastikan TRACK 1 bekerja dengan benar! 🎯**

---

---

# 🎯 **SECTION 3: ORCHESTRATOR AGENT - KOORDINATOR KEPUTUSAN TRADING**

> **Setelah data disimpan ke database, sekarang saatnya sistem membuat KEPUTUSAN TRADING!**

---

## 📍 **POSISI ORCHESTRATOR DALAM ALUR**

```
DATA TERSIMPAN DI DATABASE (realtime_ohlcv, realtime_structures)
    ↓
ORCHESTRATOR AGENT MENGAMBIL DATA ← ADA SINYAL BARU?
    ↓
    ├─ YA: Trigger 4 agents untuk diskusi
    │      (Parallel execution - semua jalan bersamaan)
    │
    └─ TIDAK: Tunggu sinyal berikutnya


ORCHESTRATOR = "MANAGER RAPAT TRADING"
├─ Panggil 4 specialist (agents)
├─ Dengarkan pendapat mereka
├─ Buat keputusan bersama (voting)
└─ Eksekusi order (jika setuju)
```

---

## 🏢 **4 AGENTS DALAM RAPAT TRADING**

Bayangkan Orchestrator seperti **MANAGER** yang memimpin rapat dengan 4 specialist:

### **1️⃣ MARKET STRUCTURE AGENT (Specialist Grafik)**
**Peran:** Membaca grafik dan mendeteksi pola

```
Dia bertanya: "Apa pattern yang terbentuk?"

Dia lihat:
├─ Higher High (HH) = Harga baru naik lebih tinggi (Bullish 📈)
├─ Lower Low (LL) = Harga baru turun lebih rendah (Bearish 📉)
├─ Change of Character (CHoCH) = Arah trend berubah 🔄
└─ Break of Structure (BoS) = Harga tembus support/resistance 💥

Dia hasil: "Signal BUY/SELL + Confidence (0-1)"
Contoh: ✅ Signal: BUY | Confidence: 0.85 (85% yakin)

Berdasarkan kode sumber aktual di 

market_structure_agent.py
 dan 

market_structure_detector.py
, berikut adalah cara kerja rinci dari Market Structure Agent:

1. Penerimaan Data & Deteksi Struktur (detect())
Agent menerima data candle (OHLCV) riil. Pendeteksi struktur (MarketStructureDetector) menyisir pergerakan harga untuk mencari titik pivot swing high/low (berdasarkan parameter swing_length kiri & kanan), lalu mencocokkan hukum SMC (Smart Money Concepts):

HH (Higher High): Swing high baru lebih tinggi dari HH sebelumnya.
LL (Lower Low): Swing low baru lebih rendah dari LL sebelumnya.
CHoCH (Change of Character): Harga menembus swing extreme arah berlawanan (sinyal awal pembalikan tren).
BoS (Break of Structure): Harga menembus swing extreme searah tren (sinyal kelanjutan tren).
Agent kemudian mengambil event struktur paling baru (latest_event = events[-1]) sebagai dasar analisis.

2. Pencocokan Pola Historis via LanceDB (_analyze_patterns())
Jika fitur use_patterns aktif, agent memanggil PatternMatcher untuk mencari situasi serupa di masa lalu pada basis data LanceDB:

Mencari kecocokan tipe event (BoS/CHoCH), arah, harga saat ini, posisi EMA200, sesi trading, dan timeframe.
Menggunakan batas kesamaan minimum (similarity >= 70%).
Mengembalikan statistik: total pola serupa di masa lalu (total_count), tingkat kemenangan historis (win_rate), dan rata-rata perolehan pips (avg_profit).
3. Penentuan Sinyal Dasar & Confidence (_generate_signal())
Sinyal awal dan kepercayaan diri ditentukan oleh jenis event struktur yang terdeteksi:

A. Break of Structure (BoS) — Sinyal Konfirmasi Entri
BOS_BULLISH → Menghasilkan sinyal BUY (Base Confidence: 0.5).
Penyelarasan Tren: Jika harga saat ini berada di atas EMA200, confidence bertambah +0.2.
BOS_BEARISH → Menghasilkan sinyal SELL (Base Confidence: 0.5).
Penyelarasan Tren: Jika harga saat ini berada di bawah EMA200, confidence bertambah +0.2.
B. Change of Character (CHoCH) — Setup Awal
Menghasilkan sinyal HOLD (Confidence: 0.4). Sistem sengaja menunggu BoS berikutnya sebagai konfirmasi agar lebih aman.
C. HH (Higher High) / LL (Lower Low)
Menghasilkan sinyal HOLD (Confidence: 0.3). Hanya dicatat sebagai referensi struktur, tidak ditindaklanjuti secara langsung.
4. Modifikasi Skor Menggunakan Pola Histori (Boost / Penalty)
Jika pola historis yang mirip di database LanceDB berjumlah minimal 5 kali, skor confidence dari BoS akan disesuaikan:

Jika win_rate >= 75% → Kepercayaan bertambah +0.3 (Sangat Bagus).
Jika win_rate >= 60% → Kepercayaan bertambah +0.2 (Bagus).
Jika win_rate >= 45% → Kepercayaan bertambah +0.1 (Netral).
Jika win_rate < 45% → Kepercayaan dikurangi -0.1 (Peringatan Performa Buruk).
5. Output Keputusan
Hasil akhir dibungkus ke dalam kamus keputusan yang dikembalikan ke Orchestrator:

signal: "BUY", "SELL", atau "HOLD".
confidence: Angka desimal terkalibrasi antara 0.0 sampai 1.0.
reasoning: Penjelasan tekstual alasan pengambilan keputusan tersebut (misal: "Confirmed Bullish BoS at 4235.44. Price above EMA200. Good historical performance: 65.0% win rate...").

```

**Bobot vote:** 25% dari total keputusan

---

### **2️⃣ ML PREDICTION AGENT (Specialist AI/Machine Learning)**
**Peran:** Memvalidasi signal dengan AI model yang sudah dilatih

```
Dia bertanya: "Market Structure bilang BUY, tapi AI saya setuju?"

Dia analisa:
├─ Historical patterns (pola yang pernah terjadi sebelumnya)
├─ Model predictions (AI model predict price direction)
├─ Probability score (confidence dari model)
└─ Risk assessment (apakah aman?)

Dia hasil: "Signal BUY/SELL + Probability (0-1)"
Contoh: ✅ Signal: BUY | Probability: 0.92 (92% confident dari AI)
```

**Bobot vote:** 40% dari total keputusan ⭐ (PALING HEAVY WEIGHT!)
```
Kenapa paling berat? Karena ML model sudah dilatih dari ribuan data historis.
Dia lebih akurat daripada manusia/pattern visual.
```

---

### **3️⃣ RISK MANAGEMENT AGENT (Specialist Manajemen Risiko)**
**Peran:** Menentukan ukuran posisi, Stop Loss, Take Profit

```
Dia bertanya: "Kalau kita BUY, berapa lot? Dimana SL/TP?"

Dia kalkulasi:
├─ Account balance (saldo akun saat ini)
├─ Risk per trade (berapa % yang boleh kami risiko?)
├─ Position size (berapa lot yang aman?)
├─ Stop Loss distance (harus jarak berapa untuk aman?)
├─ Take Profit level (target profit kita)
└─ Risk-Reward Ratio (RR = 1:2, 1:3, dst)

Dia hasil: "Lot: 0.5 | SL: 2350.00 | TP: 2360.00 | RR: 1:2"
Contoh: ✅ Approved | Lot: 0.50 | SL: 2350.25 | TP: 2360.75 | Risk: 1:2.5
```

**Bobot vote:** 15% dari total keputusan

```
Catatan: Risk Agent punya "veto power"!
Jika signal BUY/SELL tapi risk terlalu besar → REJECT!
```

---

### **4️⃣ SENTIMENT AGENT (Specialist Berita & Ekonomi)**
**Peran:** Menyesuaikan keputusan berdasarkan berita/event ekonomi

```
Dia bertanya: "Ada berita/event yang bisa mempengaruhi market?"

Dia check:
├─ Breaking news (berita terbaru)
├─ Economic calendar (jadwal event ekonomi)
├─ Market sentiment (apakah market bullish atau bearish?)
└─ Risk events (apakah ada event berisiko tinggi?)

Dia hasil: "Confidence adjustment: +10% atau -20%"
Contoh: 
├─ Kalau ada good news: boost confidence 📈
├─ Kalau ada bad news: turunkan confidence 📉
└─ Kalau ada major event (Fed meeting): JANGAN TRADE ❌

Dia hasil akhir: "Final Signal + Adjusted Confidence"
Contoh: ✅ Final Signal: BUY | Adjusted Confidence: 0.78
```

**Bobot vote:** 20% dari total keputusan

---

## 🗳️ **WEIGHTED VOTING SYSTEM - BAGAIMANA KEPUTUSAN DIBUAT**

```
┌─────────────────────────────────────────────────────────────┐
│            ORCHESTRATOR VOTING SESSION                       │
└─────────────────────────────────────────────────────────────┘

Semua 4 agents sudah selesai analisis.
Sekarang giliran Orchestrator mengitung voting mereka.

STEP 1: KUMPULKAN SUARA SEMUA AGENTS
═══════════════════════════════════════

Market Structure Agent:
├─ Signal: BUY
├─ Confidence: 0.85
└─ Bobot: 25%

ML Prediction Agent:
├─ Signal: BUY
├─ Confidence: 0.92
└─ Bobot: 40% ⭐ (PALING BERAT)

Risk Management Agent:
├─ Signal: APPROVED (okay untuk trade)
├─ Confidence: 0.80
└─ Bobot: 15%

Sentiment Agent:
├─ Signal: BUY
├─ Confidence: 0.75
└─ Bobot: 20%


STEP 2: HITUNG WEIGHTED SCORE
═════════════════════════════════

Formula:
Vote Score = (Signal Confidence × Agent Weight) + ...

BUY Score:
= (0.85 × 0.25) + (0.92 × 0.40) + (0.80 × 0.15) + (0.75 × 0.20)
= 0.2125 + 0.368 + 0.12 + 0.15
= 0.8405 ← SCORE UNTUK BUY

SELL Score:
= (0.00 × 0.25) + (0.00 × 0.40) + (0.00 × 0.15) + (0.00 × 0.20)
= 0.0 ← SCORE UNTUK SELL

HOLD Score:
= sisanya atau jika tidak ada signal jelas


STEP 3: TENTUKAN WINNING SIGNAL
═════════════════════════════════

Winning Signal = Signal dengan score tertinggi
Final Signal = BUY (score 0.8405 adalah tertinggi)
Final Confidence = 84.05%


STEP 4: CEK CONSENSUS LEVEL
═════════════════════════════

Consensus % = Final Score / Total Possible × 100%

Rumus:
Consensus % = 0.8405 / (0.25 + 0.40 + 0.15 + 0.20) × 100%
            = 0.8405 / 1.0 × 100%
            = 84.05%

Consensus Level:
├─ 95%+ = UNANIMOUS (semua sepakat)
├─ 80-94% = STRONG (mayoritas besar sepakat) ⭐ KITA DI SINI
├─ 60-79% = MODERATE (cukup sepakat)
├─ 50-59% = WEAK (agak ragu-ragu)
└─ <50% = NO CONSENSUS (tidak ada keputusan)


STEP 5: APPROVAL CHECK
═══════════════════════

Threshold Default = 60% (bisa dikonfigurasi)

Karena Final Confidence (84.05%) ≥ Threshold (60%):
✅ APPROVED! Trade akan dilanjutkan ke Risk Management


Hasil Voting:
✅ Final Signal: BUY
✅ Confidence: 84.05%
✅ Consensus: STRONG
✅ Approved: YES
❌ Reasoning: "Consensus STRONG (84.05%). Semua agents setuju BUY."
```

---

## 💼 **RISK MANAGEMENT CHECK - VALIDASI TERAKHIR**

Setelah consensus dicapai, sebelum order dieksekusi, **Risk Management Agent melakukan check terakhir**:

```
Risk Management Agent Checklist:

✅ Apakah account balance cukup untuk lot size yang dipilih?
✅ Apakah daily loss limit sudah terlampaui?
✅ Apakah position sudah terlalu besar (max positions)?
✅ Apakah SL/TP jarak valid (tidak terlalu dekat)?
✅ Apakah RR ratio acceptable (minimal 1:2)?

JIKA SEMUA CHECKED:
  → Risk Approved = TRUE
  → Lanjut ke Execution Agent

JIKA ADA YANG FAILED:
  → Risk Approved = FALSE
  → CANCEL ORDER! ❌
```

---

## 📊 **CONTOH SKENARIO VOTING**

### **Skenario 1: SEMUA AGENTS SETUJU BUY (UNANIMOUS)**

```
Market Structure: BUY (0.95 confidence)
ML Prediction:    BUY (0.98 confidence)
Risk Management:  APPROVED (0.90 confidence)
Sentiment:        BUY (0.88 confidence)

Final Score:
= (0.95 × 0.25) + (0.98 × 0.40) + (0.90 × 0.15) + (0.88 × 0.20)
= 0.2375 + 0.392 + 0.135 + 0.176
= 0.9405 → 94.05% Confidence

Consensus: STRONG ✅
Approval: YES ✅
Status: EXECUTE BUY ORDER! 🎯
```

---

### **Skenario 2: MAJORITY AGREE, SATU AGENT RAGU**

```
Market Structure: BUY (0.85 confidence)
ML Prediction:    BUY (0.92 confidence)
Risk Management:  HOLD (0.50 confidence) ⚠️ KURANG YAKIN
Sentiment:        BUY (0.80 confidence)

Final Score:
= (0.85 × 0.25) + (0.92 × 0.40) + (0.50 × 0.15) + (0.80 × 0.20)
= 0.2125 + 0.368 + 0.075 + 0.16
= 0.8155 → 81.55% Confidence

Consensus: STRONG ✅ (masih di atas 80%)
Approval: YES ✅
Status: EXECUTE BUY ORDER dengan hati-hati 🟡
```

---

### **Skenario 3: AGENTS TIDAK AGREE (CONFLICTED)**

```
Market Structure: BUY (0.72 confidence)
ML Prediction:    SELL (0.65 confidence) ⚠️ BERBEDA!
Risk Management:  HOLD (0.60 confidence)
Sentiment:        BUY (0.55 confidence)

Vote Scores:
BUY:  (0.72 × 0.25) + (0 × 0.40) + (0 × 0.15) + (0.55 × 0.20) = 0.291
SELL: (0 × 0.25) + (0.65 × 0.40) + (0 × 0.15) + (0 × 0.20) = 0.26
HOLD: sisanya = 0.249

Final Signal: BUY (score 0.291 tertinggi)
Confidence: 29.1%

Consensus: WEAK ⚠️ (di bawah 60% threshold)
Approval: NO ❌
Status: NO TRADE! ✋ Terlalu banyak disagreement!
Reasoning: "Confidence terlalu rendah 29.1% < 60% threshold"
```

---

### **Skenario 4: RISK MANAGEMENT VETO**

```
Market Structure: BUY (0.95 confidence)
ML Prediction:    BUY (0.98 confidence)
Sentiment:        BUY (0.90 confidence)

Final Score hingga sini: 94.5% ✅ UNANIMOUS!

TAPI...

Risk Management Agent:
├─ Daily loss limit sudah terlampaui → REJECT! ❌
├─ Account balance kurang untuk lot size → REJECT! ❌

Risk Approved: FALSE

Status: CANCEL ORDER! ❌
Reasoning: "Approved untuk signal, BUT risk management rejected (account limit reached)"

Ini seperti: Boss bilang YES tapi CFO bilang "Tidak cukup uang!"
```

---

## 🎯 **ORCHESTRATOR OUTPUT - HASIL KEPUTUSAN**

Setelah voting selesai, Orchestrator mengirimkan output berisi:

```json
{
  "orchestrator": "OrchestratorAgent",
  "version": "1.0.0",
  "timestamp": "2026-06-14 14:30:00",
  "symbol": "XAUUSD",
  "timeframe": "M15",
  
  "FINAL DECISION": {
    "final_signal": "BUY",
    "final_confidence": 0.841,
    "consensus_level": "strong",
    "approved": true,
    "reasoning": "Consensus strong (84.1%). Vote scores: BUY=0.841, SELL=0.000, HOLD=0.159."
  },
  
  "VOTING DETAILS": {
    "vote_scores": {
      "BUY": 0.841,
      "SELL": 0.000,
      "HOLD": 0.159
    }
  },
  
  "AGENT RESULTS": {
    "market_structure": {
      "signal": "BUY",
      "confidence": 0.85,
      "detected_pattern": "BoS (Break of Structure) Bullish"
    },
    "ml_prediction": {
      "signal": "BUY",
      "confidence": 0.92,
      "probability": 0.92
    },
    "sentiment": {
      "signal": "BUY",
      "confidence": 0.88,
      "adjustment": 0.00,
      "filtered": false
    },
    "risk_management": {
      "approved": true,
      "lot_size": 0.50,
      "sl_price": 2350.25,
      "tp_price": 2360.75,
      "rr_ratio": 2.0
    }
  },
  
  "POSITION DETAILS": {
    "entry_price": 2355.50,
    "sl_price": 2350.25,
    "tp_price": 2360.75,
    "lot_size": 0.50,
    "risk_pct": 0.025,
    "risk_usd": 25.00
  },
  
  "execution_time_ms": 234,
  "active_agents": ["market_structure", "ml_prediction", "sentiment", "risk_management"]
}
```

---

## 🔄 **ALUR LENGKAP ORCHESTRATOR DARI DATABASE KE EXECUTION**

```
STEP 1: DATABASE TRIGGERS EVENT
═══════════════════════════════
realtime_structures INSERT terbaru:
├─ Event: BoS Bullish terdeteksi
├─ Timestamp: 14:30:15
├─ Price: 2355.50
└─ → SIGNAL! Ada pola baru!


STEP 2: ORCHESTRATOR DIAKTIFKAN
════════════════════════════════
Orchestrator receive: "Ada BoS Bullish di M15!"

Dia ambil data dari database:
├─ Current bar dari realtime_ohlcv
├─ Structure events dari realtime_structures
├─ Historical data untuk ML model
└─ Latest news dari sentiment sources


STEP 3: 4 AGENTS MULAI ANALISIS (PARALLEL)
════════════════════════════════════════════
Semua agents jalan bersamaan:

├─ Market Structure Agent: Analisis pattern
│  Waktu: 50ms
│  Hasil: BUY 0.85
│
├─ ML Prediction Agent: Run model
│  Waktu: 120ms
│  Hasil: BUY 0.92
│
├─ Sentiment Agent: Check news
│  Waktu: 80ms
│  Hasil: BUY 0.88
│
└─ Risk Management Agent: Calculate position
   Waktu: 40ms
   Hasil: APPROVED (0.50 lot, SL 2350.25, TP 2360.75)

Total Waktu: ~120ms (agents fastest to complete wins, tidak perlu tunggu semuanya)


STEP 4: VOTING & CONSENSUS
═════════════════════════════
Orchestrator hitung vote scores:
BUY Score = 0.841 (84.1% confidence)
Consensus = STRONG ✅


STEP 5: APPROVAL CHECK
═══════════════════════
├─ Signal approved? YES ✅
├─ Risk approved? YES ✅
└─ Final decision? APPROVED! ✅


STEP 6: SEND TO EXECUTION AGENT
════════════════════════════════
Execution Agent menerima:
├─ Signal: BUY
├─ Entry: 2355.50 (current price)
├─ SL: 2350.25
├─ TP: 2360.75
├─ Lot: 0.50
└─ Action: PLACE ORDER


STEP 7: MT5 EXECUTE
═══════════════════
MT5 Python API:
└─ order_send(...)
   └─ ORDER PLACED! 🎯
   └─ Ticket: #12345678
   └─ Status: EXECUTION_LIVE


STEP 8: RECORD TRADE
════════════════════
INSERT INTO trades:
├─ ticket: 12345678
├─ type: BUY
├─ entry_price: 2355.50
├─ stop_loss: 2350.25
├─ take_profit: 2360.75
├─ consensus_score: 0.841
└─ status: LIVE ✅

WAKTU TOTAL: ~250ms (dari deteksi hingga order live)
```

---

## ✅ **RINGKASAN ORCHESTRATOR AGENT**

| Aspek | Keterangan |
|-------|-----------|
| **Peran** | Manager/Coordinator - merancang dan menjalankan rapat voting |
| **Agents** | 4: Market Structure (25%), ML Prediction (40%), Risk (15%), Sentiment (20%) |
| **Sistem** | Weighted voting + consensus engine |
| **Threshold** | Default 60% confidence untuk approval |
| **Execution** | Parallel (semua agents jalan bersamaan) |
| **Speed** | ~250ms dari deteksi hingga order placement |
| **Output** | JSON dengan voting details, agent results, position info |
| **Veto** | Risk Management bisa reject meskipun signal approved |
| **Storage** | agent_decisions, trades (ke PostgreSQL) |

---

## 🎯 **YANG PENTING DIINGAT:**

✅ **Orchestrator BUKAN trader**
- Dia hanya coordinator
- Yang decide adalah 4 agents

✅ **Voting adalah DEMOCRATIC**
- Setiap agent punya voice
- ML Agent suara paling berat (40%)
- Risk Agent punya veto power

✅ **Parallel execution**
- Semua agents bekerja bersamaan
- Tidak perlu tunggu satu selesai
- Total waktu hanya ~250ms

✅ **Data-driven**
- Semua keputusan berdasarkan data database
- Semua terrecord di audit tables
- Dapat diverifikasi kemudian

✅ **Risk First**
- Sebelum execute, Risk Management always check
- Account protection adalah prioritas
- Jangan trade jika risiko berlebihan

---

