import asyncio
import hashlib
import hmac
import json
import time
from typing import Any, Dict

import structlog
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
import redis.asyncio as redis

from configs.settings import settings

logger = structlog.get_logger()

app = FastAPI(title="Nova Pulse Alert Relay", docs_url=None, redoc_url=None, openapi_url=None)

redis_client = redis.from_url(settings.redis_url, decode_responses=True)
RATE_LIMIT_KEY = "rate:{ip}"
IDEMPOTENCY_KEY = "idem:{key}"

def verify_hmac(body: bytes, signature: str) -> bool:
    try:
        algo, provided = signature.split("=", 1)
        digest = hmac.new(settings.signing_secret.encode(), body, getattr(hashlib, algo)).hexdigest()
        return hmac.compare_digest(digest, provided)
    except Exception:
        return False

async def rate_limit(ip: str):
    key = RATE_LIMIT_KEY.format(ip=ip)
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, 60)
    if count > settings.rate_limit_per_minute:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="rate limit exceeded")

async def ensure_idempotent(idem_key: str | None):
    if not idem_key:
        return
    key = IDEMPOTENCY_KEY.format(key=idem_key)
    existed = await redis_client.set(key, 1, ex=settings.idempotency_ttl_seconds, nx=True)
    if not existed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="duplicate request")

@app.middleware("http")
async def add_logging(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logger.info(
        "request",
        path=request.url.path,
        method=request.method,
        status=response.status_code,
        duration_ms=round(duration_ms, 2),
        client_ip=request.client.host if request.client else None,
    )
    return response

@app.get("/health")
async def health():
    try:
        await redis_client.ping()
        return {"status": "ok"}
    except Exception as e:
        logger.error("health_failed", error=str(e))
        raise HTTPException(status_code=503, detail="redis unavailable")

@app.post("/webhook/signal")
async def webhook(
    request: Request,
    x_api_key: str = Header(None, convert_underscores=False),
    x_signature: str = Header(None, convert_underscores=False),
    idempotency_key: str | None = Header(None, convert_underscores=False),
):
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")

    raw_body = await request.body()
    if not x_signature or not verify_hmac(raw_body, x_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid signature")

    await rate_limit(request.client.host if request.client else "unknown")
    await ensure_idempotent(idempotency_key)

    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid json")

    message = {
        "payload": payload,
        "received_at": time.time(),
        "retries": 0,
    }
    await redis_client.lpush(settings.queue_name, json.dumps(message))
    return JSONResponse({"status": "accepted"}, status_code=status.HTTP_202_ACCEPTED)

@app.on_event("shutdown")
async def shutdown_event():
    await redis_client.close()
