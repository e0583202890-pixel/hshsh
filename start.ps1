# ============================================================
#  KICKLIPS Studio - one-click launcher (single server)
#  Builds the app and serves everything from ONE address:
#     http://127.0.0.1:8123
#  The browser opens automatically once the server is ready.
# ============================================================
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Port = 8123
$Url = "http://127.0.0.1:$Port"

Write-Host ""
Write-Host "  ==============================" -ForegroundColor Cyan
Write-Host "   KICKLIPS Studio" -ForegroundColor Cyan
Write-Host "  ==============================" -ForegroundColor Cyan
Write-Host ""

function Require-Tool($cmd, $name, $url) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Host ""
        Write-Host "  [MISSING] $name is not installed." -ForegroundColor Yellow
        Write-Host "            Install it from:" -ForegroundColor Yellow
        Write-Host "            $url" -ForegroundColor White
        Write-Host "            During install, tick 'Add to PATH' if offered." -ForegroundColor Yellow
        Write-Host "            Then double-click start.bat again."
        Write-Host ""
        Read-Host "  Press Enter to close"
        exit 1
    }
}

Require-Tool "python" "Python 3.11 or newer" "https://www.python.org/downloads/"
Require-Tool "node"   "Node.js (LTS)"        "https://nodejs.org"

# --- backend environment + dependencies ---
$Venv = Join-Path $Root "backend\.venv"
$Py = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "  [setup] Creating Python environment (first run only)..."
    python -m venv $Venv
}
Write-Host "  [setup] Checking backend dependencies..."
& $Py -m pip install --quiet --disable-pip-version-check -r (Join-Path $Root "backend\requirements.txt")

# --- .env (holds your OPENROUTER_API_KEY) ---
$EnvFile = Join-Path $Root ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root ".env.example") $EnvFile
    Write-Host ""
    Write-Host "  [action needed] A file named .env was created." -ForegroundColor Yellow
    Write-Host "  Open it in Notepad and paste your key after OPENROUTER_API_KEY=" -ForegroundColor Yellow
    Write-Host "  (AI features need it. You can do this now or later.)" -ForegroundColor Yellow
    Start-Process notepad.exe $EnvFile
    Write-Host ""
}

# --- frontend build (served by the backend) ---
$FrontendDir = Join-Path $Root "frontend"
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "  [setup] Installing app dependencies (first run only, a few minutes)..."
    Push-Location $FrontendDir; npm install; Pop-Location
}
if (-not (Test-Path (Join-Path $FrontendDir "dist\index.html"))) {
    Write-Host "  [setup] Building the app (first run only)..."
    Push-Location $FrontendDir; npm run build; Pop-Location
}

# --- open the browser once the server answers ---
$opener = Start-Job -ArgumentList $Url -ScriptBlock {
    param($Url)
    for ($i = 0; $i -lt 90; $i++) {
        try {
            Invoke-WebRequest "$Url/api/health" -UseBasicParsing -TimeoutSec 2 | Out-Null
            Start-Process $Url
            return
        } catch { Start-Sleep -Seconds 1 }
    }
}

Write-Host ""
Write-Host "  Starting... your browser will open at $Url" -ForegroundColor Green
Write-Host "  (Keep this window open while you use the app. Close it to stop.)" -ForegroundColor DarkGray
Write-Host ""

# --- run the server (serves UI + API on one port) ---
Push-Location (Join-Path $Root "backend")
try {
    & $Py -m uvicorn app.main:app --host 127.0.0.1 --port $Port
}
finally {
    Pop-Location
    Stop-Job $opener -ErrorAction SilentlyContinue
    Remove-Job $opener -ErrorAction SilentlyContinue
}
