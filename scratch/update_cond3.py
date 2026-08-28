import os

file_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target_card = """                <!-- Kondisi 3: BUY/SELL → Eksekusi -->
                <div class="agent-card" id="node-orch-cond3" onclick="selectNode('orch-cond3')" data-dx="2030.7739271507164" data-dy="-2189.128307544807" style="transform: translate(2030.7739271507164px, -2189.128307544807px);">
                    <div class="card-header" style="margin-bottom: 0.5rem; gap: 0.5rem;">
                        <div class="card-icon"
                            style="font-size: 1rem; width: 28px; height: 28px; border-radius: 6px; color: #00e676; background: rgba(0, 230, 118, 0.05);">
                            ✅</div>
                        <div class="card-title" style="font-size: 0.8rem; color: #00e676;">Kondisi 3: Execution Mode (BOS Confirmed)</div>
                    </div>
                    <div class="card-content"
                        style="font-size: 0.7rem; line-height: 1.35; color: var(--text-secondary);">
                        <strong style="color: #00e676;">Trigger:</strong> signal = "BUY" atau "SELL"<br><br>
                        <strong>ML Agent</strong> — dijalankan FRESH (data bar eksekusi terbaru):<br>
                        • current_bar, structure_events, h1/h4, session, sinyal dari MSA<br><br>
                        <strong>Sentiment Agent</strong> — reuse cache warm-up (tidak LLM ulang):<br>
                        • Kalau cache ada → pakai skor yang sudah tersimpan<br>
                        • Kalau tidak ada → jalankan baru<br><br>
                        <strong>Setelah kedua agent selesai:</strong><br>
                        → Consensus: voting MSA(25%) + ML(40%) + Sent(20%)<br>
                        → Kalau total &ge; 60% → Risk Management Agent<br>
                        → Risk tentukan lot, SL, TP<br>
                        → Kirim hasil final ke Frontend (marker + trade dibuka)
                    </div>
                </div>"""

# Handle dynamic attributes for node-orch-cond3
import re

card_pattern = re.compile(r'<!-- Kondisi 3: BUY/SELL → Eksekusi -->\s*<div class="agent-card" id="node-orch-cond3"[^>]*>[\s\S]*?</div>\s*</div>', re.MULTILINE)

replacement_card_inner = """<!-- Kondisi 3: BUY/SELL → Eksekusi -->
                <div class="agent-card" id="node-orch-cond3" onclick="selectNode('orch-cond3')" data-dx="2030.7739271507164" data-dy="-2189.128307544807" style="transform: translate(2030.7739271507164px, -2189.128307544807px);">
                    <div class="card-header" style="margin-bottom: 0.5rem; gap: 0.5rem;">
                        <div class="card-icon"
                            style="font-size: 1rem; width: 28px; height: 28px; border-radius: 6px; color: #00e676; background: rgba(0, 230, 118, 0.05);">
                            ✅</div>
                        <div class="card-title" style="font-size: 0.8rem; color: #00e676;">Kondisi 3: Execution Mode (BoS Terkonfirmasi)</div>
                    </div>
                    <div class="card-content"
                        style="font-size: 0.7rem; line-height: 1.35; color: var(--text-secondary);">
                        <strong>Tanda Pasar (Pemicu):</strong><br>
                        • Terjadi penembusan struktur tren yang sah (BoS), MSA resmi mengeluarkan rekomendasi BUY atau SELL.<br><br>
                        <strong>Evaluasi Multi-Agen &amp; Konsensus:</strong><br>
                        • ML Agent menganalisis candle eksekusi terbaru secara segar untuk kepresisian target.<br>
                        • Sentiment Agent langsung menggunakan skor berita dari memori persiapan (tanpa jeda LLM).<br>
                        • Mesin Konsensus menggabungkan suara (MSA 25% + ML 40% + Sentimen 20%). Jika skor &ge; 60%, sinyal diteruskan ke Manajemen Risiko.<br><br>
                        <strong>Keputusan &amp; Eksekusi Trading:</strong><br>
                        • Risk Agent menghitung ukuran Lot aman, posisi Stop Loss (SL), dan Target Profit (TP).<br>
                        • <strong>Status:</strong> Disetujui (Approved). Order transaksi resmi dibuka di MetaTrader 5 dan tanda panah entry muncul di grafik dashboard.
                    </div>
                </div>"""

