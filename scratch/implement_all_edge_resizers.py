import re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update CSS for edge resizers and corners
edge_resizers_css = """        /* Multi-Edge & Corner Card Resizers */
        .card-edge-resizer {
            position: absolute;
            z-index: 40;
            pointer-events: auto;
            background: transparent;
            transition: background 0.15s ease, opacity 0.15s ease;
        }

        /* Edges */
        .card-edge-resizer.edge-e {
            right: -5px;
            top: 14px;
            bottom: 14px;
            width: 10px;
            cursor: ew-resize;
        }

        .card-edge-resizer.edge-w {
            left: -5px;
            top: 14px;
            bottom: 14px;
            width: 10px;
            cursor: ew-resize;
        }

        .card-edge-resizer.edge-s {
            bottom: -5px;
            left: 14px;
            right: 14px;
            height: 10px;
            cursor: ns-resize;
        }

        .card-edge-resizer.edge-n {
            top: -5px;
            left: 14px;
            right: 14px;
            height: 10px;
            cursor: ns-resize;
        }

        /* Corners */
        .card-edge-resizer.edge-se {
            right: -5px;
            bottom: -5px;
            width: 18px;
            height: 18px;
            cursor: nwse-resize;
            z-index: 45;
        }

        .card-edge-resizer.edge-sw {
            left: -5px;
            bottom: -5px;
            width: 18px;
            height: 18px;
            cursor: nesw-resize;
            z-index: 45;
        }

        .card-edge-resizer.edge-ne {
            right: -5px;
            top: -5px;
            width: 18px;
            height: 18px;
            cursor: nesw-resize;
            z-index: 45;
        }

        .card-edge-resizer.edge-nw {
            left: -5px;
            top: -5px;
            width: 18px;
            height: 18px;
            cursor: nwse-resize;
            z-index: 45;
        }

        /* Visual corner markers */
        .card-edge-resizer.edge-se::after {
            content: '';
            position: absolute;
            right: 4px;
            bottom: 4px;
            width: 8px;
            height: 8px;
            border-right: 2px solid rgba(255, 255, 255, 0.25);
            border-bottom: 2px solid rgba(255, 255, 255, 0.25);
            border-bottom-right-radius: 2px;
            transition: border-color 0.2s, transform 0.2s;
        }

        .node-card:hover .card-edge-resizer.edge-se::after,
        .agent-card:hover .card-edge-resizer.edge-se::after,
        .card-edge-resizer.resizing::after {
            border-color: var(--theme-color, #00e5ff);
            transform: scale(1.15);
        }

        .card-edge-resizer:hover {
            background: rgba(0, 229, 255, 0.08);
            border-radius: 4px;
        }

        .card-edge-resizer.resizing {
            background: rgba(0, 229, 255, 0.15) !important;
        }"""

# Replace old .card-resizer CSS
html = re.sub(
    r'/\*\s*Card Resizer Handle on bottom-right corner\s*\*\/[\s\S]*?\.card-resizer:hover::after,\s*\.card-resizer\.resizing::after\s*\{[^}]*\}',
    edge_resizers_css,
    html
)

