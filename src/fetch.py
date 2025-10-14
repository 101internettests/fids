from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

import time
import requests
from lxml import etree


@dataclass
class FetchResult:
    url: str
    status_code: int
    content: Optional[bytes]
    error: Optional[str]


def fetch_url(url: str, timeout_seconds: int, user_agent: str, connect_timeout: Optional[int] = None, read_timeout: Optional[int] = None, retries: int = 1) -> FetchResult:
    headers = {"User-Agent": user_agent}
    connect = connect_timeout or timeout_seconds
    read = read_timeout or timeout_seconds
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = requests.get(url, headers=headers, timeout=(connect, read))
            return FetchResult(url=url, status_code=resp.status_code, content=resp.content, error=None)
        except Exception as exc:  # noqa: BLE001
            if attempt > max(1, retries):
                return FetchResult(url=url, status_code=0, content=None, error=str(exc))
            time.sleep(min(2 ** (attempt - 1), 4))


def extract_domain(url: str) -> Optional[str]:
    match = re.match(r"^https?://([^/]+)/?", url.strip())
    return match.group(1) if match else None


def _normalize_host(host: str) -> str:
    h = (host or '').lower().strip()
    if h.startswith('www.'):
        h = h[4:]
    return h


def is_same_domain(url: str, domain: str, allow_subdomains: bool = False) -> bool:
    other = _normalize_host(extract_domain(url or '') or '')
    base = _normalize_host(domain or '')
    if not allow_subdomains:
        return other == base
    # allow foo.base
    return other == base or other.endswith('.' + base)


def extract_origin(url: str) -> Optional[str]:
    # returns scheme://host or None
    m = re.match(r"^(https?://[^/]+)/?", url.strip())
    return m.group(1) if m else None


def extract_subfeed_links(feed_xml_bytes: bytes, parent_feed_url: str) -> List[str]:
    # Parse XML and select url-like nodes ending with .xml within same domain
    parser = etree.XMLParser(recover=True, remove_comments=True)
    try:
        root = etree.fromstring(feed_xml_bytes, parser=parser)
    except Exception:
        return []
    parent_domain = extract_domain(parent_feed_url) or ''
    candidates: List[str] = []
    # Collect text of <url> elements
    for el in root.xpath('//*[local-name()="url"]'):
        t = (el.text or '').strip()
        if t:
            candidates.append(t)
    # Also consider <link> elements
    for el in root.xpath('//*[local-name()="link"]'):
        t = (el.text or '').strip()
        if t:
            candidates.append(t)
    subfeeds: List[str] = []
    for link in candidates:
        low = link.lower()
        if not low.endswith('.xml'):
            continue
        if is_same_domain(link, parent_domain):
            subfeeds.append(link)
    # de-duplicate
    return list(dict.fromkeys(subfeeds))


def iter_all_feed_urls(root_feed_url: str, root_content: bytes) -> Iterable[str]:
    # If URL ends with feed.xml – include extracted subfeeds. Always include the root itself.
    yield root_feed_url
    if root_feed_url.lower().endswith('feed.xml'):
        for sub in extract_subfeed_links(root_content, root_feed_url):
            yield sub



