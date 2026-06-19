# 📊 PostgreSQL Data Flow - Output yang Disimpan

**Database**: Neon PostgreSQL  
**Total Tables**: 10 tables (Track 1: 6 tables, Track 2: 4 tables)

---

## 🔄 COMPLETE DATA FLOW

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MT5 TERMINAL (XAUUSD Real-time)                  │
│                    - Live price updates setiap tick                 │
│                    - New M15 bars setiap 15 menit                   │
└────────────────────┬────────────────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
   TRACK 1 (Real-time)   TRACK 2 (CSV Backup)
          │                     │
          ▼                     ▼
┌─────────────────────┐  ┌──────────────────────────┐
│  MT5 Python API     │  │  Dev_Bot_v11.cs (MQL5)   │
│  (main.py loop)     │  │  (Export CSV setiap 15min)│
└──────────┬──────────┘  └────────────┬─────────────┘
           │                          │
           ▼                          ▼
  PYTHON DETECTOR              CSV FILES
           │                          │
           ▼                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                    NEON POSTGRESQL DATABASE                      │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  TRACK 1: REAL-TIME TABLES (dari MT5 Python API)       │   │
│  │  • realtime_ohlcv                                        │   │
│  │  • realtime_structures                                   │   │
│  │  • trades                                                │   │
│  │  • agent_decisions                                       │   │
│  │  • state_machine                                         │   │
│  │  • agent_performance                                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  TRACK 2: AUDIT TABLES (dari CSV batch load)           │   │
│  │  • historical_ohlcv_audit                               │   │
│  │  • historical_structures_audit                          │   │
│  │  • csv_load_log                                         │   │
│  │  • cross_validation                                     │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📊 TRACK 1: OUTPUT REAL-TIME (Setiap 5 detik)

### 1. `realtime_ohlcv` - Data Harga Real-time

**Kapan Disimpan**: Setiap kali ada bar baru (M15 setiap 15 menit, H1 setiap jam, H4 setiap 4 jam)

**Contoh Output**:
| id | timestamp | symbol | timeframe | open | high | low | close | volume | ema200 | source |
|----|-----------|--------|-----------|------|------|-----|-------|--------|--------|--------|
| 1 | 2026-06-11 14:45:00 | XAUUSD | M15 | 2350.00 | 2351.50 | 2348.50 | 2350.80 | 1523 | 2345.60 | mt5_api |
| 2 | 2026-06-11 15:00:00 | XAUUSD | M15 | 2350.80 | 2352.30 | 2349.20 | 2351.40 | 1687 | 2345.80 | mt5_api |
| 3 | 2026-06-11 15:15:00 | XAUUSD | M15 | 2351.40 | 2353.00 | 2350.50 | 2352.20 | 1892 | 2346.00 | mt5_api |

**Total Rows per Day**:
- M15: 96 rows/hari (setiap 15 menit)
- H1: 24 rows/hari (setiap jam)
- H4: 6 rows/hari (setiap 4 jam)
- **Total**: ~126 rows/hari untuk 1 simbol

---

### 2. `realtime_structures` - Event Market Structure

**Kapan Disimpan**: Setiap kali detector menemukan HH/LL/CHoCH/BoS

**Contoh Output**:
| id | timestamp | symbol | timeframe | event_type | direction | price | phase | session | triggered_trade |
|----|-----------|--------|-----------|------------|-----------|-------|-------|---------|-----------------|
| 1 | 2026-06-11 14:45:00 | XAUUSD | M15 | CHoCH | Bullish | 2350.50 | CHOCH_PENDING | London | FALSE |
| 2 | 2026-06-11 15:30:00 | XAUUSD | M15 | BoS | Bullish | 2353.20 | BOS_CONFIRMED | London | TRUE |
| 3 | 2026-06-11 16:45:00 | XAUUSD | M15 | HH | Bullish | 2355.80 | BOS_CONFIRMED | London_NY | FALSE |
| 4 | 2026-06-11 17:15:00 | XAUUSD | M15 | CHoCH | Bearish | 2351.20 | CHOCH_PENDING | NewYork | FALSE |

**Total Rows per Day**:
- Rata-rata: 10-20 events/hari (tergantung volatilitas)
- London session: 5-8 events
- NY session: 4-7 events
- Asia session: 1-5 events

---

### 3. `trades` - Record Trading Execution

**Kapan Disimpan**: 
- **Insert**: Saat order di-execute (entry)
- **Update**: Saat position ditutup (close)

