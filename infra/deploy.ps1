# =============================================================================
# deploy.ps1 - PowerShell deployment script for AI Job Application Agent
#
# SETUP: Copy .env.template to .env and fill in your secrets.
#        Then fill in your AWS subnet/security group below.
# =============================================================================
$ErrorActionPreference = "Stop"
$env:AWS_PAGER = "aws"

# ---------------------------------------------------------------------------
# CONFIGURATION - Fill these in (DO NOT hardcode real secrets here)
# ---------------------------------------------------------------------------
$AWS_REGION        = "us-east-1"
$AWS_ACCOUNT_ID    = (aws sts get-caller-identity --query Account --output text)
$ECR_IMAGE_URI     = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/job-application-agent:latest"
$SUBNET_ID         = "subnet-0599d5337217d34dd"
$SECURITY_GROUP_ID = "sg-0976206f4b6b36d52"

# Load secrets from .env file (never hardcode these)
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
$TRIGGER_TOKEN      = $env:TRIGGER_TOKEN

if (-not $GEMINI_API_KEY -or -not $EMAIL_APP_PASSWORD) {
    Write-Host "ERROR: Missing secrets in .env. Please fill in GEMINI_API_KEY and EMAIL_APP_PASSWORD." -ForegroundColor Red
    exit 1
}

if (-not $TRIGGER_TOKEN) {
    Write-Host "ERROR: TRIGGER_TOKEN not set in .env file." -ForegroundColor Red
    Write-Host "Generate one with: python -c `"import uuid; print(uuid.uuid4())`"" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  AI Job Application Agent - AWS Deployment"   -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# STEP 1: ECR
Write-Host "[1/5] Creating ECR repository..." -ForegroundColor Yellow
aws cloudformation deploy `
  --template-file infra/ecr.yaml `
  --stack-name job-agent-ecr `
  --region $AWS_REGION `
  --capabilities CAPABILITY_NAMED_IAM

# STEP 2: Docker build
Write-Host "[2/5] Building Docker image..." -ForegroundColor Yellow
$loginPassword = aws ecr get-login-password --region $AWS_REGION
$loginPassword | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
docker build -t job-application-agent .
docker tag job-application-agent:latest $ECR_IMAGE_URI

# STEP 3: Push to ECR
Write-Host "[3/5] Pushing image to ECR..." -ForegroundColor Yellow
docker push $ECR_IMAGE_URI

# STEP 4: ECS
Write-Host "[4/5] Deploying ECS Cluster + Task Definition..." -ForegroundColor Yellow
aws cloudformation deploy `
  --template-file infra/ecs.yaml `
  --stack-name job-agent-ecs `
  --region $AWS_REGION `
  --capabilities CAPABILITY_NAMED_IAM `
  --parameter-overrides `
    ImageUri=$ECR_IMAGE_URI `
    GeminiApiKey=$GEMINI_API_KEY `
    EmailSender=$EMAIL_SENDER `
    "EmailAppPassword=$EMAIL_APP_PASSWORD" `
    SubnetId=$SUBNET_ID `
    SecurityGroupId=$SECURITY_GROUP_ID

# STEP 5: API trigger
Write-Host "[5/5] Deploying API Gateway trigger..." -ForegroundColor Yellow
aws cloudformation deploy `
  --template-file infra/api_trigger.yaml `
  --stack-name job-agent-api `
  --region $AWS_REGION `
  --capabilities CAPABILITY_NAMED_IAM `
  --parameter-overrides TriggerToken=$TRIGGER_TOKEN

# Print URL
Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "  DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
$API_ID = aws cloudformation describe-stacks `
  --stack-name job-agent-api `
  --region $AWS_REGION `
  --query "Stacks[0].Outputs[?OutputKey=='ApiId'].OutputValue" `
  --output text
$TRIGGER_URL = "https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/trigger?token=${TRIGGER_TOKEN}"
Write-Host "  Bookmark this URL on your phone:" -ForegroundColor Cyan
Write-Host "  $TRIGGER_URL" -ForegroundColor Green
Write-Host ""
Write-Host "  Tap to trigger the agent. Results in ~10 minutes." -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Green
