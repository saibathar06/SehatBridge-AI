$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Create the Python environment first; see README.md.' }
Push-Location (Join-Path $taskRoot 'backend')
try {
    Write-Host 'Document/reminder worker running. Keep this terminal open. Stop with Ctrl+C.'
    & $taskPython -m app.worker
} finally { Pop-Location }