**Contoh Output**:
| ticket | timestamp | symbol | type | entry_price | stop_loss | take_profit | lot_size | consensus_score | close_time | close_price | profit | outcome |
|--------|-----------|--------|------|-------------|-----------|-------------|----------|-----------------|------------|-------------|--------|---------|
| 123456789 | 2026-06-11 15:30:00 | XAUUSD | BUY | 2350.50 | 2348.50 | 2354.50 | 0.01 | 0.754 | 2026-06-11 17:15:00 | 2354.50 | +40.00 | WIN |
| 123456790 | 2026-06-11 18:20:00 | XAUUSD | SELL | 2351.80 | 2353.80 | 2347.80 | 0.01 | 0.682 | 2026-06-11 19:45:00 | 2347.80 | +40.00 | WIN |
| 123456791 | 2026-06-11 20:10:00 | XAUUSD | BUY | 2348.20 | 2346.20 | 2352.20 | 0.01 | 0.710 | 2026-06-11 20:35:00 | 2346.20 | -20.00 | LOSS |

**agent_votes** (JSONB column):
```json
{
  "market_structure": {"signal": "BUY", "confidence": 0.85, "reasoning": "Bullish BoS confirmed"},
  "ml_prediction": {"signal": "BUY", "confidence": 0.78, "reasoning": "Model: 78% probability"},
  "risk_management": {"signal": "APPROVED", "confidence": 0.65, "position_size": 0.01},
  "sentiment": {"signal": "NEUTRAL", "confidence": 0.40, "event_risk": "LOW"}
}
```

**Total Rows per Day**:
- Conservative: 2-5 trades/hari
- Moderate: 5-10 trades/hari
- Aggressive: 10-20 trades/hari

---

### 4. `agent_decisions` - Log Semua Keputusan Agent

**Kapan Disimpan**: Setiap kali multi-agent melakukan diskusi (bahkan yang tidak jadi trade)

**Contoh Output**:
| id | timestamp | symbol | timeframe | market_structure | ml_prediction | risk_analysis | sentiment | consensus_score | final_decision | trade_executed | ticket |
|----|-----------|--------|-----------|------------------|---------------|---------------|-----------|-----------------|----------------|----------------|--------|
| 1 | 2026-06-11 15:30:00 | XAUUSD | M15 | `{"signal":"BUY","confidence":0.85}` | `{"signal":"BUY","confidence":0.78}` | `{"signal":"APPROVED","pos":0.01}` | `{"signal":"NEUTRAL","conf":0.40}` | 0.754 | BUY | TRUE | 123456789 |
| 2 | 2026-06-11 16:00:00 | XAUUSD | M15 | `{"signal":"BUY","confidence":0.72}` | `{"signal":"HOLD","confidence":0.55}` | `{"signal":"REJECTED","reason":"spread"}` | `{"signal":"NEUTRAL","conf":0.45}` | 0.580 | HOLD | FALSE | NULL |
| 3 | 2026-06-11 16:30:00 | XAUUSD | M15 | `{"signal":"BUY","confidence":0.88}` | `{"signal":"BUY","confidence":0.85}` | `{"signal":"HOLD","reason":"max_position"}` | `{"signal":"NEUTRAL","conf":0.50}` | 0.730 | HOLD | FALSE | NULL |

**Purpose**:
- Log SEMUA diskusi agent (yang execute maupun tidak)
- Untuk debugging: "Kenapa agent tidak trade?"
- Untuk learning: "Pattern apa yang sering di-reject?"
- Untuk analytics: "Agent mana yang paling akurat?"

**Total Rows per Day**:
- Setiap market structure event → 1 decision
- Rata-rata: 15-30 decisions/hari
- Executed: 20-30% dari total decisions

---

### 5. `state_machine` - Tracking State Market

**Kapan Disimpan**: Setiap kali state berubah (NEUTRAL → CHOCH_PENDING → BOS_CONFIRMED)

**Contoh Output**:
| id | timestamp | timeframe | phase | last_hh | last_ll | choch_detected | bos_detected | metadata |
|----|-----------|-----------|-------|---------|---------|----------------|--------------|----------|
| 1 | 2026-06-11 14:45:00 | M15 | CHOCH_PENDING | 2352.80 | 2347.20 | TRUE | FALSE | `{"bars_since_choch":0}` |
| 2 | 2026-06-11 15:30:00 | M15 | BOS_CONFIRMED | 2355.20 | 2347.20 | TRUE | TRUE | `{"bars_since_bos":0}` |
| 3 | 2026-06-11 17:15:00 | M15 | NEUTRAL | 2355.20 | 2349.80 | FALSE | FALSE | `{"waiting_for_signal"}` |

