import re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Add CSS for active mode button in toolbar
active_mode_css = """        .zoom-btn.active-mode {
            background: rgba(0, 229, 255, 0.25) !important;
            border-color: #00e5ff !important;
            box-shadow: 0 0 12px rgba(0, 229, 255, 0.4) !important;
            color: #fff !important;
        }"""

if ".zoom-btn.active-mode" not in html:
    html = html.replace(
        "/* Selection Marquee Box */",
        active_mode_css + "\n\n        /* Selection Marquee Box */"
    )

# 2. Update Zoom Controls Toolbar in HTML with Mode Switcher buttons
old_toolbar = """        <!-- Floating Zoom Controls -->
        <div class="zoom-controls" id="zoom-controls">
            <button class="zoom-btn" id="zoom-in-btn" onclick="zoomIn()" title="Zoom In (Scroll Up)">➕</button>
            <div class="zoom-badge" id="zoom-level-badge" onclick="zoomReset()" title="Skala Zoom Aktif (Klik untuk Reset 100%)">100%</div>
            <button class="zoom-btn" id="zoom-out-btn" onclick="zoomOut()" title="Zoom Out (Scroll Down)">➖</button>
            <button class="zoom-btn" id="zoom-reset-btn" onclick="zoomReset()" title="Reset Zoom (1:1)">1:1</button>
            <button class="zoom-btn" id="zoom-fit-btn" onclick="fitView()" title="Fit to Screen (Pusatkan Diagram)">⛶</button>
        </div>"""

new_toolbar = """        <!-- Floating Controls & Mode Switcher -->
        <div class="zoom-controls" id="zoom-controls">
            <button class="zoom-btn active-mode" id="mode-pan-btn" onclick="setCanvasMode('pan')" title="Mode Geser Kanvas (Tombol H / Tahan Spacebar)">✋</button>
            <button class="zoom-btn" id="mode-select-btn" onclick="setCanvasMode('select')" title="Mode Drag Seleksi Area (Tombol S / Tahan Shift)">⬚</button>
            <div style="width: 1px; height: 18px; background: rgba(255, 255, 255, 0.15); margin: 0 2px;"></div>
            <button class="zoom-btn" id="zoom-in-btn" onclick="zoomIn()" title="Zoom In (Scroll Up)">➕</button>
            <div class="zoom-badge" id="zoom-level-badge" onclick="zoomReset()" title="Skala Zoom Aktif (Klik untuk Reset 100%)">100%</div>
            <button class="zoom-btn" id="zoom-out-btn" onclick="zoomOut()" title="Zoom Out (Scroll Down)">➖</button>
            <button class="zoom-btn" id="zoom-reset-btn" onclick="zoomReset()" title="Reset Zoom (1:1)">1:1</button>
            <button class="zoom-btn" id="zoom-fit-btn" onclick="fitView()" title="Fit to Screen (Pusatkan Diagram)">⛶</button>
        </div>"""

if old_toolbar in html:
    html = html.replace(old_toolbar, new_toolbar, 1)
    print("Toolbar HTML updated with Pan & Select mode buttons!")
else:
    print("Toolbar snippet not exact, trying regex...")
    html = re.sub(
        r'<!-- Floating Zoom Controls -->\s*<div class="zoom-controls" id="zoom-controls">[\s\S]*?</div>',
        new_toolbar,
        html
    )

