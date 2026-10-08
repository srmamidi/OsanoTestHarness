# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""HTML reports, designed to be read in under a minute:

run report      Result (risk + problems to fix) | Site & Osano (where it leaks) | How to read
compare report  Before vs After (risk, scorecard, problem-by-problem) | What changed | How to read
index           every comparison and run, newest first
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import osano_config
from .analysis import CHECKS, group_findings, usable
from .compare import LABELS, risk
from .html_shell import esc, evidence, page, table, tag
from .runs import REPORTS, RUNS
from .scenarios import SCENARIOS

RISK_KIND = {"HIGH": "danger", "MEDIUM": "warn", "LOW": "good"}
VERDICT_KIND = {"IMPROVED": "good", "REGRESSED": "danger", "MIXED": "warn", "UNCHANGED": "muted",
                "INCOMPLETE": "info"}
SEV_LABEL = {"high": "High", "medium": "Medium", "low": "Low", "info": "Info"}
SEV_FILL = {"high": "f-bad", "medium": "f-warn", "low": "f-info", "info": "f-muted"}
STATUS_FILL = {"fail": ("FAIL", "f-bad"), "warn": ("WARN", "f-warn"), "error": ("NOT JUDGED", "f-info"),
               "pass": ("PASS", "f-good"), "na": ("n/a", "f-muted"), "absent": ("—", "f-muted")}
CHANGE_FILL = {"new": ("NEW PROBLEM", "f-bad"), "still": ("STILL OPEN", "f-warn"), "fixed": ("FIXED", "f-good"),
               "gone": ("NO LONGER CHECKED", "f-muted"), "judged": ("NOW JUDGED", "f-info"), "unjudged": ("NOT JUDGED NOW", "f-info"), "stale": ("FAILED BEFORE, NOT JUDGED NOW", "f-warn"),
               "ok": ("OK", "f-muted")}
SCEN_SHORT = {"no_choice": "No choice", "accept_all": "Accept", "reject_all": "Reject",
              "analytics_only": "Analytics only", "marketing_only": "Marketing only",
              "personalization_only": "Personalization only", "gpc_signal": "GPC on"}


# The problem in plain words — check titles read as goals ("No ... "), a problem list must read as problems.
PROBLEM = {
    "OSN-01": "Osano script is missing", "OSN-02": "Other scripts load before Osano",
    "OSN-03": "Page uses the wrong Osano configuration", "OSN-04": "Osano is loaded twice",
    "OSN-05": "Osano is in the wrong mode", "OSN-06": "Unexpected consent model (opt-in/opt-out)",
    "BNR-01": "New visitors do not see the banner", "BNR-02": "Consent choice could not be applied",
    "BNR-03": "Banner comes back after a choice", "BNR-04": "Choice is not saved",
    "CNS-01": "Trackers fire before the visitor chooses", "CNS-02": "Tracking cookies set before the visitor chooses",
    "CNS-03": "Tracking iframes load before the visitor chooses", "CNS-04": "Trackers fire against the visitor's choice",
    "CNS-05": "Tracking cookies set against the visitor's choice",
    "CNS-06": "Tracking iframes load against the visitor's choice", "CNS-07": "Unknown third parties on the page",
    "CNS-08": "Analytics/marketing do not run even after Accept", "GPC-01": "\"Do not sell\" (GPC) signal ignored",
    "GCM-01": "Google tags fire before the consent default", "GCM-02": "Google receives the wrong consent state",
    "GCM-03": "Google Consent Mode v2 signals missing", "FUN-01": "Page does not load",
    "FUN-02": "Page feature broken by consent blocking", "FUN-03": "JavaScript errors on the page",
    "CFG-01": "Osano puts a vendor in the wrong category", "CFG-02": "Items not classified in Osano",
    "CFG-03": "Tracker placed in Osano's Ignored list", "CFG-04": "Same item in Osano Rules and Ignored",
    "CFG-05": "Essential item in Ignored (blocked in Strict mode)",
}


def _fmt(v) -> str:
    if v is None:
        return "—"
    return f"{v:g}" if isinstance(v, float) else str(v)


def _fix(cid: str) -> str:
    return CHECKS[cid][3]


def _where(g: dict, n_scenarios: int) -> str:
    bad = list(dict.fromkeys(s for s in g["scenarios_bad"] if s in SCEN_SHORT))
    if not [s for s in g["scenarios_all"] if s in SCEN_SHORT]:
        return "whole site"
    if len(bad) == n_scenarios and n_scenarios > 1:
        return "every choice"
    return ", ".join(SCEN_SHORT[s] for s in bad) or "—"


def _sample_note(*runs_) -> str:
    if any(r["meta"].get("demo") for r in runs_):
        return ('<p class="muted">Sample data from the built-in demo site — not a real website.</p>')
    return ""


def _hero(level: str, headline: str, lines: list[str], kind: str | None = None) -> str:
    k = kind or RISK_KIND[level]
    body = "".join(f"<p>{line}</p>" for line in lines)
    return (f'<div class="hero {k}"><div class="big"><small>Risk</small>{esc(level)}</div>'
            f'<div><p class="lead"><b>{headline}</b></p>{body}</div></div>')


