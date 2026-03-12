# Project Tasks

## 1. Environment Setup
- [x] Initialize Python environment and structure.
- [/] Install dependencies (e.g., `playwright`, `langchain`, `pdfkit`).
- [x] Create `.env` template for API credentials.

## 2. Skill 1: LinkedIn Job Scraper
- [ ] Implement headless scraper (Playwright) to fetch jobs.
- [ ] Filter by "Solutions Architect", "India", "Past 24 Hours".
- [ ] Extract full text for the top 3 job postings.

## 3. Skill 2: Master Resume Retrieval
- [ ] Implement Google Drive file downloader for the master resume link.
- [ ] Parse the downloaded PDF and convert it to structured Markdown.

## 4. Skill 3: ATS Keyword & Tailoring Subagent
- [ ] Build LLM chain to extract required keywords and skills from JD.
- [ ] Build LLM chain to adapt the master resume to the JD constraints (zero hallucination).
- [ ] Produce 3 unique tailored resumes in Markdown format.

## 5. Skill 4: PDF Formatting
- [ ] Implement a tool (e.g., PyMuPDF, ReportLab, or Markdown-to-PDF) to compile resumes cleanly formatted.
- [ ] Verify formatting looks ATS-friendly.

## 6. Skill 5: Summary Reporting & Dispatch
- [ ] Build logic to summarize the 3 jobs and rationale.
- [ ] Build SMTP email script to dispatch the summary + 3 PDF attachments to `pkkolla24@gmail.com`.

## 7. Workflow Orchestration (Main)
- [ ] Set up LangGraph state schema and nodes (`scraper`, `retriever`, `tailor`, `formatter`, `notifier`).
- [ ] Tie all functions together into a `main.py` LangGraph pipeline.
- [x] Perform end-to-end testing and validation.
