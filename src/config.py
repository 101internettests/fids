import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from dotenv import load_dotenv, find_dotenv
from pathlib import Path


@dataclass
class OwnerFeeds:
    owner_name: str
    feeds: List[str]


@dataclass
class Settings:
    owners: Dict[str, OwnerFeeds]
    request_timeout_seconds: int
    user_agent: str
    timezone: str
    log_dir: str
    log_public_base_url: Optional[str]
    telegram_bot_token: Optional[str]
    telegram_chat_id: Optional[str]
    telegram_enabled: bool
    telegram_enabled_success: bool
    use_telegram_proxy: bool
    telegram_proxy_url: Optional[str]
    telegram_proxy_auth_secret: Optional[str]
    telegram_proxy_creds: Optional[str]
    telegram_proxy_timeout_sec: float
    fids_stat_path: Optional[str]
    probe_origin_enabled: bool
    allow_subdomains: bool


def _split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(',') if v.strip()]


def load_settings() -> Settings:
    # Надёжно подхватываем .env из корня репозитория, даже если current working directory другой
    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(env_path)
    else:
        load_dotenv()

    owners: Dict[str, OwnerFeeds] = {}
    # Support grouped owners via env and also a single FEEDS list
    anton = _split_csv(os.getenv('ANTON_FEEDS'))
    ilya = _split_csv(os.getenv('ILYA_FEEDS'))
    yura = _split_csv(os.getenv('YURA_FEEDS'))
    if anton:
        owners['anton'] = OwnerFeeds(owner_name='anton', feeds=anton)
    if ilya:
        owners['ilya'] = OwnerFeeds(owner_name='ilya', feeds=ilya)
    if yura:
        owners['yura'] = OwnerFeeds(owner_name='yura', feeds=yura)

    # FEEDS/FEED_URLS больше не поддерживаются — используем только владельцев

    timeout = int(os.getenv('REQUEST_TIMEOUT_SECONDS', '20'))
    ua = os.getenv('USER_AGENT', 'FeedMonitorBot/1.0 (+https://example.org)')
    tz = os.getenv('TIMEZONE', 'Europe/Berlin')
    log_dir = os.getenv('LOG_DIR', 'logs')
    log_public_base_url = os.getenv('LOG_PUBLIC_BASE_URL')
    tg_token = os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('BOT_TOKEN')
    tg_chat = os.getenv('TELEGRAM_CHAT_ID') or os.getenv('CHAT_ID')
    telegram_enabled = (os.getenv('TELEGRAM_ENABLED', 'true').lower() in ['1', 'true', 'yes', 'y', 'on'])
    telegram_enabled_success = (os.getenv('TELEGRAM_ENABLED_SU', 'true').lower() in ['1', 'true', 'yes', 'y', 'on'])
    use_telegram_proxy = (os.getenv('USE_TELEGRAM_PROXY', 'false').lower() in ['1', 'true', 'yes', 'y', 'on'])
    telegram_proxy_url = (os.getenv('TELEGRAM_PROXY_URL') or '').strip() or None
    telegram_proxy_auth_secret = (os.getenv('TELEGRAM_PROXY_AUTH_SECRET') or '').strip() or None
    telegram_proxy_creds = (os.getenv('TELEGRAM_PROXY_CREDS') or '').strip() or None
    try:
        telegram_proxy_timeout_sec = float(os.getenv('TELEGRAM_PROXY_TIMEOUT_SEC', '15'))
    except Exception:
        telegram_proxy_timeout_sec = 15.0
    fids_stat_path = os.getenv('FIDS_STAT_PATH')
    # Если путь относительный — интерпретируем его относительно корня репозитория (родителя src)
    if fids_stat_path and not os.path.isabs(fids_stat_path):
        repo_root = Path(__file__).resolve().parent.parent
        fids_stat_path = str((repo_root / fids_stat_path).resolve())
    probe_origin_enabled = (os.getenv('ORIGIN_PROBE_ENABLED', 'false').lower() in ['1', 'true', 'yes', 'y', 'on'])
    allow_subdomains = (os.getenv('ALLOW_SUBDOMAINS', 'false').lower() in ['1', 'true', 'yes', 'y', 'on'])

    return Settings(
        owners=owners,
        request_timeout_seconds=timeout,
        user_agent=ua,
        timezone=tz,
        log_dir=log_dir,
        log_public_base_url=log_public_base_url,
        telegram_bot_token=tg_token,
        telegram_chat_id=tg_chat,
        telegram_enabled=telegram_enabled,
        telegram_enabled_success=telegram_enabled_success,
        use_telegram_proxy=use_telegram_proxy,
        telegram_proxy_url=telegram_proxy_url,
        telegram_proxy_auth_secret=telegram_proxy_auth_secret,
        telegram_proxy_creds=telegram_proxy_creds,
        telegram_proxy_timeout_sec=telegram_proxy_timeout_sec,
        fids_stat_path=fids_stat_path,
        probe_origin_enabled=probe_origin_enabled,
        allow_subdomains=allow_subdomains,
    )