panel_pattern = re.compile(r'<!-- Panel Detail: Kondisi 3 \(Execution Mode\) -->\s*<div class="panel-content" id="panel-orch-cond3">[\s\S]*?</div>\s*</div>', re.MULTILINE)

replacement_panel = """<!-- Panel Detail: Kondisi 3 (Execution Mode) -->
                <div class="panel-content" id="panel-orch-cond3">
                    <h2 class="panel-section-title">Kondisi 3: Execution Mode (BoS Terkonfirmasi)</h2>
                    <p class="panel-text">Alur kerja lengkap Orchestrator saat struktur penembusan tren (BoS) terkonfirmasi: memproses voting multi-agen, konsensus skor, manajemen risiko, dan eksekusi order ke MetaTrader 5.</p>
                    <ul class="meta-list">
                        <li>
                            <span class="meta-label">1. Tanda Pasar (Pemicu Eksekusi)</span>
                            <span class="meta-value">Market Structure Agent (MSA) mendeteksi bahwa harga berhasil menembus level penting (Break of Structure / BoS) dan mengonfirmasi arah tren. MSA resmi mengeluarkan sinyal aksi nyata: <strong>BUY</strong> atau <strong>SELL</strong>.</span>
                        </li>
                        <li>
                            <span class="meta-label">2. Evaluasi Multi-Agen Cepat &amp; Akurat</span>
                            <span class="meta-value">
                                • <strong>ML Agent:</strong> Dijalankan secara <em>FRESH</em> pada data candle eksekusi terbaru untuk menghitung probabilitas akurat serta estimasi jarak target keuntungan (MFE) dan batas risiko (MAE).<br>
                                • <strong>Sentiment Agent:</strong> Langsung mengambil hasil evaluasi berita dari memori persiapan (cache warm-up) tanpa perlu memanggil ulang model AI/LLM, memastikan proses berjalan ultra-cepat.
                            </span>
                        </li>
                        <li>
                            <span class="meta-label">3. Gerbang Voting Konsensus &amp; Manajemen Risiko</span>
                            <span class="meta-value">
                                • <strong>Mesin Konsensus:</strong> Menggabungkan bobot keyakinan ketiga agen: <strong>MSA (25%) + ML (40%) + Sentimen (20%)</strong>.<br>
                                • <strong>Ambang Batas Kelulusan:</strong> Jika total skor konsensus &ge; <strong>60%</strong>, sinyal dinyatakan valid dan diteruskan ke <strong>Risk Management Agent</strong>.<br>
                                • <strong>Kalkulasi Risiko:</strong> Risk Agent memvalidasi batas risiko maksimum akun (maks 5%), lalu menghitung ukuran Lot yang aman, titik Stop Loss (SL), dan Take Profit (TP) secara dinamis.
                            </span>
                        </li>
                        <li>
                            <span class="meta-label">4. Hasil Akhir &amp; Eksekusi Order MetaTrader 5</span>
                            <span class="meta-value">
                                • <strong>Status Persetujuan:</strong> Disetujui (<code>approved: true</code>).<br>
                                • <strong>Eksekusi MT5:</strong> Order transaksi (BUY / SELL) langsung dibuka di akun MetaTrader 5.<br>
                                • <strong>Tampilan Visual:</strong> Dashboard menampilkan tanda panah entry (Marker) pada grafik simulasi beserta ringkasan lengkap data konsensus.
                            </span>
                        </li>
                    </ul>
                </div>"""

if card_pattern.search(content):
    content = card_pattern.sub(replacement_card_inner, content, count=1)
    print("Card replaced via regex!")
else:
    print("Card regex not matched!")

if panel_pattern.search(content):
    content = panel_pattern.sub(replacement_panel, content, count=1)
    print("Panel replaced via regex!")
else:
    print("Panel regex not matched!")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File saved successfully!")
