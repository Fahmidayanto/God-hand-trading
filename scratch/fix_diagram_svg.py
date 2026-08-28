import os

file_path = r"B:\Project MT5\Other\Dokumen\diagram_arsitektur.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Fix midpoint calculation
old_midpoint = """                const midPoint = { x: (sx + ex) / 2, y: (sy + ey) / 2 };
                return midPoint;"""

new_midpoint = """                // Calculate exact geometric midpoint along the actual SVG curved path
                let midPoint = { x: (sx + ex) / 2, y: (sy + ey) / 2 };
                try {
                    const totalLen = path.getTotalLength();
                    if (totalLen && totalLen > 0) {
                        const pt = path.getPointAtLength(totalLen * 0.5);
                        if (pt && typeof pt.x === 'number' && typeof pt.y === 'number') {
                            midPoint = { x: pt.x, y: pt.y };
                        }
                    }
                } catch (e) {
                    // Fallback to arithmetic midpoint
                }
                return midPoint;"""

if old_midpoint in content:
    content = content.replace(old_midpoint, new_midpoint)
    print("Updated midpoint calculation!")
else:
    print("Warning: old_midpoint pattern not found directly, trying normalized...")
    # Try normalized CRLF / LF
    old_norm = "\n".join([line.strip() for line in old_midpoint.splitlines()])
    lines = content.splitlines()
    found = False
    for i in range(len(lines) - 1):
        if "const midPoint = { x: (sx + ex) / 2" in lines[i] and "return midPoint;" in lines[i+1]:
            lines[i] = new_midpoint
            lines[i+1] = ""
            found = True
            break
    if found:
        content = "\n".join(lines)
        print("Updated midpoint calculation via line scan!")

# 2. Fix delete button click & hit area
old_del_group = """                    // 3. Create delete button group (×)
                    const delBtnGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
                    delBtnGroup.setAttribute('class', 'edge-delete-btn');
                    delBtnGroup.setAttribute('title', 'Hapus aliran data ini');

                    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                    circle.setAttribute('r', '9');

                    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
                    text.textContent = '×';

                    delBtnGroup.appendChild(circle);
                    delBtnGroup.appendChild(text);"""

new_del_group = """                    // 3. Create delete button group (×) with expanded hit area
                    const delBtnGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
                    delBtnGroup.setAttribute('class', 'edge-delete-btn');
                    delBtnGroup.setAttribute('title', 'Hapus aliran data ini');

                    // Invisible expanded hit area (r=18) for effortless click
                    const hitArea = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                    hitArea.setAttribute('r', '18');
                    hitArea.setAttribute('fill', 'transparent');
                    hitArea.setAttribute('cursor', 'pointer');

                    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                    circle.setAttribute('r', '10');

                    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
                    text.textContent = '×';

                    delBtnGroup.appendChild(hitArea);
                    delBtnGroup.appendChild(circle);
                    delBtnGroup.appendChild(text);"""

if old_del_group in content:
    content = content.replace(old_del_group, new_del_group)
    print("Updated delete button hit area!")
else:
    print("Scanning for delBtnGroup...")
    if "delBtnGroup.setAttribute('class', 'edge-delete-btn');" in content:
        # replace r='9' with expanded
        pass

# 3. Fix event listeners on bridgePath and delBtnGroup
old_listeners = """                    // Click event listener to delete (triggered by both the invisible bridge path AND the delete button!)
                    const handleClick = (e) => {
                        e.stopPropagation();
                        const rect = document.getElementById('pan-container').getBoundingClientRect();
                        const x = (e.clientX - rect.left) / zoomScale;
                        const y = (e.clientY - rect.top) / zoomScale;
                        showDeletePopup(x, y, conn.from, conn.to);
                    };

                    bridgePath.addEventListener('click', handleClick);
                    delBtnGroup.addEventListener('click', handleClick);"""

new_listeners = """                    // Click and mousedown event listeners to delete reliably
                    const handleMouseDown = (e) => {
                        e.stopPropagation();
                    };
                    const handleClick = (e) => {
                        e.stopPropagation();
                        e.preventDefault();
                        const rect = document.getElementById('pan-container').getBoundingClientRect();
                        const x = (e.clientX - rect.left) / zoomScale;
                        const y = (e.clientY - rect.top) / zoomScale;
                        showDeletePopup(x, y, conn.from, conn.to);
                    };

                    bridgePath.addEventListener('mousedown', handleMouseDown);
                    bridgePath.addEventListener('click', handleClick);
                    delBtnGroup.addEventListener('mousedown', handleMouseDown);
                    delBtnGroup.addEventListener('click', handleClick);"""

if old_listeners in content:
    content = content.replace(old_listeners, new_listeners)
    print("Updated listeners!")
else:
    # Try normalized
    for part in ["bridgePath.addEventListener('click', handleClick);"]:
        if part in content:
            content = content.replace("bridgePath.addEventListener('click', handleClick);", "bridgePath.addEventListener('mousedown', (e) => e.stopPropagation());\n                    bridgePath.addEventListener('click', handleClick);")
            content = content.replace("delBtnGroup.addEventListener('click', handleClick);", "delBtnGroup.addEventListener('mousedown', (e) => e.stopPropagation());\n                    delBtnGroup.addEventListener('click', handleClick);")
            print("Updated click & mousedown listeners!")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Saved diagram_arsitektur.html successfully!")
