import re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update findCollisionFreeRoute and drawCurvedPath with Staggered Multi-Lane Stub Routing
new_routing_functions = """            function movePointOutward(point, distance) {
                if (!point) return { x: 0, y: 0 };
                if (point.dir === 'up' || point.dir === 'top') return { x: point.x, y: point.y - distance };
                if (point.dir === 'down' || point.dir === 'bottom') return { x: point.x, y: point.y + distance };
                if (point.dir === 'left') return { x: point.x - distance, y: point.y };
                return { x: point.x + distance, y: point.y };
            }

            function segmentHitsRect(a, b, rect) {
                if (a.x === b.x) {
                    return a.x > rect.left && a.x < rect.right &&
                        Math.max(a.y, b.y) > rect.top && Math.min(a.y, b.y) < rect.bottom;
                }
                if (a.y === b.y) {
                    return a.y > rect.top && a.y < rect.bottom &&
                        Math.max(a.x, b.x) > rect.left && Math.min(a.x, b.x) < rect.right;
                }
                return true;
            }

            function simplifyRoute(points) {
                const unique = points.filter((point, index) => index === 0 || point.x !== points[index - 1].x || point.y !== points[index - 1].y);
                return unique.filter((point, index) => {
                    if (index === 0 || index === unique.length - 1) return true;
                    const previous = unique[index - 1];
                    const next = unique[index + 1];
                    return !((previous.x === point.x && point.x === next.x) || (previous.y === point.y && point.y === next.y));
                });
            }

            function routeIsClear(points, obstacles) {
                for (let index = 1; index < points.length; index++) {
                    if (obstacles.some(rect => segmentHitsRect(points[index - 1], points[index], rect))) return false;
                }
                return true;
            }

            function routeLength(points) {
                let length = 0;
                for (let index = 1; index < points.length; index++) {
                    length += Math.abs(points[index].x - points[index - 1].x) + Math.abs(points[index].y - points[index - 1].y);
                }
                return length;
            }

            function routeTrackPenalty(points, usedTracks) {
                const trackSpacing = 16;
                let penalty = 0;
                for (let index = 1; index < points.length; index++) {
                    const a = points[index - 1];
                    const b = points[index];
                    if (a.x === b.x && usedTracks.x.some(x => Math.abs(x - a.x) < trackSpacing)) penalty += 50000;
                    if (a.y === b.y && usedTracks.y.some(y => Math.abs(y - a.y) < trackSpacing)) penalty += 50000;
                }
                return penalty;
            }

            function findCollisionFreeRoute(start, end, obstacles, usedTracks = { x: [], y: [] }, startStubDist = 24, endStubDist = 24) {
                const startStub = movePointOutward(start, startStubDist);
                const endStub = movePointOutward(end, endStubDist);
                const candidates = [
                    [start, startStub, { x: endStub.x, y: startStub.y }, endStub, end],
                    [start, startStub, { x: startStub.x, y: endStub.y }, endStub, end]
                ];

                const xTracks = new Set([startStub.x, endStub.x]);
                const yTracks = new Set([startStub.y, endStub.y]);
                obstacles.forEach(rect => {
                    xTracks.add(rect.left - 18);
                    xTracks.add(rect.right + 18);
                    yTracks.add(rect.top - 18);
                    yTracks.add(rect.bottom + 18);
                });

                // Nudge tracks that a previously drawn line already occupies so parallel lines never stack.
                const trackSpacing = 16;
                const nudgeTrack = (value, used) => {
                    let adjusted = value;
                    let guard = 0;
                    while (used.some(u => Math.abs(u - adjusted) < trackSpacing) && guard < 40) {
                        adjusted += trackSpacing;
                        guard++;
                    }
                    return adjusted;
                };

                xTracks.forEach(rawX => {
                    const x = nudgeTrack(rawX, usedTracks.x);
                    candidates.push([
                        start, startStub,
                        { x, y: startStub.y },
                        { x, y: endStub.y },
                        endStub, end
                    ]);
                });
                yTracks.forEach(rawY => {
                    const y = nudgeTrack(rawY, usedTracks.y);
                    candidates.push([
                        start, startStub,
                        { x: startStub.x, y },
                        { x: endStub.x, y },
                        endStub, end
                    ]);
                });

                const clearRoutes = candidates
                    .map(simplifyRoute)
                    .filter(points => routeIsClear(points, obstacles))
                    .sort((a, b) => (routeLength(a) + routeTrackPenalty(a, usedTracks)) - (routeLength(b) + routeTrackPenalty(b, usedTracks)));

                if (clearRoutes.length > 0) return clearRoutes[0];

                const outerX = Math.min(start.x, end.x, ...obstacles.map(rect => rect.left)) - 40;
                return simplifyRoute([
                    start, startStub,
                    { x: outerX, y: startStub.y },
                    { x: outerX, y: endStub.y },
                    endStub, end
                ]);
            }

            function collectRouteTracks(points, tracks) {
                for (let index = 1; index < points.length; index++) {
                    const a = points[index - 1];
                    const b = points[index];
                    if (a.x === b.x) tracks.x.push(a.x);
                    if (a.y === b.y) tracks.y.push(a.y);
                }
            }

            function drawCurvedPath(id, ptA, ptB, obstacles = [], usedTracks = { x: [], y: [] }, startStubDist = 24, endStubDist = 24) {
                const path = document.getElementById(id);
                if (!path) return null;
                const start = ptA;
                const end = ptB;
                const points = findCollisionFreeRoute(start, end, obstacles, usedTracks, startStubDist, endStubDist);
                const d = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');

                path.setAttribute('d', d);
                collectRouteTracks(points, usedTracks);

                // Calculate exact geometric midpoint along the actual SVG curved path
                let midPoint = { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };
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
            }"""

html = re.sub(
    r'function movePointOutward\(point, distance\) \{[\s\S]*?function drawCurvedPath\(id, ptA, ptB, obstacles = \[\], usedTracks = \{ x: \[\], y: \[\] \}\) \{[\s\S]*?return midPoint;\s*\}',
    new_routing_functions,
    html
)

# 2. Update drawLines to pass staggered stubs and accurate port counting
new_draw_lines = """            function drawLines() {
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
                    const startStubDist = 24 + (outIdx * 18);
                    const endStubDist = 24 + (inIdx * 18);

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

                    // Delete action with confirmation popup
                    delBtnGroup.onclick = (e) => {
                        e.stopPropagation();
                        showDeletePopup(e.clientX, e.clientY, conn.from, conn.to);
                    };

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
                });
            }"""

html = re.sub(
    r'function drawLines\(\) \{[\s\S]*?delBtnGroup\.setAttribute\(\'transform\', `translate\(\$\{mid\.x\}, \$\{mid\.y\}\)`\);\s*\}\s*\}\);\s*\}',
    new_draw_lines,
    html
)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Staggered Multi-Lane Routing engine installed successfully!")
