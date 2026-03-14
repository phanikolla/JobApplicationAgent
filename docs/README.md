<div align="center">

# 🤖 AI Job Application Agent

**Scrapes LinkedIn. Tailors resumes with AI. Emails you PDFs. Repeat.**  
*Trigger from your phone. Results in your inbox in ~10 minutes.*

<br/>

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic%20AI-blueviolet?style=for-the-badge&logo=chainlink&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Gemini](https://img.shields.io/badge/Gemini-2.5%20Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![AWS](https://img.shields.io/badge/AWS-ECS%20Fargate-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)](https://aws.amazon.com/fargate/)
[![Cost](https://img.shields.io/badge/Cost-~%241.28%2Fyear-22c55e?style=for-the-badge&logo=amazonwebservices&logoColor=white)]()
[![License](https://img.shields.io/badge/License-MIT-gray?style=for-the-badge)](LICENSE)

<br/>

<img width="700" src="https://raw.githubusercontent.com/phanikolla/JobApplicationAgent/main/assets/banner.png" alt="AI Job Application Agent Banner" onerror="this.style.display='none'"/>

</div>

---

## ✨ What It Does

Every time you tap a **single bookmark on your phone**, this agent:

| Step | Action |
|:---:|---|
| 🔍 | Scrapes LinkedIn for Architect roles at **Fortune 500 / Big Tech** companies posted in India |
| 🧠 | Sends each job description + your master resume to **Gemini AI** for ATS keyword analysis |
| 📝 | Tailors a **unique, optimized resume** for every single role |
| 📄 | Converts each resume into a **clean, professional PDF** |
| 📧 | Emails all tailored PDFs directly to your inbox |

> **Target Roles:** Solutions Architect · Gen AI Architect · AI Architect · Technical Architect · Agentic AI Architect  
> **Target Market:** India · Top-Tier Global Enterprises · Big Tech · Fortune 500 only

---

## 🏗️ Architecture

```
📱 Your Phone (browser bookmark)
        │
        │  GET /trigger?token=****
        ▼
┌───────────────────┐
│   API Gateway     │  ← Validates secret token
│   (HTTP API)      │
└────────┬──────────┘
         │  invoke
         ▼
┌───────────────────┐
│   AWS Lambda      │  ← 10 lines of Python
│   (Trigger fn)    │     calls ecs.run_task()
└────────┬──────────┘
         │  run task
         ▼
┌─────────────────────────────────────────────┐
│           ECS Fargate Container             │
│                                             │
│  ① Playwright  →  scrape LinkedIn jobs      │
│  ② LangGraph   →  extract ATS keywords      │
│  ③ Gemini AI   →  tailor each resume        │
│  ④ Playwright  →  render PDF                │
│  ⑤ SMTP        →  email PDFs to you         │
│                                             │
│  Runtime: ~10 min  │  Self-terminates ✓     │
└─────────────────────────────────────────────┘
         │
         ▼
📧  pkkolla24@gmail.com
    3 tailored PDFs attached
```

---

## 💸 Cost

> Deployed on **AWS ECS Fargate** — pay only when it runs. Zero idle cost.

| Resource | ~2 runs/week (104/year) |
|---|---|
| ECS Fargate compute (0.5 vCPU · 1 GB · 10 min) | $0.43 / yr |
| ECR image storage (~500 MB) | $0.60 / yr |
| API Gateway + Lambda (104 invocations) | < $0.01 / yr |
| CloudWatch Logs | $0.25 / yr |
| SSM Parameter Store (secrets) | $0.00 (always free) |
| **Total** | **~$1.28 / year** |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **AI / LLM** | Google Gemini 2.5 Flash via LangChain |
| **Agent Framework** | LangGraph (stateful multi-node pipeline) |
| **Browser Automation** | Playwright (headless Chromium) |
| **PDF Generation** | Playwright PDF renderer |
| **Resume Parsing** | pdfplumber |
| **Email Dispatch** | Gmail SMTP |
| **Container** | Docker on Python 3.11-slim |
| **Cloud Runtime** | AWS ECS Fargate |
| **HTTP Trigger** | AWS API Gateway (HTTP API) + Lambda |
| **Infrastructure** | AWS CloudFormation |

---

## 🚀 Deployment (One-Time Setup)

### Prerequisites
- AWS CLI configured (`aws configure`)
- Docker Desktop running
- Python 3.11+

### 1. Clone & configure secrets

```bash
git clone https://github.com/phanikolla/JobApplicationAgent.git
cd JobApplicationAgent

# Fill in your keys
cp .env.template .env
```

Edit `.env`:
```env
GEMINI_API_KEY="your_gemini_api_key"
EMAIL_SENDER="you@gmail.com"
EMAIL_APP_PASSWORD="your_gmail_app_password"
```

### 2. Configure `infra/deploy.ps1` (Windows) or `infra/deploy.sh` (Mac/Linux)

Open the file and fill in:
```
SUBNET_ID          = "subnet-XXXXXXXXXXXXXXXXX"   # your VPC public subnet
SECURITY_GROUP_ID  = "sg-XXXXXXXXXXXXXXXXX"       # allow outbound 443/80
TRIGGER_TOKEN      = "your-random-secret-string"  # keep this private
```

> **Find your subnet:** `aws ec2 describe-subnets --output json`

### 3. Deploy (single command)

**Windows:**
```powershell
.\infra\deploy.ps1
```

**Mac / Linux:**
```bash
chmod +x infra/deploy.sh && ./infra/deploy.sh
```

The script will:
1. Create an ECR repository
2. Build and push the Docker image
3. Deploy ECS Cluster + Task Definition
4. Deploy API Gateway + Lambda trigger
5. **Print your phone bookmark URL** ✅

---

## 📱 Usage — Trigger From Your Phone

After deployment you'll get a URL like:
```
https://xxxx.execute-api.us-east-1.amazonaws.com/prod/trigger?token=YOUR_TOKEN
```

**Add to your phone home screen:**
- **iPhone:** Safari → Share → *Add to Home Screen*
- **Android:** Chrome → Menu (⋮) → *Add to Home Screen*

One tap → instant confirmation page → **tailored PDFs in your inbox in ~10 min.**

---

## 📁 Project Structure

```
JobApplicationAgent/
│
├── 🐍 Core Agent
│   ├── main.py              # Pipeline orchestrator
│   ├── scraper.py           # LinkedIn scraper (Playwright + BS4)
│   ├── tailor_agent.py      # LangGraph resume tailoring agent
│   ├── notifier.py          # PDF generation + Gmail dispatch
│   ├── llm_utils.py         # Gemini / OpenAI LLM factory
│   └── resume_manager.py    # PDF resume text extractor
│
├── 🐳 Container
│   ├── Dockerfile           # python:3.11-slim + Playwright
│   └── requirements.txt     # Production dependencies
│
├── ☁️ Infrastructure (CloudFormation)
│   ├── infra/ecr.yaml       # ECR repository
│   ├── infra/ecs.yaml       # ECS Cluster + Fargate Task Definition
│   ├── infra/api_trigger.yaml  # API Gateway + Lambda trigger
│   ├── infra/deploy.ps1     # Windows one-shot deploy script
│   └── infra/deploy.sh      # Mac/Linux one-shot deploy script
│
└── 📋 Config & Docs
    ├── .env.template        # Secret keys template
    ├── .gitignore           # Excludes .env, venv, outputs
    ├── .dockerignore        # Lean image (excludes dev/docs)
    └── README.md
```

---

## 🔍 How the AI Pipeline Works

```
Job Description
      +
Master Resume
      │
      ▼
┌─────────────────────┐
│  Node 1: Keywords   │  Extracts top 15 ATS keywords from JD
│  (Gemini, temp=0)   │  Output: JSON list of skills/tools
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Node 2: Tailor     │  Rewrites resume to match JD
│  (Gemini, temp=0.2) │  Integrates keywords naturally
└──────────┬──────────┘  No hallucination - real experience only
           │
           ▼
      Markdown Resume
           │
           ▼
┌─────────────────────┐
│  PDF Generator      │  Playwright renders styled HTML → PDF
│  (Chromium)         │  Inter font, ATS-safe formatting
└──────────┬──────────┘
           │
           ▼
      Resume PDF
```

---

## 🔐 Security

- **No secrets in code** — all credentials loaded from `.env` at runtime
- **API key auth** — trigger URL protected by a secret token
- **`.env` is gitignored** — keys never leave your machine
- **ECR image scanning** — enabled on push

---

## 📬 Sample Email Output

```
Subject: Daily Agent Report: Tailored Job Applications Ready

Here are the tailored resumes for today's top matches:

### Solutions Architect @ Google
- Link: https://linkedin.com/jobs/...
- Status: ✅ PDF Generated

### AI Architect @ Microsoft  
- Link: https://linkedin.com/jobs/...
- Status: ✅ PDF Generated

### Technical Architect @ Amazon
- Link: https://linkedin.com/jobs/...
- Status: ✅ PDF Generated

[3 PDF attachments]
```

---

## 🤝 Contributing

This is a personal automation tool, but PRs are welcome for:
- Improving LinkedIn scraping resilience
- Adding more job boards (Naukri, Indeed)
- Better top-tier company detection
- Enhanced PDF formatting

---

<div align="center">

**Built with ❤️ by [Phani Kumar Kolla](https://github.com/phanikolla)**

*If this saves you time on your job hunt, give it a ⭐*

</div>
