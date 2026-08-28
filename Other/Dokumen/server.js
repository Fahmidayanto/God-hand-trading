const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

const PORT = process.env.PORT || 8080;
const BASE_DIR = __dirname;
const LAYOUT_FILE = path.join(BASE_DIR, 'diagram_layout.json');
const HTML_FILE = path.join(BASE_DIR, 'diagram_arsitektur.html');

const MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.txt': 'text/plain; charset=utf-8'
};

let lastInternalWrite = 0;
const sseClients = new Set();

function broadcastReload() {
    console.log(`[Live-Reload] External file change detected -> notifying ${sseClients.size} client(s)...`);
    for (const client of sseClients) {
        try {
            client.write('data: reload\n\n');
        } catch (e) {
            sseClients.delete(client);
        }
    }
}

// Watch HTML file for external edits (IDE/AI)
let reloadDebounceTimer = null;
if (fs.existsSync(HTML_FILE)) {
    fs.watch(HTML_FILE, (eventType) => {
        // Ignore internal auto-saves triggered by browser drag/pan
        if (Date.now() - lastInternalWrite < 2000) {
            return;
        }
        if (reloadDebounceTimer) clearTimeout(reloadDebounceTimer);
        reloadDebounceTimer = setTimeout(() => {
            broadcastReload();
        }, 300);
    });
}

function updateHtmlBakedState(state) {
    try {
        if (!fs.existsSync(HTML_FILE)) return;
        lastInternalWrite = Date.now();
        let html = fs.readFileSync(HTML_FILE, 'utf8');
        const stateJson = JSON.stringify(state, null, 4);
        
        // Update defaultLayoutState constant in script
        html = html.replace(/const defaultLayoutState = [\s\S]*?};/, `const defaultLayoutState = ${stateJson};`);
        
        // Update node card data-dx, data-dy, data-w, data-h attributes
        if (state.nodes) {
            for (let id in state.nodes) {
                const node = state.nodes[id];
                const dx = node.dx || 0;
                const dy = node.dy || 0;
                const w = node.w;
                const h = node.h;
                let styleStr = `transform: translate(${dx}px, ${dy}px);`;
                let extraAttrs = `data-dx="${dx}" data-dy="${dy}"`;
                if (w) {
                    styleStr += ` width: ${w}px;`;
                    extraAttrs += ` data-w="${w}"`;
                }
                if (h) {
                    styleStr += ` height: ${h}px;`;
                    extraAttrs += ` data-h="${h}"`;
                }
                const regex = new RegExp(`(id="${id}"[^>]*)>`, 'g');
                html = html.replace(regex, (match, prefix) => {
                    let clean = prefix.replace(/\s*data-dx="[^"]*"/g, '');
                    clean = clean.replace(/\s*data-dy="[^"]*"/g, '');
                    clean = clean.replace(/\s*data-w="[^"]*"/g, '');
                    clean = clean.replace(/\s*data-h="[^"]*"/g, '');
                    clean = clean.replace(/\s*style="[^"]*"/g, '');
                    return `${clean} ${extraAttrs} style="${styleStr}">`;
                });
            }
        }
        fs.writeFileSync(HTML_FILE, html, 'utf8');
        console.log(`[Auto-Save] Successfully baked layout into ${path.basename(HTML_FILE)}`);
    } catch (e) {
        console.warn(`[Auto-Save Warning] Failed to update HTML baked state: ${e.message}`);
    }
}

const server = http.createServer((req, res) => {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        res.writeHead(204);
        res.end();
        return;
    }

    const parsedUrl = url.parse(req.url, true);
    const pathname = parsedUrl.pathname;

    // API: Live Reload SSE Endpoint
    if (req.method === 'GET' && pathname === '/api/live-reload') {
        res.writeHead(200, {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        });
        res.write('retry: 1500\n');
        res.write('data: connected\n\n');

        sseClients.add(res);
        req.on('close', () => {
            sseClients.delete(res);
        });
        return;
    }

    // API: GET Layout
    if (req.method === 'GET' && pathname === '/api/layout') {
        if (fs.existsSync(LAYOUT_FILE)) {
            try {
                const data = fs.readFileSync(LAYOUT_FILE, 'utf8');
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(data);
                return;
            } catch (e) {
                console.error(`[Error] Failed to read ${LAYOUT_FILE}:`, e);
            }
        }
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'empty', nodes: {} }));
        return;
    }

    // API: POST Save Layout
    if (req.method === 'POST' && pathname === '/api/layout') {
        let body = '';
        req.on('data', chunk => {
            body += chunk;
            if (body.length > 5 * 1024 * 1024) { // 5MB limit
                req.destroy();
            }
        });
        req.on('end', () => {
            try {
                lastInternalWrite = Date.now();
                const state = JSON.parse(body);
                // 1. Write to diagram_layout.json
                fs.writeFileSync(LAYOUT_FILE, JSON.stringify(state, null, 2), 'utf8');
                // 2. Also update HTML file directly
                updateHtmlBakedState(state);
                console.log(`[Auto-Save] Layout saved: ${Object.keys(state.nodes || {}).length} nodes positioned.`);

                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ success: true, timestamp: Date.now() }));
            } catch (e) {
                res.writeHead(400, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ success: false, error: e.message }));
            }
        });
        return;
    }

    // Static File Serving
    let safePath = path.normalize(pathname).replace(/^(\.\.[\/\\])+/, '');
    if (safePath === '/' || safePath === '\\') {
        safePath = '/diagram_arsitektur.html';
    }

    const filePath = path.join(BASE_DIR, safePath);

    fs.stat(filePath, (err, stats) => {
        if (err || !stats.isFile()) {
            res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
            res.end('404 Not Found');
            return;
        }

        const ext = path.extname(filePath).toLowerCase();
        const contentType = MIME_TYPES[ext] || 'application/octet-stream';

        // Add no-cache for HTML and JSON to ensure fresh layout delivery
        if (ext === '.html' || ext === '.json') {
            res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
        }

        res.writeHead(200, { 'Content-Type': contentType });
        const stream = fs.createReadStream(filePath);
        stream.pipe(res);
    });
});

server.listen(PORT, '127.0.0.1', () => {
    console.log('====================================================');
    console.log(`🚀 Diagram Architecture Server running at:`);
    console.log(`   http://127.0.0.1:${PORT}`);
    console.log(`   http://localhost:${PORT}`);
    console.log(`💾 Live Auto-Save & Auto-Reload Active -> watching:`);
    console.log(`   ${path.basename(HTML_FILE)}`);
    console.log('====================================================');
});
