# Doodle Theater: set up and start the server with one command (Windows PowerShell).
#
#   .\run.ps1           install on first run, then start on port 8787
#   .\run.ps1 -Setup    install only, don't start
#   .\run.ps1 -Help     show this
#
# Another port: $env:DT_PORT = "8788"; .\run.ps1
# If scripts are blocked: powershell -ExecutionPolicy Bypass -File .\run.ps1
param([switch]$Setup, [switch]$Help)
$ErrorActionPreference = "Stop"

if ($Help) { Get-Content $PSCommandPath | Where-Object { $_ -like '#*' } | Select-Object -First 8 | ForEach-Object { $_ -replace '^# ?', '' }; exit 0 }

$server = Join-Path $PSScriptRoot "server"
$venv = Join-Path $server ".venv"
$py = Join-Path $venv "Scripts\python.exe"
$port = if ($env:DT_PORT) { $env:DT_PORT } else { "8787" }
$env:DT_PORT = $port   # the QR code on the TV uses it too

if (-not (Test-Path $py)) {
    Write-Host "Creating server\.venv (needs Python 3.10+)..."
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv $venv } else { python -m venv $venv }
    if (-not (Test-Path $py)) { throw "Couldn't create the virtual environment. Install Python 3.10+ from python.org." }
}

# Install once; delete server\.venv\.installed to force a reinstall.
$marker = Join-Path $venv ".installed"
if ($Setup -or -not (Test-Path $marker)) {
    Write-Host "Installing the server and rig packages (a few minutes the first time)..."
    & $py -m pip install --quiet --upgrade pip
    & $py -m pip install --quiet fastapi uvicorn python-multipart python-dotenv segno pillow numpy `
        opencv-python-headless boto3 strands-agents pytest httpx
    if ($LASTEXITCODE -ne 0) { throw "pip install failed." }
    & $py -m pip install --quiet -e (Join-Path $PSScriptRoot "rig")
    if ($LASTEXITCODE -ne 0) { throw "pip install of ./rig failed." }
    New-Item -ItemType File -Force $marker | Out-Null
}
if ($Setup) { Write-Host "Setup done. Start with .\run.ps1"; exit 0 }

Push-Location $server
try {
    $ip = & $py -c "from doodle_theater.config import lan_ip; print(lan_ip())"
    Write-Host ""
    Write-Host "Doodle Theater server on port $port"
    Write-Host "  TV on this Wi-Fi (Fire TV / Android TV):  http://${ip}:$port   <- 'Set server address' on the TV"
    $emu = if ($port -eq "8787") { "(the app's default: no setup needed)" } else { "<- 'Set server address' on the TV" }
    Write-Host "  Android TV emulator on this laptop:       http://10.0.2.2:$port   $emu"
    Write-Host "  Phone: scan the QR code on the TV's 'Add a star' screen."
    Write-Host "  Check it in a browser:                    http://localhost:$port/api/cast"
    Write-Host "Press Ctrl+C to stop."
    Write-Host ""
    # uvicorn logs to stderr; with "Stop", Windows PowerShell would treat a redirected log line as fatal.
    $ErrorActionPreference = "Continue"
    & $py -m uvicorn doodle_theater.app:app --host 0.0.0.0 --port $port
} finally {
    Pop-Location
}
