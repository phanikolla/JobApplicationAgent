# How This App Gets Deployed to AWS - The Simple Version

## The Big Picture (30-second version)

Think of this like ordering a pizza from your phone:

1. **You tap a link on your phone** (the order)
2. **AWS receives the request** and checks your secret password (the cashier)
3. **AWS spins up a temporary computer** that runs your Python code (the kitchen)
4. **The code does its job** - scrapes LinkedIn, tailors resumes with AI, generates PDFs
5. **Emails you the results** and the temporary computer shuts itself down (delivery)

You pay only for the ~10 minutes the "kitchen" was running. No idle servers. **~$1.28/year**.

---

## The Architecture in Plain English

```
📱 Your Phone
    │
    │  "Hey AWS, run my agent!"
    ▼
┌─────────────────┐     ┌───────────────┐     ┌──────────────────────────┐
│  API Gateway    │────▶│    Lambda     │────▶│   ECS Fargate Container  │
│  (Front Door)   │     │  (Doorbell)   │     │  (Temporary Worker)      │
│                 │     │              │     │                          │
│  Checks your    │     │  10 lines of │     │  Scrape → Tailor → PDF   │
│  secret token   │     │  Python that │     │  → Email                 │
│                 │     │  says "Start │     │                          │
│                 │     │  the worker" │     │  Runs ~10 min, then dies │
└─────────────────┘     └───────────────┘     └──────────────────────────┘
```

### What each piece does:

| AWS Service | Analogy | What it does |
|---|---|---|
| **ECR** | A locker | Stores your Docker image (the packaged app) |
| **ECS Fargate** | A temp worker | Runs your container on-demand, then shuts down |
| **Lambda** | A doorbell | A tiny function that "rings" ECS to start the worker |
| **API Gateway** | A front door | Gives you a URL to tap from your phone |
| **CloudFormation** | A blueprint | YAML files that tell AWS "build me all of this" |

---

## The 3 CloudFormation Stacks (The Blueprints)

The infrastructure is split into 3 YAML files, deployed in order because each one depends on the previous:

### Stack 1: [ecr.yaml](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/infra/ecr.yaml) - "Create the Locker"

Creates an ECR (Elastic Container Registry) repository named `job-application-agent`.

- **Image scanning** is turned on (security check on every push)
- **Lifecycle policy** keeps only the last 3 images (saves storage cost)
- **Exports** the repository URI so other stacks can reference it

> Think of it as: "AWS, give me a place to store my Docker images"

---

### Stack 2: [ecs.yaml](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/infra/ecs.yaml) - "Set Up the Worker"

Creates the ECS Cluster and Task Definition. This is the heaviest stack:

**What it creates:**
1. **CloudWatch Log Group** - where container logs go (kept 7 days)
2. **IAM Execution Role** - permission slip so ECS can pull images and write logs
3. **ECS Cluster** - a logical grouping named `job-agent-cluster`
4. **Task Definition** - the "recipe card" that says:
   - Use **0.5 vCPU** and **1 GB RAM**
   - Run on **Fargate** (serverless, no EC2 to manage)
   - Pull the Docker image from ECR
   - Inject these **environment variables**: `GEMINI_API_KEY`, `EMAIL_SENDER`, `EMAIL_APP_PASSWORD`, `RESUME_PATH`
   - Send logs to CloudWatch

**Takes as input (Parameters):**
- `ImageUri` - which Docker image to run
- `GeminiApiKey`, `EmailSender`, `EmailAppPassword` - your secrets
- `SubnetId`, `SecurityGroupId` - your VPC networking config

**Exports** cluster name, task definition ARN, subnet, and security group for the next stack.

> Think of it as: "AWS, here's the recipe. When I say 'go', run this container with these settings."

---

### Stack 3: [api_trigger.yaml](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/infra/api_trigger.yaml) - "Install the Doorbell"

Creates the phone-tappable trigger URL. This is the clever part:

