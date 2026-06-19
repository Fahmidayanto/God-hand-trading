# Orchestrator Agent Documentation

## Overview

The **Orchestrator Agent** is the central coordinator in the multi-agent trading system. It orchestrates all 4 specialized agents, applies weighted voting logic, and generates consensus trading decisions.

**Version:** 1.0.0  
**Status:** ✅ Production Ready  
**Location:** `python/valuecell/agents/orchestrator_agent.py`

---

## Architecture

### Agent Hierarchy

```
OrchestratorAgent (Coordinator)
├── 1. MarketStructureAgent (25% weight)
│   └── Detects HH/LL/CHoCH/BoS patterns
├── 2. MLPredictionAgent (40% weight) ⭐ HIGHEST
│   └── Validates signals with ML model
├── 3. SentimentAgent (20% weight)
│   └── Adjusts for news & economic events
└── 4. RiskManagementAgent (15% weight)
    └── Calculates position sizing & SL/TP
```

### Voting Weights

| Agent | Weight | Rationale |
|-------|--------|-----------|
| **ML Prediction** | 40% | Highest accuracy (92.6%), most reliable |
| **Market Structure** | 25% | Foundation signal generator |
| **Sentiment** | 20% | Important for risk management |
| **Risk Management** | 15% | Final safety check |

---

## Workflow (5 Steps)

### Step 1: Market Structure Analysis
- Analyzes price action for structure patterns
- Detects HH/LL, CHoCH, BoS events
- Returns: `BUY`, `SELL`, or `HOLD` signal
- **If HOLD:** Skip to Step 4 (no tradeable signal)

### Step 2: ML Prediction Validation
- **Only runs if Market Structure gave BUY/SELL signal**
- Validates signal against ML model (92.6% accuracy)
- Uses 19 engineered features
- Returns: `BUY`, `SELL`, or `HOLD` (rejection)
- **If HOLD:** ML model rejects structure signal

### Step 3: Sentiment Analysis
- **Only runs if there's a valid signal from Step 1 or 2**
- Analyzes news headlines for market sentiment
- Checks economic calendar for high-impact events
- Adjusts confidence: -15% to +15%
- Filters trades during FOMC, NFP, Powell Speech

### Step 4: Weighted Consensus Calculation
- Aggregates all agent signals
- Applies weighted voting:
  - Each agent vote = `weight × confidence`
  - Example: MS BUY (0.25 × 0.7) + ML HOLD (0.40 × 0.99) = ...
- Determines consensus level:
  - **UNANIMOUS:** 95%+ agreement
  - **STRONG:** 80-94% agreement
  - **MODERATE:** 60-79% agreement
  - **WEAK:** 50-59% agreement
  - **NO_CONSENSUS:** <50% agreement
- **Approval:** Requires ≥60% consensus (configurable)

### Step 5: Risk Management
- **Only runs if consensus approved AND signal is BUY/SELL**
- Calculates dynamic SL/TP based on ATR
- Determines lot size based on risk %
- Can override approval if risk limits exceeded
- Returns position sizing details

---

## Consensus Levels

### Level Definitions

| Level | Consensus | Description |
|-------|-----------|-------------|
| **UNANIMOUS** | 95-100% | All agents strongly agree |
| **STRONG** | 80-94% | High confidence signal |
| **MODERATE** | 60-79% | Good confidence (tradeable) |
| **WEAK** | 50-59% | Low confidence (avoid if possible) |
| **NO_CONSENSUS** | <50% | Conflicting signals (no trade) |

### Example Scenarios

#### Scenario 1: Strong BUY (Approved)
```python
Market Structure: BUY (0.7 confidence)
ML Prediction: BUY (0.85 confidence)
Sentiment: BUY (0.72 confidence, +0.02 adjustment)
Risk Management: Approved

Weighted Scores:
- BUY: (0.25×0.7) + (0.40×0.85) + (0.20×0.72) = 0.659 (65.9%)
- SELL: 0.0
- HOLD: 0.0

Result: BUY | MODERATE consensus (65.9%) | APPROVED ✅
```

#### Scenario 2: Conflicting Signals (Rejected)
```python
Market Structure: BUY (0.7 confidence)
ML Prediction: HOLD (0.99 confidence, probability too low)
Sentiment: (skipped - no valid signal)

Weighted Scores:
- BUY: (0.25×0.7) = 0.175 (17.5%)
- SELL: 0.0
- HOLD: (0.40×0.99) = 0.396 (39.6%)

Result: HOLD | NO_CONSENSUS (46%) | REJECTED ❌
Reason: ML model rejected structure signal
```

#### Scenario 3: FOMC Event Filtering (Rejected)
```python
Market Structure: BUY (0.7 confidence)
ML Prediction: BUY (0.85 confidence)
Sentiment: HOLD (filtered due to FOMC event)

Weighted Scores:
- BUY: (0.25×0.7) + (0.40×0.85) = 0.515 (51.5%)
- HOLD: (0.20×1.0) = 0.200 (20%)

Result: BUY | WEAK consensus (51.5%) | REJECTED ❌
Reason: High-impact event filtering by sentiment agent
```

