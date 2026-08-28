
            // Default System Connections with Specific Port Assignments
            const defaultConnections = [
                // Stage 1 Ingestion & Storage Chain
                { from: "node-mt5", fromPort: "right", to: "node-watcher-trigger", toPort: "left" },
                { from: "node-watcher-trigger", fromPort: "bottom", to: "node-neondb-mapping", toPort: "top" },
                { from: "node-neondb-mapping", fromPort: "bottom", to: "node-lancedb", toPort: "top" },

                // Stage 1 -> Stage 2 (Orchestrator Coordination)
                { from: "node-watcher-trigger", fromPort: "right", to: "node-orchestrator", toPort: "left" },
                { from: "node-neondb-mapping", fromPort: "right", to: "node-orchestrator", toPort: "left" },
                { from: "node-lancedb", fromPort: "right", to: "node-orchestrator", toPort: "left" },

                // Orchestrator -> Sub-Agents
                { from: "node-orchestrator", fromPort: "right", to: "node-ms-agent", toPort: "left" },
                { from: "node-ms-agent", fromPort: "bottom", to: "node-ms-sub1", toPort: "top" },
                { from: "node-ms-sub1", fromPort: "bottom", to: "node-ms-sub2", toPort: "top" },
                { from: "node-orchestrator", fromPort: "right", to: "node-ml-agent", toPort: "left" },
                { from: "node-orchestrator", fromPort: "right", to: "node-risk-agent", toPort: "left" },
                { from: "node-orchestrator", fromPort: "right", to: "node-sentiment-agent", toPort: "left" },

                // Sub-Agents -> Consensus Engine / Sequential Flow
                { from: "node-ms-sub2", fromPort: "right", to: "node-con-sub1", toPort: "left" },
                { from: "node-ms-sub2", fromPort: "right", to: "node-msa-to-ml-info", toPort: "left" },
                { from: "node-msa-to-ml-info", fromPort: "right", to: "node-ml-agent", toPort: "left" },
                { from: "node-ml-agent", fromPort: "bottom", to: "node-ml-sub1", toPort: "top" },
                { from: "node-ml-sub1", fromPort: "bottom", to: "node-ml-sub2", toPort: "top" },
                { from: "node-ml-sub2", fromPort: "bottom", to: "node-ml-sub3", toPort: "top" },
                { from: "node-ml-sub3", fromPort: "bottom", to: "node-ml-sub4", toPort: "top" },
                { from: "node-ml-sub4", fromPort: "bottom", to: "node-ml-sub5", toPort: "top" },
                { from: "node-ml-sub5", fromPort: "right", to: "node-con-sub2", toPort: "left" },
                { from: "node-ms-sub2", fromPort: "right", to: "node-msa-to-sent-info", toPort: "left" },
                { from: "node-msa-to-sent-info", fromPort: "right", to: "node-sent-sub3", toPort: "left" },
                { from: "node-sentiment-agent", fromPort: "bottom", to: "node-sent-sub1", toPort: "top" },
                { from: "node-sent-sub1", fromPort: "bottom", to: "node-sent-sub2", toPort: "top" },
                { from: "node-sent-sub2", fromPort: "bottom", to: "node-sent-sub3", toPort: "top" },
                { from: "node-sent-sub3", fromPort: "bottom", to: "node-sent-sub4", toPort: "top" },
                { from: "node-sent-sub4", fromPort: "bottom", to: "node-sent-sub5", toPort: "top" },
                { from: "node-sent-sub5", fromPort: "right", to: "node-con-sub3", toPort: "left" },
                { from: "node-con-sub1", fromPort: "right", to: "node-consensus", toPort: "left" },
                { from: "node-con-sub2", fromPort: "right", to: "node-consensus", toPort: "left" },
                { from: "node-con-sub3", fromPort: "right", to: "node-consensus", toPort: "left" },

                // Consensus -> Workflow Steps (Sequential)
                { from: "node-consensus", fromPort: "right", to: "node-con-step1", toPort: "left" },
                { from: "node-con-step1", fromPort: "bottom", to: "node-con-step2", toPort: "top" },
                { from: "node-con-step2", fromPort: "bottom", to: "node-con-step3", toPort: "top" },
                { from: "node-con-step3", fromPort: "bottom", to: "node-con-step4", toPort: "top" },
                { from: "node-con-step4", fromPort: "bottom", to: "node-con-step5", toPort: "top" },

                // Consensus Steps -> Risk Management -> Execution
                { from: "node-con-step5", fromPort: "right", to: "node-risk-agent", toPort: "left" },
                { from: "node-consensus", fromPort: "right", to: "node-risk-agent", toPort: "left" },

                // Risk Management Internal Workflow
                { from: "node-risk-agent", fromPort: "bottom", to: "node-risk-sub1", toPort: "top" },
                { from: "node-risk-sub1", fromPort: "bottom", to: "node-risk-sub2", toPort: "top" },
                { from: "node-risk-sub2", fromPort: "bottom", to: "node-risk-sub3", toPort: "top" },
                { from: "node-risk-sub3", fromPort: "bottom", to: "node-risk-sub4", toPort: "top" },
                { from: "node-risk-sub4", fromPort: "bottom", to: "node-risk-sub5", toPort: "top" },
                { from: "node-risk-sub5", fromPort: "right", to: "node-execution", toPort: "left" }
            ];

            let connections = [...defaultConnections];
            const LAYOUT_VERSION = 8; // ponytail: bump when defaultConnections change

            // Baked-in Default Layout State (Used when localStorage is empty or on different browser)
            const defaultLayoutState = {
    "version": 8,
    "pan": {
        "x": -45.56463499730444,
        "y": 59.97027556172486
    },
    "zoom": 0.41756287347312876,
    "nodes": {
        "node-mt5": {
            "dx": 732.211525181092,
            "dy": -464.7048853987483
        },
        "node-watcher-trigger": {
            "dx": 851.6290314025617,
            "dy": -384.70350603005704
        },
        "node-neondb-mapping": {
            "dx": 43.645071595002925,
            "dy": 0
        },
        "node-lancedb": {
            "dx": 40.153465867402694,
            "dy": 50.62828305020339
        },
        "node-orchestrator": {
            "dx": 1113.8222271044747,
            "dy": -406.77206726542727
        },
        "node-fe-to-orch-info": {
            "dx": 1236.9427769474482,
            "dy": -1043.6881205663337
        },
        "node-orch-to-msa-info": {
            "dx": 1317.8107219569988,
            "dy": -604.194517210662
        },
        "node-msa-to-orch-info": {
            "dx": 992.7689522882293,
            "dy": -653.7816843130096
        },
        "node-orch-cond1": {
            "dx": 1991.7635996547433,
            "dy": -2251.3755118923564
        },
        "node-orch-cond2": {
            "dx": 1991.7633637784113,
            "dy": -2188.015144978268
        },
        "node-orch-cond3": {
            "dx": 2015.1178136573312,
            "dy": -2120.262900766753
        },
        "node-ms-agent": {
            "dx": 1349.067187864289,
            "dy": -1783.7891057431102
        },
        "node-ms-sub1": {
            "dx": 1073.2303353838706,
            "dy": -1844.8922059761144
        },
        "node-ms-sub2": {
            "dx": 785.1728628568511,
            "dy": -1897.2662918901178
        },
        "node-msa-to-ml-info": {
            "dx": 2286.6060622440823,
            "dy": -2961.2942187915746
        },
        "node-ml-agent": {
            "dx": 2378.0715068902114,
            "dy": -2925.930962779401
        },
        "node-ml-sub1": {
            "dx": 2674.900985817117,
            "dy": -3260.905812469026
        },
        "node-ml-sub2": {
            "dx": 2811.0736091935255,
            "dy": -3576.8961308168477
        },
        "node-ml-sub3": {
            "dx": 3116.589110358546,
            "dy": -3723.5435713760576
        },
        "node-ml-sub4": {
            "dx": 3244.032719415955,
            "dy": -3683.390105508655
        },
        "node-ml-sub5": {
            "dx": 3446.545851616768,
            "dy": -4016.838452494477
        },
        "node-risk-agent": {
            "dx": 2758.3685248041847,
            "dy": -288.05747252701934
        },
        "node-msa-to-sent-info": {
            "dx": 1453.4280943076092,
            "dy": -2451.274687153412
        },
        "node-sentiment-agent": {
            "dx": 1526.751814587214,
            "dy": -2217.3371034041966
        },
        "node-sent-sub1": {
            "dx": 1530.2434203148146,
            "dy": -2178.929440400594
        },
        "node-sent-sub2": {
            "dx": 1254.406567834396,
            "dy": -2341.2891067340047
        },
        "node-sent-sub3": {
            "dx": 1252.6607649705961,
            "dy": -2302.8814437304018
        },
        "node-sent-sub4": {
            "dx": 980.3155182177775,
            "dy": -2460.0037014724126
        },
        "node-sent-sub5": {
            "dx": 978.5697153539775,
            "dy": -2803.926865641036
        },
        "node-consensus": {
            "dx": 1311.0979507138882,
            "dy": -298.53228970982
        },
        "node-con-sub1": {
            "dx": 811.7983316670544,
            "dy": -460.8919560432309
        },
        "node-con-sub2": {
            "dx": 813.5441345308545,
            "dy": -750.6952314340504
        },
        "node-con-sub3": {
            "dx": 817.0357402584548,
            "dy": -581.3523536454389
        },
        "node-con-step1": {
            "dx": 811.7983316670543,
            "dy": -34.916057276002306
        },
        "node-con-step2": {
            "dx": 1110.3306213768744,
            "dy": -183.30930069901228
        },
        "node-con-step3": {
            "dx": 1117.3138328320747,
            "dy": -139.66422910400934
        },
        "node-con-step4": {
            "dx": 813.5441345308544,
            "dy": -282.8200639356189
        },
        "node-con-step5": {
            "dx": 808.306725939454,
            "dy": -239.17499234061597
        },
        "node-risk-sub1": {
            "dx": 1248.2490476170835,
            "dy": -494.0622104554331
        },
        "node-risk-sub2": {
            "dx": 961.9373779538644,
            "dy": -731.491399932249
        },
        "node-risk-sub3": {
            "dx": 1263.9612733912847,
            "dy": -970.666392272865
        },
        "node-risk-sub4": {
            "dx": 981.1412094556657,
            "dy": -1218.5703989324818
        },
        "node-risk-sub5": {
            "dx": 1269.198681982685,
            "dy": -1454.2537855454975
        },
        "node-execution": {
            "dx": 1281.419302029286,
            "dy": -284.56586679941904
        }
    },
    "connections": [
        {
            "from": "node-mt5",
            "fromPort": "bottom",
            "to": "node-watcher-trigger",
            "toPort": "top"
        },
        {
            "from": "node-neondb-mapping",
            "fromPort": "bottom",
            "to": "node-lancedb",
            "toPort": "top"
        },
        {
            "from": "node-orchestrator",
            "fromPort": "left",
            "to": "node-neondb-mapping",
            "toPort": "right"
        },
        {
            "from": "node-orchestrator",
            "fromPort": "left",
            "to": "node-lancedb",
            "toPort": "right"
        },
        {
            "from": "node-ml-agent",
            "fromPort": "top",
            "to": "node-ml-sub1",
            "toPort": "left"
        },
        {
            "from": "node-ml-sub1",
            "fromPort": "top",
            "to": "node-ml-sub2",
            "toPort": "bottom"
        },
        {
            "from": "node-ml-sub2",
            "fromPort": "right",
            "to": "node-ml-sub3",
            "toPort": "left"
        },
        {
            "from": "node-ml-sub3",
            "fromPort": "bottom",
            "to": "node-ml-sub4",
            "toPort": "top"
        },
        {
            "from": "node-ml-sub4",
            "fromPort": "right",
            "to": "node-ml-sub5",
            "toPort": "bottom"
        },
        {
            "from": "node-ms-agent",
            "fromPort": "left",
            "to": "node-ms-sub1",
            "toPort": "top"
        },
        {
            "from": "node-ms-sub1",
            "fromPort": "left",
            "to": "node-ms-sub2",
            "toPort": "right"
        },
        {
            "from": "node-msa-to-sent-info",
            "fromPort": "bottom",
            "to": "node-sentiment-agent",
            "toPort": "left"
        },
        {
            "from": "node-sentiment-agent",
            "fromPort": "bottom",
            "to": "node-sent-sub1",
            "toPort": "top"
        },
        {
            "from": "node-sent-sub1",
            "fromPort": "left",
            "to": "node-sent-sub2",
            "toPort": "right"
        },
        {
            "from": "node-sent-sub2",
            "fromPort": "bottom",
            "to": "node-sent-sub3",
            "toPort": "top"
        },
        {
            "from": "node-sent-sub3",
            "fromPort": "left",
            "to": "node-sent-sub4",
            "toPort": "right"
        },
        {
            "from": "node-sent-sub4",
            "fromPort": "top",
            "to": "node-sent-sub5",
            "toPort": "bottom"
        },
        {
            "from": "node-con-sub2",
            "fromPort": "right",
            "to": "node-consensus",
            "toPort": "left"
        },
        {
            "from": "node-con-sub1",
            "fromPort": "right",
            "to": "node-consensus",
            "toPort": "left"
        },
        {
            "from": "node-con-sub3",
            "fromPort": "right",
            "to": "node-consensus",
            "toPort": "left"
        },
        {
            "from": "node-consensus",
            "fromPort": "bottom",
            "to": "node-con-step1",
            "toPort": "top"
        },
        {
            "from": "node-con-step1",
            "fromPort": "right",
            "to": "node-con-step2",
            "toPort": "left"
        },
        {
            "from": "node-con-step2",
            "fromPort": "bottom",
            "to": "node-con-step3",
            "toPort": "top"
        },
        {
            "from": "node-con-step3",
            "fromPort": "left",
            "to": "node-con-step4",
            "toPort": "right"
        },
        {
            "from": "node-con-step4",
            "fromPort": "bottom",
            "to": "node-con-step5",
            "toPort": "top"
        },
        {
            "from": "node-consensus",
            "fromPort": "right",
            "to": "node-risk-agent",
            "toPort": "left"
        },
        {
            "from": "node-risk-agent",
            "fromPort": "right",
            "to": "node-execution",
            "toPort": "left"
        },
        {
            "from": "node-risk-agent",
            "fromPort": "top",
            "to": "node-risk-sub1",
            "toPort": "bottom"
        },
        {
            "from": "node-risk-sub2",
            "fromPort": "top",
            "to": "node-risk-sub3",
            "toPort": "left"
        },
        {
            "from": "node-risk-sub3",
            "fromPort": "top",
            "to": "node-risk-sub4",
            "toPort": "right"
        },
        {
            "from": "node-risk-sub4",
            "fromPort": "top",
            "to": "node-risk-sub5",
            "toPort": "left"
        },
        {
            "from": "node-risk-sub1",
            "fromPort": "left",
            "to": "node-risk-sub2",
            "toPort": "bottom"
        },
        {
            "from": "node-msa-to-ml-info",
            "fromPort": "right",
            "to": "node-ml-agent",
            "toPort": "left"
        },
        {
            "from": "node-watcher-trigger",
            "fromPort": "left",
            "to": "node-neondb-mapping",
            "toPort": "top"
        },
        {
            "from": "node-watcher-trigger",
            "fromPort": "right",
            "to": "node-fe-to-orch-info",
            "toPort": "top"
        },
        {
            "from": "node-ms-agent",
            "fromPort": "top",
            "to": "node-msa-to-orch-info",
            "toPort": "bottom"
        },
        {
            "from": "node-msa-to-orch-info",
            "fromPort": "top",
            "to": "node-orchestrator",
            "toPort": "bottom"
        },
        {
            "from": "node-orchestrator",
            "fromPort": "right",
            "to": "node-orch-cond1",
            "toPort": "left"
        },
        {
            "from": "node-orchestrator",
            "fromPort": "right",
            "to": "node-orch-cond2",
            "toPort": "left"
        },
        {
            "from": "node-orchestrator",
            "fromPort": "right",
            "to": "node-orch-cond3",
            "toPort": "top"
        }
    ]
            let panStartX = 0;
            let panStartY = 0;

                viewport.addEventListener('touchstart', viewportPanStart, { passive: false });
                viewport.addEventListener('wheel', handleWheelZoom, { passive: false });
            }

            // Connection Editor Click Actions
            function handlePortClick(e, cardId, portName) {
                e.stopPropagation(); // Avoid selecting or dragging node
                hideDeletePopup();

                // Click target handle on another card? Connect them!
                if (sourceNodeId) {
                    if (sourceNodeId === cardId) {
                        clearConnectionSelection();
                    } else {
                        connectPorts(sourceNodeId, sourceNodePort, cardId, portName);
                        clearConnectionSelection();
                    }
                    return;
                }

                // Otherwise, select source port
                sourceNodeId = cardId;
                sourceNodePort = portName;
                document.getElementById(cardId).classList.add('connecting-source');
                e.currentTarget.classList.add('connecting-source-port');
            }

            function clearConnectionSelection() {
                sourceNodeId = null;
                sourceNodePort = null;
                document.querySelectorAll('.node-card, .agent-card').forEach(card => {
                    card.classList.remove('connecting-source');
                });
                document.querySelectorAll('.port-handle').forEach(handle => {
                    handle.classList.remove('connecting-source-port');
                });
            }

            function connectPorts(fromId, fromPort, toId, toPort) {
                // Check if exact connection already exists
                const exactIndex = connections.findIndex(conn =>
                    conn.from === fromId && conn.fromPort === fromPort &&
                    conn.to === toId && conn.toPort === toPort
                );

                if (exactIndex > -1) {
                    // Exact connection exists: remove it (toggle off)
                    connections.splice(exactIndex, 1);
                } else {
                    // Simply push the connection to allow multiple outputs from the same port/side
                    connections.push({ from: fromId, fromPort, to: toId, toPort });
                }
                saveLayoutState();
                drawLines();
            }

            function toggleConnection(fromId, toId) {
                // Internal fallback: remove all connections between these two cards
                connections = connections.filter(conn => !(conn.from === fromId && conn.to === toId));
                saveLayoutState();
                drawLines();
            }

            function getNameForCard(id) {
                const card = document.getElementById(id);
                if (!card) return id;
                const titleEl = card.querySelector('.card-title');
                return titleEl ? titleEl.textContent.trim() : id;
            }

            function showDeletePopup(x, y, fromId, toId) {
                const popup = document.getElementById('delete-popup');
                const text = document.getElementById('delete-popup-text');
                const delBtn = document.getElementById('popup-delete-btn');
                const cancelBtn = document.getElementById('popup-cancel-btn');

                const nameA = getNameForCard(fromId);
                const nameB = getNameForCard(toId);
                text.innerHTML = `Hapus aliran dari <strong>${nameA}</strong> ke <strong>${nameB}</strong>?`;

                popup.style.left = `${x}px`;
                popup.style.top = `${y}px`;
                popup.style.display = 'block';

                delBtn.onclick = (e) => {
                    e.stopPropagation();
                    toggleConnection(fromId, toId);
                    hideDeletePopup();
                };

                cancelBtn.onclick = (e) => {
                    e.stopPropagation();
                    hideDeletePopup();
                };
            }

            function hideDeletePopup() {
                const popup = document.getElementById('delete-popup');
                if (popup) popup.style.display = 'none';
            }

            // Viewport Pan handlers
            function viewportPanStart(e) {
                if (
                    e.target.closest('.node-card') ||
                    e.target.closest('.agent-card') ||
                    e.target.closest('a') ||
                    e.target.closest('ul') ||
                    e.target.closest('button') ||
                    e.target.closest('.floating-popup') ||
                    e.target.closest('.zoom-controls') ||
                    e.target.closest('.detail-panel') ||
                    e.target.closest('.edge-delete-btn') ||
                    e.target.closest('.flow-path-hover-bridge') ||
                    e.target.closest('.flow-path') ||
                    e.target.closest('.edge-group')
                ) return;
                if (e.type === 'mousedown' && e.button !== 0) return;

                // Clear selection, close side panel, and hide popup when clicking empty space
                if (sourceNodeId) {
                    clearConnectionSelection();
                }
                closeSidePanel();
                hideDeletePopup();

                isPanning = true;
                document.getElementById('diagram-viewport').style.cursor = 'grabbing';

                const clientX = e.type === 'touchstart' ? e.touches[0].clientX : e.clientX;
                const clientY = e.type === 'touchstart' ? e.touches[0].clientY : e.clientY;

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
            }

            // Card Drag handlers
            let dragOffsets = new Map(); // Store original offsets for each active drag node

            function dragStart(e) {
                if (e.type === 'mousedown' && e.button !== 0) return;
                if (e.target.closest('a') || e.target.closest('ul') || e.target.closest('.port-handle')) return;

                const targetCard = e.currentTarget;
                hideDeletePopup();

                // If Ctrl key is pressed, toggle selection and skip immediate dragging
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    targetCard.classList.toggle('multiselected');
                    return;
                }

                // Normal drag flow: determine if dragging a multi-selected group or a single card
                let dragGroup = [];
                if (targetCard.classList.contains('multiselected')) {
                    dragGroup = Array.from(document.querySelectorAll('.multiselected'));
                } else {
                    // Clear other selections if dragging a non-selected card
                    document.querySelectorAll('.multiselected').forEach(el => el.classList.remove('multiselected'));
                    dragGroup = [targetCard];
                }

                activeDragCard = targetCard;
                dragOffsets.clear();

                const clientX = e.type === 'touchstart' ? e.touches[0].clientX : e.clientX;
                const clientY = e.type === 'touchstart' ? e.touches[0].clientY : e.clientY;

                dragStartX = clientX;
                dragStartY = clientY;

                // Save starting positions for all elements in the drag group
                dragGroup.forEach(card => {
                    const dx = parseFloat(card.getAttribute('data-dx') || '0');
                    const dy = parseFloat(card.getAttribute('data-dy') || '0');
                    dragOffsets.set(card, { x: dx, y: dy });

                    card.style.transition = 'none';
                    card.style.cursor = 'grabbing';
                    card.style.zIndex = '100';
                });

                // Connect automatically if a connection source is already selected
                if (sourceNodeId && !targetCard.classList.contains('multiselected')) {
                    e.preventDefault();
                    if (sourceNodeId === targetCard.id) {
                        clearConnectionSelection();
                    } else {
                        const rectA = document.getElementById(sourceNodeId).getBoundingClientRect();
                        const rectB = targetCard.getBoundingClientRect();
                        const rectCanvas = document.getElementById('svg-canvas').getBoundingClientRect();
                        const startCoord = getPortCoordinates(rectA, sourceNodePort, rectCanvas);

                        const portsB = {
                            top: { x: rectB.left + rectB.width / 2 - rectCanvas.left, y: rectB.top - rectCanvas.top },
                            bottom: { x: rectB.left + rectB.width / 2 - rectCanvas.left, y: rectB.bottom - rectCanvas.top },
                            left: { x: rectB.left - rectCanvas.left, y: rectB.top + rectB.height / 2 - rectCanvas.top },
                            right: { x: rectB.right - rectCanvas.left, y: rectB.top + rectB.height / 2 - rectCanvas.top }
                        };

                        let bestPort = 'left';
                        let minDist = Infinity;
                        for (let p in portsB) {
                            const dist = Math.hypot(startCoord.x - portsB[p].x, startCoord.y - portsB[p].y);
                            if (dist < minDist) {
                                minDist = dist;
                                bestPort = p;
                            }
                        }

                        connectPorts(sourceNodeId, sourceNodePort, targetCard.id, bestPort);
                        clearConnectionSelection();
                    }
                    activeDragCard = null;
                    return;
                }

                document.addEventListener('mousemove', dragMove);
                document.addEventListener('mouseup', dragEnd);
                document.addEventListener('touchmove', dragMove, { passive: false });
                document.addEventListener('touchend', dragEnd);

                if (e.type === 'touchstart') {
                    e.preventDefault();
                }
            }

            function dragMove(e) {
                if (!activeDragCard) return;

                const clientX = e.type === 'touchmove' ? e.touches[0].clientX : e.clientX;
                const clientY = e.type === 'touchmove' ? e.touches[0].clientY : e.clientY;

                const dx = (clientX - dragStartX) / zoomScale;
                const dy = (clientY - dragStartY) / zoomScale;

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
            }

            function dragEnd() {
                if (!activeDragCard) return;

                dragOffsets.forEach((origOffset, card) => {
                    card.style.transition = 'transform 0.1s ease, box-shadow 0.4s, border-color 0.4s';
                    card.style.cursor = 'pointer';
                    card.style.zIndex = '10';
                });

                activeDragCard = null;
                dragOffsets.clear();

                document.removeEventListener('mousemove', dragMove);
                document.removeEventListener('mouseup', dragEnd);
                document.removeEventListener('touchmove', dragMove);
                document.removeEventListener('touchend', dragEnd);
                saveLayoutState();
            }

            // SVG Connector Line Math
            function getBestConnectionPoints(rectA, rectB, rectCanvas) {
                const pA = {
                    top: { x: rectA.left + rectA.width / 2 - rectCanvas.left, y: rectA.top - rectCanvas.top, dir: 'up' },
                    bottom: { x: rectA.left + rectA.width / 2 - rectCanvas.left, y: rectA.bottom - rectCanvas.top, dir: 'down' },
                    left: { x: rectA.left - rectCanvas.left, y: rectA.top + rectA.height / 2 - rectCanvas.top, dir: 'left' },
                    right: { x: rectA.right - rectCanvas.left, y: rectA.top + rectA.height / 2 - rectCanvas.top, dir: 'right' }
                };
                const pB = {
                    top: { x: rectB.left + rectB.width / 2 - rectCanvas.left, y: rectB.top - rectCanvas.top, dir: 'up' },
                    bottom: { x: rectB.left + rectB.width / 2 - rectCanvas.left, y: rectB.bottom - rectCanvas.top, dir: 'down' },
                    left: { x: rectB.left - rectCanvas.left, y: rectB.top + rectB.height / 2 - rectCanvas.top, dir: 'left' },
                    right: { x: rectB.right - rectCanvas.left, y: rectB.top + rectB.height / 2 - rectCanvas.top, dir: 'right' }
                };

                let minDistance = Infinity;
                let bestA = null;
                let bestB = null;

                for (let keyA in pA) {
                    for (let keyB in pB) {
                        const dist = Math.hypot(pA[keyA].x - pB[keyB].x, pA[keyA].y - pB[keyB].y);
                        if (dist < minDistance) {
                            minDistance = dist;
                            bestA = pA[keyA];
                            bestB = pB[keyB];
                        }
                    }
                }
                return { start: bestA, end: bestB };
            }

            function getPortCoordinates(rect, portName, rectCanvas, offsetIndex = 0, totalOnPort = 1) {
                if (!portName) return null;
                const spread = 20; // clean multi-lane lane spacing (px)
                const shift = totalOnPort > 1 ? (offsetIndex - (totalOnPort - 1) / 2) * spread : 0;

                switch (portName) {
                    case 'top':
                        return { x: rect.left + rect.width / 2 + shift - rectCanvas.left, y: rect.top - rectCanvas.top, dir: 'up' };
                    case 'bottom':
                        return { x: rect.left + rect.width / 2 + shift - rectCanvas.left, y: rect.bottom - rectCanvas.top, dir: 'down' };
                    case 'left':
                        return { x: rect.left - rectCanvas.left, y: rect.top + rect.height / 2 + shift - rectCanvas.top, dir: 'left' };
                    case 'right':
                        return { x: rect.right - rectCanvas.left, y: rect.top + rect.height / 2 + shift - rectCanvas.top, dir: 'right' };
                    default:
                        return null;
                }
            }

            function offsetBidirectionalPoint(point, offset) {
                if (!point || !offset) return point;
                if (point.dir === 'top' || point.dir === 'bottom' || point.dir === 'up' || point.dir === 'down') {
                    return { ...point, x: point.x + offset };
                }
                return { ...point, y: point.y + offset };
            }

            function drawCurvedPath(id, ptA, ptB) {
                const path = document.getElementById(id);
                if (!path) return null;
                const start = ptA;
                const end = ptB;
                const sx = start.x, sy = start.y, sDir = start.dir;
                const ex = end.x, ey = end.y, eDir = end.dir;

                let d = "";
                let midX = (sx + ex) / 2;
                let midY = (sy + ey) / 2;

                // 1. Horizontal Corridor: Right -> Left (Normal forward flow)
                if (sDir === 'right' && eDir === 'left') {
                    if (ex >= sx + 10) {
                        midX = (sx + ex) / 2;
                        d = `M ${sx} ${sy} C ${midX} ${sy}, ${midX} ${ey}, ${ex - 6} ${ey} L ${ex} ${ey}`;
                    } else {
                        // Backward wrap: route around cleanly
                        const lateralX = Math.max(sx + 50, ex + 50);
                        d = `M ${sx} ${sy} C ${lateralX} ${sy}, ${lateralX} ${ey}, ${ex - 6} ${ey} L ${ex} ${ey}`;
                    }
                }
                // 2. Horizontal Corridor: Left -> Right
                else if (sDir === 'left' && eDir === 'right') {
                    if (ex <= sx - 10) {
                        midX = (sx + ex) / 2;
                        d = `M ${sx} ${sy} C ${midX} ${sy}, ${midX} ${ey}, ${ex + 6} ${ey} L ${ex} ${ey}`;
                    } else {
                        const lateralX = Math.min(sx - 50, ex - 50);
                        d = `M ${sx} ${sy} C ${lateralX} ${sy}, ${lateralX} ${ey}, ${ex + 6} ${ey} L ${ex} ${ey}`;
                    }
                }
                // 3. Vertical Straight/S-Curve: Down -> Up (Normal downward cascade)
                else if (sDir === 'down' && eDir === 'up') {
                    if (ey >= sy) {
                        if (Math.abs(sx - ex) < 4) {
                            d = `M ${sx} ${sy} L ${ex} ${ey}`;
                        } else {
                            midY = (sy + ey) / 2;
                            d = `M ${sx} ${sy} C ${sx} ${midY}, ${ex} ${midY}, ${ex} ${ey - 6} L ${ex} ${ey}`;
                        }
                    } else {
                        // Target is above: route around side
                        const gutterX = Math.min(sx, ex) - 50;
                        d = `M ${sx} ${sy} C ${gutterX} ${sy + 40}, ${gutterX} ${ey - 40}, ${ex} ${ey - 6} L ${ex} ${ey}`;
                    }
                }
                // 4. Vertical Straight/S-Curve: Up -> Down
                else if (sDir === 'up' && eDir === 'down') {
                    if (ey <= sy) {
                        if (Math.abs(sx - ex) < 4) {
                            d = `M ${sx} ${sy} L ${ex} ${ey}`;
                        } else {
                            midY = (sy + ey) / 2;
                            d = `M ${sx} ${sy} C ${sx} ${midY}, ${ex} ${midY}, ${ex} ${ey + 6} L ${ex} ${ey}`;
                        }
                    } else {
                        const gutterX = Math.max(sx, ex) + 50;
                        d = `M ${sx} ${sy} C ${gutterX} ${sy - 40}, ${gutterX} ${ey + 40}, ${ex} ${ey + 6} L ${ex} ${ey}`;
                    }
                }
                // 5. Right -> Up (Elbow smoothly entering target top)
                else if (sDir === 'right' && eDir === 'up') {
                    if (ex >= sx && ey >= sy) {
                        d = `M ${sx} ${sy} C ${ex} ${sy}, ${ex} ${sy + (ey - sy) * 0.3}, ${ex} ${ey - 6} L ${ex} ${ey}`;
                    } else {
                        const leadX = Math.max(sx + 35, (sx + ex) / 2);
                        d = `M ${sx} ${sy} C ${leadX} ${sy}, ${ex} ${Math.min(sy, ey) - 30}, ${ex} ${ey - 6} L ${ex} ${ey}`;
                    }
                }
                // 6. Right -> Down (Elbow entering target bottom)
                else if (sDir === 'right' && eDir === 'down') {
                    const leadX = Math.max(sx + 35, (sx + ex) / 2);
                    d = `M ${sx} ${sy} C ${leadX} ${sy}, ${ex} ${Math.max(sy, ey) + 30}, ${ex} ${ey + 6} L ${ex} ${ey}`;
                }
                // 7. Down -> Left (Elbow leaving bottom and entering target left)
                else if (sDir === 'down' && eDir === 'left') {
                    if (ex >= sx && ey >= sy) {
                        d = `M ${sx} ${sy} C ${sx} ${ey}, ${sx + (ex - sx) * 0.3} ${ey}, ${ex - 6} ${ey} L ${ex} ${ey}`;
                    } else {
                        const leadY = Math.max(sy + 35, (sy + ey) / 2);
                        d = `M ${sx} ${sy} C ${sx} ${leadY}, ${Math.min(sx, ex) - 30} ${ey}, ${ex - 6} ${ey} L ${ex} ${ey}`;
                    }
                }
                // 8. Down -> Right (Elbow leaving bottom and entering target right)
                else if (sDir === 'down' && eDir === 'right') {
                    const leadY = Math.max(sy + 35, (sy + ey) / 2);
                    d = `M ${sx} ${sy} C ${sx} ${leadY}, ${Math.max(sx, ex) + 30} ${ey}, ${ex + 6} ${ey} L ${ex} ${ey}`;
                }
                // 9. Up -> Left
                else if (sDir === 'up' && eDir === 'left') {
                    const leadY = Math.min(sy - 35, (sy + ey) / 2);
                    d = `M ${sx} ${sy} C ${sx} ${leadY}, ${Math.min(sx, ex) - 30} ${ey}, ${ex - 6} ${ey} L ${ex} ${ey}`;
                }
                // 10. Up -> Right
                else if (sDir === 'up' && eDir === 'right') {
                    const leadY = Math.min(sy - 35, (sy + ey) / 2);
                    d = `M ${sx} ${sy} C ${sx} ${leadY}, ${Math.max(sx, ex) + 30} ${ey}, ${ex + 6} ${ey} L ${ex} ${ey}`;
                }
                // 11. Controlled Safe Default
                else {
                    const dist = Math.hypot(ex - sx, ey - sy);
                    const leadDist = Math.min(50, Math.max(15, dist * 0.25));

                    let cp1x = sx, cp1y = sy;
                    if (sDir === 'up') cp1y -= leadDist;
                    else if (sDir === 'down') cp1y += leadDist;
                    else if (sDir === 'left') cp1x -= leadDist;
                    else if (sDir === 'right') cp1x += leadDist;

                    let cp2x = ex, cp2y = ey;
                    if (eDir === 'up') cp2y -= leadDist;
                    else if (eDir === 'down') cp2y += leadDist;
                    else if (eDir === 'left') cp2x -= leadDist;
                    else if (eDir === 'right') cp2x += leadDist;

                    d = `M ${sx} ${sy} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${ex} ${ey}`;
                }

                path.setAttribute('d', d);

                // Calculate exact geometric midpoint along the actual SVG curved path
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
                return midPoint;
            }

            function getNodeThemeColor(cardId) {
                if (!cardId) return '#00e5ff';
                if (cardId.includes('mt5')) return '#00f2fe';
                if (cardId.includes('watcher')) return '#00e676';
                if (cardId.includes('neon')) return '#00e5ff';
                if (cardId.includes('lancedb')) return '#e040fb';
                if (cardId.includes('orchestrator')) return '#ff9100';
                if (cardId.includes('ms-agent') || cardId.includes('ms-sub')) return '#00e676';
                if (cardId.includes('msa-to-ml') || cardId.includes('msa-to-sent')) return '#ffaa00';
                if (cardId.includes('ml-agent') || cardId.includes('ml-sub')) return '#b388ff';
                if (cardId.includes('sentiment') || cardId.includes('sent-sub')) return '#ff4081';
                if (cardId.includes('consensus') || cardId.includes('con-sub') || cardId.includes('con-step')) return '#00e5ff';
                if (cardId.includes('risk') || cardId.includes('risk-sub')) return '#ffd600';
                if (cardId.includes('execution')) return '#ff1744';
                return '#00e5ff';
            }

            function getConnectedFlowGraph(startNodeId) {
                if (!startNodeId) return { activeNodes: new Set(), activeEdgeIndices: new Set() };

                const activeNodes = new Set();
                const activeEdgeIndices = new Set();

                // Seed with start node and cluster internal siblings
                const seedNodes = new Set([startNodeId]);
                const stagePrefixes = ['node-ms', 'node-ml', 'node-sent', 'node-con', 'node-risk'];
                for (const prefix of stagePrefixes) {
                    if (startNodeId.startsWith(prefix)) {
                        connections.forEach(conn => {
                            if (conn.from.startsWith(prefix) && conn.to.startsWith(prefix)) {
                                seedNodes.add(conn.from);
                                seedNodes.add(conn.to);
                            }
                        });
                        break;
                    }
                }

                seedNodes.forEach(n => activeNodes.add(n));

                // Pure Forward Downstream Traversal (Eksklusif menelusuri ke depan saja)
                const forwardQueue = Array.from(seedNodes);
                const visitedForward = new Set(seedNodes);

                while (forwardQueue.length > 0) {
                    const curr = forwardQueue.shift();
                    connections.forEach((conn, idx) => {
                        if (conn.from === curr) {
                            activeEdgeIndices.add(idx);
                            activeNodes.add(conn.to);
                            if (!visitedForward.has(conn.to)) {
                                visitedForward.add(conn.to);
                                forwardQueue.push(conn.to);
                            }
                        }
                    });
                }

                return { activeNodes, activeEdgeIndices };
            }

            
            function updateFlowHighlights() {
                const activeTargetId = hoveredCardId || selectedNodeCardId;
                const isFocusActive = !!activeTargetId;
                const { activeNodes, activeEdgeIndices } = getConnectedFlowGraph(activeTargetId);

                connections.forEach((conn, index) => {
                    const visiblePath = document.getElementById(`path-dynamic-${index}`);
                    if (!visiblePath) return;

                    const isPathActive = isFocusActive && activeEdgeIndices.has(index);
                    if (isPathActive) {
                        visiblePath.classList.remove('dimmed');
                        visiblePath.classList.add('active');
                        const color = getNodeThemeColor(conn.from);
                        visiblePath.style.setProperty('--active-color', color);
                    } else if (isFocusActive) {
                        visiblePath.classList.remove('active');
                        visiblePath.classList.add('dimmed');
                    } else {
                        visiblePath.classList.remove('active');
                        visiblePath.classList.remove('dimmed');
                    }
                });

                document.querySelectorAll('.node-card, .agent-card').forEach(card => {
                    if (isFocusActive && activeNodes.has(card.id) && card.id !== selectedNodeCardId) {
                        card.classList.add('pipeline-active');
                    } else {
                        card.classList.remove('pipeline-active');
                    }
                });
            }

            function drawLines() {
                const canvas = document.getElementById('svg-canvas');
                if (!canvas) return;
                const rectCanvas = canvas.getBoundingClientRect();

                canvas.innerHTML = '';

                // Pre-count number of connections per port for multi-lane spacing
                const outPortCounts = {};
                const inPortCounts = {};
                connections.forEach(conn => {
                    const outKey = `${conn.from}-${conn.fromPort}`;
                    const inKey = `${conn.to}-${conn.toPort}`;
                    outPortCounts[outKey] = (outPortCounts[outKey] || 0) + 1;
                    inPortCounts[inKey] = (inPortCounts[inKey] || 0) + 1;
                });

                const outPortIndices = {};
                const inPortIndices = {};

                connections.forEach((conn, index) => {
                    const cardA = document.getElementById(conn.from);
                    const cardB = document.getElementById(conn.to);
                    if (!cardA || !cardB) return;

                    const rectA = cardA.getBoundingClientRect();
                    const rectB = cardB.getBoundingClientRect();

                    const outKey = `${conn.from}-${conn.fromPort}`;
                    const inKey = `${conn.to}-${conn.toPort}`;

                    const outIdx = outPortIndices[outKey] || 0;
                    outPortIndices[outKey] = outIdx + 1;

                    const inIdx = inPortIndices[inKey] || 0;
                    inPortIndices[inKey] = inIdx + 1;

                    let startPt = getPortCoordinates(rectA, conn.fromPort, rectCanvas, outIdx, outPortCounts[outKey]);
                    let endPt = getPortCoordinates(rectB, conn.toPort, rectCanvas, inIdx, inPortCounts[inKey]);

                    // Fallback to dynamic closest points if no ports defined (migration compatibility)
                    if (!startPt || !endPt) {
                        const bestConn = getBestConnectionPoints(rectA, rectB, rectCanvas);
                        startPt = startPt || bestConn.start;
                        endPt = endPt || bestConn.end;
                    }

                    const hasReverseConnection = connections.some(other =>
                        other.from === conn.to && other.to === conn.from
                    );
                    if (hasReverseConnection) {
                        const laneOffset = conn.from < conn.to ? -12 : 12;
                        startPt = offsetBidirectionalPoint(startPt, laneOffset);
                        endPt = offsetBidirectionalPoint(endPt, laneOffset);
                    }

                    // Create SVG Group <g class="edge-group">
                    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
                    group.setAttribute('class', 'edge-group');

                    // 1. Create invisible hover bridge path
                    const bridgePath = document.createElementNS("http://www.w3.org/2000/svg", "path");
                    const bridgeId = `path-bridge-${index}`;
                    bridgePath.setAttribute('id', bridgeId);
                    bridgePath.setAttribute('class', 'flow-path-hover-bridge');

                    // 2. Create visible path
                    const visiblePath = document.createElementNS("http://www.w3.org/2000/svg", "path");
                    const visibleId = `path-dynamic-${index}`;
                    visiblePath.setAttribute('id', visibleId);
                    visiblePath.setAttribute('class', 'flow-path');

                    // 3. Create delete button group (x) with expanded hit area
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
                    delBtnGroup.appendChild(text);

                    // Add elements to group
                    group.appendChild(bridgePath);
                    group.appendChild(visiblePath);
                    group.appendChild(delBtnGroup);

                    // Append group to canvas
                    canvas.appendChild(group);

                    // Draw paths and retrieve midpoint directly
                    const midPoint = drawCurvedPath(visibleId, startPt, endPt);
                    drawCurvedPath(bridgeId, startPt, endPt);

                    if (midPoint) {
                        delBtnGroup.setAttribute('transform', `translate(${midPoint.x}, ${midPoint.y})`);
                    }

                    // Click and mousedown event listeners to delete reliably
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
                    delBtnGroup.addEventListener('click', handleClick);
                });

                // Update flow highlights for current active/hovered node
                updateFlowHighlights();
            }

            function getSelectedNodeType() {
                const selectedNode = document.querySelector('.node-card.selected, .agent-card.selected');
                if (!selectedNode) return null;
                return selectedNode.id.split('-').slice(1).join('-');
            }

            function getActiveThemeColorForType(type) {
                const panel = document.getElementById('side-panel');
                return panel.style.getPropertyValue('--active-theme-color') || 'var(--text-primary)';
            }

            // Selection logic with Toggle support
            function selectNode(type) {
                const panel = document.getElementById('side-panel');
                const cardMap = {
                    'mt5': { cardId: 'node-mt5', panelId: 'panel-mt5', color: 'var(--color-mt5)' },
                    'watcher': { cardId: 'node-watcher-trigger', panelId: 'panel-watcher', color: 'var(--color-watcher)' },
                    'watcher-trigger': { cardId: 'node-watcher-trigger', panelId: 'panel-watcher', color: 'var(--color-watcher)' },
                    'neon': { cardId: 'node-neondb-mapping', panelId: 'panel-neon', color: 'var(--color-neon)' },
                    'neondb-mapping': { cardId: 'node-neondb-mapping', panelId: 'panel-neon', color: 'var(--color-neon)' },
                    'lancedb': { cardId: 'node-lancedb', panelId: 'panel-lancedb', color: 'var(--color-lancedb)' },
                    'orchestrator': { cardId: 'node-orchestrator', panelId: 'panel-orchestrator', color: 'var(--color-orchestrator)' },
                    'ms-agent': { cardId: 'node-ms-agent', panelId: 'panel-ms-agent', color: 'var(--color-watcher)' },
                    'ms-sub1': { cardId: 'node-ms-sub1', panelId: 'panel-ms-agent', color: 'var(--color-watcher)' },
                    'ms-sub2': { cardId: 'node-ms-sub2', panelId: 'panel-ms-agent', color: 'var(--color-lancedb)' },
                    'msa-to-ml-info': { cardId: 'node-msa-to-ml-info', panelId: 'panel-msa-to-ml-info', color: '#ffaa00' },
                    'msa-to-sent-info': { cardId: 'node-msa-to-sent-info', panelId: 'panel-msa-to-sent-info', color: '#ffaa00' },
                    'ml-agent': { cardId: 'node-ml-agent', panelId: 'panel-ml-agent', color: 'var(--color-lancedb)' },
                    'ml-sub1': { cardId: 'node-ml-sub1', panelId: 'panel-ml-sub1', color: 'var(--color-lancedb)' },
                    'ml-sub2': { cardId: 'node-ml-sub2', panelId: 'panel-ml-sub2', color: 'var(--color-lancedb)' },
                    'ml-sub3': { cardId: 'node-ml-sub3', panelId: 'panel-ml-sub3', color: 'var(--color-lancedb)' },
                    'ml-sub4': { cardId: 'node-ml-sub4', panelId: 'panel-ml-sub4', color: 'var(--color-lancedb)' },
                    'ml-sub5': { cardId: 'node-ml-sub5', panelId: 'panel-ml-sub5', color: 'var(--color-lancedb)' },
                    'risk-agent': { cardId: 'node-risk-agent', panelId: 'panel-risk-agent', color: 'var(--color-neon)' },
                    'risk-sub1': { cardId: 'node-risk-sub1', panelId: 'panel-risk-sub1', color: 'var(--color-neon)' },
                    'risk-sub2': { cardId: 'node-risk-sub2', panelId: 'panel-risk-sub2', color: 'var(--color-neon)' },
                    'risk-sub3': { cardId: 'node-risk-sub3', panelId: 'panel-risk-sub3', color: 'var(--color-neon)' },
                    'risk-sub4': { cardId: 'node-risk-sub4', panelId: 'panel-risk-sub4', color: 'var(--color-neon)' },
                    'risk-sub5': { cardId: 'node-risk-sub5', panelId: 'panel-risk-sub5', color: 'var(--color-neon)' },
                    'sentiment-agent': { cardId: 'node-sentiment-agent', panelId: 'panel-sentiment-agent', color: '#ff4081' },
                    'sent-sub1': { cardId: 'node-sent-sub1', panelId: 'panel-sent-sub1', color: '#ff4081' },
                    'sent-sub2': { cardId: 'node-sent-sub2', panelId: 'panel-sent-sub2', color: '#ff4081' },
                    'sent-sub3': { cardId: 'node-sent-sub3', panelId: 'panel-sent-sub3', color: '#ff4081' },
                    'sent-sub4': { cardId: 'node-sent-sub4', panelId: 'panel-sent-sub4', color: '#ff4081' },
                    'sent-sub5': { cardId: 'node-sent-sub5', panelId: 'panel-sent-sub5', color: '#ff4081' },
                    'consensus': { cardId: 'node-consensus', panelId: 'panel-consensus', color: 'var(--color-consensus)' },
                    'con-sub1': { cardId: 'node-con-sub1', panelId: 'panel-con-sub1', color: 'var(--color-consensus)' },
                    'con-sub2': { cardId: 'node-con-sub2', panelId: 'panel-con-sub2', color: 'var(--color-consensus)' },
                    'con-sub3': { cardId: 'node-con-sub3', panelId: 'panel-con-sub3', color: 'var(--color-consensus)' },
                    'con-step1': { cardId: 'node-con-step1', panelId: 'panel-con-step1', color: 'var(--color-consensus)' },
                    'con-step2': { cardId: 'node-con-step2', panelId: 'panel-con-step2', color: 'var(--color-consensus)' },
                    'con-step3': { cardId: 'node-con-step3', panelId: 'panel-con-step3', color: 'var(--color-consensus)' },
                    'con-step4': { cardId: 'node-con-step4', panelId: 'panel-con-step4', color: 'var(--color-consensus)' },
                    'con-step5': { cardId: 'node-con-step5', panelId: 'panel-con-step5', color: 'var(--color-consensus)' },
                    'execution': { cardId: 'node-execution', panelId: 'panel-execution', color: 'var(--color-execution)' }
                };

                const config = cardMap[type];
                if (!config) {
                    closeSidePanel();
                    return;
                }

                // Toggle logic: If this exact card is already selected and panel is open -> Close it!
                if (selectedNodeCardId === config.cardId && panel && panel.classList.contains('open')) {
                    closeSidePanel();
                    return;
                }

                // Otherwise, select and open this node
                document.querySelectorAll('.node-card, .agent-card').forEach(card => card.classList.remove('selected'));
                document.querySelectorAll('.panel-content').forEach(p => p.classList.remove('active'));

                const placeholder = document.getElementById('panel-placeholder');
                if (placeholder) placeholder.style.display = 'none';

                const card = document.getElementById(config.cardId);
                const pnl = document.getElementById(config.panelId);
                if (card) card.classList.add('selected');
                if (pnl) pnl.classList.add('active');
                
                selectedNodeCardId = config.cardId;
                if (panel) {
                    panel.classList.add('open');
                    panel.style.setProperty('--active-theme-color', config.color);
                }

                updateFlowHighlights(); // Automatically updates forward path highlighting!
            }

            function closeSidePanel() {
                const panel = document.getElementById('side-panel');
                if (panel) panel.classList.remove('open');
                selectedNodeCardId = null;
                document.querySelectorAll('.node-card, .agent-card').forEach(card => card.classList.remove('selected'));
                updateFlowHighlights();
            }

            // Side Panel Resizer Logic
            const resizer = document.getElementById('panel-resize-handle');
            const sidePanel = document.getElementById('side-panel');
            if (resizer && sidePanel) {
                let startX = 0;
                let startWidth = 0;

                resizer.addEventListener('mousedown', (e) => {
                    startX = e.clientX;
                    startWidth = parseInt(document.defaultView.getComputedStyle(sidePanel).width, 10);
                    resizer.classList.add('resizing');

                    const onMouseMove = (moveEvent) => {
                        const dx = startX - moveEvent.clientX;
                        const newWidth = Math.max(320, Math.min(800, startWidth + dx));
                        sidePanel.style.width = `${newWidth}px`;
                    };

                    const onMouseUp = () => {
                        resizer.classList.remove('resizing');
                        window.removeEventListener('mousemove', onMouseMove);
                        window.removeEventListener('mouseup', onMouseUp);
                    };

                    window.addEventListener('mousemove', onMouseMove);
                    window.addEventListener('mouseup', onMouseUp);
                    e.preventDefault();
                });
            }
        
            // Persistent State Management
            function getCurrentLayoutState() {
                const state = {
                    version: LAYOUT_VERSION,
                    pan: { x: panX, y: panY },
                    zoom: zoomScale,
                    nodes: {},
                    connections: connections
                };
                document.querySelectorAll('.node-card, .agent-card').forEach(card => {
                    state.nodes[card.id] = {
                        dx: parseFloat(card.getAttribute('data-dx') || '0'),
                        dy: parseFloat(card.getAttribute('data-dy') || '0')
                    };
                });
                return state;
            }

            // Persistent State Management & Real-Time Auto-Save
            let saveDebounceTimer = null;
            function saveLayoutState(silent = true) {
                const state = getCurrentLayoutState();
                localStorage.setItem('mt5_diagram_layout', JSON.stringify(state));

                // Auto-save directly to server / disk in background
                clearTimeout(saveDebounceTimer);
                saveDebounceTimer = setTimeout(() => {
                    fetch('/api/layout', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(state)
                    }).then(res => {
                        if (res.ok && !silent) {
                            showToast('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: #00e676;"><polyline points="20 6 9 17 4 12"></polyline></svg> <span>Tersimpan otomatis ke file & server!</span>');
                        }
                    }).catch(() => {
                        // Offline or direct file load fallback
                    });
                }, 300);
            }

            function applyLayoutState(state) {
                if (!state) return;

                // 1. Apply node coordinates first with immediate transition suppression
                if (state.nodes) {
                    for (let id in state.nodes) {
                        const card = document.getElementById(id);
                        if (card) {
                            const dx = state.nodes[id].dx || 0;
                            const dy = state.nodes[id].dy || 0;
                            card.setAttribute('data-dx', dx);
                            card.setAttribute('data-dy', dy);
                            card.style.transition = 'none';
                            card.style.transform = `translate(${dx}px, ${dy}px)`;
                        }
                    }
                }

                // 2. Apply Pan & Zoom state to viewport
                if (state.pan) {
                    panX = state.pan.x;
                    panY = state.pan.y;
                }
                if (typeof state.zoom === 'number' && !isNaN(state.zoom)) {
                    zoomScale = Math.min(Math.max(state.zoom, MIN_ZOOM), MAX_ZOOM);
                }
                const panContainer = document.getElementById('pan-container');
                if (panContainer) {
                    panContainer.style.transform = `translate(${panX}px, ${panY}px) scale(${zoomScale})`;
                }
                const badge = document.getElementById('zoom-level-badge');
                if (badge) {
                    badge.textContent = `${Math.round(zoomScale * 100)}%`;
                }

                // 3. Apply connections
                if (state.connections && Array.isArray(state.connections)) {
                    connections = state.connections;
                } else {
                    connections = [...defaultConnections];
                }

                // 4. Force synchronous recalculation and double-frame line drawing
                drawLines();
                requestAnimationFrame(() => {
                    drawLines();
                });
            }

            async function restoreLayoutState() {
                // 1. Try to fetch saved layout from dev server first
                try {
                    const resp = await fetch('/api/layout');
                    if (resp.ok) {
                        const serverState = await resp.json();
                        if (serverState && serverState.nodes && Object.keys(serverState.nodes).length > 0) {
                            applyLayoutState(serverState);
                            localStorage.setItem('mt5_diagram_layout', JSON.stringify(serverState));
                            return;
                        }
                    }
                } catch (e) {
                    console.log("Server layout fetch skipped, checking local storage...");
                }

                // 2. Fallback to localStorage
                const savedStateStr = localStorage.getItem('mt5_diagram_layout');
                if (savedStateStr) {
                    try {
                        const state = JSON.parse(savedStateStr);
                        applyLayoutState(state);
                        return;
                    } catch (e) {
                        console.error("Failed to restore from localStorage", e);
                    }
                }

                // 3. Fallback to baked-in default layout if available
                if (typeof defaultLayoutState !== 'undefined' && defaultLayoutState && defaultLayoutState.nodes && Object.keys(defaultLayoutState.nodes).length > 0) {
                    applyLayoutState(defaultLayoutState);
                } else {
                    connections = [...defaultConnections];
                    updateTransform();
                }
            }

            function resetLayout() {
                localStorage.removeItem('mt5_diagram_layout');
                if (typeof defaultLayoutState !== 'undefined' && defaultLayoutState && defaultLayoutState.nodes && Object.keys(defaultLayoutState.nodes).length > 0) {
                    applyLayoutState(defaultLayoutState);
                } else {
                    panX = 0;
                    panY = 0;
                    zoomScale = 1.0;
                    updateTransform();
                    document.querySelectorAll('.node-card, .agent-card').forEach(card => {
                        card.setAttribute('data-dx', '0');
                        card.setAttribute('data-dy', '0');
                        card.style.transform = 'translate(0px, 0px)';
                    });
                    connections = [...defaultConnections];
                    drawLines();
                }
                saveLayoutState(true);
                clearConnectionSelection();
                closeSidePanel();
                hideDeletePopup();
                showToast('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: #00e5ff;"><polyline points="1 4 1 10 7 10"></polyline><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path></svg> <span>Tata letak dikembalikan ke default.</span>');
            }

            function deleteAllArrows() {
                if (!confirm('Hapus semua panah koneksi?')) return;
                connections = [];
                saveLayoutState();
                drawLines();
                showToast('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: #ff1744;"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg> <span>Semua panah berhasil dihapus.</span>');
            }

            // Dropdown Menu Helpers
            function toggleHeaderMenu(e) {
                if (e) e.stopPropagation();
                const wrapper = document.getElementById('hdr-dropdown-wrapper');
                if (wrapper) wrapper.classList.toggle('open');
            }

            function closeHeaderMenu() {
                const wrapper = document.getElementById('hdr-dropdown-wrapper');
                if (wrapper) wrapper.classList.remove('open');
            }

            // Toast UI Notification
            function showToast(message, isError = false) {
                let container = document.getElementById('toast-container');
                if (!container) {
                    container = document.createElement('div');
                    container.id = 'toast-container';
                    container.className = 'toast-container';
                    document.body.appendChild(container);
                }
                const toast = document.createElement('div');
                toast.className = 'toast-pill';
                if (isError) {
                    toast.style.borderColor = 'rgba(255, 23, 68, 0.6)';
                }
                toast.innerHTML = message;
                container.appendChild(toast);
                setTimeout(() => {
                    toast.style.opacity = '0';
                    toast.style.transition = 'opacity 0.3s ease';
                    setTimeout(() => toast.remove(), 300);
                }, 3000);
            }

            // Clean Baked HTML Generator (No DOM dump / No extension clutter)
            async function generateBakedHtml(state) {
                let html = "";
                try {
                    const resp = await fetch(window.location.href);
                    html = await resp.text();
                } catch (e) {
                    html = document.documentElement.outerHTML;
                }

                // Clean any browser extension scripts or live-server scripts
                html = html.replace(/<!-- Code injected by live-server -->[\s\S]*?<\/script>/gi, '');
                html = html.replace(/<div id="voila-extension-app"[\s\S]*?<\/div><\/div>/gi, '');
                html = html.replace(/<div id="huntr-react-container-[^"]*"[\s\S]*?<\/div>/gi, '');

                // Update defaultLayoutState object inside script
                const stateJson = JSON.stringify(state, null, 4);
                html = html.replace(/const defaultLayoutState = [\s\S]*?};/, `const defaultLayoutState = ${stateJson};`);

                // Update node attributes in HTML markup
                if (state.nodes) {
                    for (let id in state.nodes) {
                        const dx = state.nodes[id].dx;
                        const dy = state.nodes[id].dy;
                        const regex = new RegExp(`(id="${id}"[^>]*)>`, 'g');
                        html = html.replace(regex, (match, prefix) => {
                            let clean = prefix.replace(/\s*data-dx="[^"]*"/g, '');
                            clean = clean.replace(/\s*data-dy="[^"]*"/g, '');
                            clean = clean.replace(/\s*style="[^"]*"/g, '');
                            return `${clean} data-dx="${dx}" data-dy="${dy}" style="transform: translate(${dx}px, ${dy}px);">`;
                        });
                    }
                }

                // Remove dynamic port handles from saved markup
                html = html.replace(/<div class="port-handle [^"]*"[^>]*>\+<\/div>/gi, '');

                return html;
            }

            async function saveDirectlyToFile() {
                saveLayoutState(false);
                const state = getCurrentLayoutState();

                // If running on dev server, it's saved directly to disk automatically!
                try {
                    const testResp = await fetch('/api/layout', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(state)
                    });
                    if (testResp.ok) {
                        showToast('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: #00e676;"><polyline points="20 6 9 17 4 12"></polyline></svg> <span>Tersimpan permanen ke disk!</span>');
                        return;
                    }
                } catch (e) {
                    // Fallback to file picker or download if offline/standalone file
                }

                const cleanHtml = await generateBakedHtml(state);

                if ('showSaveFilePicker' in window) {
                    try {
                        const handle = await window.showSaveFilePicker({
                            suggestedName: 'diagram_arsitektur.html',
                            types: [{
                                description: 'HTML Document',
                                accept: { 'text/html': ['.html'] }
                            }]
                        });
                        const writable = await handle.createWritable();
                        await writable.write(cleanHtml);
                        await writable.close();
                        showToast('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: #00e676;"><polyline points="20 6 9 17 4 12"></polyline></svg> <span>Tersimpan permanen ke file!</span>');
                        return;
                    } catch (err) {
                        if (err.name === 'AbortError') return;
                        console.warn("File picker failed, fallback to download:", err);
                    }
                }

                // Fallback to auto download
                downloadCurrentHtml();
            }

            async function downloadCurrentHtml() {
                saveLayoutState();
                const state = getCurrentLayoutState();
                const cleanHtml = await generateBakedHtml(state);

                const blob = new Blob([cleanHtml], { type: 'text/html;charset=utf-8' });
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = 'diagram_arsitektur.html';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(a.href);
                showToast('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: #00e5ff;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> <span>File HTML berhasil diunduh.</span>');
            }

            function exportLayoutJson() {
                saveLayoutState();
                const state = getCurrentLayoutState();
                const jsonStr = JSON.stringify(state, null, 2);
                navigator.clipboard.writeText(jsonStr).then(() => {
                    showToast('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: #00e676;"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> <span>JSON posisi berhasil disalin ke clipboard!</span>');
                }).catch(err => {
                    console.error("Failed to copy JSON:", err);
                    prompt("Salin JSON berikut:", jsonStr);
                });
            }

            function triggerImportJson() {
                const input = document.getElementById('json-file-input');
                if (input) input.click();
            }

            function handleJsonFile(event) {
                const file = event.target.files[0];
                if (!file) return;
                const reader = new FileReader();
                reader.onload = (e) => {
                    try {
                        const state = JSON.parse(e.target.result);
                        applyLayoutState(state);
                        saveLayoutState();
                        showToast('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: #00e676;"><polyline points="20 6 9 17 4 12"></polyline></svg> <span>Tata letak JSON berhasil dimuat!</span>');
                    } catch (err) {
                        alert("File JSON tidak valid: " + err.message);
                    }
                };
                reader.readAsText(file);
                event.target.value = '';
            }

        