import re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

flawless_draw_lines = """            function drawLines() {
                const canvas = document.getElementById('svg-canvas');
                if (!canvas) return;
                const rectCanvas = canvas.getBoundingClientRect();

                canvas.innerHTML = '';

                // Pre-count number of connections per port for multi-lane spacing
                const outPortCounts = {};
                const inPortCounts = {};
                connections.forEach(conn => {
                    const outKey = `${conn.from}-${conn.fromPort || 'auto'}`;
                    const inKey = `${conn.to}-${conn.toPort || 'auto'}`;
                    outPortCounts[outKey] = (outPortCounts[outKey] || 0) + 1;
                    inPortCounts[inKey] = (inPortCounts[inKey] || 0) + 1;
                });

                const outPortIndices = {};
                const inPortIndices = {};

                // Shared lane memory: every drawn line registers its tracks so later lines shift aside.
                const usedTracks = { x: [], y: [] };

                connections.forEach((conn, index) => {
                    const cardA = document.getElementById(conn.from);
                    const cardB = document.getElementById(conn.to);
                    if (!cardA || !cardB) return;

                    const rectA = cardA.getBoundingClientRect();
                    const rectB = cardB.getBoundingClientRect();

                    const outKey = `${conn.from}-${conn.fromPort || 'auto'}`;
                    const inKey = `${conn.to}-${conn.toPort || 'auto'}`;

                    const outIdx = outPortIndices[outKey] || 0;
                    outPortIndices[outKey] = outIdx + 1;

                    const inIdx = inPortIndices[inKey] || 0;
                    inPortIndices[inKey] = inIdx + 1;

                    const totalOut = outPortCounts[outKey] || 1;
                    const totalIn = inPortCounts[inKey] || 1;

                    let startPt = getPortCoordinates(rectA, conn.fromPort, rectCanvas, outIdx, totalOut);
                    let endPt = getPortCoordinates(rectB, conn.toPort, rectCanvas, inIdx, totalIn);

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
                        const laneOffset = conn.from < conn.to ? -14 : 14;
                        startPt = offsetBidirectionalPoint(startPt, laneOffset);
                        endPt = offsetBidirectionalPoint(endPt, laneOffset);
                    }

                    // Staggered departure and arrival stubs so parallel or branch lines never overlap!
                    const startStubDist = 24 + (outIdx * 20);
                    const endStubDist = 24 + (inIdx * 20);

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
                    text.setAttribute('text-anchor', 'middle');
                    text.setAttribute('dominant-baseline', 'central');

                    delBtnGroup.appendChild(hitArea);
                    delBtnGroup.appendChild(circle);
                    delBtnGroup.appendChild(text);

                    group.appendChild(bridgePath);
                    group.appendChild(visiblePath);
                    group.appendChild(delBtnGroup);
                    canvas.appendChild(group);

                    // Color theme for connection
                    const color = getNodeThemeColor(conn.from);
                    visiblePath.style.stroke = color;
                    visiblePath.style.filter = `drop-shadow(0 0 6px ${color})`;

                    // Draw collision-free orthogonal path with separate lanes and staggered stubs
                    const obstacles = getObstacleRects(rectCanvas, new Set([conn.from, conn.to]));
                    drawCurvedPath(bridgeId, startPt, endPt, obstacles, { x: [], y: [] }, startStubDist, endStubDist);
                    const mid = drawCurvedPath(visibleId, startPt, endPt, obstacles, usedTracks, startStubDist, endStubDist);

                    if (mid && mid.x && mid.y) {
                        delBtnGroup.setAttribute('transform', `translate(${mid.x}, ${mid.y})`);
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
            }"""

pattern = r'function drawLines\(\) \{[\s\S]*?updateFlowHighlights\(\);\s*\}'
html = re.sub(pattern, flawless_draw_lines, html)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Replacement successful!")
