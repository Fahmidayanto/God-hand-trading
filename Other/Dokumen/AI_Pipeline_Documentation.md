# Dokumentasi End-to-End: Dual-Model AI Trading Pipeline (SMC) & Metatrader 5

> **Versi Dokumen:** 3.0 — Diperbarui 5 Mei 2026
> **Perubahan Besar:** Migrasi dari Single Model (Phase 2) ke **Dual-Model Trading System** (Filter Model + Quality Model) dengan proteksi **Market Structure State Machine** untuk mencegah overtrading.

Dokumen ini menjelaskan arsitektur sistem terbaru yang memproses data dari Expert Advisor (EA) **Dev Bot v7** di MetaTrader 5 menjadi sinyal trading via Telegram dengan akurasi tinggi dan noise minimal.

---

## 1. Alur Sistem Keseluruhan (End-to-End Flow)

Pipeline saat ini beroperasi menggunakan sistem **3-Gate (Tiga Gerbang Keputusan)** sebelum sinyal diteruskan ke pengguna.

1. **Eksport Data (MT5):** EA Dev Bot v7 mengekspor data market, struktur harga (SMC), dan sesi ke folder `Backtest_result` dalam format CSV.
2. **Deteksi Otomatis (File Watcher):** Skrip daemon `main_pipeline_run.py` mendeteksi bar M15 baru dan memicu analisis sinyal.
3. **Gate 0: State Machine (Proteksi Overtrading):** `market_structure_state_machine.py` melacak pola SMC secara kronologis (CHoCH → HH/LL → BoS). Sistem hanya akan berlanjut jika market berada di fase `BOS_CONFIRMED`. Jika di luar fase ini (misal `NEUTRAL` atau `IN_TREND`), sinyal langsung ditolak (SKIP).
4. **Ekstraksi Fitur:** `feature_engineer.py` mengubah data CSV mentah menjadi 60+ fitur teknikal (SMC, tren, volatilitas, momentum).
5. **Gate 1: Entry Filter Model:** Fitur dilempar ke `EntryFilterPredictor` (berbasis Random Forest / klasifikasi rule-based). Model ini dilatih khusus untuk mengenali kondisi market "berbahaya" (low probability). Jika market dianggap *untradeable* (Filter Score < Threshold), sinyal ditolak.
6. **Gate 2: Quality Model:** Jika lolos Filter, data dilempar ke `ModelPredictor` (berbasis XGBoost). Model ini menghitung skor **Win Probability** (Confidence). Jika Confidence < Threshold (misal 65%), sinyal ditolak.
7. **Signal Generation & Telegram:** Jika ketiga gerbang terlewati, `signal_generator.py` memaketkan harga entry, SL, TP dinamis, kalkulasi lot, dan *reasoning* (alasan) menjadi file JSON lalu dikirim realtime ke Telegram.
8. **Live Feedback Loop:** `live_outcome_watcher.py` akan memonitor sinyal yang aktif untuk melihat apakah berakhir WIN atau LOSS secara aktual, dan menyimpannya untuk re-training (`continuous_learner.py`).

---

## 2. Struktur Direktori Aktif & Penjelasan File

Pembersihan file *legacy* (Phase 2 lama) telah dilakukan. Berikut adalah arsitektur direktori yang aktif:

### A. Folder `AI_Trading_Server/core/` (Orkestrator Utama)
- **`main_signal.py`**: **ENTRY POINT UTAMA.** File yang menyatukan semua logika untuk training, backtesting, dan live signal.
  - Command penting: `--train-dual`, `--train-filter`, `--train-quality`, `--live`.
- **`market_structure_state_machine.py`**: Jantung pencegahan overtrading. Memaksa sistem untuk hanya entry pada bar pertama setelah BoS terbentuk, dan mengabaikan bar-bar berikutnya.

### B. Folder `AI_Trading_Server/models/` (AI Models)
- **`entry_filter_model.py`**: Berisi logika training dan prediksi untuk **Filter Model** (Gate 1). Fokus pada pemisahan market yang bisa ditradingkan vs market *choppy/sideways*.
- **`model_trainer.py`**: Berisi logika training untuk **Quality Model** (XGBoost). Fokus pada membedakan setup WIN dan LOSS dari market yang sudah difilter.
- **`model_predictor.py`**: Memuat class `DualModelPredictor` yang menjalankan Pipeline Prediksi (Filter → Quality) secara runtun saat mode `--live`.
- **`lot_calculator.py`**: Mengkalkulasi ukuran Lot yang aman berdasarkan *tier* konfidensi dan saldo di `config.yml`.

