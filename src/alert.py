from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable, List, Optional

import pytz
import requests


@dataclass
class NegativeAlert:
    owner: str
    feed_url: str
    offer_id: str
    message: str
    details: Optional[str]


def now_str(timezone: str) -> str:
    tz = pytz.timezone(timezone)
    return dt.datetime.now(tz).strftime('%Y-%m-%d %H:%M')


def format_negative(alert: NegativeAlert, timezone: str) -> str:
    owner_title = {
        'anton': 'Антон',
        'ilya': 'Илья',
        'yura': 'Юра',
    }.get(alert.owner.lower(), alert.owner)
    parts = [
        f'🔔 Ошибка автотеста фидов (владелец: {owner_title})',
        '',
        f'⏰ Время: {now_str(timezone)}',
        f'🌍 Фид: {alert.feed_url}',
        f'🔗 Offer ID: {alert.offer_id or "-"}',
        f'❌ Ошибка: {alert.message}',
    ]
    if alert.details:
        parts.append(f'🔍 Детали: {alert.details}')
    return '\n'.join(parts)


def format_summary(total_feeds: int, bad_feeds: int, total_offers: int, bad_offers: int, total_issues: int, log_url: Optional[str], timezone: str) -> str:
    # Формат как в примере пользователя
    parts = [
        '✅ Общий отчет по проверке фидов',
        '',
        f'⏰ Время: {now_str(timezone)}',
        f'🌍 Проверено фидов: {total_feeds}',
        f'❌ Фидов с ошибками: {bad_feeds}',
    ]
    if log_url:
        parts.append(f'🔍 Лог: {log_url}')
    return '\n'.join(parts)


def summary_from_json(stats: dict, log_url: Optional[str], timezone: str) -> str:
    # Используется твоим джобом в 09:00/17:00: читает stats JSON и формирует текст
    total_feeds = int(stats.get('total_feeds', 0))
    bad_feeds = int(stats.get('feeds_with_errors', 0))
    return format_summary(total_feeds, bad_feeds, 0, 0, 0, log_url, timezone)


def send_telegram(token: Optional[str], chat_id: Optional[str], text: str) -> None:
    if not token or not chat_id:
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': text},
            timeout=10,
        )
    except Exception:
        # Network errors are swallowed; logs on disk retain message
        pass


