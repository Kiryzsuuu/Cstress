# CStress Startup Script
# One-click startup for backend + frontend

param(
    [switch]$SkipBrowser,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-ColorOutput {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Write-Step {
    param([string]$Message)
    Write-ColorOutput "`n>> $Message" -Color Cyan
}

function Write-Success {
    param([string]$Message)
    Write-ColorOutput "[OK] $Message" -Color Green
}

function Test-CommandExists {
    param([string]$Command)
    $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

try {
    Write-ColorOutput @"

=======================================================
   CStress - Konsultasi Stress + Face Tracking
=======================================================

"@ -Color Magenta

    # Check prerequisites
    Write-Step "Checking prerequisites..."
    
    if (-not (Test-CommandExists "python")) {
        Write-ColorOutput "[ERROR] Python not found. Install from https://www.python.org/" -Color Red
        exit 1
    }
    
    if (-not (Test-CommandExists "node")) {
        Write-ColorOutput "[ERROR] Node.js not found. Install from https://nodejs.org/" -Color Red
        exit 1
    }
    
    if (-not (Test-CommandExists "npm")) {
        Write-ColorOutput "[ERROR] npm not found. Install Node.js from https://nodejs.org/" -Color Red
        exit 1
    }
    
    $pythonVersion = (python --version 2>&1) -replace 'Python ', ''
    $nodeVersion = (node --version) -replace 'v', ''
    
    Write-Success "Python $pythonVersion detected"
    Write-Success "Node.js $nodeVersion detected"
    
    # Check .env file
    $envPath = Join-Path $PSScriptRoot "apps\backend\.env"
    if (-not (Test-Path $envPath)) {
        Write-ColorOutput "`n[WARNING] .env file not found!" -Color Yellow
        Write-ColorOutput "Creating .env from .env.example..." -Color Yellow
        Copy-Item (Join-Path $PSScriptRoot "apps\backend\.env.example") $envPath
        Write-ColorOutput "`nPlease edit apps\backend\.env and add your OpenAI API key!" -Color Yellow
        Write-ColorOutput "Get your API key from: https://platform.openai.com/api-keys" -Color Cyan
        Write-ColorOutput "`nPress any key to open .env file..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        Start-Process notepad $envPath
        Write-ColorOutput "`nAfter saving, press any key to continue..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }
    
    # Install dependencies
    if (-not $SkipInstall) {
        Write-Step "Installing dependencies..."
        
        # Backend
        Write-ColorOutput "[Backend] Setting up Python environment..." -Color Yellow
        Push-Location (Join-Path $PSScriptRoot "apps\backend")
        
        if (-not (Test-Path ".venv")) {
            Write-ColorOutput "Creating virtual environment..." -Color Gray
            python -m venv .venv
        }
        
        Write-ColorOutput "Installing Python packages..." -Color Gray
        & .\.venv\Scripts\pip.exe install --quiet --upgrade pip 2>$null
        & .\.venv\Scripts\pip.exe install --quiet -r requirements.txt 2>$null
        & .\.venv\Scripts\pip.exe install --quiet -r requirements-face.txt 2>$null
        
        Pop-Location
        Write-Success "Backend dependencies installed"
        
        # Frontend
        Write-ColorOutput "[Frontend] Installing Node packages..." -Color Yellow
        npm install --silent --prefix (Join-Path $PSScriptRoot ".") 2>$null
        Write-Success "Frontend dependencies installed"
    }
    
    # Kill existing processes
    Write-Step "Cleaning up old processes..."
    Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -like "*CStress*"
    } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    
    # Start backend
    Write-Step "Starting backend server..."
    Push-Location (Join-Path $PSScriptRoot "apps\backend")
    
    $backendJob = Start-Job -ScriptBlock {
        param($BackendPath)
        Set-Location $BackendPath
        & .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
    } -ArgumentList (Get-Location)
    
    Pop-Location
    Write-Success "Backend starting (Job ID: $($backendJob.Id))"
    
    # Wait for backend
    Write-ColorOutput "Waiting for backend..." -Color Gray
    $backendReady = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:8001/api/health" -Method GET -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $backendReady = $true
                break
            }
        } catch {
            Write-Host "." -NoNewline
        }
    }
    
    if (-not $backendReady) {
        Write-ColorOutput "`n[ERROR] Backend failed to start" -Color Red
        Stop-Job $backendJob -ErrorAction SilentlyContinue
        Remove-Job $backendJob -ErrorAction SilentlyContinue
        exit 1
    }
    
    Write-Host ""
    Write-Success "Backend ready at http://127.0.0.1:8001"
    
    # Start frontend
    Write-Step "Starting frontend server..."
    $frontendJob = Start-Job -ScriptBlock {
        param($RootPath)
        Set-Location $RootPath
        npm run dev:web
    } -ArgumentList $PSScriptRoot
    
    Write-Success "Frontend starting (Job ID: $($frontendJob.Id))"
    
    # Wait for frontend
    Write-ColorOutput "Waiting for frontend..." -Color Gray
    $frontendUrl = "http://localhost:5173"
    $frontendReady = $false
    
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 1
        try {
            $response = Invoke-WebRequest -Uri $frontendUrl -Method GET -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $frontendReady = $true
                break
            }
        } catch {
            Write-Host "." -NoNewline
        }
    }
    
    if (-not $frontendReady) {
        # Try alternative port
        $frontendUrl = "http://localhost:5174"
    }
    
    Write-Host ""
    Write-Success "Frontend ready at $frontendUrl"
    
    # Success
    Write-ColorOutput @"

=======================================================
              ALL SYSTEMS READY!
=======================================================

  Backend:  http://127.0.0.1:8001
  Frontend: $frontendUrl
  
  Face Tracking: ws://127.0.0.1:8001/ws/face
  
=======================================================

"@ -Color Green
    
    # Open browser
    if (-not $SkipBrowser) {
        Write-ColorOutput "Opening browser..." -Color Cyan
        Start-Sleep -Seconds 2
        Start-Process $frontendUrl
    }
    
    Write-ColorOutput @"
Press Ctrl+C to stop all servers

Logs:
  Backend:  Receive-Job $($backendJob.Id)
  Frontend: Receive-Job $($frontendJob.Id)

"@ -Color Yellow
    
    # Keep running
    try {
        while ($true) {
            Start-Sleep -Milliseconds 500
            
            if ($backendJob.State -ne "Running") {
                Write-ColorOutput "[ERROR] Backend stopped" -Color Red
                break
            }
            if ($frontendJob.State -ne "Running") {
                Write-ColorOutput "[ERROR] Frontend stopped" -Color Red
                break
            }
        }
    } finally {
        Write-ColorOutput "`nStopping servers..." -Color Yellow
        Stop-Job $backendJob -ErrorAction SilentlyContinue
        Stop-Job $frontendJob -ErrorAction SilentlyContinue
        Remove-Job $backendJob -Force -ErrorAction SilentlyContinue
        Remove-Job $frontendJob -Force -ErrorAction SilentlyContinue
        Write-Success "All servers stopped"
    }
    
} catch {
    Write-ColorOutput "`n[ERROR] $($_.Exception.Message)" -Color Red
    Write-Host $_.ScriptStackTrace -ForegroundColor Red
    exit 1
}
