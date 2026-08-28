import re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Add CSS for Selection Marquee & Snapped Straight Lines
marquee_css = """        /* Selection Marquee Box */
        .selection-marquee {
            position: absolute;
            border: 1.5px dashed #00e5ff;
            background: rgba(0, 229, 255, 0.12);
            box-shadow: 0 0 15px rgba(0, 229, 255, 0.2);
            border-radius: 4px;
            pointer-events: none;
            z-index: 999;
        }

        .flow-path.straight-snapped {
            stroke: #00e676 !important;
            stroke-width: 4px !important;
            filter: drop-shadow(0 0 10px #00e676) drop-shadow(0 0 3px #ffffff) !important;
        }"""

if ".selection-marquee" not in html:
    html = html.replace(
        ".node-card.active-keyboard,",
        marquee_css + "\n\n        .node-card.active-keyboard,"
    )

# 2. Add Marquee Drag Selection to viewport handlers
new_viewport_handlers = """            // Viewport Pan & Marquee Selection Handlers
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

                // Shift + Click/Drag or Middle Click triggers Marquee Area Selection!
                if (e.shiftKey || e.button === 1 || e.target.classList.contains('diagram-area')) {
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

                // Default: Canvas Panning
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
            }

            function viewportMarqueeMove(e) {
                if (!isMarquee || !marqueeEl) return;

                const clientX = e.type === 'touchmove' ? e.touches[0].clientX : e.clientX;
                const clientY = e.type === 'touchmove' ? e.touches[0].clientY : e.clientY;

                const viewportRect = document.getElementById('diagram-viewport').getBoundingClientRect();
                const curX = clientX - viewportRect.left;
                const curY = clientY - viewportRect.top;

                const left = Math.min(marqueeStartX, curX);
                const top = Math.min(marqueeStartY, curY);
                const width = Math.abs(curX - marqueeStartX);
                const height = Math.abs(curY - marqueeStartY);

                marqueeEl.style.left = `${left}px`;
                marqueeEl.style.top = `${top}px`;
                marqueeEl.style.width = `${width}px`;
                marqueeEl.style.height = `${height}px`;

                // Calculate overlap with all cards in viewport coordinates
                const marqueeRect = marqueeEl.getBoundingClientRect();
                document.querySelectorAll('.node-card, .agent-card').forEach(card => {
                    const cardRect = card.getBoundingClientRect();
                    const intersects = !(
                        cardRect.right < marqueeRect.left ||
                        cardRect.left > marqueeRect.right ||
                        cardRect.bottom < marqueeRect.top ||
                        cardRect.top > marqueeRect.bottom
                    );

                    if (intersects) {
                        card.classList.add('multiselected');
                    } else if (!e.shiftKey) {
                        card.classList.remove('multiselected');
                    }
                });

                if (e.type === 'touchmove') e.preventDefault();
            }

            function viewportMarqueeEnd() {
                if (!isMarquee) return;
                isMarquee = false;

                if (marqueeEl) {
                    marqueeEl.style.display = 'none';
                }

                document.removeEventListener('mousemove', viewportMarqueeMove);
                document.removeEventListener('mouseup', viewportMarqueeEnd);
                document.removeEventListener('touchmove', viewportMarqueeMove);
                document.removeEventListener('touchend', viewportMarqueeEnd);

                const selectedCount = document.querySelectorAll('.node-card.multiselected, .agent-card.multiselected').length;
                if (selectedCount > 0) {
                    showToast(`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: #00e5ff;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg> <span>${selectedCount} kartu terpilih (geser/gunakan panah).</span>`);
                }
            }

            function viewportPanMove(e) {
                if (!isPanning) return;

                const clientX = e.type === 'touchmove' ? e.touches[0].clientX : e.clientX;
                const clientY = e.type === 'touchmove' ? e.touches[0].clientY : e.clientY;

                panX = clientX - panStartX;
                panY = clientY - panStartY;

                updateTransform();

                if (e.type === 'touchmove') {
                    e.preventDefault();
                }
            }

            function viewportPanEnd() {
                if (!isPanning) return;
                isPanning = false;

                document.getElementById('diagram-viewport').style.cursor = 'grab';

                document.removeEventListener('mousemove', viewportPanMove);
                document.removeEventListener('mouseup', viewportPanEnd);
                document.removeEventListener('touchmove', viewportPanMove);
                document.removeEventListener('touchend', viewportPanEnd);

                saveLayoutState();
            }"""

# Replace old viewport handlers
html = re.sub(
    r'function viewportPanStart\(e\) \{[\s\S]*?function viewportPanEnd\(\) \{[\s\S]*?saveLayoutState\(\);\s*\}',
    new_viewport_handlers,
    html
)

