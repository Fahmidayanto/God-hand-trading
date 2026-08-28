import re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Define the exact clean and simple card markup
simple_card_html = """<!-- Data Transfer: Kondisi HOLD -> Sentiment Agent Info Box -->
                    <div class="agent-card" id="node-msa-to-sent-info" onclick="selectNode('msa-to-sent-info')" data-dx="2313" data-dy="-762" data-h="210" style="transform: translate(2313px, -762px); height: 210px;">
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
                    </div>"""

# Match the entire block between the comment and the Sentiment Agent Column
pattern = r'<!-- Data Transfer: Kondisi HOLD -> Sentiment Agent Info Box -->[\s\S]*?(?=\s*<!-- Sentiment Agent Column -->)'

html = re.sub(pattern, simple_card_html + "\n\n", html)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Simple card content successfully applied!")