### C. Folder `AI_Trading_Server/data/` (Pabrik Dataset)
- **`data_pipeline.py`**: Pipeline pemrosesan data historis dari CSV MT5 ke DataFrame.
- **`feature_engineer.py`**: Pembuatan fitur turunan (SMC structure age, moving averages, dll).
- **`filter_dataset_builder.py`**: Pipeline khusus untuk membangun dataset untuk training Filter Model.
- **`dataset_builder.py`**: Pipeline untuk membangun dataset untuk training Quality Model.
- **`relabeler.py`**: Implementasi *Sequence-Aware Relabeling* yang memperbaiki label WIN/LOSS berdasarkan pergerakan tick aktual (mengatasi bias SL statis).

### D. Folder `AI_Trading_Server/integrations/` (Live & Telegram)
- **`send_signal_realtime.py`**: Script asinkron untuk format dan kirim pesan sinyal rapi ke Telegram.
- **`live_signal_logger.py`**: Menyimpan sinyal yang dipublish ke `live_signals_log.csv`.
- **`live_outcome_watcher.py`**: Mengawasi pergerakan harga M15 untuk menyelesaikan (resolve) sinyal yang berstatus *PENDING* menjadi WIN/LOSS secara live.
- **`live_to_backtest_converter.py`**: Mengonversi data live menjadi format dataset untuk proses re-training yang berkelanjutan (*continuous learning*).

### E. File Root
- **`main_pipeline_run.py`**: Daemon (*Watcher*) yang terus menyala untuk memantau folder `Backtest_result` dan men-trigger proses signal generation (`main_signal.py --live`).
- **`config.yml`**: Pusat konfigurasi model (Threshold, Telegram Token, Lot sizes, Parameter Relabeling).

---

## 3. Detail: Mode Operasional (`main_signal.py`)

File `main_signal.py` adalah pisau lipat Swiss Army dari sistem ini. Berikut adalah fungsi command-line (CLI) utamanya:

### 3.1 Training Models
```bash
# Melatih secara end-to-end (sangat disarankan)
python core/main_signal.py --train-dual

# Melatih secara terpisah
python core/main_signal.py --train-filter   # Hanya latih Filter Model
python core/main_signal.py --train-quality  # Hanya latih Quality Model (wajib setelah filter)
```

### 3.2 Live Trading & Evaluation
```bash
# Menjalankan generasi sinyal LIVE (biasanya dipanggil oleh daemon)
python core/main_signal.py --live

# Simulasi tanpa kirim Telegram
python core/main_signal.py --live --dry-run
```

---

## 4. Cara Kerja Dual-Model (Filter + Quality)

Pendekatan Dual-Model memecah kompleksitas trading menjadi dua tugas spesifik untuk Machine Learning.

### Masalah Sistem Lama (Single Model)
Sistem lama mencoba memprediksi (WIN vs LOSS) dari seluruh data mentah. Ini membuat AI bingung karena ada kondisi market yang memang *noise* acak (tidak bisa ditradingkan).

### Solusi Dual-Model
1. **Model 1: The Filter (Bouncer)**
   - **Tujuan:** Membuang market yang *choppy*, sesi *dead*, atau struktur tidak jelas.
   - **Data Training:** Semua bar market (Tradeable vs Untradeable).
   - **Output:** `filter_pass` (True/False) dan `filter_score`.
   - *Analogi: Satpam yang tidak membiarkan pengunjung mabuk masuk klub.*

2. **Model 2: The Quality Assessor (Expert)**
   - **Tujuan:** Dari setup yang *bersih*, tentukan apakah ini akan WIN atau LOSS.
   - **Data Training:** Hanya setup yang lolos Model 1 (Filter).
   - **Output:** `win_prob` (0.0 - 1.0) dan tier (`STRONG`/`GOOD`/`WEAK`).
   - *Analogi: Juri ahli yang menilai kualitas setup di dalam klub.*

**Hasil:** Akurasi prediksi (*Precision*) meningkat tajam karena Quality Model tidak lagi dicemari oleh data market yang *random*.

