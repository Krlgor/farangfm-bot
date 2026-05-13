# deploy.ps1 - PowerShell скрипт для деплоя FARANG.FM бота на Render

Write-Host "🚀 FARANG.FM Bot Deployment Script" -ForegroundColor Cyan
Write-Host "================================
" -ForegroundColor Cyan

# Проверка наличия git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Git not found! Please install Git first." -ForegroundColor Red
    Write-Host "   Download: https://git-scm.com/download/win"
    exit 1
}

# Проверка наличия .env файла
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  .env file not found!" -ForegroundColor Yellow
    Write-Host "   Creating from .env.example..."
    Copy-Item ".env.example" ".env"
    Write-Host "✅ Created .env file. Please edit it with your real values!" -ForegroundColor Green
    Write-Host "   Press any key to edit .env file..."
    \ = \System.Management.Automation.Internal.Host.InternalHost.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    notepad .env
}

Write-Host "
📦 Pushing to GitHub..." -ForegroundColor Cyan
git add .
git commit -m "Update FARANG.FM bot for Render"
git push origin main

Write-Host "
✅ Code pushed to GitHub!" -ForegroundColor Green

Write-Host "
📋 Next steps in Render.com:" -ForegroundColor Cyan
Write-Host "1. Go to https://dashboard.render.com" -ForegroundColor Yellow
Write-Host "2. Click 'New +' → 'Blueprint'" -ForegroundColor Yellow
Write-Host "3. Connect your GitHub repository" -ForegroundColor Yellow
Write-Host "4. Render will auto-detect render.yaml" -ForegroundColor Yellow
Write-Host "5. Add the following secrets in Render Dashboard:" -ForegroundColor Yellow
Write-Host "   - BOT_TOKEN (from @BotFather)" -ForegroundColor White
Write-Host "   - ADMIN_ID (from @userinfobot)" -ForegroundColor White
Write-Host "   - CHANNEL_ID (e.g., -1002273965696)" -ForegroundColor White
Write-Host "   - GROQ_API_KEY (from console.groq.com)" -ForegroundColor White
Write-Host "6. Click 'Apply' and wait for deployment" -ForegroundColor Yellow

Write-Host "
🔍 After deployment, check logs at:" -ForegroundColor Cyan
Write-Host "   Render Dashboard → farangfm-bot → Logs" -ForegroundColor White

Write-Host "
✅ Done!" -ForegroundColor Green
