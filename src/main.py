from __future__ import annotations
import datetime as dt
import os
from pathlib import Path
from typing import Dict, List, Tuple

import pytz
import sys
import json

# Импорты работают и в режиме пакета (python -m src.main), и при запуске как скрипт (python src/main.py)
try:
    from .config import Settings, load_settings
    from .fetch import fetch_url, extract_domain, iter_all_feed_urls, extract_origin, explain_fetch_problem
    from .parser import parse_offers
    from .validator import validate_offer, ValidationIssue
    from .alert import NegativeAlert, format_negative, format_summary, send_telegram
    from .alert import format_grouped_negative, summary_from_json
    from .alert import format_recovery
except Exception:  # noqa: BLE001
    from config import Settings, load_settings  # type: ignore
    from fetch import fetch_url, extract_domain, iter_all_feed_urls, extract_origin, explain_fetch_problem  # type: ignore
    from parser import parse_offers  # type: ignore
    from validator import validate_offer, ValidationIssue  # type: ignore
    from alert import NegativeAlert, format_negative, format_summary, send_telegram  # type: ignore
    from alert import format_grouped_negative, summary_from_json  # type: ignore
    from alert import format_recovery  # type: ignore
from typing import Dict


def ensure_log_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def today_log_file(log_dir: str, timezone: str) -> Path:
    tz = pytz.timezone(timezone)
    date_str = dt.datetime.now(tz).strftime('%Y-%m-%d')
    return ensure_log_dir(log_dir) / f'{date_str}-feed-test.log'


def append_log(log_path: Path, text: str) -> None:
    with log_path.open('a', encoding='utf-8') as f:
        f.write(text.rstrip() + '\n\n')


def log_public_url(settings: Settings, log_path: Path) -> str | None:
    if not settings.log_public_base_url:
        return None
    return settings.log_public_base_url.rstrip('/') + '/' + log_path.name

def stats_json_path(settings: Settings, log_dir_path: Path) -> Path:
    # Определяем путь к JSON: если указан FIDS_STAT_PATH и это директория – храним в <dir>/fids_stat.json
    if getattr(settings, 'fids_stat_path', None):
        base = Path(settings.fids_stat_path)
        return base if base.suffix.lower() == '.json' else (base / 'fids_stat.json')
    return log_dir_path / 'fids_stat.json'

def feed_state_json_path(settings: Settings, log_dir_path: Path) -> Path:
    """
    Хранение последних статусов фидов (ok/error) для оповещений о восстановлении.
    По умолчанию лежит рядом с логами, но если задан FIDS_STAT_PATH — кладём в ту же папку,
    чтобы файл гарантированно переживал перезапуски джоба.
    """
    if getattr(settings, 'fids_stat_path', None):
        base = Path(settings.fids_stat_path)
        state_dir = base.parent if base.suffix.lower() == '.json' else base
        return state_dir / 'feed_state.json'
    return log_dir_path / 'feed_state.json'


def save_feed_state(feed_state_path: Path, feed_state: Dict[str, str]) -> None:
    # Best-effort: состояние нужно для recovery, не должно валить прогон
    try:
        feed_state_path.parent.mkdir(parents=True, exist_ok=True)
        with feed_state_path.open('w', encoding='utf-8') as f:
            json.dump(feed_state, f, ensure_ascii=False)
    except Exception:
        pass


def log_info(log_path: Path, message: str) -> None:
    # На Windows консоль часто cp1251 и падает на emoji/символах.
    # Логи пишем всегда в UTF-8, а в консоль печатаем best-effort без падения прогона.
    try:
        print(message)
    except UnicodeEncodeError:
        try:
            sys.stdout.buffer.write((message + '\n').encode('utf-8', errors='replace'))
            sys.stdout.flush()
        except Exception:
            # last resort: не падаем
            print(message.encode('ascii', errors='backslashreplace').decode('ascii'))
    append_log(log_path, message)



