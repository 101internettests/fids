import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from dotenv import load_dotenv


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
    fids_stat_path: Optional[str]
    probe_origin_enabled: bool
    allow_subdomains: bool


def _split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(',') if v.strip()]


def load_settings() -> Settings:
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
    fids_stat_path = os.getenv('FIDS_STAT_PATH')
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
        fids_stat_path=fids_stat_path,
        probe_origin_enabled=probe_origin_enabled,
        allow_subdomains=allow_subdomains,
    )


