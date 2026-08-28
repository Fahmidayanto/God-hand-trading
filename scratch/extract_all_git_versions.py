import subprocess
import os

commits = [
    ("a330fae", "2026-08-23_enhance_drawer_and_lighting"),
    ("4989a3d", "2026-08-17_4tier_llm_fallback"),
    ("732b62e", "2026-07-22_perbarui_diagram"),
    ("17de503", "2026-07-08_perubahan_strategi"),
    ("a469cbe", "2026-07-05_initial_warmup_logic")
]

for commit, name in commits:
    try:
        content = subprocess.check_output(['git', 'show', f'{commit}:Other/Dokumen/diagram_arsitektur.html'], encoding='utf-8')
        out_path = f"b:\\Project MT5\\scratch\\diagram_git_{commit}_{name}.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Extracted {commit} ({name}) -> {len(content)} chars, {len(content.splitlines())} lines")
    except Exception as e:
        print(f"Error {commit}: {e}")