---

## Configuration

### Initialization Parameters

```python
orchestrator = OrchestratorAgent(
    # Enable/disable agents
    enable_market_structure=True,
    enable_ml_prediction=True,
    enable_risk_management=True,
    enable_sentiment=True,
    
    # Consensus threshold (0-1)
    consensus_threshold=0.60,  # 60% minimum
    
    # Per-agent configuration
    market_structure={
        "swing_length": 5,
        "timeframe": "M15",
        "use_patterns": True
    },
    ml_prediction={
        "probability_threshold": 0.7,
        "min_confidence": 0.6
    },
    risk_management={
        "account_balance": 10000.0,
        "max_risk_pct": 2.0
    },
    sentiment={
        "enable_event_filtering": True,
        "sentiment_threshold": 0.3
    }
)
```

### Recommended Settings

| Setting | Conservative | Balanced | Aggressive |
|---------|-------------|----------|-----------|
| **consensus_threshold** | 0.75 (75%) | 0.60 (60%) | 0.50 (50%) |
| **ML probability_threshold** | 0.80 | 0.70 | 0.60 |
| **Risk max_risk_pct** | 1.0% | 2.0% | 3.0% |
| **Sentiment filtering** | Enabled | Enabled | Disabled |

---

## Input Data Structure

```python
market_data = {
    # Required
    "df": pd.DataFrame,  # OHLCV + indicators (150+ bars)
    "current_bar": {
        "time": datetime,
        "open": float,
        "high": float,
        "low": float,
        "close": float,
        "volume": int
    },
    
    # Optional (for ML agent)
    "structure_events": [
        {"type": "BOS_BULLISH", "price": 2380.0, "time": datetime}
    ],
    "h1_data": pd.DataFrame,  # H1 timeframe data
    "m15_history": pd.DataFrame,  # M15 history
    
    # Optional (for risk agent)
    "atr": float,  # Average True Range
    "session": str,  # "London", "NewYork", "Asia", "Sydney"
    
    # Optional (for sentiment agent)
    "news_headlines": ["Gold rises on inflation concerns"],
    "upcoming_events": [
        {"name": "FOMC", "time": datetime, "impact": "high"}
    ]
}
```

---

## Output Structure

```python
result = {
    # Orchestrator metadata
    "orchestrator": "OrchestratorAgent",
    "version": "1.0.0",
    "timestamp": "2024-01-02T13:15:00",
    "symbol": "XAUUSD",
    "timeframe": "M15",
    "execution_time_ms": 176.57,
    
    # Consensus decision
    "final_signal": "BUY",  # or "SELL", "HOLD"
    "final_confidence": 0.659,  # 0.0 to 1.0
    "consensus_level": "moderate",  # unanimous/strong/moderate/weak/no_consensus
    "approved": True,  # True if consensus ≥ threshold
    "reasoning": "Consensus: moderate (66%). Vote scores: BUY=0.66, SELL=0.00, HOLD=0.00...",
    
    # Vote breakdown
    "vote_scores": {
        "BUY": 0.659,
        "SELL": 0.000,
        "HOLD": 0.000
    },
    
    # Risk decision (if approved)
    "risk_approved": True,
    "position_sizing": {
        "lot_size": 0.28,
        "risk_pct": 2.0,
        "risk_usd": 200.0
    },
    "sl_tp": {
        "entry_price": 2380.0,
        "sl_price": 2366.5,
        "tp_price": 2406.5,
        "sl_distance_pips": 13.5,
        "tp_distance_pips": 26.5,
        "rr_ratio": 1.96
    },
    
    # Individual agent results
    "agent_results": {
        "market_structure": {...},
        "ml_prediction": {...},
        "sentiment": {...},
        "risk_management": {...}
    },
    
    # Configuration
    "active_agents": ["market_structure", "ml_prediction", "risk_management", "sentiment"],
    "consensus_threshold": 0.60
}
```

---

## Performance Metrics

### Execution Time
- **Average:** 170ms per analysis
- **Range:** 130-220ms
- **Breakdown:**
  - Market Structure: 40-60ms
  - ML Prediction: 50-80ms
  - Sentiment: 10-20ms
  - Risk Management: 20-40ms
  - Consensus calculation: 5-10ms

### Resource Usage
- **Memory:** ~150MB (loaded models)
- **CPU:** Single-threaded execution
- **Disk:** Read-only (model loading)

---

## Testing

### Test Suite

**Location:** `scripts/test_orchestrator_agent.py`

**Test Categories:**
1. ✅ Orchestrator Info
2. ✅ Full Workflow (4 agents)
3. ✅ Partial Agents (2 agents)
4. ✅ Consensus Levels
5. ✅ Execution Time
6. ✅ High-Impact News Events

**Run Tests:**
```bash
cd "d:\Project\Project MT5\ValueCell_MT5"
venv\Scripts\activate
python scripts\test_orchestrator_agent.py
```

### Test Results

```
✅ All test categories completed:
   1. Orchestrator Info - PASS
   2. Full Workflow (4 agents) - PASS
   3. Partial Agents (2 agents) - PASS
   4. Consensus Levels - PASS
   5. Execution Time - PASS (avg 169ms)
   6. News Events Impact - PASS
```

