# 🚀 QUICK REFERENCE: Multi-Agent Trading System

**Updated**: June 10, 2026  
**Framework**: LangGraph + Neon PostgreSQL  
**Status**: Ready for Implementation

---

## 📦 TECH STACK

| Component | Technology | Version |
|-----------|-----------|---------|
| **Multi-Agent Framework** | LangGraph | 0.2.0 |
| **LLM Provider** | Anthropic Claude | claude-3-5-sonnet-20241022 |
| **Vector Database** | LanceDB | 0.5.0 |
| **Relational Database** | Neon PostgreSQL | Cloud (Neon) |
| **ML Model** | CatBoost | 1.2.2 |
| **MT5 Integration** | MetaTrader5 Python | 5.0.45 |
| **News API** | NewsAPI.org | Free tier (MVP) |

---

## 🔑 ENVIRONMENT VARIABLES

Copy to your `.env` file:

```bash
# LLM Provider
ANTHROPIC_API_KEY=your_anthropic_key_here

# Neon PostgreSQL
PGHOST=ep-green-mud-aijudrlh-pooler.c-4.us-east-1.aws.neon.tech
PGDATABASE=neondb
PGUSER=neondb_owner
PGPASSWORD=npg_gel7WiRj8NCM
PGSSLMODE=require

# Sentiment Agent
NEWS_API_KEY=your_newsapi_key_here

# Notifications
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

---

## 📂 KEY FILES

### Core Implementation Files to Create:

```
ValueCell_MT5/
├── orchestration/
│   └── langgraph_orchestrator.py    # LangGraph workflow (500 lines)
│
├── knowledge/
│   └── relational_db.py              # Neon PostgreSQL integration (200 lines)
│
├── agents/
│   ├── market_structure_agent.py    # HH/LL/CHoCH/BoS analysis
│   ├── ml_prediction_agent.py       # CatBoost integration
│   ├── risk_management_agent.py     # Position sizing, SL/TP
│   ├── sentiment_agent.py           # News + economic calendar
│   └── execution_agent.py           # MT5 order execution
│
├── adapters/
│   ├── mt5_adapter.py               # CSV watcher + MT5 API
│   └── csv_watcher.py               # Real-time CSV monitoring
│
├── config/
│   ├── settings.yaml                # System configuration
│   ├── agent_weights.yaml           # Consensus weights
│   └── .env                         # Secrets (DO NOT COMMIT)
│
└── main.py                          # Entry point
```

---

## 🏗️ LANGGRAPH WORKFLOW

```python
# 8-Node State Machine

[validate_data] → [market_structure] → [ml_prediction] 
      ↓                                        ↓
   (reject)                            [risk_management]
      ↓                                        ↓
[log_decision]                          [sentiment]
                                               ↓
                                         [consensus]
                                          ↓      ↓
                                    (execute) (skip)
                                          ↓      ↓
                                   [execute_trade]
                                          ↓
                                   [log_decision]
                                          ↓
                                        (END)
