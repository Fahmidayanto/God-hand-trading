html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

target = """                    </div>
                        <div class="card-content"
                            style="font-size: 0.7rem; line-height: 1.35; color: var(--text-secondary);">
                            • <strong>Arah Sinyal:</strong> "BUY"/"SELL" (Sinyal terkonfirmasi)<br>
                            • <strong>Confidence Awal:</strong> Skor keyakinan dari struktur SMC.
                        </div>
                    </div>"""

replacement = "                    </div>"

if target in html:
    html = html.replace(target, replacement, 1)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("Cleaned up successfully!")
else:
    print("Target not found directly.")
