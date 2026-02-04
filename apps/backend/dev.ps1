param(
  [switch]$WithFace,
  [switch]$Reload,
  [switch]$Detach
)

$ErrorActionPreference = 'Stop'

$backendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $backendDir

if (!(Test-Path -Path ".venv")) {
  Write-Host "[backend] Creating venv (.venv)" -ForegroundColor Cyan
  python -m venv .venv
}

$py = Join-Path $backendDir ".venv\Scripts\python.exe"

Write-Host "[backend] Installing base requirements" -ForegroundColor Cyan
& $py -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
  throw "[backend] Base requirements install failed"
}

if ($WithFace) {
  Write-Host "[backend] Installing face tracking requirements" -ForegroundColor Cyan
  & $py -m pip install -r requirements-face.txt
  if ($LASTEXITCODE -ne 0) {
    Write-Host "[backend] Face tracking deps failed to install. Backend will still start, but tracking will be unavailable." -ForegroundColor Yellow
    Write-Host "[backend] Hint: try Python 3.12, or run without -WithFace." -ForegroundColor Yellow
  }
} else {
  Write-Host "[backend] Face tracking deps optional (use -WithFace)" -ForegroundColor DarkGray
}

if (!(Test-Path -Path ".env")) {
  Copy-Item .env.example .env
  Write-Host "[backend] Created .env from .env.example" -ForegroundColor Cyan
}

# Friendly reminder about required config
$keyLine = (Get-Content .env -ErrorAction SilentlyContinue | Select-String -Pattern '^OPENAI_API_KEY=' | Select-Object -First 1)
if (-not $keyLine -or $keyLine.Line -match '^OPENAI_API_KEY\s*=\s*$' -or $keyLine.Line -match 'your_openai_api_key_here') {
  Write-Host "[backend] OPENAI_API_KEY belum diisi. Chat akan error sampai kamu set key di apps/backend/.env" -ForegroundColor Yellow
}

Write-Host "[backend] Starting uvicorn on http://127.0.0.1:8001" -ForegroundColor Green
$args = @('app.main:app', '--app-dir', '.', '--host', '127.0.0.1', '--port', '8001')
if ($Reload) {
  $args += '--reload'
}

if ($Detach) {
  $uvArgs = @('-m', 'uvicorn') + $args
  $p = Start-Process -FilePath $py -ArgumentList $uvArgs -WorkingDirectory $backendDir -PassThru
  Write-Host "[backend] Uvicorn started (PID=$($p.Id))." -ForegroundColor Green
  return
}

& $py -m uvicorn @args
