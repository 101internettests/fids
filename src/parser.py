from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from lxml import etree


@dataclass
class Offer:
    id: str
    fields: Dict[str, List[str]]  # field -> list of values, preserves duplicates


def parse_offers(xml_bytes: bytes) -> List[Offer]:
    parser = etree.XMLParser(recover=True, remove_comments=True)
    root = etree.fromstring(xml_bytes, parser=parser)

    offers_xpath_candidates = [
        '//offer',  # YML-like
        '//item',   # RSS item fallback
    ]
    offer_nodes: List[etree._Element] = []
    for xp in offers_xpath_candidates:
        nodes = root.xpath(xp)
        if nodes:
            offer_nodes = nodes
            break

    offers: List[Offer] = []
    for node in offer_nodes:
        offer_id = node.get('id') or node.findtext('id') or ''
        fields: Dict[str, List[str]] = {}
        for tag in ['url', 'name', 'picture', 'price', 'oldprice']:
            values = [
                (child.text or '').strip()
                for child in node.findall(tag)
            ]
            # Some feeds use namespaced tags; try local-name wildcard search
            if not values:
                values = [
                    (el.text or '').strip()
                    for el in node.xpath(f'.//*[local-name()="{tag}"]')
                ]
            if values:
                fields[tag] = values
        offers.append(Offer(id=str(offer_id), fields=fields))

    return offers


