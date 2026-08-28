import os

file_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target_card = """                        <div class="card-title" style="font-size: 0.8rem; color: #ffaa00;">Kondisi 2: Warm-Up Mode (CHoCH Detected)</div>
                    </div>
                    <div class="card-content"
                        style="font-size: 0.7rem; line-height: 1.35; color: var(--text-secondary);">
                        <strong style="color: #ffaa00;">Trigger:</strong> signal = "HOLD" + pre_signal berisi arah CHoCH<br><br>
                        <strong>Orchestrator panggil ML Agent + Sentiment Agent secara PARALEL:</strong><br>
                        • ML Agent terima: current_bar, structure_events, h1/h4, session, sinyal arah dari pre_signal<br>
                        • Sentiment Agent terima: sinyal arah, confidence awal, news, calendar<br><br>
                        <strong>Hasilnya disimpan ke cache</strong> (_latest_warmup_results).<br><br>
                        <strong>Dikirim ke Frontend:</strong><br>
                        • final_signal: "HOLD" (paksa, karena MSA masih HOLD)<br>
                        • Panel Agent Consensus diperbarui dengan angka warm-up<br>
                        • Tidak ada trade, menunggu BOS
                    </div>"""

replacement_card = """                        <div class="card-title" style="font-size: 0.8rem; color: #ffaa00;">Kondisi 2: Warm-Up Mode (CHoCH Terdeteksi)</div>
                    </div>
                    <div class="card-content"
                        style="font-size: 0.7rem; line-height: 1.35; color: var(--text-secondary);">
                        <strong>Tanda Pasar (Pemicu):</strong><br>
                        • Muncul sinyal awal pembalikan arah (CHoCH), namun belum ada penembusan kuat (BoS).<br><br>
                        <strong>Persiapan Sistem (Warm-Up):</strong><br>
                        • Orchestrator menjalankan ML Agent dan Sentiment Agent secara bersamaan.<br>
                        • Menghitung estimasi profit/risiko awal dan menganalisis berita, lalu menyimpannya ke memori persiapan agar saat sinyal matang eksekusi bisa instan.<br><br>
                        <strong>Status &amp; Hasil Trading:</strong><br>
                        • <strong>Status:</strong> Tetap HOLD (belum buka posisi di MT5, menunggu konfirmasi BoS).<br>
                        • <strong>Dashboard:</strong> Nilai konsensus mulai muncul di layar agar trader bisa bersiap lebih awal.
                    </div>"""

target_panel = """                <!-- Panel Detail: Kondisi 2 (Warm-up Mode) -->
                <div class="panel-content" id="panel-orch-cond2">
                    <h2 class="panel-section-title">Kondisi 2: Warm-Up Mode (CHoCH Terdeteksi)</h2>
                    <p class="panel-text">Alur kerja Orchestrator saat CHoCH terbentuk: melakukan pra-analisis secara paralel dan menyimpan hasilnya di cache.</p>
                    <ul class="meta-list">
                        <li>
                            <span class="meta-label">Kondisi Pemicu</span>
                            <span class="meta-value">MSA mengembalikan <code>signal = "HOLD"</code> dan <code>pre_signal</code> berisi data arah setup (Bullish/Bearish).</span>
                        </li>
                        <li>
                            <span class="meta-label">Eksekusi Paralel (Multi-Threaded)</span>
                            <span class="meta-value">
                                Orchestrator menjalankan <strong>ML Agent</strong> dan <strong>Sentiment Agent</strong> secara bersamaan menggunakan <code>ThreadPoolExecutor (max_workers=2)</code>:<br>
                                • <strong>ML Agent:</strong> Menghitung prediksi MFE &amp; MAE awal.<br>
                                • <strong>Sentiment Agent:</strong> Menghitung penyesuaian sentimen berita &amp; jadwal kalender.
                            </span>
                        </li>
                        <li>
                            <span class="meta-label">Penyimpanan Cache</span>
                            <span class="meta-value">Hasil kedua sub-agen disimpan ke dalam <code>_latest_warmup_results</code> agar siap digunakan saat konfirmasi BoS tiba.</span>
                        </li>
                        <li>
                            <span class="meta-label">Output ke Frontend</span>
                            <span class="meta-value"><code>final_signal = "HOLD"</code> (karena masih tahap persiapan, belum entry riil). Panel Agent Consensus diperbarui secara real-time.</span>
                        </li>
                    </ul>
                </div>"""

replacement_panel = """                <!-- Panel Detail: Kondisi 2 (Warm-up Mode) -->
                <div class="panel-content" id="panel-orch-cond2">
                    <h2 class="panel-section-title">Kondisi 2: Warm-Up Mode (CHoCH Terdeteksi)</h2>
                    <p class="panel-text">Alur kerja Orchestrator saat pola pembalikan arah (CHoCH) terdeteksi: melakukan pra-analisis persiapan secara paralel dan menyimpan hasilnya di memori cache.</p>
                    <ul class="meta-list">
                        <li>
                            <span class="meta-label">1. Tanda Pasar (Pemicu Awal)</span>
                            <span class="meta-value">Market Structure Agent (MSA) mendeteksi adanya perubahan karakter arah tren (CHoCH), namun formasi belum matang (belum ada Break of Structure / BoS), sehingga sinyal transaksi utama masih bernilai <strong>HOLD</strong> tetapi sudah memiliki petunjuk arah awal (Bullish / Bearish).</span>
                        </li>
                        <li>
                            <span class="meta-label">2. Persiapan Sistem (Eksekusi Paralel)</span>
                            <span class="meta-value">
                                Orchestrator langsung menyalakan <strong>ML Agent</strong> dan <strong>Sentiment Agent</strong> secara bersamaan (multi-threaded):<br>
                                • <strong>ML Agent:</strong> Menghitung estimasi potensi keuntungan (MFE) dan potensi risiko (MAE) awal berbasis data grafik multi-timeframe.<br>
                                • <strong>Sentiment Agent:</strong> Menganalisis berita pasar dan kalender ekonomi terkait mata uang/komoditas yang sedang aktif.
                            </span>
                        </li>
                        <li>
                            <span class="meta-label">3. Penyimpanan Memori Cepat (Warm-Up Cache)</span>
                            <span class="meta-value">Seluruh hasil kalkulasi awal dari kedua agen disimpan ke dalam memori persiapan (cache). Tujuannya agar saat konfirmasi penembusan (BoS) terjadi di candle berikutnya, Orchestrator tidak perlu menghitung ulang dari nol dan order bisa dieksekusi secara instan.</span>
                        </li>
                        <li>
                            <span class="meta-label">4. Status &amp; Tampilan Visual Dashboard</span>
                            <span class="meta-value">
                                • <strong>Status Sinyal:</strong> Tetap "HOLD" (aman, tidak ada order yang dibuka di akun MetaTrader).<br>
                                • <strong>Visual Dashboard:</strong> Panel Consensus di layar mulai menampilkan angka prediksi awal secara real-time agar pengguna dapat memantau persiapan sinyal trading sebelum eksekusi riil.
                            </span>
                        </li>
                    </ul>
                </div>"""

changed = False
if target_card in content:
    content = content.replace(target_card, replacement_card, 1)
    print("Card replaced successfully!")
    changed = True
else:
    print("Target card not found!")

if target_panel in content:
    content = content.replace(target_panel, replacement_panel, 1)
    print("Panel replaced successfully!")
    changed = True
else:
    print("Target panel not found!")

if changed:
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("File saved successfully!")
