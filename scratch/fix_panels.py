# -*- coding: utf-8 -*-
"""
Helper script to precisely insert all missing side panels into diagram_arsitektur.html
"""
import re

target_file = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

# Marker before which we insert everything
marker_start = '                                • <strong>Skala Dinamis (Price Ratio):</strong> bernilai <code>0.5589</code> (Close 2515.20 / Base 4500.0) untuk menjaga scaling jarak swing proporsional lintas tahun.\n                            </span>\n                        </li>'

# Marker after which sentiment begins
marker_end = '                    <h2 class="panel-section-title">Sentiment Agent</h2>'

replacement_block = '''                                • <strong>Skala Dinamis (Price Ratio):</strong> bernilai <code>0.5589</code> (Close 2515.20 / Base 4500.0) untuk menjaga scaling jarak swing proporsional lintas tahun.
                            </span>
                        </li>
                        <li>
                            <span class="meta-label">C. Riwayat Titik Swing &amp; Deteksi CHoCH</span>
                            <span class="meta-value">
                                • <strong>Titik LL (2502.50):</strong> Dasar harga terendah dari fase downtrend sebelumnya.<br>
                                • <strong>Swing High Acuan (2514.80):</strong> Titik puncak resisten swing terdekat.<br>
                                • <strong>Kunci Terjadinya CHoCH:</strong> Karena harga close (<code>2515.20</code>) <strong>&gt;</strong> Swing High (<code>2514.80</code>), struktur downtrend resmi patah dan berubah menjadi <span style="background: rgba(0, 230, 118, 0.15); color: #00e676; padding: 0.05rem 0.3rem; border-radius: 3px; font-weight: bold;">CHoCH Bullish</span>.
                            </span>
                        </li>
                        <li>
                            <span class="meta-label">D. Keselarasan Tren Makro (multi_tf_bias)</span>
                            <span class="meta-value">
                                • <strong>H1 Trend:</strong> Close 2515.20 &gt; EMA200 (2498.40) &rarr; <span style="color: #00e676; font-weight: bold;">Bullish</span>.<br>
                                • <strong>H4 Trend:</strong> Close 2515.20 &gt; EMA200 (2486.10) &rarr; <span style="color: #00e676; font-weight: bold;">Bullish</span>.<br>
                                • <strong>Hasil Evaluasi Veto:</strong> Selaras 100% dengan tren makro &rarr; <span style="color: #00e676; font-weight: bold;">Lolos Filter Veto</span>.
                            </span>
                        </li>
                    </ul>

                    <h3 style="color: #00e676; font-size: 0.85rem; margin: 1.2rem 0 0.4rem; text-transform: uppercase; letter-spacing: 0.5px;">3. Respon Balasan dari MSA ke Orchestrator</h3>
                    <div style="padding: 0.75rem; background: rgba(0, 230, 118, 0.05); border-left: 3px solid #00e676; border-radius: 4px; font-size: 0.74rem; line-height: 1.5; color: #fff;">
                        • <strong>Sinyal Resmi:</strong> <code>"HOLD"</code> (menahan order karena BoS belum terbentuk).<br>
                        • <strong>Phase:</strong> <code>"WARMUP"</code> (mengaktifkan mode persiapan).<br>
                        • <strong>Pre-Signal Context:</strong> <code>{ direction: "Bullish", type: "CHoCH", trigger_price: 2515.20, target_bos_level: 2522.40 }</code>.<br>
                        • <strong>Tindakan Orchestrator:</strong> Meneruskan <code>pre_signal</code> ke ML Agent dan Sentiment Agent di background agar skor selesai dihitung sebelum konfirmasi BoS tiba (eksekusi 0-latency).
                    </div>
                </div>

                <!-- Data Transfer: MSA -> Orchestrator -->
                <div class="panel-content" id="panel-msa-to-orch-info">
                    <h2 class="panel-section-title">Response: MSA &rarr; Orchestrator</h2>
                    <p class="panel-text">Laporan hasil evaluasi struktur pasar dari MSA ke Orchestrator.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Sinyal &amp; Confidence</span><span class="meta-value">Rekomendasi ("BUY"/"SELL"/"HOLD") dan skor keyakinan SMC (bobot 25%).</span></li>
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
                        <li><span class="meta-label">Tindakan</span><span class="meta-value">Menjalankan ML Agent &amp; Sentiment Agent di background dan menyimpan skor ke cache persiapan.</span></li>
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

                <!-- Market Structure Agent Main Panel -->
                <div class="panel-content" id="panel-ms-agent">
                    <h2 class="panel-section-title">Market Structure Agent (MSA) - SMC Analysis</h2>
                    <p class="panel-text">Agen inti evaluasi struktur Smart Money Concept (SMC) timeframe M15 yang memegang bobot voting 25% dan hak veto awal.</p>
                    
                    <h3 style="color: #00e5ff; font-size: 0.85rem; margin: 1rem 0 0.4rem; text-transform: uppercase; letter-spacing: 0.5px;">Langkah 1: Ekstraksi Data &amp; Urutan Event Pasar</h3>
                    <p class="panel-text" style="font-size: 0.73rem;">Saat Orchestrator memanggil <code>MarketStructureAgent.analyze(...)</code>, agen mengekstrak parameter kunci dan mengurutkan 3 event struktur terkonfirmasi terbaru (<code>e1</code>, <code>e2</code>, <code>e3</code>):</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Harga &amp; Skala</span><span class="meta-value"><code>current_price</code> (2515.20 USD) &amp; <code>price_ratio = 2515.20 / 4500.0 = 0.5589</code> (Base 4500.0).</span></li>
                        <li><span class="meta-label">Indikator Tren</span><span class="meta-value">EMA200 M15 (2505.10), H1 (2498.40), H4 (2486.10).</span></li>
                        <li><span class="meta-label">Riwayat Struktur</span><span class="meta-value">Daftar event terkonfirmasi 30 hari diurutkan kronologis terbalik (terbaru di posisi teratas).</span></li>
                    </ul>

                    <h3 style="color: #ffd600; font-size: 0.85rem; margin: 1rem 0 0.4rem; text-transform: uppercase; letter-spacing: 0.5px;">Contoh Data Nyata (Ekstraksi Input M15)</h3>
                    <div style="background: rgba(10, 14, 26, 0.85); border: 1px solid rgba(0, 229, 255, 0.3); border-radius: 6px; padding: 0.75rem; font-family: monospace; font-size: 0.72rem; line-height: 1.45; color: #e2e8f0; overflow-x: auto; margin-bottom: 1rem;">
<pre style="margin: 0; white-space: pre-wrap;">{
  <span style="color: #00e5ff;">"current_price"</span>: 2515.20,
  <span style="color: #00e5ff;">"price_ratio"</span>: 0.5589,
  <span style="color: #00e5ff;">"base_reference_price"</span>: 4500.0,
  <span style="color: #00e5ff;">"session"</span>: <span style="color: #ffd600;">"London"</span>,
  <span style="color: #00e5ff;">"latest_events"</span>: [
    {<span style="color: #00e5ff;">"pos"</span>: <span style="color: #ffd600;">"e1"</span>, <span style="color: #00e5ff;">"type"</span>: <span style="color: #ffd600;">"CHOCH"</span>, <span style="color: #00e5ff;">"dir"</span>: <span style="color: #00e676;">"Bullish"</span>, <span style="color: #00e5ff;">"price"</span>: 2514.80, <span style="color: #00e5ff;">"time"</span>: <span style="color: #ffd600;">"11:45:00"</span>},
    {<span style="color: #00e5ff;">"pos"</span>: <span style="color: #ffd600;">"e2"</span>, <span style="color: #00e5ff;">"type"</span>: <span style="color: #ffd600;">"LL"</span>,    <span style="color: #00e5ff;">"dir"</span>: <span style="color: #ff5252;">"Update"</span>,  <span style="color: #00e5ff;">"price"</span>: 2502.50, <span style="color: #00e5ff;">"time"</span>: <span style="color: #ffd600;">"09:30:00"</span>},
    {<span style="color: #00e5ff;">"pos"</span>: <span style="color: #ffd600;">"e3"</span>, <span style="color: #00e5ff;">"type"</span>: <span style="color: #ffd600;">"LH"</span>,    <span style="color: #00e5ff;">"dir"</span>: <span style="color: #ff5252;">"Update"</span>,  <span style="color: #00e5ff;">"price"</span>: 2518.00, <span style="color: #00e5ff;">"time"</span>: <span style="color: #ffd600;">"08:15:00"</span>}
  ]
}</pre>
                    </div>
                </div>

                <!-- MSA Sub 1: State Machine 2-Tahap -->
                <div class="panel-content" id="panel-ms-sub1">
                    <h2 class="panel-section-title">1. State Machine 2-Tahap (CHoCH &amp; BoS)</h2>
                    <p class="panel-text">Mesin status internal MSA untuk membedakan fase persiapan (Warm-Up) dan fase eksekusi (Execution Trigger).</p>
                    
                    <h3 style="color: #00e5ff; font-size: 0.85rem; margin: 1rem 0 0.4rem; text-transform: uppercase; letter-spacing: 0.5px;">Alur Transisi Fase</h3>
                    <ul class="meta-list">
                        <li><span class="meta-label">IDLE</span><span class="meta-value">Belum ada struktur SMC terkonfirmasi ➔ Sinyal <code>HOLD</code> (Confidence = 0.3).</span></li>
                        <li><span class="meta-label">PENDING_SETUP (Warm-Up)</span><span class="meta-value">Terjadi <code>CHoCH</code> lalu terbentuk titik swing baru (<code>HH</code> untuk Bullish / <code>LL</code> untuk Bearish). Mengunci harga acuan trigger BoS. Sinyal tetap <code>HOLD</code>, namun menerbitkan <code>pre_signal</code> agar ML &amp; Sentiment Agent bersiap di background.</span></li>
                        <li><span class="meta-label">BOS_TRIGGERED (Execution)</span><span class="meta-value">Harga menembus level swing acuan (Break of Structure). Sinyal berubah resmi menjadi <code>BUY</code> atau <code>SELL</code>.</span></li>
                    </ul>

                    <h3 style="color: #00e676; font-size: 0.85rem; margin: 1rem 0 0.4rem; text-transform: uppercase; letter-spacing: 0.5px;">Contoh Kasus Nyata (XAUUSD Setup Bullish)</h3>
                    <div style="padding: 0.75rem; background: rgba(0, 230, 118, 0.05); border-left: 3px solid #00e676; border-radius: 4px; font-size: 0.74rem; line-height: 1.5; color: #fff; margin-bottom: 1rem;">
                        • <strong>Step A:</strong> Muncul <code>CHOCH Bullish</code> di harga <code>2514.80</code>.<br>
                        • <strong>Step B:</strong> Terbentuk swing <code>HH</code> di harga <code>2518.50</code> ➔ State berubah menjadi <code>PENDING_SETUP</code>, mengunci target trigger BoS di <code>2518.50</code>.<br>
                        • <strong>Step C:</strong> Candle M15 berikutnya close di <code>2520.10</code> (&gt; 2518.50) ➔ Terjadi <code>BoS Bullish</code>. State berubah ke <code>BOS_TRIGGERED</code> dan MSA resmi merilis rekomendasi <code>BUY</code>.
                    </div>
                </div>

                <!-- MSA Sub 2: Filter Veto Multi-TF EMA -->
                <div class="panel-content" id="panel-ms-sub2">
                    <h2 class="panel-section-title">2. Filter Veto Multi-TF EMA (M15, H1, H4)</h2>
                    <p class="panel-text">Validasi keselarasan arah sinyal M15 terhadap tren makro timeframe yang lebih besar untuk mencegah jebakan false breakout.</p>
                    
                    <h3 style="color: #00e5ff; font-size: 0.85rem; margin: 1rem 0 0.4rem; text-transform: uppercase; letter-spacing: 0.5px;">Aturan Pembobotan &amp; Veto</h3>
                    <ul class="meta-list">
                        <li><span class="meta-label">M15 EMA200 (+0.2)</span><span class="meta-value">Close M15 di atas EMA200 = Bullish (+0.2), di bawah = Bearish (-0.2).</span></li>
                        <li><span class="meta-label">H1 EMA200 (&plusmn;0.1)</span><span class="meta-value">Tren H1 selaras menambah +0.1, berlawanan mengurangi -0.1.</span></li>
                        <li><span class="meta-label">H4 EMA200 (&plusmn;0.1)</span><span class="meta-value">Tren H4 selaras menambah +0.1, berlawanan mengurangi -0.1.</span></li>
                        <li><span class="meta-label">Mode Hard Veto</span><span class="meta-value">Jika sinyal BUY muncul saat tren H1 atau H4 Bearish, sinyal <strong>langsung dibatalkan / di-veto menjadi HOLD</strong> (Confidence = 0.0).</span></li>
                    </ul>

                    <h3 style="color: #ffd600; font-size: 0.85rem; margin: 1rem 0 0.4rem; text-transform: uppercase; letter-spacing: 0.5px;">Contoh Perhitungan Nyata</h3>
                    <div style="background: rgba(10, 14, 26, 0.85); border: 1px solid rgba(255, 214, 0, 0.3); border-radius: 6px; padding: 0.75rem; font-family: monospace; font-size: 0.72rem; line-height: 1.45; color: #e2e8f0; overflow-x: auto; margin-bottom: 1rem;">
• Harga Close M15 : 2515.20 &gt; EMA200 (2505.10) ➔ +0.2 (Bullish)
• Harga Close H1  : 2515.20 &gt; EMA200 (2498.40) ➔ +0.1 (Bullish)
• Harga Close H4  : 2515.20 &gt; EMA200 (2486.10) ➔ +0.1 (Bullish)
─────────────────────────────────────────────────────────────
Hasil Evaluasi : Selaras 100% (Skor Makro = 1.0) ➔ LOLOS VETO FILTER
                    </div>
                </div>

                <!-- MSA Sub 3: Pencocokan Pola LanceDB -->
                <div class="panel-content" id="panel-ms-sub3">
                    <h2 class="panel-section-title">3. Pencocokan Pola Historis (LanceDB)</h2>
                    <p class="panel-text">Pencarian pola fraktal swing serupa di database vektor LanceDB untuk menguji probabilitas keberhasilan berbasis data masa lalu.</p>
                    
                    <h3 style="color: #00e5ff; font-size: 0.85rem; margin: 1rem 0 0.4rem; text-transform: uppercase; letter-spacing: 0.5px;">Mekanisme Vector Similarity</h3>
                    <ul class="meta-list">
                        <li><span class="meta-label">Vektor Embedding</span><span class="meta-value">Bentuk sekuens harga (jarak HH/LL, rasio swing, durasi candle) dikonversi ke vektor embedding 128-dimensi.</span></li>
                        <li><span class="meta-label">Threshold Kemiripan</span><span class="meta-value">Cosine Similarity &ge; 0.70 dianggap pola valid.</span></li>
                        <li><span class="meta-label">Dampak ke Skor</span><span class="meta-value">Pola historis dengan win rate tinggi memberikan <strong>boost keyakinan +0.25 s/d +0.30</strong>. Pola gagal memberikan penalti -0.10.</span></li>
                    </ul>

                    <h3 style="color: #b388ff; font-size: 0.85rem; margin: 1rem 0 0.4rem; text-transform: uppercase; letter-spacing: 0.5px;">Contoh Pencocokan Vektor Nyata</h3>
                    <div style="padding: 0.75rem; background: rgba(179, 136, 255, 0.05); border-left: 3px solid #b388ff; border-radius: 4px; font-size: 0.74rem; line-height: 1.5; color: #fff; margin-bottom: 1rem;">
                        • <strong>Query Vektor:</strong> Setup CHoCH Bullish M15 (26 Agustus 2026).<br>
                        • <strong>Match Terdekat:</strong> Tabel <code>historical_structures</code> ID #8492 (14 Juli 2026).<br>
                        • <strong>Cosine Similarity:</strong> <code>0.842</code> (Sangat Mirip).<br>
                        • <strong>Hasil Historis:</strong> Win Rate = 78% (MFE Rata-rata 180 Pips / MAE 35 Pips).<br>
                        • <strong>Dampak Confidence:</strong> Skor dasar 0.60 + Boost LanceDB 0.25 ➔ <strong>Confidence = 0.85</strong>.
                    </div>
                </div>

                <!-- MSA Sub 4: Respon ke Orchestrator -->
                <div class="panel-content" id="panel-ms-sub4">
                    <h2 class="panel-section-title">4. Respon Balasan ke Orchestrator</h2>
                    <p class="panel-text">Paket output hasil analisis komprehensif yang dikembalikan oleh MSA ke Orchestrator untuk proses voting konsensus multi-agen.</p>
                    
                    <h3 style="color: #00e676; font-size: 0.85rem; margin: 1rem 0 0.4rem; text-transform: uppercase; letter-spacing: 0.5px;">Contoh JSON Response Nyata (Output analyze())</h3>
                    <div style="background: rgba(10, 14, 26, 0.85); border: 1px solid rgba(0, 230, 118, 0.3); border-radius: 6px; padding: 0.75rem; font-family: monospace; font-size: 0.72rem; line-height: 1.45; color: #e2e8f0; overflow-x: auto; margin-bottom: 1rem;">
<pre style="margin: 0; white-space: pre-wrap;">{
  <span style="color: #00e5ff;">"agent"</span>: <span style="color: #ffd600;">"MarketStructureAgent"</span>,
  <span style="color: #00e5ff;">"version"</span>: <span style="color: #ffd600;">"3.0.0"</span>,
  <span style="color: #00e5ff;">"signal"</span>: <span style="color: #00e676;">"BUY"</span>,
  <span style="color: #00e5ff;">"confidence"</span>: 0.85,
  <span style="color: #00e5ff;">"phase"</span>: <span style="color: #ffd600;">"BOS_TRIGGERED"</span>,
  <span style="color: #00e5ff;">"is_new_setup"</span>: true,
  <span style="color: #00e5ff;">"metadata"</span>: {
    <span style="color: #00e5ff;">"current_price"</span>: 2520.10,
    <span style="color: #00e5ff;">"price_ratio"</span>: 0.5600,
    <span style="color: #00e5ff;">"base_reference_price"</span>: 4500.0,
    <span style="color: #00e5ff;">"ema200_m15"</span>: 2505.10,
    <span style="color: #00e5ff;">"price_vs_ema"</span>: <span style="color: #00e676;">"ABOVE"</span>
  },
  <span style="color: #00e5ff;">"reasoning"</span>: <span style="color: #ffd600;">"BoS Bullish terkonfirmasi di 2520.10. Selaras 100% dengan EMA200 M15/H1/H4 dan didukung kemiripan pola LanceDB 0.842 (Win Rate 78%)."</span>
}</pre>
                    </div>
                </div>

                <!-- ML Agent & Sub Steps -->
                <div class="panel-content" id="panel-ml-agent">
                    <h2 class="panel-section-title">ML Prediction Agent</h2>
                    <p class="panel-text">Model regresi ganda XGBoost untuk memprediksi potensi profit MFE dan risiko MAE.</p>
                    <ul class="meta-list">
                        <li><span class="meta-label">Bobot Voting</span><span class="meta-value">40% (Bobot terbesar di sistem konsensus).</span></li>
                    </ul>
                </div>
                <div class="panel-content" id="panel-ml-sub1"><h2 class="panel-section-title">1. Inisialisasi &amp; Harga Entri</h2><p class="panel-text">Harga entri diambil dari close candle M15 pemicu.</p></div>
                <div class="panel-content" id="panel-ml-sub2"><h2 class="panel-section-title">2. Rekayasa Fitur</h2><p class="panel-text">19+ fitur input model (ATR14, spread ratio, body ratio, momentum 3/5/10 bar).</p></div>
                <div class="panel-content" id="panel-ml-sub3"><h2 class="panel-section-title">3. Prediksi MFE &amp; MAE</h2><p class="panel-text">Prediksi paralel nilai MFE dan MAE secara simultan.</p></div>
                <div class="panel-content" id="panel-ml-sub4"><h2 class="panel-section-title">4. Denormalisasi ATR</h2><p class="panel-text">Hasil prediksi dikalikan kembali dengan ATR14 pasar aktual.</p></div>
                <div class="panel-content" id="panel-ml-sub5"><h2 class="panel-section-title">5. Uji R:R &amp; Sinyal</h2><p class="panel-text">Validasi expected R:R &ge; 1.26 untuk persetujuan sinyal.</p></div>

                <!-- Sentiment Agent & Sub Steps -->
                <div class="panel-content" id="panel-sentiment-agent">
                    <h2 class="panel-section-title">Sentiment Agent</h2>'''

idx_start = content.find(marker_start)
idx_end = content.find(marker_end)

if idx_start != -1 and idx_end != -1:
    new_content = content[:idx_start] + replacement_block + content[idx_end + len(marker_end):]
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("SUCCESS: File updated cleanly.")
else:
    print(f"ERROR: Markers not found. idx_start={idx_start}, idx_end={idx_end}")
