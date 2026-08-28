import re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Define the Universal Smart Snapping Engine
smart_snap_engine = """            // ==========================================
            // UNIVERSAL SMART AUTO-ALIGN & STRAIGHT LINE SNAPPING
            // ==========================================
            function calculateSmartSnap(card, candDx, candDy, isXMove = true, isYMove = true, snapThreshold = 18) {
                if (!card) return { dx: candDx, dy: candDy, snapped: false };

                const cardW = card.offsetWidth;
                const cardH = card.offsetHeight;
                
                const cardParentLeft = card.offsetLeft;
                const cardParentTop = card.offsetTop;

                const relatedConns = connections.filter(c => c.from === card.id || c.to === card.id);
                
                let snappedDx = candDx;
                let snappedDy = candDy;
                let didSnap = false;

                // Priority 1: Connected Port Lines (Horizontal & Vertical Straight Alignment)
                for (const conn of relatedConns) {
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

                    const partnerAbsLeft = partnerCard.offsetLeft + partnerDx;
                    const partnerAbsTop = partnerCard.offsetTop + partnerDy;

                    // 1. Horizontal Straight Line (left <-> right or right <-> left)
                    // Ports align perfectly horizontal when vertical centers (or port Ys) match!
                    if ((!myPort || myPort === 'left' || myPort === 'right') && (!partnerPort || partnerPort === 'left' || partnerPort === 'right')) {
                        if (isYMove) {
                            const partnerPortY = partnerAbsTop + (partnerH / 2);
                            const targetDy = partnerPortY - (cardParentTop + (cardH / 2));
                            
                            if (Math.abs(candDy - targetDy) <= snapThreshold) {
                                snappedDy = targetDy;
                                didSnap = true;
                            }
                        }
                    }

                    // 2. Vertical Straight Line (top <-> bottom or bottom <-> top)
                    // Ports align perfectly vertical when horizontal centers (or port Xs) match!
                    if ((!myPort || myPort === 'top' || myPort === 'bottom') && (!partnerPort || partnerPort === 'top' || partnerPort === 'bottom')) {
                        if (isXMove) {
                            const partnerPortX = partnerAbsLeft + (partnerW / 2);
                            const targetDx = partnerPortX - (cardParentLeft + (cardW / 2));

                            if (Math.abs(candDx - targetDx) <= snapThreshold) {
                                snappedDx = targetDx;
                                didSnap = true;
                            }
                        }
                    }
                }

                // Priority 2: Card Edges & Centers Alignment with all other visible cards
                if (!didSnap) {
                    const allCards = document.querySelectorAll('.node-card, .agent-card');
                    for (const otherCard of allCards) {
                        if (otherCard === card || otherCard.classList.contains('multiselected')) continue;

                        const otherDx = parseFloat(otherCard.getAttribute('data-dx') || '0');
                        const otherDy = parseFloat(otherCard.getAttribute('data-dy') || '0');
                        const otherW = otherCard.offsetWidth;
                        const otherH = otherCard.offsetHeight;

                        const otherAbsLeft = otherCard.offsetLeft + otherDx;
                        const otherAbsTop = otherCard.offsetTop + otherDy;

                        // Center Y Align
                        if (isYMove) {
                            const targetCenterDy = (otherAbsTop + otherH / 2) - (cardParentTop + cardH / 2);
                            if (Math.abs(candDy - targetCenterDy) <= snapThreshold) {
                                snappedDy = targetCenterDy;
                                didSnap = true;
                            } else {
                                // Top Edge Align
                                const targetTopDy = otherAbsTop - cardParentTop;
                                if (Math.abs(candDy - targetTopDy) <= snapThreshold) {
                                    snappedDy = targetTopDy;
                                    didSnap = true;
                                }
                            }
                        }

                        // Center X Align
                        if (isXMove) {
                            const targetCenterDx = (otherAbsLeft + otherW / 2) - (cardParentLeft + cardW / 2);
                            if (Math.abs(candDx - targetCenterDx) <= snapThreshold) {
                                snappedDx = targetCenterDx;
                                didSnap = true;
                            } else {
                                // Left Edge Align
                                const targetLeftDx = otherAbsLeft - cardParentLeft;
                                if (Math.abs(candDx - targetLeftDx) <= snapThreshold) {
                                    snappedDx = targetLeftDx;
                                    didSnap = true;
                                }
                            }
                        }

                        if (didSnap) break;
                    }
                }

                return {
                    dx: Math.round(snappedDx),
                    dy: Math.round(snappedDy),
                    snapped: didSnap
                };
            }"""

