import asyncio
import logging
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.core.llm import get_llm
from src.core.config import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread pool for running sync Playwright in background
_executor = ThreadPoolExecutor(max_workers=2)


def _scrape_linkedin_jobs_sync(
    keywords, location, time_filter, limit, cfg
):
    """
    Sync Playwright LinkedIn scraping - runs in a thread.
    Returns a list of dicts: [{'title': '', 'company': '', 'link': '', 'description': ''}]
    """
    def is_valid_role(title):
        title_lower = title.lower()

        for excluded in cfg.role_filters.excluded_role_keywords:
            if excluded in title_lower:
                return False
            
        for kw in cfg.role_filters.architect_keywords:
            if kw in title_lower:
                return True
                
        return False
        
    def is_top_tier_company(company_name: str) -> bool:
        if not cfg.role_filters.require_top_tier_company:
            return True

        if not company_name or company_name.lower() == "unknown company":
            return False
            
        try:
            llm = get_llm(temperature=0.0)
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are an expert tech industry analyst. The user will provide a company name. You must determine if this company is widely considered a top-tier global enterprise, a 'Big Tech' company, or a Fortune 500 company. Respond strictly with 'YES' or 'NO' and nothing else."),
                ("human", "{company_name}")
            ])
            chain = prompt | llm | StrOutputParser()
            result = chain.invoke({"company_name": company_name}).strip().upper()
            return result == "YES"
        except Exception as e:
            logger.error(f"Error evaluating company tier: {e}")
            return True
    
    # Map time filter to LinkedIn URL param
    time_filter_map = {
        "past_24_hours": "r86400",
        "past_week": "r604800",
        "past_month": "r2592000",
    }
    tpr = time_filter_map.get(time_filter, "r86400")
    
    encoded_keywords = urllib.parse.quote(keywords)
    encoded_location = urllib.parse.quote(location)
    
    search_url = f"https://www.linkedin.com/jobs/search?keywords={encoded_keywords}&location={encoded_location}&f_TPR={tpr}&position=1&pageNum=0"
    
    logger.info(f"Navigating to {search_url}")
    
    jobs_data = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            
            # Wait for job cards to load
            page.wait_for_selector("ul.jobs-search__results-list > li", timeout=15000)
            
            # Extract basic job links from the search page
            cards = page.locator("ul.jobs-search__results-list > li").element_handles()
            
            job_links = []
            for card in cards[:limit * 10]:
                try:
                    link_element = card.query_selector("a.base-card__full-link, a.base-search-card__title")
                    if link_element:
                        href = link_element.get_attribute("href")
                        if href and "?" in href:
                            href = href.split("?")[0]
                        job_links.append(href)
                except Exception as e:
                    logger.warning(f"Failed to extract link from a card: {e}")
            
            # Deduplicate links
            job_links = list(dict.fromkeys(job_links))
            logger.info(f"Found {len(job_links)} job links. Filtering and fetching descriptions...")
            
            # Now visit each link to get full details and description
            for link in job_links:
                if len(jobs_data) >= limit:
                    break
                    
                try:
                    logger.info(f"Scraping job: {link}")
                    page.goto(link, wait_until="domcontentloaded", timeout=30000)
                    
                    page.wait_for_selector("h1.top-card-layout__title", timeout=10000)
                    
                    title = page.locator("h1.top-card-layout__title").inner_text()
                    company = page.locator("a.topcard__org-name-link").inner_text()
                    
                    if not title or not is_valid_role(title.strip()):
                        logger.info(f"Skipping job: '{title}' - does not match exact Architect criteria or is an Engineer role.")
                        continue
                        
                    if not is_top_tier_company(company):
                        logger.info(f"Skipping job: '{title}' at '{company}' - not evaluated as a top-tier global/Fortune 500 company.")
                        continue
                        
                    # Click 'Show more' button for description if it exists
                    try:
                        show_more_btn = page.query_selector("button[data-tracking-control-name='public_jobs_show-more-html-btn']")
                        if show_more_btn:
                            show_more_btn.click()
                            page.wait_for_timeout(500)
                    except:
                        pass
                    
                    desc_element = page.query_selector("div.show-more-less-html__markup")
                    
                    if desc_element:
                        desc_html = desc_element.inner_html()
                        soup = BeautifulSoup(desc_html, "html.parser")
                        description = soup.get_text(separator="\n").strip()
                    else:
                        description = "Description not found."
                        
                    jobs_data.append({
                        "title": title.strip() if title else "Unknown Title",
                        "company": company.strip() if company else "Unknown Company",
                        "link": link,
                        "description": description
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to scrape job at {link}: {e}")
                    
        except Exception as e:
            logger.error(f"Error during job search: {e}")
            
        finally:
            browser.close()
            
    return jobs_data


async def scrape_linkedin_jobs(
    keywords=None, 
    location=None, 
    time_filter=None, 
    limit=None
):
    """
    Scrape LinkedIn jobs based on criteria.
    Uses sync Playwright in a thread pool to avoid event loop conflicts.
    Returns a list of dicts: [{'title': '', 'company': '', 'link': '', 'description': ''}]
    """
    cfg = load_config()

    # Use config defaults if not provided as arguments
    if keywords is None:
        keywords = cfg.job_search.search_keywords
    if location is None:
        location = cfg.job_search.search_location
    if time_filter is None:
        time_filter = cfg.job_search.time_filter
    if limit is None:
        limit = cfg.job_search.job_limit

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        _scrape_linkedin_jobs_sync,
        keywords, location, time_filter, limit, cfg
    )


if __name__ == "__main__":
    # Test script run
    async def run_test():
        jobs = await scrape_linkedin_jobs(keywords="Solutions Architect", location="India", limit=1)
        import pprint
        pprint.pprint(jobs)
        
    asyncio.run(run_test())