def process_feed(settings: Settings, owner: str, feed_url: str, log_path: Path) -> Tuple[bool, int, int, int]:
    # Returns (has_error, offers_checked)
    log_info(log_path, f'▶ Проверка фида: {feed_url} (владелец: {owner})')
    res = fetch_url(feed_url, settings.request_timeout_seconds, settings.user_agent)
    if res.error or res.status_code >= 400 or not res.content:
        hint = explain_fetch_problem(feed_url, res.status_code, res.error)
        alert = NegativeAlert(
            owner=owner,
            feed_url=feed_url,
            offer_id='-',
            message='Фид недоступен, поля не проверены',
            details=f'status={res.status_code}, error={res.error}',
            hint=hint,
        )
        text = format_negative(alert, settings.timezone)
        log_info(log_path, text)
        if settings.telegram_enabled:
            send_telegram(settings.telegram_bot_token, settings.telegram_chat_id, text)
        return True, 0, 0, 0

    has_error = False
    offers_checked = 0
    offers_with_errors = 0
    total_issues = 0

    log_info(log_path, f'✅ Фид доступен: status={res.status_code}, bytes={len(res.content or b"")}')

    # Iterate over root and subfeeds when root is feed.xml
    urls_to_check = list(iter_all_feed_urls(feed_url, res.content))
    log_info(log_path, f'🔗 Ссылок для проверки: {len(urls_to_check)}')
    for url in urls_to_check:
        log_info(log_path, f'→ Проверка ссылки: {url}')
        # Quick origin availability check — if site is down, skip noisy offer validations
        origin = extract_origin(url) or ''
        if settings.probe_origin_enabled and origin:
            origin_probe = fetch_url(origin, settings.request_timeout_seconds, settings.user_agent)
            if origin_probe.error or origin_probe.status_code >= 400:
                hint = explain_fetch_problem(origin, origin_probe.status_code, origin_probe.error)
                alert = NegativeAlert(owner, url, '-', 'Сайт недоступен, поля не проверены', f'status={origin_probe.status_code}, error={origin_probe.error}', hint)
                text = format_negative(alert, settings.timezone)
                log_info(log_path, text)
                if settings.telegram_enabled:
                    send_telegram(settings.telegram_bot_token, settings.telegram_chat_id, text)
                has_error = True
                continue

        sub = fetch_url(url, settings.request_timeout_seconds, settings.user_agent)
        if sub.error or sub.status_code >= 400 or not sub.content:
            hint = explain_fetch_problem(url, sub.status_code, sub.error)
            alert = NegativeAlert(owner, url, '-', 'Подфид недоступен, поля не проверены', f'status={sub.status_code}, error={sub.error}', hint)
            text = format_negative(alert, settings.timezone)
            log_info(log_path, text)
            if settings.telegram_enabled:
                send_telegram(settings.telegram_bot_token, settings.telegram_chat_id, text)
            has_error = True
            continue

        offers = parse_offers(sub.content)
        offers_checked += len(offers)
        log_info(log_path, f'📦 Найдено офферов: {len(offers)}')
        grouped: Dict[str, List[ValidationIssue]] = {}
        for offer in offers:
            issues: List[ValidationIssue] = validate_offer(offer.fields, url)
            if issues:
                offers_with_errors += 1
                total_issues += len(issues)
                grouped.setdefault(offer.id or '-', []).extend(issues)
        if grouped:
            text = format_grouped_negative(owner, url, grouped, settings.timezone)
            log_info(log_path, text)
            if settings.telegram_enabled:
                send_telegram(settings.telegram_bot_token, settings.telegram_chat_id, text)
            has_error = True
        else:
            log_info(log_path, '✓ Ошибок не найдено для этой ссылки')

    return has_error, offers_checked, offers_with_errors, total_issues


