import re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update getPortCoordinates to use 24px spread for crisp distinct lanes
new_get_port = """            function getPortCoordinates(rect, portName, rectCanvas, offsetIndex = 0, totalOnPort = 1) {
                if (!portName) return null;
                const spread = 24; // clean multi-lane lane spacing (px)
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
            }"""

html = re.sub(
    r'function getPortCoordinates\(rect, portName, rectCanvas, offsetIndex = 0, totalOnPort = 1\) \{[\s\S]*?default:\s*return null;\s*\}\s*\}',
    new_get_port,
    html
)

# 2. Update drawLines with Unified Physical Port Counting (In + Out combined)
new_draw_lines = """            function drawLines() {
                const canvas = document.getElementById('svg-canvas');
                if (!canvas) return;
                const rectCanvas = canvas.getBoundingClientRect();

                canvas.innerHTML = '';

                // Unified physical port connection counting (combines incoming + outgoing lines on the same port)
                const physicalPortCounts = {};
                connections.forEach(conn => {
                    const fromKey = `${conn.from}-${conn.fromPort || 'auto'}`;
                    const toKey = `${conn.to}-${conn.toPort || 'auto'}`;
                    physicalPortCounts[fromKey] = (physicalPortCounts[fromKey] || 0) + 1;
                    physicalPortCounts[toKey] = (physicalPortCounts[toKey] || 0) + 1;
                });

                const physicalPortIndices = {};

                // Shared lane memory: every drawn line registers its tracks so later lines shift aside.
                const usedTracks = { x: [], y: [] };

                connections.forEach((conn, index) => {
                    const cardA = document.getElementById(conn.from);
                    const cardB = document.getElementById(conn.to);
                    if (!cardA || !cardB) return;

                    const rectA = cardA.getBoundingClientRect();
                    const rectB = cardB.getBoundingClientRect();

                    const fromKey = `${conn.from}-${conn.fromPort || 'auto'}`;
                    const toKey = `${conn.to}-${conn.toPort || 'auto'}`;

                    const fromIdx = physicalPortIndices[fromKey] || 0;
                    physicalPortIndices[fromKey] = fromIdx + 1;

                    const toIdx = physicalPortIndices[toKey] || 0;
                    physicalPortIndices[toKey] = toIdx + 1;

                    const totalFrom = physicalPortCounts[fromKey] || 1;
                    const totalTo = physicalPortCounts[toKey] || 1;

                    let startPt = getPortCoordinates(rectA, conn.fromPort, rectCanvas, fromIdx, totalFrom);
                    let endPt = getPortCoordinates(rectB, conn.toPort, rectCanvas, toIdx, totalTo);

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
                        const laneOffset = conn.from < conn.to ? -16 : 16;
                        startPt = offsetBidirectionalPoint(startPt, laneOffset);
                        endPt = offsetBidirectionalPoint(endPt, laneOffset);
                    }

                    // Staggered departure and arrival stubs so parallel or branch lines never overlap!
                    const startStubDist = 24 + (fromIdx * 24);
                    const endStubDist = 24 + (toIdx * 24);

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

html = re.sub(
    r'function drawLines\(\) \{[\s\S]*?updateFlowHighlights\(\);\s*\}',
    new_draw_lines,
    html
)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Unified Physical Port multi-lane separation installed successfully!")
