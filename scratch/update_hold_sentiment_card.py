import re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update the Card in the Canvas (id="node-msa-to-sent-info")
old_card_pattern = r'<!-- Data Transfer: MSA -> Sentiment Agent Info Box -->\s*<div class="agent-card" id="node-msa-to-sent-info"[\s\S]*?</div>\s*</div>'

new_card_html = """<!-- Data Transfer: Kondisi HOLD -> Sentiment Agent Info Box -->
                    <div class="agent-card" id="node-msa-to-sent-info" onclick="selectNode('msa-to-sent-info')" data-dx="2324" data-dy="-553" data-h="220" style="transform: translate(2324px, -553px); height: 220px;">
                        <div class="card-header" style="margin-bottom: 0.5rem; gap: 0.5rem;">
                            <div class="card-icon"
                                style="font-size: 1rem; width: 28px; height: 28px; border-radius: 6px; color: #ffaa00; background: rgba(255, 170, 0, 0.05);">
                                ⏳</div>
                            <div class="card-title" style="font-size: 0.8rem; color: #ffaa00;">Data Transfer: Kondisi HOLD &rarr; Sent</div>
                        </div>
                        <div class="card-content"
                            style="font-size: 0.7rem; line-height: 1.35; color: var(--text-secondary);">
                            • <strong>Pemicu (Trigger):</strong> MSA = "HOLD" + <code>pre_signal</code> aktif (Pola CHoCH terdeteksi).<br>
                            • <strong>Data ke Sentiment:</strong> Timestamp event, arah bias sementara ("BUY"/"SELL"), serta kalender berita high impact.<br>
                            • <strong>Proses Analisis:</strong> Analisis berita emas via LLM AgentRouter (GLM-5.2 / Groq Qwen 3.6), slot anchor 3 jam, dan cek filter veto FOMC/NFP.<br>
                            • <strong>Hasil Warm-Up:</strong> Skor sentimen &amp; status veto di-cache ke memori persiapan (siap saat konfirmasi BoS muncul).
                        </div>
                    </div>"""

html = re.sub(old_card_pattern, new_card_html, html)

# 2. Update the Side Panel Detail (id="panel-msa-to-sent-info")
old_panel_pattern = r'<div class="panel-content" id="panel-msa-to-sent-info">[\s\S]*?</div>\s*</div>'

new_panel_html = """<div class="panel-content" id="panel-msa-to-sent-info">
                    <h2 class="panel-section-title">Data Transfer: Kondisi HOLD &rarr; Sentiment (Warm-Up)</h2>
                    <p class="panel-text">Rincian parameter yang dikirimkan oleh Orchestrator Agent ke Sentiment Agent saat terjadi <strong>Kondisi HOLD dengan Pre-Signal</strong> (fase warm-up persiapan saat CHoCH terdeteksi sebelum konfirmasi BoS).</p>
                    <ul class="meta-list">
                        <li>
                            <span class="meta-label">1. Pemicu &amp; Arah Setup (Pre-Signal)</span>
                            <span class="meta-value">
                                • <strong>Pemicu:</strong> Market Structure Agent (MSA) mendeteksi pembalikan arah awal (CHoCH) namun belum ada penembusan tren (BoS), sehingga status = "HOLD".<br>
                                • <strong>Arah Setup:</strong> Nilai <code>pre_signal.direction</code> diterjemahkan menjadi sinyal evaluasi sementara:<br>
                                &nbsp;&nbsp;&bull; Bullish &rarr; Target uji berita: <span style="background: rgba(0, 230, 118, 0.15); color: #00e676; padding: 0.05rem 0.3rem; border-radius: 3px; font-weight: bold;">"BUY"</span><br>
                                &nbsp;&nbsp;&bull; Bearish &rarr; Target uji berita: <span style="background: rgba(255, 23, 68, 0.15); color: #ff5252; padding: 0.05rem 0.3rem; border-radius: 3px; font-weight: bold;">"SELL"</span>
                            </span>
                        </li>
                        <li>
                            <span class="meta-label">2. Parameter Data yang Dikirim</span>
                            <span class="meta-value">
                                Orchestrator mengirimkan paket data kontekstual ke <code>SentimentAgent.analyze(...)</code>:<br>
                                • <code>event_time</code>: Timestamp candle M15 saat CHoCH terjadi.<br>
                                • <code>target_direction</code>: Arah setup yang akan diuji terhadap sentimen pasar.<br>
                                • <code>calendar_events</code>: Jadwal rilis berita ekonomi terdekat dari ForexFactory / Investing.com.<br>
                                • <code>anchor_slot</code>: Slot waktu anchor 3 jam terdekat untuk query database berita.
                            </span>
                        </li>
                        <li>
                            <span class="meta-label">3. Proses Analisis &amp; Model LLM</span>
                            <span class="meta-value">
                                • <strong>AgentRouter Multi-Tier:</strong> Analisis berita dijalankan via GLM-5.2 (Tier 1) dan fallback Groq Qwen 3.6 27B.<br>
                                • <strong>Deteksi Veto High Impact:</strong> Memeriksa apakah event super krusial (FOMC, NFP, CPI) akan rilis dalam waktu &le; 30 menit.<br>
                                • <strong>Penyesuaian Skor:</strong> Memberikan bonus (+boost) jika berita searah atau degradasi jika berita berlawanan.
                            </span>
                        </li>
                        <li>
                            <span class="meta-label">4. Hasil Warm-Up &amp; Caching Instan</span>
                            <div class="meta-value"
                                style="margin-top: 0.5rem; padding: 0.65rem; background: rgba(255, 170, 0, 0.04); border-left: 3px solid #ffaa00; border-radius: 4px; font-size: 0.72rem; line-height: 1.5; font-family: monospace; word-break: normal; color: #fff;">
                                <strong style="color: #ffaa00; font-family: sans-serif;">Hasil Warm-Up Sentiment Agent:</strong><br>
                                • Skor Sentimen Final &amp; Status Veto terhitung.<br>
                                • Disimpan ke cache: <span style="color: #00e676;">self._latest_warmup_results["sentiment"]</span><br>
                                • <strong>Tujuan Utama:</strong> Saat konfirmasi BoS tiba, sistem TIDAK PERLU menunggu LLM membaca berita lagi (eksekusi konsensus berlangsung instan 0-latency).
                            </div>
                        </li>
                    </ul>
                </div>"""

html = re.sub(old_panel_pattern, new_panel_html, html)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Card node-msa-to-sent-info and Side Panel successfully updated to Data Transfer: Kondisi HOLD!")
