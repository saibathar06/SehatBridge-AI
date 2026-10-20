$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Python environment missing. Follow the first-time setup in README.md.'
}
Push-Location (Join-Path $taskRoot 'backend')
try {
    & $taskPython -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
    Write-Host 'Backend: http://127.0.0.1:8000/docs'
    Write-Host 'Keep this terminal open. Development email OTP codes appear here.'
    & $taskPython -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
} finally { Pop-Location }
