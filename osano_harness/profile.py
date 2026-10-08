# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""Loads one profile = one Osano property (e.g. production, or all lower environments).
A profile that cannot be trusted refuses to load (fail closed) instead of guessing."""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import yaml

from .scenarios import DEFAULT_SCENARIOS, SCENARIOS

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = "REPLACE-ME"
_WINDOWS_RESERVED = frozenset({"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                               *(f"lpt{i}" for i in range(1, 10))})

DEFAULTS: dict[str, Any] = {
    "consent_model_expected": "opt-in",       # opt-in | opt-out
    "google_consent_mode": "advanced",        # advanced | basic | none
    "banner_expected_on_first_visit": True,
    "expected_categories_when_accepted": ["ANALYTICS", "MARKETING"],
    "scenarios": list(DEFAULT_SCENARIOS),
    "osano": {
        "expected_customer_id": PLACEHOLDER,
        "expected_config_id": PLACEHOLDER,
        "script_url_regex": r"cmp\.osano\.com/(?P<customer>[^/]+)/(?P<config>[^/]+)/osano\.js",
        "expected_mode": "strict",            # listener | permissive | strict
        "consent_cookie_patterns": ["osano_consentmanager*"],
        "inject_event_listener": True,
        # Several selectors per button: the first visible one is clicked.
        # Confirm these against the live banner on the first real run (check BNR-02 tells you).
        "selectors": {
            "banner": [".osano-cm-dialog:not(.osano-cm-dialog--hidden)", ".osano-cm-window .osano-cm-dialog"],
            "accept_all": [".osano-cm-accept-all", ".osano-cm-button--type_accept"],
            "deny_all": [".osano-cm-denyAll", ".osano-cm-button--type_denyAll", ".osano-cm-deny"],
            "manage": [".osano-cm-manage", ".osano-cm-button--type_manage"],
            "save": [".osano-cm-save", ".osano-cm-button--type_save"],
            "category_toggle": ["input.osano-cm-toggle__input[data-category='{category}']",
                                "#osano-cm-drawer-toggle--category_{category}"],
        },
    },
    "crawl": {
        "headless": True,
        "timeout_ms": 45000,
        "settle_ms": 4000,
        "network_idle_ms": 6000,
        "polite_delay_ms": 1500,
        "viewport": {"width": 1366, "height": 900},
        "user_agent_suffix": "OsanoTestHarness/1.0",
        "screenshots": True,
    },
    "network": {
        # demo only: every non-local request is answered by built-in stubs; nothing leaves the machine.
        "offline_demo": False,
        "block_hosts": [],
    },
}


class ProfileError(ValueError):
    pass


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    if p.is_file():
        return p
    for candidate in (ROOT / p, ROOT / "config" / "profiles" / p, ROOT / "config" / "profiles" / f"{p}.yaml"):
        if candidate.is_file():
            return candidate
    raise ProfileError(f"Profile not found: {path}")


def load_profile(path: str | Path, *, allow_placeholders: bool = False) -> dict:
    file = resolve_path(path)
    try:
        raw = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ProfileError(f"Profile {file} is not valid YAML: {exc}") from None
    if not isinstance(raw, dict):
        raise ProfileError(f"Profile {file} must be a YAML mapping (key: value), not a {type(raw).__name__}")
    prof = _merge(DEFAULTS, raw)
    prof["_file"] = str(file)
    validate(prof, allow_placeholders=allow_placeholders)
    return prof


def _str_list(value) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v.strip() for v in value)


def _placeholders(value, path: str = "") -> list[str]:
    """Every setting (at any depth) whose value still contains REPLACE-ME."""
    if isinstance(value, dict):
        return [p for k, v in value.items() if not str(k).startswith("_") for p in _placeholders(v, f"{path}.{k}")]
    if isinstance(value, list):
        return [p for i, v in enumerate(value) for p in _placeholders(v, f"{path}[{i}]")]
    return [path.lstrip(".")] if isinstance(value, str) and PLACEHOLDER in value else []


def validate(prof: dict, *, allow_placeholders: bool = False) -> None:
    """Fail closed: anything the probe or the checks would misread is refused here, with every problem listed."""
    from urllib.parse import urlsplit

    from . import CATEGORIES
    problems: list[str] = []
    for key in ("name", "display_name", "environment"):
        if not isinstance(prof.get(key), str) or not prof[key].strip():
            problems.append(f"'{key}' is required (text)")
    # The name becomes a folder under runs/ and docs/reports/.
    if isinstance(prof.get("name"), str) and (not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", prof["name"])
                                              or prof["name"] in _WINDOWS_RESERVED):
        problems.append("'name' must be lower-case letters, digits and dashes, and not a Windows device name "
                        "(it becomes a folder name)")
    if not _str_list(prof.get("first_party_domains")):
        problems.append("'first_party_domains' must be a non-empty list of domains")
    if prof.get("consent_model_expected") not in ("opt-in", "opt-out"):
        problems.append("consent_model_expected must be opt-in or opt-out")
    if prof.get("google_consent_mode") not in ("advanced", "basic", "none"):
        problems.append("google_consent_mode must be advanced, basic or none")
    if not isinstance(prof.get("osano"), dict):
        problems.append("'osano' must be a mapping")
        prof["osano"] = {}
    osano = prof["osano"]
    if osano.get("expected_mode") not in ("listener", "permissive", "strict"):
        problems.append("osano.expected_mode must be listener, permissive or strict")
    try:
        rx = re.compile(str(osano.get("script_url_regex", "")))
        if not {"customer", "config"} <= set(rx.groupindex):
            problems.append("osano.script_url_regex needs named groups (?P<customer>...) and (?P<config>...)")
    except re.error as exc:
        problems.append(f"osano.script_url_regex is not a valid regular expression: {exc}")
    if not _str_list(osano.get("consent_cookie_patterns")):
        problems.append("osano.consent_cookie_patterns must be a non-empty list")
    sel = osano.get("selectors")
    if not isinstance(sel, dict):
        problems.append("osano.selectors must be a mapping")
    else:
        for key in ("banner", "accept_all", "deny_all", "manage", "save", "category_toggle"):
            # A plain string would be walked one character at a time — clicking "b", "t", "n"...
            if not _str_list(sel.get(key)):
                problems.append(f"osano.selectors.{key} must be a non-empty list of CSS selectors")
    scen = prof.get("scenarios")
    if not _str_list(scen):
        problems.append("'scenarios' must be a non-empty list")
    else:
        unknown = [s for s in scen if s not in SCENARIOS]
        if unknown:
            problems.append(f"unknown scenarios: {', '.join(unknown)} (known: {', '.join(SCENARIOS)})")
        if len(set(scen)) != len(scen):
            problems.append("'scenarios' lists a scenario twice")
    cats = prof.get("expected_categories_when_accepted")
    if not isinstance(cats, list) or any(c not in CATEGORIES for c in cats):
        problems.append(f"expected_categories_when_accepted must be a list of {CATEGORIES}")
    pages = prof.get("pages")
    if not isinstance(pages, list) or not pages or not all(isinstance(p, dict) for p in pages):
        problems.append("'pages' must be a non-empty list of {id, url} entries")
        pages = []
    ids = [p.get("id") for p in pages]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        problems.append("every page needs a unique text 'id'")
    for page in pages:
        url = str(page.get("url", ""))
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            problems.append(f"page {page.get('id')}: url must be a full http(s) address with a host")
        checks = page.get("journey_checks", [])
        if not isinstance(checks, list) or not all(isinstance(c, dict) and (c.get("selector") or c.get("js"))
                                                   for c in checks):
            problems.append(f"page {page.get('id')}: journey_checks must be a list of {{selector|js}} entries")
    # A placeholder left anywhere (not only the ids) means the profile was never finished.
    if not allow_placeholders:
        left = _placeholders({k: v for k, v in prof.items() if not k.startswith("_")})
        if left:
            problems.append("still contains REPLACE-ME: " + ", ".join(left)
                            + " (expected ids come from the osano.js URL in the Osano admin)")
    if problems:
        raise ProfileError(f"Profile {prof.get('_file', '?')} is not usable:\n  - " + "\n  - ".join(problems))
