from __future__ import annotations

import httpx

from app.config import Settings


class NotificationError(RuntimeError):
    pass


async def send_telegram(settings: Settings, text: str) -> dict:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise NotificationError("TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID belum diisi di .env")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text[:4096],
        "disable_web_page_preview": True,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.post(url, json=payload)
    if res.status_code >= 300:
        raise NotificationError(f"Telegram error {res.status_code}: {res.text[:300]}")
    return res.json()


async def send_whatsapp_text(settings: Settings, text: str) -> dict:
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id or not settings.whatsapp_to_number:
        raise NotificationError("WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, atau WHATSAPP_TO_NUMBER belum diisi.")

    url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}", "Content-Type": "application/json"}

    if settings.whatsapp_use_template:
        payload = {
            "messaging_product": "whatsapp",
            "to": settings.whatsapp_to_number,
            "type": "template",
            "template": {
                "name": settings.whatsapp_template_name,
                "language": {"code": settings.whatsapp_template_language},
            },
        }
    else:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": settings.whatsapp_to_number,
            "type": "text",
            "text": {"preview_url": False, "body": text[:4096]},
        }

    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.post(url, headers=headers, json=payload)
    if res.status_code >= 300:
        raise NotificationError(f"WhatsApp error {res.status_code}: {res.text[:500]}")
    return res.json()
