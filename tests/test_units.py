# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""Unit tests: no browser, no network."""
from __future__ import annotations

import copy

import pytest
import yaml

from osano_harness import google_consent as gcm
from osano_harness import osano_config
from osano_harness.analysis import analyse
from osano_harness.catalog import FIRST_PARTY, Catalog
from osano_harness.compare import compare
from osano_harness.html_shell import esc, table
from osano_harness.profile import DEFAULTS, ProfileError, _merge, load_profile, validate
from osano_harness.report import render_run
from osano_harness.scenarios import SCENARIOS, allowed_categories, expected_gcs, intended_consent


# ---------------- Google Consent Mode ----------------
def test_parse_gcs():
    assert gcm.parse_gcs("G100") == {"raw": "G100", "ad_storage": "denied", "analytics_storage": "denied"}
    assert gcm.parse_gcs("G101")["analytics_storage"] == "granted"
    assert gcm.parse_gcs("G1x1") is None
    assert gcm.parse_gcs(None) is None


def test_parse_gcd_v2_and_v1():
    v2 = gcm.parse_gcd("11r1r1r1r5")
    assert v2["ad_storage"]["state"] == "granted" and v2["v2_signals_set"]
    v1 = gcm.parse_gcd("11p1p1l1l5")
    assert v1["analytics_storage"]["state"] == "denied" and not v1["v2_signals_set"]
    assert gcm.parse_gcd("garbage") is None


def test_datalayer_order_detects_late_default():
    good = [{"__args": ["consent", "default", {}]}, {"__args": ["js", "x"]}, {"__args": ["config", "G-1"]}]
    bad = [{"__args": ["js", "x"]}, {"__args": ["consent", "default", {}]}]
    assert gcm.datalayer_order(good)["first_consent_default"] < gcm.datalayer_order(good)["first_tag_entry"]
    o = gcm.datalayer_order(bad)
    assert o["first_tag_entry"] < o["first_consent_default"]


def test_google_hit_detection():
    assert gcm.is_google_hit("https://region1.google-analytics.com/g/collect?v=2")
    assert not gcm.is_google_hit("https://www.googletagmanager.com/gtag/js?id=G-1")


# ---------------- scenarios ----------------
def test_allowed_categories():
    assert allowed_categories(SCENARIOS["reject_all"], "opt-in") == {"ESSENTIAL"}
    assert allowed_categories(SCENARIOS["analytics_only"], "opt-in") == {"ESSENTIAL", "ANALYTICS"}
    assert "MARKETING" in allowed_categories(SCENARIOS["no_choice"], "opt-out")
    assert "MARKETING" not in allowed_categories(SCENARIOS["gpc_signal"], "opt-out")
    assert allowed_categories(SCENARIOS["no_choice"], "opt-in") == {"ESSENTIAL"}


def test_expected_gcs():
    assert expected_gcs(SCENARIOS["accept_all"], "opt-in") == "G111"
    assert expected_gcs(SCENARIOS["analytics_only"], "opt-in") == "G101"
    assert expected_gcs(SCENARIOS["marketing_only"], "opt-in") == "G110"
    assert expected_gcs(SCENARIOS["gpc_signal"], "opt-out") == "G101"
    assert intended_consent(SCENARIOS["no_choice"]) is None


# ---------------- catalog ----------------
def test_catalog_classification():
    cat = Catalog(first_party_domains=["acecashexpress.com"])
    assert cat.classify_url("https://connect.facebook.net/x.js").category == "MARKETING"
    assert cat.classify_url("https://www.google.com/recaptcha/api.js").category == "ESSENTIAL"
    assert cat.classify_url("https://apply.acecashexpress.com/x").category == FIRST_PARTY
    assert cat.classify_url("https://evil-tracker.example/x").category == "UNCLASSIFIED"
    assert cat.classify_cookie("_ga_ABC").category == "ANALYTICS"
    assert cat.classify_cookie("ASP.NET_SessionId").category == "ESSENTIAL"
    assert cat.classify_cookie("mystery").category == "UNCLASSIFIED"
    # host suffix must match on a label boundary
    assert cat.classify_url("https://notfacebook.net/x").category == "UNCLASSIFIED"


