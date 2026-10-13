# AGENTS.md — StockSpikes (stocks-volatility)

Context for AI agents working in this repo. Keep it current when behavior changes.

## What this is
A password-protected dashboard that shows a live table of a fixed watchlist of volatile
stocks (<$50) with 24-hour market info. FastAPI backend + vanilla JS frontend, run with
Docker Compose (app + MySQL + Redis).

## Layout
- `app/main.py` — FastAPI app, CORS, auth middleware, router wiring.
- `app/routes/api.py` — `/api/stocks`, `/api/stocks/{symbol}/pin` (PUT), `/api/config`, `/api/health`.
- `app/routes/auth.py` — `/api/auth/*` login/logout/status; `app/auth.py` cookie middleware.
- `app/routes/logs.py` — container log viewer (reads Docker socket).
- `app/data/alpaca.py` — **only quote source** (Alpaca snapshots).
- `app/data/session.py` — clock-based session: overnight/pre/regular/post/closed (ET, no holiday calendar).
- `app/data/fetcher.py` — Yahoo, used **only for company names**.
- `app/data/cache.py` — Redis: 1-min quote cache, `company_names` hash.
- `app/database/` — MySQL via SQLAlchemy; only the `PinnedStock` model remains.
- `app/static/` — `index.html`, `app.js`, `style.css`, `login.html`.
- `config.yaml` — watchlist `symbols`, `volatility.threshold`, `timezone` (hot-reloaded).

## Behavior to know
- Stocks table columns: pin, Company (small font), Symbol, Price, Open, High, Low, Prev Close,
  Volume, Session, Live. 20 rows per page by default. Polls every 30s.
- Change/% = current price − previous regular-session close. Open/High/Low are the current/latest
  regular session's, not 24h values. Live dot severity uses `volatility.threshold`
  (low < T, medium < 3T, high >= 3T).
- **No Yahoo quote fallback.** Without `ALPACA_API_KEY`/`ALPACA_API_SECRET`, `/api/stocks`
  returns 503 and the table shows an error. Docker Compose passes these from the host shell
  or `.env`, so keys exported in a shell profile are picked up.
- `ALPACA_DATA_FEED=auto`: `overnight` feed 8pm–4am ET, otherwise `iex`; falls back to `iex`
  if overnight returns nothing. Overnight needs an Alpaca plan with that feed.
- Tabs: Stocks, Alerts (empty placeholder), Options (disabled), Configuration.
- Company names load in a background thread and cache in Redis; first load shows "—".

## Removed on purpose (do not re-add unless asked)
Alert history table, Last Alert column, threshold-alert analysis/scheduler jobs, Alert/AnalysisRun
models and `/api/alerts`, `/api/refresh`. Old MySQL tables (`alerts`, `analysis_runs`, `stocks`,
`price_data`) may still exist in deployed DBs, unused. README.md is outdated (still describes alerts).

## Run / deploy
```
cp -n .env.example .env     # set STOCKSPIKES_PWD (required); Alpaca keys optional in .env if exported in shell
docker compose down --remove-orphans --rmi local
docker compose build --no-cache --pull
docker compose up -d --force-recreate
```
App on http://localhost:5000. `./app` is bind-mounted and uvicorn runs with `--reload`.
Compose network is named `stocks_network` so an external reverse proxy can attach and route
to `stocks-dashboard:5000`; the proxy config lives outside this repo.
Do not use `down -v` unless wiping pins is intended (`mysql_data` volume).

## Known issues / security notes
- MySQL 3306 and Redis 6379 are published on the host; default DB passwords in compose.
- `/var/run/docker.sock` is mounted (read-only) for the log viewer.
- CORS is `*` with credentials; auth cookie is long-lived; one shared password, no rate limiting.
- Session badge ignores market holidays and half-days.

## Conventions
- Work on a feature branch, never push straight to `main` except docs like this file; open a PR.
- Keep frontend dependency-free (vanilla JS). Validate with `node --check app/static/app.js`
  and `python3 -m pyflakes app`.
