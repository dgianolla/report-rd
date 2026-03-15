import asyncio
import logging

import httpx

from config import config

logger = logging.getLogger(__name__)

RETRY_DELAYS = [2, 4, 8]


def _wts_headers() -> dict:
    return {
        "Authorization": f"Bearer {config.wts_api_token}",
        "Content-Type": "application/json",
    }


async def _post_with_retry(client: httpx.AsyncClient, url: str, payload: dict) -> dict:
    last_exc = None
    for attempt, delay in enumerate([0] + RETRY_DELAYS, start=1):
        if delay:
            await asyncio.sleep(delay)
        try:
            resp = await client.post(url, json=payload, headers=_wts_headers())
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            last_exc = exc
            logger.warning("WTS attempt %d/%d failed: %s", attempt, len(RETRY_DELAYS) + 1, exc)
    raise last_exc


def _split_message(text: str, max_chars: int = None) -> list[str]:
    max_chars = max_chars or config.max_whatsapp_chars
    if len(text) <= max_chars:
        return [text]

    separator = "\n━━━━━━━━━━━━━━━━━━━━━━\n"
    parts = text.split(separator)
    chunks: list[str] = []
    current = ""

    for part in parts:
        segment = (separator + part) if current else part
        if len(current) + len(segment) > max_chars:
            if current:
                chunks.append(current)
            current = part
        else:
            current += segment

    if current:
        chunks.append(current)

    total = len(chunks)
    if total > 1:
        chunks = [f"*[Parte {i+1}/{total}]*\n\n{chunk}" for i, chunk in enumerate(chunks)]

    return chunks


async def send_whatsapp_message(text: str) -> bool:
    url = f"{config.wts_api_base_url}/chat/v1/message/send"
    chunks = _split_message(text)
    logger.info("Sending WhatsApp report in %d chunk(s)", len(chunks))

    async with httpx.AsyncClient(timeout=config.http_timeout) as client:
        for i, chunk in enumerate(chunks, start=1):
            try:
                payload = {
                    "from": config.wts_from_phone,
                    "to": config.wts_recipient_phone,
                    "body": {"text": chunk},
                }
                result = await _post_with_retry(client, url, payload)
                logger.info(
                    "WhatsApp chunk %d/%d sent — id=%s status=%s",
                    i, len(chunks),
                    result.get("id", "?"),
                    result.get("status", "?"),
                )
            except Exception as exc:
                logger.error("Failed to send WhatsApp chunk %d/%d: %s", i, len(chunks), exc)
                return False
            if i < len(chunks):
                await asyncio.sleep(1)

    return True
