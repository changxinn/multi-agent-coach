#!/usr/bin/env pwsh
# Quick Start Script for Multi-Agent Coach
# This script starts both backend and frontend

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Multi-Agent Coach - Quick Start" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  .env file not found!" -ForegroundColor Yellow
    Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "✅ .env created. Please edit it with your API key!" -ForegroundColor Green
    Write-Host ""
    Write-Host "IMPORTANT: Edit .env and add your:" -ForegroundColor Yellow
    Write-Host "  - OPENAI_API_KEY=sk-proj-YOUR_KEY_HERE" -ForegroundColor Yellow
    Write-Host "  - DATABASE_URL (if different from default)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Press any key to continue after updating .env..." -ForegroundColor Yellow
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

# Check Python installation
Write-Host "Checking Python installation..." -ForegroundColor Cyan
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found! Please install Python 3.12+" -ForegroundColor Red
    exit 1
}

# Install dependencies
Write-Host ""
Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
pip install -e . --quiet
Write-Host "✅ Dependencies installed" -ForegroundColor Green

# Check if PostgreSQL is running
Write-Host ""
Write-Host "Checking PostgreSQL..." -ForegroundColor Cyan
try {
    $pgReady = pg_isready -h localhost -p 5432 2>&1
    Write-Host "✅ PostgreSQL is running" -ForegroundColor Green
} catch {
    Write-Host "⚠️  PostgreSQL not detected. Starting with Docker..." -ForegroundColor Yellow
    docker-compose up -d db
    Start-Sleep -Seconds 5
}

# Start backend in new window
Write-Host ""
Write-Host "Starting Backend Server..." -ForegroundColor Cyan
$backendJob = Start-Process powershell -ArgumentList "-NoExit", "-Command", "uvicorn app.main:app --reload --port 8000" -PassThru -WindowStyle Normal
Write-Host "✅ Backend starting on http://localhost:8000" -ForegroundColor Green
Write-Host "   API Docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""

# Wait for backend to start
Write-Host "Waiting for backend to initialize (10 seconds)..." -ForegroundColor Cyan
Start-Sleep -Seconds 10

# Check backend health
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -ErrorAction SilentlyContinue
    if ($health.status -eq "healthy") {
        Write-Host "✅ Backend is healthy!" -ForegroundColor Green
    }
} catch {
    Write-Host "⚠️  Backend health check failed. Check backend window for errors." -ForegroundColor Yellow
}

# Start frontend
Write-Host ""
Write-Host "Starting Frontend..." -ForegroundColor Cyan
$frontendJob = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev" -PassThru -WindowStyle Normal
Write-Host "✅ Frontend starting on http://localhost:5174" -ForegroundColor Green
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🚀 Application Started Successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Quick Links:" -ForegroundColor Cyan
Write-Host "  🌐 Frontend:    http://localhost:5174" -ForegroundColor Blue
Write-Host "  🔌 Backend API: http://localhost:8000" -ForegroundColor Blue
Write-Host "  📚 API Docs:    http://localhost:8000/docs" -ForegroundColor Blue
Write-Host "  ❤️  Health:      http://localhost:8000/health" -ForegroundColor Blue
Write-Host ""
Write-Host "Default Login:" -ForegroundColor Cyan
Write-Host "  Email:    admin@example.com" -ForegroundColor White
Write-Host "  Password: ChangeMe123!" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C in each window to stop the servers." -ForegroundColor Yellow
Write-Host ""

# Keep script running
Write-Host "Script completed. Servers are running in separate windows." -ForegroundColor Green