# 2. Update initialization and resize logic in JavaScript
new_js_block = """                    // Remove existing handles & resizers if any
                    card.querySelectorAll('.port-handle, .card-resizer, .card-edge-resizer').forEach(h => h.remove());

                    // Add 4 directional connection handles (top, bottom, left, right)
                    ['top', 'bottom', 'left', 'right'].forEach(port => {
                        const handle = document.createElement('div');
                        handle.className = `port-handle ${port}`;
                        handle.innerHTML = '+';
                        handle.title = `Tarik aliran baru dari gagang ${port} ini...`;
                        handle.addEventListener('click', (e) => handlePortClick(e, card.id, port));
                        card.appendChild(handle);
                    });

                    // Add 8 multi-directional edge & corner resizers (n, s, e, w, ne, nw, se, sw)
                    const resizeDirs = [
                        { dir: 'e', title: 'Tarik tepi kanan untuk mengubah lebar...' },
                        { dir: 'w', title: 'Tarik tepi kiri untuk mengubah lebar...' },
                        { dir: 's', title: 'Tarik tepi bawah untuk mengubah tinggi...' },
                        { dir: 'n', title: 'Tarik tepi atas untuk mengubah tinggi...' },
                        { dir: 'se', title: 'Tarik sudut kanan-bawah untuk mengubah ukuran...' },
                        { dir: 'sw', title: 'Tarik sudut kiri-bawah untuk mengubah ukuran...' },
                        { dir: 'ne', title: 'Tarik sudut kanan-atas untuk mengubah ukuran...' },
                        { dir: 'nw', title: 'Tarik sudut kiri-atas untuk mengubah ukuran...' }
                    ];

                    resizeDirs.forEach(({ dir, title }) => {
                        const edgeResizer = document.createElement('div');
                        edgeResizer.className = `card-edge-resizer edge-${dir}`;
                        edgeResizer.title = title;
                        edgeResizer.addEventListener('mousedown', (e) => handleCardEdgeResizeStart(e, card, dir));
                        edgeResizer.addEventListener('touchstart', (e) => handleCardEdgeResizeStart(e, card, dir), { passive: false });
                        card.appendChild(edgeResizer);
                    });

                    card.addEventListener('mousedown', dragStart);
                    card.addEventListener('touchstart', dragStart, { passive: false });

                    // Real-time hover flow lighting on card
                    card.addEventListener('mouseenter', () => {
                        if (!activeDragCard && !isPanning && !activeResizeCard) {
                            hoveredCardId = card.id;
                            updateFlowHighlights();
                        }
                    });
                    card.addEventListener('mouseleave', () => {
                        if (!activeDragCard && !isPanning && !activeResizeCard) {
                            hoveredCardId = null;
                            updateFlowHighlights();
                        }
                    });
                });

                // 2. Initialize viewport panning and wheel zoom
                const viewport = document.getElementById('diagram-viewport');
                viewport.addEventListener('mousedown', viewportPanStart);
                viewport.addEventListener('touchstart', viewportPanStart, { passive: false });
                viewport.addEventListener('wheel', handleWheelZoom, { passive: false });
            }

            // Universal Multi-Directional Card Resizer Handler
            let activeResizeCard = null;
            let activeResizeDir = null;
            let resizeStartX = 0;
            let resizeStartY = 0;
            let startCardWidth = 0;
            let startCardHeight = 0;
            let startCardDx = 0;
            let startCardDy = 0;

            function handleCardEdgeResizeStart(e, card, dir) {
                e.stopPropagation();
                e.preventDefault();
                hideDeletePopup();

                activeResizeCard = card;
                activeResizeDir = dir;
                const clientX = e.type === 'touchstart' ? e.touches[0].clientX : e.clientX;
                const clientY = e.type === 'touchstart' ? e.touches[0].clientY : e.clientY;

                resizeStartX = clientX;
                resizeStartY = clientY;
                startCardWidth = card.offsetWidth;
                startCardHeight = card.offsetHeight;
                startCardDx = parseFloat(card.getAttribute('data-dx') || '0');
                startCardDy = parseFloat(card.getAttribute('data-dy') || '0');

                const resizerEl = card.querySelector(`.card-edge-resizer.edge-${dir}`);
                if (resizerEl) resizerEl.classList.add('resizing');

                card.style.transition = 'none';

                const onResizeMove = (moveEvent) => {
                    if (!activeResizeCard) return;
                    const curX = moveEvent.type === 'touchmove' ? moveEvent.touches[0].clientX : moveEvent.clientX;
                    const curY = moveEvent.type === 'touchmove' ? moveEvent.touches[0].clientY : moveEvent.clientY;

                    const deltaX = (curX - resizeStartX) / zoomScale;
                    const deltaY = (curY - resizeStartY) / zoomScale;

                    const minW = activeResizeCard.classList.contains('agent-card') ? 180 : 220;
                    const minH = activeResizeCard.classList.contains('agent-card') ? 70 : 90;

                    let curW = startCardWidth;
                    let curH = startCardHeight;
                    let curDx = startCardDx;
                    let curDy = startCardDy;

                    // Horizontal calculations
                    if (activeResizeDir.includes('e')) {
                        curW = Math.max(minW, Math.round(startCardWidth + deltaX));
                    } else if (activeResizeDir.includes('w')) {
                        const targetW = Math.max(minW, Math.round(startCardWidth - deltaX));
                        const actualDeltaX = startCardWidth - targetW;
                        curDx = startCardDx + actualDeltaX;
                        curW = targetW;
                    }

                    // Vertical calculations
                    if (activeResizeDir.includes('s')) {
                        const targetH = Math.max(minH, Math.round(startCardHeight + deltaY));
                        curH = Math.max(targetH, activeResizeCard.scrollHeight);
                    } else if (activeResizeDir.includes('n')) {
                        const naturalH = activeResizeCard.scrollHeight;
                        const targetH = Math.max(minH, naturalH, Math.round(startCardHeight - deltaY));
                        const actualDeltaY = startCardHeight - targetH;
                        curDy = startCardDy + actualDeltaY;
                        curH = targetH;
                    } else {
                        // For pure horizontal resizing, ensure height still accommodates text
                        curH = Math.max(startCardHeight, activeResizeCard.scrollHeight);
                    }

                    activeResizeCard.style.width = `${curW}px`;
                    activeResizeCard.style.height = `${curH}px`;
                    activeResizeCard.style.transform = `translate(${curDx}px, ${curDy}px)`;
                    activeResizeCard.setAttribute('data-w', curW);
                    activeResizeCard.setAttribute('data-h', curH);
                    activeResizeCard.setAttribute('data-dx', curDx);
                    activeResizeCard.setAttribute('data-dy', curDy);

                    drawLines();

                    if (moveEvent.type === 'touchmove') moveEvent.preventDefault();
                };

                const onResizeEnd = () => {
                    if (activeResizeCard) {
                        const resizerEl = activeResizeCard.querySelector(`.card-edge-resizer.edge-${activeResizeDir}`);
                        if (resizerEl) resizerEl.classList.remove('resizing');
                        activeResizeCard.style.transition = 'transform 0.1s ease, box-shadow 0.4s, border-color 0.4s';
                    }
                    activeResizeCard = null;
                    activeResizeDir = null;

                    window.removeEventListener('mousemove', onResizeMove);
                    window.removeEventListener('mouseup', onResizeEnd);
                    window.removeEventListener('touchmove', onResizeMove);
                    window.removeEventListener('touchend', onResizeEnd);

                    saveLayoutState();
                };

                window.addEventListener('mousemove', onResizeMove);
                window.addEventListener('mouseup', onResizeEnd);
                window.addEventListener('touchmove', onResizeMove, { passive: false });
                window.addEventListener('touchend', onResizeEnd);
            }"""

