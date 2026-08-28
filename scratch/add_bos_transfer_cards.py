import json, re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"
json_path = r"b:\Project MT5\Other\Dokumen\diagram_layout.json"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update node-msa-to-ml-info and add node-bos-to-ml-info
ml_cards_replacement = """                    <!-- Data Transfer: Kondisi HOLD / Warm-Up -> ML Agent Info Box -->
                    <div class="agent-card" id="node-msa-to-ml-info" onclick="selectNode('msa-to-ml-info')" data-dx="3298" data-dy="-995" data-w="459" data-h="180" style="transform: translate(3298px, -995px); width: 459px; height: 180px;">
                        <div class="card-header" style="margin-bottom: 0.5rem; gap: 0.5rem;">
                            <div class="card-icon"
                                style="font-size: 1rem; width: 28px; height: 28px; border-radius: 6px; color: #ffaa00; background: rgba(255, 170, 0, 0.05);">
                                ⏳</div>
                            <div class="card-title" style="font-size: 0.8rem; color: #ffaa00;">Data Transfer: Kondisi HOLD &rarr; ML</div>
                        </div>
                        <div class="card-content"
                            style="font-size: 0.7rem; line-height: 1.4; color: var(--text-secondary);">
                            • <strong>Pemicu:</strong> Pola CHoCH aktif (Status masih HOLD / Menunggu BoS).<br>
                            • <strong>Data Masuk:</strong> Candle M15, arah setup sementara (BUY/SELL), &amp; 19 fitur indikator.<br>
                            • <strong>Tugas Agen:</strong> Hitung estimasi target MFE &amp; MAE awal via XGBoost.<br>
                            • <strong>Hasil Cache:</strong> Disimpan di memori persiapan agar saat BoS muncul validasi lebih cepat.<br>
                            • <strong>Status Akun:</strong> Tetap HOLD (belum buka posisi di MT5).
                        </div>
                    </div>

                    <!-- Data Transfer: Kondisi BoS -> ML Agent Info Box -->
                    <div class="agent-card" id="node-bos-to-ml-info" onclick="selectNode('bos-to-ml-info')" data-dx="3298" data-dy="-780" data-w="459" data-h="180" style="transform: translate(3298px, -780px); width: 459px; height: 180px;">
                        <div class="card-header" style="margin-bottom: 0.5rem; gap: 0.5rem;">
                            <div class="card-icon"
                                style="font-size: 1rem; width: 28px; height: 28px; border-radius: 6px; color: #00e676; background: rgba(0, 230, 118, 0.05);">
                                ✅</div>
                            <div class="card-title" style="font-size: 0.8rem; color: #00e676;">Data Transfer: Kondisi BoS &rarr; ML</div>
                        </div>
                        <div class="card-content"
                            style="font-size: 0.7rem; line-height: 1.4; color: var(--text-secondary);">
                            • <strong>Pemicu:</strong> Penembusan BoS terkonfirmasi (Sinyal resmi BUY/SELL dari MSA).<br>
                            • <strong>Data Masuk:</strong> Candle M15 eksekusi segar, spread pasar aktual, &amp; nilai ATR.<br>
                            • <strong>Tugas Agen:</strong> Prediksi ulang target MFE/MAE via XGBoost + validasi filter R:R (&ge; 1.26).<br>
                            • <strong>Hasil Skor:</strong> Menghasilkan skor probabilitas kemenangan (bobot voting 40%).<br>
                            • <strong>Status:</strong> Siap dieksekusi bersama ke Konsensus.
                        </div>
                    </div>"""

pattern_ml = r'<!-- Data Transfer: Kondisi HOLD / Warm-Up -> ML Agent Info Box -->[\s\S]*?(?=\s*<!-- ML Prediction Agent Column -->)'
html = re.sub(pattern_ml, ml_cards_replacement + "\n\n", html)

