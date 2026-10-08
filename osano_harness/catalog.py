# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""Vendor catalog: decides what a seen request, cookie, iframe or storage key really is."""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from . import CATEGORIES, UNCLASSIFIED

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "config" / "vendor_catalog.yaml"


@dataclass(frozen=True)
class Match:
    category: str          # an Osano category, FIRST_PARTY, or UNCLASSIFIED
    vendor_id: str
    vendor_name: str


FIRST_PARTY = "FIRST_PARTY"


def host_of(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def host_matches(host: str, pattern: str) -> bool:
    host, pattern = host.lower().rstrip("."), pattern.lower().lstrip(".")
    return host == pattern or host.endswith("." + pattern)


def _host_path_match(host: str, path: str, pattern: str) -> bool:
    """'google.com/recaptcha' = host is google.com or a subdomain (label boundary) AND path starts /recaptcha.
    A plain substring would let fakegoogle.com/recaptcha pass as essential."""
    hpat, _, ppat = pattern.lower().partition("/")
    return host_matches(host, hpat) and (not ppat or path_prefix(path, "/" + ppat))


def path_prefix(path: str, prefix: str) -> bool:
    """Prefix on a segment boundary: /lib matches /lib, /lib/x.js, /lib.js — not /library-evil.js."""
    prefix = prefix.rstrip("/")
    return path == prefix or path.startswith(prefix + "/") or path.startswith(prefix + ".") or prefix == ""


def is_first_party(host: str, first_party_domains: list[str]) -> bool:
    return bool(host) and any(host_matches(host, d) for d in first_party_domains)


@lru_cache(maxsize=4)
def _load(path: str) -> tuple[dict, ...]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    vendors = tuple(data.get("vendors", []))
    bad = [v.get("id") for v in vendors if v.get("category") not in CATEGORIES]
    if bad:
        raise ValueError(f"vendor_catalog: unknown category for {bad}; use one of {CATEGORIES}")
    return vendors


class Catalog:
    def __init__(self, path: str | Path = DEFAULT_CATALOG, first_party_domains: list[str] | None = None):
        self.vendors = _load(str(path))
        self.first_party = list(first_party_domains or [])

    def _unknown(self, host: str) -> Match:
        if is_first_party(host, self.first_party):
            return Match(FIRST_PARTY, "first-party", "First-party (your own domain)")
        return Match(UNCLASSIFIED, "unknown", "Unknown / not in catalog")

    def classify_url(self, url: str) -> Match:
        host = host_of(url)
        # host + path only: the query string must not be able to reclassify a request
        # (?ref=https://www.google.com/recaptcha/... would otherwise make a tracker "essential").
        try:
            low = host + urlsplit(url).path.lower()
        except ValueError:
            low = host
        path = low[len(host):]
        for v in self.vendors:
            if any(host_matches(host, h) for h in v.get("hosts", [])) or \
               any(_host_path_match(host, path, s) for s in v.get("url_contains", [])):
                return Match(v["category"], v["id"], v.get("name", v["id"]))
        return self._unknown(host)

    def classify_cookie(self, name: str, domain: str = "") -> Match:
        for v in self.vendors:
            if any(fnmatch.fnmatchcase(name, p) for p in v.get("cookies", [])):
                return Match(v["category"], v["id"], v.get("name", v["id"]))
        # A first-party cookie nobody has classified is still unclassified: Osano needs a rule for it.
        return Match(UNCLASSIFIED, "unknown", "Unknown cookie")

    def classify_storage(self, key: str) -> Match:
        for v in self.vendors:
            if any(fnmatch.fnmatchcase(key, p) for p in v.get("storage", [])):
                return Match(v["category"], v["id"], v.get("name", v["id"]))
        return Match(UNCLASSIFIED, "unknown", "Unknown storage key")
