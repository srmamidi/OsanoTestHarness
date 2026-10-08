# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""Google Consent Mode v2: read the gcs / gcd parameters Google tags send, and the dataLayer order.

gcs = G1<ad_storage><analytics_storage>   (1 granted, 0 denied)
gcd = 1<N><ad_storage><N><analytics_storage><N><ad_user_data><N><ad_personalization>5
gcd letters: l not set | p denied default | q denied default+update | t granted default
             r denied default, granted update | m denied update only | n granted update only
             u granted default, denied update | v granted default+update
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from .catalog import host_matches, host_of

GOOGLE_TAG_HOSTS = ("google-analytics.com", "analytics.google.com", "doubleclick.net",
                    "googleadservices.com", "googlesyndication.com", "google.com")
# Measurement endpoints (not library downloads such as /pagead/conversion.js).
_HIT_PATHS = ("/collect", "/pagead/viewthroughconversion", "/pagead/1p-", "/pagead/conversion/",
              "/activity", "/ccm/")
GCD_LETTERS = {
    "l": ("not set", None), "p": ("denied by default", "denied"),
    "q": ("denied by default and update", "denied"), "t": ("granted by default", "granted"),
    "r": ("denied by default, granted by update", "granted"), "m": ("denied by update", "denied"),
    "n": ("granted by update", "granted"), "u": ("granted by default, denied by update", "denied"),
    "v": ("granted by default and update", "granted"),
}
GCD_SIGNALS = ("ad_storage", "analytics_storage", "ad_user_data", "ad_personalization")


def is_google_hit(url: str) -> bool:
    host = host_of(url)
    if not any(host_matches(host, h) for h in GOOGLE_TAG_HOSTS):
        return False
    path = urlsplit(url).path
    if path.endswith(".js"):
        return False
    return any(k in path for k in _HIT_PATHS)


def params(url: str) -> dict[str, str]:
    q = parse_qs(urlsplit(url).query, keep_blank_values=True)
    return {k: v[0] for k, v in q.items()}


def parse_gcs(value: str | None) -> dict | None:
    if not value or len(value) != 4 or not value.startswith("G1") or any(c not in "01" for c in value[2:]):
        return None
    return {"raw": value, "ad_storage": "granted" if value[2] == "1" else "denied",
            "analytics_storage": "granted" if value[3] == "1" else "denied"}


def parse_gcd(value: str | None) -> dict | None:
    if not value or len(value) < 9:
        return None
    letters = [value[i] for i in (2, 4, 6, 8)]
    if any(c not in GCD_LETTERS for c in letters):
        return None
    out = {"raw": value}
    for name, letter in zip(GCD_SIGNALS, letters):
        meaning, state = GCD_LETTERS[letter]
        out[name] = {"letter": letter, "meaning": meaning, "state": state}
    out["v2_signals_set"] = all(out[s]["letter"] != "l" for s in ("ad_user_data", "ad_personalization"))
    return out


def analytics_denied_ping(url: str) -> bool:
    """Advanced mode sends cookieless analytics pings while analytics is denied; those are allowed."""
    gcs = parse_gcs(params(url).get("gcs"))
    return bool(gcs and gcs["analytics_storage"] == "denied")


def _entry_args(entry) -> list | None:
    """gtag() pushes an arguments object, which the probe serialises as {"__args": [...]}."""
    if isinstance(entry, dict) and isinstance(entry.get("__args"), list):
        return entry["__args"]
    if isinstance(entry, list):
        return entry
    return None


def datalayer_order(entries: list) -> dict:
    """Index of the first consent default and the first tag-firing entry in dataLayer."""
    first_default = first_update = first_tag = None
    for i, entry in enumerate(entries or []):
        args = _entry_args(entry)
        if args and args[0] == "consent":
            if args[1:2] == ["default"] and first_default is None:
                first_default = i
            elif args[1:2] == ["update"] and first_update is None:
                first_update = i
        elif args and args[0] in ("js", "config", "event") and first_tag is None:
            first_tag = i
        elif isinstance(entry, dict) and entry.get("event") in ("gtm.js", "gtm.dom", "gtm.load") and first_tag is None:
            first_tag = i
    return {"first_consent_default": first_default, "first_consent_update": first_update,
            "first_tag_entry": first_tag}
