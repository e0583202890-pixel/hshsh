# KICKLIPS Studio launcher (classic powershell.exe compatible)
# Installs dependencies if missing, then starts backend + frontend.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== KICKLIPS Studio ===" -ForegroundColor Cyan

# --- Python backend ---
$VenvDir = Join-Path $Root "backend\.venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[setup] Creating Python virtual environment..."
    python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[error] Python 3.11+ is required and must be on PATH." -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "[setup] Installing backend dependencies (first run may take a while)..."
& $VenvPython -m pip install --quiet --disable-pip-version-check -r (Join-Path $Root "backend\requirements.txt")

# --- .env ---
$EnvFile = Join-Path $Root ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root ".env.example") $EnvFile
    Write-Host "[setup] Created .env from .env.example - add your ANTHROPIC_API_KEY there." -ForegroundColor Yellow
}

# --- Node frontend ---
$FrontendDir = Join-Path $Root "frontend"
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "[setup] Installing frontend dependencies..."
    Push-Location $FrontendDir
    npm install
    Pop-Location
}

# --- start both ---
Write-Host "[run] Starting backend on http://127.0.0.1:8123 ..."
$Backend = Start-Process -PassThru -NoNewWindow $VenvPython -ArgumentList `
    "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8123" `
    -WorkingDirectory (Join-Path $Root "backend")

Write-Host "[run] Starting frontend on http://127.0.0.1:5173 ..."
Push-Location $FrontendDir
try {
    npm run dev
}
finally {
    Pop-Location
    if ($Backend -and -not $Backend.HasExited) {
        Write-Host "[run] Stopping backend..."
        Stop-Process -Id $Backend.Id -Force -ErrorAction SilentlyContinue
    }
}
