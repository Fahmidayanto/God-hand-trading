import re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Define all rich panel contents for side-panel
panels_html = """            <div class="detail-panel" id="side-panel">
                <div class="resize-handle" id="panel-resize-handle"></div>
                <button class="panel-close-btn" onclick="closeSidePanel()" title="Tutup Panel Detail">×</button>
                <div class="panel-placeholder" id="panel-placeholder" style="display: none;">
                    <svg viewBox="0 0 24 24">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="12" y1="16" x2="12" y2="12" />
                        <line x1="12" y1="8" x2="12.01" y2="8" />
                    </svg>
                    <p>Klik salah satu komponen untuk melihat detail arsitektur, parameter, dan relasi data.</p>
                </div>

                <!-- 1. MT5 Terminal -->
                <div class="panel-content" id="panel-mt5">
                    <h2 class="panel-section-title">MetaTrader 5 & MQL5 EA</h2>
                    <p class="panel-text">Terminal trading eksekusi pasar XAUUSD dan Expert Advisor Dev_Bot_v11.cs.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Timeframe</span><span class="meta-value">M15 (Execution), H1, H4 (Multi-TF Bias)</span></li>
                        <li><span class="meta-label">Output Data</span><span class="meta-value">Ekspor CSV berkala per close candle (llhhbosdata, backtest_results, marketdata_m15)</span></li>
                        <li><span class="meta-label">Fungsi</span><span class="meta-value">Deteksi swing Higher High (HH), Lower Low (LL), CHoCH, dan BoS secara lokal.</span></li>
                    </ul>
                </div>

                <!-- 2. Watcher Service -->
                <div class="panel-content" id="panel-watcher">
                    <h2 class="panel-section-title">CSV Watcher Service</h2>
                    <p class="panel-text">Daemon pemantau file CSV lokal MT5 secara inkremental dan realtime.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Teknologi</span><span class="meta-value">Python Watchdog / Polling Daemon</span></li>
                        <li><span class="meta-label">Tugas</span><span class="meta-value">Mendeteksi baris baru, memfilter duplikasi, dan memicu bulk insert ke NeonDB serta koordinasi ke Orchestrator.</span></li>
                    </ul>
                </div>

                <!-- 3. NeonDB Mapping -->
                <div class="panel-content" id="panel-neon">
                    <h2 class="panel-section-title">Pemetaan File CSV ke NeonDB</h2>
                    <p class="panel-text">Database cloud relasional Serverless PostgreSQL untuk penyimpanan riwayat pasar komprehensif.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Tabel Utama</span><span class="meta-value"><code>llhhbosdata_xauusd</code>, <code>marketdata_xauusd_m15</code>, <code>backtest_results_xauusd</code></span></li>
                        <li><span class="meta-label">Penyimpanan</span><span class="meta-value">Candle history 30 hari, struktur swing, session zones, dan sentiment cache 3h.</span></li>
                    </ul>
                </div>

                <!-- 4. LanceDB Vector Storage -->
                <div class="panel-content" id="panel-lancedb">
                    <h2 class="panel-section-title">KNOWLEDGE BASE (LanceDB)</h2>
                    <p class="panel-text">Database vektor berkecepatan tinggi untuk pencocokan pola kesamaan historis (Similarity Search).</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Tabel Vektor</span><span class="meta-value"><code>historical_structures</code>, <code>market_conditions</code>, <code>session_patterns</code></span></li>
                        <li><span class="meta-label">Metrik Kemiripan</span><span class="meta-value">Cosine Similarity &ge; 0.70 memberikan boost confidence +0.3 pada setup SMC.</span></li>
                    </ul>
                </div>

                <!-- 5. Orchestrator Agent -->
                <div class="panel-content" id="panel-orchestrator">
                    <h2 class="panel-section-title">ORCHESTRATOR AGENT</h2>
                    <p class="panel-text">Koordinator pusat alur kerja multi-agen keputusan trading otomatis.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Peran</span><span class="meta-value">Menerima data pasar mentah dari NeonDB & Watcher, mengorkestrasi evaluasi agen (MSA, ML, Sentiment), dan memicu mesin konsensus.</span></li>
                        <li><span class="meta-label">Mode Operasi</span><span class="meta-value">HOLD (Standby), Warm-Up (CHoCH detected), Execution (BoS confirmed).</span></li>
                    </ul>
                </div>

                <!-- Data Transfer: Ghost Engine -> Orchestrator -->
                <div class="panel-content" id="panel-fe-to-orch-info">
                    <h2 class="panel-section-title">Data Transfer: Ghost Engine &rarr; Orchestrator</h2>
                    <p class="panel-text">Aliran payload dari frontend simulasi replay ke backend <code>/simulate-event</code>.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Parameter</span><span class="meta-value">Timestamp event, type (CHoCH/BoS), timeframe M15, dan veto_mode (hard/soft).</span></li>
                        <li><span class="meta-label">Query Backend</span><span class="meta-value">Mengambil candle 30 hari + event struktur + sentimen 3h dari NeonDB.</span></li>
                    </ul>
                </div>

                <!-- Data Transfer: Orchestrator -> MSA -->
                <div class="panel-content" id="panel-orch-to-msa-info">
                    <h2 class="panel-section-title">Data Transfer: Orchestrator &rarr; MSA</h2>
                    <p class="panel-text">Paket data pasar lengkap yang diteruskan Orchestrator ke Market Structure Agent.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Data Grafik</span><span class="meta-value">Candle M15, H1, H4 lengkap dengan EMA200 & ATR.</span></li>
                        <li><span class="meta-label">Riwayat Struktur</span><span class="meta-value">Higher High, Lower Low, CHoCH, dan BoS 30 hari terakhir.</span></li>
                    </ul>
                </div>

                <!-- Data Transfer: MSA -> Orchestrator -->
                <div class="panel-content" id="panel-msa-to-orch-info">
                    <h2 class="panel-section-title">Response: MSA &rarr; Orchestrator</h2>
                    <p class="panel-text">Laporan hasil evaluasi struktur pasar dari MSA ke Orchestrator.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Sinyal & Confidence</span><span class="meta-value">Rekomendasi ("BUY"/"SELL"/"HOLD") dan skor keyakinan SMC (bobot 25%).</span></li>
                        <li><span class="meta-label">Tahapan Pola</span><span class="meta-value">Status CHoCH (pre_signal aktif) atau BoS (sinyal sah konfirmasi).</span></li>
                    </ul>
                </div>

                <!-- Kondisi 1: HOLD -->
                <div class="panel-content" id="panel-orch-cond1">
                    <h2 class="panel-section-title">Kondisi 1: MSA = HOLD (Tidak Ada Setup)</h2>
                    <p class="panel-text">Pasar berada dalam kondisi netral / tanpa pola SMC valid.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Tindakan</span><span class="meta-value">Orchestrator langsung berhenti tanpa memanggil agen ML/Sentimen untuk menghemat resource.</span></li>
                        <li><span class="meta-label">Status Transaksi</span><span class="meta-value">Standby (0 order di MT5).</span></li>
                    </ul>
                </div>

                <!-- Kondisi 2: Warm-Up (CHoCH) -->
                <div class="panel-content" id="panel-orch-cond2">
                    <h2 class="panel-section-title">Kondisi 2: Warm-Up Mode (CHoCH Terdeteksi)</h2>
                    <p class="panel-text">Pola pembalikan tren awal terdeteksi sebelum terbentuk konfirmasi BoS.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Tindakan</span><span class="meta-value">Menjalankan ML Agent & Sentiment Agent di background dan menyimpan skor ke cache persiapan.</span></li>
                        <li><span class="meta-label">Tujuan</span><span class="meta-value">Eksekusi instan 0-latency saat sinyal BoS terkonfirmasi.</span></li>
                    </ul>
                </div>

                <!-- Kondisi 3: Execution (BoS) -->
                <div class="panel-content" id="panel-orch-cond3">
                    <h2 class="panel-section-title">Kondisi 3: Execution Mode (BoS Terkonfirmasi)</h2>
                    <p class="panel-text">Penembusan struktur sah terkonfirmasi, memicu voting konsensus dan eksekusi MT5.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Konsensus</span><span class="meta-value">Voting bobot (MSA 25% + ML 40% + Sent 20%) &ge; 60% lolos ke Risk Management.</span></li>
                        <li><span class="meta-label">Eksekusi</span><span class="meta-value">Kirim order BUY/SELL ke EA MT5 dengan Lot aman dan Dynamic SL/TP.</span></li>
                    </ul>
                </div>

                <!-- Data Transfer HOLD -> ML -->
                <div class="panel-content" id="panel-msa-to-ml-info">
                    <h2 class="panel-section-title">Data Transfer: Kondisi HOLD &rarr; ML (Warm-Up)</h2>
                    <p class="panel-text">Pengiriman data market M15 untuk kalkulasi MFE/MAE awal saat CHoCH aktif.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Fitur Diuji</span><span class="meta-value">19 fitur input XGBoost (spread, ATR, momentum, trend H1/H4).</span></li>
                        <li><span class="meta-label">Hasil Cache</span><span class="meta-value">Disimpan di <code>_latest_warmup_results["ml_prediction"]</code>.</span></li>
                    </ul>
                </div>

                <!-- Data Transfer BoS -> ML -->
                <div class="panel-content" id="panel-bos-to-ml-info">
                    <h2 class="panel-section-title">Data Transfer: Kondisi BoS &rarr; ML (Eksekusi)</h2>
                    <p class="panel-text">Validasi candle eksekusi segar terhadap model regresi XGBoost ganda.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Filter Rasio</span><span class="meta-value">Expected R:R = MFE/MAE wajib &ge; 1.26.</span></li>
                        <li><span class="meta-label">Bobot Konsensus</span><span class="meta-value">Menyumbang 40% bobot voting utama.</span></li>
                    </ul>
                </div>

                <!-- Data Transfer HOLD -> Sentiment -->
                <div class="panel-content" id="panel-msa-to-sent-info">
                    <h2 class="panel-section-title">Data Transfer: Kondisi HOLD &rarr; Sentiment (Warm-Up)</h2>
                    <p class="panel-text">Pemicu pembacaan berita emas di background pada slot anchor 3 jam.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Model LLM</span><span class="meta-value">AgentRouter GLM-5.2 (Tier 1) / Groq Qwen 3.6 27B (Tier 2).</span></li>
                        <li><span class="meta-label">Filter Veto</span><span class="meta-value">Deteksi event High Impact (FOMC/NFP/CPI) &le; 30 menit.</span></li>
                    </ul>
                </div>

                <!-- Data Transfer BoS -> Sentiment -->
                <div class="panel-content" id="panel-bos-to-sent-info">
                    <h2 class="panel-section-title">Data Transfer: Kondisi BoS &rarr; Sentiment (Eksekusi)</h2>
                    <p class="panel-text">Penarikan skor berita instan dari memori cache (0 detik latency).</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Waktu Respons</span><span class="meta-value">0 milidetik (tanpa jeda LLM).</span></li>
                        <li><span class="meta-label">Bobot Konsensus</span><span class="meta-value">Menyumbang 20% bobot voting.</span></li>
                    </ul>
                </div>

                <!-- Market Structure Agent -->
                <div class="panel-content" id="panel-ms-agent">
                    <h2 class="panel-section-title">Market Structure Agent (MSA)</h2>
                    <p class="panel-text">Evaluasi struktur SMC, konfirmasi tren Multi-TF EMA, dan pencocokan LanceDB.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Bobot Voting</span><span class="meta-value">25% (Hak veto keras jika sinyal = HOLD).</span></li>
                    </ul>
                </div>

                <!-- MSA Sub 1 & Sub 2 -->
                <div class="panel-content" id="panel-ms-sub1">
                    <h2 class="panel-section-title">1. Cek EMA Multi-TF</h2>
                    <p class="panel-text">Kalkulasi keselarasan arah close candle terhadap EMA200 di timeframe M15, H1, dan H4.</p>
                </div>
                <div class="panel-content" id="panel-ms-sub2">
                    <h2 class="panel-section-title">2. Kemiripan Pola & Skor (LanceDB)</h2>
                    <p class="panel-text">Pencocokan pola historis di LanceDB (similarity &ge; 0.70) untuk boost confidence.</p>
                </div>

                <!-- ML Agent & Sub Steps -->
                <div class="panel-content" id="panel-ml-agent">
                    <h2 class="panel-section-title">ML Prediction Agent</h2>
                    <p class="panel-text">Model regresi ganda XGBoost untuk memprediksi potensi profit MFE dan risiko MAE.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Bobot Voting</span><span class="meta-value">40% (Bobot terbesar di sistem konsensus).</span></li>
                    </ul>
                </div>
                <div class="panel-content" id="panel-ml-sub1"><h2 class="panel-section-title">1. Inisialisasi & Harga Entri</h2><p class="panel-text">Harga entri diambil dari close candle M15 pemicu.</p></div>
                <div class="panel-content" id="panel-ml-sub2"><h2 class="panel-section-title">2. Rekayasa Fitur</h2><p class="panel-text">19+ fitur input model (ATR14, spread ratio, body ratio, momentum 3/5/10 bar).</p></div>
                <div class="panel-content" id="panel-ml-sub3"><h2 class="panel-section-title">3. Prediksi MFE & MAE</h2><p class="panel-text">Prediksi paralel nilai MFE dan MAE secara simultan.</p></div>
                <div class="panel-content" id="panel-ml-sub4"><h2 class="panel-section-title">4. Denormalisasi ATR</h2><p class="panel-text">Hasil prediksi dikalikan kembali dengan ATR14 pasar aktual.</p></div>
                <div class="panel-content" id="panel-ml-sub5"><h2 class="panel-section-title">5. Uji R:R & Sinyal</h2><p class="panel-text">Validasi expected R:R &ge; 1.26 untuk persetujuan sinyal.</p></div>

                <!-- Sentiment Agent & Sub Steps -->
                <div class="panel-content" id="panel-sentiment-agent">
                    <h2 class="panel-section-title">Sentiment Agent</h2>
                    <p class="panel-text">Analisis berita emas dan event kalender makro ekonomi (Bobot 20%).</p>
                </div>
                <div class="panel-content" id="panel-sent-sub1"><h2 class="panel-section-title">1. Sentimen Berita</h2><p class="panel-text">Analisis berita via GLM-5.2 & Groq Qwen 3.6 dengan slot anchor 3 jam.</p></div>
                <div class="panel-content" id="panel-sent-sub2"><h2 class="panel-section-title">2. Analisis Kalender</h2><p class="panel-text">Deteksi rilis data makro utama (NFP, FOMC, CPI).</p></div>
                <div class="panel-content" id="panel-sent-sub3"><h2 class="panel-section-title">3. Penyesuaian Skor</h2><p class="panel-text">Bonus boost jika berita searah, penalti degradasi jika berlawanan.</p></div>
                <div class="panel-content" id="panel-sent-sub4"><h2 class="panel-section-title">4. Veto High Impact</h2><p class="panel-text">Veto otomatis ke HOLD jika berita super krusial rilis &le; 30 menit.</p></div>
                <div class="panel-content" id="panel-sent-sub5"><h2 class="panel-section-title">5. Shadow Mode & Hasil</h2><p class="panel-text">Pencatatan sentimen ke log audit tanpa mengintervensi eksekusi jika mode shadow aktif.</p></div>

                <!-- Consensus Engine & Sub Steps -->
                <div class="panel-content" id="panel-consensus">
                    <h2 class="panel-section-title">CONSENSUS ENGINE</h2>
                    <p class="panel-text">Penghitungan skor voting tertimbang (MSA 25% + ML 40% + Sent 20%) dengan threshold minimal 60%.</p>
                </div>
                <div class="panel-content" id="panel-con-sub1"><h2 class="panel-section-title">1. Input MSA</h2><p class="panel-text">Sinyal BUY/SELL dan confidence SMC awal (Bobot 25%).</p></div>
                <div class="panel-content" id="panel-con-sub2"><h2 class="panel-section-title">2. Input ML</h2><p class="panel-text">Sinyal validasi XGBoost dan expected R:R (Bobot 40%).</p></div>
                <div class="panel-content" id="panel-con-sub3"><h2 class="panel-section-title">3. Input Sentiment</h2><p class="panel-text">Sinyal terfilter kalender dan skor keyakinan berita (Bobot 20%).</p></div>
                <div class="panel-content" id="panel-con-step1"><h2 class="panel-section-title">1. Pengumpulan Hasil</h2><p class="panel-text">Agregasi arah sinyal dan skor dari ketiga agen evaluasi.</p></div>
                <div class="panel-content" id="panel-con-step2"><h2 class="panel-section-title">2. Skor Voting Tertimbang</h2><p class="panel-text">Perhitungan matematis: <code>0.25*MSA + 0.40*ML + 0.20*Sent</code>.</p></div>
                <div class="panel-content" id="panel-con-step3"><h2 class="panel-section-title">3. Veto & Bypass</h2><p class="panel-text">Aplikasi hak veto keras MSA atau bypass veto jika ML mendeteksi R:R &ge; 1.35.</p></div>
                <div class="panel-content" id="panel-con-step4"><h2 class="panel-section-title">4. Klasifikasi Konsensus</h2><p class="panel-text">Klasifikasi tier kekuatan sinyal (Unanimous, Strong, Moderate, Weak).</p></div>
                <div class="panel-content" id="panel-con-step5"><h2 class="panel-section-title">5. Keputusan Akhir</h2><p class="panel-text">Persetujuan sinyal jika persentase konsensus &ge; 60%.</p></div>

                <!-- Risk Management & Sub Steps -->
                <div class="panel-content" id="panel-risk-agent">
                    <h2 class="panel-section-title">Risk Management</h2>
                    <p class="panel-text">Pengontrol besaran Lot Size, validasi rasio risiko, dan hak veto pasca-konsensus.</p>
                </div>
                <div class="panel-content" id="panel-risk-sub1"><h2 class="panel-section-title">1. Klasifikasi Confidence Tier</h2><p class="panel-text">Penentuan persentase risiko modal berdasarkan tier konsensus.</p></div>
                <div class="panel-content" id="panel-risk-sub2"><h2 class="panel-section-title">2. Kalkulasi Lot Size</h2><p class="panel-text">Kalkulasi lot aman: <code>Lot = RiskUSD / (SL_pips * PipValue)</code> (0.01 - 10.0 lot).</p></div>
                <div class="panel-content" id="panel-risk-sub3"><h2 class="panel-section-title">3. Dynamic SL/TP</h2><p class="panel-text">SL/TP berbasis ATR dan regime volatilitas pasar.</p></div>
                <div class="panel-content" id="panel-risk-sub4"><h2 class="panel-section-title">4. Validasi Risiko</h2><p class="panel-text">Cek batas maksimum SL &le; 500 pips dan total risiko &le; 5% saldo.</p></div>
                <div class="panel-content" id="panel-risk-sub5"><h2 class="panel-section-title">5. Output Final</h2><p class="panel-text">Penerbitan paket order lengkap siap dieksekusi ke EA MT5.</p></div>

                <!-- Execution Agent -->
                <div class="panel-content" id="panel-execution">
                    <h2 class="panel-section-title">EXECUTION AGENT</h2>
                    <p class="panel-text">Pengirim order transaksi (BUY/SELL) ke terminal MT5 EA dan pemantau daily loss limit.</p>
                </div>
            </div>"""

