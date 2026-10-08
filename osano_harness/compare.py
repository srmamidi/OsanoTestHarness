# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""Before vs after, at the level a reader cares about: one row per problem (check x page), a short
scorecard, a single risk rating, and what changed on the site and in Osano."""
from __future__ import annotations

from . import osano_config
from .analysis import group_findings

# (key, label, better) — the scorecard. better: "lower" | "higher".
# One wording for each headline number, shared by the run and compare reports.
LABELS = {
    "pre_consent_violations": "Tracking items (hosts, cookies, iframes) active before the visitor chooses",
    "reject_all_violations": "Tracking items active after \"Reject all\"",
    "gpc_violations": "Tracking items active with GPC \"Do not sell\" on",
    "broken_journeys": "Page functions broken by consent blocking",
    "unclassified_items": "Unknown third parties (hosts and cookies)",
}

KPI_SPEC = (
    ("compliance_score", "Compliance score (out of 100; blank when checks were not judged)", "higher"),
    ("issues_high", "High-risk problems", "lower"),
    ("issues_total", "All problems", "lower"),
    ("pre_consent_violations", LABELS["pre_consent_violations"], "lower"),
    ("reject_all_violations", LABELS["reject_all_violations"], "lower"),
    ("gpc_violations", LABELS["gpc_violations"], "lower"),
    ("broken_journeys", LABELS["broken_journeys"], "lower"),
    ("unclassified_items", LABELS["unclassified_items"], "lower"),
    ("osano_unclassified", "Items waiting for classification in Osano", "lower"),
    ("avg_load_ms", "Average page load (ms)", "lower"),
)
# Timing noise: a page-load change smaller than this share is "same".
PERF_TOLERANCE = 0.10
_PERF_KEYS = {"avg_load_ms", "avg_lcp_ms", "avg_transfer_kb", "avg_osano_script_ms", "avg_cls"}
BAD = ("fail", "warn", "error")


def _direction(key, before, after, better) -> str:
    if before is None or after is None:
        return "n/a"
    if before == after:
        return "same"
    if key in _PERF_KEYS and before and abs(after - before) / abs(before) < PERF_TOLERANCE:
        return "same"
    improved = after > before if better == "higher" else after < before
    return "better" if improved else "worse"


def _change(bs: str, as_: str) -> str:
    if bs == "error" and as_ == "pass":
        return "judged"      # could not be checked before — not evidence of a fix
    if bs in BAD and as_ == "pass":
        return "fixed"
    if bs in ("pass", "na", "absent") and as_ == "error":
        return "unjudged"    # was fine, now could not be checked — not proof of a problem, not proof of none
    if bs in ("pass", "na", "absent") and as_ in BAD:
        return "new"
    if bs == "error" and as_ in ("fail", "warn"):
        return "new"         # could not be checked before: it cannot be shown to be pre-existing
    if bs in ("fail", "warn") and as_ == "error":
        return "stale"       # failed before, not checked after: still treated as open, never as fixed
    if bs in BAD and as_ in BAD:
        return "still"
    if bs in BAD:
        return "gone"
    return "ok"


def risk(after_groups: list[dict], new_rows: list[dict]) -> dict:
    """Risk of the latest state. Fail closed: what could not be judged is never LOW.
    HIGH   = a high-severity problem is open, or a high-severity check could not be judged
    MEDIUM = medium problems, high-severity warnings, or any check that could not be judged
    LOW    = everything judged and nothing above low severity open."""
    open_high = [g for g in after_groups if g["status"] == "fail" and g["severity"] == "high"]
    err_high = [g for g in after_groups if g["status"] == "error" and g["severity"] == "high"]
    open_med = [g for g in after_groups if g["status"] in ("fail", "warn") and g["severity"] in ("medium", "high")]
    errors = [g for g in after_groups if g["status"] == "error"]
    new_high = [r for r in new_rows if r["severity"] == "high" and r["after"] == "fail"]
    judged = [g for g in after_groups if g["status"] in ("pass", "fail", "warn")]
    open_low = [g for g in after_groups if g["status"] in ("fail", "warn") and g["severity"] in ("low", "info")]
    if open_high:
        level = "HIGH"
    elif err_high or not judged:
        level = "HIGH"
    elif open_med or errors:
        level = "MEDIUM"
    else:
        level = "LOW"
    # The reason names everything that is open or unknown, whatever decided the level.
    parts = []
    if not judged:
        parts.append("nothing could be judged")
    if open_high:
        parts.append(f"{len(open_high)} high-risk problem(s) open"
                     + (f", {len(new_high)} of them introduced by the change" if new_high else ""))
    if err_high:
        parts.append(f"{len(err_high)} high-risk check(s) could not be judged — the result cannot be trusted")
    med_only = [g for g in open_med if g not in open_high]
    if med_only:
        parts.append(f"{len(med_only)} medium-risk problem(s) or high-risk warning(s) open")
    if open_low:
        parts.append(f"{len(open_low)} low-risk problem(s) open")
    other_err = len(errors) - len(err_high)
    if other_err > 0 and judged:
        parts.append(f"{other_err} other check(s) not judged — fix and re-run")
    return {"level": level, "why": "; ".join(parts) if parts else "no problems open, everything judged"}


def compare(before: dict, after: dict) -> dict:
    bk, ak = before["analysis"]["metrics"]["kpis"], after["analysis"]["metrics"]["kpis"]
    kpis = []
    for key, label, better in KPI_SPEC:
        b, a = bk.get(key), ak.get(key)
        delta = round(a - b, 1) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None
        kpis.append({"key": key, "label": label, "before": b, "after": a, "delta": delta,
                     "direction": _direction(key, b, a, better)})

    bg = {(g["id"], g["page"]): g for g in group_findings(before["analysis"]["findings"])}
    ag = {(g["id"], g["page"]): g for g in group_findings(after["analysis"]["findings"])}
    rows = []
    for key in set(bg) | set(ag):
        b, a = bg.get(key), ag.get(key)
        bs, as_ = (b or {}).get("status", "absent"), (a or {}).get("status", "absent")
        g = a or b
        rows.append({"id": key[0], "page": key[1], "title": g["title"], "severity": g["severity"],
                     "before": bs, "after": as_, "change": _change(bs, as_),
                     "before_bad": len((b or {}).get("scenarios_bad", [])),
                     "after_bad": len((a or {}).get("scenarios_bad", [])),
                     "scenarios_total": len((a or b)["scenarios_all"]),
                     # A fixed problem is described by what was wrong BEFORE; anything open by its state AFTER.
                     "detail": ((b or {}).get("detail", "") if as_ == "pass"
                                else (a or {}).get("detail") or (b or {}).get("detail", "")),
                     "evidence": ((b or {}).get("evidence", []) if as_ == "pass"
                                  else (a or {}).get("evidence") or (b or {}).get("evidence", []))})
    order = {"new": 0, "unjudged": 1, "still": 2, "stale": 3, "fixed": 4, "judged": 5, "gone": 6, "ok": 7}
    sev = {"high": 0, "medium": 1, "low": 2, "info": 3}
    rows.sort(key=lambda r: (order[r["change"]], sev[r["severity"]], r["id"], r["page"]))

    def inv_index(run):
        return {(r["kind"], r["key"], r.get("vendor_id", r["vendor"])): r
                for r in run["analysis"]["metrics"]["inventory"]}
    bi, ai = inv_index(before), inv_index(after)
    inventory = []
    for key in sorted(set(bi) | set(ai)):
        b, a = bi.get(key), ai.get(key)
        if key[0] == "storage":
            continue
        if b and not a:
            change = "removed"
        elif a and not b:
            change = "added"
        elif (b["category"], b["config_section"], bool(b["disallowed_in"])) != \
             (a["category"], a["config_section"], bool(a["disallowed_in"])):
            change = "changed"
        else:
            continue
        r = a or b
        inventory.append({"kind": key[0], "key": key[1], "change": change, "vendor": r["vendor"],
                          "category_before": (b or {}).get("category", "-"),
                          "category_after": (a or {}).get("category", "-"),
                          "config_before": (b or {}).get("config_section", "-"),
                          "config_after": (a or {}).get("config_section", "-"),
                          "leaks_before": bool((b or {}).get("disallowed_in")),
                          "leaks_after": bool((a or {}).get("disallowed_in"))})

    counts = {c: sum(1 for r in rows if r["change"] == c) for c in ("fixed", "new", "still", "stale", "gone", "judged", "unjudged")}
    new_serious = [r for r in rows if r["change"] == "new" and r["severity"] in ("high", "medium")
                   and r["after"] == "fail"]
    if new_serious and counts["fixed"]:
        verdict = "MIXED"
    elif new_serious:
        verdict = "REGRESSED"
    elif counts["fixed"]:
        verdict = "IMPROVED"
    else:
        verdict = "UNCHANGED"
    # A high-risk check the AFTER run could not judge means the change cannot be called better or the same.
    if any(g["status"] == "error" and g["severity"] == "high" for g in ag.values()):
        verdict = "INCOMPLETE"
    return {"verdict": verdict, "risk": risk(list(ag.values()), [r for r in rows if r["change"] == "new"]),
            "counts": counts, "new_serious": len(new_serious), "kpis": kpis, "findings": rows,
            "inventory": inventory,
            "config_changes": osano_config.diff(before.get("osano_config"), after.get("osano_config")),
            "config_matrix_before": before["analysis"]["metrics"].get("config_matrix"),
            "config_matrix_after": after["analysis"]["metrics"].get("config_matrix"),
            "same_profile": before["meta"]["profile"] == after["meta"]["profile"],
            "same_pages": [p["id"] for p in before["profile"]["pages"]] == [p["id"] for p in after["profile"]["pages"]]}
