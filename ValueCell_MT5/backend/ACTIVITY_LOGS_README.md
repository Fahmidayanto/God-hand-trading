# Activity Logs System - Documentation

## Overview

The Activity Logs System provides comprehensive event tracking and aggregation for the ValueCell MT5 trading platform. It collects events from multiple sources and presents them through a unified REST API.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Activity Logs API                         │
│              GET /api/v1/activity-logs                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              ActivityLogService                              │
│          (In-memory cache: 200 events)                       │
└──┬────────────┬────────────┬────────────┬───────────────────┘
   │            │            │            │
   ▼            ▼            ▼            ▼
┌────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐
│Signal  │ │Structure│ │Position  │ │System   │
│Collect.│ │Collect. │ │Collect.  │ │Collect. │
└────┬───┘ └────┬────┘ └────┬─────┘ └────┬────┘
     │          │            │            │
     ▼          ▼            ▼            ▼
  ┌──────┐  ┌──────┐    ┌──────┐    ┌──────┐
  │ CSV  │  │ CSV  │    │ MT5  │    │Memory│
  │Files │  │Files │    │ API  │    │Queue │
  └──────┘  └──────┘    └──────┘    └──────┘
```

## Components

### 1. Models (`app/models/activity_log.py`)

#### ActivityLog
Main model representing an activity log entry:

```python
{
    "id": "SIGNAL_20260505_131500_001",
    "timestamp": "2026-05-05T13:15:00Z",
    "event_id": "SMC_20260505_131500_SELL",
    "event_type": "SIGNAL_GENERATED",
    "severity": "INFO",
    "icon": "TrendingDown",
    "title": "SELL Signal Generated",
    "message": "New SELL signal for XAUUSD at 4553.16 with 75.58% confidence",
    "metadata": {
        "symbol": "XAUUSD",
        "direction": "SELL",
        "entry_price": 4553.16,
        "confidence": 75.58,
        "tier": "GOOD"
    }
}
```

#### EventType Enum
- **Signal Events**: `SIGNAL_GENERATED`, `SIGNAL_EXECUTED`, `SIGNAL_CLOSED`
- **Structure Events**: `STRUCTURE_CHOCH`, `STRUCTURE_BOS`, `STRUCTURE_LL`, `STRUCTURE_HH`
- **Position Events**: `POSITION_OPENED`, `POSITION_CLOSED`, `POSITION_MODIFIED`
- **Trade Events**: `TRADE_WIN`, `TRADE_LOSS`, `TRADE_BREAKEVEN`
- **System Events**: `SYSTEM_STARTUP`, `SYSTEM_SHUTDOWN`, `SYSTEM_ERROR`, `SYSTEM_WARNING`, `SYSTEM_INFO`

#### SeverityLevel Enum
- `INFO` - General information
- `SUCCESS` - Successful operations
- `WARNING` - Warning conditions
- `ERROR` - Error conditions

### 2. Event Collectors

#### SignalCollector (`signal_collector.py`)
- **Source**: `AI_Trading_Server/integrations/live_signals_log.csv`
- **Events**: Trading signals with outcomes
- **Features**:
  - Parses signal generation and closure events
  - Tracks WIN/LOSS outcomes
  - Extracts confidence, tier, SL/TP levels
  - ISO timestamp parsing with timezone handling

#### StructureCollector (`structure_collector.py`)
- **Source**: `Backtest_result/LLHHBOSData_XAUUSD_*.csv`
- **Events**: Market structure changes (CHoCH, BoS, LL, HH)
- **Features**:
  - Parses multiple backtest result files
  - Handles custom CSV format with header skipping
  - Limits to 3 most recent files for performance
  - Extracts price levels and timeframes

#### PositionCollector (`position_collector.py`)
- **Source**: MT5 API (via MT5Manager)
- **Events**: Position open/close events
- **Features**:
  - Real-time position monitoring
  - Profit/loss tracking
  - Duplicate detection via ticket tracking
  - Falls back gracefully if MT5 unavailable

#### SystemCollector (`system_collector.py`)
- **Source**: In-memory event queue
- **Events**: System-level events
- **Features**:
  - In-memory deque with configurable size
  - Convenience methods: `log_info()`, `log_warning()`, `log_error()`
  - Startup event auto-logging
  - Thread-safe event appending

### 3. ActivityLogService (`activity_log_service.py`)

Central service for log aggregation and management.

**Features**:
- In-memory caching (deque with 200 max size)
- Multi-source aggregation
- Automatic deduplication by ID
- Timestamp-based sorting (newest first)
- Filtering by event type and severity
- Cache statistics tracking

**Key Methods**:

```python
# Get recent logs from all sources
logs = service.get_recent_logs(limit=50, since=datetime, refresh_cache=False)

# Filter by event type
logs = service.get_logs_by_type(event_type="SIGNAL_GENERATED", limit=50)

# Filter by severity
logs = service.get_logs_by_severity(severity="ERROR", limit=50)

