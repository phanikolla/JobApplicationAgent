import asyncio
import logging
import os
from dotenv import load_dotenv

from scraper import scrape_linkedin_jobs
from resume_manager import parse_resume
from tailor_agent import tailor_for_job
from notifier import generate_pdf, send_summary_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_agent_pipeline():
    logger.info("=== STARTING AI JOB APPLICATION AGENT ===")
    
    # 1. Retrieve Master Resume
    logger.info("Phase 1: Retrieving Master Resume")
    pdf_path = os.getenv("RESUME_PATH", "Phani_Kumar_Kolla_profile.pdf")
    
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
        keywords='"Solutions Architect" OR "GEN AI Architect" OR "AI Architect" OR "Technical Architect" OR "Agentic AI Architect"', 
        location="India", 
        limit=3
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
    os.makedirs("output", exist_ok=True)
    
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
            md_path = f"output/Tailored_{safe_company}.md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(tailored_md)
                
            # Generate PDF
            pdf_out_path = f"output/Resume_{safe_company}.pdf"
            generated_pdf = await generate_pdf(tailored_md, pdf_out_path)
            
            if generated_pdf:
                pdf_attachments.append(generated_pdf)
                status = "✅ PDF Generated"
            else:
                # Fallback to attaching markdown if PDF fails
                pdf_attachments.append(md_path)
                status = "⚠️ PDF generation failed (wkhtmltopdf missing?), attaching Markdown instead."
                
            # Add to summary
            summary_lines.append(f"### {job['title']} @ {job['company']}")
            summary_lines.append(f"- **Link:** {job['link']}")
            summary_lines.append(f"- **Status:** {status}")
            summary_lines.append("")
            
        except Exception as e:
            logger.error(f"Error processing job {job['title']}: {e}")
            summary_lines.append(f"### {job['title']} @ {job['company']}")
            summary_lines.append(f"- **Status:** ❌ Failed to tailor due to AI error.")
            summary_lines.append("")
            
    # 5. Send Email
    logger.info("Phase 5: Sending Summary Email")
    summary_md = "\n".join(summary_lines)
    
    success = send_summary_email(
        receiver_email="pkkolla24@gmail.com",
        summary_markdown=summary_md,
        attachment_paths=pdf_attachments
    )
    
    if success:
        logger.info("=== AGENT PIPELINE COMPLETED SUCCESSFULLY ===")
    else:
        logger.warning("Agent finished, but email dispatch failed (check .env credentials).")

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(run_agent_pipeline())