def main() -> None:
    settings = load_settings()
    log_path = today_log_file(settings.log_dir, settings.timezone)
    log_dir_path = ensure_log_dir(settings.log_dir)
    # Загружаем состояния фидов (для оповещений о восстановлении)
    feed_state_path = feed_state_json_path(settings, log_dir_path)
    feed_state: Dict[str, str] = {}
    try:
        if feed_state_path.exists():
            with feed_state_path.open('r', encoding='utf-8') as f:
                data = json.load(f) or {}
                if isinstance(data, dict):
                    feed_state = {str(k): str(v) for k, v in data.items()}
    except Exception:
        # игнорируем ошибки чтения состояния
        feed_state = {}
    # Режим суточного отчёта из JSON (для cron 09:00/17:00): python src/main.py --daily-summary
    if len(sys.argv) > 1 and sys.argv[1] in ('--daily-summary', '--send-daily', '--summary'):
        stats_path = stats_json_path(settings, log_dir_path)
        stats = {
            'total_feeds': 0,
            'feeds_with_errors': 0,
            'total_offers': 0,
            'offers_with_errors': 0,
            'total_issues': 0,
        }
        # Пытаемся прочитать из основного пути, иначе резервно из корня репо (fids_stat.json)
        for candidate in (stats_path, Path('fids_stat.json')):
            try:
                if candidate.exists():
                    with candidate.open('r', encoding='utf-8') as f:
                        data = json.load(f) or {}
                        if isinstance(data, dict):
                            stats.update(data)
                            break
            except Exception:
                continue
        # Формируем суточный отчёт по готовым данным
        text = summary_from_json(stats, log_public_url(settings, log_path), settings.timezone)
        print(text)
        append_log(log_path, text)
        if settings.telegram_enabled and settings.telegram_enabled_success:
            send_telegram(settings.telegram_bot_token, settings.telegram_chat_id, text)
        return

    total_feeds = 0
    feeds_with_errors = 0
    total_offers = 0
    offers_with_errors = 0
    total_issues = 0

    for owner_key, owner in settings.owners.items():
        for feed_url in owner.feeds:
            total_feeds += 1
            has_error, offers_count, offers_err, issues_cnt = process_feed(settings, owner_key, feed_url, log_path)
            total_offers += offers_count
            offers_with_errors += offers_err
            total_issues += issues_cnt
            if has_error:
                feeds_with_errors += 1
            # Определяем текущее и предыдущее состояние фида
            new_state = 'error' if has_error else 'ok'
            prev_state = feed_state.get(feed_url)
            # Отправляем уведомление о восстановлении при переходе ERROR -> OK
            if prev_state == 'error' and new_state == 'ok':
                text = format_recovery(owner_key, feed_url, settings.timezone)
                log_info(log_path, text)
                if settings.telegram_enabled:
                    send_telegram(settings.telegram_bot_token, settings.telegram_chat_id, text)
            # Обновляем состояние
            feed_state[feed_url] = new_state
            # Сохраняем сразу после каждого фида, чтобы recovery не терялся при падениях позже по прогону
            save_feed_state(feed_state_path, feed_state)
    
    # Обновляем суточную статистику в JSON (fids_stat)
    stats_path = stats_json_path(settings, log_dir_path)

    today = pytz.timezone(settings.timezone).localize(dt.datetime.now()).strftime('%Y-%m-%d')
    stats = {
        'date': today,
        'total_feeds': 0,
        'feeds_with_errors': 0,
        'total_offers': 0,
        'offers_with_errors': 0,
        'total_issues': 0,
    }
    try:
        if stats_path.exists():
            with stats_path.open('r', encoding='utf-8') as f:
                prev = json.load(f)
            if prev.get('date') == today:
                stats.update({k: int(prev.get(k, 0)) for k in stats.keys() if k != 'date'})
    except Exception:
        pass

    stats['total_feeds'] += total_feeds
    stats['feeds_with_errors'] += feeds_with_errors
    stats['total_offers'] += total_offers
    stats['offers_with_errors'] += offers_with_errors
    stats['total_issues'] += total_issues

    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with stats_path.open('w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False)

    # Финальная запись состояний (на всякий случай)
    save_feed_state(feed_state_path, feed_state)

    # Отправляем позитивное сообщение по итогам текущего прогона
    run_text = format_summary(
        total_feeds,
        feeds_with_errors,
        total_offers,
        offers_with_errors,
        total_issues,
        None,
        settings.timezone,
    )
    print(run_text)
    append_log(log_path, run_text)
    if settings.telegram_enabled and settings.telegram_enabled_success:
        send_telegram(settings.telegram_bot_token, settings.telegram_chat_id, run_text)



if __name__ == '__main__':
    main()


