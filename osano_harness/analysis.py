# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""Turns raw probe observations into checks (pass/fail) and metrics.

Analysis is a pure function of (profile, observations, osano config, catalog), so two saved runs
can be re-analysed with the same rules before they are compared — apples to apples.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from . import NON_ESSENTIAL, UNCLASSIFIED
from . import google_consent as gcm
from . import osano_config
from .catalog import FIRST_PARTY, Catalog, host_of, is_first_party
from .probe import osano_script_ids
from .scenarios import SCENARIOS, allowed_categories, expected_gcs

SEVERITY_WEIGHT = {"high": 5, "medium": 3, "low": 1, "info": 0}

# id: (title, severity, what it proves, how to fix)
CHECKS: dict[str, tuple[str, str, str, str]] = {
    "OSN-01": ("Osano script loads", "high",
               "osano.js is requested on the page.", "Add the Osano script tag from Osano admin > Get Code."),
    "OSN-02": ("Osano loads before every other third-party script", "high",
               "Osano can only block what loads after it.",
               "Move osano.js to the very top of <head>, above GTM and any tag."),
    "OSN-03": ("Osano configuration matches this property", "high",
               "The customer/config id in osano.js is the one expected for this environment.",
               "Production pages must use the production config id; lower environments the LLE one."),
    "OSN-04": ("Osano loads only once", "medium",
               "Two copies (hard-coded + GTM) fight over consent.", "Remove the duplicate tag."),
    "OSN-05": ("Compliance mode is the expected one", "high",
               "Osano.cm.mode at runtime (listener / permissive / strict).",
               "Publish the configuration with the intended mode."),
    "OSN-06": ("Consent model is the expected one", "medium",
               "Osano.cm.consentModel (opt-in / opt-out) for this visitor's jurisdiction.",
               "Check jurisdiction settings in Osano."),
    "BNR-01": ("Banner shown to a new visitor", "high",
               "A brand-new visitor sees the consent banner.", "Check the banner is enabled for this region."),
    "BNR-02": ("Consent click applied and confirmed by Osano", "high",
               "After clicking, Osano.cm.getConsent() reports the intended choice.",
               "If ERROR: the harness could not find the button — update osano.selectors in the profile."),
    "BNR-03": ("Banner stays hidden after a choice", "medium",
               "Reloading after a choice does not ask again.", "Check the consent cookie domain/path."),
    "BNR-04": ("Choice stored in the consent cookie", "medium",
               "The Osano consent cookie exists after a choice.", "Check cookie domain and SameSite settings."),
    "CNS-01": ("No disallowed third-party requests before a choice", "high",
               "Nothing non-essential leaves the browser on arrival (opt-in) or after GPC.",
               "Classify the vendor in Osano, or gate the tag on consent."),
    "CNS-02": ("No disallowed cookies before a choice", "high",
               "No analytics/marketing cookies are written on arrival.", "Classify the cookie in Osano."),
    "CNS-03": ("No disallowed iframes before a choice", "high",
               "Embedded players/widgets that track do not load on arrival.", "Classify the iframe in Osano."),
    "CNS-04": ("Choice respected: no disallowed requests", "high",
               "After the choice (and a reload) only allowed categories send requests.",
               "Classify or re-classify the vendor; remove hard-coded tags that bypass Osano."),
    "CNS-05": ("Choice respected: no disallowed cookies", "high",
               "After the choice only allowed categories have cookies.",
               "Classify the cookie; a cookie set before the choice also lands here."),
    "CNS-06": ("Choice respected: no disallowed iframes", "high",
               "After the choice only allowed iframes load.", "Classify the iframe in Osano."),
    "CNS-07": ("Every third-party item is classified", "medium",
               "Seen items unknown to both the vendor catalog and Osano rules.",
               "Classify them in Osano (Discovered -> Rules) and add them to vendor_catalog.yaml."),
    "CNS-08": ("Accept all: expected categories actually run", "medium",
               "Catches over-blocking: analytics/marketing silently dead after Accept.",
               "Check the vendor is classified in the right category, not blocked by Strict mode."),
    "GPC-01": ("Global Privacy Control honoured", "high",
               "With the GPC signal, Osano records marketing as denied.", "Enable GPC support in Osano."),
    "GCM-01": ("Consent default set before Google tags", "high",
               "dataLayer has gtag('consent','default',...) before any config/event.",
               "Set the consent default (Osano's Google Consent Mode setting) above GTM."),
    "GCM-02": ("Google hits carry the right consent state (gcs)", "high",
               "gcs=G1<ads><analytics> matches the visitor's choice.",
               "Enable Osano's Google Consent Mode integration; check category mapping."),
    "GCM-03": ("Consent Mode v2 signals present (gcd)", "medium",
               "ad_user_data and ad_personalization are set, as Google requires for EEA ads.",
               "Upgrade to Consent Mode v2 in Osano / GTM."),
    "FUN-01": ("Page responds without error", "high",
               "HTTP status below 400 and the page loaded.", "Check the URL and the environment."),
    "FUN-02": ("Key page functions work under this choice", "high",
               "Journey checks from the profile (form visible, autocomplete loaded...).",
               "Something essential was classified as non-essential and got blocked."),
    "FUN-03": ("No JavaScript errors on the page", "low",
               "Uncaught page errors; blocking often breaks code that expects a tag to exist.",
               "Guard calls to optional vendors (e.g. `window.fbq && fbq(...)`)."),
    "CFG-01": ("Osano classification agrees with the vendor catalog", "medium",
               "An Osano rule puts a vendor in a different category than it really is.",
               "Fix the category in Osano, or correct vendor_catalog.yaml if the catalog is wrong."),
    "CFG-02": ("Seen items are classified in Osano", "medium",
               "Items seen on the site that are only in Discovered, or missing from the config.",
               "Classify them in Osano and publish."),
    "CFG-03": ("No non-essential item in Ignored", "high",
               "In Permissive mode Ignored items run as Essential — a tracker there bypasses consent.",
               "Move it from Ignored to Rules with the right category."),
    "CFG-04": ("No item in both Rules and Ignored", "medium",
               "Osano cannot publish a configuration with this conflict.", "Remove one of the two entries."),
    "CFG-05": ("No essential item in Ignored under Strict mode", "medium",
               "In Strict mode Ignored items are blocked — an essential one breaks the site.",
               "Move it to Rules as Essential."),
}

