# Activity Logs System - Quick Start Guide

## 🚀 Get Started in 3 Steps

### 1. Start the Backend Server
```bash
cd d:\Project\Project MT5\ValueCell_MT5\backend
python -m uvicorn app.main:app --reload
```

### 2. Test the API
```bash
# In a new terminal
cd d:\Project\Project MT5\ValueCell_MT5\backend
python test_api_endpoint.py
```

### 3. Use the API
```bash
curl http://localhost:8000/api/v1/activity-logs?limit=50
```

## 📡 API Endpoints

### Main Endpoint
```
GET /api/v1/activity-logs
```

**Parameters:**
- `limit` (1-200): Number of logs to return (default: 50)
- `since` (ISO timestamp): Filter logs after this time
- `event_type` (string): Filter by event type
- `severity` (string): Filter by severity (INFO, SUCCESS, WARNING, ERROR)
- `refresh` (bool): Force cache refresh

**Example Requests:**
```bash
# Get 50 recent logs
GET /api/v1/activity-logs

# Get last 100 logs
GET /api/v1/activity-logs?limit=100

# Get logs from last hour
GET /api/v1/activity-logs?since=2026-05-05T13:00:00Z

# Get only signal events
GET /api/v1/activity-logs?event_type=SIGNAL_GENERATED

# Get only errors
GET /api/v1/activity-logs?severity=ERROR

# Force refresh
GET /api/v1/activity-logs?refresh=true
```

### Other Endpoints
```bash
# Get cache statistics
GET /api/v1/activity-logs/stats

# Clear cache
POST /api/v1/activity-logs/clear-cache

# Get available event types
GET /api/v1/activity-logs/event-types

# Get available severity levels
GET /api/v1/activity-logs/severity-levels
```

## 📊 Response Format

```json
{
    "success": true,
    "total": 50,
    "has_more": true,
    "logs": [
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
    ]
}
```

## 🎯 Event Types

### Signals (6 types)
- `SIGNAL_GENERATED` - New signal created
- `SIGNAL_EXECUTED` - Signal traded
- `SIGNAL_CLOSED` - Signal closed
- `TRADE_WIN` - Win outcome
- `TRADE_LOSS` - Loss outcome
- `TRADE_BREAKEVEN` - Breakeven outcome

### Structure (4 types)
- `STRUCTURE_CHOCH` - Change of Character
- `STRUCTURE_BOS` - Break of Structure
- `STRUCTURE_LL` - Lower Low
- `STRUCTURE_HH` - Higher High

### Positions (3 types)
- `POSITION_OPENED` - New position
- `POSITION_CLOSED` - Closed position
- `POSITION_MODIFIED` - Modified position

### System (5 types)
- `SYSTEM_STARTUP` - System start
- `SYSTEM_SHUTDOWN` - System stop
- `SYSTEM_ERROR` - Error event
- `SYSTEM_WARNING` - Warning event
- `SYSTEM_INFO` - Info event

## 🎨 Severity Levels

- `INFO` - General information (blue)
- `SUCCESS` - Successful operations (green)
- `WARNING` - Warning conditions (yellow)
- `ERROR` - Error conditions (red)

## 🔧 Icon Mapping

Map `log.icon` to your frontend icons:

```javascript
const iconMap = {
    'TrendingUp': '📈',
    'TrendingDown': '📉',
    'Activity': '📊',
    'GitBranch': '🔀',
    'ArrowUp': '⬆️',
    'ArrowDown': '⬇️',
    'Play': '▶️',
    'CheckCircle': '✅',
    'XCircle': '❌',
    'Minus': '➖',
    'Power': '🔌',
    'Info': 'ℹ️',
    'AlertTriangle': '⚠️',
    'AlertCircle': '🚨'
};
```

## 💻 Frontend Integration

