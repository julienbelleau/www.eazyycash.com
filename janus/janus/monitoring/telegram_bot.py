"""Lightweight Telegram alerter.

Sends operational alerts (kill switch trips, drawdown thresholds, daily
P&L summaries). Avoids `python-telegram-bot`'s heavy event loop —
plain `httpx` to the Bot API is enough for a handful of messages per day.

Phase 0 was a stub; this is the real implementation. Auth comes from
`Settings.observability.telegram_*`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
from loguru import logger

from janus.config.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class TelegramAlert:
    severity: str           # info | warning | critical
    title: str
    body: str

    def to_text(self) -> str:
        emoji = {"info": "[i]", "warning": "[!]", "critical": "[X]"}[self.severity]
        return f"{emoji} *{self.title}*\n{self.body}"


class TelegramAlerter:
    def __init__(self, settings: Settings | None = None,
                 client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client or httpx.AsyncClient(timeout=10.0)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @property
    def enabled(self) -> bool:
        token = self.settings.observability.telegram_bot_token.get_secret_value()
        chat = self.settings.observability.telegram_chat_id
        return bool(token and chat)

    async def send(self, alert: TelegramAlert) -> bool:
        if not self.enabled:
            logger.debug("telegram disabled — would have sent: {}", alert.title)
            return False

        token = self.settings.observability.telegram_bot_token.get_secret_value()
        chat = self.settings.observability.telegram_chat_id
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            response = await self._client.post(url, json={
                "chat_id": chat, "text": alert.to_text(), "parse_mode": "Markdown",
            })
            response.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            # Don't escalate — alert delivery failure isn't worth more than a log.
            logger.warning("telegram send failed: {}", exc)
            return False
