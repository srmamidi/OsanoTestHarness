# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""Builds docs/production-handoff.html (living document — edit here, add a Version History entry, re-run)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from osano_harness.html_shell import esc, page, table  # noqa: E402

OUT = ROOT / "docs" / "production-handoff.html"


def code(text: str) -> str:
    return f"<pre><code>{esc(text)}</code></pre>"


def steps(items: list[str]) -> str:
    return "<ol>" + "".join(f"<li>{i}</li>" for i in items) + "</ol>"


def bullets(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


DIAGRAM = """
<svg class="chart" viewBox="0 0 900 250" role="img" aria-label="How the pieces connect">
 <defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
  <path d="M0,0 L10,5 L0,10 z" fill="var(--muted)"/></marker></defs>
 <g font-size="13" fill="var(--text)">
  <rect x="10" y="80" width="190" height="80" rx="10" fill="var(--panel)" stroke="var(--accent)" stroke-width="2"/>
  <text x="105" y="112" text-anchor="middle" font-weight="700">Ecom Control Center</text>
  <text x="105" y="132" text-anchor="middle" fill="var(--muted)">Run button + results page</text>
  <rect x="290" y="20" width="230" height="80" rx="10" fill="var(--panel)" stroke="var(--accent)" stroke-width="2"/>
  <text x="405" y="52" text-anchor="middle" font-weight="700">Azure DevOps pipeline</text>
  <text x="405" y="72" text-anchor="middle" fill="var(--muted)">before → pause → after → compare</text>
  <rect x="290" y="150" width="230" height="80" rx="10" fill="var(--panel)" stroke="var(--border)" stroke-width="2"/>
  <text x="405" y="182" text-anchor="middle" font-weight="700">Azure Storage (reports)</text>
  <text x="405" y="202" text-anchor="middle" fill="var(--muted)">HTML reports + summary JSON</text>
  <rect x="610" y="20" width="280" height="80" rx="10" fill="var(--panel)" stroke="var(--border)" stroke-width="2"/>
  <text x="750" y="52" text-anchor="middle" font-weight="700">Self-hosted Windows agent</text>
  <text x="750" y="72" text-anchor="middle" fill="var(--muted)">Python + Chromium, inside the network</text>
  <rect x="610" y="150" width="280" height="80" rx="10" fill="var(--panel)" stroke="var(--border)" stroke-width="2"/>
  <text x="750" y="182" text-anchor="middle" font-weight="700">Websites (prod + LLE)</text>
  <text x="750" y="202" text-anchor="middle" fill="var(--muted)">MVC apply flow, CMS marketing site</text>
 </g>
 <g stroke="var(--muted)" stroke-width="2" fill="none" marker-end="url(#a)">
  <path d="M200,100 L288,62"/><path d="M520,60 L608,60"/><path d="M750,100 L750,148"/>
  <path d="M405,100 L405,148"/><path d="M288,190 L202,140"/>
 </g>
 <g font-size="11" fill="var(--muted)">
  <text x="150" y="62">1. start run (REST)</text><text x="535" y="50">2. runs on</text>
  <text x="758" y="130">3. browses</text><text x="412" y="130">4. uploads</text><text x="150" y="215">5. reads + shows</text>
 </g>
</svg>
"""

summary = (
    "<h2>What this is</h2><div class='panel'><p>The Osano Test Harness opens each website page in a real browser, "
    "once for every consent choice a visitor can make (no choice, accept, reject, each category on its own, "
    "and the GPC 'do not sell' signal). It records every tracker, cookie and embedded frame, and checks them "
    "against the choice. Run it before and after every Osano change. It produces three reports: before, "
    "after, and a one-page before-vs-after comparison with a HIGH / MEDIUM / LOW risk rating.</p></div>"
    "<h2>Recommendation</h2><div class='banner good'><p><b>Run the harness as an Azure DevOps pipeline. Ecom "
    "Control Center starts that pipeline and shows the results.</b> Do not run the harness inside the "
    "Ecom Control Center web application.</p></div>"
    + table(["Option", "Good for", "Problems", "Verdict"], [
        ["<b>Local (a laptop)</b>", "Trying it out; investigating one problem",
         "Depends on one person and one machine; no history; easy to forget", ("Use for investigation only", "f-warn")],
        ["<b>Azure DevOps pipeline</b>",
         "Repeatable runs, a pause for the change, history of every run, nightly drift check, "
         "can block a bad change, audit trail of who ran it", "Needs a self-hosted Windows agent",
         ("Recommended — the engine", "f-good")],
        ["<b>Inside Ecom Control Center</b>",
         "One place for the team to look",
         "A browser run takes 2–10 minutes and hundreds of MB of memory — too long for a web request; "
         "Chromium under the IIS app-pool identity is fragile; widens what the web app can do on the network",
         ("Use as the front end only", "f-warn")],
    ]) + "<h2>How the pieces connect</h2>" + DIAGRAM
    + "<h2>Who does what</h2>" + table(["Role", "Responsibility"], [
        ["DevOps", "Agent, pipeline, storage, keeping Chromium and Python current"],
        ["Osano administrator", "Exports the Osano configuration before and after each change; approves the pause step"],
        ["Ecom Control Center developers", "Results page and Run button (Ecom Control Center tab)"],
        ["Marketing / analytics owners", "Know that harness runs send a small number of real analytics hits"],
    ])
)

local = (
    "<h2>Prerequisites</h2>" + bullets([
        "Windows 10/11 or Windows Server 2019+ with internet access to the sites being tested",
        "Python 3.12 or 3.13 (<code>py -0p</code> lists installed versions)",
        "About 600 MB of disk for the browser",
        "Network access to the LLE hosts (VPN if off-site)",
    ]) + "<h2>One-time setup</h2>" + steps([
        "Copy or clone the folder, e.g. <code>C:\\GitRepos-GraceAlone\\OsanoTestHarness</code>.",
        "<code>.\\scripts\\Invoke-OsanoHarness.ps1 -Action Setup</code> — creates <code>.venv</code>, installs "
        "pinned packages and Chromium.",
        "<code>.\\scripts\\Invoke-OsanoHarness.ps1 -Action Test</code> — must show all tests passing. "
        "The tests use the built-in demo site, so nothing leaves the machine.",
        "<code>.\\scripts\\Invoke-OsanoHarness.ps1 -Action Demo</code> — produces sample reports in "
        "<code>docs\\reports</code>. Open <code>docs\\reports\\index.html</code>.",
        "Fill <code>config\\profiles\\ace-prod.yaml</code> and <code>ace-lle.yaml</code>: Osano customer id and "
        "config id (from the <code>osano.js</code> URL), real page URLs, LLE hosts. The tool refuses to run while "
        "any <code>REPLACE-ME</code> is left.",
    ]) + "<h2>Every Osano change</h2>" + steps([
        "Export the Osano configuration (Osano MCP / REST) and normalise it:<br>"
        "<code>.venv\\Scripts\\python.exe -m osano_harness import-config --input raw.json --output "
        "config\\osano_exports\\prod-before.json</code>",
        "<code>.\\scripts\\Invoke-OsanoHarness.ps1 -Action Run -Profile ace-prod -Label before -OsanoConfig "
        "config\\osano_exports\\prod-before.json</code>",
        "Make and publish the change in Osano. Wait about 5 minutes for Osano's CDN.",
        "Export again, then run with <code>-Label after</code> and the new export.",
        "<code>.\\scripts\\Invoke-OsanoHarness.ps1 -Action Compare -Profile ace-prod</code> and open the "
        "compare report it prints.",
    ]) + "<h2>Where things land</h2>" + table(["Path", "Contents"], [
        ["<code>runs\\&lt;profile&gt;\\*.json</code>", "Raw data of each run (git-ignored for real sites)"],
        ["<code>docs\\reports\\&lt;profile&gt;\\*.html</code>", "Before / after / compare reports"],
        ["<code>docs\\reports\\index.html</code> / <code>index.json</code>", "List of everything, for people / for tools"],
    ]) + "<h2>When something goes wrong</h2>" + table(["Symptom", "Cause and fix"], [
        ["Problems marked <b>NOT JUDGED</b>", "The banner buttons changed. Inspect the banner and set "
         "<code>osano.selectors</code> in the profile."],
        ["Pages time out or show a challenge", "Akamai bot protection. Set <code>crawl.headless: false</code> or "
         "allow-list the <code>OsanoTestHarness/1.0</code> user agent."],
        ["'Wrong Osano configuration' everywhere", "Expected config id in the profile is wrong, or the page really "
         "loads the other property's config."],
        ["Looks stuck", "It is not printing. Each page × choice takes 3–20 s; check that files appear under "
         "<code>runs\\</code>."],
    ])
)

pipeline = (
    "<h2>What the pipeline does</h2>" + table(["Stage", "What happens"], [
        ["1. Before", "Sets up Python + Chromium, self-tests, probes every page × choice, publishes the BEFORE report"],
        ["2. Make the Osano change", "Pipeline pauses (up to 3 days). The Osano admin makes and publishes the "
         "change, then presses <b>Resume</b>"],
        ["3. After + compare", "Probes again, compares, publishes the reports. <b>Fails the run</b> when the change "
         "introduced a high-risk problem (default gate <code>new-high</code>)"],
        ["Nightly", "One run per night of the pipeline's default property, compared with that property's last "
         "nightly run (found by build tag). Catches drift: a tag added to the CMS, an Osano rule edited, a new "
         "vendor. For a nightly of the other property, copy the YAML with the other default and create a second "
         "pipeline."],
    ]) + "<h2>Set it up (one time)</h2>" + steps([
        "<b>Agent.</b> Create agent pool <code>Osano-Harness-Win</code> and register a self-hosted Windows agent "
        "on a server <i>inside</i> the network (LLE hosts are internal; Microsoft-hosted agents may be blocked by "
        "Akamai). Install Python 3.13 for all users. 2 vCPU / 4 GB RAM is enough.",
        "<b>Repo.</b> Push this folder to an Azure Repos repository (e.g. <code>OsanoTestHarness</code>).",
        "<b>Pipeline.</b> Pipelines → New → Azure Repos Git → Existing YAML → <code>/azure-pipelines.yml</code>.",
        "<b>Permissions.</b> Pipeline settings → allow it to use the agent pool. Restrict who can run it and who can "
        "approve the pause step (Osano administrators).",
        "<b>Profiles.</b> Commit the filled <code>ace-prod.yaml</code> / <code>ace-lle.yaml</code>. They hold no "
        "secrets.",
        "<b>Optional storage.</b> For Ecom Control Center: create a storage account with container "
        "<code>osano-reports</code>, an Azure Resource Manager service connection with <i>Storage Blob Data "
        "Contributor</i>, and set pipeline variables <code>publishToStorage=true</code>, "
        "<code>storageServiceConnection</code>, <code>storageAccount</code>.",
    ]) + "<h2>Running it</h2>" + table(["Parameter", "Meaning"], [
        ["<code>profile</code>", "<code>ace-prod</code> or <code>ace-lle</code> (one Osano property each)"],
        ["<code>mode</code>", "<code>before-after</code> (with the pause) or <code>single</code> (one run, no compare)"],
        ["<code>osanoConfigBefore/After</code>", "Repo path to the normalised Osano export (optional; without it the "
         "Osano-configuration checks are skipped)"],
        ["<code>failOn</code>", "<code>new-high</code> (default): fail if the change made a high-risk check fail "
         "or made it impossible to judge. <code>high-risk</code>: fail if the after state is HIGH risk — a "
         "high-risk problem is open, or a high-risk check could not be judged. <code>never</code>: report only"],
    ]) + "<h2>Exit codes</h2>" + table(["Code", "Meaning"], [
        ["0", "Done; gate passed"], ["2", "Profile, Osano export or run file missing or not usable (message says which)"],
        ["3", "Gate failed: open the compare report"], ["other", "The tool crashed — see the log"],
    ]) + "<h2>Files</h2>" + table(["File", "Purpose"], [
        ["<code>azure-pipelines.yml</code>", "Stages, schedule, parameters"],
        ["<code>pipelines/setup-steps.yml</code>", "Python, packages, Chromium, self-test"],
        ["<code>pipelines/publish-steps.yml</code>", "Artifacts (always, even on failure) and optional storage copy"],
    ])
)

ecc = (
    "<h2>Yes — integrate as the front end</h2><p>Ecom Control Center gets two features. It does not run "
    "browsers itself.</p>"
    "<h3>A. Results page (read-only)</h3>" + steps([
        "The pipeline copies reports to blob container <code>osano-reports</code> "
        "(<code>&lt;profile&gt;/compare_*.json</code> summaries and <code>*.html</code> reports).",
        "Ecom Control Center lists <code>*/compare_*.json</code> with the Azure Storage SDK (managed identity or "
        "service principal with <i>Storage Blob Data Reader</i>). Each summary has <code>risk</code>, "
        "<code>verdict</code> (IMPROVED / REGRESSED / MIXED / UNCHANGED / INCOMPLETE), <code>counts</code>, "
        "<code>compared_utc</code>, <code>before_finished_utc</code>, <code>after_finished_utc</code> and the "
        "scorecard numbers (a number can be <code>null</code> = not judged; show it as such, never as 0).",
        "Show a table: Risk (red / amber / green fill), property, date, fixed / new / still open, link to the report.",
        "Serve a report through a controller action that streams the blob with header "
        "<code>Content-Security-Policy: sandbox allow-scripts</code> — reports contain text taken from websites. "
        "It is escaped, but the sandbox keeps it from ever touching the Ecom Control Center session.",
    ]) + "<h3>B. Run button</h3>" + steps([
        "Ecom Control Center calls the Azure DevOps REST API: <code>POST https://dev.azure.com/{org}/{project}/"
        "_apis/pipelines/{pipelineId}/runs?api-version=7.1</code> with body "
        "<code>{\"templateParameters\": {\"profile\": \"ace-lle\", \"mode\": \"before-after\"}}</code>.",
        "Authenticate with a service principal / managed identity added to the Azure DevOps organisation, with "
        "only <i>queue builds</i> on this one pipeline. If a PAT is unavoidable: scope <i>Build (read &amp; "
        "execute)</i>, stored in Key Vault, rotated.",
        "Show the run link. Approving the pause step stays in Azure DevOps (it is audited there).",
        "Only Osano administrators see the button (Ecom Control Center role check, server side).",
    ]) + "<h3>Code sketch (C#, not compiled — adapt to the app's patterns)</h3>" + code(
        """// Results: list compare summaries
var container = new BlobContainerClient(new Uri(storageUrl + "/osano-reports"), new DefaultAzureCredential());
await foreach (var blob in container.GetBlobsAsync(prefix: profile + "/"))
    if (blob.Name.Contains("/compare_") && blob.Name.EndsWith(".json")) { /* download, deserialize, add to model */ }

// Report viewer: stream HTML in a sandbox
Response.Headers["Content-Security-Policy"] = "sandbox allow-scripts";
return File(await container.GetBlobClient(path).OpenReadAsync(), "text/html");   // path validated against the listing

// Run button: queue the pipeline (server side, after a role check)
var body = new { templateParameters = new { profile, mode = "before-after" } };
await http.PostAsJsonAsync($"https://dev.azure.com/{org}/{project}/_apis/pipelines/{id}/runs?api-version=7.1", body);""")
    + "<h3>Do not</h3>" + bullets([
        "Install Chromium or Python on the Ecom Control Center web servers.",
        "Pass a user-typed URL or blob path straight to storage — only names from the listing.",
        "Put the Azure DevOps credential in <code>web.config</code> — use Key Vault or managed identity.",
    ])
)

risks = (
    "<h2>Before the first real run</h2>" + table(["Item", "Owner", "Status"], [
        ["Production and LLE Osano customer id + config id", "Osano administrator", ("Open", "f-bad")],
        ["Exact path of apply step one (guessed /payday-lending/payday-loans/step/one)", "Ecom team", ("Open", "f-bad")],
        ["List of LLE hostnames to cover", "DevOps", ("Open", "f-bad")],
        ["US visitors get opt-in or opt-out? (first run reports it as check OSN-06)", "Osano administrator", ("Open", "f-warn")],
        ["Banner button selectors match the live banner (first run shows NOT JUDGED if not)", "DevOps", ("Open", "f-warn")],
        ["Shape of the Osano export from the MCP / REST call (adapt <code>import-config</code> if needed)",
         "Osano administrator", ("Open", "f-warn")],
        ["Analytics team informed about harness traffic", "Marketing", ("Open", "f-warn")],
        ["Akamai allow-list for the harness user agent, if challenged", "DevOps", ("If needed", "f-muted")],
        ["Hash-locked dependencies (<code>pip-compile --generate-hashes</code>) before production use", "DevOps",
         ("Open", "f-warn")],
    ]) + "<h2>Known limits</h2>" + bullets([
        "Results reflect the agent's location: Osano chooses the consent model by visitor region. Testing EU "
        "behaviour needs an agent or proxy in the EU.",
        "Accept-all runs send real hits to analytics and ad platforms (small volume).",
        "Timings are single lab samples — trust trends, not single numbers.",
        "The vendor catalog (<code>config/vendor_catalog.yaml</code>) decides what each third party really is; "
        "keep it in step with Osano.",
    ])
)

history = table(["Version", "Date", "Change"], [
    ["1.1", "2026-10-07", "After code review: risk is fail-closed (un-judged checks never read as safe), pipeline "
     "parameters can no longer inject code, nightly baseline found by build tag, storage step only when enabled, "
     "stricter profile and Osano-export validation, exit 2 for bad input files."],
    ["1.0", "2026-10-07", "First handoff: local setup, Azure DevOps pipeline with pause and gate, nightly drift "
     "check, Ecom Control Center integration design."],
])

html_text = page("Osano Test Harness — production handoff", "for DevOps, Osano admins and Ecom Control Center developers",
                 [("v1.1", "info"), ("Recommendation: pipeline", "good")],
                 [("summary", "Summary", summary), ("local", "Run locally", local),
                  ("pipeline", "Azure DevOps pipeline", pipeline), ("ecc", "Ecom Control Center", ecc),
                  ("risks", "Open items & limits", risks), ("history", "Version history", history)])
html_text = html_text.replace("</style>", "pre{background:var(--code-bg);padding:12px;border-radius:8px;"
                                          "overflow-x:auto;border:1px solid var(--border)}pre code{background:none}"
                                          "ol li,ul li{margin:6px 0}</style>", 1)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html_text, encoding="utf-8")
print(OUT)
