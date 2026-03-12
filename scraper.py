import asyncio
import logging
import urllib.parse
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from llm_utils import get_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def scrape_linkedin_jobs(
    keywords, 
    location, 
    time_filter="past_24_hours", 
    limit=3
):
    """
    Scrape LinkedIn jobs based on criteria.
    Uses Playwright to render the dynamic content.
    Returns a list of dicts: [{'title': '', 'company': '', 'link': '', 'description': ''}]
    """
    
    def is_valid_role(title):
        title_lower = title.lower()
        if "engineer" in title_lower or "developer" in title_lower:
            return False
            
        architect_keywords = [
            "solutions architect", "solution architect", "gen ai architect", 
            "ai architect", "technical architect", 
            "agentic ai architect"
        ]
        
        for kw in architect_keywords:
            if kw in title_lower:
                return True
                
        # If none of the specific architect keywords match but it doesn't have engineer,
        # we still reject if it totally misses the keywords, but since LinkedIn search 
        # is broad we enforce the keywords strictly here.
        return False
        
    def is_top_tier_company(company_name: str) -> bool:
        """
        Uses an LLM to quickly evaluate if a company is a global top-tier, 
        Big Tech, or Fortune 500 entity.
        """
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
            # Err on the side of caution or allow fallback if LLM fails (allowing for now to not break pipeline)
            return True
    
    # Map time filter to LinkedIn URL param
    # r86400 = 24 hours
    # r604800 = past week
    tpr = "r86400" if time_filter == "past_24_hours" else ""
    
    encoded_keywords = urllib.parse.quote(keywords)
    encoded_location = urllib.parse.quote(location)
    
    search_url = f"https://www.linkedin.com/jobs/search?keywords={encoded_keywords}&location={encoded_location}&f_TPR={tpr}&position=1&pageNum=0"
    
    logger.info(f"Navigating to {search_url}")
    
    jobs_data = []
    
    async with async_playwright() as p:
        # Launching browser (headless=True for automation)
        browser = await p.chromium.launch(headless=True)
        # Randomize user agent to avoid basic blocks
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            
            # Wait for job cards to load
            await page.wait_for_selector("ul.jobs-search__results-list > li", timeout=15000)
            
            # Extract basic job links from the search page
            cards = await page.locator("ul.jobs-search__results-list > li").element_handles()
            
            job_links = []
            for card in cards[:limit * 10]: # Increase pool to account for heavy Fortune 500 filtering
                try:
                    link_element = await card.query_selector("a.base-card__full-link, a.base-search-card__title")
                    if link_element:
                        href = await link_element.get_attribute("href")
                        if href and "?" in href:
                            # Clean up the link
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
                    await page.goto(link, wait_until="domcontentloaded", timeout=30000)
                    
                    # Sometimes LinkedIn redirects or asks for login, wait for title
                    await page.wait_for_selector("h1.top-card-layout__title", timeout=10000)
                    
                    title = await page.locator("h1.top-card-layout__title").inner_text()
                    company = await page.locator("a.topcard__org-name-link").inner_text()
                    
                    if not title or not is_valid_role(title.strip()):
                        logger.info(f"Skipping job: '{title}' - does not match exact Architect criteria or is an Engineer role.")
                        continue
                        
                    # LLM Company Filter Check
                    if not is_top_tier_company(company):
                        logger.info(f"Skipping job: '{title}' at '{company}' - not evaluated as a top-tier global/Fortune 500 company.")
                        continue
                        
                    # Click 'Show more' button for description if it exists
                    try:
                        show_more_btn = await page.query_selector("button[data-tracking-control-name='public_jobs_show-more-html-btn']")
                        if show_more_btn:
                            await show_more_btn.click()
                            await page.wait_for_timeout(500)
                    except:
                        pass
                    
                    desc_element = await page.query_selector("div.show-more-less-html__markup")
                    
                    if desc_element:
                        # Extract inner HTML and convert to text using BeautifulSoup for cleaner text
                        desc_html = await desc_element.inner_html()
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
            await browser.close()
            
    return jobs_data

if __name__ == "__main__":
    # Test script run
    async def run_test():
        jobs = await scrape_linkedin_jobs("Solutions Architect", "India", limit=1)
        import pprint
        pprint.pprint(jobs)
        
    asyncio.run(run_test())