# 3. Update JavaScript logic for setCanvasMode and viewportPanStart
new_mode_js = """            // Canvas Interaction Modes: 'pan' (Hand Tool) vs 'select' (Marquee Area Tool)
            let currentCanvasMode = 'pan';

            function setCanvasMode(mode) {
                currentCanvasMode = mode;
                const panBtn = document.getElementById('mode-pan-btn');
                const selectBtn = document.getElementById('mode-select-btn');
                const viewport = document.getElementById('diagram-viewport');
                
                if (mode === 'pan') {
                    if (panBtn) panBtn.classList.add('active-mode');
                    if (selectBtn) selectBtn.classList.remove('active-mode');
                    if (viewport) viewport.style.cursor = 'grab';
                    showToast('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: #00e5ff;"><path d="M18 11V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v0"></path><path d="M14 10V4a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v2"></path><path d="M10 10.5V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v8"></path><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"></path></svg> <span>Mode Geser Kanvas (Hand Tool ✋)</span>', false);
                } else {
                    if (selectBtn) selectBtn.classList.add('active-mode');
                    if (panBtn) panBtn.classList.remove('active-mode');
                    if (viewport) viewport.style.cursor = 'crosshair';
                    showToast('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: #00e5ff;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg> <span>Mode Drag Seleksi Area (Marquee ⬚)</span>', false);
                }
            }

            // Viewport Pan & Marquee Selection Handlers
            let isMarquee = false;
            let marqueeStartX = 0;
            let marqueeStartY = 0;
            let marqueeEl = null;

            function viewportPanStart(e) {
                if (
                    e.target.closest('.node-card') ||
                    e.target.closest('.agent-card') ||
                    e.target.closest('a') ||
                    e.target.closest('ul') ||
                    e.target.closest('button') ||
                    e.target.closest('#side-panel') ||
                    e.target.closest('.zoom-controls') ||
                    e.target.closest('.header-dropdown-menu') ||
                    e.target.closest('#hdr-dropdown-wrapper') ||
                    e.target.closest('.flow-path-hover-bridge') ||
                    e.target.closest('.edge-delete-btn')
                ) {
                    return;
                }

                if (sourceNodeId) {
                    clearConnectionSelection();
                }
                closeSidePanel();
                hideDeletePopup();

                const clientX = e.type === 'touchstart' ? e.touches[0].clientX : e.clientX;
                const clientY = e.type === 'touchstart' ? e.touches[0].clientY : e.clientY;

                // Determine whether action is Marquee Selection or Canvas Panning
                const isSelectAction = (currentCanvasMode === 'select' && e.button === 0) || e.shiftKey || e.button === 1;

                if (isSelectAction) {
                    isMarquee = true;
                    isPanning = false;

                    if (!e.shiftKey) {
                        document.querySelectorAll('.node-card.multiselected, .agent-card.multiselected').forEach(c => c.classList.remove('multiselected'));
                    }

                    const viewportRect = document.getElementById('diagram-viewport').getBoundingClientRect();
                    marqueeStartX = clientX - viewportRect.left;
                    marqueeStartY = clientY - viewportRect.top;

                    if (!marqueeEl) {
                        marqueeEl = document.createElement('div');
                        marqueeEl.className = 'selection-marquee';
                        document.getElementById('diagram-viewport').appendChild(marqueeEl);
                    }
                    marqueeEl.style.left = `${marqueeStartX}px`;
                    marqueeEl.style.top = `${marqueeStartY}px`;
                    marqueeEl.style.width = '0px';
                    marqueeEl.style.height = '0px';
                    marqueeEl.style.display = 'block';

                    document.addEventListener('mousemove', viewportMarqueeMove);
                    document.addEventListener('mouseup', viewportMarqueeEnd);
                    document.addEventListener('touchmove', viewportMarqueeMove, { passive: false });
                    document.addEventListener('touchend', viewportMarqueeEnd);
                    return;
                }

                // Default: Canvas Panning (Smooth ✋)
                isPanning = true;
                isMarquee = false;
                document.getElementById('diagram-viewport').style.cursor = 'grabbing';

                panStartX = clientX - panX;
                panStartY = clientY - panY;

                document.addEventListener('mousemove', viewportPanMove);
                document.addEventListener('mouseup', viewportPanEnd);
                document.addEventListener('touchmove', viewportPanMove, { passive: false });
                document.addEventListener('touchend', viewportPanEnd);

                if (e.type === 'touchstart') {
                    e.preventDefault();
                }
            }"""

# Replace old viewport handlers
html = re.sub(
    r'// Viewport Pan & Marquee Selection Handlers[\s\S]*?if \(e\.type === \'touchstart\'\) \{\s*e\.preventDefault\(\);\s*\}\s*\}',
    new_mode_js,
    html
)

# 4. Add shortcut keys H and S to keydown handler
old_shortcuts = """                if (e.key === 'Escape') {
                    clearConnectionSelection();
                    hideDeletePopup();
                    document.querySelectorAll('.active-keyboard, .multiselected').forEach(c => {
                        c.classList.remove('active-keyboard');
                        c.classList.remove('multiselected');
                    });
                    return;
                }"""

new_shortcuts = """                if (e.key === 'Escape') {
                    clearConnectionSelection();
                    hideDeletePopup();
                    document.querySelectorAll('.active-keyboard, .multiselected').forEach(c => {
                        c.classList.remove('active-keyboard');
                        c.classList.remove('multiselected');
                    });
                    return;
                }

                // Tool Switch Shortcuts: H (Hand/Pan) vs S (Select/Marquee)
                if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                    if (e.key.toLowerCase() === 'h' || e.key.toLowerCase() === 'v') {
                        setCanvasMode('pan');
                        return;
                    }
                    if (e.key.toLowerCase() === 's' || e.key.toLowerCase() === 'm') {
                        setCanvasMode('select');
                        return;
                    }
                }"""

if old_shortcuts in html:
    html = html.replace(old_shortcuts, new_shortcuts, 1)
    print("Keyboard shortcuts H and S updated!")

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Canvas mode switcher successfully installed!")
