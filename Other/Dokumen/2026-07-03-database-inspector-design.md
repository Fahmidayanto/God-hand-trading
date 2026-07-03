# DESIGN SPEC: Database Inspector (Tab-Based View)

**Created Date:** 2026-07-03  
**Status:** Approved (Opsi A)

---

## 🎯 **1. PENDAHULUAN & TUJUAN**

Dokumen ini mendefinisikan desain teknis untuk fitur **Database Inspector** pada dashboard frontend ValueCell MT5. 

### **Latar Belakang**
Sistem ValueCell MT5 berjalan menggunakan dua jenis database:
1. **Neon PostgreSQL (NeonDB)**: Menyimpan data pasar (`marketdata_*`), swing events (`llhhbosdata_*`), data sesi (`sessionzone_*`), hasil backtest/live trades (`backtest_results_*`), dan log impor (`csv_load_log`).
2. **LanceDB**: Menyimpan representasi vektor dari pola struktur pasar untuk kemiripan (*similarity matching*).

### **Tujuan Fitur**
Menambahkan menu baru di sidebar web dashboard bernama **"DB Inspector"** yang menyajikan preview data NeonDB dan LanceDB secara instan untuk verifikasi kesuksesan sinkronisasi data live trading tanpa perlu membuka database terminal eksternal.

---

## 🎨 **2. DESAIN ANTARMUKA PENGGUNA (UI)**

Sesuai persetujuan desain **Opsi A**, antarmuka menggunakan struktur **Tab-Based View** dengan detail berikut:

### **Sidebar Navigation**
* Menambahkan satu item navigasi baru di `MT5Sidebar.tsx`:
  * **Label**: `DB Inspector`
  * **Icon**: `💾`
  * **Route**: `/mt5/database`

### **Layout Halaman Utama**
* **Header**: Judul halaman "Database Inspector 💾" dengan sub-teks deskripsi.
* **Tab Bar**: Dua tombol tab navigasi:
  * **Tab 1: NeonDB (PostgreSQL)** (Active secara default)
  * **Tab 2: LanceDB (Vector)**
* **Stats Cards**: Baris atas menampilkan ringkasan data di NeonDB:
  * Jumlah baris di tabel `llhhbosdata_xauusd`.
  * Jumlah baris di tabel `backtest_results_xauusd`.
  * Jumlah file sukses/gagal di `csv_load_log`.
* **Control Bar**:
  * Dropdown pemilih tabel (`llhhbosdata_xauusd`, `backtest_results_xauusd`, `marketdata_xauusd_m15`, `sessionzone_xauusd`, `csv_load_log`).
  * Tombol **"🔄 Refresh Data"** manual.
* **Data Grid**: Tabel scrollable dengan glassmorphism dark theme, memuat maksimal **50 data terbaru** berdasarkan timestamp dari tabel terpilih.

---

## ⚙️ **3. DESAIN BACKEND API (FASTAPI)**

Kita akan membuat router baru di backend: `backend/app/api/v1/database.py`.

### **Endpoint 1: Statistik Database**
* **Path**: `GET /api/v1/database/stats`
* **Fungsi**: Mengambil jumlah baris total untuk tabel-tabel utama di NeonDB dan mendeteksi apakah folder LanceDB aktif di server lokal.
* **Response Schema**:
  ```json
  {
    "neon_stats": {
      "llhhbosdata_xauusd": 450,
      "backtest_results_xauusd": 24,
      "csv_load_log": 8,
      "marketdata_xauusd_m15": 100000
    },
    "lancedb_active": true,
    "lancedb_collections": [
      { "name": "historical_structures", "count": 324 },
      { "name": "market_conditions", "count": 120 }
    ]
  }
  ```

### **Endpoint 2: Preview Baris Tabel**
* **Path**: `GET /api/v1/database/neon/preview?table={table_name}&limit=50`
* **Fungsi**: Query 50 baris data terbaru dari tabel NeonDB yang dipilih.
* **Response Schema**:
  ```json
  {
    "table": "llhhbosdata_xauusd",
    "columns": ["id", "type", "direction_action", "price", "time", "timeframe", "status"],
    "rows": [
      {
        "id": 450,
        "type": "HH",
        "direction_action": "Bullish Update",
        "price": 2045.20,
        "time": "2026-07-03T18:30:00",
        "timeframe": "M15",
        "status": "Accepted"
      }
    ]
  }
  ```

---

## 🧠 **4. PENANGANAN LANCEDB**

* Karena LanceDB disimpan secara lokal di dalam folder proyek python (`.lancedb` atau path tertentu), backend akan mencoba memuat LanceDB menggunakan library `lancedb` Python secara pasif.
* Jika folder database tidak ditemukan (misal karena belum diinisialisasi atau Track 1 dinonaktifkan), backend **tidak boleh mengalami crash (500 Error)**.
* **Mitigasi**: Gunakan blok `try/except` saat inisialisasi koneksi LanceDB. Jika gagal, kembalikan `"lancedb_active": false` dan daftar koleksi kosong. UI akan menampilkan pesan ramah: *"LanceDB belum diinisialisasi atau dinonaktifkan."*

---

## 🛡️ **5. KEKURANGAN SKENARIO & MITIGASI (RISK ANALYSIS)**

| Kekurangan yang Mungkin Terjadi (Risiko) | Analisis Dampak | Solusi / Mitigasi |
|------------------------------------------|-----------------|-------------------|
| **Performa query lambat pada tabel besar** (seperti `marketdata_xauusd_m15` yang berisi >100.000 baris) | Halaman lag atau memori backend membengkak jika seluruh data dimuat. | Batasi query preview secara ketat (`LIMIT 50`) di tingkat database dan gunakan index pada kolom waktu (`time`/`timestamp`). |
| **Koneksi pool NeonDB habis / bocor** | Request backend lain akan macet dan mengalami timeout. | Selalu gunakan generator `get_db_conn()` dengan blok `with` untuk menjamin koneksi dikembalikan ke pool secepatnya setelah query selesai. |
| **LanceDB dilempar Exception di server headless/production** | Halaman DB Inspector menampilkan error blank (Crash). | Lakukan *graceful fallback* di tingkat backend (deteksi keberadaan folder db fisik terlebih dahulu sebelum memanggil API LanceDB). |
| **Format data non-string/raw json** | Grid frontend pecah jika ada data bertipe objek JSON atau array panjang. | Di backend, serialize data non-primitive (seperti data koordinat jika ada) menjadi string representatif atau kecualikan kolom tersebut dari visualisasi preview (tetap bersih sesuai Pilihan 1). |

---

## 🧪 **6. RENCANA VERIFIKASI**

### **Automated Tests**
1. **Integration Test (Python)**:
   * Memanggil endpoint `GET /api/v1/database/stats` dan memverifikasi kembalian tipe JSON yang valid.
   * Memanggil endpoint `GET /api/v1/database/neon/preview` dengan parameter tabel yang valid dan invalid untuk memastikan proteksi query-injection.

### **Manual Verification**
1. Buka browser pada menu web dashboard ValueCell.
2. Klik menu **"DB Inspector"** di sidebar.
3. Verifikasi jumlah baris pada stats card cocok dengan total data di database.
4. Ganti dropdown tabel dan klik tombol **"🔄 Refresh Data"** untuk memverifikasi data baru masuk real-time seiring berjalannya MT5 live trading.
