# Agent Onboarding

Welcome! Follow this reading order to get productive fast:
1) README.md — architecture, endpoints, environment.
2) docker-compose.yml — service topology and bindings.
3) configs/settings.py — config contract and env variables.
4) app/main.py — webhook ingress, auth, rate limit, idempotency, logging.
5) worker/main.py — dispatch + retry logic.
6) CHANGELOG.md — what changed and when (must update for every change).

## Change policy
- Every code or config change **must** add an entry to CHANGELOG.md (date + concise bullets).
- Do not commit secrets (.env, tokens). Keep them local.
- Preserve localhost binding unless explicitly requested to expose.

## Development notes
- Queue name defaults to `alerts`; adjust via `.env`.
- Redis runs in the same compose network (`internal`).
- Tests: manual `curl` against `/health` and `/webhook/signal` with valid HMAC.

## Monitoring hooks
- Uptime Kuma available on host port 3001; add checks for app health if needed.

