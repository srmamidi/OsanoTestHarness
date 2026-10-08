# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""Regression tests for the defects found in the code review (2026-10-07). Each test executes the
behaviour and fails on the original code. Grouped by the review finding it guards."""
from __future__ import annotations

import json

import pytest

from osano_harness import cli, osano_config, runs
from osano_harness import google_consent as gcm
from osano_harness.analysis import analyse, group_findings
from osano_harness.catalog import Catalog
from osano_harness.compare import compare, risk
from osano_harness.profile import DEFAULTS, ProfileError, _merge, load_profile, validate
from osano_harness.report import render_run

from test_units import _find, _obs, _profile, _req, _snap

CAT = Catalog(first_party_domains=["site.test"])


def _run_of(obs, prof=None, cfg=None):
    prof = prof or _profile()
    run = {"meta": {"run_id": "20261007-000000_x", "label": "x", "profile": "t", "display_name": "T",
                    "environment": "prod", "started_utc": "s", "finished_utc": "2026-10-07T00:00:00Z",
                    "harness_version": "1", "analysed_with_catalog": "c"},
           "profile": prof, "osano_config": cfg, "observations": obs}
    run["analysis"] = analyse(prof, obs, cfg, CAT)
    return run


def _clean_obs(scenario="no_choice"):
    snap = _snap()
    return _obs(scenario, [_req("https://cmp.osano.com/C/K/osano.js", "pre_consent")],
                {"pre_consent": snap, "after_reload": snap})


# ---- fail-open: nothing judged must never read as safe ----------------------------------------
def test_all_probes_errored_is_high_risk_no_score_incomplete():
    before = _run_of([_obs("no_choice", [_req("https://connect.facebook.net/x.js", "pre_consent")],
                           {"pre_consent": _snap(), "after_reload": _snap()})])
    dead = {"page_id": "home", "url": "u", "scenario": "no_choice", "phases": {}, "requests": [],
            "consent_action": None, "error": "TimeoutError", "console_errors": [], "page_errors": []}
    after = _run_of([dead])
    k = after["analysis"]["metrics"]["kpis"]
    assert k["compliance_score"] is None
    assert k["pre_consent_violations"] is None
    assert risk(group_findings(after["analysis"]["findings"]), [])["level"] == "HIGH"
    cmp = compare(before, after)
    assert cmp["verdict"] == "INCOMPLETE" and cmp["risk"]["level"] == "HIGH"
    assert cli._gate_compare(cmp, "high-risk") == cli.GATE_EXIT
    assert cli._gate_run(after, "high") == cli.GATE_EXIT
    assert not any(r["change"] == "gone" and r["id"] == "CNS-01" for r in cmp["findings"])


def test_unconfirmed_click_counts_are_not_judged_not_zero():
    act = {"applied": False, "steps": [], "error": "no visible deny_all button", "intended": {}}
    obs = [_obs("reject_all", [], {"pre_consent": _snap(), "post_consent": _snap(), "after_reload": _snap()}, act)]
    run = _run_of(obs, _merge(_profile(), {"scenarios": ["reject_all"]}))
    assert run["analysis"]["metrics"]["kpis"]["reject_all_violations"] is None
    html_text = render_run(run)
    assert "not judged" in html_text


def test_high_severity_warning_is_not_low_risk():
    assert risk([{"status": "warn", "severity": "high"}], [])["level"] == "MEDIUM"


def test_error_before_pass_after_is_not_a_fix():
    def f(status):
        return {"id": "CNS-01", "page": "home", "scenario": "no_choice", "status": status, "severity": "high",
                "title": "t", "detail": "", "evidence": []}

    def run(fs):
        return {"meta": {"profile": "p", "run_id": "r"}, "profile": {"pages": [{"id": "home"}]},
                "osano_config": None, "analysis": {"findings": fs, "metrics": {
                    "kpis": {}, "by_scenario": {}, "inventory": [], "perf": {}}}}
    cmp = compare(run([f("error")]), run([f("pass")]))
    assert cmp["counts"]["fixed"] == 0 and cmp["counts"]["judged"] == 1 and cmp["verdict"] != "IMPROVED"


# ---- consent reads ------------------------------------------------------------------------------
def test_gpc_with_unreadable_consent_is_error_not_pass():
    prof = _merge(_profile(), {"scenarios": ["gpc_signal"]})
    snap = _snap()
    snap["gpc"] = True
    snap["osano"] = {"present": True, "consent": None}
    res = analyse(prof, [_obs("gpc_signal", [], {"pre_consent": snap, "after_reload": snap})], None, CAT)
    assert _find(res, "GPC-01", "gpc_signal")[0]["status"] == "error"


def test_missing_http_status_is_error_and_absent_osano_reports_mode_checks():
    snap = _snap()
    snap["status"] = None
    snap["osano"] = {"present": False}
    res = analyse(_profile(), [_obs("no_choice", [], {"pre_consent": snap, "after_reload": snap})], None, CAT)
    assert _find(res, "FUN-01", "no_choice")[0]["status"] == "error"
    assert {f["status"] for f in res["findings"] if f["id"] in ("OSN-05", "OSN-06")} == {"error"}


# ---- Osano export parsing (fail closed) -----------------------------------------------------------
@pytest.mark.parametrize("raw", [
    {"scripts": {"rules": "facebook.net"}},                       # string walked char by char
    {"scripts": {"discovered": "abc"}},                           # same, where no category check would catch it
    {"items": ["abc"]},                                           # non-object item
    {"scripts": {"rules": [42]}},
    {"scripts": {"rules": [{"match": "x.io"}]}},                  # rule without category
    {"scripts": {"rules": [{"match": "x.io", "category": "STRICTLY_NECESSARY"}]}},
])
def test_bad_osano_exports_raise(raw):
    with pytest.raises(osano_config.ConfigError):
        osano_config.normalize(raw)


def test_query_string_cannot_reclassify():
    assert CAT.classify_url("https://tracker.evil.io/px?ref=https://www.google.com/recaptcha/api.js").category \
        == "UNCLASSIFIED"
    cfg = osano_config.normalize({"items": [{"type": "script", "section": "rules", "match": "connect.facebook.net",
                                             "category": "MARKETING"},
                                            {"type": "script", "section": "ignored", "match": "cdn.io"}]})
    assert osano_config.lookup(cfg, "script", "https://pixel.adnet.com/t?u=connect.facebook.net") is None
    assert osano_config.lookup(cfg, "script", "https://notcdn.io.tracker.com/a.js") is None
    assert osano_config.lookup(cfg, "script", "https://connect.facebook.net/en_US/fbevents.js")["section"] == "rules"
    # A pattern with a path segment is matched on host + path, never the query string either.
    cfg2 = osano_config.normalize({"items": [{"type": "script", "section": "rules", "match": "facebook.net/en_US",
                                              "category": "MARKETING"}]})
    assert osano_config.lookup(cfg2, "script", "https://pixel.adnet.com/t?u=connect.facebook.net/en_US") is None
    assert osano_config.lookup(cfg2, "script", "https://connect.facebook.net/en_US/fbevents.js") is not None


def test_unknown_vendor_osano_calls_essential_is_still_judged_and_unknown_in_ignored_flagged():
    cfg = osano_config.normalize({"items": [
        {"type": "script", "section": "rules", "match": "newtracker.io", "category": "ESSENTIAL"},
        {"type": "script", "section": "ignored", "match": "othertracker.io"}]})
    reqs = [_req("https://px.newtracker.io/hit", "pre_consent"), _req("https://a.othertracker.io/x.js", "pre_consent")]
    res = analyse(_profile(), [_obs("no_choice", reqs, {"pre_consent": _snap(), "after_reload": _snap()})], cfg, CAT)
    assert _find(res, "CNS-01", "no_choice")[0]["status"] == "fail"
    assert any("Osano calls it ESSENTIAL" in e for e in _find(res, "CNS-07", "all")[0]["evidence"])
    assert next(f for f in res["findings"] if f["id"] == "CFG-03")["status"] == "fail"


def test_google_library_downloads_are_not_hits_but_google_com_hits_are():
    assert not gcm.is_google_hit("https://www.googleadservices.com/pagead/conversion.js")
    assert not gcm.is_google_hit("https://www.googleadservices.com/pagead/conversion/123/conversion_async.js")
    assert gcm.is_google_hit("https://www.google.com/pagead/1p-conversion/123/?gcs=G100")
    assert not gcm.is_google_hit("https://www.google.com/recaptcha/api.js")


# ---- counts mean what the label says -----------------------------------------------------------------
def test_counts_are_distinct_trackers_and_distinct_broken_functions():
    hits = [_req(f"https://region1.google-analytics.com/g/collect?v=2&n={i}", "pre_consent") for i in range(5)]
    snap = _snap()
    snap["journey"] = [{"id": "autocomplete", "description": "", "ok": False, "detail": "false"}]
    res = analyse(_profile(), [_obs("no_choice", hits, {"pre_consent": snap, "after_reload": snap})], None, CAT)
    assert res["metrics"]["kpis"]["pre_consent_violations"] == 1
    assert len(_find(res, "CNS-01", "no_choice")[0]["evidence"]) == 5      # every URL still shown as evidence
    assert res["metrics"]["kpis"]["broken_journeys"] == 1


# ---- profile validation (fail closed) -------------------------------------------------------------
def _valid():
    return _merge(DEFAULTS, {"name": "x", "display_name": "x", "environment": "e", "first_party_domains": ["a.com"],
                             "pages": [{"id": "p", "url": "https://a.com/"}],
                             "osano": {"expected_customer_id": "c", "expected_config_id": "k"}})


@pytest.mark.parametrize("patch,needle", [
    ({"scenarios": []}, "scenarios"),
    ({"scenarios": ["no_choice", "no_choice"]}, "twice"),
    ({"first_party_domains": "a.com"}, "first_party_domains"),
    ({"name": "../../evil"}, "folder name"),
    ({"pages": [{"id": "p", "url": "https://"}]}, "with a host"),
    ({"pages": ["https://a.com"]}, "'pages'"),
    ({"osano": {"expected_config_id": "REPLACE-ME-prod"}}, "REPLACE-ME"),
    ({"osano": {"selectors": {"accept_all": ".btn"}}}, "selectors.accept_all"),
    ({"osano": {"script_url_regex": "(("}}, "regular expression"),
    ({"osano": {"consent_cookie_patterns": []}}, "consent_cookie_patterns"),
    ({"expected_categories_when_accepted": ["ANALYTICZ"]}, "expected_categories"),
])
def test_profile_validation_refuses(patch, needle):
    validate(_valid())                          # control: the base profile is fine
    with pytest.raises(ProfileError) as e:
        validate(_merge(_valid(), patch))
    assert needle in str(e.value)


def test_non_mapping_profile_file_is_profile_error(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ProfileError):
        load_profile(str(f))


# ---- CLI: errors are messages with exit 2; compare direction --------------------------------------------
def test_missing_input_files_exit_2(tmp_path, capsys):
    assert cli.main(["import-config", "--input", str(tmp_path / "nope.json"), "--output", str(tmp_path / "o.json")]) == 2
    assert cli.main(["compare", "--profile", "x", "--before", str(tmp_path / "a.json"),
                     "--after", str(tmp_path / "b.json")]) == 2
    assert "not found" in capsys.readouterr().err


def test_latest_before_is_older_than_after(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "RUNS", tmp_path)
    folder = tmp_path / "p"
    folder.mkdir()
    for stem in ("20261001-100000_before", "20261001-110000_after", "20261001-120000_before"):
        (folder / f"{stem}.json").write_text("{}", encoding="utf-8")
    after = runs.latest("p", "after")
    assert after.stem == "20261001-110000_after"
    assert runs.latest("p", "before", older_than=after.stem).stem == "20261001-100000_before"


def test_index_skips_bad_run_files(tmp_path, monkeypatch):
    from osano_harness import report
    monkeypatch.setattr(report, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(report, "REPORTS", tmp_path / "reports")
    (tmp_path / "runs" / "p").mkdir(parents=True)
    (tmp_path / "runs" / "p" / "old.json").write_text(json.dumps({"hello": 1}), encoding="utf-8")
    data = report.index_data()
    assert data["runs"] == [] and data["skipped"][0]["file"] == "p/old.json"


# ---- browser behaviour -------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as pw:
        try:
            b = pw.chromium.launch()
        except Exception as exc:  # noqa: BLE001
            if "Executable doesn't exist" in str(exc):
                pytest.skip("browser not installed")
            raise
        yield b
        b.close()


def test_fixed_position_banner_is_visible_without_dialogopen(browser):
    from osano_harness.probe import _CAPTURE_JS
    page = browser.new_page()
    page.set_content("<div class='osano-cm-dialog' style='position:fixed;bottom:0;height:80px'>banner</div>")
    assert page.evaluate(_CAPTURE_JS, DEFAULTS["osano"]["selectors"]["banner"])["banner_visible"] is True
    page.set_content("<div class='osano-cm-dialog' style='position:fixed;display:none'>banner</div>")
    assert page.evaluate(_CAPTURE_JS, DEFAULTS["osano"]["selectors"]["banner"])["banner_visible"] is False
    page.close()


def test_toggle_is_never_force_clicked_onto_other_ui(browser):
    from osano_harness.probe import _set_toggle
    page = browser.new_page()
    page.set_content("<div style='position:relative'><input type=checkbox id=t style='opacity:0'>"
                     "<a href='#clicked-other' style='position:absolute;left:0;top:0;width:40px;height:40px'>x</a></div>")
    with pytest.raises(Exception):
        _set_toggle(page, page.locator("#t"), True)
    assert not page.url.endswith("#clicked-other")
    page.close()


def test_demo_server_refuses_a_port_in_use():
    from osano_harness.demo.site import DemoServer
    with DemoServer(8779):
        with pytest.raises(OSError):
            DemoServer(8779)


# ================================================================================ round 2
def test_full_url_export_entries_still_match_and_ignored_tracker_fires_cfg03():
    cfg = osano_config.normalize({"items": [
        {"type": "script", "section": "rules", "match": "https://connect.facebook.net/en_US/fbevents.js?v=2",
         "category": "MARKETING"},
        {"type": "script", "section": "ignored", "match": "https://www.googletagmanager.com/gtm.js"}]})
    assert osano_config.lookup(cfg, "script", "https://connect.facebook.net/en_US/fbevents.js")["section"] == "rules"
    reqs = [_req("https://www.googletagmanager.com/gtm.js?id=GTM-1", "pre_consent"),
            _req("https://www.unknown-ads.io/gtm.js", "pre_consent")]
    res = analyse(_profile(), [_obs("no_choice", reqs, {"pre_consent": _snap(), "after_reload": _snap()})], cfg, CAT)
    sections = {it["key"]: it["config_section"] for it in res["metrics"]["inventory"] if it["kind"] == "host"}
    assert sections["www.googletagmanager.com"] == "ignored"


def test_not_judged_before_failing_after_is_new_and_gated():
    def f(cid, status):
        return {"id": cid, "page": "home", "scenario": "reject_all", "status": status, "severity": "high",
                "title": "t", "detail": "", "evidence": []}

    def run(fs):
        return {"meta": {"profile": "p", "run_id": "r"}, "profile": {"pages": [{"id": "home"}]},
                "osano_config": None, "analysis": {"findings": fs, "metrics": {
                    "kpis": {}, "by_scenario": {}, "inventory": [], "perf": {}}}}
    cmp = compare(run([f("CNS-04", "error"), f("OSN-02", "fail")]), run([f("CNS-04", "fail"), f("OSN-02", "pass")]))
    assert next(r for r in cmp["findings"] if r["id"] == "CNS-04")["change"] == "new"
    assert cmp["verdict"] != "IMPROVED"
    assert cli._gate_compare(cmp, "new-high") == cli.GATE_EXIT


def test_counts_after_unjudged_run_are_unknown_not_better():
    good = _run_of([_obs("no_choice", [_req("https://connect.facebook.net/x.js", "pre_consent")],
                         {"pre_consent": _snap(), "after_reload": _snap()})])
    dead = _run_of([{"page_id": "home", "url": "u", "scenario": "no_choice", "phases": {}, "requests": [],
                     "consent_action": None, "error": "TimeoutError", "console_errors": [], "page_errors": []}])
    assert dead["analysis"]["metrics"]["kpis"]["issues_high"] is None
    kp = {k["key"]: k for k in compare(good, dead)["kpis"]}
    assert kp["issues_high"]["direction"] == "n/a" and kp["issues_total"]["direction"] == "n/a"


def test_index_skips_malformed_comparison_summaries(tmp_path, monkeypatch):
    from osano_harness import report
    monkeypatch.setattr(report, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(report, "REPORTS", tmp_path / "reports")
    (tmp_path / "reports" / "p").mkdir(parents=True)
    ok_counts = {"fixed": 1, "new": 0, "still": 0}
    (tmp_path / "reports" / "p" / "compare_a.json").write_text(json.dumps({"verdict": "MIXED", "counts": ok_counts}))
    (tmp_path / "reports" / "p" / "compare_b.json").write_text(json.dumps(
        {"display_name": "d", "before": "b", "after": "a", "verdict": "MIXED", "risk": {"x": 1}, "counts": ok_counts}))
    assert len(report.index_data()["skipped"]) == 2
    report.render_index()                      # must not raise


def test_observation_without_phases_and_without_error_does_not_crash():
    odd = {"page_id": "home", "url": "u", "scenario": "no_choice", "phases": {}, "requests": [],
           "consent_action": None, "error": None, "console_errors": [], "page_errors": []}
    run = _run_of([odd])
    render_run(run)
    assert _find(run["analysis"], "FUN-01", "no_choice")[0]["status"] == "error"


def test_risk_reason_names_every_open_item():
    why = risk([{"status": "fail", "severity": "low"}, {"status": "error", "severity": "medium"},
                {"status": "pass", "severity": "high"}], [])["why"]
    assert "low-risk problem" in why and "not judged" in why
    why = risk([{"status": "error", "severity": "high"}, {"status": "fail", "severity": "medium"},
                {"status": "pass", "severity": "low"}], [])["why"]
    assert "medium-risk problem" in why and "could not be judged" in why


def test_demo_port_option_rewrites_page_urls(monkeypatch):
    import argparse
    from osano_harness import probe
    seen = {}

    def fake_probe(prof, router=None, progress=print):
        seen["urls"] = [p["url"] for p in prof["pages"]]
        raise SystemExit(0)
    monkeypatch.setattr(probe, "run_probe", fake_probe)
    with pytest.raises(SystemExit):
        cli.cmd_run(argparse.Namespace(profile="demo-prod", label="x", headed=False, allow_placeholders=False,
                                       demo_port=8790, notes=""), router=lambda r: None, osano_cfg=None)
    assert all(":8790/" in u for u in seen["urls"])


def test_failed_click_and_missing_gpc_are_not_called_leaks():
    prof = _merge(_profile(), {"scenarios": ["reject_all", "gpc_signal"]})
    act = {"applied": False, "steps": [], "error": "no button", "intended": {}}
    leak = [_req("https://connect.facebook.net/x.js", "after_reload")]
    nogpc = _snap()
    nogpc["gpc"] = False
    obs = [_obs("reject_all", leak, {"pre_consent": _snap(), "post_consent": _snap(), "after_reload": _snap()}, act),
           _obs("gpc_signal", [_req("https://connect.facebook.net/x.js", "pre_consent")],
                {"pre_consent": nogpc, "after_reload": nogpc})]
    res = analyse(prof, obs, None, CAT)
    fb = next(it for it in res["metrics"]["inventory"] if it["key"] == "connect.facebook.net")
    assert fb["disallowed_in"] == []
    assert res["metrics"]["kpis"]["gpc_violations"] is None
    assert _find(res, "CNS-01", "gpc_signal")[0]["status"] == "error"


def test_url_contains_respects_host_label_boundary():
    assert CAT.classify_url("https://www.google.com/recaptcha/api.js").category == "ESSENTIAL"
    assert CAT.classify_url("https://fakegoogle.com/recaptcha/api.js").category == "UNCLASSIFIED"


def test_report_command_checks_meta_and_never_copies_outside_files(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runs, "RUNS", tmp_path / "history")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"observations": [], "profile": {}}), encoding="utf-8")
    assert cli.main(["report", "--run", str(bad)]) == 2
    assert not (tmp_path / "history").exists()


# ================================================================================ round 3
def test_osano_path_patterns_respect_host_boundary():
    cfg = osano_config.normalize({"items": [
        {"type": "script", "section": "rules", "match": "cdn.vendor.com/lib", "category": "ANALYTICS"},
        {"type": "script", "section": "rules", "match": "*.facebook.net", "category": "MARKETING"},
        {"type": "script", "section": "rules", "match": "/", "category": "ESSENTIAL"}]})
    assert osano_config.lookup(cfg, "script", "https://evil.example/x/cdn.vendor.com/lib.js") is None
    assert osano_config.lookup(cfg, "script", "https://notcdn.vendor.com.evil.io/lib.js") is None
    assert osano_config.lookup(cfg, "script", "https://evil.example/a.facebook.net/x") is None
    assert osano_config.lookup(cfg, "script", "https://cdn.vendor.com/lib/v2.js")["category"] == "ANALYTICS"
    assert osano_config.lookup(cfg, "script", "https://connect.facebook.net/x.js")["category"] == "MARKETING"


def test_partly_probed_page_cannot_be_declared_clean():
    cfg = osano_config.normalize({"items": [{"type": "script", "section": "rules", "match": "cmp.osano.com",
                                             "category": "ESSENTIAL"}]})
    prof = _merge(_profile(), {"scenarios": ["no_choice", "reject_all"]})
    dead = {"page_id": "home", "url": "u", "scenario": "reject_all", "phases": {}, "requests": [],
            "consent_action": None, "error": "TimeoutError", "console_errors": [], "page_errors": []}
    res = analyse(prof, [_clean_obs(), dead], cfg, CAT)
    assert _find(res, "CNS-07", "all")[0]["status"] == "error"
    assert {f["status"] for f in res["findings"] if f["id"] in ("CFG-01", "CFG-02", "CFG-03")} == {"error"}


def test_gcm02_not_judged_when_gpc_signal_missing():
    prof = _merge(_profile(), {"scenarios": ["gpc_signal"]})
    snap = _snap()
    snap["gpc"] = False
    hit = _req("https://region1.google-analytics.com/g/collect?gcs=G111", "pre_consent", "image")
    res = analyse(prof, [_obs("gpc_signal", [hit], {"pre_consent": snap, "after_reload": snap})], None, CAT)
    assert _find(res, "GCM-02", "gpc_signal")[0]["status"] == "error"


def test_report_refuses_paths_outside_its_folders(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(runs, "REPORTS", tmp_path / "reports")
    run = _run_of([_clean_obs()])
    run["meta"]["profile"] = "..\\..\\ESCAPED"
    f = tmp_path / "evil.json"
    f.write_text(json.dumps(run), encoding="utf-8")
    assert cli.main(["report", "--run", str(f)]) == 2
    assert not any(p.name == "ESCAPED" for p in tmp_path.rglob("*"))
    with pytest.raises(ValueError):
        runs.save(run)
    run["meta"]["profile"] = "p"
    run["meta"]["run_id"] = "20261007-000000_x/../../../pwn"     # the file name can escape too
    with pytest.raises(ValueError):
        runs.check_ids(run["meta"])
    with pytest.raises(ValueError):
        runs.save(run)
    assert not list(tmp_path.rglob("pwn*"))


def test_index_survives_bad_timestamps_and_bool_counts(tmp_path, monkeypatch):
    from osano_harness import report
    monkeypatch.setattr(report, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(report, "REPORTS", tmp_path / "reports")
    (tmp_path / "reports" / "p").mkdir(parents=True)
    base = {"display_name": "d", "before": "b", "after": "a", "verdict": "MIXED", "risk": "HIGH",
            "counts": {"fixed": 1, "new": 0, "still": 0}}
    (tmp_path / "reports" / "p" / "compare_a.json").write_text(json.dumps({**base, "compared_utc": 5}))
    (tmp_path / "reports" / "p" / "compare_b.json").write_text(json.dumps(
        {**base, "counts": {"fixed": True, "new": 0, "still": 0}}))
    (tmp_path / "reports" / "p" / "compare_c.json").write_text(json.dumps({**base, "compared_utc": "2026-10-07"}))
    data = report.index_data()
    assert len(data["comparisons"]) == 1 and len(data["skipped"]) == 2


def test_run_summary_withholds_counts_when_checks_not_judged():
    dead = {"page_id": "home", "url": "u", "scenario": "reject_all", "phases": {}, "requests": [],
            "consent_action": None, "error": "TimeoutError", "console_errors": [], "page_errors": []}
    run = _run_of([_obs("no_choice", [_req("https://connect.facebook.net/x.js", "pre_consent")],
                        {"pre_consent": _snap(), "after_reload": _snap()}), dead],
                  _merge(_profile(), {"scenarios": ["no_choice", "reject_all"]}))
    html_text = render_run(run)
    assert "None" not in html_text.split("<main>")[1].split("</section>")[0]
    assert "totals are withheld" in html_text


# ================================================================================ round 4
def test_non_ascii_label_gives_a_valid_run_id():
    for label in ("Café", "naïve", "ÄFTER", "x²", "Ⅻ", "my label", ""):
        runs.check_ids({"profile": "p", "run_id": runs.new_run_id(label)})


def test_bad_run_files_exit_2_not_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runs, "RUNS", tmp_path / "runs")
    inside = tmp_path / "runs" / "p"
    inside.mkdir(parents=True)
    run = _run_of([_clean_obs()])
    run["meta"]["profile"] = "Bad Name"
    (inside / "r.json").write_text(json.dumps(run), encoding="utf-8")
    assert cli.main(["report", "--run", str(inside / "r.json")]) == 2
    weird = _run_of([_clean_obs()])
    weird["meta"] = ["x"]
    (tmp_path / "w.json").write_text(json.dumps(weird), encoding="utf-8")
    assert cli.main(["compare", "--profile", "p", "--before", str(tmp_path / "w.json"),
                     "--after", str(tmp_path / "w.json")]) == 2


def test_pass_then_not_judged_is_labelled_and_gated(capsys):
    def f(status):
        return {"id": "CNS-01", "page": "home", "scenario": "no_choice", "status": status, "severity": "high",
                "title": "t", "detail": "", "evidence": []}

    def run(fs):
        return {"meta": {"profile": "p", "run_id": "r"}, "profile": {"pages": [{"id": "home"}]},
                "osano_config": None, "analysis": {"findings": fs, "metrics": {
                    "kpis": {}, "by_scenario": {}, "inventory": [], "perf": {}}}}
    cmp = compare(run([f("pass")]), run([f("error")]))
    assert cmp["findings"][0]["change"] == "unjudged" and cmp["counts"]["new"] == 0
    assert cli._gate_compare(cmp, "new-high") == cli.GATE_EXIT
    out = capsys.readouterr().out
    assert "could not be judged" in out and "introduced" not in out


def test_page_with_no_probeable_choice_reports_every_page_check():
    dead = {"page_id": "home", "url": "u", "scenario": "no_choice", "phases": {}, "requests": [],
            "consent_action": None, "error": "TimeoutError", "console_errors": [], "page_errors": []}
    res = analyse(_profile(), [dead], None, CAT)
    ids = {f["id"] for f in res["findings"] if f["status"] == "error"}
    assert {"OSN-04", "OSN-05", "OSN-06", "GCM-01", "GCM-03"} <= ids


def test_windows_device_name_refused_as_profile():
    with pytest.raises(ValueError):
        runs.check_ids({"profile": "nul", "run_id": "20261007-000000_x"})
    with pytest.raises(ProfileError):
        validate(_merge(_valid(), {"name": "con"}))


def test_path_prefix_respects_segment_boundary():
    cfg = osano_config.normalize({"items": [{"type": "script", "section": "rules", "match": "cdn.vendor.com/lib",
                                             "category": "ANALYTICS"}]})
    assert osano_config.lookup(cfg, "script", "https://cdn.vendor.com/library-evil.js") is None
    assert osano_config.lookup(cfg, "script", "https://cdn.vendor.com/lib.js") is not None
    assert CAT.classify_url("https://www.google.com/recaptchaEVIL/x.js").category != "ESSENTIAL"


# ================================================================================ round 5
def test_dead_page_reports_every_check_it_would_have_made():
    prof = _merge(_profile(), {"scenarios": ["reject_all"],
                               "pages": [{"id": "home", "url": "https://site.test/",
                                          "journey_checks": [{"id": "f", "selector": "form"}]}]})
    dead = {"page_id": "home", "url": "u", "scenario": "reject_all", "phases": {}, "requests": [],
            "consent_action": None, "error": "TimeoutError", "console_errors": [], "page_errors": []}
    res = analyse(prof, [dead], None, CAT)
    ids = {f["id"] for f in res["findings"] if f["status"] == "error"}
    assert {"BNR-03", "BNR-04", "FUN-02", "GCM-02"} <= ids


def test_failed_before_not_judged_after_is_not_called_still_failing():
    def f(status):
        return {"id": "GCM-02", "page": "home", "scenario": "accept_all", "status": status, "severity": "high",
                "title": "t", "detail": "", "evidence": []}

    def run(fs):
        return {"meta": {"profile": "p", "run_id": "r"}, "profile": {"pages": [{"id": "home"}]},
                "osano_config": None, "analysis": {"findings": fs, "metrics": {
                    "kpis": {}, "by_scenario": {}, "inventory": [], "perf": {}}}}
    cmp = compare(run([f("fail")]), run([f("error")]))
    assert cmp["findings"][0]["change"] == "stale" and cmp["counts"]["fixed"] == 0
    from osano_harness.report import CHANGE_FILL
    assert "NOT JUDGED" in CHANGE_FILL["stale"][0]