**Purpose**:
- Track current market phase
- Prevent duplicate signals
- Context untuk multi-agent discussion

**Total Rows per Day**:
- Rata-rata: 8-15 state changes/hari

---

### 6. `agent_performance` - Tracking Akurasi Agent

**Kapan Disimpan**: End of day (00:00) - summary harian

**Contoh Output**:
| id | date | agent_name | correct_predictions | total_predictions | accuracy | avg_confidence |
|----|------|------------|---------------------|-------------------|----------|----------------|
| 1 | 2026-06-11 | market_structure | 7 | 10 | 0.70 | 0.82 |
| 2 | 2026-06-11 | ml_prediction | 6 | 10 | 0.60 | 0.75 |
| 3 | 2026-06-11 | risk_management | 8 | 10 | 0.80 | 0.68 |
| 4 | 2026-06-11 | sentiment | 5 | 10 | 0.50 | 0.45 |

**Purpose**:
- Monitor agent accuracy over time
- Auto-adjust agent weights (jika accuracy turun)
- Identify underperforming agents

**Total Rows per Day**:
- 4 rows/hari (1 per agent)
- 120 rows/bulan

---

## 📁 TRACK 2: AUDIT OUTPUT (Batch load harian)

### 7. `historical_ohlcv_audit` - Backup CSV OHLCV

