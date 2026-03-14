# How This App Gets Deployed to AWS (The "Pizza Delivery" Version)

## The Big Picture (Feynman Style)

Imagine you want a tailored suit. You *could* hire a tailor to live in your house 24/7 (which would be crazy expensive). Or, you could just pull out your phone, send a text message, and a tailor shows up, does the job, and leaves immediately. You only pay for the 10 minutes the tailor was working.

Our Option B AWS Deployment does exactly that. 

1. **You tap a link on your phone** (sending the text message).
2. **AWS checks your secret password** (making sure it's really you).
3. **AWS summons a temporary worker** (the tailor) loaded with your Python code.
4. **The worker does its job** (scrapes jobs, writes resumes, emails you the PDFs).
5. **The worker disappears** to save you money.

Because we do it this way, your AWS bill is pennies. **~$1.44 per year** instead of a flat ~$190/year for keeping a server running 24/7!

---

## Meet the AWS Cast of Characters

Let’s translate the jargon into plain English:

| AWS Service | The Real-World Equivalent | What it does here |
|---|---|---|
| **ECR** (Elastic Container Registry) | **The Recipe Book** | This stores your `Docker` image. A Docker image is just a neat package containing your exact Python code, your resume, and Google Chrome (to scrape websites). |
| **ECS Fargate** | **The Temporary Worker** | This is the actual computer that runs your code. It's "serverless," meaning you don't own the computer. AWS lends it to you, runs your Docker package, and takes it back when finished. |
| **Lambda** | **The Fast Order-Taker** | A tiny piece of super-fast code that costs nothing to run. Its *only* job is to say: "Hey Fargate, someone tapped the link! Wake up and start the agent!" |
| **API Gateway** | **The Front Door URL** | This gives you the actual `https://...` link you can bookmark on your phone to trigger the Lambda request. |
| **CloudFormation** | **The Architect's Blueprint** | YAML files that tell AWS: "Hey, build all of the things listed above for me automatically." |

---

## How it All Deploys (The Magic Scripts)

You don't have to click around the AWS Dashboard manually. The scripts handle it all.

When you run `.\infra\deploy.ps1`, here is exactly what happens in order:

### 1. It builds the Recipe Book (ECR)
AWS reads `infra/ecr.yaml` and spins up a locker to hold your code.

### 2. It packs the Suitcase (Docker)
The script looks at your `Dockerfile` and builds a new image containing:
- Playwright/Chrome (to browse LinkedIn)
- Your `src/` modules (the Python logic)
- Your `Phani_Kumar_Kolla_profile.pdf`
- It zips this all up and uploads it to the ECR locker.

### 3. It sets the Rules for the Worker (ECS)
AWS reads `infra/ecs.yaml`. It creates the "Task Definition". This is simply a rulebook that tells the worker:
- **How strong to be:** Use exactly 0.5 CPU and 1GB RAM.
- **What to wear:** Wear the Docker image we just uploaded to ECR.
- **What to remember:** Here are Phani's secrets (`GEMINI_API_KEY`, `EMAIL_APP_PASSWORD`) so you can do your job.

### 4. It installs the Doorbell (API Gateway + Lambda)
AWS reads `infra/api_trigger.yaml`. 
- It creates the public web URL. 
- It creates the Lambda function. 
- *Crucially*, we configured the Lambda function so that when it wakes up the ECS worker, it forces the worker to run the `python -m src.main` one-shot pipeline script! If it didn't do this, the worker would accidentally start your FastAPI web dashboard and run forever!

### 5. It gives you the Keys!
The script finishes by printing out your **Trigger Token URL**. 

Bookmark this URL. Every time you tap it, the Lambda fires the one-shot Fargate task, the jobs are scraped and tailored, the PDFs hit your inbox, and the Fargate task shuts itself down immediately.

---

## What Do I Do If...

**Q: I updated my Python code. How do I send it to AWS?**
A: Just run the deploy script again! It will figure out what changed, build a new Docker image, and upload it smoothly.

**Q: I changed my Gemini API key. How does AWS know?**
A: Update your `.env` file on your laptop. Run the deploy script again. The script will notice the change and magically update the secrets embedded in your ECS worker rules.

**Q: Wait, does AWS know about the new `src/` modular layout we just made?**
A: Yes! We updated the `Dockerfile` to copy the whole `src/` folder. The Lambda function automatically targets `src.main` to run the background job, keeping everything running cleanly. You're completely good to go.
