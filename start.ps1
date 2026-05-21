# Levanta backend (FastAPI) y frontend (Next.js) en ventanas separadas
$root = $PSScriptRoot

# Backend (-NoExit mantiene la ventana abierta aunque haya errores)
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
Write-Host ""
Read-Host "Pulsa Enter para cerrar esta ventana"
