# 🗄️ Neon PostgreSQL Setup Guide

**Date**: 2026-06-11  
**Status**: ✅ COMPLETED  
**Database**: Neon PostgreSQL (Cloud-hosted)

---

## ✅ Setup Status

### Completed ✅
- [x] Environment variables configured (`.env`)
- [x] Connection tested successfully
- [x] Schema created (10 tables, 7 indexes)
- [x] Insert operations tested
- [x] JSONB fields validated
- [x] UNIQUE constraints tested

### Summary
```
✅ Connection: Successful
✅ Tables: 10 tables created
✅ Indexes: 7 indexes created
✅ Insert Tests: All passed
✅ Database Status: READY FOR PRODUCTION
```

---

## 🔧 Configuration

### Environment Variables (`.env`)
```env
# Neon PostgreSQL Credentials
PGHOST=your_neon_host.neon.tech
PGDATABASE=neondb
PGUSER=your_db_user
PGPASSWORD=your_db_password
PGSSLMODE=require
```

### Database Info
```
Host: your_neon_host.neon.tech
Database: neondb
User: your_db_user
Version: PostgreSQL 17.10
SSL Mode: require (mandatory)
```

---

## 📊 Database Schema

### Track 1: Real-time Tables (6 tables)

#### 1. `realtime_ohlcv`
**Purpose**: Store real-time OHLCV data from MT5 Python API

**Columns**:
- `id` (SERIAL PRIMARY KEY)
- `timestamp` (TIMESTAMP) - Bar timestamp
- `symbol` (VARCHAR) - Trading symbol (e.g., XAUUSD)
- `timeframe` (VARCHAR) - M15, H1, H4
- `open`, `high`, `low`, `close` (DECIMAL)
- `volume` (BIGINT)
- `ema200` (DECIMAL) - EMA200 value
- `source` (VARCHAR) - 'mt5_api'
- `created_at` (TIMESTAMP)
- **UNIQUE**: (timestamp, symbol, timeframe, source)

**Indexes**:
- `idx_realtime_ohlcv_timestamp` (timestamp DESC)

---

#### 2. `realtime_structures`
**Purpose**: Store market structure events detected in real-time

**Columns**:
- `id` (SERIAL PRIMARY KEY)
- `timestamp` (TIMESTAMP)
- `symbol` (VARCHAR)
- `timeframe` (VARCHAR)
- `event_type` (VARCHAR) - CHoCH, BoS, HH, LL
- `direction` (VARCHAR) - Bullish, Bearish
- `price` (DECIMAL)
- `phase` (VARCHAR) - NEUTRAL, CHOCH_PENDING, BOS_CONFIRMED
- `session` (VARCHAR) - London, NewYork, Asia
- `source` (VARCHAR) - 'python_detector'
- `triggered_trade` (BOOLEAN) - Did this event trigger a trade?
- `created_at` (TIMESTAMP)

**Indexes**:
- `idx_realtime_structures_timestamp` (timestamp DESC)
- `idx_realtime_structures_event` (event_type, direction)

---

#### 3. `trades`
**Purpose**: Store executed trades

**Columns**:
- `ticket` (BIGINT PRIMARY KEY) - MT5 ticket number
- `timestamp` (TIMESTAMP)
- `symbol` (VARCHAR)
- `type` (VARCHAR) - BUY, SELL
- `entry_price` (DECIMAL)
- `stop_loss` (DECIMAL)
- `take_profit` (DECIMAL)
- `lot_size` (DECIMAL)
- `consensus_score` (DECIMAL) - Multi-agent consensus
- `agent_votes` (JSONB) - Individual agent votes
- `close_time` (TIMESTAMP)
- `close_price` (DECIMAL)
- `profit` (DECIMAL)
- `outcome` (VARCHAR) - WIN, LOSS

**Indexes**:
- `idx_trades_timestamp` (timestamp DESC)

---

#### 4. `agent_decisions`
**Purpose**: Log all multi-agent decisions

