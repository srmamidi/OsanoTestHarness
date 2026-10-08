# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""Command line:

  python -m osano_harness run      --profile ace-prod --label before [--osano-config export.json]
  python -m osano_harness run      --profile ace-prod --label after  [--osano-config export.json]
  python -m osano_harness compare  --profile ace-prod                (latest before vs latest after)
  python -m osano_harness demo                                       (sample reports from the local demo site)
  python -m osano_harness serve                                      (browse docs/reports on http://127.0.0.1:8780)
  python -m osano_harness import-config --input raw.json --output config/osano_exports/x.json
  python -m osano_harness report   --run runs/<profile>/<id>.json    (re-render with the current catalog)
  python -m osano_harness index
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import osano_config, report, runs
from .compare import compare as do_compare
from .profile import ProfileError, load_profile


def _write_run_report(run: dict) -> Path:
    try:
        runs.check_ids(run["meta"])
        path = runs.inside(runs.REPORTS / run["meta"]["profile"] / f"{run['meta']['run_id']}.html", runs.REPORTS)
    except ValueError as exc:
        raise UsageError(str(exc)) from None
    return report.write(path, report.render_run(run))


def _write_index() -> Path:
    # index.json is the integration point for other tools (pipeline summary, Ecom Control Center).
    (runs.REPORTS / "index.json").parent.mkdir(parents=True, exist_ok=True)
    (runs.REPORTS / "index.json").write_text(json.dumps(report.index_data(), indent=1), encoding="utf-8")
    return report.write(runs.REPORTS / "index.html", report.render_index())


GATE_EXIT = 3   # distinct from 1 (crash) and 2 (bad profile/config) so pipelines can tell them apart


class UsageError(Exception):
    """Bad input file or missing runs: exit 2 with a message, never a traceback."""


def _load_json(path, what: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise UsageError(f"{what} not found: {path}") from None
    except (OSError, ValueError) as exc:
        raise UsageError(f"{what} is not readable JSON: {path} ({type(exc).__name__})") from None


def _gate_run(run: dict, fail_on: str) -> int:
    from .analysis import group_findings
    from .compare import risk
    k = run["analysis"]["metrics"]["kpis"]
    r = risk(group_findings(run["analysis"]["findings"]), [])
    if fail_on == "high" and r["level"] == "HIGH":
        print(f"GATE FAILED: risk is HIGH — {r['why']} (--fail-on high)")
        return GATE_EXIT
    if fail_on == "errors" and k.get("checks_error"):
        print(f"GATE FAILED: {k['checks_error']} check(s) could not be judged (--fail-on {fail_on})")
        return GATE_EXIT
    return 0


def _gate_compare(cmp: dict, fail_on: str) -> int:
    new_high = [r for r in cmp["findings"] if r["change"] == "new" and r["severity"] == "high"]
    # pass -> NOT JUDGED also fails the gate: a high-risk check nobody could run is not a pass.
    lost_high = [r for r in cmp["findings"] if r["change"] == "unjudged" and r["severity"] == "high"]
    if fail_on == "new-high" and (new_high or lost_high):
        parts = ([f"the change introduced {len(new_high)} high-risk problem(s)"] if new_high else []) + \
                ([f"{len(lost_high)} high-risk check(s) could not be judged in the after run"] if lost_high else [])
        print(f"GATE FAILED: {'; '.join(parts)} (--fail-on new-high)")
        return GATE_EXIT
    if fail_on == "high-risk" and cmp["risk"]["level"] == "HIGH":
        print(f"GATE FAILED: after-state risk is HIGH — {cmp['risk']['why']} (--fail-on high-risk)")
        return GATE_EXIT
    return 0


def cmd_run(args, *, router=None, osano_cfg=None) -> Path:
    prof = load_profile(args.profile, allow_placeholders=getattr(args, "allow_placeholders", False))
    if getattr(args, "headed", False):
        prof["crawl"]["headless"] = False
    demo_port = getattr(args, "demo_port", None)
    if demo_port and prof["network"].get("offline_demo"):
        for page in prof["pages"]:     # demo profiles are written for :8770
            page["url"] = page["url"].replace("127.0.0.1:8770", f"127.0.0.1:{demo_port}")
    if osano_cfg is None and getattr(args, "osano_config", None):
        osano_cfg = osano_config.normalize(_load_json(args.osano_config, "Osano export"),
                                           source=str(args.osano_config))
    if prof["network"].get("offline_demo") and router is None:
        from .demo.vendors import route_handler
        router = route_handler
    try:   # refuse an unusable label BEFORE a several-minute probe, not after it
        runs.check_ids({"profile": prof["name"], "run_id": runs.new_run_id(args.label)})
    except ValueError as exc:
        raise UsageError(str(exc)) from None
    from .probe import run_probe
    started = runs.now_utc()
    print(f"Run '{args.label}' for {prof['display_name']}: {len(prof['pages'])} pages x "
          f"{len(prof['scenarios'])} consent choices")
    observations = run_probe(prof, router=router)
    run = runs.build_run(prof, args.label, observations, osano_cfg, started, getattr(args, "notes", "") or "")
    json_path = runs.save(run)
    html_path = _write_run_report(run)
    _write_index()
    k = run["analysis"]["metrics"]["kpis"]
    def show(v):
        return "-" if v is None else v
    print(f"  score {show(k['compliance_score'])}  problems {show(k['issues_total'])} "
          f"({show(k['issues_high'])} high-risk)  not judged {k['checks_error']}")
    print(f"  data   {json_path}\n  report {html_path}")
    return _gate_run(run, getattr(args, "fail_on", "never") or "never")


def cmd_compare(args) -> Path:
    after_p = Path(args.after) if args.after else runs.latest(args.profile, "after")
    # The newest "before" that is OLDER than the chosen "after" — never a later before-run.
    before_p = Path(args.before) if args.before else runs.latest(
        args.profile, "before", older_than=after_p.stem if after_p else None)
    if not before_p or not after_p:
        raise UsageError(f"Need a 'before' run older than an 'after' run for profile {args.profile} "
                         f"(found before={before_p}, after={after_p}). Pass --before/--after to choose files.")
    before, after = _load_json(before_p, "before run"), _load_json(after_p, "after run")
    for name, r in (("before", before), ("after", after)):
        if not isinstance(r, dict) or "observations" not in r or "profile" not in r \
                or not isinstance(r.get("meta"), dict):
            raise UsageError(f"{name} file is not a harness run: {before_p if name == 'before' else after_p}")
    try:                                   # ids become output file names
        runs.check_ids(before["meta"])
        runs.check_ids(after["meta"])
    except ValueError as exc:
        raise UsageError(str(exc)) from None
    if not args.before and not args.after and before["meta"]["run_id"] >= after["meta"]["run_id"]:
        raise UsageError("The 'before' run is not older than the 'after' run")
    # Same rules for both sides: re-analyse with the current catalog before comparing.
    runs.reanalyse(before)
    runs.reanalyse(after)
    cmp = do_compare(before, after)
    folder = runs.REPORTS / after["meta"]["profile"]
    stem = f"compare_{before['meta']['run_id']}_vs_{after['meta']['run_id']}"
    html_path = report.write(folder / f"{stem}.html", report.render_compare(before, after, cmp))
    summary = {"display_name": after["meta"]["display_name"], "profile": after["meta"]["profile"],
               "before": before["meta"]["run_id"], "after": after["meta"]["run_id"],
               "before_finished_utc": before["meta"].get("finished_utc"),
               "after_finished_utc": after["meta"].get("finished_utc"), "compared_utc": runs.now_utc(),
               "verdict": cmp["verdict"], "risk": cmp["risk"]["level"], "risk_reason": cmp["risk"]["why"],
               "counts": cmp["counts"],
               "kpis": {r["key"]: {"before": r["before"], "after": r["after"], "direction": r["direction"]}
                        for r in cmp["kpis"]}}
    (folder / f"{stem}.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    _write_index()
    print(f"Risk {cmp['risk']['level']} · {cmp['verdict']}: fixed {cmp['counts']['fixed']}  "
          f"new {cmp['counts']['new']}  still open {cmp['counts']['still']}")
    print(f"  report {html_path}")
    return _gate_compare(cmp, getattr(args, "fail_on", "never") or "never")


def cmd_demo(args) -> None:
    from .demo.site import DemoServer
    from .demo.vendors import route_handler
    exports = runs.ROOT / "config" / "osano_exports"
    with DemoServer(args.port) as srv:
        for variant in ("before", "after"):
            srv.set_variant(variant)
            for prof_name in ("demo-prod", "demo-lle"):
                cfg = osano_config.load(exports / f"demo-prod-{variant}.json")
                if prof_name == "demo-lle":
                    cfg["property"] = "demo-lle"
                    cfg["source"] = cfg["source"].replace("before", "before (LLE)").replace("after", "after (LLE)")
                ns = argparse.Namespace(profile=prof_name, label=variant, headed=False, allow_placeholders=False,
                                        demo_port=args.port,
                                        notes=("Demo site, first-pass Osano setup" if variant == "before"
                                               else "Demo site after the Osano clean-up change"))
                cmd_run(ns, router=route_handler, osano_cfg=cfg)
    for prof_name in ("demo-prod", "demo-lle"):
        cmd_compare(argparse.Namespace(profile=prof_name, before=None, after=None))
    print(f"\nOpen {runs.REPORTS / 'index.html'}")


def cmd_serve(args) -> None:
    import functools
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(runs.REPORTS))
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Serving {runs.REPORTS} on http://127.0.0.1:{args.port}/index.html  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


def cmd_import(args) -> None:
    norm = osano_config.normalize(_load_json(args.input, "Osano export"), source=args.input)
    if args.property:
        norm["property"] = args.property
    if args.captured_at:
        norm["captured_at"] = args.captured_at
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(norm, indent=1), encoding="utf-8")
    grid = osano_config.matrix(norm)
    print(f"Wrote {args.output}: " + ", ".join(f"{t}s {grid[t]}" for t in osano_config.TYPES))


def cmd_report(args) -> None:
    run = _load_json(args.run, "run")
    if not isinstance(run, dict) or not all(k in run for k in ("observations", "profile", "meta")) \
            or not isinstance(run["meta"], dict):
        raise UsageError(f"not a harness run file: {args.run}")
    run = runs.reanalyse(run)
    # Refresh the stored analysis only for this harness's own history — never copy an outside file into it.
    if Path(args.run).resolve().is_relative_to(runs.RUNS.resolve()):
        try:
            runs.save(run)
        except ValueError as exc:
            raise UsageError(str(exc)) from None
    print(_write_run_report(run))
    _write_index()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="osano_harness", description="Osano consent before/after test harness")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="probe a profile and write a run report")
    r.add_argument("--profile", required=True)
    r.add_argument("--label", required=True, help="before | after | any short word")
    r.add_argument("--osano-config", help="normalised Osano export for this moment (see import-config)")
    r.add_argument("--notes", default="")
    r.add_argument("--headed", action="store_true", help="show the browser")
    r.add_argument("--allow-placeholders", action="store_true",
                   help="dry-run a profile that still has REPLACE-ME ids (OSN-03 results are then meaningless)")
    r.add_argument("--fail-on", choices=("never", "high", "errors"), default="never",
                   help=f"exit {GATE_EXIT} when risk is HIGH (high problems or high checks not judged), "
                        "or with 'errors' when any check could not be judged — for pipelines")
    c = sub.add_parser("compare", help="compare a before run with an after run")
    c.add_argument("--profile", required=True)
    c.add_argument("--before")
    c.add_argument("--after")
    c.add_argument("--fail-on", choices=("never", "new-high", "high-risk"), default="never",
                   help=f"exit {GATE_EXIT} when the change adds a high-risk problem, or the after state is HIGH risk")
    d = sub.add_parser("demo", help="produce sample reports from the built-in demo site")
    d.add_argument("--port", type=int, default=8770)
    s = sub.add_parser("serve", help="serve docs/reports locally")
    s.add_argument("--port", type=int, default=8780)
    i = sub.add_parser("import-config", help="normalise an Osano config export")
    i.add_argument("--input", required=True)
    i.add_argument("--output", required=True)
    i.add_argument("--property")
    i.add_argument("--captured-at")
    rp = sub.add_parser("report", help="re-render a saved run")
    rp.add_argument("--run", required=True)
    sub.add_parser("index", help="rebuild docs/reports/index.html")
    args = p.parse_args(argv)
    try:
        if args.cmd == "run":
            return cmd_run(args)
        elif args.cmd == "compare":
            return cmd_compare(args)
        elif args.cmd == "demo":
            cmd_demo(args)
        elif args.cmd == "serve":
            cmd_serve(args)
        elif args.cmd == "import-config":
            cmd_import(args)
        elif args.cmd == "report":
            cmd_report(args)
        elif args.cmd == "index":
            print(_write_index())
    except (ProfileError, osano_config.ConfigError, UsageError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0
