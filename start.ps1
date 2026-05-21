# Levanta backend (FastAPI) y frontend (Next.js) en ventanas separadas
$root = $PSScriptRoot

# Verificar ANTHROPIC_API_KEY
if (-not $env:ANTHROPIC_API_KEY) {
    Write-Host "ERROR: ANTHROPIC_API_KEY no esta definida en el entorno." -ForegroundColor Red
    Write-Host "Ejecuta: `$env:ANTHROPIC_API_KEY = 'sk-...'" -ForegroundColor Yellow
    exit 1
}

# Backend
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "Set-Location '$root\backend'; pip install -r requirements.txt -q; uvicorn main:app --reload"

# Frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "Set-Location '$root\ui'; npm install --silent; npm run dev"

Write-Host ""
Write-Host "Servicios arrancando..." -ForegroundColor Green
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Cierra las ventanas de PowerShell para detener los servicios."