# 3. Add Smart Alignment & Straight Snapping to Keyboard Handlers
new_keyboard_logic = """            // Keyboard Card Movement with Smart Auto-Straight Snapping
            window.addEventListener('keydown', (e) => {
                if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName) || e.target.isContentEditable) {
                    return;
                }

                if (e.key === 'Escape') {
                    clearConnectionSelection();
                    hideDeletePopup();
                    document.querySelectorAll('.active-keyboard, .multiselected').forEach(c => {
                        c.classList.remove('active-keyboard');
                        c.classList.remove('multiselected');
                    });
                    return;
                }

                // Select All Cards Shortcut (Ctrl + A)
                if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
                    e.preventDefault();
                    document.querySelectorAll('.node-card, .agent-card').forEach(c => c.classList.add('multiselected'));
                    showToast('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: #00e5ff;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg> <span>Semua kartu terpilih.</span>');
                    return;
                }

                // Arrow keys card movement
                if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
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

                    const snapThreshold = 18; // px snapping magnet zone
                    let didSnapStraight = false;

                    targets.forEach(card => {
                        const curDx = parseFloat(card.getAttribute('data-dx') || '0');
                        const curDy = parseFloat(card.getAttribute('data-dy') || '0');
                        let nextDx = curDx + dX;
                        let nextDy = curDy + dY;

                        // Smart Straight Line Snapping (when moving 1 card)
                        if (targets.length === 1 && !e.altKey) {
                            const relatedConns = connections.filter(c => c.from === card.id || c.to === card.id);
                            
                            for (let conn of relatedConns) {
                                const isFrom = conn.from === card.id;
                                const partnerId = isFrom ? conn.to : conn.from;
                                const partnerCard = document.getElementById(partnerId);
                                if (!partnerCard) continue;

                                const myPort = isFrom ? conn.fromPort : conn.toPort;
                                const partnerPort = isFrom ? conn.toPort : conn.fromPort;

                                const partnerDx = parseFloat(partnerCard.getAttribute('data-dx') || '0');
                                const partnerDy = parseFloat(partnerCard.getAttribute('data-dy') || '0');
                                const partnerW = partnerCard.offsetWidth;
                                const partnerH = partnerCard.offsetHeight;
                                const myW = card.offsetWidth;
                                const myH = card.offsetHeight;

                                // 1. Horizontal Straight Line Snapping (e.g. left-to-right ports aligned on same Y)
                                if ((myPort === 'left' || myPort === 'right') && (partnerPort === 'left' || partnerPort === 'right')) {
                                    if (dY !== 0) {
                                        // Target exact DY where vertical centers match
                                        const targetStraightDy = partnerDy + (partnerH / 2) - (myH / 2);
                                        if (Math.abs(nextDy - targetStraightDy) <= snapThreshold) {
                                            nextDy = targetStraightDy;
                                            didSnapStraight = true;
                                            break;
                                        }
                                    }
                                }

                                // 2. Vertical Straight Line Snapping (e.g. top-to-bottom ports aligned on same X)
                                if ((myPort === 'top' || myPort === 'bottom') && (partnerPort === 'top' || partnerPort === 'bottom')) {
                                    if (dX !== 0) {
                                        // Target exact DX where horizontal centers match
                                        const targetStraightDx = partnerDx + (partnerW / 2) - (myW / 2);
                                        if (Math.abs(nextDx - targetStraightDx) <= snapThreshold) {
                                            nextDx = targetStraightDx;
                                            didSnapStraight = true;
                                            break;
                                        }
                                    }
                                }
                            }
                        }

                        nextDx = Math.round(nextDx);
                        nextDy = Math.round(nextDy);

                        card.setAttribute('data-dx', nextDx);
                        card.setAttribute('data-dy', nextDy);
                        card.style.transition = 'none';
                        card.style.transform = `translate(${nextDx}px, ${nextDy}px)`;
                    });

                    drawLines();
                    saveLayoutState();

                    if (didSnapStraight) {
                        showToast('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: #00e676;"><polyline points="20 6 9 17 4 12"></polyline></svg> <span>Garis otomatis lurus sejajar!</span>', false);
                    }
                }
            });"""

# Replace old keydown listener
html = re.sub(
    r'// Keyboard Card Movement & Shortcut Handlers\s*window\.addEventListener\(\'keydown\',[\s\S]*?saveLayoutState\(\);\s*\}\s*\}\);',
    new_keyboard_logic,
    html
)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Marquee selection and Smart Auto-Align Snapping successfully installed!")
