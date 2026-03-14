"""
Generic job page scraper for manually-provided URLs.
Supports any job platform (LinkedIn, company career pages, Naukri, etc.).
Uses Playwright (sync API) to render JS-heavy pages, then LLM to extract structured job data.

NOTE: Uses sync Playwright + thread executor to avoid async event loop conflicts
when called from within FastAPI's already-running asyncio loop.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.core.llm import get_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread pool for running sync Playwright in background
_executor = ThreadPoolExecutor(max_workers=2)


async def scrape_job_from_url(url: str) -> dict | None:
    """
    Scrapes a single job posting from any URL.
    
    1. Renders the page with Playwright (handles JS-heavy sites)
    2. Extracts raw page text
    3. Uses LLM to intelligently extract job_title, company_name, description
    
    Returns: {'title': str, 'company': str, 'link': str, 'description': str} or None
    """
    logger.info(f"Scraping job details from: {url}")
    
    # Run sync Playwright in a thread to avoid event loop conflicts
    loop = asyncio.get_event_loop()
    page_text = await loop.run_in_executor(_executor, _fetch_page_text_sync, url)

    if not page_text:
        logger.error(f"Failed to extract any text from {url}")
        return None

    # Truncate to avoid token limits (most JDs are in the first ~8000 chars)
    truncated_text = page_text[:8000]

    job_data = _extract_job_details_with_llm(truncated_text, url)
    return job_data


def _fetch_page_text_sync(url: str) -> str | None:
    """Render the page with sync Playwright and extract text content."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Give JS time to render dynamic content
            page.wait_for_timeout(3000)

            html_content = page.content()
            browser.close()

        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        text = soup.get_text(separator="\n")
        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)

        logger.info(f"Extracted {len(clean_text)} chars of text from page")
        return clean_text

    except Exception as e:
        logger.error(f"Error fetching page {url}: {e}")
        return None


def _extract_job_details_with_llm(page_text: str, url: str) -> dict | None:
    """Use LLM to extract structured job data from raw page text."""
    try:
        llm = get_llm(temperature=0.0)

        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are an expert at parsing job postings from web pages. "
                "The user will provide raw text extracted from a job posting page. "
                "Extract the following fields and return them as valid JSON:\n"
                "- job_title: The exact title of the position\n"
                "- company_name: The company offering the role\n"
                "- description: The full job description including responsibilities, "
                "requirements, qualifications, skills, and any other relevant details. "
                "Preserve as much detail as possible.\n\n"
                "If you cannot find a field, use 'Unknown' as the value. "
                "Output MUST be valid JSON with exactly these three keys: "
                "'job_title', 'company_name', 'description'."
            )),
            ("human", "Page URL: {url}\n\nPage Text:\n{page_text}")
        ])

        chain = prompt | llm | JsonOutputParser()
        result = chain.invoke({"url": url, "page_text": page_text})

        job_title = result.get("job_title", "Unknown Title")
        company_name = result.get("company_name", "Unknown Company")
        description = result.get("description", "Description not available.")

        logger.info(f"LLM extracted: '{job_title}' at '{company_name}'")

        return {
            "title": job_title,
            "company": company_name,
            "link": url,
            "description": description
        }

    except Exception as e:
        logger.error(f"Error extracting job details with LLM: {e}")
        return None


if __name__ == "__main__":
    async def test():
        result = await scrape_job_from_url("https://www.linkedin.com/jobs/view/1234567890")
        import pprint
        pprint.pprint(result)

    asyncio.run(test())
