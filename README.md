# StockSpikes

A password-protected dashboard with a live table of a fixed watchlist of volatile (<$50) stocks,
including pre-market, after-hours and overnight (24-hour market) pricing.
FastAPI backend, vanilla JS frontend, run with Docker Compose (app + MySQL + Redis).

See [AGENTS.md](AGENTS.md) for context aimed at AI agents.

## Features
- Live quotes for the watchlist from **Alpaca** (the only quote source), refreshed every 30s
- Table columns: Pin, Company, Symbol, Price, Open, High, Low, Prev Close, Volume, Session, Live
- **Session** badge: Open, Pre-market, After-hours, Overnight (8pm–4am ET) or Closed (clock-based; ignores holidays)
- **Live** dot colored by how far the price moved vs. the previous close, relative to a threshold
- Pin favorites to keep them on top (stored in MySQL, shared across devices)
- Paginated table (20 per page by default), light/dark theme
- Cookie-based password login
- Container log viewer drawer (App / MySQL / Redis)
- Tabs: Stocks, Alerts (placeholder), Options (disabled), Configuration

## How values are calculated
| Field | Source |
|---|---|
| Price | Alpaca latest trade (else bid/ask midpoint, else daily close) |
| Open / High / Low / Volume | Alpaca `dailyBar` (current/latest regular session, not 24h) |
| Prev Close | Alpaca `prevDailyBar` close |
| Change / % | price − Prev Close, and that ÷ Prev Close. In extended hours this is vs. the last regular close |
| Live severity | `abs(%)`: low < T, medium < 3T, high ≥ 3T, with T = `volatility.threshold` |
| Company name | Yahoo (`yfinance`), cached in Redis; the only Yahoo use |

Without Alpaca keys, `/api/stocks` returns 503 and the table shows an error. There is no fallback.
Free Alpaca plans use the IEX feed (partial volume). The `overnight` feed needs a plan that includes it.

## Quick start
```bash
cp -n .env.example .env     # set STOCKSPIKES_PWD (required)
# Alpaca keys: put ALPACA_API_KEY / ALPACA_API_SECRET in .env, or export them in your shell
docker compose up -d --build
```
Open http://localhost:5000 and log in.

### Clean rebuild (nothing stale)
```bash
docker compose down --remove-orphans --rmi local
docker compose build --no-cache --pull
docker compose up -d --force-recreate
```
Don't use `down -v` unless you want to wipe pins (`mysql_data` volume). `./rebuild.sh --force` is a cached alternative.

## Configuration
`config.yaml` (hot-reloaded, no restart needed):
```yaml
symbols: [RIVN, LCID, NIO, ...]   # watchlist
volatility:
  threshold: 5.0                  # Live severity threshold (%)
timezone: CT                      # display timezone
```

### Environment variables (`.env`)
| Variable | Purpose |
|---|---|
| `STOCKSPIKES_PWD` | Dashboard password (required by compose) |
| `ALPACA_API_KEY`, `ALPACA_API_SECRET` | Alpaca market data credentials |
| `ALPACA_DATA_FEED` | `auto` (default: overnight 8pm–4am ET, else iex), `iex`, `sip`, `overnight` |
| `MYSQL_*`, `REDIS_HOST`, `REDIS_PORT` | Service settings (defaults in compose) |
| `DEBUG`, `LOG_LEVEL` | Logging |

## API
| Endpoint | Description |
|---|---|
| `GET /api/stocks` | Watchlist with quotes, company name, session, pin state, live severity |
| `PUT /api/stocks/{symbol}/pin` | Body `{"pinned": true/false}` |
| `GET /api/config` | Symbols, threshold, timezone |
| `GET /api/health` | Health check |
| `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/status` | Auth |
| `GET /api/logs/containers`, `GET /api/logs/{container_id}` | Container logs |

## Layout
```
app/
├── main.py              # FastAPI app, middleware, routing
├── config.py            # env settings + config.yaml loader
├── auth.py              # cookie auth middleware
├── data/                # alpaca.py (quotes), session.py, fetcher.py (names), cache.py (Redis)
├── database/            # SQLAlchemy; only PinnedStock
├── routes/              # api.py, auth.py, logs.py, static.py
└── static/              # index.html, app.js, style.css, login.html
config.yaml  Dockerfile  docker-compose.yml  rebuild.sh  requirements.txt  AGENTS.md
```

## Deployment notes
- Compose network is named `stocks_network` so an external reverse proxy can join it and route to `stocks-dashboard:5000`.
- MySQL (3306) and Redis (6379) are published on the host and use default passwords; lock these down if the host is reachable from outside.
- `/var/run/docker.sock` is mounted read-only for the log viewer; `--reload` and the `./app` bind mount are dev-style settings.

## Troubleshooting
- **Table shows "Alpaca API keys not set":** export the keys in your shell or set them in `.env`, then `docker compose up -d --force-recreate stocks-dashboard`.
- **Company shows "—":** names load in the background; they appear on the next refresh.
- **Stale UI:** hard-refresh the browser (Ctrl+Shift+R).
- **Logs:** `docker compose logs -f stocks-dashboard`

## License
MIT

Not investment advice.
