# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""Saving and loading run snapshots (runs/<profile>/<run_id>.json)."""
from __future__ import annotations

import hashlib
import json
import platform
import re
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .analysis import analyse
from .catalog import DEFAULT_CATALOG, Catalog

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
REPORTS = ROOT / "docs" / "reports"


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id(label: str) -> str:
    # UTC: local time repeats an hour at the daylight-saving change, which would break run ordering.
    # ASCII only: str.isalnum() also accepts "é", "²", "Ⅻ", which check_ids() then rejects after a full probe.
    safe = "".join(ch for ch in label.lower() if ch in "abcdefghijklmnopqrstuvwxyz0123456789-")[:30] or "run"
    return f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}_{safe}"


def catalog_hash(path: Path = DEFAULT_CATALOG) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def build_run(profile: dict, label: str, observations: list[dict], osano_cfg: dict | None,
              started: str, notes: str = "") -> dict:
    run = {
        "meta": {"run_id": new_run_id(label), "label": label, "profile": profile["name"],
                 "display_name": profile["display_name"], "environment": profile["environment"],
                 "osano_property": profile.get("osano_property", ""), "started_utc": started,
                 "finished_utc": now_utc(), "harness_version": __version__,
                 "catalog_hash": catalog_hash(), "machine": platform.node(), "notes": notes,
                 "demo": bool(profile["network"].get("offline_demo"))},
        "profile": {k: v for k, v in profile.items() if not k.startswith("_")},
        "osano_config": osano_cfg,
        "observations": observations,
    }
    reanalyse(run)
    return run


def reanalyse(run: dict) -> dict:
    """(Re)compute checks and metrics with the CURRENT catalog, so compared runs use the same rules."""
    catalog = Catalog(DEFAULT_CATALOG, run["profile"]["first_party_domains"])
    run["analysis"] = analyse(run["profile"], run["observations"], run.get("osano_config"), catalog)
    run["meta"]["analysed_with_catalog"] = catalog_hash()
    return run


_PROFILE_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,40}")
# Device names Windows will not use as a folder ("runs\nul\x.json" fails).
WINDOWS_RESERVED = frozenset({"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                              *(f"lpt{i}" for i in range(1, 10))})
_RUN_ID_RE = re.compile(r"\d{8}-\d{6}_[a-z0-9-]{1,30}")


def check_ids(meta: dict) -> None:
    """profile and run_id become file paths: anything else could write outside runs/ or docs/reports/."""
    if not isinstance(meta, dict):
        raise ValueError("run meta is not an object")
    if not (isinstance(meta.get("profile"), str) and _PROFILE_RE.fullmatch(meta["profile"])
            and meta["profile"] not in WINDOWS_RESERVED):
        raise ValueError(f"run meta.profile is not a valid profile name: {meta.get('profile')!r}")
    if not (isinstance(meta.get("run_id"), str) and _RUN_ID_RE.fullmatch(meta["run_id"])):
        raise ValueError(f"run meta.run_id is not a valid run id: {meta.get('run_id')!r}")


def inside(path: Path, base: Path) -> Path:
    if not path.resolve().is_relative_to(base.resolve()):
        raise ValueError(f"refusing to write outside {base}: {path}")
    return path


def save(run: dict) -> Path:
    check_ids(run["meta"])
    folder = inside(RUNS / run["meta"]["profile"], RUNS)
    folder.mkdir(parents=True, exist_ok=True)
    path = inside(folder / f"{run['meta']['run_id']}.json", RUNS)
    path.write_text(json.dumps(run, indent=1, ensure_ascii=False, default=sorted), encoding="utf-8")
    return path


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def latest(profile: str, label: str | None = None, older_than: str | None = None) -> Path | None:
    """Newest run file for a label; with older_than (a run id), only runs strictly older than it."""
    folder = RUNS / profile
    files = sorted(folder.glob("*.json")) if folder.is_dir() else []
    if label:
        files = [f for f in files if f.stem.split("_", 1)[-1] == label]
    if older_than:
        files = [f for f in files if f.stem.split("_", 1)[0] < older_than.split("_", 1)[0]]
    return files[-1] if files else None