# Cache management
service.clear_cache()
stats = service.get_cache_stats()
```

### 4. API Endpoints (`app/api/v1/activity_logs.py`)

#### GET `/api/v1/activity-logs`
Get recent activity logs with filtering options.

**Query Parameters**:
- `limit` (int, 1-200): Maximum logs to return (default: 50)
- `since` (ISO timestamp): Only return logs after this time
- `event_type` (string): Filter by event type
- `severity` (string): Filter by severity level
- `refresh` (bool): Force refresh cache (default: false)

**Response**:
```json
{
    "success": true,
    "total": 50,
    "logs": [...],
    "has_more": true
}
```

**Example Requests**:
```bash
# Get 50 most recent logs
GET /api/v1/activity-logs

# Get logs after specific timestamp
GET /api/v1/activity-logs?since=2026-05-05T13:00:00Z

# Get only signal events
GET /api/v1/activity-logs?event_type=SIGNAL_GENERATED

# Get only errors
GET /api/v1/activity-logs?severity=ERROR&limit=100

# Force cache refresh
GET /api/v1/activity-logs?refresh=true
```

#### GET `/api/v1/activity-logs/stats`
Get cache statistics.

**Response**:
```json
{
    "success": true,
    "stats": {
        "cache_size": 150,
        "cache_max_size": 200,
        "last_update": "2026-05-05T14:30:00Z"
    }
}
```

#### POST `/api/v1/activity-logs/clear-cache`
Clear the in-memory cache.

#### GET `/api/v1/activity-logs/event-types`
Get list of available event types.

#### GET `/api/v1/activity-logs/severity-levels`
Get list of available severity levels.

## Configuration

### Data Source Paths

The collectors automatically resolve paths relative to the backend directory:

```python
# Signal CSV
AI_Trading_Server/integrations/live_signals_log.csv

# Structure CSVs
Backtest_result/LLHHBOSData_XAUUSD_*.csv
```

To override paths, pass them during initialization:

```python
signal_collector = SignalCollector(csv_path="/custom/path/signals.csv")
structure_collector = StructureCollector(backtest_dir="/custom/path/backtest")
```

### Cache Configuration

Default cache size is 200 events. To change:

```python
service = ActivityLogService(mt5_manager=mt5, cache_size=500)
```

## Error Handling

The system includes comprehensive error handling:

1. **File Not Found**: Logs warning, returns empty list
2. **Parse Errors**: Logs warning, skips problematic rows
3. **MT5 Unavailable**: Logs warning, skips position events
4. **API Errors**: Returns HTTP 500 with error details

## Logging

All components use Python's logging module:

```python
logger = logging.getLogger(__name__)
```

Log levels:
- `INFO`: Normal operations, event counts
- `WARNING`: Missing files, parse errors
- `ERROR`: Critical failures, exceptions
- `DEBUG`: Detailed operation traces

## Performance Considerations

1. **CSV Parsing**: Limited to 3 most recent structure files
2. **In-Memory Cache**: Deque with max size prevents memory issues
3. **Deduplication**: Set-based duplicate detection (O(1) lookup)
4. **Sorting**: Python's Timsort (O(n log n)) on already sorted data
5. **MT5 Queries**: Limited to 7 days of history

## Testing

Run the test script:

```bash
cd d:\Project\Project MT5\ValueCell_MT5\backend
python test_activity_logs.py
```

Test output includes:
- Service initialization
- Individual collector tests
- Filtering tests
- Cache statistics
- Sample log display

## Integration with Frontend

The API is designed for real-time activity feed display:

```javascript
// Fetch recent logs
const response = await fetch('/api/v1/activity-logs?limit=50');
const data = await response.json();

// Render logs
data.logs.forEach(log => {
    renderLogItem({
        icon: log.icon,
        title: log.title,
        message: log.message,
        timestamp: log.timestamp,
        severity: log.severity
    });
});
```

## Maintenance

### Adding New Event Types

1. Add to `EventType` enum in `activity_log.py`
2. Update collector to generate new event type
3. Update frontend icon mapping

### Adding New Collectors

1. Create new collector in `app/services/event_collectors/`
2. Implement `collect(limit, since)` method
3. Add to `ActivityLogService.__init__()`
4. Update `get_recent_logs()` to include new collector

### Monitoring

Check cache statistics regularly:

```bash
curl http://localhost:8000/api/v1/activity-logs/stats
```

Monitor log levels for warnings/errors in application logs.

## Future Enhancements

- [ ] WebSocket support for real-time updates
- [ ] Database persistence for historical logs
- [ ] Advanced filtering (multiple event types, date ranges)
- [ ] Export functionality (CSV, JSON)
- [ ] Log retention policies
- [ ] Performance metrics tracking
- [ ] Alert/notification system

## Troubleshooting

### No logs appearing

1. Check CSV files exist at expected paths
2. Verify MT5 connection (for position events)
3. Check application logs for errors
4. Try force refresh: `?refresh=true`

### Old logs not showing

1. Check `since` parameter
2. Verify cache size sufficient
3. Check CSV data timestamps

### Performance issues

1. Reduce `limit` parameter
2. Increase cache size
3. Check CSV file sizes
4. Monitor memory usage

## Support

For issues or questions:
- Check application logs in `backend/logs/`
- Review test script output
- Examine individual collector logs
- Verify data source files are accessible
