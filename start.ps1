#!/usr/bin/env pwsh
<#
.SYNOPSIS
    One-click startup script for CStress application
.DESCRIPTION
    This script starts both backend (Python FastAPI) and frontend (Vite React) servers
    and opens the application in your default browser.
#>

param(
    [switch]$SkipBrowser,  # Don't open browser automatically
    [switch]$SkipInstall   # Skip dependency installation
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Colors for output
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
    Write-ColorOutput "`n✓ $Message" -Color Cyan
}

function Write-Error-Custom {
    param([string]$Message)
    Write-ColorOutput "✗ ERROR: $Message" -Color Red
}

function Write-Success {
    param([string]$Message)
    Write-ColorOutput "✓ $Message" -Color Green
}

# Check if command exists
function Test-CommandExists {
    param([string]$Command)
    $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

# Main execution
try {
    Write-ColorOutput @"
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║   ██████╗███████╗████████╗██████╗ ███████╗███████╗  ║
║  ██╔════╝██╔════╝╚══██╔══╝██╔══██╗██╔════╝██╔════╝  ║
║  ██║     ███████╗   ██║   ██████╔╝█████╗  ███████╗  ║
║  ██║     ╚════██║   ██║   ██╔══██╗██╔══╝  ╚════██║  ║
║  ╚██████╗███████║   ██║   ██║  ██║███████╗███████║  ║
║   ╚═════╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚══════╝  ║
║                                                       ║
║       Konsultasi Stress + Face Tracking              ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
"@ -Color Magenta

    # Check prerequisites
    Write-Step "Checking prerequisites..."
    
    if (-not (Test-CommandExists "python")) {
        Write-Error-Custom "Python not found. Please install Python 3.12 or later from https://www.python.org/"
        exit 1
    }
    
    if (-not (Test-CommandExists "node")) {
        Write-Error-Custom "Node.js not found. Please install Node.js from https://nodejs.org/"
        exit 1
    }
    
    if (-not (Test-CommandExists "npm")) {
        Write-Error-Custom "npm not found. Please install Node.js (includes npm) from https://nodejs.org/"
        exit 1
    }
    
    $pythonVersion = (python --version 2>&1) -replace 'Python ', ''
    $nodeVersion = (node --version) -replace 'v', ''
    
    Write-Success "Python $pythonVersion detected"
    Write-Success "Node.js $nodeVersion detected"
    
    # Check .env file
    $envPath = Join-Path $PSScriptRoot "apps\backend\.env"
    if (-not (Test-Path $envPath)) {
        Write-ColorOutput "`n⚠ WARNING: .env file not found!" -Color Yellow
        Write-ColorOutput "Creating .env from .env.example..." -Color Yellow
        Copy-Item (Join-Path $PSScriptRoot "apps\backend\.env.example") $envPath
        Write-ColorOutput "`nPlease edit apps\backend\.env and add your OpenAI API key!" -Color Yellow
        Write-ColorOutput "Get your API key from: https://platform.openai.com/api-keys" -Color Cyan
        Write-ColorOutput "`nPress any key to open .env file in notepad..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        Start-Process notepad $envPath
        Write-ColorOutput "`nAfter saving your API key, press any key to continue..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }
    
    # Install dependencies
    if (-not $SkipInstall) {
        Write-Step "Installing/updating dependencies..."
        
        # Backend dependencies
        Write-ColorOutput "`n[Backend] Setting up Python environment..." -Color Yellow
        Push-Location (Join-Path $PSScriptRoot "apps\backend")
        
        if (-not (Test-Path ".venv")) {
            Write-ColorOutput "Creating virtual environment..." -Color Gray
            python -m venv .venv
        }
        
        Write-ColorOutput "Installing Python packages..." -Color Gray
        & .\.venv\Scripts\pip.exe install --quiet --upgrade pip
        & .\.venv\Scripts\pip.exe install --quiet -r requirements.txt
        & .\.venv\Scripts\pip.exe install --quiet -r requirements-face.txt
        
        Pop-Location
        Write-Success "Backend dependencies installed"
        
        # Frontend dependencies
        Write-ColorOutput "`n[Frontend] Installing Node packages..." -Color Yellow
        npm install --silent --prefix (Join-Path $PSScriptRoot ".")
        Write-Success "Frontend dependencies installed"
    }
    
    # Start backend
    Write-Step "Starting backend server..."
    Push-Location (Join-Path $PSScriptRoot "apps\backend")
    
    # Kill existing Python processes for this project
    Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -like "*CStress*"
    } | Stop-Process -Force -ErrorAction SilentlyContinue
    
    Start-Sleep -Milliseconds 500
    
    # Start backend in background
    $backendJob = Start-Job -ScriptBlock {
        param($BackendPath)
        Set-Location $BackendPath
        & .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
    } -ArgumentList (Get-Location)
    
    Pop-Location
    Write-Success "Backend starting... (Job ID: $($backendJob.Id))"
    
    # Wait for backend to be ready
    Write-ColorOutput "Waiting for backend to be ready..." -Color Gray
    $maxAttempts = 30
    $attempt = 0
    $backendReady = $false
    
    while ($attempt -lt $maxAttempts -and -not $backendReady) {
        $attempt++
        Start-Sleep -Seconds 1
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:8001/health" -Method GET -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $backendReady = $true
            }
        } catch {
            # Backend not ready yet
        }
        Write-Host "." -NoNewline
    }
    
    if (-not $backendReady) {
        Write-Error-Custom "Backend failed to start within 30 seconds"
        Stop-Job $backendJob
        Remove-Job $backendJob
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
    
    Write-Success "Frontend starting... (Job ID: $($frontendJob.Id))"
    
    # Wait for frontend to be ready
    Write-ColorOutput "Waiting for frontend to be ready..." -Color Gray
    $attempt = 0
    $frontendReady = $false
    $frontendUrl = ""
    
    while ($attempt -lt 30 -and -not $frontendReady) {
        $attempt++
        Start-Sleep -Seconds 1
        
        # Check job output for the URL
        $output = Receive-Job $frontendJob -ErrorAction SilentlyContinue
        if ($output -match "Local:.*?(http://localhost:\d+)") {
            $frontendUrl = $matches[1]
            $frontendReady = $true
        }
        Write-Host "." -NoNewline
    }
    
    if (-not $frontendReady) {
        # Try default port
        $frontendUrl = "http://localhost:5173"
        try {
            $response = Invoke-WebRequest -Uri $frontendUrl -Method GET -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $frontendReady = $true
            }
        } catch {
            # Try alternative port
            $frontendUrl = "http://localhost:5174"
        }
    }
    
    Write-Host ""
    Write-Success "Frontend ready at $frontendUrl"
    
    # Success message
    Write-ColorOutput @"

