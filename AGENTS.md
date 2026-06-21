# Agent notes for Wildland Dashboard

## Purpose

Standalone invited-viewer wildland dashboard with a mobile-first, read-only surface.

## Guardrails

- Keep the public route surface narrow.
- Do not add public admin, shell, proxy, or arbitrary refresh routes.
- Keep `ACCESS_PIN` and `REFRESH_TOKEN` in environment variables only.
- Preserve the cached snapshot model: app serves cached JSON, refresh happens server-side.
- Keep the UI incident-first and phone-friendly.
- Do not add infrastructure-specific names, private URLs, or local filesystem details to repo copy.

## Acceptance checks

- `GET /health` returns `200` with JSON.
- login flow works with the configured PIN.
- unauthenticated `GET /api/status` redirects to login.
- authenticated `GET /api/status` returns JSON.
- protected `POST /internal/refresh` rejects missing/wrong token and accepts the correct token.
