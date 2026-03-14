import asyncio
import logging
import os
from dotenv import load_dotenv

from src.core.config import load_config
from src.scrapers.linkedin_search import scrape_linkedin_jobs
from src.models.resume_manager import parse_resume
from src.agents.tailor_agent import tailor_for_job
from src.utils.notifier import generate_pdf, send_summary_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_agent_pipeline():
    cfg = load_config()
    logger.info("=== STARTING AI JOB APPLICATION AGENT ===")
    
    # 1. Retrieve Master Resume
    logger.info("Phase 1: Retrieving Master Resume")
    pdf_path = os.getenv("RESUME_PATH", cfg.profile.resume_path)
    
    if not os.path.exists(pdf_path):
        logger.error(f"Local master resume not found at {pdf_path}. Exiting.")
        return
        
    master_text = parse_resume(pdf_path)
    if not master_text:
        logger.error("Failed to parse master resume text. Exiting.")
        return
        
    # 2. Scrape Jobs
    logger.info("Phase 2: Scraping LinkedIn Jobs")
    jobs = await scrape_linkedin_jobs(
        keywords=cfg.job_search.search_keywords, 
        location=cfg.job_search.search_location, 
        time_filter=cfg.job_search.time_filter,
        limit=cfg.job_search.job_limit
    )
    
    if not jobs:
        logger.warning("No jobs found matching criteria.")
        return
        
    logger.info(f"Found {len(jobs)} jobs. Proceeding to tailoring.")
    
    # 3. Optimize and Tailor
    logger.info("Phase 3 & 4: Tailoring Resumes and Generating PDFs")
    
    pdf_attachments = []
    summary_lines = [
        "# Daily AI Job Agent Report",
        "Here are the tailored resumes for today's top matches:",
        ""
    ]
    
    # Ensure output directory exists
    os.makedirs(cfg.output_dir, exist_ok=True)
    
    for i, job in enumerate(jobs):
        logger.info(f"--- Processing Job {i+1}: {job['title']} at {job['company']} ---")
        
        try:
            # Generate Tailored Markdown
            tailored_md = tailor_for_job(
                job_title=job['title'],
                company_name=job['company'],
                job_description=job['description'],
                master_resume_text=master_text
            )
            
            # Save Markdown (for backup/review)
            safe_company = "".join(x for x in job['company'] if x.isalnum() or x in " _-").strip()
            md_path = f"{cfg.output_dir}/Tailored_{safe_company}.md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(tailored_md)
                
            # Generate PDF
            pdf_out_path = f"{cfg.output_dir}/Resume_{safe_company}.pdf"
            generated_pdf = await generate_pdf(tailored_md, pdf_out_path)
            
            if generated_pdf:
                pdf_attachments.append(generated_pdf)
                status = "PDF Generated"
            else:
                # Fallback to attaching markdown if PDF fails
                pdf_attachments.append(md_path)
                status = "PDF generation failed, attaching Markdown instead."
                
            # Add to summary
            summary_lines.append(f"### {job['title']} @ {job['company']}")
            summary_lines.append(f"- **Link:** {job['link']}")
            summary_lines.append(f"- **Status:** {status}")
            summary_lines.append("")
            
        except Exception as e:
            logger.error(f"Error processing job {job['title']}: {e}")
            summary_lines.append(f"### {job['title']} @ {job['company']}")
            summary_lines.append(f"- **Status:** Failed to tailor due to AI error.")
            summary_lines.append("")
            
    # 5. Send Email
    logger.info("Phase 5: Sending Summary Email")
    summary_md = "\n".join(summary_lines)
    
    success = send_summary_email(
        receiver_email=cfg.notification.receiver_email,
        summary_markdown=summary_md,
        attachment_paths=pdf_attachments
    )
    
    if success:
        logger.info("=== AGENT PIPELINE COMPLETED SUCCESSFULLY ===")
    else:
        logger.warning("Agent finished, but email dispatch failed (check .env credentials).")

async def run_single_job_pipeline(job_url: str = "", job_text: str = "") -> dict:
    """
    Process a single job - either from URL or plain-text JD.
    Scrapes/parses the JD, tailors a resume, and generates a PDF.
    Returns a dict with result info.
    """
    cfg = load_config()
    logger.info(f"=== SINGLE JOB PIPELINE ===")

    # 1. Parse master resume
    pdf_path = os.getenv("RESUME_PATH", cfg.profile.resume_path)
    if not os.path.exists(pdf_path):
        return {"success": False, "error": f"Resume not found at {pdf_path}"}

    master_text = parse_resume(pdf_path)
    if not master_text:
        return {"success": False, "error": "Failed to parse master resume."}

    # 2. Get job details - from URL or plain text
    if job_url:
        from src.scrapers.job_url_scraper import scrape_job_from_url
        logger.info(f"Scraping job from URL: {job_url}")
        job = await scrape_job_from_url(job_url)
        if not job:
            return {"success": False, "error": "Failed to extract job details from the URL."}
    elif job_text:
        logger.info("Parsing plain-text job description via LLM...")
        from src.core.llm import get_llm
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser

        llm = get_llm(temperature=0.0)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Extract the job title, company name, and full description from the following job posting text. Return JSON: {{\"title\": \"...\", \"company\": \"...\", \"description\": \"...\"}}. If company or title is unclear, use reasonable defaults."),
            ("human", "{text}")
        ])
        chain = prompt | llm | JsonOutputParser()
        try:
            job = chain.invoke({"text": job_text})
            job.setdefault("title", "Unknown Role")
            job.setdefault("company", "Unknown Company")
            job.setdefault("description", job_text)
            job["link"] = ""
        except Exception as e:
            logger.error(f"LLM parsing failed: {e}")
            job = {
                "title": "Unknown Role",
                "company": "Unknown Company",
                "description": job_text,
                "link": ""
            }
    else:
        return {"success": False, "error": "No job URL or text provided."}

    logger.info(f"Extracted: {job['title']} at {job['company']}")

    # 3. Tailor resume
    tailored_md = tailor_for_job(
        job_title=job['title'],
        company_name=job['company'],
        job_description=job['description'],
        master_resume_text=master_text
    )

    # 4. Save files
    os.makedirs(cfg.output_dir, exist_ok=True)
    safe_company = "".join(x for x in job['company'] if x.isalnum() or x in " _-").strip()
    md_path = f"{cfg.output_dir}/Tailored_{safe_company}.md"
    pdf_out_path = f"{cfg.output_dir}/Resume_{safe_company}.pdf"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(tailored_md)

    generated_pdf = await generate_pdf(tailored_md, pdf_out_path)

    return {
        "success": True,
        "job_title": job['title'],
        "company": job['company'],
        "job_url": job_url or "",
        "pdf_path": generated_pdf or md_path,
        "md_path": md_path,
        "is_pdf": generated_pdf is not None
    }

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(run_agent_pipeline())
