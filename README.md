# StockSpikes

A real-time stock price volatility monitoring system that detects sharp price movements and unusual trading patterns across a configurable portfolio of stocks.

**Status**: MVP Complete | **Tech Stack**: Python/FastAPI, MySQL, Redis, yfinance | **Deployment**: Docker Compose

## 🎯 Project Overview

This application analyzes historical stock price data to identify and alert on significant volatility events. It monitors 1-year price histories and detects:

1. **Sharp Movements** - Daily price changes exceeding a configurable threshold (default: ±5%)
2. **Volatility Patterns** - Bounce-back patterns after sustained price declines
3. **Trending Behavior** - Multi-day patterns indicating market swings

All alerts are visualized in real-time on a web dashboard, with data persisted to MySQL and cached in Redis for fast retrieval.

## ✨ Key Features

- **Real-time Monitoring**: Analyzes stock data every 4 hours (configurable)
- **Configurable Watchlist**: YAML-based config to add/remove stock symbols
- **Multiple Alert Types**: 
  - `sharp_up` - Sudden upward price spikes
  - `sharp_down` - Sudden downward price drops
  - `pattern` - Recovery bounces after sustained declines
- **Severity Levels**: Low (5%), Medium (10%), High (15%+)
- **Web Dashboard**: Single-page app showing stock list and real-time alerts
- **Local Network Accessible**: Run on any machine, access from any device on network
- **Persistent Storage**: MySQL database for long-term alert history
- **Smart Caching**: Redis cache for fast data retrieval and reduced API calls

## 🏗️ Architecture

### Components

```
Frontend (HTML/CSS/JS)
         ↓
FastAPI REST API (Python)
         ↓
┌─────────┴──────────┐
│                    │
MySQL Database   Redis Cache
(Persistent)     (Fast Access)
│
└→ yfinance (Data Source)
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | FastAPI (Python 3.11) | REST API, business logic, analysis |
| **Database** | MySQL 8.0 | Persistent storage of alerts & stock data |
| **Cache** | Redis 7 | Fast access to price data & analysis results |
| **Data Source** | yfinance | Historical stock price data (free, no API key) |
| **Scheduler** | APScheduler | Background jobs for recurring analysis |
| **Frontend** | HTML/CSS/JavaScript | Single-page dashboard |
| **Deployment** | Docker Compose | Containerized multi-service setup |

### File Structure

```
stocks-volatility/
├── app/
│   ├── main.py                 # FastAPI app entry point & scheduler setup
│   ├── config.py               # Configuration loader (config.yaml)
│   ├── database/
│   │   ├── models.py           # SQLAlchemy ORM models (Stock, Alert, etc.)
│   │   └── connection.py       # MySQL connection pool & session factory
│   ├── data/
│   │   ├── fetcher.py          # yfinance wrapper for historical data
│   │   └── cache.py            # Redis caching layer
│   ├── analysis/
│   │   ├── volatility.py       # Core volatility detection logic
│   │   └── patterns.py         # Pattern matching (future enhancements)
│   ├── scheduler/
│   │   └── jobs.py             # Background analysis job
│   ├── routes/
│   │   ├── api.py              # REST API endpoints
│   │   └── static.py           # Static file serving
│   └── static/
│       ├── index.html          # Single-page app HTML
│       ├── app.js              # Frontend logic & polling
│       └── style.css           # Responsive styling
├── docker-compose.yml          # Multi-service container setup
├── Dockerfile                  # Python app container image
├── requirements.txt            # Python dependencies
├── config.yaml                 # Application configuration
└── .env.example                # Environment variables template
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose installed
- OR Python 3.11+, MySQL 8.0, Redis 7+

### Option 1: Docker Compose (Recommended)

```bash
# Clone or extract the repository
cd stocks-volatility

# Create .env file (optional, uses defaults)
cp .env.example .env

# Start all services
docker-compose up -d

# Access the dashboard
# Open http://localhost:5000 in your browser
```

### Option 2: Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set up MySQL database
mysql -u root -p < schema.sql  # (create this if needed)

# Start Redis
redis-server

# Run the app
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 5000

# Access at http://localhost:5000
```

## ⚙️ Configuration

Edit `config.yaml` to customize:

```yaml
symbols:
  - AAPL      # Add/remove stock symbols here
  - GOOGL
  - MSFT

