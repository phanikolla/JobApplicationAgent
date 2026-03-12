# AI Job Application Agent

Automatically scrapes LinkedIn for Architect roles at top-tier companies, tailors a unique resume for each using AI, and emails you the PDFs - on demand, from your phone.

## How It Works

```
Phone browser tap
      → API Gateway (validates secret token)
        → Lambda (fires ECS task)
          → ECS Fargate (runs ~10 min, shuts down)
            → Email with tailored PDFs lands in inbox
```

## Prerequisites

- AWS CLI configured (`aws configure`)
- Docker installed and running
- Python 3.11+

## One-Time Deployment

**1. Fill in your config** in `infra/deploy.sh`:
```bash
SUBNET_ID="subnet-XXXXXXXXXXXXXXXXX"       # Your VPC subnet (needs internet access)
SECURITY_GROUP_ID="sg-XXXXXXXXXXXXXXXXX"   # Allow outbound 443/80
GEMINI_API_KEY="your_gemini_api_key"
EMAIL_APP_PASSWORD="your_gmail_app_password"
TRIGGER_TOKEN="your-random-secret-string"  # Make this unique
```

**2. Run the deploy script** (from project root):
```bash
chmod +x infra/deploy.sh
./infra/deploy.sh
```

This will:
- Create ECR repository
- Build and push Docker image
- Deploy ECS Cluster + Task Definition
- Deploy API Gateway + Lambda trigger
- Print your final **bookmark URL**

## Triggering the Agent

After deploy, you'll get a URL like:
```
https://xxxx.execute-api.ap-south-1.amazonaws.com/prod/trigger?token=YOUR_TOKEN
```

**On your phone:**
1. Open the URL in Safari/Chrome
2. Add to bookmarks (or "Add to Home Screen" for a one-tap shortcut)
3. Tap whenever you want to run the agent → confirmation page appears
4. Check `pkkolla24@gmail.com` in ~10 minutes for tailored resumes

## Monitoring

View logs in AWS Console:
```
CloudWatch → Log Groups → /ecs/job-application-agent
```

## Local Development

```bash
# Install deps
pip install -r requirements.txt
playwright install chromium

# Copy env template and fill in your keys
cp .env.template .env

# Run locally
python main.py
```

## Project Structure

```
├── main.py              # Pipeline orchestration
├── scraper.py           # LinkedIn scraper (Playwright)
├── tailor_agent.py      # LangGraph resume tailoring agent
├── notifier.py          # PDF generation + email dispatch
├── llm_utils.py         # Gemini/OpenAI LLM factory
├── resume_manager.py    # PDF resume parser
├── Dockerfile           # Container definition
├── requirements.txt     # Python dependencies
└── infra/
    ├── ecr.yaml         # ECR repository
    ├── ecs.yaml         # ECS Cluster + Task Definition
    ├── api_trigger.yaml # API Gateway + Lambda trigger
    └── deploy.sh        # One-shot deployment script
```

## Cost (~2 runs/week, no free tier)

| Resource | Cost |
|---|---|
| ECS Fargate compute | ~$0.43/yr |
| ECR image storage | ~$0.60/yr |
| API Gateway + Lambda | ~$0.00/yr |
| CloudWatch Logs | ~$0.25/yr |
| **Total** | **~$1.28/yr** |
