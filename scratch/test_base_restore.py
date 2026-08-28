import json
import re

# Read original base HTML from git commit a330fae
import subprocess
git_html = subprocess.check_output(['git', 'show', 'a330fae:Other/Dokumen/diagram_arsitektur.html'], encoding='utf-8')

# Read layout_data v15
layout_path = r"b:\Project MT5\Other\Dokumen\diagram_layout.json"
layout_data = json.loads(open(layout_path, encoding='utf-8').read())
layout_data["version"] = 15

# Let's inspect where cards are placed in git_html
# In git_html, we can reconstruct the full clean canvas
# Let's check the cards in git_html and add the missing ones:
# 1. node-fe-to-orch-info
# 2. node-orch-to-msa-info
# 3. node-msa-to-orch-info
# 4. node-orch-cond1, node-orch-cond2, node-orch-cond3
# 5. node-msa-to-ml-info, node-msa-to-sent-info, node-bos-to-ml-info, node-bos-to-sent-info
# 6. node-llm-msa, node-llm-ml, node-llm-sentiment, node-cross-review, node-llm-decision, node-council-gate

print("Base git_html length:", len(git_html))