**What it creates:**
1. **Lambda IAM Role** - permission to call `ecs:RunTask` and `iam:PassRole`
2. **Lambda Function** (`job-agent-trigger`) - a tiny inline Python function that:
   - Checks the `?token=` in the URL matches your secret
   - If valid, calls `ecs.run_task()` to fire up the Fargate container
   - Returns a friendly HTML page: "Agent Triggered! Check your email in ~10 min"
3. **HTTP API Gateway** - creates the public URL
4. **Route** - maps `GET /trigger` to the Lambda function
5. **Stage** - deploys under `/prod` with auto-deploy
6. **Lambda Permission** - allows API Gateway to invoke the Lambda

**Imports** from Stack 2: cluster name, task definition ARN, subnet, security group.

**Final output**: A URL like:
```
https://abc123.execute-api.us-east-1.amazonaws.com/prod/trigger?token=YOUR_SECRET
```

> Think of it as: "AWS, give me a URL. When someone visits it with the right password, start my agent."

---

## The Deploy Script - What Happens When You Run It

The [deploy.ps1](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/infra/deploy.ps1) script does 5 things in sequence:

```
Step 1 ──▶ Step 2 ──▶ Step 3 ──▶ Step 4 ──▶ Step 5
 ECR       Docker      Push       ECS        API
 repo      build       image     cluster    gateway
```

### Step-by-Step Breakdown:

#### Step 0: Load Secrets
```
.env file ──▶ Script reads GEMINI_API_KEY, EMAIL_SENDER, 
              EMAIL_APP_PASSWORD, TRIGGER_TOKEN
```
The script reads your [.env](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/.env) file and loads all secrets into memory. Also pulls your AWS Account ID automatically via `aws sts get-caller-identity`.

#### Step 1: Create ECR Repository
```powershell
aws cloudformation deploy --template-file infra/ecr.yaml --stack-name job-agent-ecr
```
Deploys [ecr.yaml](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/infra/ecr.yaml). Creates the Docker image storage. **Idempotent** - safe to run multiple times.

#### Step 2: Build Docker Image
```powershell
docker login ...    # Authenticate Docker to your private ECR
docker build -t job-application-agent .   # Build the image
docker tag ... :latest   # Tag it for ECR
```
Builds your [Dockerfile](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/Dockerfile):
- Starts from `python:3.11-slim`
- Installs Chromium system dependencies (needed by Playwright for browser automation)
- Installs Python packages from [requirements.txt](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/requirements.txt)
- Installs Playwright + Chromium browser
- Copies your Python code and master resume PDF
- Sets `CMD ["python", "main.py"]` as the entry point

#### Step 3: Push to ECR
```powershell
docker push $ECR_IMAGE_URI
```
Uploads the ~500MB image to your private ECR repository.

#### Step 4: Deploy ECS
```powershell
aws cloudformation deploy --template-file infra/ecs.yaml --stack-name job-agent-ecs \
  --parameter-overrides ImageUri=... GeminiApiKey=... EmailSender=... ...
```
Deploys the cluster, task definition, IAM role, and log group. Passes all your secrets as parameters.

#### Step 5: Deploy API Gateway + Lambda
```powershell
aws cloudformation deploy --template-file infra/api_trigger.yaml --stack-name job-agent-api \
  --parameter-overrides TriggerToken=YOUR_TOKEN
```
Deploys the Lambda trigger and API Gateway. Prints your bookmark URL at the end.

---

## What Happens When You Tap the URL

Here's the full chain reaction:

```
1. Phone taps: GET /trigger?token=abc123
       │
2. API Gateway receives it, forwards to Lambda
       │
3. Lambda checks: does token == my secret?
       │          NO → 403 Forbidden
       │          YES ↓
4. Lambda calls ecs.run_task() with:
       - cluster: job-agent-cluster
       - task definition: job-application-agent
       - subnet + security group (for internet access)
       - assignPublicIp: ENABLED (needs internet to scrape LinkedIn)
       │
5. ECS provisions a Fargate container:
       - Allocates 0.5 vCPU + 1 GB RAM
       - Pulls Docker image from ECR
       - Injects environment variables
       - Runs: python main.py
       │
6. main.py executes the pipeline:
       ① Parse master resume (pdfplumber)
       ② Scrape LinkedIn with Playwright (headless Chromium)
       ③ For each job: Gemini AI extracts keywords + tailors resume
       ④ Generate PDF for each tailored resume (Playwright)
       ⑤ Email all PDFs to pkkolla24@gmail.com
       │
7. Container exits → Fargate stops billing → done
```

---

## Prerequisites Checklist

Before running the deploy script, you need:

| # | What | How to get it |
|---|---|---|
| 1 | **AWS CLI** configured | `aws configure` with your Access Key + Secret Key |
| 2 | **Docker Desktop** running | Install from docker.com, make sure it's started |
| 3 | **[.env](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/.env) file** with secrets | `cp .env.template .env` and fill in values |
| 4 | **Gemini API Key** | Get from [Google AI Studio](https://aistudio.google.com/apikey) |
| 5 | **Gmail App Password** | Google Account → Security → 2FA → App Passwords |
| 6 | **VPC Subnet ID** | `aws ec2 describe-subnets --output table` - pick a public subnet |
| 7 | **Security Group ID** | `aws ec2 describe-security-groups` - needs outbound 443/80 |
| 8 | **Trigger Token** | `python -c "import uuid; print(uuid.uuid4())"` |

---

## The One Command to Deploy Everything

**Windows (PowerShell):**
```powershell
.\infra\deploy.ps1
```

**Mac/Linux:**
```bash
chmod +x infra/deploy.sh && ./infra/deploy.sh
```

That's it. One command creates all 3 stacks, builds and pushes Docker, and gives you a URL.

---

## Quick Reference: Files Involved

| File | Purpose |
|---|---|
| [ecr.yaml](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/infra/ecr.yaml) | CloudFormation: Docker image storage |
| [ecs.yaml](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/infra/ecs.yaml) | CloudFormation: ECS cluster + task definition |
| [api_trigger.yaml](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/infra/api_trigger.yaml) | CloudFormation: API Gateway + Lambda |
| [deploy.ps1](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/infra/deploy.ps1) | Windows deploy script (runs all 5 steps) |
| [deploy.sh](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/infra/deploy.sh) | Mac/Linux deploy script |
| [Dockerfile](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/Dockerfile) | Container recipe (Python + Playwright + Chromium) |
| [.env.template](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/.env.template) | Template for your secrets |

---

## Common "Wait, but..." Questions

**Q: Where do my secrets live?**
In the [.env](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/.env) file on your machine (gitignored). During deployment, they get passed as CloudFormation parameters into the ECS Task Definition as environment variables. They never get committed to Git.

**Q: What if I update my code?**
Re-run the deploy script. Steps 1 and 4-5 will detect "no changes" and skip. Steps 2-3 will rebuild and push the new image. Then manually trigger the agent.

**Q: What if I rotate my Gemini API key?**
Update [.env](file:///c:/S%20T%20U%20D%20Y/JobApplicationAgent/.env) and re-run the deploy script (it will update the ECS task definition). Or use `aws ecs register-task-definition` directly for a faster update.

**Q: What's this "Fargate" thing?**
It means "serverless containers." You don't manage any EC2 instances. AWS handles the servers. You just say "run this container" and AWS handles the rest. You pay per-second of compute used.

**Q: Why Lambda + API Gateway instead of just running ECS directly?**
Because Fargate tasks can't be triggered by a URL directly. You need something to "translate" the HTTP request into a `RunTask` API call. Lambda is that translator, and API Gateway gives it a public URL.

**Q: Why 3 separate CloudFormation stacks instead of 1?**
Separation of concerns. If you need to update just the Lambda code (stack 3), you don't risk touching your ECS cluster (stack 2). Each stack can be updated independently.
