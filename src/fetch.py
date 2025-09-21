from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

import requests


@dataclass
class FetchResult:
    url: str
    status_code: int
    content: Optional[bytes]
    error: Optional[str]


def fetch_url(url: str, timeout_seconds: int, user_agent: str) -> FetchResult:
    headers = {"User-Agent": user_agent}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout_seconds)
        return FetchResult(url=url, status_code=resp.status_code, content=resp.content, error=None)
    except Exception as exc:  # noqa: BLE001 - surface network errors
        return FetchResult(url=url, status_code=0, content=None, error=str(exc))


def extract_domain(url: str) -> Optional[str]:
    match = re.match(r"^https?://([^/]+)/?", url.strip())
    return match.group(1) if match else None


def is_same_domain(url: str, domain: str) -> bool:
    other = extract_domain(url or '') or ''
    return other.lower() == domain.lower()


XML_LINK_RE = re.compile(r"<url>\s*([^<\s]+)\s*</url>", re.IGNORECASE)


def extract_subfeed_links(feed_xml_bytes: bytes, parent_feed_url: str) -> List[str]:
    # Extract <url>...</url> links. Limit to same-domain XMLs.
    text = feed_xml_bytes.decode('utf-8', errors='ignore')
    candidates = [m.group(1).strip() for m in XML_LINK_RE.finditer(text)]
    parent_domain = extract_domain(parent_feed_url) or ''
    subfeeds: List[str] = []
    for link in candidates:
        if not link.lower().endswith('.xml'):
            continue
        if is_same_domain(link, parent_domain):
            subfeeds.append(link)
    return list(dict.fromkeys(subfeeds))


def iter_all_feed_urls(root_feed_url: str, root_content: bytes) -> Iterable[str]:
    # If URL ends with feed.xml – include extracted subfeeds. Always include the root itself.
    yield root_feed_url
    if root_feed_url.lower().endswith('feed.xml'):
        for sub in extract_subfeed_links(root_content, root_feed_url):
            yield sub