def _numbers(rows: list[tuple[str, object, bool]]) -> str:
    """(label, value, is_bad) as one compact filled table — reads faster than cards.
    None = could not be judged: shown as such, never as a green zero."""
    cells = [[esc(label), ("not judged", "num f-info") if v is None
              else (esc(_fmt(v)), "num " + ("f-bad" if bad else "f-good"))] for label, v, bad in rows]
    return table(["Measure", "Value"], cells)


# ------------------------------------------------------------------ run report
def _run_hero(run: dict, groups: list[dict]) -> str:
    k = run["analysis"]["metrics"]["kpis"]
    r = risk(groups, [])
    open_ = [g for g in groups if g["status"] in ("fail", "warn")]
    pages = len(run["profile"]["pages"])
    top = [PROBLEM[g["id"]] for g in open_ if g["severity"] == "high"]
    top = list(dict.fromkeys(top))[:3]
    scope = f"{pages} page(s) × {len(run['profile']['scenarios'])} consent choices"
    if k.get("issues_total") is None:
        # Counts are withheld when anything was not judged — say so instead of printing a partial count.
        lines = [f"Score <b>—</b> · <b>{k['checks_error']}</b> check(s) could not be judged, so totals are "
                 f"withheld · at least <b>{len(open_)}</b> problem(s) found so far · {scope}."]
    else:
        lines = [f"Score <b>{_fmt(k['compliance_score'])}</b> / 100 · <b>{k['issues_total']}</b> problem(s) to fix, "
                 f"<b>{k['issues_high']}</b> high-risk · {scope}."]
    if top:
        lines.append("Biggest: " + "; ".join(esc(t) for t in top) + ".")
    m = run["meta"]
    headline = f"{esc(m['display_name'])} — {esc(m['label'])} run, {esc(m['finished_utc'][:16].replace('T', ' '))} UTC"
    return _hero(r["level"], headline, lines)


def _problems_table(groups: list[dict], n_scenarios: int) -> str:
    rows = []
    for g in groups:
        if g["status"] not in ("fail", "warn", "error"):
            continue
        sev = (SEV_LABEL[g["severity"]], SEV_FILL[g["severity"]]) if g["status"] != "error" else ("Not judged", "f-info")
        rows.append([sev, f"<b>{esc(PROBLEM[g['id']])}</b><br><span class='muted'>{esc(g['detail'])}</span>",
                     esc(g["page"]), esc(_where(g, n_scenarios)), esc(_fix(g["id"])), evidence(g["evidence"], 15)])
    return table(["Risk", "Problem", "Page", "Where", "How to fix", "Evidence"], rows,
                 empty="Nothing to fix — every check passed.")


def _passed(groups: list[dict]) -> str:
    ok = [g for g in groups if g["status"] in ("pass", "na")]
    if not ok:
        return ""
    names = sorted({g["title"] for g in ok})
    return (f"<details><summary>{len(ok)} checks passed</summary><ul class='ev'>"
            + "".join(f"<li>{esc(n)}</li>" for n in names) + "</ul></details>")


def _matrix(run: dict) -> str:
    """Page x consent choice: how many disallowed items fired. Green 0, red otherwise."""
    pages = [p["id"] for p in run["profile"]["pages"]]
    scen = run["profile"]["scenarios"]
    ps = run["analysis"]["metrics"]["by_page_scenario"]
    rows = []
    for p in pages:
        cells = [f"<b>{esc(p)}</b>"]
        for s in scen:
            m = ps.get(f"{p}|{s}", {})
            if m.get("error") or m.get("unjudged"):
                # A choice that was never applied has no meaningful leak count — never show it as a green 0.
                cells.append(("not judged", "f-info"))
                continue
            v = m.get("violations", 0)
            cells.append((str(v), "num " + ("f-bad" if v else "f-good")))
        rows.append(cells)
    return table(["Page", *[SCEN_SHORT[s] for s in scen]], rows)


def _grid(cfg_grid: dict | None, observed: dict | None) -> str:
    if not cfg_grid:
        return '<p class="muted">No Osano export was supplied for this run, so the Osano grid is not shown.</p>'
    rows = []
    for t in osano_config.TYPES:
        g = cfg_grid.get(t, {})
        missing = (observed or {}).get(t, {}).get("missing", 0)
        rows.append([f"<b>{esc(t.title())}s</b>",
                     (str(g.get("rules", 0)), "num f-good"),
                     (str(g.get("discovered", 0)), "num " + ("f-warn" if g.get("discovered") else "f-muted")),
                     (str(g.get("ignored", 0)), "num f-muted"),
                     (str(missing), "num " + ("f-bad" if missing else "f-muted"))])
    return table(["Type", "Classified (Rules)", "Waiting (Discovered)", "Ignored", "On the site but not in Osano"],
                 rows)


PHASE_SHORT = {"pre_consent": "on arrival", "post_consent": "after click", "after_reload": "after reload"}


def _osano_cell(section: str):
    if section == "n/a":
        return ("no export", "f-muted")
    return (esc(section), {"rules": "f-good", "discovered": "f-warn", "ignored": "f-muted",
                           "missing": "f-bad"}.get(section, "f-muted"))