---

## 5. Cara Kerja Market Structure State Machine

EA Dev Bot v7 mengirimkan setiap bar M15. Pada sistem lama, jika trend sedang bullish, sistem akan mengirimkan sinyal BUY pada *setiap bar M15 tunggal* selama kondisi H1/EMA terpenuhi (Spam Sinyal / Overtrading per candle).

**State Machine (`market_structure_state_machine.py`) mengatasi ini dengan cara:**
1. Menyimpan status tren (State) di RAM.
2. Ketika terdeteksi CHoCH baru, state = `CHOCH_PENDING`.
3. Ketika terdeteksi High/Low baru, state = `BOS_PENDING`.
4. Ketika harga menembus High/Low (Break of Structure), state = **`BOS_CONFIRMED`**.
5. **HANYA pada state `BOS_CONFIRMED` (di bar itu saja), sinyal diizinkan untuk dikirim.**
6. Di bar berikutnya, state berubah menjadi `IN_TREND`, dan semua upaya sinyal di-BLOCK hingga ada BoS atau CHoCH baru.

**Manfaat:**
- Tidak ada lagi spam 5-10 sinyal di trend yang sama.
- Sinyal hanya dikirim tepat di titik *breakout / pullback konfirmasi* struktur.

---

## 6. Feedback Loop & Live Outcome Tracking

Sistem yang baru memiliki kemampuan belajar mandiri tanpa bias *hindsight* (*Survivor Bias*).

1. Ketika Sinyal (misal: Sinyal `SMC_BUY_123`) dikirim, ia di-log sebagai `PENDING` di `live_signals_log.csv`.
2. `live_outcome_watcher.py` (yang berjalan di *daemon*) terus memantau harga M15.
3. Ia mensimulasikan harga aktual terhadap SL dan TP yang diberikan pada sinyal.
4. Jika garis SL tersentuh, sinyal di-update menjadi `LOSS`. Jika TP tersentuh, menjadi `WIN`.
5. Data hasil aktual ini nantinya digabungkan ulang dengan dataset backtest melalui `live_to_backtest_converter.py`, sehingga AI dapat dilatih ulang dengan data performa *real* di masa depan.

---

## 7. Format Output Signal JSON & Telegram

Jika sinyal lolos ketiga gerbang (State Machine -> Filter -> Quality), file `signal_latest.json` dibuat dan dikirim ke Telegram.

**Contoh Pesan Telegram:**
```
🤖 𝐀𝐔𝐑𝐀 𝐀𝐈 𝐒𝐢𝐠𝐧𝐚𝐥 𝐀𝐥𝐞𝐫𝐭
━━━━━━━━━━━━━━━━━━
📈 𝐃𝐢𝐫𝐞𝐜𝐭𝐢𝐨𝐧: BUY XAUUSD
📍 𝐄𝐧𝐭𝐫𝐲 𝐙𝐨𝐧𝐞: 2345.50 (± 0.5)

🎯 𝐓𝐚𝐫𝐠𝐞𝐭𝐬 (𝐓𝐏):
   TP1: 2348.00 (RR 1.5)
   TP2: 2351.50 (RR 2.5)
   TP3: 2356.00 (RR 3.6)

🛑 𝐒𝐭𝐨𝐩 𝐋𝐨𝐬𝐬: 2340.50 (50 pips)
📊 𝐋𝐨𝐭 𝐒𝐢𝐳𝐞: 0.15 (Risk 5% | $50)

⚡ 𝐀𝐈 𝐀𝐧𝐚𝐥𝐲𝐬𝐢𝐬:
   Tier: STRONG
   Win Probability: 82.5%
   Filter Score: 95.0%

💡 𝐑𝐞𝐚𝐬𝐨𝐧𝐬:
  • Market Structure State: BOS_CONFIRMED
  • BoS chain: 3 consecutive BoS
  • H1 EMA200 trend aligned
  • London Session Overlap
━━━━━━━━━━━━━━━━━━
```

## Kesimpulan

Dengan arsitektur **Dual-Model + State Machine**, sistem *AI Trading Server* kini bertransformasi dari sekadar alat analisis data historis menjadi sistem generasi sinyal real-time tingkat produksi (*production-grade*) yang memiliki manajemen risiko cerdas dan minim noise/spam.