_MODE_MAP = {"production": "strict", "strict": "strict", "permissive": "permissive",
             "listener": "listener", "discovery": "listener", "debug": "listener"}


class _Ctx:
    def __init__(self, profile: dict, config: dict | None, catalog: Catalog):
        self.profile, self.config, self.catalog = profile, config, catalog
        self.model = profile["consent_model_expected"]
        self.gcm_mode = profile["google_consent_mode"]
        self.osano_re = profile["osano"]["script_url_regex"]

    def classify(self, kind: str, value: str, domain: str = "") -> dict:
        """kind: request | cookie | iframe | storage."""
        if kind == "cookie":
            m = self.catalog.classify_cookie(value, domain)
            cfg = osano_config.lookup(self.config, "cookie", value)
        elif kind == "storage":
            m, cfg = self.catalog.classify_storage(value), None
        else:
            m = self.catalog.classify_url(value)
            cfg = osano_config.lookup(self.config, "iframe" if kind == "iframe" else "script", value)
        category = m.category
        # The catalog is the truth when it knows the vendor; otherwise Osano's own rule decides —
        # except ESSENTIAL: an unknown vendor Osano calls essential would bypass every consent check,
        # so it stays UNCLASSIFIED (fail closed) until the catalog confirms it.
        if (category == UNCLASSIFIED and cfg and cfg["section"] == "rules" and cfg["category"]
                and cfg["category"] != "ESSENTIAL"):
            category = cfg["category"]
        return {"category": category, "vendor": m.vendor_id, "vendor_name": m.vendor_name,
                "catalog_category": m.category,
                "config_section": cfg["section"] if cfg else ("n/a" if self.config is None else "missing"),
                "config_category": cfg["category"] if cfg else None}

    def disallowed(self, cls: dict, allowed: frozenset[str], url: str = "") -> bool:
        cat = cls["category"]
        if cat in ("ESSENTIAL", FIRST_PARTY):
            return False
        if url and self.gcm_mode == "advanced" and gcm.is_google_hit(url):
            gcs = gcm.parse_gcs(gcm.params(url).get("gcs"))
            if gcs and cat == "ANALYTICS" and gcs["analytics_storage"] == "denied":
                return False      # cookieless ping, allowed in Advanced mode
            if gcs and cat == "MARKETING" and gcs["ad_storage"] == "denied":
                return False
        if cat == UNCLASSIFIED:
            # Unknown counts as non-essential: allowed only when everything is allowed.
            return not set(NON_ESSENTIAL) <= allowed
        return cat not in allowed


PARTIAL_PAGE = "Not judged: some consent choices on this page could not be probed"
PARTIAL_RUN = "Not judged: some pages or consent choices could not be probed"


def _whole_view(found: bool, partial: bool) -> str:
    """Checks over everything seen: a finding is real even on a partial view, a clean bill is not."""
    return "fail" if found else ("error" if partial else "pass")


def usable(obs: dict) -> bool:
    """One definition everywhere: an observation can be judged only if it has no error and both phases."""
    ph = obs.get("phases") or {}
    return not obs.get("error") and bool(ph.get("pre_consent")) and bool(ph.get("after_reload"))


def _phase_allowed(scenario, phase: str, model: str) -> frozenset[str]:
    if phase == "pre_consent" and scenario.action != "none":
        return allowed_categories(SCENARIOS["gpc_signal" if scenario.gpc else "no_choice"], model)
    return allowed_categories(scenario, model)


def _label(cls: dict, text: str) -> str:
    return f"{cls['category']} · {text}"


