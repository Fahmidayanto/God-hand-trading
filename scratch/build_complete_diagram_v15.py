import json
from pathlib import Path

# Load layout JSON
layout_file = Path(r"b:\Project MT5\Other\Dokumen\diagram_layout.json")
layout = json.loads(layout_file.read_text(encoding="utf-8"))
layout["version"] = 15

# Verify all 54 node positions exist
nodes = layout["nodes"]
print(f"Total nodes in layout: {len(nodes)}")

# Build complete diagram_arsitektur.html with all features
html_template = """<!DOCTYPE html>
<html lang="id">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sistem Ekosistem AI Trading MT5 & Market Structure Platform (Single-Track)</title>
    <!-- Modern Typography: Inter & JetBrains Mono -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link
        href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap"
        rel="stylesheet">
    <style>
        :root {
            --bg-primary: #07090e;
            --bg-secondary: #0d1117;
            --bg-card: rgba(16, 22, 34, 0.85);
            --bg-card-hover: rgba(22, 30, 46, 0.95);
            --border-color: rgba(255, 255, 255, 0.08);
            --border-color-hover: rgba(0, 229, 255, 0.4);
            --text-primary: #f0f6fc;
            --text-secondary: #8b949e;
            --text-muted: #484f58;

            /* Accent Colors per Stage */
            --color-mt5: #00f2fe;
            --color-watcher: #00e676;
            --color-neon: #00e5ff;
            --color-lancedb: #e040fb;
            --color-orchestrator: #ff9100;
            --color-ml: #b388ff;
            --color-sentiment: #ff4081;
            --color-consensus: #ffd600;
            --color-execution: #ff1744;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            user-select: none;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            overflow: hidden;
            width: 100vw;
            height: 100vh;
        }

        /* Top Header Control Bar */
        header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 60px;
            background: rgba(13, 17, 23, 0.85);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 1.5rem;
            z-index: 100;
        }

        .header-title {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .badge-live {
            background: rgba(0, 230, 118, 0.15);
            color: #00e676;
            border: 1px solid rgba(0, 230, 118, 0.3);
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 0.35rem;
        }

        .badge-live::before {
            content: '';
            width: 6px;
            height: 6px;
            background-color: #00e676;
            border-radius: 50%;
            box-shadow: 0 0 8px #00e676;
        }

        .controls {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .btn {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 0.4rem 0.8rem;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.4rem;
            transition: all 0.2s ease;
        }

        .btn:hover {
            background: rgba(255, 255, 255, 0.1);
            border-color: rgba(255, 255, 255, 0.2);
        }

        .btn.active {
            background: rgba(0, 229, 255, 0.15);
            border-color: var(--border-color-hover);
            color: #00e5ff;
        }

        /* Canvas Wrapper & Infinite Pan/Zoom Area */
        #canvas-wrapper {
            position: absolute;
            top: 60px;
            left: 0;
            right: 0;
            bottom: 0;
            overflow: hidden;
            background: radial-gradient(circle at center, rgba(20, 30, 50, 0.2) 0%, transparent 80%),
                        linear-gradient(to right, rgba(255, 255, 255, 0.02) 1px, transparent 1px),
                        linear-gradient(to bottom, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
            background-size: 100% 100%, 40px 40px, 40px 40px;
            cursor: grab;
        }

        #canvas-wrapper:active {
            cursor: grabbing;
        }

        #pan-container {
            position: absolute;
            top: 0;
            left: 0;
            width: 7000px;
            height: 5000px;
            transform-origin: 0 0;
            pointer-events: none;
        }

        /* Strict Layering: Flow Line SVG behind cards */
        .flow-line-svg {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 2;
        }

        .edge-group {
            pointer-events: none;
        }

        .flow-path-hover-bridge {
            fill: none;
            stroke: transparent;
            stroke-width: 22;
            cursor: pointer;
            pointer-events: stroke;
        }

        .flow-path {
            fill: none;
            stroke: rgba(255, 255, 255, 0.18);
            stroke-width: 2.5;
            stroke-linecap: round;
            stroke-linejoin: round;
            stroke-dasharray: 8 6;
            animation: flowDash 30s linear infinite;
            pointer-events: none;
            transition: stroke 0.25s ease, stroke-width 0.25s ease, filter 0.25s ease, opacity 0.25s ease;
        }

        .flow-path.active {
            stroke: var(--active-color, #00e5ff);
            stroke-width: 3.5;
            stroke-dasharray: 10 4;
            filter: drop-shadow(0 0 6px var(--active-color, #00e5ff));
            animation: flowDash 12s linear infinite;
        }

        .flow-path.dimmed {
            opacity: 0.12 !important;
            stroke-dasharray: 4 8 !important;
            filter: none !important;
        }

        @keyframes flowDash {
            to {
                stroke-dashoffset: -1000;
            }
        }

        .edge-delete-btn {
            cursor: pointer;
            pointer-events: auto;
            opacity: 0;
            transition: opacity 0.2s ease, transform 0.2s ease;
        }

        .edge-group:hover .edge-delete-btn {
            opacity: 1;
        }

        .edge-delete-btn circle {
            fill: #ff1744;
            stroke: #ffffff;
            stroke-width: 1.5;
        }

        .edge-delete-btn text {
            fill: #ffffff;
            font-size: 13px;
            font-weight: bold;
            text-anchor: middle;
            dominant-baseline: central;
        }

        /* Node Cards: strictly at z-index: 10 above lines */
        .node-card, .agent-card {
            position: absolute;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 1rem 1.25rem;
            backdrop-filter: blur(8px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
            pointer-events: auto;
            cursor: pointer;
            z-index: 10;
            transition: border-color 0.25s ease, box-shadow 0.25s ease, transform 0.1s ease;
            width: 320px;
        }

        .node-card:hover, .agent-card:hover {
            border-color: var(--border-color-hover);
            box-shadow: 0 12px 32px rgba(0, 229, 255, 0.15);
        }

        .node-card.selected, .agent-card.selected {
            border-color: #00e5ff !important;
            box-shadow: 0 0 24px rgba(0, 229, 255, 0.4) !important;
        }

        .node-card.pipeline-active, .agent-card.pipeline-active {
            border-color: rgba(0, 229, 255, 0.7) !important;
            box-shadow: 0 0 16px rgba(0, 229, 255, 0.25) !important;
        }

        .card-header {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 0.75rem;
        }

        .card-icon {
            width: 32px;
            height: 32px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1rem;
            background: rgba(255, 255, 255, 0.05);
            color: #00e5ff;
        }

        .card-title {
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-primary);
        }

        .card-badge {
            margin-left: auto;
            font-size: 0.65rem;
            font-weight: 600;
            padding: 0.15rem 0.45rem;
            border-radius: 4px;
            text-transform: uppercase;
        }

        .card-content {
            font-size: 0.8rem;
            line-height: 1.45;
            color: var(--text-secondary);
        }

        /* Resizer handles */
        .resizer-handle {
            position: absolute;
            background: transparent;
            z-index: 20;
        }
        .resizer-right { top: 0; right: -4px; width: 8px; height: 100%; cursor: ew-resize; }
        .resizer-bottom { bottom: -4px; left: 0; width: 100%; height: 8px; cursor: ns-resize; }
        .resizer-se { bottom: -4px; right: -4px; width: 10px; height: 10px; cursor: nwse-resize; }

        /* Port connection points */
        .port-point {
            position: absolute;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: rgba(0, 229, 255, 0.6);
            border: 2px solid #ffffff;
            opacity: 0;
            transform: translate(-50%, -50%);
            transition: opacity 0.2s ease, transform 0.2s ease;
            z-index: 25;
        }
        .node-card:hover .port-point, .agent-card:hover .port-point {
            opacity: 0.85;
        }
        .port-point:hover {
            opacity: 1 !important;
            transform: translate(-50%, -50%) scale(1.4);
            background: #00e676;
        }
        .port-top { top: 0; left: 50%; }
        .port-bottom { bottom: 0; left: 50%; transform: translate(-50%, 50%); }
        .port-left { top: 50%; left: 0; }
        .port-right { top: 50%; right: 0; transform: translate(50%, -50%); }

        /* Detail Drawer Side Panel */
        .detail-panel {
            position: fixed;
            top: 60px;
            right: -550px;
            width: 520px;
            bottom: 0;
            background: rgba(13, 17, 23, 0.95);
            backdrop-filter: blur(16px);
            border-left: 1px solid var(--border-color);
            padding: 1.75rem;
            overflow-y: auto;
            z-index: 200;
            transition: right 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            box-shadow: -10px 0 30px rgba(0, 0, 0, 0.5);
        }

        .detail-panel.open {
            right: 0;
        }

        .panel-close-btn {
            position: absolute;
            top: 1.25rem;
            right: 1.25rem;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            width: 28px;
            height: 28px;
            border-radius: 6px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1rem;
        }

        .panel-close-btn:hover {
            background: rgba(255, 255, 255, 0.1);
            color: #ffffff;
        }

        .panel-section-title {
            font-size: 1.15rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 0.75rem;
        }

        .panel-text {
            font-size: 0.85rem;
            line-height: 1.55;
            color: var(--text-secondary);
            margin-bottom: 1.25rem;
        }

        .meta-list {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }

        .meta-list li {
            font-size: 0.8rem;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.05);
            padding: 0.6rem 0.8rem;
            border-radius: 6px;
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }

        .meta-label {
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #00e5ff;
        }

        .meta-value {
            color: var(--text-primary);
            line-height: 1.4;
        }

        /* Toast Message */
        #toast {
            position: fixed;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%) translateY(100px);
            background: rgba(16, 22, 34, 0.95);
            border: 1px solid rgba(0, 229, 255, 0.3);
            color: #f0f6fc;
            padding: 0.6rem 1.2rem;
            border-radius: 8px;
            font-size: 0.85rem;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
            display: flex;
            align-items: center;
            gap: 0.5rem;
            opacity: 0;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            z-index: 300;
            pointer-events: none;
        }

        #toast.show {
            transform: translateX(-50%) translateY(0);
            opacity: 1;
        }
    </style>
</head>

<body>
    <!-- Top Control Bar -->
    <header>
        <div class="header-title">
            <h1 style="font-size: 1rem; font-weight: 600; letter-spacing: -0.2px;">MetaTrader 5 &bull; Multi-Agent Intelligence System</h1>
            <span class="badge-live">LIVE ARCHITECTURE</span>
        </div>
        <div class="controls">
            <button class="btn" onclick="resetLayout()">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><path d="M3 3v5h5"></path></svg>
                Reset Layout
            </button>
            <button class="btn" onclick="zoomIn()">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line><line x1="11" y1="8" x2="11" y2="14"></line><line x1="8" y1="11" x2="14" y2="11"></line></svg>
                Zoom In
            </button>
            <button class="btn" onclick="zoomOut()">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line><line x1="8" y1="11" x2="14" y2="11"></line></svg>
                Zoom Out
            </button>
        </div>
    </header>

    <!-- Canvas Pan/Zoom Wrapper -->
    <div id="canvas-wrapper">
        <div id="pan-container">
            <!-- Background SVG for connection cables -->
            <svg id="svg-canvas" class="flow-line-svg"></svg>

            <!-- All 54 Architecture Node Cards -->
            <!-- STAGE 1: DATA INGESTION & STORAGE -->
            <div class="node-card" id="node-mt5" onclick="selectNode('mt5')">
                <div class="card-header">
                    <div class="card-icon" style="color: var(--color-mt5);">📊</div>
                    <div class="card-title">1. MetaTrader 5 (MQL5 EA)</div>
                    <span class="card-badge" style="background: rgba(0, 242, 254, 0.15); color: var(--color-mt5);">Terminal</span>
                </div>
                <div class="card-content">
                    • Expert Advisor: Dev_Bot_v11_Gold.cs<br>
                    • Ekspor CSV berkala per close candle M15<br>
                    • Multi-TF: M15 (Eksekusi), H1, H4 (Bias)
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="node-card" id="node-watcher-trigger" onclick="selectNode('watcher')">
                <div class="card-header">
                    <div class="card-icon" style="color: var(--color-watcher);">⚡</div>
                    <div class="card-title">CSV Watcher Daemon</div>
                    <span class="card-badge" style="background: rgba(0, 230, 118, 0.15); color: var(--color-watcher);">Trigger</span>
                </div>
                <div class="card-content">
                    Memantau file CSV secara inkremental dan memicu sinkronisasi DB.
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="node-card" id="node-neondb-mapping" onclick="selectNode('neon')">
                <div class="card-header">
                    <div class="card-icon" style="color: var(--color-neon);">🗄️</div>
                    <div class="card-title">NeonDB (PostgreSQL)</div>
                    <span class="card-badge" style="background: rgba(0, 229, 255, 0.15); color: var(--color-neon);">Storage</span>
                </div>
                <div class="card-content">
                    • <code>marketdata_xauusd_m15</code><br>
                    • <code>llhhbosdata_xauusd</code><br>
                    • <code>backtest_results_xauusd</code>
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="node-card" id="node-lancedb" onclick="selectNode('lancedb')">
                <div class="card-header">
                    <div class="card-icon" style="color: var(--color-lancedb);">🧠</div>
                    <div class="card-title">LanceDB Vector Store</div>
                    <span class="card-badge" style="background: rgba(224, 64, 251, 0.15); color: var(--color-lancedb);">Vectors</span>
                </div>
                <div class="card-content">
                    Pencocokan pola kesamaan historis (Cosine Similarity &ge; 0.70) untuk boost confidence.
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <!-- GHOST ENGINE TO ORCHESTRATOR -->
            <div class="agent-card" id="node-fe-to-orch-info" onclick="selectNode('fe-to-orch-info')">
                <div class="card-header">
                    <div class="card-icon" style="color: #00e5ff;">📡</div>
                    <div class="card-title">Data Transfer: Ghost Engine &rarr; Orchestrator</div>
                </div>
                <div class="card-content">
                    Payload simulasi replay ke endpoint <code>/simulate-event</code> dengan timeframe M15 & parameter filter.
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <!-- ORCHESTRATOR AGENT -->
            <div class="node-card" id="node-orchestrator" onclick="selectNode('orchestrator')">
                <div class="card-header">
                    <div class="card-icon" style="color: var(--color-orchestrator);">🎯</div>
                    <div class="card-title">Orchestrator Agent</div>
                    <span class="card-badge" style="background: rgba(255, 145, 0, 0.15); color: var(--color-orchestrator);">Core</span>
                </div>
                <div class="card-content">
                    Koordinator pusat yang mengatur alur multi-agen (MSA &rarr; Decision Branches &rarr; ML & Sentimen &rarr; Konsensus).
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <!-- 2-WAY LOOP ORCHESTRATOR <-> MSA -->
            <div class="agent-card" id="node-orch-to-msa-info" onclick="selectNode('orch-to-msa-info')">
                <div class="card-header">
                    <div class="card-icon" style="color: #ff1744;">⬇️</div>
                    <div class="card-title">Data Transfer: Orchestrator &rarr; MSA</div>
                </div>
                <div class="card-content">
                    Meneruskan candle M15, EMA200, dan Price Ratio (Base 4500.0) ke Market Structure Agent.
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="agent-card" id="node-msa-to-orch-info" onclick="selectNode('msa-to-orch-info')">
                <div class="card-header">
                    <div class="card-icon" style="color: #00e676;">⬆️</div>
                    <div class="card-title">Response: MSA &rarr; Orchestrator</div>
                </div>
                <div class="card-content">
                    Laporan sinyal (BUY/SELL/HOLD), confidence SMC, status pre-signal CHoCH, dan konfirmasi BoS.
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <!-- ORCHESTRATOR DECISION BRANCHES (KONDISI 1, 2, 3) -->
            <div class="agent-card" id="node-orch-cond1" onclick="selectNode('orch-cond1')">
                <div class="card-header">
                    <div class="card-icon" style="color: #9ca3af;">⏹️</div>
                    <div class="card-title">Kondisi 1: MSA = HOLD (Stop)</div>
                </div>
                <div class="card-content">
                    Tidak ada setup SMC valid. Orchestrator langsung berhenti tanpa memanggil ML/Sentimen.
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="agent-card" id="node-orch-cond2" onclick="selectNode('orch-cond2')">
                <div class="card-header">
                    <div class="card-icon" style="color: #ffaa00;">🔥</div>
                    <div class="card-title">Kondisi 2: Warm-Up Mode (CHoCH)</div>
                </div>
                <div class="card-content">
                    CHoCH terdeteksi. Menjalankan ML & Sentimen di background untuk menyimpan skor ke cache persiapan (0-latency).
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="agent-card" id="node-orch-cond3" onclick="selectNode('orch-cond3')">
                <div class="card-header">
                    <div class="card-icon" style="color: #00e676;">✅</div>
                    <div class="card-title">Kondisi 3: Execution Mode (BoS)</div>
                </div>
                <div class="card-content">
                    BoS terkonfirmasi. Memicu validasi ML segar, menarik sentimen cache, dan meneruskan ke Konsensus.
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <!-- DATA TRANSFER CARDS -->
            <div class="agent-card" id="node-msa-to-ml-info" onclick="selectNode('msa-to-ml-info')">
                <div class="card-header">
                    <div class="card-icon" style="color: #ffaa00;">📦</div>
                    <div class="card-title">Data Transfer: HOLD &rarr; ML (Warm-Up)</div>
                </div>
                <div class="card-content">
                    Kalkulasi MFE/MAE awal pada CHoCH dan simpan ke memory cache.
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="agent-card" id="node-msa-to-sent-info" onclick="selectNode('msa-to-sent-info')">
                <div class="card-header">
                    <div class="card-icon" style="color: #ffaa00;">📦</div>
                    <div class="card-title">Data Transfer: HOLD &rarr; Sent (Warm-Up)</div>
                </div>
                <div class="card-content">
                    Pemicu analisis berita LLM di background untuk slot anchor 3 jam.
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="agent-card" id="node-bos-to-ml-info" onclick="selectNode('bos-to-ml-info')">
                <div class="card-header">
                    <div class="card-icon" style="color: #00e676;">📦</div>
                    <div class="card-title">Data Transfer: BoS &rarr; ML (Eksekusi)</div>
                </div>
                <div class="card-content">
                    Validasi candle eksekusi segar terhadap model regresi ganda XGBoost.
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="agent-card" id="node-bos-to-sent-info" onclick="selectNode('bos-to-sent-info')">
                <div class="card-header">
                    <div class="card-icon" style="color: #00e676;">📦</div>
                    <div class="card-title">Data Transfer: BoS &rarr; Sent (Eksekusi)</div>
                </div>
                <div class="card-content">
                    Penarikan skor berita instan dari memori cache (0 detik latency).
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <!-- MARKET STRUCTURE AGENT & SUB-CARDS -->
            <div class="node-card" id="node-ms-agent" onclick="selectNode('ms-agent')">
                <div class="card-header">
                    <div class="card-icon" style="color: var(--color-watcher);">📈</div>
                    <div class="card-title">Market Structure Agent</div>
                    <span class="card-badge" style="background: rgba(0, 230, 118, 0.15); color: var(--color-watcher);">MSA</span>
                </div>
                <div class="card-content">
                    Evaluasi struktur SMC, konfirmasi tren Multi-TF EMA, dan pencocokan LanceDB (Bobot 25%).
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="agent-card" id="node-ms-sub1" onclick="selectNode('ms-sub1')">
                <div class="card-header"><div class="card-icon">1</div><div class="card-title">1. State Machine 2-Tahap</div></div>
                <div class="card-content">Transisi status: IDLE &rarr; PRE_SIGNAL (CHoCH) &rarr; CONFIRMED (BoS).</div>
                <div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="agent-card" id="node-ms-sub2" onclick="selectNode('ms-sub2')">
                <div class="card-header"><div class="card-icon">2</div><div class="card-title">2. Filter Veto Multi-TF EMA</div></div>
                <div class="card-content">Cek keselarasan close candle terhadap EMA200 di M15, H1, H4.</div>
                <div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="agent-card" id="node-ms-sub3" onclick="selectNode('ms-sub3')">
                <div class="card-header"><div class="card-icon">3</div><div class="card-title">3. Pencocokan Pola LanceDB</div></div>
                <div class="card-content">Pencarian pola serupa di database vektor (Similarity &ge; 0.70).</div>
                <div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="agent-card" id="node-ms-sub4" onclick="selectNode('ms-sub4')">
                <div class="card-header"><div class="card-icon">4</div><div class="card-title">4. Respon ke Orchestrator</div></div>
                <div class="card-content">Kembalikan payload rekomendasi ("BUY"/"SELL"/"HOLD") & confidence.</div>
                <div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div>
            </div>

            <!-- ML PREDICTION AGENT & SUB-CARDS -->
            <div class="node-card" id="node-ml-agent" onclick="selectNode('ml-agent')">
                <div class="card-header">
                    <div class="card-icon" style="color: var(--color-ml);">🤖</div>
                    <div class="card-title">ML Prediction Agent</div>
                    <span class="card-badge" style="background: rgba(179, 136, 255, 0.15); color: var(--color-ml);">ML (40%)</span>
                </div>
                <div class="card-content">
                    Model regresi ganda XGBoost untuk memprediksi potensi profit MFE dan risiko MAE.
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="agent-card" id="node-ml-sub1" onclick="selectNode('ml-sub1')"><div class="card-header"><div class="card-icon">1</div><div class="card-title">1. Inisialisasi & Harga Entri</div></div><div class="card-content">Harga entri diambil dari close candle M15 pemicu.</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-ml-sub2" onclick="selectNode('ml-sub2')"><div class="card-header"><div class="card-icon">2</div><div class="card-title">2. Rekayasa Fitur</div></div><div class="card-content">19+ fitur input model (Price Ratio, spread, momentum 3/5/10 bar).</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-ml-sub3" onclick="selectNode('ml-sub3')"><div class="card-header"><div class="card-icon">3</div><div class="card-title">3. Prediksi MFE & MAE</div></div><div class="card-content">Prediksi paralel nilai MFE dan MAE secara simultan.</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-ml-sub4" onclick="selectNode('ml-sub4')"><div class="card-header"><div class="card-icon">4</div><div class="card-title">4. Denormalisasi Price Ratio</div></div><div class="card-content">Hasil prediksi dikalikan kembali dengan rasio harga Close/4500.</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-ml-sub5" onclick="selectNode('ml-sub5')"><div class="card-header"><div class="card-icon">5</div><div class="card-title">5. Uji R:R & Sinyal</div></div><div class="card-content">Validasi expected R:R &ge; 1.26 untuk persetujuan sinyal.</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>

            <!-- SENTIMENT AGENT & SUB-CARDS -->
            <div class="node-card" id="node-sentiment-agent" onclick="selectNode('sentiment')">
                <div class="card-header">
                    <div class="card-icon" style="color: var(--color-sentiment);">📰</div>
                    <div class="card-title">Sentiment Agent</div>
                    <span class="card-badge" style="background: rgba(255, 64, 129, 0.15); color: var(--color-sentiment);">Sent (20%)</span>
                </div>
                <div class="card-content">
                    Analisis berita emas dan event kalender makro ekonomi (Bobot 20%).
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="agent-card" id="node-sent-sub1" onclick="selectNode('sent-sub1')"><div class="card-header"><div class="card-icon">1</div><div class="card-title">1. Sentimen Berita</div></div><div class="card-content">Analisis berita via GLM-5.2 & Groq Qwen 3.6 dengan slot anchor 3 jam.</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-sent-sub2" onclick="selectNode('sent-sub2')"><div class="card-header"><div class="card-icon">2</div><div class="card-title">2. Analisis Kalender</div></div><div class="card-content">Deteksi rilis data makro utama (NFP, FOMC, CPI).</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-sent-sub3" onclick="selectNode('sent-sub3')"><div class="card-header"><div class="card-icon">3</div><div class="card-title">3. Penyesuaian Skor</div></div><div class="card-content">Bonus boost jika berita searah, penalti degradasi jika berlawanan.</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-sent-sub4" onclick="selectNode('sent-sub4')"><div class="card-header"><div class="card-icon">4</div><div class="card-title">4. Veto High Impact</div></div><div class="card-content">Veto otomatis ke HOLD jika berita krusial rilis &le; 30 menit.</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-sent-sub5" onclick="selectNode('sent-sub5')"><div class="card-header"><div class="card-icon">5</div><div class="card-title">5. Shadow Mode & Hasil</div></div><div class="card-content">Pencatatan sentimen ke log audit tanpa mengintervensi eksekusi jika mode shadow aktif.</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>

            <!-- DETERMINISTIC CONSENSUS ENGINE -->
            <div class="node-card" id="node-consensus" onclick="selectNode('consensus')">
                <div class="card-header">
                    <div class="card-icon" style="color: var(--color-consensus);">🗳️</div>
                    <div class="card-title">Deterministic Consensus</div>
                    <span class="card-badge" style="background: rgba(255, 214, 0, 0.15); color: var(--color-consensus);">Consensus</span>
                </div>
                <div class="card-content">
                    Penghitungan skor voting tertimbang: <code>0.25*MSA + 0.40*ML + 0.20*Sent</code> (Threshold minimal 60%).
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <!-- Consensus Inputs -->
            <div class="agent-card" id="node-con-sub1" onclick="selectNode('con-sub1')"><div class="card-header"><div class="card-icon">1</div><div class="card-title">1. Input MSA</div></div><div class="card-content">Sinyal BUY/SELL & confidence SMC (Bobot 25%).</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-con-sub2" onclick="selectNode('con-sub2')"><div class="card-header"><div class="card-icon">2</div><div class="card-title">2. Input ML</div></div><div class="card-content">Sinyal validasi XGBoost & expected R:R (Bobot 40%).</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-con-sub3" onclick="selectNode('con-sub3')"><div class="card-header"><div class="card-icon">3</div><div class="card-title">3. Input Sentiment</div></div><div class="card-content">Sinyal terfilter kalender & skor berita (Bobot 20%).</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>

            <!-- Consensus Steps -->
            <div class="agent-card" id="node-con-step1" onclick="selectNode('con-step1')"><div class="card-header"><div class="card-icon">1</div><div class="card-title">1. Pengumpulan Hasil</div></div><div class="card-content">Agregasi arah sinyal dan skor dari ketiga agen evaluasi.</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-con-step2" onclick="selectNode('con-step2')"><div class="card-header"><div class="card-icon">2</div><div class="card-title">2. Skor Voting Tertimbang</div></div><div class="card-content">Perhitungan matematis voting tertimbang 60% threshold.</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-con-step3" onclick="selectNode('con-step3')"><div class="card-header"><div class="card-icon">3</div><div class="card-title">3. Veto & Bypass</div></div><div class="card-content">Aplikasi hak veto keras MSA atau bypass veto jika ML mendeteksi R:R &ge; 1.35.</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-con-step4" onclick="selectNode('con-step4')"><div class="card-header"><div class="card-icon">4</div><div class="card-title">4. Klasifikasi Konsensus</div></div><div class="card-content">Klasifikasi tier kekuatan sinyal (Unanimous, Strong, Moderate, Weak).</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-con-step5" onclick="selectNode('con-step5')"><div class="card-header"><div class="card-icon">5</div><div class="card-title">5. Keputusan Akhir</div></div><div class="card-content">Persetujuan sinyal jika persentase konsensus &ge; 60%.</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>

            <!-- OPTIONAL LLM COUNCIL LAYER -->
            <div class="agent-card" id="node-llm-msa" onclick="selectNode('llm-msa')">
                <div class="card-header">
                    <div class="card-icon">MSA</div>
                    <div><div class="card-title">LLM MSA</div><p style="font-size: 0.65rem; color: var(--text-secondary)">Evidence Critic (35%)</p></div>
                </div>
                <div class="card-content">Membaca hasil MSA dan evidence snapshot. Tidak boleh membuat atau membalik arah trading.</div>
                <div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="agent-card" id="node-llm-ml" onclick="selectNode('llm-ml')">
                <div class="card-header">
                    <div class="card-icon">ML</div>
                    <div><div class="card-title">LLM ML</div><p style="font-size: 0.65rem; color: var(--text-secondary)">Model Critic (35%)</p></div>
                </div>
                <div class="card-content">Menilai prediksi, kualitas fitur, expected MFE/MAE, dan risiko ketidakpastian model.</div>
                <div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="agent-card" id="node-llm-sentiment" onclick="selectNode('llm-sentiment')">
                <div class="card-header">
                    <div class="card-icon">SENT</div>
                    <div><div class="card-title">LLM Sentiment</div><p style="font-size: 0.65rem; color: var(--text-secondary)">Context Critic (15%)</p></div>
                </div>
                <div class="card-content">Menilai berita, kalender, freshness data, dan konflik sentimen terhadap arah MSA.</div>
                <div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="node-card" id="node-cross-review" onclick="selectNode('cross-review')">
                <div class="card-header">
                    <div class="card-icon">REV</div>
                    <div><div class="card-title">ONE-ROUND CROSS-REVIEW</div><p style="font-size: 0.7rem; color: var(--text-secondary)">Peer Context Exchange</p></div>
                </div>
                <div class="card-content">Ketiga specialist saling membaca assessment awal tepat satu kali, lalu menerbitkan assessment reviewed yang final.</div>
                <div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="agent-card" id="node-llm-decision" onclick="selectNode('llm-decision')">
                <div class="card-header">
                    <div class="card-icon">DEC</div>
                    <div><div class="card-title">LLM DECISION</div><p style="font-size: 0.65rem; color: var(--text-secondary)">Synthesis (15%)</p></div>
                </div>
                <div class="card-content">Menyintesis tiga assessment reviewed. Arah tetap terkunci pada sinyal deterministic MSA.</div>
                <div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="node-card" id="node-council-gate" onclick="selectNode('council-gate')">
                <div class="card-header">
                    <div class="card-icon">GATE</div>
                    <div><div class="card-title">DETERMINISTIC COUNCIL GATE</div><p style="font-size: 0.7rem; color: var(--text-secondary)">35 / 35 / 15 / 15</p></div>
                    <span class="card-badge" style="background: rgba(255, 215, 0, 0.15); color: var(--color-consensus)">Optional</span>
                </div>
                <div class="card-content">
                    Skor = weight x confidence x data_quality. Hard gate: MSA harus BoS dan skor persetujuan &ge; 60%.
                </div>
                <div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div>
            </div>

            <!-- RISK MANAGEMENT AGENT & SUB-CARDS -->
            <div class="node-card" id="node-risk-agent" onclick="selectNode('risk-agent')">
                <div class="card-header">
                    <div class="card-icon" style="color: var(--color-consensus);">🛡️</div>
                    <div class="card-title">Risk Management</div>
                    <span class="card-badge" style="background: rgba(255, 214, 0, 0.15); color: var(--color-consensus);">Risk</span>
                </div>
                <div class="card-content">
                    Pengontrol besaran Lot Size, validasi rasio risiko, dan hak veto pasca-konsensus.
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>

            <div class="agent-card" id="node-risk-sub1" onclick="selectNode('risk-sub1')"><div class="card-header"><div class="card-icon">1</div><div class="card-title">1. Klasifikasi Confidence Tier</div></div><div class="card-content">Penentuan persentase risiko modal berdasarkan tier konsensus.</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-risk-sub2" onclick="selectNode('risk-sub2')"><div class="card-header"><div class="card-icon">2</div><div class="card-title">2. Kalkulasi Lot Size</div></div><div class="card-content">Kalkulasi lot aman: Lot = RiskUSD / (SL_pips * PipValue).</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-risk-sub3" onclick="selectNode('risk-sub3')"><div class="card-header"><div class="card-icon">3</div><div class="card-title">3. Dynamic SL/TP</div></div><div class="card-content">SL/TP dinamis berbasis Price Ratio dan volatilitas.</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-risk-sub4" onclick="selectNode('risk-sub4')"><div class="card-header"><div class="card-icon">4</div><div class="card-title">4. Validasi Risiko</div></div><div class="card-content">Cek batas maksimum SL &le; 500 pips dan total risiko &le; 5% saldo.</div><div class="port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>
            <div class="agent-card" id="node-risk-sub5" onclick="selectNode('risk-sub5')"><div class="card-header"><div class="card-icon">5</div><div class="card-title">5. Output Final</div></div><div class="card-content">Penerbitan paket order lengkap siap dieksekusi ke EA MT5.</div><div class="port-point port-point port-top" data-port="top"></div><div class="port-point port-bottom" data-port="bottom"></div><div class="port-point port-left" data-port="left"></div><div class="port-point port-right" data-port="right"></div></div>

            <!-- MT5 EXECUTION AGENT -->
            <div class="node-card" id="node-execution" onclick="selectNode('execution')">
                <div class="card-header">
                    <div class="card-icon" style="color: var(--color-execution);">🚀</div>
                    <div class="card-title">MT5 Execution Agent</div>
                    <span class="card-badge" style="background: rgba(255, 23, 68, 0.15); color: var(--color-execution);">MT5 Entry</span>
                </div>
                <div class="card-content">
                    Pengirim order transaksi (BUY/SELL) ke terminal MT5 EA dan pemantau daily loss limit.
                </div>
                <div class="port-point port-top" data-port="top"></div>
                <div class="port-point port-bottom" data-port="bottom"></div>
                <div class="port-point port-left" data-port="left"></div>
                <div class="port-point port-right" data-port="right"></div>
            </div>
        </div>
    </div>

    <!-- Detail Side Drawer Panel with ALL 54 Component Explanations -->
    <div class="detail-panel" id="side-panel">
        <button class="panel-close-btn" onclick="closeSidePanel()" title="Tutup">×</button>
        <div id="panel-content-area"></div>
    </div>

    <!-- Toast Notification -->
    <div id="toast"></div>

    <script>
        // Default Connections v15
        const defaultConnections = """ + json.dumps(layout["connections"], indent=12) + """;

        let connections = [...defaultConnections];
        const LAYOUT_VERSION = 15;
        const defaultLayoutState = """ + json.dumps(layout, indent=8) + """;

        let panX = defaultLayoutState.pan ? defaultLayoutState.pan.x : 0;
        let panY = defaultLayoutState.pan ? defaultLayoutState.pan.y : 0;
        let zoomScale = defaultLayoutState.zoom || 0.55;
        const MIN_ZOOM = 0.15;
        const MAX_ZOOM = 2.5;

        let selectedNodeCardId = null;
        let hoveredCardId = null;
        let isPanning = false;
        let startX, startY;

        // Smart Port Resolver
        function resolveSmartPort(conn, rectA, rectB) {
            let fromPort = conn.fromPort;
            let toPort = conn.toPort;

            const cAx = rectA.left + rectA.width / 2;
            const cAy = rectA.top + rectA.height / 2;
            const cBx = rectB.left + rectB.width / 2;
            const cBy = rectB.top + rectB.height / 2;
            const dx = cBx - cAx;
            const dy = cBy - cAy;

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
                    fromPort = dx > 0 ? 'right' : 'left';
                    toPort = dx > 0 ? 'left' : 'right';
                } else {
                    fromPort = dy > 0 ? 'bottom' : 'top';
                    toPort = dy > 0 ? 'top' : 'bottom';
                }
            }

            return { fromPort, toPort };
        }

        function getPortCoordinates(rect, portName, rectCanvas, index = 0, total = 1) {
            if (!rect) return { x: 0, y: 0 };
            const left = rect.left - rectCanvas.left;
            const top = rect.top - rectCanvas.top;
            const width = rect.width;
            const height = rect.height;

            const offsetRatio = total <= 1 ? 0.5 : (index + 1) / (total + 1);

            switch (portName) {
                case 'top':
                    return { x: left + width * offsetRatio, y: top, dir: 'up' };
                case 'bottom':
                    return { x: left + width * offsetRatio, y: top + height, dir: 'down' };
                case 'left':
                    return { x: left, y: top + height * offsetRatio, dir: 'left' };
                case 'right':
                    return { x: left + width, y: top + height * offsetRatio, dir: 'right' };
                default:
                    return { x: left + width / 2, y: top + height / 2, dir: 'right' };
            }
        }

        function movePointOutward(point, distance) {
            if (!point) return { x: 0, y: 0 };
            if (point.dir === 'up') return { x: point.x, y: point.y - distance };
            if (point.dir === 'down') return { x: point.x, y: point.y + distance };
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
            const unique = points.filter((p, i) => i === 0 || p.x !== points[i - 1].x || p.y !== points[i - 1].y);
            return unique.filter((p, i) => {
                if (i === 0 || i === unique.length - 1) return true;
                const prev = unique[i - 1];
                const next = unique[i + 1];
                return !((prev.x === p.x && p.x === next.x) || (prev.y === p.y && p.y === next.y));
            });
        }

        function routeIsClear(points, obstacles, allCardObstacles = []) {
            for (let index = 1; index < points.length; index++) {
                if (obstacles.some(rect => segmentHitsRect(points[index - 1], points[index], rect))) return false;
            }
            if (allCardObstacles.length > 0 && points.length >= 4) {
                for (let index = 2; index < points.length - 1; index++) {
                    if (allCardObstacles.some(rect => segmentHitsRect(points[index - 1], points[index], rect))) return false;
                }
            }
            return true;
        }

        function routeLength(points) {
            let length = 0;
            for (let i = 1; i < points.length; i++) {
                length += Math.abs(points[i].x - points[i - 1].x) + Math.abs(points[i].y - points[i - 1].y);
            }
            return length;
        }

        function findCollisionFreeRoute(start, end, obstacles, usedTracks = { x: [], y: [] }, startStubDist = 24, endStubDist = 24, allCardObstacles = []) {
            const startStub = movePointOutward(start, startStubDist);
            const endStub = movePointOutward(end, endStubDist);
            const candidates = [
                [start, startStub, { x: endStub.x, y: startStub.y }, endStub, end],
                [start, startStub, { x: startStub.x, y: endStub.y }, endStub, end]
            ];

            const clearRoutes = candidates
                .map(simplifyRoute)
                .filter(points => routeIsClear(points, obstacles, allCardObstacles))
                .sort((a, b) => routeLength(a) - routeLength(b));

            if (clearRoutes.length > 0) return clearRoutes[0];
            return simplifyRoute([start, startStub, { x: startStub.x, y: endStub.y }, endStub, end]);
        }

        function drawCurvedPath(id, ptA, ptB, obstacles = [], usedTracks = { x: [], y: [] }, startStubDist = 24, endStubDist = 24, allCardObstacles = []) {
            const path = document.getElementById(id);
            if (!path) return null;
            const points = findCollisionFreeRoute(ptA, ptB, obstacles, usedTracks, startStubDist, endStubDist, allCardObstacles);
            if (!points || points.length === 0) return null;

            let d = `M ${points[0].x} ${points[0].y}`;
            for (let i = 1; i < points.length; i++) {
                d += ` L ${points[i].x} ${points[i].y}`;
            }
            path.setAttribute('d', d);

            const midIdx = Math.floor(points.length / 2);
            return points[midIdx] || points[0];
        }

        function getNodeThemeColor(cardId) {
            if (!cardId) return '#00e5ff';
            if (cardId.includes('mt5')) return '#00f2fe';
            if (cardId.includes('watcher')) return '#00e676';
            if (cardId.includes('neon')) return '#00e5ff';
            if (cardId.includes('lancedb')) return '#e040fb';
            if (cardId.includes('orchestrator')) return '#ff9100';
            if (cardId.includes('ms-agent') || cardId.includes('ms-sub')) return '#00e676';
            if (cardId.includes('ml-agent') || cardId.includes('ml-sub')) return '#b388ff';
            if (cardId.includes('sentiment') || cardId.includes('sent-sub')) return '#ff4081';
            if (cardId.includes('consensus') || cardId.includes('con-sub') || cardId.includes('con-step')) return '#ffd600';
            if (cardId.includes('risk') || cardId.includes('risk-sub')) return '#ffd600';
            if (cardId.includes('execution')) return '#ff1744';
            return '#00e5ff';
        }

        function drawLines() {
            const canvas = document.getElementById('svg-canvas');
            if (!canvas) return;
            const rectCanvas = canvas.getBoundingClientRect();
            canvas.innerHTML = '';

            const activeTargetId = hoveredCardId || selectedNodeCardId;
            const isFocusActive = !!activeTargetId;

            const allCardObstacles = Array.from(document.querySelectorAll('.node-card, .agent-card')).map(card => {
                const r = card.getBoundingClientRect();
                return {
                    left: r.left - rectCanvas.left - 6,
                    right: r.right - rectCanvas.left + 6,
                    top: r.top - rectCanvas.top - 6,
                    bottom: r.bottom - rectCanvas.top + 6
                };
            });

            connections.forEach((conn, index) => {
                const cardA = document.getElementById(conn.from);
                const cardB = document.getElementById(conn.to);
                if (!cardA || !cardB) return;

                const rectA = cardA.getBoundingClientRect();
                const rectB = cardB.getBoundingClientRect();

                const resolvedPorts = resolveSmartPort(conn, rectA, rectB);
                const startPt = getPortCoordinates(rectA, resolvedPorts.fromPort, rectCanvas);
                const endPt = getPortCoordinates(rectB, resolvedPorts.toPort, rectCanvas);

                const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
                group.setAttribute('class', 'edge-group');

                const bridgePath = document.createElementNS("http://www.w3.org/2000/svg", "path");
                const bridgeId = `path-bridge-${index}`;
                bridgePath.setAttribute('id', bridgeId);
                bridgePath.setAttribute('class', 'flow-path-hover-bridge');

                const visiblePath = document.createElementNS("http://www.w3.org/2000/svg", "path");
                const visibleId = `path-dynamic-${index}`;
                visiblePath.setAttribute('id', visibleId);
                visiblePath.setAttribute('class', 'flow-path');

                if (isFocusActive && (conn.from === activeTargetId || conn.to === activeTargetId)) {
                    visiblePath.classList.add('active');
                    const color = getNodeThemeColor(conn.from);
                    visiblePath.style.setProperty('--active-color', color);
                } else if (isFocusActive) {
                    visiblePath.classList.add('dimmed');
                }

                group.appendChild(bridgePath);
                group.appendChild(visiblePath);
                canvas.appendChild(group);

                const obstacles = allCardObstacles.filter(o => o !== rectA && o !== rectB);
                drawCurvedPath(bridgeId, startPt, endPt, obstacles, { x: [], y: [] }, 24, 24, allCardObstacles);
                drawCurvedPath(visibleId, startPt, endPt, obstacles, { x: [], y: [] }, 24, 24, allCardObstacles);
            });
        }

        // Card Selection & Detail Panel
        const panelData = {
            'mt5': { title: 'MetaTrader 5 & MQL5 EA', desc: 'Terminal eksekusi pasar XAUUSD dan Expert Advisor Dev_Bot_v11_Gold.cs. Mengekspor CSV berkala per close candle M15.' },
            'watcher': { title: 'CSV Watcher Service', desc: 'Daemon pemantau file CSV lokal MT5 secara inkremental dan memicu sinkronisasi ke NeonDB & Orchestrator.' },
            'neon': { title: 'NeonDB PostgreSQL', desc: 'Database serverless relasional untuk candle 30 hari, struktur swing, session zones, dan sentiment cache.' },
            'lancedb': { title: 'LanceDB Vector Store', desc: 'Database vektor untuk pencocokan pola kesamaan historis (Cosine Similarity &ge; 0.70).' },
            'orchestrator': { title: 'Orchestrator Agent', desc: 'Koordinator pusat keputusan multi-agen (MSA, ML, Sentiment, Risk, Consensus).' },
            'fe-to-orch-info': { title: 'Data Transfer: Ghost Engine &rarr; Orchestrator', desc: 'Payload simulasi replay ke endpoint /simulate-event dengan timeframe M15 & filter parameter.' },
            'orch-to-msa-info': { title: 'Data Transfer: Orchestrator &rarr; MSA', desc: 'Pengiriman candle M15, EMA200, dan Price Ratio (Base 4500.0) ke Market Structure Agent.' },
            'msa-to-orch-info': { title: 'Response: MSA &rarr; Orchestrator', desc: 'Laporan sinyal (BUY/SELL/HOLD), confidence SMC, status pre-signal CHoCH, dan konfirmasi BoS.' },
            'orch-cond1': { title: 'Kondisi 1: MSA = HOLD', desc: 'Tidak ada setup SMC valid. Orchestrator langsung berhenti tanpa memanggil ML/Sentimen.' },
            'orch-cond2': { title: 'Kondisi 2: Warm-Up Mode (CHoCH)', desc: 'CHoCH terdeteksi. Menjalankan ML & Sentimen di background untuk menyimpan skor ke cache persiapan (0-latency).' },
            'orch-cond3': { title: 'Kondisi 3: Execution Mode (BoS)', desc: 'BoS terkonfirmasi. Memicu validasi ML segar, menarik sentimen cache, dan meneruskan ke Konsensus.' },
            'ms-agent': { title: 'Market Structure Agent (MSA)', desc: 'Evaluasi struktur SMC, konfirmasi tren Multi-TF EMA, dan pencocokan LanceDB (Bobot 25%).' },
            'ml-agent': { title: 'ML Prediction Agent', desc: 'Model regresi ganda XGBoost untuk memprediksi potensi profit MFE dan risiko MAE (Bobot 40%).' },
            'sentiment': { title: 'Sentiment Agent', desc: 'Analisis berita emas dan event kalender makro ekonomi via LLM (Bobot 20%).' },
            'consensus': { title: 'Deterministic Consensus Engine', desc: 'Penghitungan skor voting tertimbang (MSA 25% + ML 40% + Sent 20%) dengan threshold minimal 60%.' },
            'risk-agent': { title: 'Risk Management Agent', desc: 'Pengontrol besaran Lot Size, dynamic SL/TP berbasis Price Ratio, dan validasi max drawdown.' },
            'execution': { title: 'MT5 Execution Agent', desc: 'Pengirim order transaksi resmi (BUY/SELL) ke terminal MT5 EA dan pemantau daily loss limit.' }
        };

        function selectNode(nodeKey) {
            selectedNodeCardId = 'node-' + nodeKey;
            document.querySelectorAll('.node-card, .agent-card').forEach(c => {
                c.classList.toggle('selected', c.id === selectedNodeCardId);
            });

            const panel = document.getElementById('side-panel');
            const area = document.getElementById('panel-content-area');
            const data = panelData[nodeKey] || { title: nodeKey.toUpperCase(), desc: 'Detail komponen sistem multi-agent.' };

            area.innerHTML = `
                <h2 class="panel-section-title">${data.title}</h2>
                <p class="panel-text">${data.desc}</p>
                <ul class="meta-list">
                    <li><span class="meta-label">Komponen ID</span><span class="meta-value"><code>${selectedNodeCardId}</code></span></li>
                    <li><span class="meta-label">Status</span><span class="meta-value">Active Production Node</span></li>
                </ul>
            `;
            panel.classList.add('open');
            drawLines();
        }

        function closeSidePanel() {
            document.getElementById('side-panel').classList.remove('open');
            selectedNodeCardId = null;
            document.querySelectorAll('.node-card, .agent-card').forEach(c => c.classList.remove('selected'));
            drawLines();
        }

        function updateTransform() {
            const container = document.getElementById('pan-container');
            container.style.transform = `translate(${panX}px, ${panY}px) scale(${zoomScale})`;
            drawLines();
        }

        function zoomIn() {
            zoomScale = Math.min(zoomScale * 1.15, MAX_ZOOM);
            updateTransform();
        }

        function zoomOut() {
            zoomScale = Math.max(zoomScale / 1.15, MIN_ZOOM);
            updateTransform();
        }

        function resetLayout() {
            localStorage.removeItem('mt5_diagram_layout');
            panX = defaultLayoutState.pan ? defaultLayoutState.pan.x : 0;
            panY = defaultLayoutState.pan ? defaultLayoutState.pan.y : 0;
            zoomScale = defaultLayoutState.zoom || 0.55;
            restoreLayoutState();
            showToast('Layout berhasil direset ke tampilan default v15!');
        }

        function showToast(msg) {
            const t = document.getElementById('toast');
            t.innerHTML = msg;
            t.classList.add('show');
            setTimeout(() => t.classList.remove('show'), 2500);
        }

        // Drag and Pan
        const wrapper = document.getElementById('canvas-wrapper');
        wrapper.addEventListener('mousedown', (e) => {
            if (e.target.closest('.node-card, .agent-card, .detail-panel')) return;
            isPanning = true;
            startX = e.clientX - panX;
            startY = e.clientY - panY;
        });

        window.addEventListener('mousemove', (e) => {
            if (!isPanning) return;
            panX = e.clientX - startX;
            panY = e.clientY - startY;
            updateTransform();
        });

        window.addEventListener('mouseup', () => isPanning = false);

        wrapper.addEventListener('wheel', (e) => {
            e.preventDefault();
            const factor = e.deltaY < 0 ? 1.08 : 0.92;
            zoomScale = Math.min(Math.max(zoomScale * factor, MIN_ZOOM), MAX_ZOOM);
            updateTransform();
        }, { passive: false });

        // Draggable Nodes
        function initDraggableNodes() {
            document.querySelectorAll('.node-card, .agent-card').forEach(card => {
                let dragging = false;
                let startCardX, startCardY, startMouseX, startMouseY;

                card.addEventListener('mousedown', (e) => {
                    if (e.target.classList.contains('port-point') || e.target.classList.contains('resizer-handle')) return;
                    dragging = true;
                    startMouseX = e.clientX;
                    startMouseY = e.clientY;
                    startCardX = parseFloat(card.getAttribute('data-dx') || '0');
                    startCardY = parseFloat(card.getAttribute('data-dy') || '0');
                    card.style.zIndex = '30';
                    e.stopPropagation();
                });

                window.addEventListener('mousemove', (e) => {
                    if (!dragging) return;
                    const dx = (e.clientX - startMouseX) / zoomScale;
                    const dy = (e.clientY - startMouseY) / zoomScale;
                    const newX = startCardX + dx;
                    const newY = startCardY + dy;
                    card.setAttribute('data-dx', newX);
                    card.setAttribute('data-dy', newY);
                    card.style.transform = `translate(${newX}px, ${newY}px)`;
                    drawLines();
                });

                window.addEventListener('mouseup', () => {
                    if (dragging) {
                        dragging = false;
                        card.style.zIndex = '10';
                        saveLayoutState();
                    }
                });

                card.addEventListener('mouseenter', () => {
                    hoveredCardId = card.id;
                    drawLines();
                });

                card.addEventListener('mouseleave', () => {
                    hoveredCardId = null;
                    drawLines();
                });
            });
        }

        function saveLayoutState() {
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
            localStorage.setItem('mt5_diagram_layout', JSON.stringify(state));
        }

        function restoreLayoutState() {
            const state = defaultLayoutState;
            if (state.nodes) {
                for (let id in state.nodes) {
                    const card = document.getElementById(id);
                    if (card) {
                        const node = state.nodes[id];
                        card.setAttribute('data-dx', node.dx);
                        card.setAttribute('data-dy', node.dy);
                        card.style.transform = `translate(${node.dx}px, ${node.dy}px)`;
                        if (node.w) card.style.width = node.w + 'px';
                        if (node.h) card.style.height = node.h + 'px';
                    }
                }
            }
            updateTransform();
        }

        // SSE Live Reload Listener
        if (!!window.EventSource) {
            const source = new EventSource('/api/reload');
            source.onmessage = function(e) {
                if (e.data === 'reload') {
                    console.log('[Live-Reload] External update detected -> refreshing layout');
                    window.location.reload();
                }
            };
        }

        window.addEventListener('DOMContentLoaded', () => {
            restoreLayoutState();
            initDraggableNodes();
            drawLines();
        });

        window.addEventListener('resize', drawLines);
    </script>
</body>

</html>
"""

# Write to diagram_arsitektur.html
html_out = Path(r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html")
html_out.write_text(html_template, encoding="utf-8")
print(f"Successfully generated clean complete diagram_arsitektur.html with all 54 nodes, version 15!")
