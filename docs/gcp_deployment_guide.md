# How to Deploy to Google Cloud Run (The $0 Forever Plan)

This guide walks you through deploying your AI Job Application Agent to Google Cloud Run. 

**Why Google Cloud Run?**
Because you want a public Dashboard available 24/7 for exactly $0.00. Cloud Run natively supports "Scale to Zero." When you close the dashboard tab, your server turns off and stops billing. Google gives you 360,000 seconds of free compute *every single month*, which is enough to tailor thousands of resumes for free.

---

## 🚀 Step 1: Install the Google Cloud CLI

If you don't already have the `gcloud` tool installed on your computer, you need it!

1. Download the [Google Cloud CLI Installer](https://cloud.google.com/sdk/docs/install#windows) for Windows.
2. Run the installer.
3. Once installed, open a fresh PowerShell window and log in:
   ```powershell
   gcloud auth login
   ```
4. A web browser will open asking you to log into your Google Account.

---

## 🏗️ Step 2: Create a Google Cloud Project

If you haven't made a Google Cloud Project yet:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the dropdown at the top left and select **New Project**.
3. Name it something like `job-agent-prod` and click **Create**.
4. In your terminal, tell the `gcloud` tool to use this new project (replace `YOUR_PROJECT_ID` with the actual ID from the console):
   ```powershell
   gcloud config set project YOUR_PROJECT_ID
   ```
5. **CRITICAL:** You must enable Billing on the project. (Google requires a credit card to prevent abuse, but Cloud Run is covered by the Always Free tier).

---

## 🔑 Step 3: Enable the Services

You need to tell Google Cloud you intend to use Cloud Run and Cloud Build. Run this in your terminal:

```powershell
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

---

## 🚢 Step 4: Deploy the App!

You are ready! Ensure your `.env` file has your `GEMINI_API_KEY` and your `EMAIL_APP_PASSWORD` inside it. Then run the deployment script:

```powershell
.\infra\deploy-gcp.ps1
```

**What the script does for you automatically:**
1. It reads your `.env` file to grab your secrets.
2. It packages up your code, your resume, and the Playwright Chrome Browser into a Container.
3. It sends it to Google Cloud Build.
4. It sets the container to use **2 GB of Memory** and **1 CPU** (so the Chrome browser doesn't crash).
5. It limits the "Concurrency" to 1 (meaning it processes one tailored resume at a time to prevent memory spikes).
6. It passes your Secrets securely into the container.

When the script finishes (it takes about 3-5 minutes), it will print out a permanent URL that looks like this:
`https://job-agent-xxxxx-uc.a.run.app`

Bookmark that URL! That is your free, 24/7 web dashboard.
