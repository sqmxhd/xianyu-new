"""Offline location lookup for proxy egress IP addresses."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import maxminddb
from ip2region import searcher, util

from .settings import settings


@dataclass(frozen=True, slots=True)
class ProxyIPLocation:
    country: str | None = None
    continent: str | None = None
    region: str | None = None
    city: str | None = None
    isp: str | None = None

    @property
    def label(self) -> str:
        parts: list[str] = []
        for value in (self.country, self.continent, self.region, self.city, self.isp):
            if value and (not parts or parts[-1] != value):
                parts.append(value)
        return " ".join(parts)


@lru_cache(maxsize=1)
def _ipv4_searcher() -> searcher.Searcher:
    database = Path(settings.ip2region_db_path).read_bytes()
    return searcher.new_with_buffer(util.IPv4, database)


@lru_cache(maxsize=1)
def _geoip_reader() -> maxminddb.Reader:
    return maxminddb.open_database(settings.geoip_db_path)


def _clean(value: str) -> str | None:
    normalized = value.strip()
    return None if not normalized or normalized == "0" or normalized.lower() == "null" else normalized


@lru_cache(maxsize=2048)
def lookup_proxy_ip(value: str) -> ProxyIPLocation:
    address = ipaddress.ip_address(value)
    if not address.is_global:
        return ProxyIPLocation(country="内网")
    if address.version != 4:
        record = _geoip_reader().get(str(address)) or {}
        return ProxyIPLocation(
            country=_clean(str(record.get("country_name") or record.get("country") or "")),
            continent=_clean(
                str(record.get("continent_name") or record.get("continent") or "")
            ),
        )

    raw = _ipv4_searcher().search(str(address))
    parts = (raw.split("|") + ["", "", "", "", ""])[:5]
    country, region, city, isp = (_clean(part) for part in parts[:4])
    return ProxyIPLocation(country=country, region=region, city=city, isp=isp)