def _short(url: str, n: int = 0) -> str:
    u = re.sub(r"^https?://", "", url)
    # Full URL, never cut: the query string is often the evidence (gcs, event names, ids).
    return u


def analyse(profile: dict, observations: list[dict], config: dict | None, catalog: Catalog) -> dict:
    cx = _Ctx(profile, config, catalog)
    findings: list[dict] = []

    def add(cid, status, page, scenario, detail="", evidence=None):
        title, sev, _, _ = CHECKS[cid]
        findings.append({"id": cid, "title": title, "severity": sev, "status": status,
                         "page": page, "scenario": scenario, "detail": detail,
                         "evidence": list(evidence or [])})

    inventory: dict[tuple[str, str], dict] = {}
    scen_metrics: dict[str, Counter] = defaultdict(Counter)
    page_scen: dict[str, dict] = {}
    perf: dict[str, dict] = {}
    blocked_events: Counter = Counter()
    unclassified_by_page: dict[str, set[str]] = defaultdict(set)

    broken_functions: set[tuple[str, str]] = set()

    def unclassified(page, label, cls):
        note = " (Osano calls it ESSENTIAL — confirm and add it to the vendor catalog)" \
            if cls.get("config_category") == "ESSENTIAL" else ""
        unclassified_by_page[page].add(label + note)

    def inv(kind, key, cls, scenario, phase, bad, extra=None):
        # Keyed by vendor too: one host (e.g. www.google.com) can serve an essential and a marketing vendor.
        item = inventory.setdefault((kind, key, cls["vendor"]), {
            "kind": kind, "key": key, "vendor_id": cls["vendor"], "category": cls["category"],
            "vendor": cls["vendor_name"],
            "config_section": cls["config_section"], "config_category": cls["config_category"],
            "catalog_category": cls["catalog_category"], "scenarios": set(), "disallowed_in": set(),
            "pages": set(), **(extra or {})})
        item["scenarios"].add(scenario)
        item["pages"].add(page_id)   # the page currently being analysed (loop below)
        if bad:
            item["disallowed_in"].add(f"{scenario}/{phase}")
        return item

    journeys_by_page = {p.get("id"): p.get("journey_checks") for p in profile.get("pages", [])}
    by_page: dict[str, list[dict]] = defaultdict(list)
    for obs in observations:
        by_page[obs["page_id"]].append(obs)

    for page_id, obs_list in by_page.items():
        for obs in obs_list:
            scen = SCENARIOS[obs["scenario"]]
            sid = scen.id
            m = Counter()
            # ---- FUN-01 ----
            pre = obs["phases"].get("pre_consent")
            rel = obs["phases"].get("after_reload")
            if not usable(obs):
                add("FUN-01", "error", page_id, sid, f"Probe error: {obs.get('error') or 'missing phase'}")
                # Fail closed: the checks this observation would have judged are ERROR, never absent —
                # absent would read as "gone" in a comparison and lower the risk.
                would = (["CNS-01", "CNS-02", "CNS-03"] if scen.action == "none"
                         else ["BNR-02", "BNR-03", "BNR-04", "CNS-04", "CNS-05", "CNS-06"])
                would += (["GPC-01"] if scen.gpc else []) + (["BNR-01"] if sid == "no_choice" else [])
                would += ["FUN-02"] if journeys_by_page.get(page_id) else []
                would += ["GCM-02"] if cx.gcm_mode != "none" else []
                for cid in would:
                    add(cid, "error", page_id, sid, "Not judged: the page could not be probed")
                if sid == "accept_all":
                    add("CNS-08", "error", page_id, "accept_all", "Not judged: the page could not be probed")
                page_scen[f"{page_id}|{sid}"] = {"error": True, "unjudged": 1}
                scen_metrics[sid]["unjudged"] += 1
                continue
            statuses = [s for s in (pre.get("status"), rel.get("status")) if s]
            bad_status = [s for s in statuses if s >= 400]
            if not statuses:
                add("FUN-01", "error", page_id, sid, "No HTTP status was captured for the page")
            else:
                add("FUN-01", "fail" if bad_status else "pass", page_id, sid,
                    f"HTTP {bad_status[0]}" if bad_status else f"HTTP {statuses[0]}")

            # ---- BNR-02: was the click applied and confirmed? ----
            action_ok = True
            act = obs.get("consent_action")
            if scen.action != "none":
                post = obs["phases"].get("post_consent") or {}
                recorded = (post.get("osano") or {}).get("consent") or {}
                intended = (act or {}).get("intended") or {}
                if not act or not act.get("applied"):
                    action_ok = False
                    add("BNR-02", "error", page_id, sid,
                        f"Harness could not apply the choice: {(act or {}).get('error', 'unknown')}",
                        (act or {}).get("steps", []))
                elif not recorded:
                    action_ok = False
                    add("BNR-02", "error", page_id, sid,
                        "Clicked, but Osano.cm.getConsent() returned nothing — the choice cannot be confirmed",
                        act.get("steps", []))
                else:
                    wrong = [f"{k}: wanted {v}, Osano recorded {recorded.get(k)}"
                             for k, v in intended.items() if recorded.get(k) != v]
                    action_ok = not wrong
                    add("BNR-02", "fail" if wrong else "pass", page_id, sid,
                        "Osano recorded a different choice" if wrong else "Osano confirmed the choice",
                        wrong or act.get("steps", []))

            # ---- per phase: requests, cookies, iframes ----
            gpc_ok = not scen.gpc or bool(pre.get("gpc") and rel.get("gpc"))
            phases = ["pre_consent"] + (["post_consent"] if scen.action != "none" else []) + ["after_reload"]
            bad_by_phase: dict[str, dict[str, list[str]]] = {}
            # Counted items are distinct trackers (host / cookie name / iframe host), not distinct URLs:
            # one analytics tag sending five hits is one leaking tracker. URLs stay as evidence.
            bad_keys: dict[str, dict[str, set]] = {}
            for phase in phases:
                allowed = _phase_allowed(scen, phase, cx.model)
                # After an unconfirmed click (or without the GPC signal) the page is not in the chosen state:
                # nothing there is a "leak".
                judged_phase = (phase == "pre_consent" or action_ok) and gpc_ok
                bad = {"requests": [], "cookies": [], "iframes": []}
                keys = {"requests": set(), "cookies": set(), "iframes": set()}
                for r in obs["requests"]:
                    if r["phase"] != phase or not r["third_party"]:
                        continue
                    kind = "iframe" if (r["type"] == "document" and not r["main_frame"]) else "request"
                    cls = cx.classify(kind, r["url"])
                    is_bad = cx.disallowed(cls, allowed, r["url"])
                    if cls["category"] == UNCLASSIFIED:
                        unclassified(page_id, f"request · {r['host']}", cls)
                    inv("iframe" if kind == "iframe" else "host", r["host"], cls, sid, phase,
                        is_bad and judged_phase)
                    if phase == "after_reload":
                        m[f"req_{cls['category']}"] += 1
                        m["third_party_requests"] += 1
                    if is_bad:
                        k = "iframes" if kind == "iframe" else "requests"
                        bad[k].append(_label(cls, _short(r["url"])))
                        keys[k].add(r["host"])
                snap = obs["phases"].get(phase) or {}
                for c in snap.get("cookies", []):
                    cls = cx.classify("cookie", c["name"], c["domain"])
                    is_bad = cx.disallowed(cls, allowed)
                    if cls["category"] == UNCLASSIFIED:
                        unclassified(page_id, f"cookie · {c['name']}", cls)
                    item = inv("cookie", c["name"], cls, sid, phase, is_bad and judged_phase,
                               {"domain": c["domain"], "secure": c.get("secure"), "httpOnly": c.get("httpOnly"),
                                "sameSite": c.get("sameSite"), "expires": c.get("expires")})
                    item.setdefault("set_in", set()).add(f"{sid}/{phase}")
                    if phase == "after_reload":
                        m[f"cookie_{cls['category']}"] += 1
                        m["cookies"] += 1
                    if is_bad:
                        bad["cookies"].append(_label(cls, f"{c['name']} ({c['domain']})"))
                        keys["cookies"].add(c["name"])
                for key in snap.get("local_storage", []):
                    cls = cx.classify("storage", key)
                    inv("storage", key, cls, sid, phase, False)
                bad_by_phase[phase] = {k: sorted(set(v)) for k, v in bad.items()}
                bad_keys[phase] = keys
                if phase == "after_reload":
                    m["iframes_loaded"] = sum(1 for r in obs["requests"] if r["phase"] == phase
                                              and r["type"] == "document" and not r["main_frame"])
                    m["third_party_hosts"] = len({r["host"] for r in obs["requests"]
                                                  if r["phase"] == phase and r["third_party"]})

            # ---- CNS-01..03: before any choice (only for no-click scenarios, to avoid duplicates) ----
            if scen.action == "none":
                pb = bad_by_phase["pre_consent"]
                for cid, key in (("CNS-01", "requests"), ("CNS-02", "cookies"), ("CNS-03", "iframes")):
                    if not gpc_ok:
                        add(cid, "error", page_id, sid, "Not judged: the GPC signal did not reach the page")
                        continue
                    add(cid, "fail" if pb[key] else "pass", page_id, sid,
                        f"{len(pb[key])} disallowed {key} before a choice" if pb[key] else "none", pb[key])
                m["pre_consent_violations"] = sum(len(v) for v in bad_keys["pre_consent"].values())

            # ---- CNS-04..06: after the choice ----
            if scen.action != "none":
                merged = {k: sorted(set(bad_by_phase["post_consent"][k]) | set(bad_by_phase["after_reload"][k]))
                          for k in ("requests", "cookies", "iframes")}
                for cid, key in (("CNS-04", "requests"), ("CNS-05", "cookies"), ("CNS-06", "iframes")):
                    if not action_ok:
                        add(cid, "error", page_id, sid, "Not judged: the consent choice was not confirmed (BNR-02)")
                        continue
                    add(cid, "fail" if merged[key] else "pass", page_id, sid,
                        f"{len(merged[key])} disallowed {key} after '{scen.title}'" if merged[key] else "none",
                        merged[key])
                if action_ok:
                    m["post_choice_violations"] = sum(len(bad_keys["post_consent"][k] | bad_keys["after_reload"][k])
                                                      for k in ("requests", "cookies", "iframes"))
                    m["violations"] = m["post_choice_violations"]
                else:
                    # The page was not in the state the choice names: its leak count means nothing.
                    m["unjudged"] = 1
            else:
                # No click: the stored state never changes, so arrival and reload are one view; count items once.
                m["violations"] = sum(len(bad_keys["pre_consent"][k] | bad_keys["after_reload"][k])
                                      for k in ("requests", "cookies", "iframes"))

            # ---- banner checks ----
            if sid == "no_choice":
                want = profile["banner_expected_on_first_visit"]
                add("BNR-01", "pass" if bool(pre.get("banner_visible")) == want else "fail", page_id, sid,
                    f"banner visible={pre.get('banner_visible')}, expected={want}")
            if scen.action != "none" and action_ok:
                add("BNR-03", "fail" if rel.get("banner_visible") else "pass", page_id, sid,
                    "banner shown again after reload" if rel.get("banner_visible") else "not shown again")
                pats = profile["osano"]["consent_cookie_patterns"]
                names = [c["name"] for c in rel.get("cookies", [])]
                has = any(re.fullmatch(p.replace("*", ".*"), n) for p in pats for n in names)
                add("BNR-04", "pass" if has else "fail", page_id, sid,
                    "consent cookie present" if has else f"no cookie matching {pats}")

            # ---- GPC ----
            if scen.gpc:
                consent = (rel.get("osano") or {}).get("consent") or {}
                if not gpc_ok:
                    add("GPC-01", "error", page_id, sid, "The GPC signal did not reach the page")
                    m["unjudged"] = 1            # the page was not in the GPC state: its leak count means nothing
                elif not (rel.get("osano") or {}).get("present"):
                    add("GPC-01", "error", page_id, sid, "Osano not present")
                elif "MARKETING" not in consent:
                    # Fail closed: no readable consent is "unknown", never "honoured".
                    add("GPC-01", "error", page_id, sid, "Osano.cm.getConsent() returned no MARKETING value",
                        [f"getConsent: {consent}"])
                else:
                    ok = consent["MARKETING"] == "DENY"
                    add("GPC-01", "pass" if ok else "fail", page_id, sid,
                        f"Osano MARKETING={consent['MARKETING']}", [f"getConsent: {consent}"])

            # ---- Google Consent Mode ----
            if cx.gcm_mode != "none":
                # Click scenarios are judged on what happens after the click; arrival is judged by no_choice.
                hits = [r for r in obs["requests"] if gcm.is_google_hit(r["url"])
                        and (scen.action == "none" or r["phase"] != "pre_consent")]
                wrong = []
                for r in hits:
                    exp = expected_gcs(scen, cx.model)
                    got = gcm.params(r["url"]).get("gcs")
                    if got != exp:
                        wrong.append(f"{r['phase']}: gcs={got or 'MISSING'} expected {exp} · {_short(r['url'], 70)}")
                if hits:
                    if not gpc_ok:
                        add("GCM-02", "error", page_id, sid, "Not judged: the GPC signal did not reach the page")
                    elif not action_ok and scen.action != "none":
                        add("GCM-02", "error", page_id, sid, "Not judged: consent choice not confirmed")
                    else:
                        add("GCM-02", "fail" if wrong else "pass", page_id, sid,
                            f"{len(wrong)} of {len(hits)} Google hits had the wrong consent state"
                            if wrong else f"{len(hits)} Google hits, all correct", wrong)
                m["google_hits"] = len(hits)

            # ---- journeys & JS errors ----
            journey = rel.get("journey", [])
            if journey:
                broken = [f"{j['description'] or j['id']}: {j['detail']}" for j in journey if not j["ok"]]
                broken_functions.update((page_id, j["id"]) for j in journey if not j["ok"])
                add("FUN-02", "fail" if broken else "pass", page_id, sid,
                    f"{len(broken)} of {len(journey)} journey checks failed" if broken
                    else f"{len(journey)} journey checks passed", broken)
            if obs.get("page_errors"):
                add("FUN-03", "warn", page_id, sid, f"{len(obs['page_errors'])} uncaught JS errors",
                    obs["page_errors"])
            m["js_errors"] = len(obs.get("page_errors", []))

            for e in rel.get("events", []) + pre.get("events", []):
                if e["name"].endswith("Blocked") and sid == "no_choice":
                    blocked_events[e["name"]] += 1

            scen_metrics[sid].update(m)
            page_scen[f"{page_id}|{sid}"] = dict(m)

        # ---- page-level checks from the no_choice run ----
        # A whole-page check over a partly probed page can find problems, but cannot declare the page clean.
        page_partial = any(not usable(o) for o in obs_list)
        base = next((o for o in obs_list if o["scenario"] == "no_choice" and usable(o)), None)
        if base is None:
            base = next((o for o in obs_list if usable(o)), None)
        if base is None:
            # Every page-level check that would have run is ERROR — a missing row reads as "OK" in a comparison.
            page_checks = ["OSN-01", "OSN-02", "OSN-03", "OSN-04", "OSN-05", "OSN-06", "BNR-01"]
            page_checks += ["GCM-01", "GCM-03"] if cx.gcm_mode != "none" else []
            for cid in page_checks:
                add(cid, "error", page_id, "no_choice", "Not judged: no scenario of this page could be probed")
            add("CNS-07", "error", page_id, "all", "Not judged: no scenario of this page could be probed")
            continue
        pre = base["phases"]["pre_consent"]
        osano_reqs = [r for r in base["requests"] if r["phase"] == "pre_consent"
                      and re.search(cx.osano_re, r["url"])]
        add("OSN-01", "pass" if osano_reqs else "fail", page_id, base["scenario"],
            _short(osano_reqs[0]["url"]) if osano_reqs else "osano.js was not requested")
        if osano_reqs:
            ids = osano_script_ids(osano_reqs[0]["url"], cx.osano_re) or {}
            exp_c, exp_k = profile["osano"]["expected_customer_id"], profile["osano"]["expected_config_id"]
            ok = ids.get("customer") == exp_c and ids.get("config") == exp_k
            add("OSN-03", "pass" if ok else "fail", page_id, base["scenario"],
                f"loaded {ids.get('customer')}/{ids.get('config')}, expected {exp_c}/{exp_k}")
            distinct = sorted({r["url"].split("?")[0] for r in osano_reqs})
            add("OSN-04", "fail" if len(distinct) > 1 else "pass", page_id, base["scenario"],
                f"{len(distinct)} distinct osano.js loads", distinct if len(distinct) > 1 else [])
        # OSN-02: document order of third-party scripts.
        srcs = [s for s in pre.get("scripts", []) if s["src"] and host_of(s["src"])
                and not is_first_party(host_of(s["src"]), profile["first_party_domains"])]
        first_osano = next((i for i, s in enumerate(srcs) if re.search(cx.osano_re, s["src"])), None)
        if first_osano is None:
            add("OSN-02", "fail" if not osano_reqs else "warn", page_id, base["scenario"],
                "osano.js not found as a <script src> element")
        else:
            before = [_short(s["src"]) for s in srcs[:first_osano]]
            add("OSN-02", "fail" if before else "pass", page_id, base["scenario"],
                f"{len(before)} third-party scripts load before Osano" if before else "Osano is first", before)
        osn = pre.get("osano") or {}
        if not osn.get("present"):
            for cid in ("OSN-05", "OSN-06"):
                add(cid, "error", page_id, base["scenario"], "Osano.cm was not available on arrival — cannot read it")
        else:
            mode = _MODE_MAP.get(str(osn.get("mode") or "").lower())
            exp = profile["osano"]["expected_mode"]
            add("OSN-05", "pass" if mode == exp else ("warn" if mode is None else "fail"), page_id,
                base["scenario"], f"Osano.cm.mode={osn.get('mode')!r} (= {mode}), expected {exp}")
            cm = osn.get("consentModel")
            add("OSN-06", "pass" if cm == cx.model else ("warn" if not cm else "fail"), page_id,
                base["scenario"], f"Osano.cm.consentModel={cm!r}, expected {cx.model}")
        # GCM-01 / GCM-03
        if cx.gcm_mode != "none":
            order = gcm.datalayer_order(pre.get("datalayer", []))
            if order["first_tag_entry"] is None:
                add("GCM-01", "na", page_id, base["scenario"], "No Google tag entries in dataLayer")
            elif order["first_consent_default"] is None:
                add("GCM-01", "fail", page_id, base["scenario"], "No gtag('consent','default') in dataLayer")
            else:
                ok = order["first_consent_default"] < order["first_tag_entry"]
                add("GCM-01", "pass" if ok else "fail", page_id, base["scenario"],
                    f"consent default at #{order['first_consent_default']}, first tag at #{order['first_tag_entry']}")
            all_hits = [r for o in obs_list for r in o["requests"] if gcm.is_google_hit(r["url"])]
            if all_hits or page_partial:
                missing = sorted({_short(r["url"], 70) for r in all_hits
                                  if not (gcm.parse_gcd(gcm.params(r["url"]).get("gcd")) or {}).get("v2_signals_set")})
                st = _whole_view(bool(missing), page_partial)
                add("GCM-03", st, page_id, "all",
                    f"{len(missing)} Google hits without v2 signals" if missing else
                    (PARTIAL_PAGE if st == "error" else "all hits carry v2 signals"), missing)
        # CNS-07 / CNS-08
        unk = sorted(unclassified_by_page.get(page_id, set()))
        st = _whole_view(bool(unk), page_partial)
        add("CNS-07", st, page_id, "all",
            f"{len(unk)} unclassified items" if unk else (PARTIAL_PAGE if st == "error" else "all items classified"),
            unk)
        acc = next((o for o in obs_list if o["scenario"] == "accept_all" and usable(o)), None)
        if acc and page_scen.get(f"{page_id}|accept_all", {}).get("unjudged"):
            add("CNS-08", "error", page_id, "accept_all", "Not judged: Accept all was not confirmed (BNR-02)")
        elif acc:
            m_acc = page_scen.get(f"{page_id}|accept_all", {})
            missing_cats = [c for c in profile["expected_categories_when_accepted"]
                            if not m_acc.get(f"req_{c}") and not m_acc.get(f"cookie_{c}")]
            add("CNS-08", "warn" if missing_cats else "pass", page_id, "accept_all",
                f"nothing seen for {', '.join(missing_cats)} after Accept all" if missing_cats
                else "every expected category ran", missing_cats)
        perf[page_id] = dict(pre.get("perf") or {})

    # ---- configuration checks ----
    if config is not None:
        run_partial = any(not usable(o) for o in observations)
        mism, not_in, ignored_bad, ignored_ess = [], [], [], []
        for item in inventory.values():
            if item["kind"] == "storage" or item["category"] == FIRST_PARTY:
                continue
            label = f"{item['kind']} · {item['key']}"
            cat_cat, cfg_cat, sect = item["catalog_category"], item["config_category"], item["config_section"]
            if sect == "rules" and cfg_cat and cat_cat not in (UNCLASSIFIED, FIRST_PARTY) and cfg_cat != cat_cat:
                mism.append(f"{label}: Osano says {cfg_cat}, catalog says {cat_cat}")
            if sect in ("missing", "discovered"):
                not_in.append(f"{label} ({sect})")
            if sect == "ignored" and (cat_cat in NON_ESSENTIAL or cat_cat == UNCLASSIFIED):
                # Unknown counts as non-essential here too: in Permissive mode Ignored runs as Essential.
                ignored_bad.append(f"{label} is {cat_cat} but Ignored")
            if sect == "ignored" and cat_cat == "ESSENTIAL" and profile["osano"]["expected_mode"] == "strict":
                ignored_ess.append(f"{label} is ESSENTIAL but Ignored (blocked in Strict)")
        for cid, items, bad_text, ok_text in (
                ("CFG-01", mism, "classification disagreements", "Osano rules agree with the catalog"),
                ("CFG-02", sorted(not_in), "seen items not classified in Osano", "everything seen is in Rules/Ignored"),
                ("CFG-03", ignored_bad, "trackers sit in Ignored", "none")):
            st = _whole_view(bool(items), run_partial)
            add(cid, st, "(all pages)", "-",
                f"{len(items)} {bad_text}" if items else (PARTIAL_RUN if st == "error" else ok_text), items)
        dups = osano_config.duplicates_across_sections(config)
        add("CFG-04", "fail" if dups else "pass", "(config)", "-",
            f"{len(dups)} items in both Rules and Ignored" if dups else "none",
            [f"{d['type']} · {d['match']}" for d in dups])
        st = "warn" if ignored_ess else ("error" if run_partial else "pass")
        add("CFG-05", st, "(all pages)", "-",
            f"{len(ignored_ess)} essential items in Ignored" if ignored_ess else
            (PARTIAL_RUN if st == "error" else "none"), ignored_ess)

    metrics = _metrics(findings, scen_metrics, page_scen, perf, inventory, blocked_events, config, profile)
    # Distinct (page, function) pairs — one broken autocomplete is one, however many choices break it.
    metrics["kpis"]["broken_journeys"] = len(broken_functions)
    if metrics["kpis"]["checks_error"]:
        # Counts over a partial view are not totals: "0 problems" after nothing could be checked would read
        # as "better". Unknown, not zero.
        for key in ("issues_total", "issues_high", "issues_medium", "broken_journeys",
                    "unclassified_items", "osano_unclassified"):
            metrics["kpis"][key] = None
    return {"findings": findings, "metrics": metrics}


