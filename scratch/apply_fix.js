const fs = require('fs');

const HTML_PATH = 'B:\\Project MT5\\Other\\Dokumen\\diagram_arsitektur.html';
const LAYOUT_PATH = 'B:\\Project MT5\\Other\\Dokumen\\diagram_layout.json';

let html = fs.readFileSync(HTML_PATH, 'utf8');
const layoutJson = fs.readFileSync(LAYOUT_PATH, 'utf8');

const middleBlock = `const defaultLayoutState = ${layoutJson};

            // Selection & Hover Flow State
            let hoveredCardId = null;
            let selectedNodeCardId = null;

            // Drag-and-drop state
            let activeDragCard = null;
            let dragStartX = 0;
            let dragStartY = 0;
            let cardOffsetX = 0;
            let cardOffsetY = 0;

            // Viewport Pan & Zoom state
            let isPanning = false;
            let panX = 0;
            let panY = 0;
            let panStartX = 0;
            let panStartY = 0;

            let zoomScale = 1.0;
            const MIN_ZOOM = 0.2;
            const MAX_ZOOM = 2.5;

            function updateTransform() {
                const panContainer = document.getElementById('pan-container');
                if (panContainer) {
                    panContainer.style.transform = \`translate(\${panX}px, \${panY}px) scale(\${zoomScale})\`;
                }
                const badge = document.getElementById('zoom-level-badge');
                if (badge) {
                    badge.textContent = \`\${Math.round(zoomScale * 100)}%\`;
                }
                drawLines();
            }

            // Mouse Wheel Focal Zoom Handler (Zoom towards cursor position)
            function handleWheelZoom(e) {
                e.preventDefault();
                const viewport = document.getElementById('diagram-viewport');
                const rect = viewport.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;

                const zoomDelta = -e.deltaY * 0.0012;
                const factor = Math.exp(zoomDelta);
                const targetScale = Math.min(Math.max(zoomScale * factor, MIN_ZOOM), MAX_ZOOM);

                if (Math.abs(targetScale - zoomScale) < 0.001) return;

                // Focal point zoom math
                panX = mouseX - (mouseX - panX) * (targetScale / zoomScale);
                panY = mouseY - (mouseY - panY) * (targetScale / zoomScale);
                zoomScale = targetScale;

                updateTransform();
                saveLayoutState();
            }

            // Zoom Toolbar Handlers
            function zoomIn() {
                const viewport = document.getElementById('diagram-viewport');
                const rect = viewport ? viewport.getBoundingClientRect() : { width: window.innerWidth, height: window.innerHeight, left: 0, top: 0 };
                const mouseX = rect.width / 2;
                const mouseY = rect.height / 2;
                const targetScale = Math.min(zoomScale * 1.2, MAX_ZOOM);
                if (targetScale === zoomScale) return;

                panX = mouseX - (mouseX - panX) * (targetScale / zoomScale);
                panY = mouseY - (mouseY - panY) * (targetScale / zoomScale);
                zoomScale = targetScale;

                updateTransform();
                saveLayoutState();
            }

            function zoomOut() {
                const viewport = document.getElementById('diagram-viewport');
                const rect = viewport ? viewport.getBoundingClientRect() : { width: window.innerWidth, height: window.innerHeight, left: 0, top: 0 };
                const mouseX = rect.width / 2;
                const mouseY = rect.height / 2;
                const targetScale = Math.max(zoomScale / 1.2, MIN_ZOOM);
                if (targetScale === zoomScale) return;

                panX = mouseX - (mouseX - panX) * (targetScale / zoomScale);
                panY = mouseY - (mouseY - panY) * (targetScale / zoomScale);
                zoomScale = targetScale;

                updateTransform();
                saveLayoutState();
            }

            function zoomReset() {
                zoomScale = 1.0;
                panX = 0;
                panY = 0;
                updateTransform();
                saveLayoutState();
            }

            function fitView() {
                const cards = document.querySelectorAll('.node-card, .agent-card');
                if (!cards.length) return;
                const viewport = document.getElementById('diagram-viewport');
                const vRect = viewport.getBoundingClientRect();

                let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
                cards.forEach(card => {
                    const dx = parseFloat(card.getAttribute('data-dx') || '0');
                    const dy = parseFloat(card.getAttribute('data-dy') || '0');
                    const left = card.offsetLeft + dx;
                    const top = card.offsetTop + dy;
                    const right = left + card.offsetWidth;
                    const bottom = top + card.offsetHeight;

                    if (left < minX) minX = left;
                    if (top < minY) minY = top;
                    if (right > maxX) maxX = right;
                    if (bottom > maxY) maxY = bottom;
                });

                const pad = 100;
                const contentW = (maxX - minX) + pad * 2;
                const contentH = (maxY - minY) + pad * 2;
                const sidePanel = document.getElementById('side-panel');
                const sidePanelW = sidePanel ? sidePanel.offsetWidth : 350;
                const availableW = Math.max(300, vRect.width - sidePanelW - 40);
                const availableH = Math.max(300, vRect.height);

                const scaleFit = Math.min(availableW / contentW, availableH / contentH);
                zoomScale = Math.min(Math.max(scaleFit, MIN_ZOOM), 1.2);
                panX = pad - minX * zoomScale;
                panY = pad - minY * zoomScale;

                updateTransform();
                saveLayoutState();
            }

            // Connection selection state
            let sourceNodeId = null;
            let sourceNodePort = null;

            // Update lines on resize/load
            window.addEventListener('resize', drawLines);
            window.addEventListener('load', () => {
                initializeDragAndDrop();
                restoreLayoutState();
                drawLines();
            });

            // Clear connection source selection when pressing Escape key
            window.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    clearConnectionSelection();
                    hideDeletePopup();
                }
            });

            function initializeDragAndDrop() {
                // 1. Initialize card drags and dynamic handles
                document.querySelectorAll('.node-card, .agent-card').forEach(card => {
                    if (!card.hasAttribute('data-dx')) card.setAttribute('data-dx', '0');
                    if (!card.hasAttribute('data-dy')) card.setAttribute('data-dy', '0');
                    card.style.userSelect = 'none';
                    card.style.touchAction = 'none';

                    // Remove existing handles if any
                    card.querySelectorAll('.port-handle').forEach(h => h.remove());

                    // Add 4 directional handles (top, bottom, left, right)
                    ['top', 'bottom', 'left', 'right'].forEach(port => {
                        const handle = document.createElement('div');
                        handle.className = \`port-handle \${port}\`;
                        handle.innerHTML = '+';
                        handle.title = \`Tarik aliran baru dari gagang \${port} ini...\`;
                        handle.addEventListener('click', (e) => handlePortClick(e, card.id, port));
                        card.appendChild(handle);
                    });

                    card.addEventListener('mousedown', dragStart);
                    card.addEventListener('touchstart', dragStart, { passive: false });

                    // Real-time hover flow lighting on card
                    card.addEventListener('mouseenter', () => {
                        if (!activeDragCard && !isPanning) {
                            hoveredCardId = card.id;
                            updateFlowHighlights();
                        }
                    });
                    card.addEventListener('mouseleave', () => {
                        if (!activeDragCard && !isPanning) {
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

            // Connection Editor Click Actions`;

html = html.replace(/const defaultLayoutState = [\s\S]*?\/\/ Connection Editor Click Actions/, middleBlock);

fs.writeFileSync(HTML_PATH, html, 'utf8');
console.log('Successfully updated HTML file!');