╔═══════════════════════════════════════════════════════╗
║                  🚀 ALL SYSTEMS GO! 🚀                ║
╚═══════════════════════════════════════════════════════╝

    Backend:  http://127.0.0.1:8001
    Frontend: $frontendUrl
    
    Face Tracking: WebSocket ready at ws://127.0.0.1:8001/ws/face
    
"@ -Color Green
    
    # Open browser
    if (-not $SkipBrowser) {
        Write-ColorOutput "Opening browser..." -Color Cyan
        Start-Sleep -Seconds 2
        Start-Process $frontendUrl
    }
    
    Write-ColorOutput @"
╔═══════════════════════════════════════════════════════╗
║                     TIPS & CONTROLS                   ║
╠═══════════════════════════════════════════════════════╣
║                                                       ║
║  • Press Ctrl+C to stop all servers                  ║
║  • Backend logs: Receive-Job $($backendJob.Id)              ║
║  • Frontend logs: Receive-Job $($frontendJob.Id)             ║
║                                                       ║
║  • Face tracking memerlukan kamera                   ║
║  • Toggle tracking dengan checkbox di UI             ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝

Press Ctrl+C to stop all servers...

"@ -Color Yellow
    
    # Keep script running and forward output
    try {
        while ($true) {
            # Forward backend logs
            $backendOutput = Receive-Job $backendJob -ErrorAction SilentlyContinue
            if ($backendOutput) {
                Write-Host "[Backend] " -ForegroundColor Blue -NoNewline
                Write-Host $backendOutput
            }
            
            # Forward frontend logs
            $frontendOutput = Receive-Job $frontendJob -ErrorAction SilentlyContinue
            if ($frontendOutput) {
                Write-Host "[Frontend] " -ForegroundColor Magenta -NoNewline
                Write-Host $frontendOutput
            }
            
            # Check if jobs are still running
            if ($backendJob.State -ne "Running") {
                Write-Error-Custom "Backend job stopped unexpectedly"
                break
            }
            if ($frontendJob.State -ne "Running") {
                Write-Error-Custom "Frontend job stopped unexpectedly"
                break
            }
            
            Start-Sleep -Milliseconds 500
        }
    } finally {
        # Cleanup
        Write-ColorOutput "`n`nStopping servers..." -Color Yellow
        Stop-Job $backendJob -ErrorAction SilentlyContinue
        Stop-Job $frontendJob -ErrorAction SilentlyContinue
        Remove-Job $backendJob -Force -ErrorAction SilentlyContinue
        Remove-Job $frontendJob -Force -ErrorAction SilentlyContinue
        Write-Success "All servers stopped"
    }
    
} catch {
    Write-Error-Custom $_.Exception.Message
    Write-Host $_.ScriptStackTrace -ForegroundColor Red
    exit 1
}