# Replace the old JS block from '// Remove existing handles & resizers' to end of 'handleCardResizeStart'
html = re.sub(
    r'// Remove existing handles & resizers if any[\s\S]*?window\.addEventListener\(\'touchend\', onResizeEnd\);\s*\}',
    new_js_block,
    html
)

# 3. Update dragStart filter and generateBakedHtml cleanups
html = re.sub(
    r"if \(e\.target\.closest\('a'\) \|\| e\.target\.closest\('ul'\) \|\| e\.target\.closest\('\.port-handle'\) \|\| e\.target\.closest\('\.card-resizer'\)\) return;",
    "if (e.target.closest('a') || e.target.closest('ul') || e.target.closest('.port-handle') || e.target.closest('.card-edge-resizer') || e.target.closest('.card-resizer')) return;",
    html
)

html = re.sub(
    r"html = html\.replace\(/\<div class=\"card-resizer\[\^\"\]\*\"\[\^>\]\*\>\<\/div\>/gi, ''\);",
    "html = html.replace(/<div class=\"card-edge-resizer [^\"]*\"[^>]*><\\/div>/gi, '');\n                html = html.replace(/<div class=\"card-resizer[^\"]*\"[^>]*><\\/div>/gi, '');",
    html
)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Edge resizers applied successfully!")
