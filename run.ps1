<#
.SYNOPSIS
  Counter-PC launcher: installs, builds the web app and serves everything on one port.

.DESCRIPTION
  Verifies Python 3.12 (through uv) and Node 24+, syncs the backend, installs and builds the web
  app, then starts the backend with SERVE_WEB=1 so the same process serves the UI and /api.
  An API key is optional: without one the app runs in OFFLINE mode (calculators and keyword search).

.PARAMETER SkipBuild
  Reuse an existing web/build (skips npm ci and the web build).

.PARAMETER Port
  Port to listen on (default 8000). Only 127.0.0.1 is bound.
#>
param(
  [switch]$SkipBuild,
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Fail([string]$message) {
  Write-Host ""
  Write-Host "ERROR: $message" -ForegroundColor Red
  exit 1
}

function Step([string]$message) {
  Write-Host ""
  Write-Host "==> $message" -ForegroundColor Cyan
}

# -- prerequisites ---------------------------------------------------------------------------

Step "Checking prerequisites"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Fail "uv is not installed. Install it from https://docs.astral.sh/uv/ and run this script again."
}

# uv manages Python: the backend pins 3.12 (backend/.python-version). Fetch it if it is missing.
$python = & uv python find 3.12 2>$null
if ($LASTEXITCODE -ne 0 -or -not $python) {
  Write-Host "Python 3.12 not found; asking uv to install it..."
  & uv python install 3.12
  if ($LASTEXITCODE -ne 0) { Fail "Could not install Python 3.12 with uv." }
  $python = & uv python find 3.12
}
Write-Host "Python 3.12: $python"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Fail "Node.js is not installed. Install Node 24 or newer from https://nodejs.org/ and run this script again."
}
$nodeVersion = (& node --version).TrimStart("v")
if ([int]($nodeVersion.Split(".")[0]) -lt 24) {
  Fail "Node $nodeVersion found; Node 24 or newer is required."
}
Write-Host "Node: v$nodeVersion"

# -- configuration ---------------------------------------------------------------------------

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env from .env.example. Add CEREBRAS_API_KEY and ANTHROPIC_API_KEY to it for LIVE mode;"
  Write-Host "without them the app runs in OFFLINE mode (calculators and keyword search, no model)."
}

# -- install and build -----------------------------------------------------------------------

Step "Installing the backend (uv sync)"
& uv --directory backend sync
if ($LASTEXITCODE -ne 0) { Fail "uv sync failed." }

if ($SkipBuild -and (Test-Path "web/build/index.html")) {
  Write-Host "Skipping the web build (web/build already exists)."
} else {
  Step "Installing the web app (npm ci)"
  & npm ci --prefix web --no-audit --no-fund
  if ($LASTEXITCODE -ne 0) { Fail "npm ci failed." }

  Step "Building the web app"
  & npm run build --prefix web
  if ($LASTEXITCODE -ne 0) { Fail "The web build failed." }
}
if (-not (Test-Path "web/build/index.html")) { Fail "web/build/index.html is missing after the build." }

# -- run -------------------------------------------------------------------------------------

$env:SERVE_WEB = "1"

Step "Starting Bhumi Vikas Sahayak"
Write-Host ""
Write-Host "  Open  http://127.0.0.1:$Port  in your browser." -ForegroundColor Green
Write-Host "  Stop with Ctrl+C. Prototype, not legal advice."
Write-Host ""

& uv --directory backend run uvicorn app.main:app --host 127.0.0.1 --port $Port
