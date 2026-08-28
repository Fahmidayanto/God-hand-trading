import subprocess, re

out = subprocess.check_output(['git', 'show', 'HEAD:Other/Dokumen/diagram_arsitektur.html'], encoding='utf-8')
panels = re.findall(r'id="(panel-[^"]+)"', out)
print('Total panels in git:', len(panels))
print('Panels in git:', panels)

# Let's also find all panels in the current file
with open(r'b:\Project MT5\Other\Dokumen\diagram_arsitektur.html', 'r', encoding='utf-8') as f:
    curr = f.read()

curr_panels = re.findall(r'id="(panel-[^"]+)"', curr)
print('Total panels in current:', len(curr_panels))
print('Panels in current:', curr_panels)
