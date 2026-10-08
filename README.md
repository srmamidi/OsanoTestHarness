# Osano Test Harness

Measures what each website really does under every consent choice, saves it as a **run**, and compares a
**before** run with an **after** run. Built for Osano rollouts across many domains and environments,
with one Osano property for production and one for all lower environments (LLE).

Every time you change Osano you get three HTML reports, each with a HIGH / MEDIUM / LOW risk rating:

1. **before** report — problems to fix, one row per problem, with where it happens and how to fix it
2. **after** report — the same pages and checks after the change
3. **before vs after** report — one screen: risk, scorecard (before / after / change, colour-filled),
   problems still open (new ones first), then fixed problems; every section is expanded, nothing to click

Risk is fail-closed: a high-risk problem, or a high-risk check that could not be judged, is HIGH; medium
problems, high-risk warnings or any un-judged check are at least MEDIUM. When any check could not be judged
the score is left blank and the comparison verdict is INCOMPLETE.

`docs/reports/index.html` lists every run and comparison; `docs/reports/index.json` is the same list for
other tools. **Production setup, Azure DevOps pipeline and Ecom Control Center integration:**
`docs/production-handoff.html`.

Pipeline gates exit with code 3 when they fail: `run --fail-on high` (risk is HIGH), `run --fail-on errors`
(any check not judged), `compare --fail-on new-high` (the change made a high-risk check fail or
un-judgeable), `compare --fail-on high-risk` (after-state risk is HIGH). Exit 2 = unusable profile, Osano
export or run file (with a message); exit 1 = the tool crashed.

## Quick start

```powershell
.\scripts\Invoke-OsanoHarness.ps1 -Action Setup      # venv + Playwright Chromium
.\scripts\Invoke-OsanoHarness.ps1 -Action Demo       # sample reports from the built-in demo site
.\scripts\Invoke-OsanoHarness.ps1 -Action Test       # unit + end-to-end tests (offline)
```

The demo runs a local fake site (a CMS-style home page and an MVC-style "apply step one" page) on
`127.0.0.1:8770`. Every third-party request is answered by local stubs, so **nothing leaves the
machine** and no real site is touched. The demo reports are marked **SAMPLE DATA**.

## Real use (per Osano change)

1. Fill `config/profiles/ace-prod.yaml` and `ace-lle.yaml`: the expected Osano customer/config id
   (from the `osano.js` URL), real page URLs, and journey checks. The harness refuses to run while
   any `REPLACE-ME` is left, because a wrong expected config id would hide the "LLE page on prod config"
   check.
2. Export the Osano configuration (via your Osano MCP / REST calls) and normalise it:
   `python -m osano_harness import-config --input raw.json --output config/osano_exports/prod-before.json`
3. Run before the change:
   `.\scripts\Invoke-OsanoHarness.ps1 -Action Run -Profile ace-prod -Label before -OsanoConfig config\osano_exports\prod-before.json`
4. Make the Osano change and publish. Export the config again.
5. Run after the change: same command with `-Label after` and the new export.
6. Compare: `.\scripts\Invoke-OsanoHarness.ps1 -Action Compare -Profile ace-prod`

Repeat per profile (ace-lle). Add a profile per Osano property if you get more.

## What one run does

For each page × each consent choice, in a brand-new browser (no cookies):

| Moment | What is recorded |
| --- | --- |
| arrival | every request, cookie, iframe, script tag, localStorage key, Osano state, dataLayer, timings, screenshot |
| after the click | the same, plus what Osano says the choice was (`Osano.cm.getConsent()`) |
| after reload | the same, plus journey checks (form visible, autocomplete loaded…) |

Consent choices: no choice, accept all, reject all, analytics only, marketing only,
personalization only, Global Privacy Control signal.

The harness only clicks the consent banner. It never fills or submits a form.

## Checks (30)

| Group | What it catches |
| --- | --- |
| OSN | Osano missing, not first in `<head>`, wrong config for the environment (LLE on prod or prod on LLE), loaded twice, wrong mode (listener/permissive/strict), wrong consent model |
| BNR | banner not shown, click not applied (harness error, not a pass), banner returns after a choice, choice not stored |
| CNS | leaks before a choice, leaks after reject / partial choices (requests, cookies, iframes), unclassified items, over-blocking after Accept |
| GPC | Global Privacy Control not honoured |
| GCM | Google Consent Mode: default set after tags, wrong `gcs` for the choice, v2 signals (`gcd`) missing |
| FUN | page errors, broken journeys (essential script classified as non-essential), JS errors |
| CFG | (needs the Osano export) Osano category disagrees with reality, items left in Discovered, trackers in Ignored, same item in Rules and Ignored, essential item Ignored under Strict |

Unknown items count as **non-essential** (fail closed) — Osano Strict mode blocks them too.

## The 3 × 3 Osano grid

Osano keeps scripts, cookies and iframes, each in Rules (classified), Discovered (not classified) or
Ignored. The report shows that grid from the export, and a second grid of what the site **actually
loaded**, by the section Osano has it in — including items Osano does not know at all.

## Files

| Path | What it is |
| --- | --- |
| `osano_harness/probe.py` | Playwright browser recorder (raw facts only) |
| `osano_harness/analysis.py` | checks and metrics (pure function of the saved run) |
| `osano_harness/compare.py` | before vs after |
| `osano_harness/report.py`, `html_shell.py` | self-contained HTML reports (tabs, dark/light, Listen) |
| `osano_harness/osano_config.py` | Osano export normaliser, 3×3 grid, config diff |
| `osano_harness/google_consent.py` | `gcs` / `gcd` decoding, dataLayer order |
| `osano_harness/catalog.py` + `config/vendor_catalog.yaml` | what each third party really is |
| `osano_harness/demo/` | local demo site and stubs |
| `config/profiles/*.yaml` | one file per Osano property |
| `runs/<profile>/*.json` | raw run data (real-site runs are git-ignored) |
| `docs/reports/` | HTML reports |

## Things to know before running against real sites

- **Real hits.** Accept-all runs send real hits to your analytics and ad platforms. Volume is small
  (pages × 7 choices × 2–3 page loads); tell the analytics team, or filter the
  `OsanoTestHarness/1.0` user-agent suffix.
- **Bot protection.** Akamai may challenge a headless browser. Set `crawl.headless: false`, or ask for
  the harness to be allow-listed by user agent.
- **Banner selectors.** The default selectors are Osano's usual class names. If check BNR-02 shows
  NOT JUDGED, open the page, inspect the banner buttons, and set `osano.selectors` in the profile.
- **Location.** Osano picks the consent model by visitor location. The harness reports what it saw
  (OSN-06). To test another region, run it from a machine or VPN in that region.
- **Re-analysis.** `compare` re-analyses both runs with the current vendor catalog, so a catalog edit
  never makes a comparison unfair.