---

## Important Notes

### ML Model Validation Behavior

⚠️ **The ML Prediction Agent can reject Market Structure signals!**

This is **correct behavior** when:
- Structure pattern detected BUT ML model predicts very low probability (<0.7)
- This prevents false signals from being traded
- ML model is trained on real historical data (92.6% accuracy)
- Synthetic test data often fails ML validation (expected)

**Example:**
```
Market Structure: BUY (BoS detected, 0.7 confidence)
ML Prediction: HOLD (probability 0.019, below 0.7 threshold)
Result: HOLD wins (ML weight 40% > MS weight 25%)
```

### Consensus Threshold

The **60% consensus threshold** is critical:
- Too low (e.g., 40%): More trades but lower quality
- Too high (e.g., 80%): Fewer trades but higher quality
- **Recommended:** 60% for balanced approach

### Agent Dependencies

```
Market Structure (independent)
    ↓
ML Prediction (depends on MS signal)
    ↓
Sentiment (depends on MS or ML signal)
    ↓
Risk Management (depends on consensus approval)
```

If any upstream agent returns HOLD, downstream agents are skipped.

---

## Integration Example

```python
from valuecell.agents.orchestrator_agent import OrchestratorAgent

# Initialize
orchestrator = OrchestratorAgent(
    consensus_threshold=0.60,
    market_structure={"swing_length": 5, "timeframe": "M15"},
    risk_management={"account_balance": 10000.0}
)

# Prepare market data
market_data = {
    "df": df,  # 150+ bars of OHLCV data
    "current_bar": current_bar_dict,
    "structure_events": structure_events,
    "atr": 7.2,
    "session": "London",
    "news_headlines": recent_news,
    "upcoming_events": economic_calendar
}

# Analyze
result = orchestrator.analyze(
    market_data=market_data,
    symbol="XAUUSD",
    timeframe="M15"
)

# Check decision
if result["approved"] and result["final_signal"] in ["BUY", "SELL"]:
    # Execute trade
    signal = result["final_signal"]
    lot_size = result["position_sizing"]["lot_size"]
    sl_price = result["sl_tp"]["sl_price"]
    tp_price = result["sl_tp"]["tp_price"]
    
    print(f"✅ TRADE APPROVED: {signal}")
    print(f"   Lot: {lot_size:.2f}")
    print(f"   SL: {sl_price:.2f} | TP: {tp_price:.2f}")
    print(f"   Consensus: {result['consensus_level']} ({result['final_confidence']:.1%})")
else:
    print(f"❌ NO TRADE: {result['reasoning']}")
```

---

## Future Enhancements

### Planned Features
1. **Parallel Agent Execution** - Run independent agents concurrently
2. **Dynamic Weight Adjustment** - Adjust weights based on recent performance
3. **Conflict Resolution UI** - Visual display of agent disagreements
4. **Backtesting Integration** - Replay historical data through orchestrator
5. **Performance Tracking** - Track consensus accuracy over time

### Potential Improvements
- Add agent-level timeout handling
- Implement retry logic for failed agents
- Add agent health monitoring
- Support custom voting strategies
- Add agent priority overrides

---

## Troubleshooting

### Issue: Always getting NO_CONSENSUS

**Possible Causes:**
1. ML model rejecting structure signals (check probability threshold)
2. Conflicting agent signals (check individual agent results)
3. Consensus threshold too high (try lowering to 0.50)

**Solution:**
```python
# Lower consensus threshold
orchestrator = OrchestratorAgent(consensus_threshold=0.50)

# Check individual agent results
for agent_name, agent_result in result['agent_results'].items():
    print(f"{agent_name}: {agent_result['signal']} ({agent_result['confidence']})")
```

### Issue: ML always returns HOLD

**Possible Causes:**
1. Using synthetic/test data (not matching real market patterns)
2. ML probability threshold too high
3. Missing required features in input data

**Solution:**
Use real historical data or lower ML threshold:
```python
orchestrator = OrchestratorAgent(
    ml_prediction={"probability_threshold": 0.60}  # Lower from 0.70
)
```

### Issue: Sentiment always filtering trades

**Possible Causes:**
1. High-impact economic events upcoming
2. Conflicting news sentiment
3. Event filtering too aggressive

**Solution:**
```python
# Disable event filtering for testing
orchestrator = OrchestratorAgent(
    sentiment={"enable_event_filtering": False}
)
```

---

## Related Documentation

- [Market Structure Agent](MARKET_STRUCTURE_AGENT.md)
- [ML Prediction Agent](ML_PREDICTION_AGENT.md)
- [Sentiment Agent](SENTIMENT_AGENT.md)
- [Risk Management Agent](RISK_MANAGEMENT_AGENT.md)
- [Implementation Plan](../Dokumen/implementation_plan.md)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-01-02 | Initial production release |

---

**Status:** ✅ PRODUCTION READY  
**Last Updated:** June 11, 2026  
**Maintained By:** ValueCell MT5 Development Team