def _lifetime(expires, finished_utc: str) -> str:
    if expires in (None, -1) or (isinstance(expires, (int, float)) and expires <= 0):
        return "session"
    from datetime import datetime, timezone
    try:
        base = datetime.strptime(finished_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return "persistent"
    days = (expires - base) / 86400
    return f"{days / 365:.1f} years" if days >= 365 else (f"{days:.0f} days" if days >= 1 else f"{days * 24:.0f} hours")


def _cookies(run: dict) -> str:
    inv = [it for it in run["analysis"]["metrics"]["inventory"] if it["kind"] == "cookie"]
    inv.sort(key=lambda it: (not it["disallowed_in"], it["category"], it["key"]))
    scen = run["profile"]["scenarios"]
    short_phase = {"pre_consent": "arrival", "post_consent": "click", "after_reload": "reload"}
    rows = []
    for it in inv:
        flags = " · ".join(x for x in (
            "Secure" if it.get("secure") else "not Secure", "HttpOnly" if it.get("httpOnly") else "JS-readable",
            f"SameSite={it.get('sameSite') or '—'}"))
        cells = []
        for s in scen:
            def when(entries):
                phases = {e.split("/")[1] for e in entries if e.split("/")[0] == s}
                return [short_phase[p] for p in short_phase if p in phases]   # time order: arrival, click, reload
            present, leaked = when(it.get("set_in", [])), when(it["disallowed_in"])
            if leaked:
                cells.append(("LEAK: " + esc(", ".join(dict.fromkeys(leaked))), "f-bad"))
            elif present:
                cells.append((esc(", ".join(dict.fromkeys(present))), "f-good"))
            else:
                cells.append(("—", "f-muted"))
        rows.append([f"<code>{esc(it['key'])}</code>", f"<code>{esc(it.get('domain', ''))}</code>", esc(it["vendor"]),
                     tag(it["category"]), _osano_cell(it["config_section"]), *cells,
                     esc(_lifetime(it.get("expires"), run["meta"]["finished_utc"])), esc(flags)])
    return ("<h2>Cookies</h2><p class='muted'>Every cookie, by consent choice. Each cell says when the cookie "
            "existed: on <b>arrival</b>, after the <b>click</b>, after <b>reload</b>. "
            "<b>Red LEAK</b> = present although that choice did not allow its category. Green = allowed. "
            "— = not set. Leaking cookies first.</p>"
            + table(["Cookie", "Domain", "What it is", "Category", "In Osano", *[SCEN_SHORT[s] for s in scen],
                     "Lifetime", "Attributes"], rows, empty="No cookies were set."))


def _hosts(run: dict) -> str:
    inv = [it for it in run["analysis"]["metrics"]["inventory"]
           if it["kind"] in ("host", "iframe") and it["category"] != "FIRST_PARTY"]
    inv.sort(key=lambda it: (not it["disallowed_in"], it["kind"], it["category"], it["key"]))
    rows = [[f"<code>{esc(it['key'])}</code>", esc("iframe" if it["kind"] == "iframe" else "request/script"),
             esc(it["vendor"]), tag(it["category"]), _osano_cell(it["config_section"]),
             esc(", ".join(SCEN_SHORT.get(s, s) for s in it["scenarios"])),
             (esc(", ".join(SCEN_SHORT.get(s, s) for s in dict.fromkeys(e.split("/")[0] for e in it["disallowed_in"]))),
              "f-bad") if it["disallowed_in"] else ("never", "f-good")]
            for it in inv]
    storage = [it for it in run["analysis"]["metrics"]["inventory"] if it["kind"] == "storage"]
    srows = [[f"<code>{esc(it['key'])}</code>", esc(it["vendor"]), tag(it["category"]),
              esc(", ".join(SCEN_SHORT.get(s, s) for s in it["scenarios"]))] for it in storage]
    return ("<h2>Third-party hosts and iframes</h2><p class='muted'>Every outside server the pages talked to. "
            "Leaking ones first.</p>"
            + table(["Host", "Kind", "What it is", "Category", "In Osano", "Seen in", "Leaked in"], rows,
                    empty="No third-party traffic.")
            + "<h2>Browser storage (localStorage)</h2>"
            + table(["Key", "What it is", "Category", "Seen in"], srows, empty="Nothing stored."))


def consent_rows(run: dict) -> dict:
    """(page, scenario) -> what the visitor saw and what Osano / Google recorded."""
    from . import google_consent as gcm
    pats = run["profile"]["osano"]["consent_cookie_patterns"]
    ps = run["analysis"]["metrics"]["by_page_scenario"]
    out = {}
    for o in run["observations"]:
        key = (o["page_id"], o["scenario"])
        if not usable(o):
            out[key] = {"error": o.get("error") or "missing data"}
            continue
        pre, rel = o["phases"]["pre_consent"], o["phases"]["after_reload"]
        rec = (rel.get("osano") or {}).get("consent") or {}
        names = [c["name"] for c in rel.get("cookies", [])]
        saved = any(fnmatch_any(n, pats) for n in names)
        hits = [r for r in o["requests"] if r["phase"] != "pre_consent" or o["scenario"] in ("no_choice", "gpc_signal")]
        gcs = sorted({gcm.params(r["url"]).get("gcs") or "MISSING" for r in hits if gcm.is_google_hit(r["url"])})
        gcd = sorted({gcm.params(r["url"]).get("gcd") or "MISSING" for r in hits if gcm.is_google_hit(r["url"])})
        act = o.get("consent_action") or {}
        out[key] = {"banner_arrival": bool(pre.get("banner_visible")), "banner_reload": bool(rel.get("banner_visible")),
                    "recorded": {k: rec.get(k, "—") for k in ("ANALYTICS", "MARKETING", "PERSONALIZATION")},
                    "saved": saved, "gcs": gcs, "gcd": gcd, "applied": act.get("applied"),
                    "leaks": (None if ps.get(f"{o['page_id']}|{o['scenario']}", {}).get("unjudged")
                              else ps.get(f"{o['page_id']}|{o['scenario']}", {}).get("violations", 0)),
                    "gpc": bool(rel.get("gpc"))}
    return out


def fnmatch_any(name: str, patterns: list[str]) -> bool:
    import fnmatch
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def _recorded_text(rec: dict) -> str:
    return " · ".join(f"{k.title()}: {v}" for k, v in rec.items())


def _consent_table(run: dict) -> str:
    data = consent_rows(run)
    rows = []
    for p in [p["id"] for p in run["profile"]["pages"]]:
        for s in run["profile"]["scenarios"]:
            d = data.get((p, s))
            if not d:
                continue
            if "error" in d:
                rows.append([esc(p), esc(SCEN_SHORT[s]), ("probe error: " + esc(d["error"]), "f-info"), "", "", "", "", "", ""])
                continue
            rec_fill = "f-muted"
            want = None
            from .scenarios import intended_consent
            want = intended_consent(SCENARIOS[s])
            if want:
                rec_fill = "f-good" if all(d["recorded"].get(k) == v for k, v in want.items()) else "f-bad"
            rows.append([
                esc(p), esc(SCEN_SHORT[s]),
                ("shown", "f-good") if d["banner_arrival"] else ("NOT shown", "f-bad"),
                (esc(_recorded_text(d["recorded"])), rec_fill),
                (("yes", "f-good") if d["saved"] else (("no", "f-bad") if want else ("no (no choice made)", "f-muted"))),
                (("shown again", "f-bad" if want else "f-muted") if d["banner_reload"] else ("hidden", "f-good" if want else "f-muted")),
                esc(", ".join(d["gcs"]) or "no Google hits"),
                f"<code>{esc(', '.join(d['gcd']) or '—')}</code>",
                (("not judged", "num f-info") if d["leaks"] is None else (str(d["leaks"]), "num " + ("f-bad" if d["leaks"] else "f-good")))])
    return ("<h2>Consent per page and choice</h2><p class='muted'>What the visitor saw, what Osano recorded "
            "(Osano.cm.getConsent after reload: Analytics / Marketing / Personalization), whether the choice was "
            "saved, and the consent state Google received (gcs: G1&lt;ads&gt;&lt;analytics&gt;, 1 = granted).</p>"
            + table(["Page", "Choice", "Banner on arrival", "Osano recorded", "Choice saved", "Banner after reload",
                     "Google gcs", "Google gcd", "Leaks"], rows))


def _google_hits(run: dict) -> str:
    from . import google_consent as gcm
    rows = []
    for o in run["observations"]:
        for r in o.get("requests", []):
            if not gcm.is_google_hit(r["url"]):
                continue
            p = gcm.params(r["url"])
            gcd = gcm.parse_gcd(p.get("gcd"))
            dec = "; ".join(f"{k}={gcd[k]['state'] or 'not set'}" for k in gcm.GCD_SIGNALS) if gcd else "—"
            rows.append([esc(o["page_id"]), esc(SCEN_SHORT[o["scenario"]]), esc(PHASE_SHORT[r["phase"]]),
                         f"<code>{esc(r['host'])}</code>",
                         (esc(p.get("gcs") or "MISSING"), "f-bad" if not p.get("gcs") else "f-info"), esc(dec),
                         esc(p.get("en") or "")])
    return ("<h2>Every Google measurement hit</h2>"
            + table(["Page", "Choice", "When", "Host", "gcs", "gcd decoded", "Event"], rows,
                    empty="No Google measurement hits were seen."))


def _osano_items(run: dict) -> str:
    cfg = run.get("osano_config")
    if not cfg:
        return ""
    rows = [[esc(i["type"]), f"<code>{esc(i['match'])}</code>", _osano_cell(i["section"]),
             tag(i["category"]) if i["category"] else "—"] for i in cfg["items"]]
    return (f"<h3>Every item in the Osano export ({esc(cfg.get('source', ''))})</h3>"
            + table(["Type", "Match", "Section", "Category"], rows))


def _speed(run: dict) -> str:
    perf = run["analysis"]["metrics"]["perf"]
    rows = [[esc(p), (_fmt(v.get("load_ms")), "num"), (_fmt(v.get("lcp_ms")), "num"),
             (_fmt(v.get("osano_script_ms")), "num")] for p, v in perf.items()]
    return ("<details><summary>Page speed on arrival</summary>"
            + table(["Page", "Load (ms)", "Largest paint (ms)", "osano.js (ms)"], rows) + "</details>")


def _shots(run: dict) -> str:
    parts = [f'<p><b>{esc(o["page_id"])}</b></p><img class="shot" alt="first view of {esc(o["page_id"])}" '
             f'src="data:image/jpeg;base64,{o["screenshot_b64"]}">'
             for o in run["observations"] if o.get("screenshot_b64") and o["scenario"] == "no_choice"
             # defence in depth: a run file edited on disk must not inject markup through the src attribute
             and re.fullmatch(r"[A-Za-z0-9+/=]+", o["screenshot_b64"])]
    return f"<details><summary>What a new visitor sees</summary>{''.join(parts)}</details>" if parts else ""


def _how_to_read(compare_mode: bool) -> str:
    rows = [[f"<code>{esc(cid)}</code>", (SEV_LABEL[sev], SEV_FILL[sev]), esc(title), esc(what)]
            for cid, (title, sev, what, _fix_) in CHECKS.items()]
    intro = ("<p><b>Before vs After</b> compares two runs of the same pages. "
             "<b>NEW PROBLEM</b> = passed before, fails now. <b>FIXED</b> = failed before, passes now. "
             "<b>STILL OPEN</b> = failing in both. <b>NOT JUDGED NOW</b> = passed before, could not be checked after "
             "(for a high-risk check this fails the pipeline gate: a check nobody could run is not a pass).</p>"
             if compare_mode else "")
    return ("<h2>How to read this</h2><div class='panel'>" + intro +
            "<p><b>Risk</b> is about the latest state. <b>HIGH</b> = a high-risk problem is open (trackers firing "
            "without consent, wrong Osano config, broken page), or a high-risk check could not be judged. "
            "<b>MEDIUM</b> = medium problems, high-risk warnings, or any other check that could not be judged. "
            "<b>LOW</b> = everything judged and only low-risk problems, if any.</p>"
            "<p><b>How a run works:</b> each page is opened in a brand-new browser once per consent choice "
            "(no choice, accept, reject, analytics only, marketing only, personalization only, "
            "GPC 'do not sell' signal). The tool clicks only the consent banner, never a form.</p>"
            "<p><b>A leak</b> is a request, cookie or iframe from a category the visitor did not allow. "
            "Unknown third parties count as non-essential.</p>"
            "<p><b>NOT JUDGED</b> means the tool could not check it (page did not load, the banner button was not "
            "found, or Osano could not be read). It is never counted as a pass: a high-risk check that was not "
            "judged makes the risk HIGH, any other makes it at least MEDIUM, and the score is withheld.</p>"
            "<p><b>Score</b> = 100 minus the weighted share of checks that failed (high 5, medium 3, low 1; a "
            "warning counts half). Each check is counted once per page and consent choice. No score is shown "
            "when any check could not be judged.</p>"
            "<p><b>Counts</b> in the headline numbers are distinct tracking items — a host, a cookie or an iframe — "
            "per page, added up over pages. One analytics tag sending five hits is one item.</p></div>"
            "<details><summary>All checks and what they prove</summary>"
            + table(["ID", "Risk", "Check", "What it proves"], rows) + "</details>")


def render_run(run: dict) -> str:
    a = run["analysis"]
    k = a["metrics"]["kpis"]
    groups = group_findings(a["findings"])
    result = (_sample_note(run) + _run_hero(run, groups)
              + _numbers([(LABELS["pre_consent_violations"], k["pre_consent_violations"],
                           bool(k["pre_consent_violations"])),
                          (LABELS["reject_all_violations"], k["reject_all_violations"],
                           bool(k["reject_all_violations"])),
                          (LABELS["gpc_violations"], k["gpc_violations"], bool(k["gpc_violations"])),
                          (LABELS["broken_journeys"], k.get("broken_journeys"), bool(k.get("broken_journeys"))),
                          (LABELS["unclassified_items"], k["unclassified_items"], bool(k["unclassified_items"]))])
              + "<h2>Problems to fix</h2><p class='muted'>One row per problem, highest risk first. "
                "'Where' = the consent choices in which it happened.</p>"
              + _problems_table(groups, len(run["profile"]["scenarios"])) + _passed(groups))
    site = ("<h2>Leaks by page and consent choice</h2><p class='muted'>Number of items that fired although "
            "the visitor's choice did not allow them. Green = clean.</p>" + _matrix(run)
            + _consent_table(run) + _cookies(run) + _hosts(run) + _google_hits(run)
            + "<h2>Osano configuration</h2><p class='muted'>Scripts, cookies and iframes by Osano section. "
              "Amber and red cells need classifying.</p>" + _grid(a["metrics"].get("config_matrix"),
                                                                  a["metrics"].get("observed_matrix"))
            + _osano_items(run) + _speed(run) + _shots(run))
    m = run["meta"]
    r = risk(groups, [])
    tags = [(f"{r['level']} RISK", RISK_KIND[r["level"]]), (m["label"].upper(), "info")]
    if m.get("demo"):
        tags.append(("SAMPLE", "warn"))
    return page(f"Osano check — {m['display_name']}", m["run_id"], tags,
                [("result", "Result", result), ("site", "Consent, cookies & Osano", site),
                 ("read", "How to read", _how_to_read(False))])


# ------------------------------------------------------------------ compare report
def _scorecard(cmp: dict) -> str:
    rows = []
    for r in cmp["kpis"]:
        if r["before"] is None and r["after"] is None:
            continue
        d = r["direction"]
        fill = {"better": "f-good", "worse": "f-bad"}.get(d, "f-muted")
        change = {"better": "▲ better", "worse": "▼ worse", "same": "same", "n/a": "—"}[d]
        delta = f" ({'+' if (r['delta'] or 0) > 0 else ''}{_fmt(r['delta'])})" if r["delta"] not in (None, 0) else ""
        rows.append([esc(r["label"]), (esc(_fmt(r["before"])), "num"), (esc(_fmt(r["after"])), "num " + fill),
                     (esc(change + delta), fill)])
    return table(["Measure", "Before", "After", "Change"], rows)


def _status_cell(status: str, bad: int, total: int):
    label, fill = STATUS_FILL.get(status, (status, "f-muted"))
    if status in ("fail", "warn") and total > 1:
        label = f"{label} · {bad}/{total}"
    return (esc(label), fill)


def _problem_rows(rows: list[dict]) -> list[list]:
    out = []
    for r in rows:
        out.append([CHANGE_FILL[r["change"]], (SEV_LABEL[r["severity"]], SEV_FILL[r["severity"]]),
                    f"<b>{esc(PROBLEM[r['id']])}</b><br><span class='muted'>"
                    f"{'Was: ' if r['change'] == 'fixed' else ''}{esc(r['detail'])}</span>", esc(r["page"]),
                    _status_cell(r["before"], r["before_bad"], r["scenarios_total"]),
                    _status_cell(r["after"], r["after_bad"], r["scenarios_total"]),
                    evidence(r["evidence"], 10)])
    return out


def _consent_compare(before: dict, after: dict) -> str:
    from .scenarios import intended_consent
    b, a = consent_rows(before), consent_rows(after)
    rows = []
    for p in [p["id"] for p in after["profile"]["pages"]]:
        for s in after["profile"]["scenarios"]:
            db, da = b.get((p, s), {}), a.get((p, s), {})
            want = intended_consent(SCENARIOS[s])

            def rec(d):
                if not d or "error" in d:
                    return ("—", "f-muted")
                ok = (not want) or all(d["recorded"].get(k) == v for k, v in want.items())
                return (esc(_recorded_text(d["recorded"])), "f-good" if ok else "f-bad")

            def leaks(d):
                if not d or "error" in d:
                    return ("—", "f-muted")
                return (("not judged", "num f-info") if d["leaks"] is None else (str(d["leaks"]), "num " + ("f-bad" if d["leaks"] else "f-good")))

            def gcs(d):
                return esc(", ".join(d.get("gcs", [])) or "—") if d and "error" not in d else "—"
            rows.append([esc(p), esc(SCEN_SHORT[s]), rec(db), rec(da), gcs(db), gcs(da), leaks(db), leaks(da)])
    return ("<h2>Consent per page and choice — before vs after</h2><p class='muted'>Osano recorded = "
            "Osano.cm.getConsent() after reload. Red = Osano recorded something other than the visitor's choice, "
            "or items leaked.</p>"
            + table(["Page", "Choice", "Osano recorded — before", "Osano recorded — after", "Google gcs — before",
                     "Google gcs — after", "Leaks before", "Leaks after"], rows))


def _cookie_compare(before: dict, after: dict) -> str:
    def idx(run):
        return {it["key"]: it for it in run["analysis"]["metrics"]["inventory"] if it["kind"] == "cookie"}
    b, a = idx(before), idx(after)

    def state(it):
        if not it:
            return ("not set", "f-muted")
        if it["disallowed_in"]:
            choices = dict.fromkeys(e.split("/")[0] for e in it["disallowed_in"])
            return ("LEAKS in: " + esc(", ".join(SCEN_SHORT.get(s, s) for s in choices)), "f-bad")
        return ("only where allowed: " + esc(", ".join(SCEN_SHORT.get(s, s) for s in it["scenarios"])), "f-good")
    keys = sorted(set(b) | set(a), key=lambda k: (not (a.get(k) or {}).get("disallowed_in"),
                                                   not (b.get(k) or {}).get("disallowed_in"), k))
    rows = []
    for k in keys:
        it = a.get(k) or b.get(k)
        rows.append([f"<code>{esc(k)}</code>", f"<code>{esc(it.get('domain', ''))}</code>", esc(it["vendor"]),
                     tag(it["category"]), _osano_cell((b.get(k) or {}).get("config_section", "n/a")),
                     _osano_cell((a.get(k) or {}).get("config_section", "n/a")), state(b.get(k)), state(a.get(k))])
    return ("<h2>Every cookie — before vs after</h2><p class='muted'>Leaking cookies after the change first.</p>"
            + table(["Cookie", "Domain", "What it is", "Category", "Osano before", "Osano after", "Before", "After"],
                    rows, empty="No cookies in either run."))


def render_compare(before: dict, after: dict, cmp: dict) -> str:
    c, rk = cmp["counts"], cmp["risk"]
    ba = {r["key"]: r for r in cmp["kpis"]}
    headline = (f"{esc(cmp['verdict'].title())}: {c['fixed']} fixed, {c['new']} new, {c['still']} still open"
                + (f", {c['unjudged']} not judged now" if c.get("unjudged") else ""))
    lines = [esc(rk["why"]) + ".",
             f"Score {_fmt(ba['compliance_score']['before'])} → <b>{_fmt(ba['compliance_score']['after'])}</b> · "
             f"high-risk problems {_fmt(ba['issues_high']['before'])} → <b>{_fmt(ba['issues_high']['after'])}</b>."]
    warn = ""
    if not cmp["same_profile"] or not cmp["same_pages"]:
        warn = ('<div class="banner warn"><b>Not like-for-like:</b> the two runs used a different profile or '
                'page list.</div>')
    open_rows = [r for r in cmp["findings"] if r["change"] in ("new", "unjudged", "still", "stale")]
    fixed_rows = [r for r in cmp["findings"] if r["change"] == "fixed"]
    other_rows = [r for r in cmp["findings"] if r["change"] in ("judged", "gone")]
    unchanged_ok = sum(1 for r in cmp["findings"] if r["change"] == "ok")
    hdr = ["Result", "Risk", "Problem", "Page", "Before", "After", "Evidence"]
    fixed_block = (f"<details><summary><b>{len(fixed_rows)} problem(s) fixed</b></summary>"
                   + table(hdr, _problem_rows(fixed_rows)) + "</details>") if fixed_rows else ""
    if other_rows:
        # Not fixes: a check that only now could be judged, or one the after run no longer made.
        fixed_block += (f"<details><summary><b>{len(other_rows)} check(s) not comparable</b> — not judged before, "
                        "or not made after</summary>" + table(hdr, _problem_rows(other_rows)) + "</details>")
    main = (_sample_note(before, after) + _hero(rk["level"], headline, lines) + warn
            + f"<p class='muted'>Before: <code>{esc(before['meta']['run_id'])}</code> · "
              f"After: <code>{esc(after['meta']['run_id'])}</code> · {esc(after['meta']['display_name'])}</p>"
            + "<h2>Scorecard</h2>" + _scorecard(cmp)
            + "<h2>Still to fix after the change</h2><p class='muted'>New problems first. "
              "'FAIL · 5/7' = failed in 5 of 7 consent choices.</p>"
            + table(hdr, _problem_rows(open_rows), empty="Nothing open — every problem is fixed.")
            + fixed_block
            + (f"<p class='muted'>{unchanged_ok} other checks passed both times.</p>" if unchanged_ok else ""))

    inv_rows = []
    for r in sorted(cmp["inventory"], key=lambda r: (not r["leaks_after"], r["change"] != "added", r["key"])):
        if r["change"] == "added":
            label, fill = ("NEW ON SITE · LEAKS", "f-bad") if r["leaks_after"] else ("NEW ON SITE", "f-warn")
        elif r["change"] == "removed":
            label, fill = "REMOVED FROM SITE", "f-muted"
        elif r["leaks_before"] and not r["leaks_after"]:
            label, fill = "STOPPED LEAKING", "f-good"
        elif r["leaks_after"] and not r["leaks_before"]:
            label, fill = "STARTED LEAKING", "f-bad"
        elif r["category_before"] != r["category_after"]:
            label, fill = "CATEGORY CHANGED", "f-info"
        else:
            label, fill = f"MOVED IN OSANO ({r['config_before']} → {r['config_after']})", "f-info"
        leak_b = ("leaks", "f-bad") if r["leaks_before"] else ("clean", "f-good")
        leak_a = ("leaks", "f-bad") if r["leaks_after"] else ("clean", "f-good")
        if r["change"] == "removed":
            leak_a = ("—", "f-muted")
        if r["change"] == "added":
            leak_b = ("—", "f-muted")
        cat = (tag(r["category_after"] if r["change"] != "removed" else r["category_before"])
               if r["category_before"] in (r["category_after"], "-") or r["category_after"] == "-"
               else f"{tag(r['category_before'])} → {tag(r['category_after'])}")
        inv_rows.append([(esc(label), fill), f"<code>{esc(r['key'])}</code>", esc(r["vendor"]), cat, leak_b, leak_a])
    cb, ca = cmp["config_matrix_before"], cmp["config_matrix_after"]
    grid_rows = []
    if cb or ca:
        for t in osano_config.TYPES:
            cells = [f"<b>{esc(t.title())}s</b>"]
            for s, good_when in (("rules", "higher"), ("discovered", "lower"), ("ignored", None)):
                b = (cb or {}).get(t, {}).get(s, 0)
                a = (ca or {}).get(t, {}).get(s, 0)
                fill = "f-muted" if a == b or good_when is None else (
                    "f-good" if (a > b) == (good_when == "higher") else "f-bad")
                cells.append((f"{b} → {a}", "num " + fill))
            grid_rows.append(cells)
    cfg_rows = [[(esc(r["change"].upper()), {"added": "f-info", "removed": "f-muted", "moved": "f-info",
                                             "recategorised": "f-warn"}[r["change"]]),
                 esc(r["type"]), f"<code>{esc(r['match'])}</code>", esc(r["before"]), esc(r["after"])]
                for r in cmp["config_changes"]]
    what = (_consent_compare(before, after) + _cookie_compare(before, after)
            + "<h2>Third parties that appeared, disappeared or changed</h2><p class='muted'>Leaking items first. "
            "'leaks' = fired in at least one consent choice that did not allow it.</p>"
            + table(["Change", "Item", "What it is", "Category", "Before", "After"], inv_rows,
                    empty="No change in third parties.")
            + "<h2>Osano configuration</h2><p class='muted'>Item counts before → after. "
              "Green = moving the right way (more classified, fewer waiting).</p>"
            + table(["Type", "Classified (Rules)", "Waiting (Discovered)", "Ignored"], grid_rows,
                    empty="No Osano exports supplied for these runs.")
            + ("<details><summary>" + f"{len(cfg_rows)} Osano item(s) changed" + "</summary>"
               + table(["Change", "Type", "Match", "Before (section/category)", "After (section/category)"], cfg_rows)
               + "</details>" if cfg_rows else ""))
    tags = [(f"{rk['level']} RISK", RISK_KIND[rk["level"]]), (cmp["verdict"], VERDICT_KIND[cmp["verdict"]])]
    if before["meta"].get("demo") or after["meta"].get("demo"):
        tags.append(("SAMPLE", "warn"))
    return page(f"Osano before vs after — {after['meta']['display_name']}",
                f"{before['meta']['run_id']} → {after['meta']['run_id']}", tags,
                [("main", "Before vs After", main), ("what", "Consent, cookies & Osano", what),
                 ("read", "How to read", _how_to_read(True))])


# ------------------------------------------------------------------ index
def index_data() -> dict:
    """Machine-readable list of runs and comparisons, newest first (also written as index.json).
    Every run is re-analysed with the current rules, so the index never shows stale numbers;
    a file that is not a readable harness run is listed under 'skipped', never allowed to crash a run."""
    from .runs import reanalyse
    runs_out, comps, skipped = [], [], []
    for folder in sorted(RUNS.glob("*")) if RUNS.is_dir() else []:
        for f in folder.glob("*.json") if folder.is_dir() else []:
            try:
                run = reanalyse(json.loads(f.read_text(encoding="utf-8")))
                k = run["analysis"]["metrics"]["kpis"]
                r = risk(group_findings(run["analysis"]["findings"]), [])
                runs_out.append({"profile": run["meta"]["profile"], "display_name": run["meta"]["display_name"],
                                 "run_id": run["meta"]["run_id"], "label": run["meta"]["label"],
                                 "finished_utc": run["meta"]["finished_utc"], "risk": r["level"],
                                 "score": k["compliance_score"], "issues_high": k.get("issues_high"),
                                 "demo": bool(run["meta"].get("demo")),
                                 "report": f"{folder.name}/{run['meta']['run_id']}.html"})
            except Exception as exc:  # noqa: BLE001 — one bad file must not break every run's index
                skipped.append({"file": f"{folder.name}/{f.name}", "reason": type(exc).__name__})
    for f in REPORTS.glob("*/compare_*.json") if REPORTS.is_dir() else []:
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
            # Validate every field render_index reads, so one bad file can never break later runs.
            if not (isinstance(c, dict) and all(isinstance(c.get(k), str) for k in
                                                ("display_name", "before", "after", "verdict", "risk"))
                    and all(isinstance(c.get(k), (str, type(None))) for k in ("compared_utc", "after_finished_utc"))
                    and isinstance(c.get("counts"), dict)
                    and all(type(c["counts"].get(k)) is int for k in ("fixed", "new", "still"))):   # not bool
                raise ValueError("not a comparison summary")
            comps.append({**c, "report": f"{f.parent.name}/{f.stem}.html"})
        except Exception as exc:  # noqa: BLE001
            skipped.append({"file": f"{f.parent.name}/{f.name}", "reason": type(exc).__name__})
    runs_out.sort(key=lambda r: str(r["finished_utc"] or ""), reverse=True)        # str(): never a type clash
    comps.sort(key=lambda c: str(c.get("compared_utc") or c.get("after", "")), reverse=True)
    return {"runs": runs_out, "comparisons": comps, "skipped": skipped}


def render_index() -> str:
    data = index_data()
    comp_rows = [[(esc(c.get("risk", "?")), {"HIGH": "f-bad", "MEDIUM": "f-warn", "LOW": "f-good"}.get(c.get("risk"), "f-muted")),
                  esc(c["display_name"]), f'<a href="{esc(c["report"])}">{esc(c["before"])} → {esc(c["after"])}</a>',
                  esc(c["verdict"]), (str(c["counts"]["fixed"]), "num f-good"),
                  (str(c["counts"]["new"]), "num " + ("f-bad" if c["counts"]["new"] else "f-muted")),
                  (str(c["counts"]["still"]), "num " + ("f-warn" if c["counts"]["still"] else "f-muted"))]
                 for c in data["comparisons"]]
    run_rows = [[(esc(r["risk"]), {"HIGH": "f-bad", "MEDIUM": "f-warn", "LOW": "f-good"}.get(r["risk"], "f-muted")),
                 esc(r["display_name"]), esc(r["label"]), f'<a href="{esc(r["report"])}">{esc(r["run_id"])}</a>',
                 (_fmt(r["score"]), "num"), "sample" if r["demo"] else "live site"] for r in data["runs"]]
    body = ("<h2>Before vs after</h2>"
            + table(["Risk", "Property", "Runs", "Verdict", "Fixed", "New", "Still open"], comp_rows,
                    empty="No comparisons yet.")
            + "<h2>Single runs</h2>"
            + table(["Risk", "Property", "Label", "Run", "Score", "Source"], run_rows, empty="No runs yet."))
    return page("Osano checks", "all reports", [], [("index", "Reports", body), ("read", "How to read", _how_to_read(True))])


def write(path: Path, html_text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")
    return path
