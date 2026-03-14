#!/usr/bin/env bash
# =============================================================================
# deploy.sh - One-shot deployment script for AI Job Application Agent
# Run this ONCE to set up everything on AWS.
# After this, just tap your phone bookmark to trigger the agent.
#
# SETUP: Copy .env.template to .env and fill in your secrets.
#        Then fill in your AWS subnet/security group below.
# =============================================================================
set -e

# ---------------------------------------------------------------------------
# CONFIGURATION - Fill these in (DO NOT commit real values)
# ---------------------------------------------------------------------------
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/job-application-agent:latest"

# Your VPC settings (run 'aws ec2 describe-subnets' to find these)
SUBNET_ID="subnet-0599d5337217d34dd"
SECURITY_GROUP_ID="sg-0976206f4b6b36d52"

# Load secrets from .env (never hardcode these here)
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

GEMINI_API_KEY="${GEMINI_API_KEY:-}"
EMAIL_SENDER="${EMAIL_SENDER:-}"
EMAIL_APP_PASSWORD="${EMAIL_APP_PASSWORD:-}"
TRIGGER_TOKEN="${TRIGGER_TOKEN:-}"

if [ -z "$GEMINI_API_KEY" ] || [ -z "$EMAIL_APP_PASSWORD" ]; then
  echo "ERROR: Missing secrets. Copy .env.template to .env and fill in your keys."
  exit 1
fi

if [ -z "$TRIGGER_TOKEN" ]; then
  echo "ERROR: TRIGGER_TOKEN not set in .env file."
  echo "Generate one with: python -c \"import uuid; print(uuid.uuid4())\""
  exit 1
fi

echo ""
echo "=============================================="
echo "  AI Job Application Agent - AWS Deployment"
echo "=============================================="
echo ""

# STEP 1: Deploy ECR Repository
echo "[1/5] Creating ECR repository..."
aws cloudformation deploy \
  --template-file infra/ecr.yaml \
  --stack-name job-agent-ecr \
  --region "$AWS_REGION" \
  --capabilities CAPABILITY_NAMED_IAM

# STEP 2: Build Docker image
echo ""
echo "[2/5] Building Docker image..."
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

docker build -t job-application-agent .
docker tag job-application-agent:latest "$ECR_IMAGE_URI"

# STEP 3: Push image to ECR
echo ""
echo "[3/5] Pushing image to ECR..."
docker push "$ECR_IMAGE_URI"

# STEP 4: Deploy ECS Cluster + Task Definition
echo ""
echo "[4/5] Deploying ECS Cluster and Task Definition..."
aws cloudformation deploy \
  --template-file infra/ecs.yaml \
  --stack-name job-agent-ecs \
  --region "$AWS_REGION" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ImageUri="$ECR_IMAGE_URI" \
    GeminiApiKey="$GEMINI_API_KEY" \
    EmailSender="$EMAIL_SENDER" \
    EmailAppPassword="$EMAIL_APP_PASSWORD" \
    SubnetId="$SUBNET_ID" \
    SecurityGroupId="$SECURITY_GROUP_ID"

# STEP 5: Deploy API Gateway + Lambda Trigger
echo ""
echo "[5/5] Deploying API Gateway trigger..."
aws cloudformation deploy \
  --template-file infra/api_trigger.yaml \
  --stack-name job-agent-api \
  --region "$AWS_REGION" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    TriggerToken="$TRIGGER_TOKEN"

# Print bookmark URL
echo ""
echo "=============================================="
echo "  DEPLOYMENT COMPLETE!"
echo "=============================================="
API_ID=$(aws cloudformation describe-stacks \
  --stack-name job-agent-api \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiId'].OutputValue" \
  --output text)
TRIGGER_URL="https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/trigger?token=${TRIGGER_TOKEN}"
echo ""
echo "  Bookmark this URL on your phone:"
echo "  $TRIGGER_URL"
echo ""
echo "  Tap to fire the agent. Email arrives in ~10 minutes."
echo "=============================================="