### React Example
```jsx
import { useEffect, useState } from 'react';

function ActivityFeed() {
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(true);
    
    useEffect(() => {
        fetchLogs();
        const interval = setInterval(fetchLogs, 30000); // Refresh every 30s
        return () => clearInterval(interval);
    }, []);
    
    async function fetchLogs() {
        try {
            const response = await fetch('/api/v1/activity-logs?limit=50');
            const data = await response.json();
            setLogs(data.logs);
            setLoading(false);
        } catch (error) {
            console.error('Failed to fetch logs:', error);
        }
    }
    
    if (loading) return <div>Loading...</div>;
    
    return (
        <div className="activity-feed">
            {logs.map(log => (
                <div key={log.id} className={`log-item ${log.severity.toLowerCase()}`}>
                    <span className="icon">{log.icon}</span>
                    <div className="content">
                        <h4>{log.title}</h4>
                        <p>{log.message}</p>
                        <span className="timestamp">
                            {new Date(log.timestamp).toLocaleString()}
                        </span>
                    </div>
                </div>
            ))}
        </div>
    );
}
```

### JavaScript Example
```javascript
async function loadActivityLogs() {
    const response = await fetch('/api/v1/activity-logs?limit=50');
    const data = await response.json();
    
    const container = document.getElementById('activity-feed');
    container.innerHTML = '';
    
    data.logs.forEach(log => {
        const div = document.createElement('div');
        div.className = `log-item severity-${log.severity.toLowerCase()}`;
        div.innerHTML = `
            <span class="icon">${log.icon}</span>
            <div class="content">
                <h4>${log.title}</h4>
                <p>${log.message}</p>
                <span class="timestamp">${new Date(log.timestamp).toLocaleString()}</span>
            </div>
        `;
        container.appendChild(div);
    });
}

// Load every 30 seconds
loadActivityLogs();
setInterval(loadActivityLogs, 30000);
```

## 📁 Data Sources

The system automatically collects from:

1. **Signal Logs**: `AI_Trading_Server/integrations/live_signals_log.csv`
2. **Structure Logs**: `Backtest_result/LLHHBOSData_XAUUSD_*.csv`
3. **Position Logs**: MT5 API (via MT5Manager)
4. **System Logs**: In-memory event queue

## 🧪 Testing

### Test the Service
```bash
cd d:\Project\Project MT5\ValueCell_MT5\backend
python test_activity_logs.py
```

### Test the API
```bash
cd d:\Project\Project MT5\ValueCell_MT5\backend
python test_api_endpoint.py
```

### Manual API Test
```bash
# With curl
curl http://localhost:8000/api/v1/activity-logs

# With Python
python -c "import requests; print(requests.get('http://localhost:8000/api/v1/activity-logs').json())"
```

## 🐛 Troubleshooting

### No logs appearing?
1. Check if CSV files exist
2. Verify backend is running
3. Check logs: `backend/logs/`
4. Try force refresh: `?refresh=true`

### Server not starting?
```bash
# Check if port 8000 is available
netstat -ano | findstr :8000

# Install dependencies
pip install -r requirements.txt

# Check Python version (3.11+)
python --version
```

### Import errors?
```bash
# Make sure you're in the backend directory
cd d:\Project\Project MT5\ValueCell_MT5\backend

# Verify imports
python -c "from app.main import app; print('OK')"
```

## 📚 Documentation

- **README**: `ACTIVITY_LOGS_README.md` - Complete guide
- **Implementation**: `ACTIVITY_LOGS_IMPLEMENTATION.md` - Technical details
- **Quick Start**: `ACTIVITY_LOGS_QUICK_START.md` - This file

## 🎉 Features

✅ Real-time event collection  
✅ Multi-source aggregation  
✅ In-memory caching (200 events)  
✅ Flexible filtering  
✅ Timezone-aware (UTC)  
✅ Automatic deduplication  
✅ Graceful error handling  
✅ Comprehensive logging  
✅ Type-safe implementation  
✅ Full documentation  

## 🔮 Next Steps

1. Start the backend server
2. Test the API endpoints
3. Integrate with your frontend
4. Customize event icons
5. Style the activity feed
6. Add real-time updates (WebSocket - future)

## 💡 Pro Tips

- Use `refresh=true` sparingly (performance impact)
- Cache statistics help monitor system health
- Filter by severity for error monitoring
- Use `since` parameter for incremental updates
- Limit to 50-100 for best performance

## 🆘 Support

- Check application logs: `backend/logs/`
- Review test outputs
- Verify CSV file paths
- Check MT5 connection status
- Review error responses

---

**Ready to use!** 🚀

Start the server and test the API to see your activity logs in action!
