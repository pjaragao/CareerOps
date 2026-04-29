import re
import asyncio
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, BrowserContext
from app.core.config import settings
from app.db.session import get_db_connection
from app.services.pipeline_service import PipelineService
from app.services.strategy_service import StrategyService
from app.services.job_service import JobService
from datetime import datetime, timezone
import json

class ScraperService:
    @staticmethod
    async def _get_context(p, headless: bool = True) -> (BrowserContext, any):
        if not settings.SESSION_FILE.exists():
            raise FileNotFoundError("LinkedIn session file not found. Please login first.")
        
        browser = await p.chromium.launch(headless=headless)
        
        # Try to use the user's real user agent if synced via extension
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ua_file = settings.AUTH_DIR / "user_agent.txt"
        if ua_file.exists():
            user_agent = ua_file.read_text().strip()

        context = await browser.new_context(
            storage_state=str(settings.SESSION_FILE),
            user_agent=user_agent,
            viewport={"width": 1280, "height": 1024}
        )
        return context, browser

    @staticmethod
    async def search_jobs(keywords: List[str], locations: List[str], remote_only: bool = True) -> List[str]:
        async with async_playwright() as p:
            context, browser = await ScraperService._get_context(p)
            page = await context.new_page()
            found_urls = []

            for kw in keywords:
                for loc in locations:
                    search_url = f"https://www.linkedin.com/jobs/search/?keywords={kw.replace(' ', '%20')}&location={loc.replace(' ', '%20')}"
                    if remote_only:
                        search_url += "&f_WT=2"
                    
                    try:
                        await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                        await asyncio.sleep(5)
                        
                        # Scroll to load results
                        for _ in range(3):
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            await asyncio.sleep(2)
                        
                        links = await page.query_selector_all('a[href*="/jobs/view/"]')
                        for link in links:
                            href = await link.get_attribute("href")
                            if href:
                                clean_url = href.split("?")[0]
                                if clean_url not in found_urls:
                                    found_urls.append(clean_url)
                    except Exception as e:
                        print(f"Error searching {kw} in {loc}: {e}")
            
            await browser.close()
            return found_urls

    @staticmethod
    async def scrape_job_details(url: str) -> Dict[str, any]:
        async with async_playwright() as p:
            context, browser = await ScraperService._get_context(p)
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(5)
                
                # Scroll to load sections
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await asyncio.sleep(2)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

                # Multi-strategy extraction for title
                title = ""
                for selector in [
                    '.jobs-unified-top-card__job-title', 
                    '.t-24.t-bold', 
                    'h1.t-24',
                    '.job-details-jobs-unified-top-card__job-title'
                ]:
                    el = await page.query_selector(selector)
                    if el:
                        title = await el.inner_text()
                        break

                # Multi-strategy extraction for company
                company = ""
                for selector in [
                    '.jobs-unified-top-card__company-name',
                    '.jobs-unified-top-card__company-name a',
                    '.t-14.t-black--light.t-normal a',
                    '.job-details-jobs-unified-top-card__company-name'
                ]:
                    el = await page.query_selector(selector)
                    if el:
                        company = await el.inner_text()
                        break

                # Extract description
                desc_el = await page.query_selector('div.jobs-description__content, div.jobs-box__html-content, section.jobs-description, #job-details')
                description = await desc_el.inner_text() if desc_el else ""

                return {
                    "url": url,
                    "job_title": title.strip(),
                    "company": company.strip(),
                    "description": description.strip(),
                    "scraped_at": datetime.now(timezone.utc).isoformat()
                }
            finally:
                await browser.close()

    @staticmethod
    async def run_search_strategy(strat_id: int):
        strategies = StrategyService.get_strategies()
        strat = next((s for s in strategies if s['id'] == strat_id), None)
        if not strat:
            return
        
        urls = await ScraperService.search_jobs(
            keywords=strat['keywords'],
            locations=strat['locations'],
            remote_only=strat.get('remote_only', True)
        )
        
        for url in urls:
            PipelineService.add_url(url, source=f"Strategy: {strat['title']}")

    @staticmethod
    async def run_all_strategies():
        strategies = StrategyService.get_strategies()
        for strat in strategies:
            await ScraperService.run_search_strategy(strat['id'])

    @staticmethod
    async def process_pipeline():
        urls = PipelineService.get_urls(status='pending')
        for item in urls:
            try:
                PipelineService.update_status(item['id'], 'processing')
                
                details = await ScraperService.scrape_job_details(item['url'])
                if details:
                    # Save to job_listings
                    JobService.insert_manual_job(
                        details['job_title'],
                        details['company'],
                        "", # location extraction needs improvement
                        item['url'],
                        details['description']
                    )
                    PipelineService.update_status(item['id'], 'done')
                else:
                    PipelineService.update_status(item['id'], 'error')
            except Exception as e:
                print(f"Error processing pipeline URL {item['url']}: {e}")
                PipelineService.update_status(item['id'], 'error')

    @staticmethod
    async def auto_apply(job_id: int):
        job = JobService.get_job_by_id(job_id)
        if not job or not job.get('url'):
            print(f"Cannot auto-apply: Job {job_id} not found or has no URL")
            return
        
        async with async_playwright() as p:
            try:
                context, browser = await ScraperService._get_context(p, headless=True)
                page = await context.new_page()
                await page.goto(job['url'], wait_until="domcontentloaded")
                await asyncio.sleep(5)
                
                # Logic for Easy Apply button
                apply_button = await page.query_selector('button.jobs-apply-button')
                if apply_button:
                    text = await apply_button.inner_text()
                    if "Easy Apply" in text:
                        await apply_button.click()
                        await asyncio.sleep(3)
                        # Further automation steps would go here
                        print(f"Clicked Easy Apply for job {job_id}")
                    else:
                        print(f"Job {job_id} is not Easy Apply")
                else:
                    print(f"No apply button found for job {job_id}")
                
                await browser.close()
            except Exception as e:
                print(f"Auto-apply error for job {job_id}: {e}")

    @staticmethod
    async def scrape_own_profile() -> Dict[str, any]:
        """
        Robustly scrape the user's own profile in both English and Portuguese.
        Migrated from legacy system with multiple extraction strategies.
        """
        async with async_playwright() as p:
            context, browser = await ScraperService._get_context(p, headless=True)
            page = await context.new_page()
            try:
                await page.set_viewport_size({"width": 1280, "height": 1024})
                
                result = {
                    "profile_url": "",
                    "name": "",
                    "location": "",
                    "headline": "",
                    "en": {"headline": "", "about": "", "experience": [], "skills": []},
                    "pt": {"headline": "", "about": "", "experience": [], "skills": []},
                }

                # 1. Navigate to 'me' to resolve actual profile URL
                try:
                    await page.goto("https://www.linkedin.com/in/me/", wait_until="domcontentloaded", timeout=60000)
                    await asyncio.sleep(5)
                except Exception as e:
                    await page.screenshot(path=str(settings.OUTPUT_DIR / "error_profile_nav.png"))
                    raise Exception(f"Failed to navigate to LinkedIn profile: {str(e)}")
                
                if "login" in page.url or "checkpoint" in page.url:
                    await page.screenshot(path=str(settings.OUTPUT_DIR / "error_session_expired.png"))
                    raise Exception("Session expired or invalid. Please sync session via extension again.")

                result["profile_url"] = page.url.split("?")[0]
                
                # --- Helper for Extraction ---
                async def extract_current_view():
                    # Click 'see more' buttons
                    try:
                        buttons = await page.query_selector_all('button[aria-label*="more"], button[aria-label*="mais"], .lt-line-clamp__more, .inline-show-more-text__button')
                        for btn in buttons:
                            if await btn.is_visible():
                                await btn.click()
                                await asyncio.sleep(0.5)
                    except: pass

                    # Extract basic info if not already set
                    nonlocal result
                    if not result["name"]:
                        el = await page.query_selector("h1.text-heading-xlarge")
                        if el: result["name"] = (await el.inner_text()).strip()
                    
                    if not result["location"]:
                        el = await page.query_selector("span.text-body-small.inline.t-black--light.break-words")
                        if el: result["location"] = (await el.inner_text()).strip()

                    # Headline
                    headline = ""
                    el = await page.query_selector("div.text-body-medium.break-words")
                    if el: headline = (await el.inner_text()).strip()

                    # About (Simplified but effective strategy)
                    about = await page.evaluate("""() => {
                        const keywords = ['About', 'Sobre', 'Summary', 'Resumo'];
                        for (const h2 of document.querySelectorAll('h2')) {
                            if (keywords.includes(h2.innerText.trim())) {
                                const section = h2.closest('section');
                                if (section) return section.innerText.replace(h2.innerText, '').trim();
                            }
                        }
                        return '';
                    }""")

                    # Experience
                    experience = await page.evaluate("""() => {
                        const results = [];
                        const sections = Array.from(document.querySelectorAll('section'));
                        const expSection = sections.find(s => s.innerText.includes('Experience') || s.innerText.includes('Experiência'));
                        if (expSection) {
                            const lis = expSection.querySelectorAll('li.artdeco-list__item');
                            lis.forEach(li => {
                                const lines = li.innerText.split('\\n').map(l => l.trim()).filter(l => l);
                                results.push({
                                    title: lines[0] || '',
                                    company: lines[1] || '',
                                    period: lines[2] || '',
                                    description: lines.slice(3).join(' ')
                                });
                            });
                        }
                        return results;
                    }""")

                    # Skills
                    skills = await page.evaluate("""() => {
                        const sections = Array.from(document.querySelectorAll('section'));
                        const skillSection = sections.find(s => s.innerText.includes('Skills') || s.innerText.includes('Competências'));
                        if (skillSection) {
                            return Array.from(skillSection.querySelectorAll('span[aria-hidden="true"]'))
                                .map(s => s.innerText.trim())
                                .filter(s => s && s.length > 2 && !s.includes('endorsement'));
                        }
                        return [];
                    }""")

                    return {
                        "headline": headline,
                        "about": about,
                        "experience": experience,
                        "skills": skills
                    }

                # --- Scrape English ---
                await page.goto(f"{result['profile_url']}?locale=en_US", wait_until="domcontentloaded")
                await asyncio.sleep(4)
                result["en"] = await extract_current_view()
                
                # --- Scrape Portuguese ---
                await page.goto(f"{result['profile_url']}?locale=pt_BR", wait_until="domcontentloaded")
                await asyncio.sleep(4)
                result["pt"] = await extract_current_view()

                # Set global headline/name for convenience
                result["headline"] = result["pt"]["headline"] or result["en"]["headline"]
                result["personal"] = {
                    "name": result["name"],
                    "location": result["location"],
                    "headline": result["headline"]
                }
                result["experience"] = result["pt"]["experience"] or result["en"]["experience"]
                result["skills"] = result["pt"]["skills"] or result["en"]["skills"]
                
                return result
            finally:
                await browser.close()