volatility:
  threshold: 5.0        # Alert on ±5% daily moves
  lookback_days: 365    # Analyze 1 year of history

scheduler:
  interval_hours: 4     # Run analysis every 4 hours

alerts:
  max_history: 1000     # Keep up to 1000 alerts
  retention_days: 90    # Delete alerts older than 90 days
```

Changes are picked up on the next scheduled run.

## 📊 API Endpoints

All endpoints are JSON-based and accessible at `http://localhost:5000/api/`:

### `GET /api/stocks`
List all monitored stocks with current status.

**Response:**
```json
[
  {
    "symbol": "AAPL",
    "price": 145.32,
    "last_update": "2024-01-15T10:30:00",
    "unread_alerts": 2
  }
]
```

### `GET /api/alerts?limit=50&skip=0`
Get recent volatility alerts.

**Response:**
```json
[
  {
    "id": 1,
    "symbol": "AAPL",
    "alert_type": "sharp_down",
    "severity": "high",
    "message": "AAPL moved -7.50% on 2024-01-15",
    "triggered_at": "2024-01-15T09:45:00",
    "price_at_trigger": 134.50,
    "percent_change": -7.50,
    "is_read": false,
    "created_at": "2024-01-15T09:46:00"
  }
]
```

### `POST /api/refresh`
Manually trigger analysis job immediately.

**Response:**
```json
{
  "status": "success",
  "symbols": 5,
  "alerts": 3
}
```

### `GET /api/config`
Get current application configuration.

**Response:**
```json
{
  "symbols": ["AAPL", "GOOGL", "MSFT"],
  "volatility_threshold": 5.0,
  "lookback_days": 365,
  "scheduler_interval_hours": 4
}
```

### `POST /api/alerts/{alert_id}/read`
Mark an alert as read.

### `GET /health`
Health check endpoint.

## 📈 How Volatility Detection Works

### Sharp Move Detection
1. Fetches 1 year of daily price data for each stock
2. Calculates daily percent change: `(Close - Open) / Open * 100`
3. Flags days where absolute change ≥ threshold (default 5%)
4. Creates "sharp_up" or "sharp_down" alert

### Pattern Detection
1. Analyzes sequences of daily movements (up/down)
2. Identifies pattern: **down → down → sharp up**
3. Indicates potential recovery/bounce after sustained decline
4. Creates "pattern" alert with "high" severity

### Example
```
Day 1: -3% (down)
Day 2: -2% (down)        } Sustained decline
Day 3: +8% (sharp up)    } Creates PATTERN alert
```

## 🗄️ Database Schema

### `stocks` table
- `id` (PRIMARY KEY)
- `symbol` (VARCHAR, unique)
- `name` (VARCHAR)
- `last_price` (FLOAT)
- `last_update` (DATETIME)

### `alerts` table
- `id` (PRIMARY KEY)
- `symbol` (VARCHAR, indexed)
- `alert_type` (VARCHAR) - "sharp_up", "sharp_down", "pattern"
- `severity` (VARCHAR) - "low", "medium", "high"
- `message` (TEXT)
- `triggered_at` (DATETIME) - when price event occurred
- `price_at_trigger` (FLOAT)
- `percent_change` (FLOAT)
- `is_read` (BOOLEAN)
- `created_at` (DATETIME, indexed)

### `price_data` table
- `id` (PRIMARY KEY)
- `symbol` (VARCHAR, indexed)
- `date` (DATETIME)
- `open_price` (FLOAT)
- `high_price` (FLOAT)
- `low_price` (FLOAT)
- `close_price` (FLOAT)
- `volume` (INT)
- `percent_change` (FLOAT)

### `analysis_runs` table
- `id` (PRIMARY KEY)
- `run_at` (DATETIME, indexed)
- `status` (VARCHAR) - "running", "completed", "failed"
- `error_message` (TEXT)
- `symbols_processed` (INT)
- `alerts_generated` (INT)
- `duration_seconds` (FLOAT)

## 🔄 Data Flow

### Startup
1. Load `config.yaml` (stock symbols, thresholds)
2. Initialize MySQL database (create tables if needed)
3. Connect to Redis
4. Start APScheduler with 4-hour interval
5. Run initial analysis job

### Every 4 Hours (Scheduled)
1. Fetch 1-year price data via yfinance for each symbol
2. Cache raw price data in Redis (6-hour TTL)
3. Run volatility analysis on cached data
4. Detect sharp moves and patterns
5. Store new Alert records in MySQL
6. Update Stock.last_price

