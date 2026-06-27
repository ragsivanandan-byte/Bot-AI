# Installateur tout-en-un — Quiet Capital (Windows / PowerShell)
# Usage (clic droit > Exécuter avec PowerShell, ou) :  .\bot\setup.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "🤖  Quiet Capital — installation automatique" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════"

# 1. Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Write-Host "❌  Python manquant : https://www.python.org/downloads/ (coche 'Add to PATH')" -ForegroundColor Red; exit 1 }
Write-Host "✓  Python : $(python --version)"

# 2. Environnement isolé
Write-Host "📦  Création de l'environnement Python (.venv)…"
python -m venv .venv
$venvPy = ".\.venv\Scripts\python.exe"
& $venvPy -m pip install --upgrade pip | Out-Null
Write-Host "📦  Installation des dépendances…"
& $venvPy -m pip install -r requirements.txt

# 3. ffmpeg
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
  Write-Host "✓  ffmpeg déjà installé"
} else {
  Write-Host "🎬  ffmpeg manquant, tentative via winget…"
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --silent --accept-source-agreements --accept-package-agreements Gyan.FFmpeg
    Write-Host "⚠️   Ferme et rouvre PowerShell après l'install de ffmpeg pour qu'il soit reconnu."
  } else {
    Write-Host "⚠️   Installe ffmpeg à la main : https://ffmpeg.org/download.html"
  }
}

# 4. .env
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

function Set-Key($key, $val) {
  $lines = Get-Content .env
  if ($lines -match "^$key=") {
    ($lines -replace "^$key=.*", "$key=$val") | Set-Content .env
  } else {
    Add-Content .env "$key=$val"
  }
}

# 5. Clés API
Write-Host ""
Write-Host "🔑  Tes clés API (Entrée pour configurer plus tard dans bot\.env)"
$el = Read-Host "    ElevenLabs (obligatoire)"
if ($el) { Set-Key "ELEVENLABS_API_KEY" $el; Write-Host "    ✓ enregistrée" }
$xa = Read-Host "    xAI Grok (optionnel)"
if ($xa) { Set-Key "XAI_API_KEY" $xa; Write-Host "    ✓ enregistrée" }

# 6. Vérification
Write-Host ""
Write-Host "🔎  Vérification du contenu…"
& $venvPy pipeline.py list

Write-Host ""
Write-Host "✅  Installation terminée !" -ForegroundColor Green
Write-Host "👉  Produis ta 1re vidéo :   .\bot\run.ps1 make 1"
