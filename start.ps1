<#
.SYNOPSIS
  Start ResearchOS (backend + frontend). The first run installs dependencies.

.EXAMPLE
  .\start.ps1               # development mode (hot reload)
  .\start.ps1 -Production   # optimised build, faster pages
#>
param([switch]$Production)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"

function Require-Command($name, $hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: '$name' was not found. $hint" -ForegroundColor Red
        exit 1
    }
}

Require-Command "npm" "Install Node.js LTS from https://nodejs.org (or: winget install OpenJS.NodeJS.LTS), then open a new terminal."

if (-not (Test-Path $venvPython)) {
    Require-Command "python" "Install Python 3.11+ from https://python.org (or: winget install Python.Python.3.12)."
    Write-Host "Creating the Python environment (first run only)..." -ForegroundColor Cyan
    python -m venv (Join-Path $backend ".venv")
    & $venvPython -m pip install --upgrade pip --quiet
    & $venvPython -m pip install -r (Join-Path $backend "requirements.txt")
    if ($LASTEXITCODE -ne 0) { Write-Host "Installing Python packages failed." -ForegroundColor Red; exit 1 }
}

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "Installing frontend packages (first run only)..." -ForegroundColor Cyan
    Push-Location $frontend
    npm install
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { Write-Host "npm install failed." -ForegroundColor Red; exit 1 }
}

try {
    Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:11434/api/version" -TimeoutSec 2 | Out-Null
    Write-Host "Ollama is running." -ForegroundColor Green
} catch {
    Write-Host "Ollama is not running: the library works, but AI features need it (https://ollama.com)." -ForegroundColor Yellow
}

foreach ($port in 8000, 3000) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        Write-Host "ERROR: port $port is already in use. Is ResearchOS already running?" -ForegroundColor Red
        exit 1
    }
}

if ($Production) {
    Write-Host "Building the frontend..." -ForegroundColor Cyan
    Push-Location $frontend
    npm run build
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { Write-Host "Frontend build failed." -ForegroundColor Red; exit 1 }
    $frontendArgs = @("run", "start")
} else {
    $frontendArgs = @("run", "dev")
}

$backendProcess = Start-Process -FilePath $venvPython -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory $backend -PassThru -NoNewWindow
$frontendProcess = Start-Process -FilePath "npm.cmd" -ArgumentList $frontendArgs -WorkingDirectory $frontend -PassThru -NoNewWindow

Write-Host ""
Write-Host "ResearchOS is starting:" -ForegroundColor Green
Write-Host "  App:      http://localhost:3000"
Write-Host "  API docs: http://127.0.0.1:8000/docs"
Write-Host "Press Ctrl+C to stop both servers."

try {
    while (-not $backendProcess.HasExited -and -not $frontendProcess.HasExited) {
        Start-Sleep -Seconds 1
    }
    Write-Host "A server stopped unexpectedly; shutting down." -ForegroundColor Yellow
} finally {
    foreach ($process in $backendProcess, $frontendProcess) {
        if ($process -and -not $process.HasExited) {
            # /T also stops child processes (npm starts node).
            taskkill /PID $process.Id /T /F | Out-Null
        }
    }
    Write-Host "Stopped."
}