### On Browser Request
1. User opens http://localhost:5000
2. Frontend polls `/api/stocks` and `/api/alerts` every 30 seconds
3. API queries MySQL and returns recent data
4. Dashboard updates with new alerts in real-time

## 🛠️ Development

### Adding New Stock Symbols
Edit `config.yaml`:
```yaml
symbols:
  - AAPL
  - GOOGL
  - MSFT
  - TSLA
  - AMZN  # Add new symbol
```

Restart the app or wait for next scheduled run.

### Adjusting Volatility Threshold
Edit `config.yaml`:
```yaml
volatility:
  threshold: 3.0  # Lower = more sensitive, more alerts
```

### Changing Analysis Interval
Edit `config.yaml`:
```yaml
scheduler:
  interval_hours: 2  # Run every 2 hours instead of 4
```

### Adding New Alert Types
1. Add detection logic to `app/analysis/volatility.py`
2. Extend `Alert.alert_type` enum in `app/database/models.py`
3. Update frontend `app/static/app.js` to render new type
4. Add styling to `app/static/style.css`

## 🧪 Testing

### Manual Testing
```bash
# Trigger analysis manually
curl -X POST http://localhost:5000/api/refresh

# Get alerts
curl http://localhost:5000/api/alerts

# Get stocks
curl http://localhost:5000/api/stocks
```

### Docker Logs
```bash
docker-compose logs -f stocks-dashboard
docker-compose logs -f mysql
docker-compose logs -f redis
```

## 📝 Environment Variables

See `.env.example`:

```
MYSQL_ROOT_PASSWORD=rootpassword
MYSQL_DATABASE=stocks_db
MYSQL_USER=stocks_user
MYSQL_PASSWORD=stocks_password
REDIS_HOST=redis
REDIS_PORT=6379
DEBUG=False
LOG_LEVEL=INFO
```

## 🚨 Error Handling

- **yfinance Fetch Fails**: Logs warning, uses cached data if available
- **MySQL Connection Lost**: Retries with exponential backoff
- **Analysis Job Timeout**: Creates error record in AnalysisRun, continues
- **Invalid Config**: Logs error, uses previous valid config

## 🔮 Future Enhancements

- [ ] Email/SMS alerts for critical volatility events
- [ ] More sophisticated pattern detection (V-shapes, head-and-shoulders)
- [ ] Technical indicators (RSI, MACD, Bollinger Bands)
- [ ] Trading strategy suggestions
- [ ] Performance optimization (timeseries DB like InfluxDB)
- [ ] User accounts with per-user watchlists
- [ ] Mobile app (React Native)
- [ ] Webhook integrations (Slack, Discord)
- [ ] Machine learning for anomaly detection

## 📄 License

MIT

## 🤝 For AI Agents

**Key Information for Code Understanding:**
- Entry point: `app/main.py` (FastAPI app initialization)
- Configuration: `app/config.py` (loads `config.yaml`)
- Database: `app/database/models.py` (SQLAlchemy ORM definitions)
- Analysis Logic: `app/analysis/volatility.py` (core detection algorithm)
- Background Jobs: `app/scheduler/jobs.py` (APScheduler tasks)
- API Layer: `app/routes/api.py` (REST endpoints)
- Frontend State: `app/static/app.js` (polling logic)
- Data Source: `app/data/fetcher.py` (yfinance wrapper)

**To Extend:**
1. Add new analysis functions to `app/analysis/`
2. Add new API endpoints to `app/routes/api.py`
3. Add database models to `app/database/models.py`
4. Update scheduler job in `app/scheduler/jobs.py`
5. Update frontend in `app/static/` (HTML/CSS/JS)

## 🐛 Troubleshooting

**Port 5000 already in use:**
```bash
docker-compose down
docker-compose up -d
```

**MySQL connection fails:**
```bash
docker-compose logs mysql
# Check MYSQL_PASSWORD matches in docker-compose.yml
```

**No alerts appearing:**
- Check `config.yaml` has valid stock symbols
- Run `POST /api/refresh` to trigger analysis
- Check logs: `docker-compose logs stocks-dashboard`

**Redis connection issues:**
```bash
docker exec stocks-redis redis-cli ping
# Should return PONG
```

---

**Built with ❤️ using Python, FastAPI, MySQL, and Redis**
