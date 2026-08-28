import re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update CSS for .card-edge-resizer to have generous hit areas and clear visual hover indicators
new_css = """        /* Multi-Edge & Corner Card Resizers */
        .card-edge-resizer {
            position: absolute;
            z-index: 40;
            pointer-events: auto;
            background: transparent;
            transition: background 0.15s ease, opacity 0.15s ease, box-shadow 0.15s ease;
        }

        /* Edges with generous grab area (16px hit target) */
        .card-edge-resizer.edge-e {
            right: -8px;
            top: 10px;
            bottom: 10px;
            width: 16px;
            cursor: ew-resize;
        }

        .card-edge-resizer.edge-w {
            left: -8px;
            top: 10px;
            bottom: 10px;
            width: 16px;
            cursor: ew-resize;
        }

        .card-edge-resizer.edge-s {
            bottom: -8px;
            left: 10px;
            right: 10px;
            height: 16px;
            cursor: ns-resize;
        }

        .card-edge-resizer.edge-n {
            top: -8px;
            left: 10px;
            right: 10px;
            height: 16px;
            cursor: ns-resize;
        }

        /* Corners with 22px hit target */
        .card-edge-resizer.edge-se {
            right: -8px;
            bottom: -8px;
            width: 22px;
            height: 22px;
            cursor: nwse-resize;
            z-index: 45;
        }

        .card-edge-resizer.edge-sw {
            left: -8px;
            bottom: -8px;
            width: 22px;
            height: 22px;
            cursor: nesw-resize;
            z-index: 45;
        }

        .card-edge-resizer.edge-ne {
            right: -8px;
            top: -8px;
            width: 22px;
            height: 22px;
            cursor: nesw-resize;
            z-index: 45;
        }

        .card-edge-resizer.edge-nw {
            left: -8px;
            top: -8px;
            width: 22px;
            height: 22px;
            cursor: nwse-resize;
            z-index: 45;
        }

        /* Visual corner markers */
        .card-edge-resizer.edge-se::after {
            content: '';
            position: absolute;
            right: 5px;
            bottom: 5px;
            width: 8px;
            height: 8px;
            border-right: 2.5px solid rgba(255, 255, 255, 0.35);
            border-bottom: 2.5px solid rgba(255, 255, 255, 0.35);
            border-bottom-right-radius: 2px;
            transition: border-color 0.2s, transform 0.2s;
        }

        .node-card:hover .card-edge-resizer.edge-se::after,
        .agent-card:hover .card-edge-resizer.edge-se::after,
        .card-edge-resizer.resizing::after {
            border-color: var(--theme-color, #00e5ff);
            transform: scale(1.2);
        }

        .card-edge-resizer:hover {
            background: rgba(0, 229, 255, 0.2);
            border-radius: 6px;
        }

        .card-edge-resizer.edge-s:hover,
        .card-edge-resizer.edge-n:hover {
            box-shadow: 0 0 10px rgba(0, 229, 255, 0.35);
        }

        .card-edge-resizer.edge-e:hover,
        .card-edge-resizer.edge-w:hover {
            box-shadow: 0 0 10px rgba(0, 229, 255, 0.35);
        }

        .card-edge-resizer.resizing {
            background: rgba(0, 229, 255, 0.3) !important;
            box-shadow: 0 0 14px rgba(0, 229, 255, 0.5) !important;
        }"""

html = re.sub(
    r'/\*\s*Multi-Edge & Corner Card Resizers\s*\*\/[\s\S]*?\.card-edge-resizer\.resizing\s*\{[^}]*\}',
    new_css,
    html
)

# 2. Update handleCardEdgeResizeStart in JavaScript
new_js = """            // Universal Multi-Directional Card Resizer Handler
            let activeResizeCard = null;
            let activeResizeDir = null;
            let resizeStartX = 0;
            let resizeStartY = 0;
            let startCardWidth = 0;
            let startCardHeight = 0;
            let startCardDx = 0;
            let startCardDy = 0;
            let startMinContentH = 0;

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

                // Measure true minimum content height by temporarily testing auto height
                const curInlineH = card.style.height;
                card.style.height = 'auto';
                const naturalAutoH = card.offsetHeight;
                card.style.height = curInlineH || `${startCardHeight}px`;
                const minH = card.classList.contains('agent-card') ? 70 : 90;
                startMinContentH = Math.max(minH, naturalAutoH);

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
                        curH = Math.max(startMinContentH, Math.round(startCardHeight + deltaY));
                    } else if (activeResizeDir.includes('n')) {
                        const targetH = Math.max(startMinContentH, Math.round(startCardHeight - deltaY));
                        const actualDeltaY = startCardHeight - targetH;
                        curDy = startCardDy + actualDeltaY;
                        curH = targetH;
                    } else {
                        // For pure horizontal resizing, ensure height still accommodates wrapped text
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

html = re.sub(
    r'// Universal Multi-Directional Card Resizer Handler[\s\S]*?window\.addEventListener\(\'touchend\', onResizeEnd\);\s*\}',
    new_js,
    html
)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Updated edge resizers and vertical calculations successfully!")
