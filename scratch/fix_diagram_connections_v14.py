import json
from pathlib import Path

html_path = Path(r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html")
json_path = Path(r"b:\Project MT5\Other\Dokumen\diagram_layout.json")

layout_data = json.loads(json_path.read_text(encoding="utf-8"))

# Read current HTML
html_content = html_path.read_text(encoding="utf-8")

# Panel HTML blocks to restore
missing_panels = """                <div class="panel-content" id="panel-con-sub1"><h2 class="panel-section-title">1. Input MSA</h2><p class="panel-text">Sinyal BUY/SELL/HOLD, phase, confidence, dan evidence snapshot deterministic.</p></div>
                <div class="panel-content" id="panel-con-sub2"><h2 class="panel-section-title">2. Input ML</h2><p class="panel-text">Sinyal validasi XGBoost, confidence, expected MFE/MAE, dan expected R:R.</p></div>
                <div class="panel-content" id="panel-con-sub3"><h2 class="panel-section-title">3. Input Sentiment</h2><p class="panel-text">Sinyal terfilter kalender, confidence, freshness, dan status high-impact event.</p></div>
                <div class="panel-content" id="panel-con-step1"><h2 class="panel-section-title">1. Pengumpulan Hasil</h2><p class="panel-text">Agregasi arah sinyal dan skor dari ketiga agen evaluasi.</p></div>
                <div class="panel-content" id="panel-con-step2"><h2 class="panel-section-title">2. Skor Voting Tertimbang</h2><p class="panel-text">Council Gate menghitung setiap kontribusi dengan <code>weight x confidence x data_quality</code>.</p></div>
                <div class="panel-content" id="panel-con-step3"><h2 class="panel-section-title">3. Hard Gate MSA</h2><p class="panel-text">MSA HOLD atau phase selain <code>BOS_TRIGGERED</code> selalu menghasilkan HOLD. Tidak ada bypass arah.</p></div>
                <div class="panel-content" id="panel-con-step4"><h2 class="panel-section-title">4. Klasifikasi Konsensus</h2><p class="panel-text">Klasifikasi tier kekuatan sinyal (Unanimous, Strong, Moderate, Weak).</p></div>
                <div class="panel-content" id="panel-con-step5"><h2 class="panel-section-title">5. Keputusan Akhir</h2><p class="panel-text">Persetujuan sinyal jika MSA BOS_TRIGGERED, arah valid, dan skor council >= 60%.</p></div>

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
            </div>

        <script>
            // Default System Connections with Specific Port Assignments
            const defaultConnections = """ + json.dumps(layout_data["connections"], indent=16) + """;

            let connections = [...defaultConnections];
            const LAYOUT_VERSION = """ + str(layout_data["version"]) + """; // ponytail: bump when defaultConnections change

            // Baked-in Default Layout State (Used when localStorage is empty or on different browser)
            const defaultLayoutState = """ + json.dumps(layout_data, indent=4) + """;
"""

# Split before // Baked-in Default Layout State or similar
marker_start = '<div class="panel-content" id="panel-consensus">'
pos_start = html_content.find(marker_start)
if pos_start == -1:
    raise ValueError("Cannot find marker_start")

# Find closing of panel-consensus
marker_end_panel = '</div>'
pos_end_panel = html_content.find(marker_end_panel, pos_start) + len(marker_end_panel)

# Find where selection flow starts: "// Selection & Hover Flow State"
marker_js_rest = "// Selection & Hover Flow State"
pos_js_rest = html_content.find(marker_js_rest)
if pos_js_rest == -1:
    raise ValueError("Cannot find marker_js_rest")

new_html = html_content[:pos_end_panel] + "\n" + missing_panels + "\n" + html_content[pos_js_rest:]
html_path.write_text(new_html, encoding="utf-8")
print("Successfully reconstructed diagram_arsitektur.html with v14!")
