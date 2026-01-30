from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable, List, Optional, Dict

import pytz
import requests


@dataclass
class NegativeAlert:
    owner: str
    feed_url: str
    offer_id: str
    message: str
    details: Optional[str]
    hint: Optional[str] = None


def now_str(timezone: str) -> str:
    tz = pytz.timezone(timezone)
    return dt.datetime.now(tz).strftime('%Y-%m-%d %H:%M')


def format_negative(alert: NegativeAlert, timezone: str) -> str:
    owner_title = {
        'anton': 'Антон',
        'ilya': 'Илья',
        'yura': 'Юра',
        'default': '—',
    }.get((alert.owner or '').lower(), alert.owner)
    prefix = f'🔔 Ошибка автотеста фидов (владелец: {owner_title})' if owner_title else '🔔 Ошибка автотеста фидов'
    parts = [
        prefix,
        '',
        f'⏰ Время: {now_str(timezone)}',
        f'🌍 Фид: {alert.feed_url}',
        f'🔗 Offer ID: {alert.offer_id or "-"}',
        f'❌ Ошибка: {alert.message}',
    ]
    if alert.details:
        parts.append(f'🔍 Детали: {alert.details}')
    if getattr(alert, 'hint', None):
        parts.append(f'📝 Возможная причина: {alert.hint}')
    return '\n'.join(parts)


def format_summary(total_feeds: int, bad_feeds: int, total_offers: int, bad_offers: int, total_issues: int, log_url: Optional[str], timezone: str) -> str:
    # Формат суточного отчёта со всеми основными метриками
    parts = [
        '✅ Общий отчет по проверке фидов',
        '',
        f'⏰ Время: {now_str(timezone)}',
        f'🌍 Проверено фидов: {total_feeds}',
        f'❌ Фидов с ошибками: {bad_feeds}',
        f'📦 Всего офферов: {total_offers}',
        f'⚠️ Офферов с ошибками: {bad_offers}',
        f'🧩 Всего ошибок: {total_issues}',
    ]
    if log_url:
        parts.append(f'📄 Лог: {log_url}')
    return '\n'.join(parts)


def summary_from_json(stats: dict, log_url: Optional[str], timezone: str) -> str:
    # Используется твоим джобом в 09:00/17:00: читает stats JSON и формирует текст
    total_feeds = int(stats.get('total_feeds', 0))
    bad_feeds = int(stats.get('feeds_with_errors', 0))
    total_offers = int(stats.get('total_offers', 0))
    bad_offers = int(stats.get('offers_with_errors', 0))
    total_issues = int(stats.get('total_issues', 0))
    return format_summary(total_feeds, bad_feeds, total_offers, bad_offers, total_issues, log_url, timezone)


def format_grouped_negative(owner: str, feed_url: str, issues_by_offer: Dict[str, List[object]], timezone: str) -> str:
    # Back-compat: ValidationAlert type alias for ValidationIssue-like objects
    return _format_grouped(owner, feed_url, issues_by_offer, timezone)


def _format_grouped(owner: str, feed_url: str, issues_by_offer: Dict[str, List[object]], timezone: str) -> str:
    owner_title = {
        'anton': 'Антон',
        'ilya': 'Илья',
        'yura': 'Юра',
        'default': '—',
    }.get((owner or '').lower(), owner)
    header = f'🔔 Ошибка автотеста фидов (владелец: {owner_title})' if owner_title else '🔔 Ошибка автотеста фидов'
    parts: List[str] = [
        header,
        '',
        f'⏰ Время: {now_str(timezone)}',
        f'🌍 Фид: {feed_url}',
        '❌ Найдены проблемы в офферах:',
    ]
    for offer_id, issues in issues_by_offer.items():
        parts.append(f'- Offer ID: {offer_id or "-"}')
        for issue in issues:
            msg = getattr(issue, 'message', str(issue))
            details = getattr(issue, 'details', None)
            line = f'  - {msg}'
            if details:
                line += f' ({details})'
            parts.append(line)
    return '\n'.join(parts)


def send_telegram(token: Optional[str], chat_id: Optional[str], text: str) -> None:
    if not token or not chat_id:
        return
    try:
        resp = requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': text},
            timeout=10,
        )
        # Best-effort: print non-200 for easier debugging
        if getattr(resp, 'status_code', 200) >= 400:
            print(f'[telegram] sendMessage failed: {resp.status_code} {getattr(resp, "text", "")}')
    except Exception:
        # Network errors are swallowed; logs on disk retain message
        pass


def format_recovery(owner: str, feed_url: str, timezone: str) -> str:
    owner_title = {
        'anton': 'Антон',
        'ilya': 'Илья',
        'yura': 'Юра',
        'default': '—',
    }.get((owner or '').lower(), owner)
    header = f'✅ Фид восстановился (владелец: {owner_title})' if owner_title else '✅ Фид восстановился'
    parts = [
        header,
        '',
        f'⏰ Время: {now_str(timezone)}',
        f'🌍 Фид: {feed_url}',
        '✓ Ошибок не обнаружено в текущем прогоне',
    ]
    return '\n'.join(parts)