**Columns**:
- `id` (SERIAL PRIMARY KEY)
- `timestamp` (TIMESTAMP)
- `symbol` (VARCHAR)
- `timeframe` (VARCHAR)
- `market_structure` (JSONB) - Market Structure Agent vote
- `ml_prediction` (JSONB) - ML Agent vote
- `risk_analysis` (JSONB) - Risk Management Agent vote
- `sentiment` (JSONB) - Sentiment Agent vote
- `consensus_score` (DECIMAL)
- `final_decision` (VARCHAR) - BUY, SELL, HOLD
- `trade_executed` (BOOLEAN)
- `ticket` (BIGINT) - Link to trades table
- `error` (TEXT)

**Indexes**:
- `idx_agent_decisions_timestamp` (timestamp DESC)

**Example JSONB**:
```json
{
  "signal": "BUY",
  "confidence": 0.85,
  "reasoning": "Confirmed bullish BoS after CHoCH. Price above EMA200."
}
```

---

#### 5. `state_machine`
**Purpose**: Track current market structure state

**Columns**:
- `id` (SERIAL PRIMARY KEY)
- `timestamp` (TIMESTAMP)
- `timeframe` (VARCHAR)
- `phase` (VARCHAR) - Current phase (NEUTRAL, CHOCH_PENDING, etc.)
- `last_hh` (DECIMAL) - Last Higher High
- `last_ll` (DECIMAL) - Last Lower Low
- `choch_detected` (BOOLEAN)
- `bos_detected` (BOOLEAN)
- `metadata` (JSONB) - Additional state info

---

#### 6. `agent_performance`
**Purpose**: Track agent accuracy and performance

**Columns**:
- `id` (SERIAL PRIMARY KEY)
- `date` (DATE)
- `agent_name` (VARCHAR) - Which agent
- `correct_predictions` (INT)
- `total_predictions` (INT)
- `accuracy` (DECIMAL)
- `avg_confidence` (DECIMAL)
- **UNIQUE**: (date, agent_name)

---

### Track 2: Audit Tables (4 tables)

#### 7. `historical_ohlcv_audit`
**Purpose**: Audit trail from CSV exports

**Columns**:
- Same as `realtime_ohlcv` plus:
- `csv_filename` (VARCHAR) - Source CSV file
- `loaded_at` (TIMESTAMP) - When loaded
- `source` (VARCHAR) - 'csv_export'

**Indexes**:
- `idx_historical_audit_timestamp` (timestamp DESC)

---

#### 8. `historical_structures_audit`
**Purpose**: Audit trail of structure events from CSV

**Columns**:
- Similar to `realtime_structures` plus:
- `status` (VARCHAR) - Event status
- `csv_filename` (VARCHAR)
- `loaded_at` (TIMESTAMP)
- `source` (VARCHAR) - 'csv_export'

---

#### 9. `csv_load_log`
**Purpose**: Track CSV file loads

**Columns**:
- `id` (SERIAL PRIMARY KEY)
- `filename` (VARCHAR) - CSV filename
- `file_date` (DATE) - Date from filename
- `rows_loaded` (INT) - How many rows
- `loaded_at` (TIMESTAMP)
- `status` (VARCHAR) - SUCCESS, FAILED, SKIPPED
- `error_message` (TEXT)
- **UNIQUE**: (filename)

**Indexes**:
- `idx_csv_load_date` (file_date DESC)

---

#### 10. `cross_validation`
**Purpose**: Compare Track 1 vs Track 2 data

**Columns**:
- `id` (SERIAL PRIMARY KEY)
- `validation_date` (DATE)
- `timeframe` (VARCHAR)
- `event_type` (VARCHAR)
- `total_realtime` (INT) - Events in Track 1
- `total_csv` (INT) - Events in Track 2
- `matches` (INT)
- `mismatches` (INT)
- `missing_in_realtime` (INT)
- `missing_in_csv` (INT)
- `match_rate` (DECIMAL) - % match
- `avg_price_diff` (DECIMAL) - Average price difference
- `created_at` (TIMESTAMP)
- **UNIQUE**: (validation_date, timeframe)