# ---------------- Osano config ----------------
def test_normalize_both_shapes_and_matrix():
    flat = osano_config.normalize({"items": [{"type": "scripts", "section": "Classified", "match": "a.com",
                                              "category": "marketing"}]})
    assert flat["items"][0] == {"type": "script", "section": "rules", "match": "a.com", "category": "MARKETING"}
    nested = osano_config.normalize({"cookies": {"ignored": ["_x"], "discovered": [{"name": "_y"}]},
                                     "iframes": {"rules": [{"domain": "yt.com", "classification": "MARKETING"}]}})
    grid = osano_config.matrix(nested)
    assert grid["cookie"] == {"rules": 0, "discovered": 1, "ignored": 1}
    assert grid["iframe"]["rules"] == 1


def test_normalize_rejects_unknown_shapes():
    with pytest.raises(osano_config.ConfigError):
        osano_config.normalize({"whatever": 1})
    with pytest.raises(osano_config.ConfigError):
        osano_config.normalize({"scripts": {"weird": []}})


def test_lookup_prefers_rules_and_finds_duplicates():
    cfg = osano_config.normalize({"items": [
        {"type": "cookie", "section": "ignored", "match": "_ga"},
        {"type": "cookie", "section": "rules", "match": "_ga", "category": "ANALYTICS"}]})
    assert osano_config.lookup(cfg, "cookie", "_ga")["section"] == "rules"
    assert osano_config.duplicates_across_sections(cfg)


def test_config_diff():
    a = osano_config.normalize({"items": [{"type": "script", "section": "discovered", "match": "fb.net"}]})
    b = osano_config.normalize({"items": [{"type": "script", "section": "rules", "match": "fb.net",
                                           "category": "MARKETING"},
                                          {"type": "script", "section": "rules", "match": "new.com",
                                           "category": "ANALYTICS"}]})
    changes = {c["match"]: c["change"] for c in osano_config.diff(a, b)}
    assert changes == {"fb.net": "moved", "new.com": "added"}


# ---------------- profile (fail closed) ----------------
def test_profile_refuses_placeholders():
    with pytest.raises(ProfileError) as e:
        load_profile("ace-prod")
    assert "expected_config_id" in str(e.value)
    assert load_profile("ace-prod", allow_placeholders=True)["name"] == "ace-prod"


def test_profile_rejects_bad_values():
    prof = _merge(DEFAULTS, {"name": "x", "display_name": "x", "environment": "x", "first_party_domains": ["a.com"],
                             "pages": [{"id": "p", "url": "ftp://a.com"}], "consent_model_expected": "maybe",
                             "osano": {"expected_customer_id": "c", "expected_config_id": "k"}})
    with pytest.raises(ProfileError) as e:
        validate(prof)
    assert "consent_model_expected" in str(e.value) and "full http(s) address" in str(e.value)


# ---------------- analysis on synthetic observations ----------------
def _profile():
    return _merge(DEFAULTS, {"name": "t", "display_name": "T", "environment": "production",
                             "first_party_domains": ["site.test"],
                             "pages": [{"id": "home", "url": "https://site.test/"}],
                             "scenarios": ["no_choice", "reject_all"],
                             "osano": {"expected_customer_id": "C", "expected_config_id": "K"}})


def _snap(cookies=(), consent=None, banner=True):
    return {"osano": {"present": True, "mode": "strict", "consentModel": "opt-in", "consent": consent or {}},
            "banner_visible": banner, "scripts": [{"src": "https://cmp.osano.com/C/K/osano.js", "type": "",
                                                    "inline": False, "in_head": True, "index": 0}],
            "iframes": [], "local_storage": [], "session_storage": [], "datalayer": [], "events": [],
            "gpc": False, "perf": {}, "status": 200, "journey": [],
            "cookies": [{"name": n, "domain": "site.test"} for n in cookies]}


def _req(url, phase, rtype="script"):
    host = url.split("/")[2]
    return {"url": url, "host": host, "type": rtype, "method": "GET", "phase": phase, "t_ms": 1,
            "third_party": host != "site.test", "main_frame": True}


