import json
from pathlib import Path
import re

html_path = Path(r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html")
json_path = Path(r"b:\Project MT5\Other\Dokumen\diagram_layout.json")

# 1. Update diagram_layout.json
layout_data = json.loads(json_path.read_text(encoding="utf-8"))
layout_data["version"] = 15

# Update connections in layout_data
updated_conns = []
for conn in layout_data["connections"]:
    # Market Structure sub-connections refinement
    if conn["from"] == "node-ms-sub1" and conn["to"] == "node-ms-sub2":
        conn["fromPort"] = "left"
        conn["toPort"] = "top"
    elif conn["from"] == "node-ms-sub2" and conn["to"] == "node-ms-sub3":
        conn["fromPort"] = "bottom"
        conn["toPort"] = "left"
    elif conn["from"] == "node-ms-sub3" and conn["to"] == "node-ms-sub4":
        conn["fromPort"] = "right"
        conn["toPort"] = "left"
    updated_conns.append(conn)

layout_data["connections"] = updated_conns
json_path.write_text(json.dumps(layout_data, indent=2), encoding="utf-8")
print("Updated diagram_layout.json to version 15!")

# 2. Update diagram_arsitektur.html
html_content = html_path.read_text(encoding="utf-8")

# Fix CSS z-index for .flow-line-svg
html_content = re.sub(
    r'(\.flow-line-svg\s*\{[^}]*?z-index:\s*)\d+;',
    r'\g<1>2;',
    html_content
)

# Smart Port Resolver function & improved collision-free routing
smart_port_js = """
            // Resolve flexible port based on spatial geometry & relative card positions
            function resolveSmartPort(conn, rectA, rectB) {
                let fromPort = conn.fromPort;
                let toPort = conn.toPort;

                const cAx = rectA.left + rectA.width / 2;
                const cAy = rectA.top + rectA.height / 2;
                const cBx = rectB.left + rectB.width / 2;
                const cBy = rectB.top + rectB.height / 2;
                const dx = cBx - cAx;
                const dy = cBy - cAy;

                // Check if configured ports are physically backwards or awkward
                let isConflicted = false;
                if (fromPort === 'bottom' && dy < -50) isConflicted = true;
                if (fromPort === 'top' && dy > 50) isConflicted = true;
                if (fromPort === 'right' && dx < -50) isConflicted = true;
                if (fromPort === 'left' && dx > 50) isConflicted = true;

                if (toPort === 'top' && dy < -50) isConflicted = true;
                if (toPort === 'bottom' && dy > 50) isConflicted = true;
                if (toPort === 'left' && dx < -50) isConflicted = true;
                if (toPort === 'right' && dx > 50) isConflicted = true;

                if (!fromPort || !toPort || fromPort === 'auto' || toPort === 'auto' || isConflicted) {
                    if (Math.abs(dx) >= Math.abs(dy) * 0.8) {
                        // Predominantly horizontal
                        fromPort = dx > 0 ? 'right' : 'left';
                        toPort = dx > 0 ? 'left' : 'right';
                    } else {
                        // Predominantly vertical
                        fromPort = dy > 0 ? 'bottom' : 'top';
                        toPort = dy > 0 ? 'top' : 'bottom';
                    }
                }

                return { fromPort, toPort };
            }
"""

# Replace in drawLines where ports are extracted
old_drawlines_ports = """                    let startPt = getPortCoordinates(rectA, conn.fromPort, rectCanvas, fromIdx, totalFrom);
                    let endPt = getPortCoordinates(rectB, conn.toPort, rectCanvas, toIdx, totalTo);"""

new_drawlines_ports = """                    const resolvedPorts = resolveSmartPort(conn, rectA, rectB);
                    let startPt = getPortCoordinates(rectA, resolvedPorts.fromPort, rectCanvas, fromIdx, totalFrom);
                    let endPt = getPortCoordinates(rectB, resolvedPorts.toPort, rectCanvas, toIdx, totalTo);"""

if old_drawlines_ports in html_content:
    html_content = html_content.replace(old_drawlines_ports, new_drawlines_ports)
    print("Replaced drawLines port calculation with resolveSmartPort!")
else:
    print("WARNING: old_drawlines_ports not found directly, checking regex")

# Add resolveSmartPort function before drawLines if not present
if "function resolveSmartPort(" not in html_content:
    html_content = html_content.replace("function drawLines()", smart_port_js + "\n            function drawLines()")
    print("Added resolveSmartPort function!")

# Replace getObstacleRects and routeIsClear to prevent lines cutting across endpoints
old_route_is_clear = """            function routeIsClear(points, obstacles) {
                for (let index = 1; index < points.length; index++) {
                    if (obstacles.some(rect => segmentHitsRect(points[index - 1], points[index], rect))) return false;
                }
                return true;
            }"""

new_route_is_clear = """            function routeIsClear(points, obstacles, allCardObstacles = []) {
                for (let index = 1; index < points.length; index++) {
                    if (obstacles.some(rect => segmentHitsRect(points[index - 1], points[index], rect))) return false;
                }
                // Intermediate segments (between stubs) MUST NOT pass through any card
                if (allCardObstacles.length > 0 && points.length >= 4) {
                    for (let index = 2; index < points.length - 1; index++) {
                        if (allCardObstacles.some(rect => segmentHitsRect(points[index - 1], points[index], rect))) return false;
                    }
                }
                return true;
            }"""

if old_route_is_clear in html_content:
    html_content = html_content.replace(old_route_is_clear, new_route_is_clear)
    print("Replaced routeIsClear to strictly block intermediate segments cutting through cards!")

# Update findCollisionFreeRoute call to pass allCardObstacles
old_call_drawcurved = """                    const obstacles = getObstacleRects(rectCanvas, new Set([conn.from, conn.to]));
                    drawCurvedPath(bridgeId, startPt, endPt, obstacles, { x: [], y: [] }, startStubDist, endStubDist);
                    const mid = drawCurvedPath(visibleId, startPt, endPt, obstacles, usedTracks, startStubDist, endStubDist);"""

new_call_drawcurved = """                    const obstacles = getObstacleRects(rectCanvas, new Set([conn.from, conn.to]));
                    const allCardObstacles = getObstacleRects(rectCanvas, new Set());
                    drawCurvedPath(bridgeId, startPt, endPt, obstacles, { x: [], y: [] }, startStubDist, endStubDist, allCardObstacles);
                    const mid = drawCurvedPath(visibleId, startPt, endPt, obstacles, usedTracks, startStubDist, endStubDist, allCardObstacles);"""

if old_call_drawcurved in html_content:
    html_content = html_content.replace(old_call_drawcurved, new_call_drawcurved)
    print("Updated drawCurvedPath calls in drawLines!")

# Update drawCurvedPath signature
old_draw_curved_sig = "function drawCurvedPath(id, ptA, ptB, obstacles = [], usedTracks = { x: [], y: [] }, startStubDist = 24, endStubDist = 24) {"
new_draw_curved_sig = "function drawCurvedPath(id, ptA, ptB, obstacles = [], usedTracks = { x: [], y: [] }, startStubDist = 24, endStubDist = 24, allCardObstacles = []) {"

old_find_coll_sig = "function findCollisionFreeRoute(start, end, obstacles, usedTracks = { x: [], y: [] }, startStubDist = 24, endStubDist = 24) {"
new_find_coll_sig = "function findCollisionFreeRoute(start, end, obstacles, usedTracks = { x: [], y: [] }, startStubDist = 24, endStubDist = 24, allCardObstacles = []) {"

if old_draw_curved_sig in html_content:
    html_content = html_content.replace(old_draw_curved_sig, new_draw_curved_sig)
    html_content = html_content.replace("findCollisionFreeRoute(start, end, obstacles, usedTracks, startStubDist, endStubDist)", "findCollisionFreeRoute(start, end, obstacles, usedTracks, startStubDist, endStubDist, allCardObstacles)")
    print("Updated drawCurvedPath signature and call!")

if old_find_coll_sig in html_content:
    html_content = html_content.replace(old_find_coll_sig, new_find_coll_sig)
    html_content = html_content.replace(".filter(points => routeIsClear(points, obstacles))", ".filter(points => routeIsClear(points, obstacles, allCardObstacles))")
    print("Updated findCollisionFreeRoute signature and filter!")

# Also sync defaultConnections, LAYOUT_VERSION = 15, and defaultLayoutState
# Re-run fix_diagram_connections logic for v15
marker_conns = "const defaultConnections ="
pos_conns = html_content.find(marker_conns)
pos_layout_state = html_content.find("const defaultLayoutState =")
pos_after_layout_state = html_content.find("};", pos_layout_state) + 2

conns_json = json.dumps(layout_data["connections"], indent=16)
state_json = json.dumps(layout_data, indent=4)

new_middle_js = f"""const defaultConnections = {conns_json};

            let connections = [...defaultConnections];
            const LAYOUT_VERSION = 15; // ponytail: bump when defaultConnections change

            // Baked-in Default Layout State (Used when localStorage is empty or on different browser)
            const defaultLayoutState = {state_json};"""

html_content = html_content[:pos_conns] + new_middle_js + html_content[pos_after_layout_state:]
html_path.write_text(html_content, encoding="utf-8")
print("Saved diagram_arsitektur.html successfully with v15 and smart flexible routing!")
