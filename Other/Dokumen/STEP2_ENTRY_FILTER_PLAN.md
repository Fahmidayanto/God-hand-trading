# Step 2: Entry Filter Model - Implementation Plan

**Date**: 2026-06-11  
**Previous Step**: ✅ Market Structure Detector (83.3% accuracy)  
**Current Step**: Entry Filter Model  
**Next Step**: Dynamic SL/TP Calculator

---

## 🎯 Goal

Build an **Entry Filter Model** that predicts whether a market structure signal (CHoCH/BoS) will lead to a profitable trade.

**Purpose**: 
- Filter out low-quality signals
- Improve win rate by rejecting risky entries
- Use existing CatBoost model from `AI_Trading_Server/models/`

---

## 📋 Requirements (from implementation_plan.md)

### Input Features
The model needs these features from CSV data:

1. **Market Structure State**:
   - `choch_bullish` / `choch_bearish` (boolean)
   - `bos_bullish` / `bos_bearish` (boolean)
   - `last_hh` / `last_ll` (price levels)
   - `structure_phase` (NEUTRAL, CHOCH_PENDING, BOS_CONFIRMED)

2. **EMA200 Context**:
   - `ema200` (current value)
   - `price_vs_ema` (close - ema200)
   - `ema_distance_pct` ((close - ema200) / ema200 * 100)

3. **Session Info**:
   - `session` (Sydney, Tokyo, London, NewYork, Overlap)
   - `is_dst` (boolean - broker in DST mode)

4. **Price Action**:
   - `candle_body_ratio` (body / range)
   - `spread` (bid-ask spread)
   - Current OHLC

### Output
- **Signal**: BUY / SELL / HOLD
- **Confidence**: 0.0 - 1.0 (model probability)
- **Reasoning**: Feature importance explanation

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  CSV Data Sources                                           │
│  - LLHHBOSData_XAUUSD_YYYY-MM-DD.csv (structure events)    │
│  - MarketData_XAUUSD_M15_YYYY-MM-DD.csv (OHLCV + EMA)      │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│  Feature Engineer                                           │
│  - Load and merge CSV data                                  │
│  - Calculate derived features (EMA distance, session, etc)  │
│  - Create feature vector for model input                    │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│  Entry Filter Model (CatBoost)                              │
│  - Load model: AI_Trading_Server/models/saved/              │
│  - Predict: probability of profitable trade                 │
│  - Threshold: confidence >= 0.6 → PASS                      │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│  Output                                                     │
│  - Signal: BUY/SELL/HOLD                                    │
│  - Confidence: 0.65                                         │
│  - Reasoning: "EMA distance favorable, London session"      │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 File Structure

```
ValueCell_MT5/
├── python/
│   └── valuecell/
│       ├── adapters/
│       │   └── mt5/
│       │       ├── market_structure_detector.py  ✅ (Done)
│       │       ├── entry_filter_model.py         🆕 (New)
│       │       └── __init__.py
│       │
│       └── models/
│           └── saved/  (copy from AI_Trading_Server)
│
└── scripts/
    ├── test_entry_filter.py       🆕 (New - test model)
    └── validate_entry_signals.py  🆕 (New - validate accuracy)
```

---

## 🔧 Implementation Steps

### Step 2.1: Copy Existing Model ✅

Copy trained model from AI_Trading_Server to ValueCell_MT5:

```bash
# Source (existing trained model)
d:\Project\Project MT5\AI_Trading_Server\models\saved\

# Destination (new location)
d:\Project\Project MT5\ValueCell_MT5\python\valuecell\models\saved\
```

**Files to copy**:
- `entry_filter_model.cbm` (CatBoost model)
- `feature_columns.json` (feature names & order)
- `scaler.pkl` (optional - if feature scaling used)

### Step 2.2: Build Feature Engineer 🆕

Create `feature_engineer.py` to transform CSV data into model features:

```python
# valuecell/adapters/mt5/feature_engineer.py

class FeatureEngineer:
    """Transform CSV data into model-ready features."""
    
    def __init__(self):
        self.feature_columns = self._load_feature_columns()
    
    def engineer_features(self, market_data_df, structure_events_df):
        """
        Engineer features from CSV data.
        
        Args:
            market_data_df: DataFrame from MarketData CSV
            structure_events_df: DataFrame from LLHHBOSData CSV
        
        Returns:
            DataFrame with engineered features
        """
        # Merge data
        # Calculate EMA distance
        # Detect session
        # Extract structure state
        # Return feature vector
        pass
```

### Step 2.3: Build Entry Filter Model 🆕

Create `entry_filter_model.py`:

```python
# valuecell/adapters/mt5/entry_filter_model.py

from catboost import CatBoostClassifier
import pandas as pd

class EntryFilterModel:
    """
    Entry filter model using CatBoost.
    
    Predicts if a market structure signal will be profitable.
    """
    
    def __init__(self, model_path: str):
        self.model = CatBoostClassifier()
        self.model.load_model(model_path)
        self.confidence_threshold = 0.6
    
    def predict(self, features: pd.DataFrame) -> dict:
        """
        Predict entry signal quality.
        
        Args:
            features: Engineered features
        
        Returns:
            {
                "signal": "BUY" | "SELL" | "HOLD",
                "confidence": 0.65,
                "probability_buy": 0.65,
                "probability_sell": 0.35,
                "reasoning": "EMA favorable, London session",
                "should_trade": True
            }
        """
        # Run model prediction
        # Apply confidence threshold
        # Generate reasoning
        pass
    
    def explain_prediction(self, features: pd.DataFrame) -> str:
        """Generate human-readable explanation using SHAP or feature importance."""
        pass
```

### Step 2.4: Integration Test 🆕

Test the complete pipeline:

```python
# scripts/test_entry_filter.py

def test_entry_filter_pipeline():
    """Test complete entry filter pipeline."""
    
    # 1. Load CSV data
    market_data = load_csv("MarketData_XAUUSD_M15_2026-06-10.csv")
    structure_events = load_csv("LLHHBOSData_XAUUSD_2026-06-10.csv")
    
    # 2. Engineer features
    engineer = FeatureEngineer()
    features = engineer.engineer_features(market_data, structure_events)
    
    # 3. Load model and predict
    model = EntryFilterModel("valuecell/models/saved/entry_filter_model.cbm")
    prediction = model.predict(features)
    
    # 4. Print results
    print(f"Signal: {prediction['signal']}")
    print(f"Confidence: {prediction['confidence']:.2f}")
    print(f"Reasoning: {prediction['reasoning']}")
    
    assert prediction['signal'] in ['BUY', 'SELL', 'HOLD']
    assert 0.0 <= prediction['confidence'] <= 1.0
```

### Step 2.5: Validation Against Backtest 🆕

Validate model predictions against historical trades:

```python
# scripts/validate_entry_signals.py

def validate_entry_filter():
    """
    Validate entry filter against historical backtest results.
    
    Compare:
    - Model predictions vs actual trade outcomes
    - Filtered signals vs unfiltered signals
    - Win rate improvement
    """
    
    # Load backtest results
    backtest = load_csv("Backtest_Results_XAUUSD_2026-06-10.csv")
    
    # For each trade, predict if it should have been taken
    # Compare with actual profit/loss
    # Calculate metrics:
    #   - Accuracy: % of correct predictions
    #   - Precision: % of BUY/SELL signals that were profitable
    #   - Recall: % of profitable trades that were predicted
    #   - Win rate improvement: filtered vs unfiltered
    
    pass
```

---

## 📊 Expected Metrics

| Metric | Target | Notes |
|--------|--------|-------|
| **Accuracy** | >70% | Correct BUY/SELL/HOLD predictions |
| **Precision** | >65% | Of signals given, % profitable |
| **Recall** | >60% | Of profitable trades, % caught |
| **Win Rate Improvement** | +10-15% | Filtered vs unfiltered |
| **False Positive Rate** | <30% | Bad signals that passed filter |

---

## 🚀 Quick Start Commands

```bash
# 1. Copy existing model
cd d:\Project\Project MT5
xcopy "AI_Trading_Server\models\saved" "ValueCell_MT5\python\valuecell\models\saved\" /E /I

# 2. Activate venv
cd ValueCell_MT5
.\venv\Scripts\activate

# 3. Install CatBoost (if not installed)
pip install catboost

# 4. Run tests
python scripts\test_entry_filter.py
python scripts\validate_entry_signals.py
```

---

## 📝 Notes

### Existing Model Location
```
d:\Project\Project MT5\AI_Trading_Server\models\
├── entry_filter_model.py      (trainer code)
├── model_predictor.py          (predictor code)
└── saved\
    └── entry_filter_model.cbm  (trained model)
```

### Model Training Status
- ✅ Model already trained on historical data
- ✅ Uses CatBoost (fast inference, good for production)
- ✅ Features documented in AI_Trading_Server code
- ⏳ Need to copy to ValueCell_MT5 location

### Integration Points
- **Input**: Market structure events from Step 1
- **Output**: Filtered signals to Risk Management Agent
- **Latency**: <100ms per prediction (CatBoost is fast)

---

## 🎯 Success Criteria

**Step 2 Complete When**:
1. ✅ Model copied to ValueCell_MT5
2. ✅ Feature engineering works with CSV data
3. ✅ Model predicts BUY/SELL/HOLD signals
4. ✅ Confidence scores calculated correctly
5. ✅ Validation shows >70% accuracy
6. ✅ Integration test passes

---

## ⏭️ Next Steps After Step 2

Once Entry Filter Model is complete:
- **Step 3**: Dynamic SL/TP Calculator
- **Step 4**: LangGraph Multi-Agent Orchestrator
- **Step 5**: MT5 Execution Agent

---

**Status**: 📋 Planning Complete  
**Ready to Start**: ✅ Yes  
**Estimated Time**: 4-6 hours  
**Complexity**: Medium (model already trained, just integration)