def _obs(scenario, requests, phases, action=None):
    return {"page_id": "home", "url": "https://site.test/", "scenario": scenario, "phases": phases,
            "requests": requests, "consent_action": action, "error": None, "console_errors": [], "page_errors": []}


def _find(result, cid, scenario):
    return [f for f in result["findings"] if f["id"] == cid and f["scenario"] == scenario]


def test_leak_before_consent_and_cookieless_ping_allowed():
    prof = _profile()
    reqs = [_req("https://cmp.osano.com/C/K/osano.js", "pre_consent"),
            _req("https://connect.facebook.net/fbevents.js", "pre_consent"),
            _req("https://region1.google-analytics.com/g/collect?gcs=G100&gcd=11p1p1p1p5", "pre_consent", "image")]
    obs = [_obs("no_choice", reqs, {"pre_consent": _snap(["_fbp"]), "after_reload": _snap(["_fbp"])})]
    res = analyse(prof, obs, None, Catalog(first_party_domains=["site.test"]))
    cns1 = _find(res, "CNS-01", "no_choice")[0]
    assert cns1["status"] == "fail"
    assert any("facebook" in e for e in cns1["evidence"])
    assert not any("google-analytics" in e for e in cns1["evidence"])   # cookieless G100 ping is fine
    assert _find(res, "CNS-02", "no_choice")[0]["status"] == "fail"
    assert _find(res, "OSN-03", "no_choice")[0]["status"] == "pass"


def test_unconfirmed_click_is_error_not_pass():
    prof = _profile()
    act = {"applied": False, "steps": [], "error": "no visible deny_all button", "intended": {}}
    obs = [_obs("reject_all", [], {"pre_consent": _snap(), "post_consent": _snap(), "after_reload": _snap()}, act)]
    res = analyse(prof, obs, None, Catalog(first_party_domains=["site.test"]))
    assert _find(res, "BNR-02", "reject_all")[0]["status"] == "error"
    assert all(f["status"] == "error" for f in res["findings"] if f["id"] in ("CNS-04", "CNS-05", "CNS-06"))


def test_unclassified_counts_as_non_essential_after_reject():
    prof = _profile()
    act = {"applied": True, "steps": ["clicked"], "intended": {"ANALYTICS": "DENY", "MARKETING": "DENY",
                                                                 "PERSONALIZATION": "DENY"}}
    denied = {"ANALYTICS": "DENY", "MARKETING": "DENY", "PERSONALIZATION": "DENY"}
    reqs = [_req("https://cdn.unknown-vendor.io/x.js", "after_reload")]
    obs = [_obs("reject_all", reqs, {"pre_consent": _snap(), "post_consent": _snap(consent=denied, banner=False),
                                     "after_reload": _snap(["osano_consentmanager"], denied, banner=False)}, act)]
    res = analyse(prof, obs, None, Catalog(first_party_domains=["site.test"]))
    assert _find(res, "BNR-02", "reject_all")[0]["status"] == "pass"
    assert _find(res, "CNS-04", "reject_all")[0]["status"] == "fail"
    assert _find(res, "BNR-04", "reject_all")[0]["status"] == "pass"


def test_wrong_osano_config_id_fails():
    prof = _profile()
    snap = _snap()
    obs = [_obs("no_choice", [_req("https://cmp.osano.com/C/OTHER/osano.js", "pre_consent")],
                {"pre_consent": snap, "after_reload": snap})]
    res = analyse(prof, obs, None, Catalog(first_party_domains=["site.test"]))
    assert _find(res, "OSN-03", "no_choice")[0]["status"] == "fail"


# ---------------- compare ----------------
def _run(findings, kpis=None):
    base = {"compliance_score": 50, "checks_fail": 1, "high_severity_fails": 1}
    return {"meta": {"profile": "p", "run_id": "r"}, "profile": {"pages": [{"id": "home"}]}, "osano_config": None,
            "analysis": {"findings": findings, "metrics": {"kpis": {**base, **(kpis or {})}, "by_scenario": {},
                                                           "inventory": [], "perf": {}}}}