# 2. Update node-msa-to-sent-info and add node-bos-to-sent-info
sent_cards_replacement = """<!-- Data Transfer: Kondisi HOLD -> Sentiment Agent Info Box -->
                    <div class="agent-card" id="node-msa-to-sent-info" onclick="selectNode('msa-to-sent-info')" data-dx="2313" data-dy="-762" data-w="459" data-h="180" style="transform: translate(2313px, -762px); width: 459px; height: 180px;">
                        <div class="card-header" style="margin-bottom: 0.5rem; gap: 0.5rem;">
                            <div class="card-icon"
                                style="font-size: 1rem; width: 28px; height: 28px; border-radius: 6px; color: #ffaa00; background: rgba(255, 170, 0, 0.05);">
                                ⏳</div>
                            <div class="card-title" style="font-size: 0.8rem; color: #ffaa00;">Data Transfer: Kondisi HOLD &rarr; Sent</div>
                        </div>
                        <div class="card-content"
                            style="font-size: 0.7rem; line-height: 1.4; color: var(--text-secondary);">
                            • <strong>Pemicu:</strong> Pola CHoCH aktif (Status masih HOLD / Menunggu BoS).<br>
                            • <strong>Data Masuk:</strong> Waktu candle, arah sinyal awal (BUY/SELL), &amp; kalender berita.<br>
                            • <strong>Tugas Agen:</strong> Baca berita emas via LLM + cek rilis berita bahaya (FOMC/NFP).<br>
                            • <strong>Hasil Cache:</strong> Skor disimpan di memori agar saat BoS muncul eksekusi langsung instan (0 detik).<br>
                            • <strong>Status Akun:</strong> Tetap HOLD (belum buka posisi di MT5).
                        </div>
                    </div>

                    <!-- Data Transfer: Kondisi BoS -> Sentiment Agent Info Box -->
                    <div class="agent-card" id="node-bos-to-sent-info" onclick="selectNode('bos-to-sent-info')" data-dx="2313" data-dy="-540" data-w="459" data-h="180" style="transform: translate(2313px, -540px); width: 459px; height: 180px;">
                        <div class="card-header" style="margin-bottom: 0.5rem; gap: 0.5rem;">
                            <div class="card-icon"
                                style="font-size: 1rem; width: 28px; height: 28px; border-radius: 6px; color: #00e676; background: rgba(0, 230, 118, 0.05);">
                                ✅</div>
                            <div class="card-title" style="font-size: 0.8rem; color: #00e676;">Data Transfer: Kondisi BoS &rarr; Sent</div>
                        </div>
                        <div class="card-content"
                            style="font-size: 0.7rem; line-height: 1.4; color: var(--text-secondary);">
                            • <strong>Pemicu:</strong> Sinyal BoS resmi valid (Arah BUY/SELL terkonfirmasi).<br>
                            • <strong>Data Masuk:</strong> Arah transaksi terkonfirmasi, timestamp eksekusi, &amp; kalender menit ini.<br>
                            • <strong>Tugas Agen:</strong> Langsung tarik skor berita dari cache memori (0 detik) + validasi akhir Veto.<br>
                            • <strong>Hasil Skor:</strong> Skor keyakinan sentimen berita (bobot voting 20% di konsensus).<br>
                            • <strong>Status:</strong> Siap dieksekusi bersama ke Konsensus.
                        </div>
                    </div>"""

pattern_sent = r'<!-- Data Transfer: Kondisi HOLD -> Sentiment Agent Info Box -->[\s\S]*?(?=\s*<!-- Sentiment Agent Column -->)'
html = re.sub(pattern_sent, sent_cards_replacement + "\n\n", html)

