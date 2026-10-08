# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""Osano configuration snapshot: the 3 x 3 grid (scripts / cookies / iframes x rules / discovered / ignored).

The harness stores one normalised shape, whatever the export looked like:

    {"property": "...", "mode": "strict", "captured_at": "...", "source": "...",
     "items": [{"type": "script|cookie|iframe", "section": "rules|discovered|ignored",
                "match": "connect.facebook.net", "category": "MARKETING" | null}]}

Export the configuration through your Osano MCP / REST calls, save the JSON, and pass it with
--osano-config. normalize() accepts the shape above, or {"scripts": {"rules": [...], ...}, ...}.
If your export looks different, adapt _SECTION_ALIASES / _MATCH_KEYS below; unknown shapes raise.
"""
from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path

from urllib.parse import urlsplit

from . import CATEGORIES
from .catalog import host_matches, path_prefix

TYPES = ("script", "cookie", "iframe")
SECTIONS = ("rules", "discovered", "ignored")
_TYPE_ALIASES = {"script": "script", "scripts": "script", "cookie": "cookie", "cookies": "cookie",
                 "iframe": "iframe", "iframes": "iframe"}
_SECTION_ALIASES = {"rules": "rules", "rule": "rules", "classified": "rules", "managed": "rules",
                    "discovered": "discovered", "discoveries": "discovered", "uncategorized": "discovered",
                    "unclassified": "discovered", "pending": "discovered",
                    "ignored": "ignored", "ignore": "ignored"}
_MATCH_KEYS = ("match", "pattern", "name", "domain", "url", "src", "value")
_CATEGORY_KEYS = ("category", "classification", "type_category")


class ConfigError(ValueError):
    pass


def _category(raw) -> str | None:
    if not raw:
        return None
    value = str(raw).strip().upper().replace("_", "-")
    if value in ("OPTOUT", "OPT-OUT"):
        value = "OPT-OUT"
    return value if value in CATEGORIES else None


def _item(type_: str, section: str, entry) -> dict:
    if isinstance(entry, str):
        match, raw_cat = entry, None
    elif isinstance(entry, dict):
        match = next((entry[k] for k in _MATCH_KEYS if entry.get(k)), None)
        raw_cat = next((entry[k] for k in _CATEGORY_KEYS if entry.get(k)), None)
    else:
        raise ConfigError(f"{type_}/{section} entry must be a string or an object, got {entry!r}")
    if not match or not str(match).strip():
        raise ConfigError(f"{type_}/{section} entry has none of {_MATCH_KEYS}: {entry!r}")
    cat = _category(raw_cat)
    # Fail closed: a classified rule must carry a category we understand, or no check can judge it.
    if section == "rules" and cat is None:
        raise ConfigError(f"{type_} rule {match!r} has a missing or unknown category {raw_cat!r} "
                          f"(expected one of {CATEGORIES})")
    return {"type": type_, "section": section, "match": str(match).strip(), "category": cat}


def normalize(raw: dict, *, source: str = "") -> dict:
    if not isinstance(raw, dict):
        raise ConfigError("Osano config export must be a JSON object")
    items: list[dict] = []
    if "items" in raw and not isinstance(raw["items"], list):
        raise ConfigError("'items' must be a list")
    if isinstance(raw.get("items"), list):
        for e in raw["items"]:
            if not isinstance(e, dict):
                raise ConfigError(f"every item must be an object, got {e!r}")
            t = _TYPE_ALIASES.get(str(e.get("type", "")).lower())
            s = _SECTION_ALIASES.get(str(e.get("section", "")).lower())
            if not t or not s:
                raise ConfigError(f"item needs type {TYPES} and section {SECTIONS}: {e!r}")
            items.append(_item(t, s, e))
    else:
        for key, block in raw.items():
            t = _TYPE_ALIASES.get(key.lower())
            if not t:
                continue
            if not isinstance(block, dict):
                raise ConfigError(f"'{key}' must map section -> list")
            for skey, entries in block.items():
                s = _SECTION_ALIASES.get(skey.lower())
                if not s:
                    raise ConfigError(f"unknown section '{skey}' under '{key}'")
                if entries is None:
                    continue
                if not isinstance(entries, list):
                    # A string here would be walked character by character into one-letter rules.
                    raise ConfigError(f"'{key}.{skey}' must be a list, got {type(entries).__name__}")
                items.extend(_item(t, s, e) for e in entries)
    if not items:
        raise ConfigError("no scripts/cookies/iframes found in the Osano export")
    return {"property": raw.get("property", ""), "mode": str(raw.get("mode", "")).lower(),
            "captured_at": raw.get("captured_at", ""), "source": raw.get("source", source),
            "items": items}


def load(path: str | Path) -> dict:
    p = Path(path)
    return normalize(json.loads(p.read_text(encoding="utf-8")), source=str(p))


def matrix(config: dict | None) -> dict:
    """{type: {section: count}} — the nine cells."""
    grid = {t: {s: 0 for s in SECTIONS} for t in TYPES}
    for it in (config or {}).get("items", []):
        grid[it["type"]][it["section"]] += 1
    return grid


def _matches(item: dict, value: str) -> bool:
    pat = item["match"].lower().strip()
    val = value.lower()
    if item["type"] == "cookie":
        return fnmatch.fnmatchcase(val, pat)
    # Normalise the pattern exactly like the value: exports often hold full URLs
    # ("https://connect.facebook.net/en_US/fbevents.js?v=2") — drop scheme, query and fragment.
    pat = re.sub(r"^[a-z][a-z0-9+.-]*://", "", pat).split("#", 1)[0].split("?", 1)[0].rstrip("/") or pat
    # Scripts / iframes: match host + path only. The query string is attacker-shaped text
    # (?ref=connect.facebook.net would otherwise match the Facebook rule).
    parts = urlsplit(val if "://" in val else "https://" + val)
    host, path = (parts.hostname or ""), parts.path
    if "/" in pat or "*" in pat:
        # Host part and path part are matched separately, the host on a label boundary — a plain
        # substring would let evil.example/x/cdn.vendor.com/lib.js borrow cdn.vendor.com's category.
        hpat, _, ppat = pat.partition("/")
        if not hpat:
            return False
        if "*" in hpat:
            host_ok = fnmatch.fnmatchcase(host, hpat) or fnmatch.fnmatchcase(host, "*." + hpat.lstrip("*."))
        else:
            host_ok = host_matches(host, hpat)
        if not host_ok or not ppat:
            return host_ok
        if "*" in ppat:
            return fnmatch.fnmatchcase(path, "/" + ppat + "*")
        return path_prefix(path, "/" + ppat)
    # A bare name is a host (label boundary) or a file name at the end of the path.
    return host_matches(host, pat) or path.endswith("/" + pat)


def lookup(config: dict | None, type_: str, value: str) -> dict | None:
    """The config entry covering this observed item. rules wins over ignored over discovered."""
    if not config:
        return None
    hits = [it for it in config["items"] if it["type"] == type_ and _matches(it, value)]
    for section in ("rules", "ignored", "discovered"):
        for it in hits:
            if it["section"] == section:
                return it
    return None


def duplicates_across_sections(config: dict | None) -> list[dict]:
    """Osano cannot publish when one item sits in both Rules and Ignored."""
    seen: dict[tuple[str, str], set[str]] = {}
    for it in (config or {}).get("items", []):
        seen.setdefault((it["type"], it["match"].lower()), set()).add(it["section"])
    return [{"type": t, "match": m, "sections": sorted(s)} for (t, m), s in seen.items()
            if {"rules", "ignored"} <= s]


def diff(before: dict | None, after: dict | None) -> list[dict]:
    """What moved between two config snapshots: added, removed, moved section, recategorised."""
    def index(cfg):
        return {(it["type"], it["match"].lower()): it for it in (cfg or {}).get("items", [])}
    b, a = index(before), index(after)
    out: list[dict] = []
    for key in sorted(set(b) | set(a)):
        old, new = b.get(key), a.get(key)
        if old and not new:
            out.append({"change": "removed", "type": key[0], "match": old["match"],
                        "before": f"{old['section']}/{old['category'] or '-'}", "after": "-"})
        elif new and not old:
            out.append({"change": "added", "type": key[0], "match": new["match"],
                        "before": "-", "after": f"{new['section']}/{new['category'] or '-'}"})
        elif old["section"] != new["section"] or old["category"] != new["category"]:
            change = "moved" if old["section"] != new["section"] else "recategorised"
            out.append({"change": change, "type": key[0], "match": new["match"],
                        "before": f"{old['section']}/{old['category'] or '-'}",
                        "after": f"{new['section']}/{new['category'] or '-'}"})
    return out
