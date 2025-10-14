from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .fetch import extract_domain, is_same_domain
import re


@dataclass
class ValidationIssue:
    field: str
    message: str
    details: Optional[str] = None


def _is_number(value: str) -> bool:
    if value is None:
        return False
    try:
        float(value)
        return True
    except Exception:
        return False


def _normalize_price(value: str) -> str:
    if value is None:
        return ''
    # Replace non-breaking spaces and regular spaces, remove thousands separators, replace comma with dot for decimals
    v = value.replace('\xa0', ' ').strip()
    # Remove spaces inside
    v = re.sub(r"[\s]", '', v)
    # Replace comma decimal to dot only if there's exactly one comma and no dot
    if ',' in v and '.' not in v:
        v = v.replace(',', '.')
    # Remove any non-digit/non-dot/non-minus characters
    v = re.sub(r"[^0-9.\-]", '', v)
    return v


def validate_offer(
    offer_fields: Dict[str, List[str]],
    feed_url: str,
) -> List[ValidationIssue]:
    from .config import load_settings
    settings = load_settings()
    domain = extract_domain(feed_url) or ''
    issues: List[ValidationIssue] = []

    # url (required, same-domain, non-empty)
    urls = offer_fields.get('url', [])
    if not urls or all(not u.strip() for u in urls):
        issues.append(ValidationIssue('url', 'Поле url пустое', 'Отсутствует значение url'))
    else:
        for u in urls:
            if not u.strip():
                issues.append(ValidationIssue('url', 'Поле url пустое'))
            elif not is_same_domain(u, domain, allow_subdomains=settings.allow_subdomains):
                issues.append(ValidationIssue('url', f'Url не содержит домен {domain}', f'Найден url: {u}'))

    # name (required non-empty text)
    names = offer_fields.get('name', [])
    if not names or all(not n.strip() for n in names):
        issues.append(ValidationIssue('name', 'Поле name пустое'))

    # picture (required, url on same domain)
    pictures = offer_fields.get('picture', [])
    if not pictures or all(not p.strip() for p in pictures):
        issues.append(ValidationIssue('picture', 'Поле picture пустое'))
    else:
        for p in pictures:
            if not p.strip():
                issues.append(ValidationIssue('picture', 'Поле picture пустое'))
            elif not is_same_domain(p, domain, allow_subdomains=settings.allow_subdomains):
                issues.append(ValidationIssue('picture', 'Поле picture на чужом домене', f'Найден picture: {p}'))

    # price (required numeric)
    prices = [
        _normalize_price(pr)
        for pr in offer_fields.get('price', [])
    ]
    if not prices or all(not pr.strip() for pr in prices):
        issues.append(ValidationIssue('price', 'Поле price пустое'))
        price_value: Optional[float] = None
    else:
        price_value = None
        for pr in prices:
            if not _is_number(pr):
                issues.append(ValidationIssue('price', 'Поле price не число', f'Найдено: {pr!r}'))
            else:
                try:
                    price_value = float(pr)
                except Exception:
                    pass

    # oldprice (optional numeric, > price if both present)
    oldprices_raw = offer_fields.get('oldprice', [])
    oldprices = [_normalize_price(op) for op in oldprices_raw]
    for op in oldprices:
        if not op.strip():
            issues.append(ValidationIssue('oldprice', 'Поле oldprice пустое'))
        elif not _is_number(op):
            issues.append(ValidationIssue('oldprice', 'Поле oldprice не число', f'Найдено: {op!r}'))
        elif price_value is not None and float(op) <= price_value:
            issues.append(ValidationIssue('oldprice', 'oldprice должен быть больше price', f'oldprice={op}, price={price_value}'))

    return issues