def _f(cid, status, sev="high"):
    return {"id": cid, "page": "home", "scenario": "no_choice", "status": status, "severity": sev,
            "title": cid, "detail": "", "evidence": []}


def test_compare_verdicts():
    assert compare(_run([_f("A", "fail")]), _run([_f("A", "pass")]))["verdict"] == "IMPROVED"
    assert compare(_run([_f("A", "pass")]), _run([_f("A", "fail")]))["verdict"] == "REGRESSED"
    assert compare(_run([_f("A", "fail"), _f("B", "pass")]),
                   _run([_f("A", "pass"), _f("B", "fail")]))["verdict"] == "MIXED"
    assert compare(_run([_f("A", "pass")]), _run([_f("A", "pass")]))["verdict"] == "UNCHANGED"
    # a new LOW-severity failure alone is not a regression verdict
    assert compare(_run([_f("A", "pass", "low")]), _run([_f("A", "fail", "low")]))["verdict"] == "UNCHANGED"


def test_compare_perf_noise_is_same():
    cmp = compare(_run([], {"avg_load_ms": 1000}), _run([], {"avg_load_ms": 1050}))
    assert next(k for k in cmp["kpis"] if k["key"] == "avg_load_ms")["direction"] == "same"


# ---------------- HTML ----------------
def test_html_escapes_site_data():
    assert "<script>" not in esc("<script>alert(1)</script>")
    assert "&lt;img" in table(["a"], [[esc("<img src=x onerror=alert(1)>")]])


def test_run_report_has_house_features_and_escapes():
    prof = _profile()
    evil = '<img src=x onerror=alert(1)>'
    obs = [_obs("no_choice", [_req("https://cmp.osano.com/C/K/osano.js", "pre_consent")],
                {"pre_consent": _snap([evil]), "after_reload": _snap([evil])})]
    run = {"meta": {"run_id": "r1", "label": "before", "profile": "t", "display_name": "T", "environment": "prod",
                    "started_utc": "s", "finished_utc": "f", "harness_version": "1", "analysed_with_catalog": "c"},
           "profile": prof, "osano_config": None, "observations": obs}
    run["analysis"] = analyse(prof, obs, None, Catalog(first_party_domains=["site.test"]))
    html_text = render_run(run)
    assert evil not in html_text
    for marker in ("html-artifact-theme", "speechSynthesis", "tab-btn", 'data-theme="dark"', "voiceSel", "rateSel"):
        assert marker in html_text
    assert "http://" not in html_text.split("<body>")[0].replace('http://www.w3.org', '')   # no external assets


def test_reports_never_truncate_or_hide_content():
    prof = _profile()
    long_url = "https://connect.facebook.net/" + "x" * 300 + ".js"
    cookies = [f"c{i}" for i in range(60)]           # more than any old limit (40 / 15 / 10)
    obs = [_obs("no_choice", [_req("https://cmp.osano.com/C/K/osano.js", "pre_consent"), _req(long_url, "pre_consent")],
                {"pre_consent": _snap(cookies), "after_reload": _snap(cookies)})]
    run = {"meta": {"run_id": "r1", "label": "before", "profile": "t", "display_name": "T", "environment": "prod",
                    "started_utc": "s", "finished_utc": "2026-10-07T00:00:00Z", "harness_version": "1",
                    "analysed_with_catalog": "c"},
           "profile": prof, "osano_config": None, "observations": obs}
    run["analysis"] = analyse(prof, obs, None, Catalog(first_party_domains=["site.test"]))
    html_text = render_run(run)
    assert "x" * 300 in html_text                       # full URL, no ellipsis
    assert all(f"<code>c{i}</code>" in html_text for i in range(60))   # every cookie listed
    assert "<details>" not in html_text                 # every collapsible starts open
    assert "more</li>" not in html_text


def test_vendor_catalog_is_valid_yaml_with_known_categories():
    from osano_harness.catalog import DEFAULT_CATALOG
    data = yaml.safe_load(DEFAULT_CATALOG.read_text(encoding="utf-8"))
    ids = [v["id"] for v in data["vendors"]]
    assert len(ids) == len(set(ids))
    copy.deepcopy(Catalog())  # loads and validates categories