---

## 🚀 Usage

### 1. Create Schema
```bash
# Windows
cd d:\Project\Project MT5\ValueCell_MT5
run_create_schema.bat

# Or directly
python scripts/create_neon_schema.py
```

**Output**:
```
✅ Connected to Neon PostgreSQL
🔧 Creating schema for DUAL-TRACK SYSTEM...
📊 TRACK 1: Creating real-time tables...
   ✅ Track 1 tables created (6 tables)
📁 TRACK 2: Creating audit tables...
   ✅ Track 2 tables created (4 tables)
🔍 Creating indexes for performance...
   ✅ All indexes created (7 indexes)
✅ All 10 expected tables created successfully!
```

---

### 2. Test Connection
```bash
python scripts/test_neon_connection.py
```

**Expected Output**:
```
✅ PGHOST: ep-green-mud-aijudrlh-pooler.c-4.us-east-1.aws.neon.tech
✅ PGDATABASE: neondb
✅ PGUSER: neondb_owner
✅ PGPASSWORD: npg***********
✅ Connection successful!
📊 Database info:
   Version: PostgreSQL 17.10
   Database: neondb
   User: neondb_owner
```

---

### 3. Test Insert Operations
```bash
python scripts/test_neon_insert.py
```

**Expected Output**:
```
📊 Testing: realtime_ohlcv
   ✅ Inserted row ID: 1
📊 Testing: realtime_structures
   ✅ Inserted row ID: 1
📊 Testing: agent_decisions
   ✅ Inserted row ID: 1
   JSONB fields: MS Signal=BUY, ML Confidence=0.78
✅ ALL INSERT TESTS PASSED!
```

---

## 💻 Python Usage Examples

### Connect to Database
```python
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("PGHOST"),
    database=os.getenv("PGDATABASE"),
    user=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
    sslmode=os.getenv("PGSSLMODE", "require")
)
conn.autocommit = True
```

---

### Insert Real-time OHLCV
```python
with conn.cursor() as cur:
    cur.execute("""
        INSERT INTO realtime_ohlcv (
            timestamp, symbol, timeframe, open, high, low, close, 
            volume, ema200, source
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (timestamp, symbol, timeframe, source) DO NOTHING
    """, (
        datetime.now(),
        "XAUUSD",
        "M15",
        2350.00,
        2351.50,
        2348.50,
        2350.80,
        1523,
        2345.60,
        "mt5_api"
    ))
```

---

### Insert Market Structure Event
```python
with conn.cursor() as cur:
    cur.execute("""
        INSERT INTO realtime_structures (
            timestamp, symbol, timeframe, event_type, direction, 
            price, phase, session, source, triggered_trade
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """, (
        datetime.now(),
        "XAUUSD",
        "M15",
        "BoS",
        "Bullish",
        2350.50,
        "BOS_CONFIRMED",
        "London",
        "python_detector",
        False
    ))
```

---

### Insert Agent Decision (with JSONB)
```python
import psycopg2.extras

with conn.cursor() as cur:
    cur.execute("""
        INSERT INTO agent_decisions (
            timestamp, symbol, timeframe,
            market_structure, ml_prediction, risk_analysis, sentiment,
            consensus_score, final_decision, trade_executed
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """, (
        datetime.now(),
        "XAUUSD",
        "M15",
        psycopg2.extras.Json({"signal": "BUY", "confidence": 0.85}),
        psycopg2.extras.Json({"signal": "BUY", "confidence": 0.78}),
        psycopg2.extras.Json({"signal": "APPROVED", "position_size": 0.01}),
        psycopg2.extras.Json({"signal": "NEUTRAL", "confidence": 0.40}),
        0.67,
        "BUY",
        False
    ))
```

---