```

### Conditional Routing:
1. **After validation**: Reject if data is stale/invalid
2. **After consensus**: Execute if score >= 0.70, skip otherwise
3. **Event blocking**: Skip if high-impact event detected

---

## 🎯 AGENT WEIGHTS (CONSENSUS)

| Agent | Weight | Role |
|-------|--------|------|
| **Market Structure** | 0.35 | Primary signal (HH/LL/CHoCH/BoS) |
| **ML Prediction** | 0.30 | CatBoost model probability |
| **Risk Management** | 0.20 | Position sizing validation |
| **Sentiment** | 0.15 | News + event risk (MVP: simplified) |

**Consensus Threshold**: 0.70 (adjustable in settings.yaml)

---

## 🗄️ NEON POSTGRESQL TABLES

### 1. `trades` (Trade Execution Records)
```sql
ticket BIGINT PRIMARY KEY
timestamp TIMESTAMP
symbol VARCHAR(10)
type VARCHAR(10)        -- BUY/SELL
entry_price DECIMAL(10,2)
stop_loss DECIMAL(10,2)
take_profit DECIMAL(10,2)
lot_size DECIMAL(10,2)
consensus_score DECIMAL(5,4)
agent_votes JSONB
close_time TIMESTAMP
close_price DECIMAL(10,2)
profit DECIMAL(10,2)
outcome VARCHAR(20)     -- WIN/LOSS/BREAKEVEN
```

### 2. `agent_decisions` (All Agent Discussions)
```sql
id SERIAL PRIMARY KEY
timestamp TIMESTAMP
symbol VARCHAR(10)
timeframe VARCHAR(10)
market_structure JSONB
ml_prediction JSONB
risk_analysis JSONB
sentiment JSONB
consensus_score DECIMAL(5,4)
final_decision VARCHAR(20)
trade_executed BOOLEAN
ticket BIGINT
error TEXT
```

### 3. `state_machine` (Market Structure State)
```sql
id SERIAL PRIMARY KEY
timestamp TIMESTAMP
timeframe VARCHAR(10)
phase VARCHAR(50)       -- NEUTRAL/CHOCH_PENDING/BOS_CONFIRMED
last_hh DECIMAL(10,2)
last_ll DECIMAL(10,2)
choch_detected BOOLEAN
bos_detected BOOLEAN
metadata JSONB
```

### 4. `agent_performance` (Accuracy Tracking)
```sql
id SERIAL PRIMARY KEY
date DATE
agent_name VARCHAR(50)
correct_predictions INT
total_predictions INT
accuracy DECIMAL(5,4)
avg_confidence DECIMAL(5,4)
```

---

## 🚀 QUICK START COMMANDS

### Step 1: Setup Environment
```bash
# Clone and setup
cd d:/Project/Project MT5/ValueCell_MT5
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env with your credentials
```

### Step 2: Initialize Database
```python
# Run in Python
from knowledge.relational_db import RelationalDB

db = RelationalDB()
db.init_schema()  # Creates 4 tables in Neon
print("✅ Database initialized")
```

### Step 3: Test LangGraph
```python
from orchestration.langgraph_orchestrator import TradingOrchestrator

orchestrator = TradingOrchestrator()
orchestrator.visualize_graph()  # Creates workflow diagram
print("✅ LangGraph ready")
```

### Step 4: Load Historical Data
```python
# Load CSV files into LanceDB
python scripts/init_knowledge_base.py
```

### Step 5: Start System
```bash
# Paper trading mode
python main.py --mode paper

# Live trading (after testing)
python main.py --mode live
```

---

## 📊 MONITORING COMMANDS

### Check Database
```python
from knowledge.relational_db import RelationalDB

db = RelationalDB()

# Get recent trades
trades = db.get_recent_trades(limit=10)

# Get agent performance (last 30 days)
performance = db.get_agent_performance("market_structure", days=30)

# Get today's decisions
decisions = db.get_decisions_by_date("2026-06-10")
```

### Check LangGraph Checkpoints
```python
from orchestration.langgraph_orchestrator import TradingOrchestrator

orchestrator = TradingOrchestrator()
config = {"configurable": {"thread_id": "event_12345"}}

# List checkpoints
checkpoints = orchestrator.checkpointer.list(config)
print(f"Found {len(checkpoints)} checkpoints")

# Resume from last checkpoint (after crash)
final_state = orchestrator.graph.invoke(None, config)
```

### View Graph Visualization
```python
orchestrator.visualize_graph()
# Opens: ./docs/langgraph_workflow.png
```

---

## 🛡️ SAFETY LIMITS (DEFAULT)

| Parameter | Value | Location |
|-----------|-------|----------|
| **Max Risk Per Trade** | 2% | risk_params.yaml |
| **Max Daily Loss** | 3% | risk_params.yaml |
| **Max Open Positions** | 3 | risk_params.yaml |
| **Min Risk/Reward** | 1.0 | risk_params.yaml |
| **Max Spread** | 5 pips | risk_params.yaml |
| **Consensus Threshold** | 0.70 | settings.yaml |

---

## 📱 TELEGRAM COMMANDS

Send to your bot:

```
/status       - System status
/balance      - Account balance
/positions    - Open positions
/performance  - Today's P&L
/agents       - Agent accuracy
/stop         - Emergency stop (close all positions)
/resume       - Resume trading
```

---

## 🔧 TROUBLESHOOTING

### Database Connection Error
```python
# Test Neon connection
import psycopg2
conn = psycopg2.connect(
    host=os.getenv("PGHOST"),
    database=os.getenv("PGDATABASE"),
    user=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
    sslmode=os.getenv("PGSSLMODE")
)
print("✅ Connected to Neon PostgreSQL")
```

### LangGraph Not Loading
```bash
# Reinstall dependencies
pip uninstall langgraph langchain langchain-anthropic
pip install langgraph==0.2.0 langchain==0.1.0 langchain-anthropic==0.1.0
```

### MT5 Connection Issues
```python
import MetaTrader5 as mt5

