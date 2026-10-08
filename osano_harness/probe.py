# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""Browser probe: open each page once per consent scenario in a clean browser and record raw facts.

Per page x scenario, three moments are captured:
  pre_consent   after the page settles, before any click
  post_consent  after the consent click (scenarios with a click only)
  after_reload  after reloading the page, so the stored choice is what drives behaviour

Read-only by design: the probe clicks only the consent banner and never fills or submits forms.
No judgement happens here; analysis.py turns these facts into checks and metrics.
"""
from __future__ import annotations

import base64
import json
import re
import time
from typing import Callable

from .catalog import host_of, is_first_party
from .scenarios import SCENARIOS, Scenario, intended_consent

_INIT_JS = r"""
(() => {
  const GPC = __GPC__, LISTEN = __LISTEN__;
  if (GPC) {
    try { Object.defineProperty(Navigator.prototype, 'globalPrivacyControl', {get: () => true, configurable: true}); } catch (e) {}
  }
  window.__oth = {events: [], lcp: null, cls: 0};
  const summarize = (d) => {
    try {
      if (d == null) return null;
      if (typeof d === 'string') return d.slice(0, 300);
      if (d.src || d.name || d.url) return String(d.src || d.name || d.url).slice(0, 300);
      return JSON.stringify(d).slice(0, 300);
    } catch (e) { return String(d).slice(0, 300); }
  };
  if (LISTEN) {
    // Osano's documented pre-load interface: queue calls until osano.js loads.
    (function (w, o, d) { w[o] = w[o] || function () { w[o][d].push(arguments); }; w[o][d] = w[o][d] || []; })(window, 'Osano', 'data');
    ['onInitialized', 'onConsentSaved', 'onConsentChanged', 'onConsentNew', 'onScriptBlocked',
     'onCookieBlocked', 'onIframeBlocked', 'onLocalStorageBlocked', 'onUiChanged'].forEach((n) => {
      try { window.Osano(n, (d) => window.__oth.events.push({name: n, t: Math.round(performance.now()), detail: summarize(d)})); } catch (e) {}
    });
  }
  try {
    new PerformanceObserver((l) => { const e = l.getEntries(); if (e.length) window.__oth.lcp = e[e.length - 1].startTime; })
      .observe({type: 'largest-contentful-paint', buffered: true});
    new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__oth.cls += e.value; })
      .observe({type: 'layout-shift', buffered: true});
  } catch (e) {}
})();
"""

_CAPTURE_JS = r"""
(bannerSelectors) => {
  const safe = (fn, dflt) => { try { return fn(); } catch (e) { return dflt; } };
  const plain = (v, depth) => {
    if (depth > 4) return '…';
    if (v == null || typeof v !== 'object') return typeof v === 'function' ? '[fn]' : v;
    if (!Array.isArray(v) && typeof v.length === 'number' && '0' in v && !(v instanceof Element))
      return {__args: Array.from(v).map((x) => plain(x, depth + 1))};
    if (Array.isArray(v)) return v.slice(0, 30).map((x) => plain(x, depth + 1));
    const o = {}; let n = 0;
    for (const k of Object.keys(v)) { if (n++ > 30) break; o[k] = plain(v[k], depth + 1); }
    return o;
  };
  const cm = safe(() => window.Osano && window.Osano.cm, null);
  // Not offsetParent: it is null for position:fixed elements, which consent banners usually are.
  const visible = (el) => {
    if (!el) return false;
    const cs = getComputedStyle(el);
    return el.getClientRects().length > 0 && cs.display !== 'none' && cs.visibility !== 'hidden'
      && parseFloat(cs.opacity || '1') > 0;
  };
  const bannerEls = bannerSelectors.flatMap((s) => safe(() => [...document.querySelectorAll(s)], []));
  const bannerVisible = bannerEls.some(visible);
  const nav = safe(() => performance.getEntriesByType('navigation')[0], null);
  const res = safe(() => performance.getEntriesByType('resource'), []);
  const osanoRes = res.find((r) => /osano\.js/.test(r.name));
  return {
    title: document.title,
    osano: cm ? {
      present: true,
      mode: safe(() => cm.mode, null), consentModel: safe(() => cm.consentModel, null),
      jurisdiction: safe(() => cm.jurisdiction, null), dialogOpen: safe(() => cm.dialogOpen, null),
      consent: safe(() => plain(cm.getConsent(), 0), null), cmpVersion: safe(() => cm.cmpVersion, null),
    } : {present: false},
    // The DOM decides when a banner element exists; Osano.cm.dialogOpen is only a fallback when none matched.
    banner_visible: bannerEls.length ? bannerVisible : !!(cm && safe(() => cm.dialogOpen, false)),
    scripts: [...document.scripts].map((s, i) => ({
      src: s.src || '', type: s.getAttribute('type') || '', inline: !s.src,
      in_head: !!s.closest('head'), index: i,
      data_src: s.getAttribute('data-src') || s.getAttribute('data-oth-src') || '',
    })),
    iframes: [...document.querySelectorAll('iframe')].map((f) => ({
      src: f.getAttribute('src') || '', data_src: f.getAttribute('data-src') || f.getAttribute('data-oth-src') || '',
      visible: visible(f),
    })),
    local_storage: safe(() => Object.keys(localStorage), []),
    session_storage: safe(() => Object.keys(sessionStorage), []),
    datalayer: safe(() => (window.dataLayer || []).slice(0, 200).map((e) => plain(e, 0)), []),
    events: safe(() => window.__oth.events.slice(0, 500), []),
    gpc: safe(() => navigator.globalPrivacyControl === true, false),
    perf: {
      dcl_ms: nav ? Math.round(nav.domContentLoadedEventEnd) : null,
      load_ms: nav ? Math.round(nav.loadEventEnd) : null,
      lcp_ms: safe(() => window.__oth.lcp == null ? null : Math.round(window.__oth.lcp), null),
      cls: safe(() => Math.round(window.__oth.cls * 1000) / 1000, null),
      resources: res.length,
      transfer_kb: Math.round(res.reduce((a, r) => a + (r.transferSize || 0), 0) / 1024),
      osano_script_ms: osanoRes ? Math.round(osanoRes.duration) : null,
      osano_script_start_ms: osanoRes ? Math.round(osanoRes.startTime) : null,
    },
  };
}
"""


def _first_visible(page, selectors: list[str]):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                return loc, sel
        except Exception:  # noqa: BLE001 — a bad selector just means "try the next one"
            continue
    return None, None


def _set_toggle(page, toggle, want: bool) -> str:
    """Never force-click: a forced click lands on whatever covers the toggle (possibly a real link).
    Try the input itself, then the label around it; if neither works, raise so the choice is ERROR."""
    try:
        toggle.set_checked(want, timeout=3000)
        return "input"
    except Exception:  # noqa: BLE001 — hidden inputs are normal in styled switches; try the label
        label = toggle.locator("xpath=ancestor::label[1]")
        if label.count():
            label.first.click(timeout=3000)
            if toggle.is_checked() == want:
                return "label"
        raise RuntimeError("toggle could not be switched without forcing a click")


def _apply_consent(page, scenario: Scenario, selectors: dict, on_commit=None) -> dict:
    """Click the banner like a visitor. Returns what was clicked; never raises.
    on_commit() runs immediately before the click that commits the choice (Accept / Deny / Save),
    so requests are tagged post_consent from that moment — not from when the drawer was opened."""
    steps: list[str] = []
    commit = on_commit or (lambda: None)
    try:
        if scenario.action in ("accept_all", "deny_all"):
            loc, sel = _first_visible(page, selectors[scenario.action])
            if not loc:
                return {"applied": False, "steps": steps,
                        "error": f"no visible {scenario.action} button ({', '.join(selectors[scenario.action])})"}
            commit()
            loc.click(timeout=5000)
            steps.append(f"clicked {sel}")
            return {"applied": True, "steps": steps}
        if scenario.action == "custom":
            loc, sel = _first_visible(page, selectors["manage"])
            if loc:
                loc.click(timeout=5000)
                steps.append(f"clicked {sel}")
            else:
                page.evaluate("() => window.Osano && window.Osano.cm && window.Osano.cm.showDrawer && "
                              "window.Osano.cm.showDrawer('osano-cm-dom-info-dialog-open')")
                steps.append("opened preferences via Osano.cm.showDrawer()")
            page.wait_for_timeout(600)
            for category in ("ANALYTICS", "MARKETING", "PERSONALIZATION"):
                want = category in scenario.granted
                toggle = None
                for tmpl in selectors["category_toggle"]:
                    cand = page.locator(tmpl.format(category=category)).first
                    if cand.count():
                        toggle = cand
                        break
                if toggle is None:
                    steps.append(f"no toggle for {category}")
                    continue
                how = "unchanged"
                if toggle.is_checked() != want:
                    how = _set_toggle(page, toggle, want)
                steps.append(f"{category} -> {'on' if want else 'off'} ({how})")
            loc, sel = _first_visible(page, selectors["save"])
            if not loc:
                return {"applied": False, "steps": steps, "error": "no visible save button"}
            commit()
            loc.click(timeout=5000)
            steps.append(f"clicked {sel}")
            return {"applied": True, "steps": steps}
    except Exception as exc:  # noqa: BLE001 — recorded as a harness error, not a site result
        return {"applied": False, "steps": steps, "error": f"{type(exc).__name__}: {exc}"[:300]}
    return {"applied": False, "steps": steps, "error": "no action for scenario"}


def _settle(page, crawl: dict) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=crawl["network_idle_ms"])
    except Exception:  # noqa: BLE001 — busy pages never go idle; the fixed wait below still applies
        pass
    page.wait_for_timeout(crawl["settle_ms"] // 2)


def _cookies(ctx) -> list[dict]:
    return [{"name": c["name"], "domain": c["domain"], "path": c["path"], "secure": c["secure"],
             "httpOnly": c["httpOnly"], "sameSite": c.get("sameSite"),
             "expires": c["expires"], "session": c["expires"] in (-1, None)} for c in ctx.cookies()]


def probe_page_scenario(browser, profile: dict, page_cfg: dict, scenario: Scenario,
                        router: Callable | None = None, user_agent: str | None = None) -> dict:
    crawl, osano = profile["crawl"], profile["osano"]
    first_party = profile["first_party_domains"]
    # A fresh context per scenario = a brand-new visitor with no cookies or storage.
    ctx_args: dict = {"viewport": crawl["viewport"], "locale": "en-US"}
    if user_agent:
        ctx_args["user_agent"] = user_agent
    if scenario.gpc:
        ctx_args["extra_http_headers"] = {"Sec-GPC": "1"}
    ctx = browser.new_context(**ctx_args)
    init = (_INIT_JS.replace("__GPC__", "true" if scenario.gpc else "false")
                    .replace("__LISTEN__", "true" if osano.get("inject_event_listener", True) else "false"))
    ctx.add_init_script(init)
    if router:
        ctx.route("**/*", router)
    elif profile["network"].get("block_hosts"):
        blocked = [h.lower() for h in profile["network"]["block_hosts"]]

        def _block(route):
            host = host_of(route.request.url)
            if any(host == b or host.endswith("." + b) for b in blocked):
                return route.abort()
            return route.continue_()
        ctx.route("**/*", _block)

    page = ctx.new_page()
    page.set_default_timeout(crawl["timeout_ms"])
    t0 = time.monotonic()
    state = {"phase": "pre_consent"}
    requests: list[dict] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    statuses: dict[str, int] = {}

    def on_request(req):
        url = req.url
        if url.startswith(("data:", "blob:")):
            return
        host = host_of(url)
        requests.append({
            "url": url[:1500], "host": host, "type": req.resource_type, "method": req.method,
            "phase": state["phase"], "t_ms": round((time.monotonic() - t0) * 1000),
            "third_party": not is_first_party(host, first_party),
            "main_frame": req.frame == page.main_frame if req.frame else False,
        })

    def on_response(resp):
        if resp.request.resource_type == "document" and resp.frame == page.main_frame:
            statuses[state["phase"]] = resp.status

    page.on("request", on_request)
    page.on("response", on_response)
    page.on("console", lambda m: console_errors.append(m.text[:300]) if m.type == "error" else None)
    page.on("pageerror", lambda e: page_errors.append(str(e)[:300]))

    result: dict = {"page_id": page_cfg["id"], "url": page_cfg["url"], "scenario": scenario.id,
                    "phases": {}, "consent_action": None, "error": None}
    banner_sel = osano["selectors"]["banner"]
    try:
        page.goto(page_cfg["url"], wait_until="load", timeout=crawl["timeout_ms"])
        _settle(page, crawl)
        snap = page.evaluate(_CAPTURE_JS, banner_sel)
        snap["cookies"] = _cookies(ctx)
        snap["status"] = statuses.get("pre_consent")
        result["phases"]["pre_consent"] = snap
        if crawl.get("screenshots") and scenario.id in ("no_choice", "reject_all"):
            shot = page.screenshot(type="jpeg", quality=45, full_page=False)
            result["screenshot_b64"] = base64.b64encode(shot).decode("ascii")

        if scenario.action != "none":
            def commit():
                # Deliver every request event already queued, so pre-click requests keep pre_consent.
                page.evaluate("0")
                state["phase"] = "post_consent"
            result["consent_action"] = _apply_consent(page, scenario, osano["selectors"], commit)
            state["phase"] = "post_consent"
            _settle(page, crawl)
            snap = page.evaluate(_CAPTURE_JS, banner_sel)
            snap["cookies"] = _cookies(ctx)
            result["phases"]["post_consent"] = snap
            result["consent_action"]["intended"] = intended_consent(scenario)

        page.evaluate("0")          # flush queued request events before re-tagging
        state["phase"] = "after_reload"
        page.reload(wait_until="load", timeout=crawl["timeout_ms"])
        _settle(page, crawl)
        snap = page.evaluate(_CAPTURE_JS, banner_sel)
        snap["cookies"] = _cookies(ctx)
        snap["status"] = statuses.get("after_reload")
        snap["journey"] = _journey(page, page_cfg.get("journey_checks", []))
        result["phases"]["after_reload"] = snap
    except Exception as exc:  # noqa: BLE001 — one broken page must not stop the run
        result["error"] = f"{type(exc).__name__}: {exc}"[:500]
    finally:
        result["requests"] = requests
        result["console_errors"] = console_errors[:50]
        result["page_errors"] = page_errors[:50]
        result["duration_ms"] = round((time.monotonic() - t0) * 1000)
        ctx.close()
    return result


def _journey(page, checks: list[dict]) -> list[dict]:
    """Read-only checks that the page still works: an element is visible, or a JS expression is true."""
    out = []
    for chk in checks:
        ok, detail = False, ""
        try:
            if chk.get("selector"):
                loc = page.locator(chk["selector"]).first
                ok = bool(loc.count()) and loc.is_visible()
                detail = "visible" if ok else "not visible"
            elif chk.get("js"):
                ok = bool(page.evaluate(f"() => {{ try {{ return !!({chk['js']}); }} catch (e) {{ return false; }} }}"))
                detail = "true" if ok else "false"
        except Exception as exc:  # noqa: BLE001
            detail = f"{type(exc).__name__}"
        out.append({"id": chk.get("id", chk.get("selector") or chk.get("js")),
                    "description": chk.get("description", ""), "ok": ok, "detail": detail})
    return out


def run_probe(profile: dict, *, progress: Callable[[str], None] = print,
              router: Callable | None = None) -> list[dict]:
    from playwright.sync_api import sync_playwright

    observations: list[dict] = []
    scenarios = [SCENARIOS[s] for s in profile["scenarios"]]
    total = len(scenarios) * len(profile["pages"])
    n = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=profile["crawl"]["headless"])
        try:
            # Tag the user agent so site owners can recognise (and allow-list) harness traffic.
            user_agent = None
            if profile["crawl"].get("user_agent_suffix"):
                tmp = browser.new_page()
                user_agent = f"{tmp.evaluate('() => navigator.userAgent')} {profile['crawl']['user_agent_suffix']}"
                tmp.close()
            for page_cfg in profile["pages"]:
                for scenario in scenarios:
                    n += 1
                    progress(f"[{n}/{total}] {page_cfg['id']} :: {scenario.id}")
                    obs = probe_page_scenario(browser, profile, page_cfg, scenario, router, user_agent)
                    progress(f"    {obs['duration_ms'] / 1000:.1f}s, {len(obs['requests'])} requests"
                             + (f"  ! {obs['error']}" if obs.get("error") else ""))
                    observations.append(obs)
                    time.sleep(profile["crawl"]["polite_delay_ms"] / 1000)
        finally:
            browser.close()
    return observations


def osano_script_ids(url: str, regex: str) -> dict | None:
    m = re.search(regex, url)
    return {"customer": m.group("customer"), "config": m.group("config")} if m else None


def dumps(obj) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False)