**Kapan Disimpan**: Daily at 00:05 (load yesterday's CSV)

**Contoh Output**: Sama seperti `realtime_ohlcv` tapi:
- `source` = 'csv_export'
- `csv_filename` = 'MarketData_XAUUSD_M15_2026-06-10.csv'
- `loaded_at` = '2026-06-11 00:05:23'

**Purpose**: 
- Audit trail untuk compliance
- Cross-validate dengan Track 1
- Backup jika Track 1 ada issue

**Total Rows per Day**:
- Same as Track 1: ~126 rows/hari

---

### 8. `historical_structures_audit` - Backup CSV Structure Events

**Kapan Disimpan**: Daily at 00:05

**Contoh Output**: Sama seperti `realtime_structures` tapi dari CSV

**Purpose**: Compare Python detector vs MQL5 detector

**Total Rows per Day**:
- Rata-rata: 10-20 events/hari

---

### 9. `csv_load_log` - Track CSV Loading

**Kapan Disimpan**: Daily at 00:05 (setelah load CSV)

**Contoh Output**:
| id | filename | file_date | rows_loaded | loaded_at | status | error_message |
|----|----------|-----------|-------------|-----------|--------|---------------|
| 1 | MarketData_XAUUSD_M15_2026-06-10.csv | 2026-06-10 | 96 | 2026-06-11 00:05:23 | SUCCESS | NULL |
| 2 | LLHHBOSData_XAUUSD_2026-06-10.csv | 2026-06-10 | 18 | 2026-06-11 00:05:25 | SUCCESS | NULL |
| 3 | MarketData_XAUUSD_H1_2026-06-10.csv | 2026-06-10 | 24 | 2026-06-11 00:05:27 | SUCCESS | NULL |

**Purpose**: Monitor CSV load pipeline

**Total Rows per Day**:
- 4 rows/hari (4 CSV files)

---

### 10. `cross_validation` - Compare Track 1 vs Track 2

**Kapan Disimpan**: Daily at 00:10 (after CSV load)

**Contoh Output**:
| id | validation_date | timeframe | event_type | total_realtime | total_csv | matches | mismatches | match_rate | avg_price_diff |
|----|-----------------|-----------|------------|----------------|-----------|---------|------------|------------|----------------|
| 1 | 2026-06-10 | M15 | ALL | 18 | 18 | 17 | 1 | 0.944 | 0.3 |
| 2 | 2026-06-10 | M15 | BoS | 5 | 5 | 5 | 0 | 1.000 | 0.0 |
| 3 | 2026-06-10 | M15 | CHoCH | 7 | 7 | 6 | 1 | 0.857 | 0.5 |

**Purpose**: 
- Validate Python detector accuracy
- Alert if match rate < 95%
- Identify systematic differences

**Total Rows per Day**:
- 3-4 rows/hari (per timeframe/event type)

---

## 📊 TOTAL DATA VOLUME ESTIMATE

### Per Day (1 Symbol - XAUUSD):
```
Track 1 (Real-time):
  realtime_ohlcv:           ~126 rows/hari
  realtime_structures:       ~15 rows/hari
  trades:                     ~5 rows/hari
  agent_decisions:           ~25 rows/hari
  state_machine:             ~12 rows/hari
  agent_performance:          ~4 rows/hari
  Subtotal Track 1:         ~187 rows/hari

Track 2 (Audit):
  historical_ohlcv_audit:   ~126 rows/hari
  historical_structures_audit: ~15 rows/hari
  csv_load_log:               ~4 rows/hari
  cross_validation:           ~4 rows/hari
  Subtotal Track 2:         ~149 rows/hari

TOTAL PER DAY:              ~336 rows/hari
```

### Per Month (30 days):
```
Total rows: ~10,080 rows/bulan
Storage: ~5-10 MB/bulan (compressed)
```

### Per Year:
```
Total rows: ~122,640 rows/tahun
Storage: ~60-120 MB/tahun
```

**Neon Free Tier**: 10 GB storage → Cukup untuk 80-160 tahun data! 🎉

---

## 📈 EXAMPLE: 1 Trading Day Full Flow

### Morning (08:00-12:00 London Open):
```sql
-- 1. OHLCV data masuk setiap 15 menit
INSERT INTO realtime_ohlcv (96 rows for M15)

-- 2. Detector menemukan pattern
INSERT INTO realtime_structures 
  (08:15) CHoCH Bullish detected
  (09:30) BoS Bullish confirmed
  (10:45) HH detected

-- 3. Multi-agent diskusi
INSERT INTO agent_decisions
  (09:30) BUY signal - consensus 0.75 - EXECUTED → ticket #123456789
  (10:00) BUY signal - consensus 0.62 - REJECTED (spread too high)
  (11:15) HOLD - consensus 0.55 - NOT EXECUTED

-- 4. Trade executed
INSERT INTO trades (ticket #123456789, entry 2350.50)

-- 5. State machine update
UPDATE state_machine SET phase = 'BOS_CONFIRMED'
```

### Afternoon (12:00-17:00 London-NY Overlap):
```sql
-- Trade monitoring
-- Position closed at TP
UPDATE trades SET close_time='15:45', profit=+40.00, outcome='WIN'

-- More structure events
INSERT INTO realtime_structures (3 more events)

-- More agent decisions
INSERT INTO agent_decisions (5 more decisions, 2 executed)
```

### Evening (17:00-00:00):
```sql
-- End of day summary
INSERT INTO agent_performance (4 rows, 1 per agent)

-- Lower volume
INSERT INTO realtime_ohlcv (continued)
INSERT INTO realtime_structures (1-2 events)
```

### Midnight (00:00-00:30):
```sql
-- CSV batch load (Track 2)
python csv_to_db_loader.py

-- Load yesterday's CSV files
INSERT INTO historical_ohlcv_audit (126 rows from CSV)
INSERT INTO historical_structures_audit (15 rows from CSV)
INSERT INTO csv_load_log (4 rows - load status)

-- Cross-validation
INSERT INTO cross_validation (compare Track 1 vs Track 2)
  Result: 95% match rate ✅
```

---

## 🔍 QUERY EXAMPLES - Apa yang Bisa Dilihat

### 1. Trading Summary Hari Ini:
```sql
SELECT 
    COUNT(*) as total_trades,
    COUNT(CASE WHEN outcome = 'WIN' THEN 1 END) as wins,
    COUNT(CASE WHEN outcome = 'LOSS' THEN 1 END) as losses,
    ROUND(AVG(CASE WHEN outcome = 'WIN' THEN 1.0 ELSE 0.0 END) * 100, 2) as win_rate,
    SUM(profit) as total_profit,
    AVG(consensus_score) as avg_consensus
FROM trades
WHERE DATE(timestamp) = CURRENT_DATE;
```

**Output**:
```
total_trades: 5
wins: 3
losses: 2
win_rate: 60.00%
total_profit: +60.00
avg_consensus: 0.712
```

---

### 2. Agent Performance Last 7 Days:
```sql
SELECT 
    agent_name,
    AVG(accuracy) as avg_accuracy,
    SUM(total_predictions) as total_predictions,
    AVG(avg_confidence) as avg_confidence
FROM agent_performance
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY agent_name
ORDER BY avg_accuracy DESC;
```

**Output**:
```
agent_name          | avg_accuracy | total_predictions | avg_confidence
--------------------|--------------|-------------------|---------------
risk_management     | 0.75         | 70                | 0.68
market_structure    | 0.72         | 70                | 0.83
ml_prediction       | 0.68         | 70                | 0.76
sentiment           | 0.52         | 70                | 0.43
```

---

### 3. Recent Structure Events:
```sql
SELECT 
    timestamp,
    event_type,
    direction,
    price,
    phase,
    session,
    triggered_trade
FROM realtime_structures
WHERE timestamp >= NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC;
```

**Output**:
```
timestamp           | event_type | direction | price   | phase          | session   | triggered_trade
--------------------|------------|-----------|---------|----------------|-----------|----------------
2026-06-11 15:30:00 | BoS        | Bullish   | 2353.20 | BOS_CONFIRMED  | London    | TRUE
2026-06-11 14:45:00 | CHoCH      | Bullish   | 2350.50 | CHOCH_PENDING  | London    | FALSE
2026-06-11 12:15:00 | HH         | Bullish   | 2355.80 | BOS_CONFIRMED  | London    | FALSE
```

---

### 4. Why Was This Signal Rejected?
```sql
SELECT 
    timestamp,
    final_decision,
    consensus_score,
    market_structure->>'signal' as ms_signal,
    ml_prediction->>'signal' as ml_signal,
    risk_analysis->>'signal' as risk_signal,
    risk_analysis->>'reason' as rejection_reason
FROM agent_decisions
WHERE final_decision = 'HOLD'
  AND trade_executed = FALSE
ORDER BY timestamp DESC
LIMIT 10;
```

**Output**:
```
timestamp           | final_decision | consensus | ms_signal | ml_signal | risk_signal | rejection_reason
--------------------|----------------|-----------|-----------|-----------|-------------|------------------
2026-06-11 16:30:00 | HOLD           | 0.730     | BUY       | BUY       | HOLD        | max_position_reached
2026-06-11 16:00:00 | HOLD           | 0.580     | BUY       | HOLD      | REJECTED    | spread_too_high
2026-06-11 14:15:00 | HOLD           | 0.650     | BUY       | BUY       | REJECTED    | daily_loss_limit
```

---

### 5. Cross-Validation Results:
```sql
SELECT 
    validation_date,
    timeframe,
    total_realtime,
    total_csv,
    matches,
    match_rate,
    CASE 
        WHEN match_rate >= 0.95 THEN '✅ Excellent'
        WHEN match_rate >= 0.90 THEN '⚠️ Warning'
        ELSE '❌ Critical'
    END as status
FROM cross_validation
WHERE validation_date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY validation_date DESC;
```

**Output**:
```
validation_date | timeframe | total_realtime | total_csv | matches | match_rate | status
----------------|-----------|----------------|-----------|---------|------------|-------------
2026-06-10      | M15       | 18             | 18        | 17      | 0.944      | ⚠️ Warning
2026-06-09      | M15       | 20             | 20        | 20      | 1.000      | ✅ Excellent
2026-06-08      | M15       | 15             | 15        | 14      | 0.933      | ⚠️ Warning
```

---

## 💡 SUMMARY

### Apa yang Disimpan ke PostgreSQL:

1. **Real-time Market Data** (OHLCV setiap bar)
2. **Market Structure Events** (HH/LL/CHoCH/BoS)
3. **Trading Records** (Entry, Exit, Profit/Loss)
4. **Agent Decisions** (Semua diskusi agent, bahkan yang tidak execute)
5. **Market State** (Current phase tracker)
6. **Agent Performance** (Daily accuracy tracking)
7. **CSV Audit Trail** (Backup dari Dev_Bot)
8. **Cross-Validation** (Comparison Track 1 vs Track 2)

### Kenapa Ini Penting:

✅ **Debugging**: "Kenapa trade ini loss?"  
✅ **Learning**: "Pattern apa yang paling profitable?"  
✅ **Compliance**: Audit trail untuk regulator  
✅ **Performance**: Track agent accuracy over time  
✅ **Optimization**: Identify best sessions/patterns  
✅ **Accountability**: Record setiap keputusan agent

### Volume Data:

```
Per Hari: ~336 rows (~1-2 MB)
Per Bulan: ~10,080 rows (~5-10 MB)
Per Tahun: ~122,640 rows (~60-120 MB)
```

**Kesimpulan**: Database akan penuh dengan data trading yang sangat lengkap! 🚀

