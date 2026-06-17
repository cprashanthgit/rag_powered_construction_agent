# start.ps1 - One-command startup for the Construction RAG Assistant
#
# Starts everything in order:
#   1. Docker (Redis + PostgreSQL + Prometheus + Grafana)
#   2. FastAPI backend  -> http://localhost:8000
#   3. Streamlit UI     -> http://localhost:8501
#
# Usage:
#   .\start.ps1

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Construction RAG Assistant - Starting Up  " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Start Docker infrastructure
Write-Host "[1/3] Starting Docker (Redis, PostgreSQL, Prometheus, Grafana)..." -ForegroundColor Yellow
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker failed to start. Is Docker Desktop running?" -ForegroundColor Red
    exit 1
}

Write-Host "      Waiting 3 seconds for PostgreSQL to be ready..." -ForegroundColor DarkGray
Start-Sleep -Seconds 3
Write-Host "      Docker services running." -ForegroundColor Green
Write-Host ""

# Step 2: Start FastAPI in a new terminal window
Write-Host "[2/3] Starting FastAPI backend on http://localhost:8000 ..." -ForegroundColor Yellow

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'FastAPI - Construction RAG' -ForegroundColor Cyan; uvicorn api:app --host 0.0.0.0 --port 8000 --reload"

Write-Host "      FastAPI started. Waiting 3s for it to load..." -ForegroundColor Green
Start-Sleep -Seconds 3
Write-Host ""

# Step 3: Start Streamlit in a new terminal window
Write-Host "[3/3] Starting Streamlit UI on http://localhost:8501 ..." -ForegroundColor Yellow

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Streamlit - Construction RAG UI' -ForegroundColor Cyan; streamlit run app.py"

Write-Host "      Streamlit started." -ForegroundColor Green
Write-Host ""

# Summary
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  All services running!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Streamlit UI  ->  http://localhost:8501" -ForegroundColor White
Write-Host "  FastAPI docs  ->  http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Grafana       ->  http://localhost:3000  (admin/admin)" -ForegroundColor White
Write-Host "  Prometheus    ->  http://localhost:9090" -ForegroundColor White
Write-Host ""
Write-Host "  To stop everything: .\stop.ps1" -ForegroundColor DarkGray
Write-Host ""