# 2. Update keydown handler to use calculateSmartSnap cleanly
new_keydown_handler = """            // Keyboard Card Movement with Smart Auto-Straight Snapping
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

                    const isXMove = dX !== 0;
                    const isYMove = dY !== 0;
                    let anySnapped = false;

                    targets.forEach(card => {
                        const curDx = parseFloat(card.getAttribute('data-dx') || '0');
                        const curDy = parseFloat(card.getAttribute('data-dy') || '0');
                        let candDx = curDx + dX;
                        let candDy = curDy + dY;

                        // Apply Universal Smart Snap (when moving 1 card without Alt)
                        if (targets.length === 1 && !e.altKey) {
                            const snapRes = calculateSmartSnap(card, candDx, candDy, isXMove, isYMove, 20);
                            candDx = snapRes.dx;
                            candDy = snapRes.dy;
                            if (snapRes.snapped) anySnapped = true;
                        }

                        candDx = Math.round(candDx);
                        candDy = Math.round(candDy);

                        card.setAttribute('data-dx', candDx);
                        card.setAttribute('data-dy', candDy);
                        card.style.transition = 'none';
                        card.style.transform = `translate(${candDx}px, ${candDy}px)`;
                    });

                    drawLines();
                    saveLayoutState();

                    if (anySnapped) {
                        showToast('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: #00e676;"><polyline points="20 6 9 17 4 12"></polyline></svg> <span>Garis otomatis lurus & sejajar!</span>', false);
                    }
                }
            });"""

# 3. Update dragMove to also support Smart Auto-Snap when dragging cards
new_drag_move = """            function dragMove(e) {
                if (!activeDragCard) return;

                const clientX = e.type === 'touchmove' ? e.touches[0].clientX : e.clientX;
                const clientY = e.type === 'touchmove' ? e.touches[0].clientY : e.clientY;

                let dx = (clientX - dragStartX) / zoomScale;
                let dy = (clientY - dragStartY) / zoomScale;

                // If dragging a single card (without Alt key), apply Smart Snapping!
                if (dragOffsets.size === 1 && !e.altKey) {
                    const origOffset = dragOffsets.get(activeDragCard);
                    if (origOffset) {
                        const candDx = origOffset.x + dx;
                        const candDy = origOffset.y + dy;
                        const snapRes = calculateSmartSnap(activeDragCard, candDx, candDy, true, true, 16);
                        
                        activeDragCard.setAttribute('data-dx', snapRes.dx);
                        activeDragCard.setAttribute('data-dy', snapRes.dy);
                        activeDragCard.style.transform = `translate(${snapRes.dx}px, ${snapRes.dy}px)`;
                        
                        drawLines();
                        if (e.type === 'touchmove') e.preventDefault();
                        return;
                    }
                }

                // Move all selected nodes in the group
                dragOffsets.forEach((origOffset, card) => {
                    const newX = origOffset.x + dx;
                    const newY = origOffset.y + dy;
                    card.setAttribute('data-dx', newX);
                    card.setAttribute('data-dy', newY);
                    card.style.transform = `translate(${newX}px, ${newY}px)`;
                });

                drawLines();

                if (e.type === 'touchmove') {
                    e.preventDefault();
                }
            }"""

# Insert smart_snap_engine before keydown listener
if "function calculateSmartSnap" not in html:
    html = html.replace(
        "// Keyboard Card Movement with Smart Auto-Straight Snapping",
        smart_snap_engine + "\n\n            // Keyboard Card Movement with Smart Auto-Straight Snapping"
    )

# Replace keydown listener
html = re.sub(
    r'// Keyboard Card Movement with Smart Auto-Straight Snapping[\s\S]*?saveLayoutState\(\);\s*\}\s*\}\);',
    new_keydown_handler,
    html
)

# Replace dragMove
html = re.sub(
    r'function dragMove\(e\) \{[\s\S]*?if \(e\.type === \'touchmove\'\) \{\s*e\.preventDefault\(\);\s*\}\s*\}',
    new_drag_move,
    html
)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Universal Straight Line Snapping engine installed successfully!")
