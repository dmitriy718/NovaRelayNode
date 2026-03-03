import asyncio
import json
import random
from email.message import EmailMessage

import httpx
import redis.asyncio as redis
import structlog
import aiosmtplib

from configs.settings import settings

logger = structlog.get_logger()

redis_client = redis.from_url(settings.redis_url, decode_responses=True)


def format_message(payload: dict) -> str:
    return json.dumps(payload, indent=2, default=str)


async def send_telegram(payload: dict) -> None:
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    text = f"Nova Pulse Alert:\n{format_message(payload)}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json={"chat_id": settings.telegram_chat_id, "text": text})
        if resp.status_code >= 400:
            raise RuntimeError(f"telegram status {resp.status_code}")


async def send_discord(payload: dict) -> None:
    if not settings.discord_webhook_url:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(settings.discord_webhook_url, json={"content": format_message(payload)})
        if resp.status_code >= 400:
            raise RuntimeError(f"discord status {resp.status_code}")


async def send_email(payload: dict) -> None:
    if not (settings.smtp_host and settings.smtp_from and settings.smtp_to):
        return
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = settings.smtp_to
    msg["Subject"] = "Nova Pulse Alert"
    msg.set_content(format_message(payload))
    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password,
        start_tls=True,
    )


async def send_twilio(payload: dict) -> None:
    if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from and settings.twilio_to):
        return
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    data = {"From": settings.twilio_from, "To": settings.twilio_to, "Body": format_message(payload)}
    async with httpx.AsyncClient(timeout=10, auth=(settings.twilio_account_sid, settings.twilio_auth_token)) as client:
        resp = await client.post(url, data=data)
        if resp.status_code >= 400:
            raise RuntimeError(f"twilio status {resp.status_code} body={resp.text}")


async def dispatch(payload: dict) -> None:
    tasks = [send_telegram(payload), send_discord(payload), send_email(payload), send_twilio(payload)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    errors = [r for r in results if isinstance(r, Exception)]
    if errors:
        # Raise the first error to trigger retry logic while logging all
        for err in errors:
            logger.error("dispatch_channel_failed", error=str(err))
        raise errors[0]


async def process_loop() -> None:
    queue = settings.queue_name
    while True:
        try:
            item = await redis_client.brpop(queue, timeout=5)
        except Exception as e:
            logger.error("redis_brpop_error", error=str(e))
            await asyncio.sleep(1)
            continue

        if not item:
            continue

        _, raw = item
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("invalid_message_json", raw=raw)
            continue

        payload = msg.get("payload", {})
        retries = int(msg.get("retries", 0))

        try:
            await dispatch(payload)
            logger.info("dispatched", retries=retries)
        except Exception as e:
            retries += 1
            if retries <= settings.max_retry_attempts:
                delay = min(60, 2 ** retries + random.random())
                await redis_client.lpush(queue, json.dumps({"payload": payload, "retries": retries}))
                logger.error(
                    "dispatch_failed_retry",
                    error=str(e),
                    retries=retries,
                    delay=round(delay, 2),
                )
                await asyncio.sleep(delay)
            else:
                logger.error("dispatch_failed_giveup", error=str(e), payload_sample=str(payload)[:200])


def main() -> None:
    asyncio.run(process_loop())


if __name__ == "__main__":
    main()
