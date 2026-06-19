# 🚀 ValueCell Trading Backend

Professional FastAPI backend for ValueCell Trading Dashboard with real-time MT5 integration.

## 🎯 Features

- ✅ **FastAPI** - Modern, fast async API framework
- ✅ **MT5 Integration** - Real-time MetaTrader 5 connection
- ✅ **WebSocket Support** - Live data streaming
- ✅ **AI Agents** - Multi-agent trading system
- ✅ **Performance Analytics** - Comprehensive metrics
- ✅ **Error Handling** - Robust error management
- ✅ **Logging** - Structured logging system
- ✅ **Type Safety** - Pydantic data validation
- ✅ **Production Ready** - Deployment-ready architecture

## 📁 Project Structure

```
backend/
├── app/
│   ├── api/v1/          # API endpoints
│   ├── core/            # Business logic
│   ├── models/          # Pydantic models
│   ├── services/        # Business services
│   ├── middleware/      # Custom middleware
│   ├── utils/           # Utilities
│   ├── config.py        # Configuration
│   ├── dependencies.py  # Dependency injection
│   └── main.py          # Application entry
├── tests/               # Unit tests
├── logs/                # Application logs
├── .env                 # Environment variables
├── requirements.txt     # Dependencies
└── README.md           # This file
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and update:

```bash
cp .env.example .env
```

Edit `.env`:
```env
MT5_LOGIN=your_login
MT5_PASSWORD=your_password
MT5_SERVER=your_server
TRADING_MODE=paper
```

### 3. Run Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or use the Python entry point:

```bash
python -m app.main
```

### 4. Test API

Open browser: http://localhost:8000/docs

## 📡 API Endpoints

### Dashboard
- `GET /api/v1/dashboard/stats` - Account statistics
- `GET /api/v1/dashboard/account` - Account information
- `GET /api/v1/dashboard/status` - System status

### Trading
- `GET /api/v1/trading/candles` - OHLC candlestick data
- `GET /api/v1/trading/positions` - Open positions
- `GET /api/v1/trading/signal` - Current trading signal
- `GET /api/v1/trading/history` - Trade history
- `POST /api/v1/trading/order` - Place order (paper mode)

### Agents
- `GET /api/v1/agents/consensus` - AI agents consensus
- `GET /api/v1/agents/metrics` - Agent performance metrics

### Performance
- `GET /api/v1/performance/stats` - Performance statistics
- `GET /api/v1/performance/monthly` - Monthly breakdown
- `GET /api/v1/performance/risk` - Risk metrics

### WebSocket
- `WS /api/v1/ws/live` - Real-time data stream

## 🔌 WebSocket Usage

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/live');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(data);
};
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test
pytest tests/test_api/test_dashboard.py
```

## 📝 Development

### Add New Endpoint

1. Create route in `app/api/v1/your_route.py`:
```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/endpoint")
async def your_endpoint():
    return {"message": "Hello"}
```

2. Register in `app/main.py`:
```python
from app.api.v1 import your_route

app.include_router(
    your_route.router,
    prefix=f"{settings.API_V1_PREFIX}/your-prefix",
    tags=["Your Tag"],
)
```

### Add Pydantic Model

Create in `app/models/your_model.py`:
```python
from pydantic import BaseModel

class YourModel(BaseModel):
    field: str
    value: int
```

## 🚢 Production Deployment

### Using Uvicorn

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using Gunicorn

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Using Docker

```bash
docker build -t valuecell-backend .
docker run -p 8000:8000 valuecell-backend
```

## 🔒 Security

- JWT authentication (placeholder - implement in `dependencies.py`)
- CORS configuration
- Input validation
- SQL injection prevention
- Rate limiting (TODO)

## 📊 Logging

Logs are stored in `logs/app.log`:

```python
import logging
logger = logging.getLogger(__name__)

logger.info("Info message")
logger.error("Error message")
```

## 🐛 Troubleshooting

### MT5 Connection Failed
- Check MT5 terminal is running
- Verify credentials in `.env`
- Check firewall settings

### Port Already in Use
```bash
# Change port in .env
API_PORT=8001
```

### Module Not Found
```bash
pip install -r requirements.txt
```

## 📖 Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## 🤝 Contributing

1. Create feature branch
2. Make changes
3. Add tests
4. Submit pull request

## 📄 License

MIT License

## 🔗 Links

- Frontend: `../frontend/`
- Main Project: `../README.md`
- API Docs: http://localhost:8000/docs

---

**Version**: 1.0.0  
**Status**: Production Ready ✅
