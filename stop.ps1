# stop.ps1 - Gracefully stop all Construction RAG Assistant services
#
# Usage:
#   .\stop.ps1

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Construction RAG Assistant - Stopping     " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Stop FastAPI (port 8000)
Write-Host "[1/3] Stopping FastAPI (port 8000)..." -ForegroundColor Yellow
$api = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($api) {
    $api | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Write-Host "      FastAPI stopped." -ForegroundColor Green
} else {
    Write-Host "      FastAPI was not running." -ForegroundColor DarkGray
}

# Stop Streamlit (port 8501)
Write-Host "[2/3] Stopping Streamlit (port 8501)..." -ForegroundColor Yellow
$st = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue
if ($st) {
    $st | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Write-Host "      Streamlit stopped." -ForegroundColor Green
} else {
    Write-Host "      Streamlit was not running." -ForegroundColor DarkGray
}

# Stop Docker containers
Write-Host "[3/3] Stopping Docker containers..." -ForegroundColor Yellow
docker-compose stop
Write-Host "      Docker containers stopped (data preserved)." -ForegroundColor Green
Write-Host ""
Write-Host "  All services stopped. To restart: .\start.ps1" -ForegroundColor Cyan
Write-Host ""
