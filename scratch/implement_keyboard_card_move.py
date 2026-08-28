import re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Add CSS for active-keyboard focus ring
active_kb_css = """        .node-card.active-keyboard,
        .agent-card.active-keyboard {
            border-color: #00e5ff !important;
            box-shadow: 0 0 25px rgba(0, 229, 255, 0.4) !important;
        }"""

if ".node-card.active-keyboard" not in html:
    html = html.replace(
        ".agent-card.multiselected, .node-card.multiselected {",
        active_kb_css + "\n\n        .agent-card.multiselected, .node-card.multiselected {"
    )

# 2. Add keyboard movement logic to window keydown listener
old_keydown_listener = """            // Clear connection source selection when pressing Escape key
            window.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    clearConnectionSelection();
                    hideDeletePopup();
                }
            });"""

new_keydown_listener = """            // Keyboard Card Movement & Shortcut Handlers
            window.addEventListener('keydown', (e) => {
                // Ignore if user is typing inside input, textarea, or contenteditable
                if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName) || e.target.isContentEditable) {
                    return;
                }

                if (e.key === 'Escape') {
                    clearConnectionSelection();
                    hideDeletePopup();
                    document.querySelectorAll('.active-keyboard').forEach(c => c.classList.remove('active-keyboard'));
                    return;
                }

                // Arrow keys card movement
                if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
                    // Gather target cards: multiselected > active-keyboard > selected (side panel) > last hovered
                    let targets = Array.from(document.querySelectorAll('.node-card.multiselected, .agent-card.multiselected'));
                    
                    if (!targets.length) {
                        const activeKb = document.querySelector('.node-card.active-keyboard, .agent-card.active-keyboard');
                        if (activeKb) targets = [activeKb];
                    }

                    if (!targets.length) {
                        const selectedSide = document.querySelector('.node-card.selected, .agent-card.selected');
                        if (selectedSide) targets = [selectedSide];
                    }

                    if (!targets.length && hoveredCardId) {
                        const hovered = document.getElementById(hoveredCardId);
                        if (hovered) targets = [hovered];
                    }

                    if (!targets.length) return;

                    e.preventDefault();

                    // Step size: Alt = 1px, Shift = 50px, Default = 10px
                    let step = 10;
                    if (e.shiftKey) step = 50;
                    else if (e.altKey) step = 1;

                    let dX = 0;
                    let dY = 0;
                    if (e.key === 'ArrowLeft') dX = -step;
                    else if (e.key === 'ArrowRight') dX = step;
                    else if (e.key === 'ArrowUp') dY = -step;
                    else if (e.key === 'ArrowDown') dY = step;

                    targets.forEach(card => {
                        const curDx = parseFloat(card.getAttribute('data-dx') || '0');
                        const curDy = parseFloat(card.getAttribute('data-dy') || '0');
                        const nextDx = Math.round(curDx + dX);
                        const nextDy = Math.round(curDy + dY);

                        card.setAttribute('data-dx', nextDx);
                        card.setAttribute('data-dy', nextDy);
                        card.style.transition = 'none';
                        card.style.transform = `translate(${nextDx}px, ${nextDy}px)`;
                    });

                    drawLines();
                    saveLayoutState();
                }
            });"""

if old_keydown_listener in html:
    html = html.replace(old_keydown_listener, new_keydown_listener, 1)
    print("Keydown listener updated!")
else:
    print("Old keydown listener not exact, using regex...")
    html = re.sub(
        r'// Clear connection source selection when pressing Escape key\s*window\.addEventListener\(\'keydown\',[\s\S]*?\}\);',
        new_keydown_listener,
        html
    )

# 3. Add click focus to card dragStart so clicking any card sets it as active-keyboard target
old_drag_start = """                activeDragCard = targetCard;
                dragOffsets.clear();"""

new_drag_start = """                // Set active target for keyboard arrow movement
                if (!e.ctrlKey && !e.metaKey) {
                    document.querySelectorAll('.active-keyboard').forEach(c => c.classList.remove('active-keyboard'));
                    targetCard.classList.add('active-keyboard');
                }

                activeDragCard = targetCard;
                dragOffsets.clear();"""

if old_drag_start in html:
    html = html.replace(old_drag_start, new_drag_start, 1)
    print("dragStart focus updated!")

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Keyboard card movement successfully installed!")
