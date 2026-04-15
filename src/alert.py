from __future__ import annotations

import datetime as dt
import html
import os
from dataclasses import dataclass
from typing import Iterable, List, Optional, Dict

import pytz
import requests


_PROXY_MISSING_ENV_LOGGED = False


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


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'y', 'on')


def _get_proxy_env(
    telegram_proxy_url: Optional[str] = None,
    telegram_proxy_auth_secret: Optional[str] = None,
    telegram_proxy_creds: Optional[str] = None,
) -> Optional[tuple[str, str, str]]:
    global _PROXY_MISSING_ENV_LOGGED

    proxy_url = (telegram_proxy_url or os.getenv('TELEGRAM_PROXY_URL') or '').strip()
    auth_secret = (telegram_proxy_auth_secret or os.getenv('TELEGRAM_PROXY_AUTH_SECRET') or '').strip()
    creds = (telegram_proxy_creds or os.getenv('TELEGRAM_PROXY_CREDS') or '').strip()

    missing = []
    if not proxy_url:
        missing.append('TELEGRAM_PROXY_URL')
    if not auth_secret:
        missing.append('TELEGRAM_PROXY_AUTH_SECRET')
    if not creds:
        missing.append('TELEGRAM_PROXY_CREDS')

    if missing:
        if not _PROXY_MISSING_ENV_LOGGED:
            print(f"[telegram][proxy] Missing required env vars: {', '.join(missing)}")
            _PROXY_MISSING_ENV_LOGGED = True
        return None

    return proxy_url, auth_secret, creds


def send_telegram(
    token: Optional[str],
    chat_id: Optional[str],
    text: str,
    *,
    use_telegram_proxy: Optional[bool] = None,
    telegram_proxy_url: Optional[str] = None,
    telegram_proxy_auth_secret: Optional[str] = None,
    telegram_proxy_creds: Optional[str] = None,
    telegram_proxy_timeout_sec: Optional[float] = None,
) -> None:
    use_proxy = _env_bool('USE_TELEGRAM_PROXY', False) if use_telegram_proxy is None else bool(use_telegram_proxy)
    if telegram_proxy_timeout_sec is None:
        try:
            timeout = float(os.getenv('TELEGRAM_PROXY_TIMEOUT_SEC', '15'))
        except Exception:
            timeout = 15.0
    else:
        timeout = float(telegram_proxy_timeout_sec)

    if use_proxy:
        proxy_env = _get_proxy_env(
            telegram_proxy_url=telegram_proxy_url,
            telegram_proxy_auth_secret=telegram_proxy_auth_secret,
            telegram_proxy_creds=telegram_proxy_creds,
        )
        if not proxy_env:
            return
        proxy_url, auth_secret, creds = proxy_env
        try:
            resp = requests.post(
                proxy_url,
                headers={
                    'Content-Type': 'application/json',
                    'X-Authentication': auth_secret,
                },
                json={
                    'title': html.escape('Runtime alert'),
                    'text': html.escape(text),
                    'creds': creds,
                    'parse_mode': 'HTML',
                    'disable_notification': False,
                },
                timeout=timeout,
            )
            if getattr(resp, 'status_code', 200) >= 400:
                print(f'[telegram][proxy] send failed: {resp.status_code} {getattr(resp, "text", "")[:180]}')
            return
        except requests.Timeout:
            print(f'[telegram][proxy] timeout after {timeout}s')
            return
        except requests.RequestException as exc:
            print(f'[telegram][proxy] transport error: {exc}')
            return
        except Exception:
            return

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