# 3. Add Side Panel Detail for both new cards
side_panels_add = """                <div class="panel-content" id="panel-bos-to-ml-info">
                    <h2 class="panel-section-title">Data Transfer: Kondisi BoS &rarr; ML (Eksekusi)</h2>
                    <p class="panel-text">Rincian parameter yang dikirimkan oleh Orchestrator Agent ke ML Prediction Agent saat terjadi <strong>Kondisi BoS Terkonfirmasi</strong> (fase eksekusi transaksi sah).</p>
                    <ul class="meta-list">
                        <li>
                            <span class="meta-label">1. Pemicu &amp; Arah Sinyal Sah</span>
                            <span class="meta-value">
                                • <strong>Pemicu:</strong> Market Structure Agent (MSA) mendeteksi penembusan struktur valid (Break of Structure / BoS).<br>
                                • <strong>Sinyal Resmi:</strong> Diterbitkan sinyal sah <span style="background: rgba(0, 230, 118, 0.15); color: #00e676; padding: 0.05rem 0.3rem; border-radius: 3px; font-weight: bold;">"BUY"</span> atau <span style="background: rgba(255, 23, 68, 0.15); color: #ff5252; padding: 0.05rem 0.3rem; border-radius: 3px; font-weight: bold;">"SELL"</span>.
                            </span>
                        </li>
                        <li>
                            <span class="meta-label">2. Evaluasi XGBoost Eksekusi</span>
                            <span class="meta-value">
                                • Model dual regresi XGBoost menghitung target jarak profit maksimum (MFE) dan batas risiko terburuk (MAE).<br>
                                • <strong>Uji Rasio R:R:</strong> Wajib memenuhi expected R:R &ge; 1.26 untuk lolos ke Mesin Konsensus.
                            </span>
                        </li>
                    </ul>
                </div>

                <div class="panel-content" id="panel-bos-to-sent-info">
                    <h2 class="panel-section-title">Data Transfer: Kondisi BoS &rarr; Sentiment (Eksekusi)</h2>
                    <p class="panel-text">Rincian parameter yang dikirimkan ke Sentiment Agent saat terjadi <strong>Kondisi BoS Terkonfirmasi</strong> untuk memperoleh skor sentimen instan (0-latency).</p>
                    <ul class="meta-list">
                        <li>
                            <span class="meta-label">1. Penarikan Cache Instan</span>
                            <span class="meta-value">
                                • Sentiment Agent langsung menarik skor berita dari cache memori persiapan (tanpa memanggil LLM ulang).<br>
                                • Waktu respons: <strong>0 milidetik</strong>.
                            </span>
                        </li>
                        <li>
                            <span class="meta-label">2. Filter Veto Kalender Menit Terakhir</span>
                            <span class="meta-value">
                                • Melakukan verifikasi akhir apakah ada jadwal rilis berita super krusial (seperti FOMC/NFP) dalam &le; 30 menit.<br>
                                • Jika aman, skor 20% langsung diteruskan ke Mesin Konsensus.
                            </span>
                        </li>
                    </ul>
                </div>"""

if "id=\"panel-bos-to-ml-info\"" not in html:
    html = html.replace(
        '<div class="panel-content" id="panel-msa-to-sent-info">',
        side_panels_add + '\n\n                <div class="panel-content" id="panel-msa-to-sent-info">'
    )

# 4. Add default connections for both new cards
if '"node-bos-to-ml-info"' not in html:
    new_conns = """                { from: "node-ms-sub2", fromPort: "right", to: "node-bos-to-ml-info", toPort: "left" },
                { from: "node-bos-to-ml-info", fromPort: "right", to: "node-ml-agent", toPort: "left" },
                { from: "node-ms-sub2", fromPort: "right", to: "node-bos-to-sent-info", toPort: "left" },
                { from: "node-bos-to-sent-info", fromPort: "right", to: "node-sentiment-agent", toPort: "left" },"""
    html = html.replace(
        '{ from: "node-msa-to-ml-info", fromPort: "right", to: "node-ml-agent", toPort: "left" },',
        '{ from: "node-msa-to-ml-info", fromPort: "right", to: "node-ml-agent", toPort: "left" },\n' + new_conns
    )

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("HTML updated with 2 new BoS Transfer Cards!")

# 5. Update diagram_layout.json
try:
    with open(json_path, "r", encoding="utf-8") as f:
        layout = json.load(f)
    if "nodes" not in layout:
        layout["nodes"] = {}
    layout["nodes"]["node-msa-to-ml-info"] = {"dx": 3298, "dy": -995, "w": 459, "h": 180}
    layout["nodes"]["node-bos-to-ml-info"] = {"dx": 3298, "dy": -780, "w": 459, "h": 180}
    layout["nodes"]["node-msa-to-sent-info"] = {"dx": 2313, "dy": -762, "w": 459, "h": 180}
    layout["nodes"]["node-bos-to-sent-info"] = {"dx": 2313, "dy": -540, "w": 459, "h": 180}

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(layout, f, indent=2)
    print("diagram_layout.json updated successfully with new BoS cards!")
except Exception as e:
    print("JSON update notice:", e)
