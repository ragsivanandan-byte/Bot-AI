# Lanceur quotidien — Quiet Capital (Windows / PowerShell)
#   .\bot\run.ps1 list
#   .\bot\run.ps1 make 1
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
  Write-Host "❌  Environnement absent. Lance d'abord :  .\bot\setup.ps1" -ForegroundColor Red
  exit 1
}
& $venvPy (Join-Path $PSScriptRoot "pipeline.py") @args
