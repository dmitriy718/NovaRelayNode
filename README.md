# Nova Pulse Alert Relay Node

Production-hardened alert ingress + dispatch service for Nova Pulse trading signals running on Raspberry Pi 5 (8GB).

## Core capabilities
- FastAPI webhook (`/webhook/signal`) with API key + HMAC validation, rate limiting, and idempotency.
- Pushes signals to Redis queue; async worker fan-outs to Telegram, Discord, SMTP, optional Twilio SMS.
- Structured logs, retry with exponential backoff, never blocks ingress.
- Health endpoint `/health` (local only) verifies Redis connectivity.

## Deployment topology
- Host: Raspberry Pi 5
  - LAN IP: `192.168.1.20`
  - External IP: `203.0.113.10`
- Services (Docker): `app` (FastAPI), `worker`, `redis`.
- Bindings: app listens on `127.0.0.1:8000` inside host; exposed via docker-compose only on localhost.

## Upstream Nova endpoints (reference)
- Nova Web: `horizonsvc.com` → `203.0.113.193`
- Nova Bot: `nova.horizonsvc.com` → `198.51.100.68`
- Horizon API: `api.horizonsvc.com` (DNS unresolved at time of writing) — use health once available.

## Runbook
### Build & up
```bash
cd ~/horizon/alert-relay
docker compose build
docker compose up -d
```

### Health
```bash
curl -s http://127.0.0.1:8000/health
```
Expect `{"status":"ok"}`.

### Webhook contract
- Method: `POST /webhook/signal`
- Headers: `X-API-Key`, `X-Signature` (format `sha256=<hex>` of raw body using `SIGNING_SECRET`), optional `Idempotency-Key`.
- Body: JSON payload (free-form); enqueued with metadata.
- Rate limit: `RATE_LIMIT_PER_MINUTE` per client IP (Redis-based).

### Environment
See `.env.example` for full list:
- `API_KEY`, `SIGNING_SECRET`
- `RATE_LIMIT_PER_MINUTE`, `IDEMPOTENCY_TTL_SECONDS`, `QUEUE_NAME`
- Delivery creds: `TELEGRAM_*`, `DISCORD_WEBHOOK_URL`, `SMTP_*`, `TWILIO_*`

### Queue + worker
- Redis list `alerts`
- Worker pops with `BRPOP`, dispatches all channels concurrently, retries with backoff up to `MAX_RETRY_ATTEMPTS`.

### Logs
- Container stdout; add volume `./logs:/app/logs` if file persistence is desired.

## Security
- API bound to localhost; expose only via reverse proxy with auth if needed.
- Secrets must live in `.env` (never commit). Current `.env` uses placeholders.

## Current status (2026-03-03)
- Containers running: app, worker, redis (see `docker ps`).
- Health returns 200.
- Uptime Kuma present on host (port 3001) for monitoring; relay not exposed there yet.

## Troubleshooting
- If `/health` is 503, ensure `redis` container is up.
- Worker retries logged as `dispatch_failed_retry`; check Redis backlog with `docker exec alert-relay-redis-1 redis-cli LLEN alerts`.

## Roadmap / fit
- Fits Nova Pulse stack as secure edge relay on Pi; forward-looking plan is to integrate with uptime dashboard and Horizon status page.