if not mt5.initialize():
    print("❌ MT5 initialization failed")
    print(f"Error: {mt5.last_error()}")
else:
    print("✅ MT5 connected")
    print(f"Version: {mt5.version()}")
```

### CSV Watcher Not Detecting Files
```python
# Check CSV path
import os
csv_path = "d:/Project/Project MT5/Backtest_result"
files = os.listdir(csv_path)
print(f"Found {len(files)} files")

# Check latest file timestamp
latest = max([os.path.getmtime(f"{csv_path}/{f}") for f in files])
print(f"Latest file modified: {datetime.fromtimestamp(latest)}")
```

---

## 📈 EXPECTED PERFORMANCE (MVP TARGETS)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Win Rate** | 60%+ | After 100 trades |
| **Profit Factor** | 1.5+ | Gross profit / gross loss |
| **Avg R-multiple** | 1.5R+ | Average win / average loss |
| **Max Drawdown** | <15% | Peak to trough decline |
| **Sharpe Ratio** | 1.2+ | Risk-adjusted returns |
| **Agent Response Time** | <2s | Consensus calculation |
| **System Uptime** | >99.5% | Weekly average |

---

## 📚 KEY DOCUMENTATION

### Implementation Plan
- **File**: `d:\Project\Project MT5\Dokumen\implementation_plan.md`
- **Lines**: 2172
- **Sections**: Architecture, Agents, LangGraph, Configuration, Roadmap

### Changelog
- **File**: `d:\Project\Project MT5\Dokumen\CHANGELOG_LANGGRAPH_NEON.md`
- **Content**: Detailed migration from SQLite+CrewAI to Neon+LangGraph

### External Resources
- **LangGraph**: https://langchain-ai.github.io/langgraph/
- **Neon PostgreSQL**: https://neon.tech/docs/
- **MT5 Python API**: https://www.mql5.com/en/docs/python_metatrader5
- **NewsAPI**: https://newsapi.org/docs

---

## ⏱️ IMPLEMENTATION TIMELINE

### Week 1-2: Foundation
- Setup project structure
- Implement MT5 CSV watcher
- Initialize Neon PostgreSQL schema
- Setup LanceDB collections

### Week 3-4: Core Agents
- Build Market Structure Agent
- Integrate CatBoost (ML Agent)
- Build Risk Management Agent
- Build Sentiment Agent (MVP)
- Implement LangGraph orchestrator

### Week 5-6: Execution
- Build Execution Agent (MT5 API)
- Position monitoring
- Paper trading tests
- Load historical data

### Week 7: Safety & Monitoring
- Circuit breakers
- Error handling
- Telegram notifications
- Dashboard setup

### Week 8-9: Testing
- Backtest (2023-2026)
- Paper trading (2 weeks)
- Optimize weights
- Performance analysis

### Week 10: Production
- Live trading (small capital)
- Daily monitoring
- Performance tracking
- Documentation finalization

---

## 🎯 QUICK CHECKLIST

### Before Starting Development:
- [ ] Review implementation_plan.md
- [ ] Understand LangGraph workflow
- [ ] Neon PostgreSQL credentials ready
- [ ] Anthropic API key ready
- [ ] NewsAPI key ready (free tier)
- [ ] MT5 Python API enabled
- [ ] Dev_Bot_v11.cs deployed (detection only)

### Before Testing:
- [ ] Database schema created
- [ ] LanceDB collections initialized
- [ ] Historical CSV data loaded
- [ ] Agent weights configured
- [ ] Risk limits configured
- [ ] Telegram bot setup
- [ ] Paper trading mode active

### Before Going Live:
- [ ] Backtest results reviewed (90+ days)
- [ ] Paper trading results reviewed (14+ days)
- [ ] All safety limits tested
- [ ] Emergency stop tested
- [ ] Monitoring dashboard operational
- [ ] Notifications working
- [ ] Documentation complete

---

**Status**: ✅ READY FOR IMPLEMENTATION  
**Next Action**: Start Week 1 (Foundation)  
**Contact**: Review implementation_plan.md for full details

---

_Last Updated: June 10, 2026_
