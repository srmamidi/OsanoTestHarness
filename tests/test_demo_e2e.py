# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""End to end against the local demo site in a real headless browser. Offline: every non-local
request is answered by stubs. Proves the harness catches known mistakes and sees the fix."""
from __future__ import annotations

import pytest

from osano_harness.analysis import analyse
from osano_harness.catalog import Catalog
from osano_harness.profile import load_profile

playwright = pytest.importorskip("playwright.sync_api")

PORT = 8772


@pytest.fixture(scope="module")
def server():
    from osano_harness.demo.site import DemoServer
    with DemoServer(PORT) as srv:
        yield srv


def _run(variant, server):
    from osano_harness.demo.vendors import route_handler
    from osano_harness.probe import run_probe
    server.set_variant(variant)
    prof = load_profile("demo-prod")
    prof["scenarios"] = ["no_choice", "reject_all", "analytics_only"]
    for p in prof["pages"]:
        p["url"] = p["url"].replace(":8770", f":{PORT}")
    try:
        obs = run_probe(prof, router=route_handler, progress=lambda _m: None)
    except Exception as exc:  # noqa: BLE001
        # Skip ONLY when Chromium is not installed; any other error is a real failure of the harness.
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
            pytest.skip(f"browser not installed: {exc}")
        raise
    return analyse(prof, obs, None, Catalog(first_party_domains=prof["first_party_domains"]))


def _status(res, cid, page, scenario):
    return next(f["status"] for f in res["findings"] if f["id"] == cid and f["page"] == page
                and f["scenario"] == scenario)


def test_before_variant_mistakes_are_caught(server):
    res = _run("before", server)
    assert _status(res, "OSN-02", "home", "no_choice") == "fail"          # GTM above Osano
    assert _status(res, "OSN-03", "apply-step-one", "no_choice") == "fail"  # LLE config on prod page
    assert _status(res, "CNS-01", "home", "no_choice") == "fail"          # pixel fires on arrival
    assert _status(res, "CNS-05", "home", "reject_all") == "fail"         # _ga survives Reject
    assert _status(res, "GCM-01", "home", "no_choice") == "fail"          # no consent default
    assert _status(res, "BNR-02", "home", "analytics_only") == "pass"     # custom toggles really applied


def test_after_variant_fixes_and_regression_are_seen(server):
    res = _run("after", server)
    assert _status(res, "OSN-02", "home", "no_choice") == "pass"
    assert _status(res, "OSN-03", "apply-step-one", "no_choice") == "pass"
    assert _status(res, "CNS-01", "home", "no_choice") == "pass"
    assert _status(res, "CNS-05", "home", "reject_all") == "pass"
    assert _status(res, "GCM-02", "home", "analytics_only") == "pass"
    # Google Maps classified as MARKETING: autocomplete breaks once marketing is refused.
    assert _status(res, "FUN-02", "apply-step-one", "reject_all") == "fail"