_WORST = {"fail": 0, "error": 1, "warn": 2, "pass": 3, "na": 4}


def group_findings(findings: list[dict]) -> list[dict]:
    """One row per check and page: the same problem across 7 consent choices is ONE issue.
    status = the worst seen; scenarios_bad lists the choices where it failed/warned/errored."""
    groups: dict[tuple[str, str], dict] = {}
    for f in findings:
        g = groups.setdefault((f["id"], f["page"]), {
            "id": f["id"], "page": f["page"], "title": f["title"], "severity": f["severity"],
            "status": "na", "scenarios_bad": [], "scenarios_all": [], "detail": "", "evidence": []})
        g["scenarios_all"].append(f["scenario"])
        if _WORST[f["status"]] < _WORST[g["status"]]:
            g["status"], g["detail"] = f["status"], f["detail"]
        elif not g["detail"]:
            g["detail"] = f["detail"]
        if f["status"] in ("fail", "warn", "error"):
            g["scenarios_bad"].append(f["scenario"])
            for e in f["evidence"]:
                if e not in g["evidence"]:
                    g["evidence"].append(e)
    return sorted(groups.values(), key=lambda g: (_WORST[g["status"]], SEVERITY_WEIGHT[g["severity"]] * -1,
                                                  g["id"], g["page"]))