### Query JSONB Fields
```python
with conn.cursor() as cur:
    cur.execute("""
        SELECT 
            timestamp,
            final_decision,
            consensus_score,
            market_structure->>'signal' as ms_signal,
            market_structure->>'confidence' as ms_confidence,
            ml_prediction->>'signal' as ml_signal
        FROM agent_decisions
        WHERE final_decision = 'BUY'
        ORDER BY timestamp DESC
        LIMIT 10
    """)
    
    for row in cur.fetchall():
        print(f"{row[0]} | {row[1]} | Consensus: {row[2]} | MS: {row[3]} ({row[4]}) | ML: {row[5]}")
```

---

## 📊 Sample Queries

### Get Recent Structure Events
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
WHERE timeframe = 'M15'
ORDER BY timestamp DESC
LIMIT 20;
```

---

### Get Agent Performance Summary
```sql
SELECT 
    agent_name,
    AVG(accuracy) as avg_accuracy,
    SUM(total_predictions) as total_predictions,
    AVG(avg_confidence) as avg_confidence
FROM agent_performance
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY agent_name
ORDER BY avg_accuracy DESC;
```

---

### Cross-Validation Results
```sql
SELECT 
    validation_date,
    timeframe,
    total_realtime,
    total_csv,
    matches,
    match_rate,
    avg_price_diff
FROM cross_validation
WHERE validation_date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY validation_date DESC;
```

---

### Today's Trading Summary
```sql
SELECT 
    COUNT(*) as total_trades,
    COUNT(CASE WHEN outcome = 'WIN' THEN 1 END) as wins,
    COUNT(CASE WHEN outcome = 'LOSS' THEN 1 END) as losses,
    ROUND(AVG(CASE WHEN outcome = 'WIN' THEN 1.0 ELSE 0.0 END) * 100, 2) as win_rate,
    SUM(profit) as total_profit
FROM trades
WHERE DATE(timestamp) = CURRENT_DATE;
```

---

## 🔍 Troubleshooting

### Connection Failed
**Error**: `psycopg2.OperationalError: could not connect to server`

**Solutions**:
1. Check internet connection
2. Verify credentials in `.env` file
3. Ensure SSL mode is set to `require`
4. Check if Neon database is active (not paused)

---

### SSL Required
**Error**: `SSL connection required`

**Solution**:
```env
PGSSLMODE=require
```

---

### Table Already Exists
**Error**: `relation "realtime_ohlcv" already exists`

**Solution**: This is normal! The `CREATE TABLE IF NOT EXISTS` will skip existing tables.

---

### JSONB Insert Error
**Error**: `can't adapt type 'dict'`

**Solution**: Use `psycopg2.extras.Json()` wrapper:
```python
import psycopg2.extras
cur.execute("INSERT ... VALUES (%s)", (psycopg2.extras.Json({"key": "value"}),))
```

---

## 📝 Notes

### Performance
- All tables have appropriate indexes
- UNIQUE constraints prevent duplicate data
- Timestamps indexed for fast queries
- JSONB fields for flexible agent data

### Security
- SSL connection required (encrypted)
- Credentials stored in `.env` (not committed to git)
- Connection pooler for better performance

### Scaling
- Neon PostgreSQL auto-scales
- Connection pooling built-in
- No manual maintenance required

---

## ✅ Verification Checklist

- [x] Environment variables configured
- [x] Connection test passed
- [x] All 10 tables created
- [x] All 7 indexes created
- [x] Insert operations tested
- [x] JSONB fields working
- [x] UNIQUE constraints working
- [x] Query examples tested

---

## 🎯 Next Steps

1. ✅ **PostgreSQL Setup**: COMPLETE
2. ⏸️ **LanceDB Setup**: Next (vector database for pattern search)
3. ⏸️ **Entry Filter Model**: Continue integration
4. ⏸️ **Main Loop**: Build real-time trading loop

---

**Status**: ✅ NEON POSTGRESQL READY FOR PRODUCTION  
**Last Updated**: 2026-06-11  
**Database**: Operational and tested  
**Phase 1 Progress**: 80% (up from 70%)

