# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
<#
.SYNOPSIS
  Runs the Osano test harness from Windows PowerShell 5.1.

.EXAMPLE
  .\scripts\Invoke-OsanoHarness.ps1 -Action Setup
  .\scripts\Invoke-OsanoHarness.ps1 -Action Run -Profile ace-prod -Label before -OsanoConfig config\osano_exports\prod-before.json
  .\scripts\Invoke-OsanoHarness.ps1 -Action Run -Profile ace-prod -Label after  -OsanoConfig config\osano_exports\prod-after.json
  .\scripts\Invoke-OsanoHarness.ps1 -Action Compare -Profile ace-prod
  .\scripts\Invoke-OsanoHarness.ps1 -Action Demo
  .\scripts\Invoke-OsanoHarness.ps1 -Action Test
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Setup', 'Run', 'Compare', 'Demo', 'Serve', 'Test')]
    [string]$Action,
    [Alias('Profile')]
    [string]$HarnessProfile,
    [string]$Label,
    [string]$OsanoConfig,
    [string]$Notes = '',
    [switch]$Headed
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root '.venv\Scripts\python.exe'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'

function Assert-Venv {
    if (-not (Test-Path $py)) {
        throw "No virtual environment at $py. Run: .\scripts\Invoke-OsanoHarness.ps1 -Action Setup"
    }
}

Push-Location $root
try {
    switch ($Action) {
        'Setup' {
            if (-not (Test-Path $py)) {
                # Any Python 3.12+: the launcher's newest 3.x first, then python on PATH.
                $made = $false
                if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv .venv; $made = ($LASTEXITCODE -eq 0) }
                if (-not $made -and (Get-Command python -ErrorAction SilentlyContinue)) { & python -m venv .venv; $made = ($LASTEXITCODE -eq 0) }
                if (-not $made) { throw 'No Python found. Install Python 3.12 or newer.' }
            }
            & $py -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
            if ($LASTEXITCODE -ne 0) { throw 'The .venv Python is older than 3.12. Delete .venv and install a newer Python.' }
            & $py -m pip install -r requirements.txt
            if ($LASTEXITCODE -ne 0) { throw "pip install failed ($LASTEXITCODE)" }
            & $py -m playwright install chromium
            if ($LASTEXITCODE -ne 0) { throw "Chromium install failed ($LASTEXITCODE)" }
        }
        'Run' {
            Assert-Venv
            if (-not $HarnessProfile -or -not $Label) { throw 'Run needs -Profile and -Label (before / after).' }
            $argList = @('-m', 'osano_harness', 'run', '--profile', $HarnessProfile, '--label', $Label)
            if ($OsanoConfig) { $argList += @('--osano-config', $OsanoConfig) }
            if ($Notes) { $argList += @('--notes', $Notes) }
            if ($Headed) { $argList += '--headed' }
            & $py @argList
        }
        'Compare' {
            Assert-Venv
            if (-not $HarnessProfile) { throw 'Compare needs -Profile.' }
            & $py -m osano_harness compare --profile $HarnessProfile
        }
        'Demo'    { Assert-Venv; & $py -m osano_harness demo }
        'Serve'   { Assert-Venv; & $py -m osano_harness serve }
        'Test'    { Assert-Venv; & $py -m pytest tests -q }
    }
    if ($LASTEXITCODE -ne 0) { throw "Harness exited with code $LASTEXITCODE" }
    $reports = Join-Path $root 'docs\reports'
    if (Test-Path $reports) {
        Get-ChildItem $reports -Recurse -Filter *.html | Unblock-File
    }
}
finally {
    Pop-Location
}

