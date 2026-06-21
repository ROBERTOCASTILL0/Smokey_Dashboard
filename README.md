# Wildland Dashboard

Mobile-first, PIN-gated wildland conditions dashboard for invited viewers.

## What it exposes

- `GET /health`
- `GET /login`
- `POST /login`
- `POST /logout`
- `GET /`
- `GET /api/status`
- `POST /internal/refresh` (protected by refresh token)

Public viewers can read the dashboard and the read-only status API only after entering the PIN. Refresh runs server-side only.

## Environment variables

- `SECRET_KEY`: Flask session signing key
- `ACCESS_PIN`: PIN required for viewer access
- `SESSION_HOURS`: session lifetime in hours (default `24`)
- `SOURCE_STATUS_URL`: optional upstream read-only JSON source for snapshot refreshes
- `SOURCE_STATUS_BEARER_TOKEN`: optional bearer token used when calling `SOURCE_STATUS_URL`
- `REFRESH_TOKEN`: secret required by the internal refresh route and cron trigger script
- `APP_BASE_URL`: base URL used by the cron trigger script (for example `https://wildland-dashboard.onrender.com`)

## Local run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python collector.py refresh
python app.py
```

Then open `http://127.0.0.1:5000`.

## Refresh workflow

This app follows the same public-safe pattern used in the event finder app:

- the web app serves a cached JSON snapshot
- viewers do not trigger live scraping
- a protected internal refresh endpoint updates the snapshot server-side
- a scheduled job calls that protected endpoint every 30 minutes

### Manual local refresh

```bash
python collector.py refresh
```

### Trigger the protected refresh endpoint

```bash
REFRESH_TOKEN=*** APP_BASE_URL=http://127.0.0.1:5000 python trigger_refresh.py
```

## Render

The repo includes a `render.yaml` blueprint with:

- a Python web service
- a Render cron job that hits the protected refresh endpoint every 30 minutes

Before deploy, set the same `REFRESH_TOKEN` value on both services.
