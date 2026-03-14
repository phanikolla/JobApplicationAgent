# =============================================================================
# deploy-gcp.ps1 - Deploy Job Application Agent to Google Cloud Run ($0/mo)
# =============================================================================
$ErrorActionPreference = "Stop"

# 1. Load Secrets from .env
if (Test-Path ".env") {
    Get-Content ".env" | Where-Object { $_ -match "^\s*[^#]" } | ForEach-Object {
        $parts = $_ -split "=", 2
        if ($parts.Count -eq 2) {
            [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim().Trim('"'), "Process")
        }
    }
} else {
    Write-Host "ERROR: .env file not found. Copy .env.template to .env and fill in your keys." -ForegroundColor Red
    exit 1
}

$GEMINI_API_KEY     = $env:GEMINI_API_KEY
$EMAIL_SENDER       = $env:EMAIL_SENDER
$EMAIL_APP_PASSWORD = $env:EMAIL_APP_PASSWORD

if (-not $GEMINI_API_KEY -or -not $EMAIL_APP_PASSWORD) {
    Write-Host "ERROR: Missing secrets in .env. Please fill in GEMINI_API_KEY and EMAIL_APP_PASSWORD." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  Job Application Agent -> Google Cloud Run"    -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This will build your Docker container and deploy it to a free HTTPS URL." -ForegroundColor Yellow
Write-Host "Make sure you have run 'gcloud auth login' and 'gcloud config set project YOUR_PROJECT_ID'." -ForegroundColor Yellow

# 2. Deploy to Cloud Run
# - Allocates 1 CPU and 2GB RAM 
# - Sets concurrency to 1 (one user at a time) to prevent Chromium out-of-memory crashes
# - Passes in secrets securely as environment variables
Write-Host ""
Write-Host "Deploying to Cloud Run... (This usually takes 2-3 minutes)" -ForegroundColor Green

gcloud run deploy job-agent `
    --source . `
    --region us-central1 `
    --allow-unauthenticated `
    --memory 2Gi `
    --cpu 1 `
    --concurrency 1 `
    --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY,EMAIL_SENDER=$EMAIL_SENDER,EMAIL_APP_PASSWORD=$EMAIL_APP_PASSWORD"

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "  DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "  Use the URL provided above to access your dashboard safely from anywhere." -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
