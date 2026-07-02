# start-all.ps1 - one-shot launcher for EsportsPostAI.
#
# Brings up the whole stack in the right order:
#   1. Docker Desktop  -> Redis (:6379) + MongoDB (:27017) containers
#   2. FastAPI backend  (:8000)   - its own window
#   3. RQ worker        (drains the poster queue) - its own window
#   4. Frontend         (:5173)   - its own window
#   5. Opens the app in your browser
#
# Safe to re-run: anything already up is left alone. Each service runs in its
# own PowerShell window - close that window to stop the service.
#
# Double-click "start.bat" (which calls this), or run:
#   powershell -ExecutionPolicy Bypass -File start-all.ps1

$ErrorActionPreference = "Continue"  # launcher handles its own errors

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Frontend    = Join-Path $ProjectRoot "Poster-ai-frontend"
$Python      = "python"

# Container names + images for the data services.
$RedisName = "epai-redis";  $RedisImage = "redis:7"
$MongoName = "epai-mongo";  $MongoImage = "mongo:7"

function Test-Port([int]$Port) {
    [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-Port([int]$Port, [int]$TimeoutSec, [string]$Label) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
        if (Test-Port $Port) { Write-Host "  $Label up (port $Port)." -ForegroundColor Green; return $true }
        Start-Sleep -Milliseconds 800
    }
    return $false
}

# Run a docker command quietly via cmd so PowerShell never wraps native stderr.
function Docker-Quiet([string]$DockerArgs) { cmd /c "docker $DockerArgs >nul 2>nul"; return ($LASTEXITCODE -eq 0) }
function Docker-Up { return (Docker-Quiet "info") }

# Bring a data service up on $Port. Preference order (keeps your existing data):
#   1. already listening      -> nothing to do
#   2. reuse ANY container publishing this port (your existing data volume)
#   3. start our named container if it exists
#   4. create a fresh named container
function Ensure-Container([int]$Port, [string]$Name, [string]$Image, [string]$RunArgs, [string]$Label) {
    if (Test-Port $Port) { return }
    Write-Host "Starting $Label..." -ForegroundColor Yellow
    $existing = @(& cmd /c "docker ps -aq --filter publish=$Port" 2>$null | Where-Object { $_ })
    if ($existing.Count -gt 0) {
        Docker-Quiet "start $($existing[0])" | Out-Null
    } elseif (-not (Docker-Quiet "start $Name")) {
        Docker-Quiet "run -d --name $Name $RunArgs $Image" | Out-Null
    }
}

function Start-Service-Window([string]$Title, [string]$Command, [string]$WorkDir) {
    $inner = "`$Host.UI.RawUI.WindowTitle = '$Title'; Write-Host '[$Title]' -ForegroundColor Cyan; $Command"
    Start-Process -FilePath "powershell.exe" -WorkingDirectory $WorkDir `
        -ArgumentList "-NoExit", "-NoProfile", "-Command", $inner | Out-Null
}

Write-Host ""
Write-Host "==== EsportsPostAI launcher ====" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot" -ForegroundColor DarkGray

# ---------------------------------------------------------------- 1. Data services
if ((Test-Port 6379) -and (Test-Port 27017)) {
    Write-Host "Redis + MongoDB already running." -ForegroundColor Green
} else {
    if (-not (Docker-Up)) {
        Write-Host "Starting Docker Desktop (this can take a minute)..." -ForegroundColor Yellow
        $dd = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        if (Test-Path $dd) { Start-Process $dd | Out-Null }
        else { Write-Host "Docker Desktop not found at $dd - start it manually." -ForegroundColor Red }

        $sw = [Diagnostics.Stopwatch]::StartNew()
        while ($sw.Elapsed.TotalSeconds -lt 150 -and -not (Docker-Up)) { Start-Sleep -Seconds 2 }
    }

    if (-not (Docker-Up)) {
        Write-Host "Docker daemon never came up. Start Docker Desktop, then re-run." -ForegroundColor Red
        Read-Host "Press Enter to exit"; exit 1
    }
    Write-Host "Docker is ready." -ForegroundColor Green

    Ensure-Container 6379  $RedisName $RedisImage "-p 6379:6379"   "Redis"
    Ensure-Container 27017 $MongoName $MongoImage "-p 27017:27017" "MongoDB"

    if (-not (Wait-Port 6379 60 "Redis"))    { Write-Host "Redis not reachable on 6379." -ForegroundColor Red; Read-Host "Press Enter to exit"; exit 1 }
    if (-not (Wait-Port 27017 60 "MongoDB")) { Write-Host "MongoDB not reachable on 27017." -ForegroundColor Red; Read-Host "Press Enter to exit"; exit 1 }
}

# ---------------------------------------------------------------- 2. API (:8000)
if (Test-Port 8000) {
    Write-Host "API already on :8000." -ForegroundColor Green
} else {
    Write-Host "Starting API (:8000)..." -ForegroundColor Yellow
    Start-Service-Window "EPAI API" "$Python -m esports_poster_ai.api" $ProjectRoot
}

# ---------------------------------------------------------------- 3. Worker
$workerRunning = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*esports_poster_ai.worker*" }
if ($workerRunning) {
    Write-Host "Worker already running." -ForegroundColor Green
} else {
    Write-Host "Starting worker..." -ForegroundColor Yellow
    Start-Service-Window "EPAI Worker" "$Python -m esports_poster_ai.worker" $ProjectRoot
}

# ---------------------------------------------------------------- 4. Frontend (:5173)
if (Test-Port 5173) {
    Write-Host "Frontend already on :5173." -ForegroundColor Green
} else {
    Write-Host "Starting frontend (:5173)..." -ForegroundColor Yellow
    Start-Service-Window "EPAI Frontend" "$Python -m http.server 5173 --bind 127.0.0.1" $Frontend
}

# ---------------------------------------------------------------- 5. Open the app
if (Wait-Port 8000 60 "API") {
    Start-Sleep -Seconds 1
    Start-Process "http://localhost:5173/EsportsPostAI.html" | Out-Null
    Write-Host ""
    Write-Host "All set ->  http://localhost:5173/EsportsPostAI.html" -ForegroundColor Cyan
} else {
    Write-Host "API did not answer on :8000 - check the [EPAI API] window for the error." -ForegroundColor Red
}

Write-Host "Each service runs in its own window; close those windows to stop them." -ForegroundColor DarkGray
Read-Host "Press Enter to close this launcher (services keep running)"