# Replace side panel in HTML
pattern_side_panel = r'<div class="detail-panel" id="side-panel">[\s\S]*?</div>\s*(?=\s*<script>)'
html = re.sub(pattern_side_panel, panels_html + "\n\n        ", html)

# Update cardMap in JavaScript to include ALL cards
cardmap_js = """            // Selection logic with Toggle support & Dynamic Fallback
            function selectNode(type) {
                const panel = document.getElementById('side-panel');
                const cardMap = {
                    'mt5': { cardId: 'node-mt5', panelId: 'panel-mt5', color: 'var(--color-mt5)' },
                    'watcher': { cardId: 'node-watcher-trigger', panelId: 'panel-watcher', color: 'var(--color-watcher)' },
                    'watcher-trigger': { cardId: 'node-watcher-trigger', panelId: 'panel-watcher', color: 'var(--color-watcher)' },
                    'neon': { cardId: 'node-neondb-mapping', panelId: 'panel-neon', color: 'var(--color-neon)' },
                    'neondb-mapping': { cardId: 'node-neondb-mapping', panelId: 'panel-neon', color: 'var(--color-neon)' },
                    'lancedb': { cardId: 'node-lancedb', panelId: 'panel-lancedb', color: 'var(--color-lancedb)' },
                    'orchestrator': { cardId: 'node-orchestrator', panelId: 'panel-orchestrator', color: 'var(--color-orchestrator)' },
                    'fe-to-orch-info': { cardId: 'node-fe-to-orch-info', panelId: 'panel-fe-to-orch-info', color: '#00e5ff' },
                    'orch-to-msa-info': { cardId: 'node-orch-to-msa-info', panelId: 'panel-orch-to-msa-info', color: '#ff1744' },
                    'msa-to-orch-info': { cardId: 'node-msa-to-orch-info', panelId: 'panel-msa-to-orch-info', color: '#00e676' },
                    'orch-cond1': { cardId: 'node-orch-cond1', panelId: 'panel-orch-cond1', color: '#9ca3af' },
                    'orch-cond2': { cardId: 'node-orch-cond2', panelId: 'panel-orch-cond2', color: '#ffaa00' },
                    'orch-cond3': { cardId: 'node-orch-cond3', panelId: 'panel-orch-cond3', color: '#00e676' },
                    'msa-to-ml-info': { cardId: 'node-msa-to-ml-info', panelId: 'panel-msa-to-ml-info', color: '#ffaa00' },
                    'bos-to-ml-info': { cardId: 'node-bos-to-ml-info', panelId: 'panel-bos-to-ml-info', color: '#00e676' },
                    'msa-to-sent-info': { cardId: 'node-msa-to-sent-info', panelId: 'panel-msa-to-sent-info', color: '#ffaa00' },
                    'bos-to-sent-info': { cardId: 'node-bos-to-sent-info', panelId: 'panel-bos-to-sent-info', color: '#00e676' },
                    'ms-agent': { cardId: 'node-ms-agent', panelId: 'panel-ms-agent', color: 'var(--color-watcher)' },
                    'ms-sub1': { cardId: 'node-ms-sub1', panelId: 'panel-ms-sub1', color: 'var(--color-watcher)' },
                    'ms-sub2': { cardId: 'node-ms-sub2', panelId: 'panel-ms-sub2', color: 'var(--color-lancedb)' },
                    'ml-agent': { cardId: 'node-ml-agent', panelId: 'panel-ml-agent', color: 'var(--color-lancedb)' },
                    'ml-sub1': { cardId: 'node-ml-sub1', panelId: 'panel-ml-sub1', color: 'var(--color-lancedb)' },
                    'ml-sub2': { cardId: 'node-ml-sub2', panelId: 'panel-ml-sub2', color: 'var(--color-lancedb)' },
                    'ml-sub3': { cardId: 'node-ml-sub3', panelId: 'panel-ml-sub3', color: 'var(--color-lancedb)' },
                    'ml-sub4': { cardId: 'node-ml-sub4', panelId: 'panel-ml-sub4', color: 'var(--color-lancedb)' },
                    'ml-sub5': { cardId: 'node-ml-sub5', panelId: 'panel-ml-sub5', color: 'var(--color-lancedb)' },
                    'risk-agent': { cardId: 'node-risk-agent', panelId: 'panel-risk-agent', color: 'var(--color-neon)' },
                    'risk-sub1': { cardId: 'node-risk-sub1', panelId: 'panel-risk-sub1', color: 'var(--color-neon)' },
                    'risk-sub2': { cardId: 'node-risk-sub2', panelId: 'panel-risk-sub2', color: 'var(--color-neon)' },
                    'risk-sub3': { cardId: 'node-risk-sub3', panelId: 'panel-risk-sub3', color: 'var(--color-neon)' },
                    'risk-sub4': { cardId: 'node-risk-sub4', panelId: 'panel-risk-sub4', color: 'var(--color-neon)' },
                    'risk-sub5': { cardId: 'node-risk-sub5', panelId: 'panel-risk-sub5', color: 'var(--color-neon)' },
                    'sentiment-agent': { cardId: 'node-sentiment-agent', panelId: 'panel-sentiment-agent', color: '#ff4081' },
                    'sent-sub1': { cardId: 'node-sent-sub1', panelId: 'panel-sent-sub1', color: '#ff4081' },
                    'sent-sub2': { cardId: 'node-sent-sub2', panelId: 'panel-sent-sub2', color: '#ff4081' },
                    'sent-sub3': { cardId: 'node-sent-sub3', panelId: 'panel-sent-sub3', color: '#ff4081' },
                    'sent-sub4': { cardId: 'node-sent-sub4', panelId: 'panel-sent-sub4', color: '#ff4081' },
                    'sent-sub5': { cardId: 'node-sent-sub5', panelId: 'panel-sent-sub5', color: '#ff4081' },
                    'consensus': { cardId: 'node-consensus', panelId: 'panel-consensus', color: 'var(--color-consensus)' },
                    'con-sub1': { cardId: 'node-con-sub1', panelId: 'panel-con-sub1', color: 'var(--color-consensus)' },
                    'con-sub2': { cardId: 'node-con-sub2', panelId: 'panel-con-sub2', color: 'var(--color-consensus)' },
                    'con-sub3': { cardId: 'node-con-sub3', panelId: 'panel-con-sub3', color: 'var(--color-consensus)' },
                    'con-step1': { cardId: 'node-con-step1', panelId: 'panel-con-step1', color: 'var(--color-consensus)' },
                    'con-step2': { cardId: 'node-con-step2', panelId: 'panel-con-step2', color: 'var(--color-consensus)' },
                    'con-step3': { cardId: 'node-con-step3', panelId: 'panel-con-step3', color: 'var(--color-consensus)' },
                    'con-step4': { cardId: 'node-con-step4', panelId: 'panel-con-step4', color: 'var(--color-consensus)' },
                    'con-step5': { cardId: 'node-con-step5', panelId: 'panel-con-step5', color: 'var(--color-consensus)' },
                    'execution': { cardId: 'node-execution', panelId: 'panel-execution', color: 'var(--color-execution)' }
                };

                let config = cardMap[type];
                if (!config) {
                    // Smart fallback for any custom node
                    const guessedCardId = `node-${type}`;
                    const guessedCard = document.getElementById(guessedCardId);
                    if (guessedCard) {
                        config = { cardId: guessedCardId, panelId: `panel-${type}`, color: '#00e5ff' };
                    } else {
                        closeSidePanel();
                        return;
                    }
                }

                // Toggle logic: If this exact card is already selected and panel is open -> Close it!
                if (selectedNodeCardId === config.cardId && panel && panel.classList.contains('open')) {
                    closeSidePanel();
                    return;
                }

                // Otherwise, select and open this node
                document.querySelectorAll('.node-card, .agent-card').forEach(card => card.classList.remove('selected'));
                document.querySelectorAll('.panel-content').forEach(p => p.classList.remove('active'));

                const placeholder = document.getElementById('panel-placeholder');
                if (placeholder) placeholder.style.display = 'none';

                const card = document.getElementById(config.cardId);
                let pnl = document.getElementById(config.panelId);
                
                // Fallback panel generator if specific panel is missing
                if (!pnl && card) {
                    pnl = document.createElement('div');
                    pnl.className = 'panel-content active';
                    pnl.id = config.panelId;
                    const title = card.querySelector('.card-title') ? card.querySelector('.card-title').textContent : type;
                    const content = card.querySelector('.card-content') ? card.querySelector('.card-content').innerHTML : '';
                    pnl.innerHTML = `<h2 class="panel-section-title">${title}</h2><div class="panel-text">${content}</div>`;
                    panel.appendChild(pnl);
                }

                if (card) card.classList.add('selected');
                if (pnl) pnl.classList.add('active');
                
                selectedNodeCardId = config.cardId;
                if (panel) {
                    panel.classList.add('open');
                    panel.style.setProperty('--active-theme-color', config.color);
                }

                // Smoothly focus flow graph
                highlightFlowGraph(config.cardId);
            }"""

pattern_select_node = r'function selectNode\(type\) \{[\s\S]*?highlightFlowGraph\(config\.cardId\);\s*\}'
html = re.sub(pattern_select_node, cardmap_js, html)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("All panels and selectNode mapping fixed 100%!")
