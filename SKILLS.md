---
description: AI Job Application Agent Core Skills and Workflows
---
# AI Job Application Agent - Skills

This document defines the specific skills, capabilities, and workflows the agent must implement to automate the job application process end-to-end.

## Skill 1: LinkedIn Job Scraping
**Description**: The ability to search, filter, and extract job postings from LinkedIn programmatically.
- **Workflow Steps**:
  1. Initialize web scraping subagent or use appropriate LinkedIn API/networking tools.
  2. Navigate to LinkedIn Jobs search.
  3. Apply mandatory filters: 
     - Keyword: "Solutions Architect" (or "Gen AI Architect", "AI Architect", "Technical Architect", "Agentic AI Architect")
     - Company: Evaluate dynamically; MUST be a Top-Tier Global, Big Tech, or Fortune 500 company.
     - Location: "India"
     - Time: "Past 24 hours"
  4. Extract the top matching job postings (prioritizing the most relevant ones to present exactly 3 top-tier options).
  5. Parse and save: Job Title, Company Name, Job Description context, and Application URL.
  6. Store the structured data temporarily for the tailoring phase.

## Skill 2: Master Resume Retrieval & Parsing
**Description**: The ability to fetch and ingest the user's master resume.
- **Workflow Steps**:
  1. Access the master resume from: `https://drive.google.com/file/d/1sGCVwkP0bbHnnlptbLtR4lmQmjnUkQPH/view?usp=drive_link`.
  2. Download the document and parse its contents.
  3. Convert the parsed content into a highly structured markdown format to make it easy for the LLM to process and manipulate sections.

## Skill 3: ATS Keyword Optimization & Resume Tailoring
**Description**: The core AI capability to cross-reference a job description with the master resume to create a highly optimized, distinct resume for the role.
- **Workflow Steps**:
  1. Iterate over each scraped job description.
  2. Analyze the job description for primary ATS keywords, required skills, and core competencies.
  3. Feed both the job description and the parsed master resume into the tailoring pipeline.
  4. Intelligently adapt bullet points, rewrite summaries, and highlight relevant experience, matching the scraped ATS keywords naturally. Do not fabricate experience.
  5. Format Rule: NEVER generate em-dashes (`—`) anywhere in the output. Use standard hyphens (`-`) instead.
  6. Output a unique, tailored markdown version of the resume for each specific role.

## Skill 4: PDF Formatting & Generation
**Description**: The ability to convert the tailored text into clean, professional, ATS-friendly PDFs.
- **Workflow Steps**:
  1. Employ a programmatic document generator (e.g., a Python/Node library like ReportLab, pdfkit, puppeteer, or pandoc).
  2. Apply standard, professional formatting (clear headings, standard fonts, bullet points, standard margins) that guarantees ATS readability.
  3. Render the tailored markdown resumes into separate PDF files named effectively (e.g., `Company_Role_Resume.pdf`).

## Skill 5: Summary Reporting & Email Dispatch
**Description**: The ability to package the daily results into an executive summary and deliver it to the user.
- **Workflow Steps**:
  1. Generate a daily summary report detailing:
     - The 3 selected jobs (Company, Title, Link).
     - Brief highlighting why they match based on the master resume.
     - Status of the tailored resumes.
  2. Format this summary report into a clear PDF or professional HTML email body.
  3. Initialize an email dispatch script or integration.
  4. Set recipient to: `pkkolla24@gmail.com`.
  5. Subject: "Daily Agent Report: 3 Tailored Job Applications Ready".
  6. Send the email with the summary and the 3 tailored PDF resumes attached.
