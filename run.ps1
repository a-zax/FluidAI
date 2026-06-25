Write-Host "Starting Enterprise AI Assistant..."
Write-Host "Frontend: http://localhost:8001"
Write-Host "API docs: http://localhost:8001/docs"
Write-Host ""

python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