def _metrics(findings, scen_metrics, page_scen, perf, inventory, blocked_events, config, profile) -> dict:
    status = Counter(f["status"] for f in findings)
    applicable = [f for f in findings if f["status"] in ("pass", "fail", "warn")]
    weight = sum(SEVERITY_WEIGHT[f["severity"]] for f in applicable) or 1
    lost = sum(SEVERITY_WEIGHT[f["severity"]] * (1 if f["status"] == "fail" else 0.5)
               for f in applicable if f["status"] in ("fail", "warn"))
    inv_rows = []
    for it in inventory.values():
        inv_rows.append({**it, "scenarios": sorted(it["scenarios"]), "disallowed_in": sorted(it["disallowed_in"]),
                         "pages": sorted(it["pages"]), "set_in": sorted(it.get("set_in", ()))})
    inv_rows.sort(key=lambda r: (r["kind"], r["category"], r["key"]))
    perf_vals = [p for p in perf.values() if p]

    def avg(key):
        vals = [p[key] for p in perf_vals if p.get(key) is not None]
        return round(sum(vals) / len(vals)) if vals else None

    sm = {k: dict(v) for k, v in scen_metrics.items()}
    observed_grid = {t: Counter() for t in osano_config.TYPES}
    for it in inv_rows:
        t = {"host": "script", "iframe": "iframe", "cookie": "cookie"}.get(it["kind"])
        if t and it["category"] != FIRST_PARTY:
            observed_grid[t][it["config_section"]] += 1
    def judged(scenario: str, key: str):
        """A count over a scenario that had an un-judged page is unknown, not a smaller number."""
        s = sm.get(scenario, {})
        return None if s.get("unjudged") else s.get(key, 0)

    kpis = {
        # No score when anything could not be judged: 100 over an empty or partial set reads as "safe".
        "compliance_score": round(100 * (1 - lost / weight), 1) if applicable and not status["error"] else None,
        "checks_total": len(findings),
        "checks_pass": status["pass"], "checks_fail": status["fail"], "checks_warn": status["warn"],
        "checks_error": status["error"],
        "high_severity_fails": sum(1 for f in findings if f["status"] == "fail" and f["severity"] == "high"),
        "pre_consent_violations": judged("no_choice", "pre_consent_violations"),
        "reject_all_violations": judged("reject_all", "post_choice_violations"),
        "gpc_violations": judged("gpc_signal", "violations"),
        "unclassified_items": len({(r["kind"], r["key"]) for r in inv_rows
                                   if r["category"] == UNCLASSIFIED and r["kind"] != "storage"}),
        "third_party_hosts_accept_all": len({r["key"] for r in inv_rows if r["kind"] == "host"
                                             and "accept_all" in r["scenarios"]}),
        "cookies_accept_all": len({r["key"] for r in inv_rows if r["kind"] == "cookie"
                                   and "accept_all" in r["scenarios"]}),
        "iframes_seen": len({r["key"] for r in inv_rows if r["kind"] == "iframe"}),
        "osano_blocked_events": sum(blocked_events.values()),
        "avg_lcp_ms": avg("lcp_ms"), "avg_load_ms": avg("load_ms"), "avg_transfer_kb": avg("transfer_kb"),
        "avg_osano_script_ms": avg("osano_script_ms"), "avg_cls": None,
    }
    cls_vals = [p["cls"] for p in perf_vals if p.get("cls") is not None]
    kpis["avg_cls"] = round(sum(cls_vals) / len(cls_vals), 3) if cls_vals else None
    issues = [g for g in group_findings(findings) if g["status"] in ("fail", "warn")]
    kpis["issues_total"] = len(issues)
    kpis["issues_high"] = sum(1 for g in issues if g["severity"] == "high" and g["status"] == "fail")
    kpis["issues_medium"] = sum(1 for g in issues if g["severity"] == "medium")
    kpis["broken_journeys"] = sum(1 for f in findings if f["id"] == "FUN-02" and f["status"] == "fail")
    grid = osano_config.matrix(config) if config else None
    kpis["osano_unclassified"] = (sum(grid[t]["discovered"] for t in grid)
                                  + sum(observed_grid[t].get("missing", 0) for t in observed_grid)) if grid else None
    return {"kpis": kpis, "by_scenario": sm, "by_page_scenario": page_scen, "perf": perf,
            "inventory": inv_rows, "blocked_events": dict(blocked_events),
            "config_matrix": osano_config.matrix(config) if config else None,
            "observed_matrix": {t: dict(c) for t, c in observed_grid.items()}}
