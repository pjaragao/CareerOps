"""
LinkedIn Scraper — uses Playwright to scrape saved jobs with an authenticated session.
"""
import re
import time
import threading
from playwright.sync_api import sync_playwright, Page
from config import SESSION_FILE, LINKEDIN_EMAIL, SCRAPE_DELAY
import db

# Signal to finish login early (set from web UI)
_finish_login_event = threading.Event()


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _session_exists() -> bool:
    return SESSION_FILE.exists() and SESSION_FILE.stat().st_size > 100


def login():
    """
    Open a visible browser for the user to log in manually.
    Auto-detects login by polling the URL (works from both CLI and web UI).
    After login, the session (cookies + storage) is saved to disk.
    """
    print("🔐 Opening browser for LinkedIn login...")
    print("   → Log in manually (including 2FA if needed).")
    print("   → The browser will close automatically once login is detected.\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.linkedin.com/login")

        if LINKEDIN_EMAIL:
            try:
                page.fill('input#username', LINKEDIN_EMAIL, timeout=3000)
            except Exception:
                pass  # field might not be ready yet

        # Auto-detect login by polling URL (max 5 minutes)
        # Also checks _finish_login_event for early finish from web UI
        _finish_login_event.clear()
        print("   ⏳ Waiting for login (auto-detect, up to 5 min)...")
        print("   💡 Click 'Finish Login' in the web UI when done.")
        max_wait = 300  # seconds
        elapsed = 0
        logged_in = False

        while elapsed < max_wait:
            time.sleep(2)
            elapsed += 2

            # Check if finish was requested from web UI
            if _finish_login_event.is_set():
                print("   🏁 Finish Login requested — saving session now.")
                break

            try:
                current_url = page.url
            except Exception:
                # Browser was closed manually
                print("   ⚠️  Browser closed before login detected.")
                return

            if any(kw in current_url for kw in ["feed", "mynetwork", "/in/", "messaging"]):
                logged_in = True
                break

            if elapsed % 30 == 0:
                print(f"   ⏳ Still waiting... ({elapsed}s elapsed)")

        if logged_in:
            print("   ✅ Login detected!")
        elif not _finish_login_event.is_set():
            print(f"   ⚠️  Timeout — current URL: {page.url}")
            print("   Saving session anyway — you can verify later.")

        # Save session
        try:
            context.storage_state(path=str(SESSION_FILE))
            print(f"   💾 Session saved to {SESSION_FILE}")
        except Exception as e:
            print(f"   ❌ Could not save session: {e}")

        browser.close()


def finish_login():
    """Signal the login loop to save session and close immediately."""
    _finish_login_event.set()


def _create_context(playwright, headless=True):
    """Create a browser context with the saved session."""
    if not _session_exists():
        raise RuntimeError(
            "No LinkedIn session found. Run 'python main.py login' first."
        )

    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context(storage_state=str(SESSION_FILE))
    return browser, context


# ---------------------------------------------------------------------------
# Scrape saved jobs list
# ---------------------------------------------------------------------------

def _extract_job_id(url: str) -> str:
    """Extract the numeric job ID from a LinkedIn job URL."""
    match = re.search(r'/jobs/view/(\d+)', url)
    if match:
        return match.group(1)
    # fallback: try to find any long number
    match = re.search(r'(\d{8,})', url)
    return match.group(1) if match else ""


def scrape_saved_jobs(max_jobs: int = 100) -> list[dict]:
    """
    Scrape the user's saved jobs page on LinkedIn.
    Handles pagination (Next button). Extracts title, company, location from card text.
    Also syncs removals: jobs in DB but no longer saved → marked 'removed'.
    """
    print(f"\n🔍 Scraping saved jobs (max {max_jobs})...")

    with sync_playwright() as p:
        browser, context = _create_context(p, headless=True)
        page = context.new_page()

        try:
            page.goto(
                "https://www.linkedin.com/my-items/saved-jobs/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            time.sleep(4)

            # Check if we're redirected to login
            if "login" in page.url or "checkpoint" in page.url:
                print("   ❌ Session expired. Click 'LinkedIn Login' to re-authenticate.")
                browser.close()
                return []

            jobs_data = []
            seen_ids = set()
            page_num = 1

            while len(jobs_data) < max_jobs:
                print(f"   📄 Scraping page {page_num}...")

                # Scroll down to ensure all cards on this page are rendered
                for _ in range(3):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1)
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(1)

                # Find all list items that contain a job link
                all_li = page.query_selector_all('li')
                cards = [li for li in all_li if li.query_selector('a[href*="/jobs/view/"]')]

                if not cards:
                    print(f"   ⚠️  No job cards found on page {page_num}")
                    break

                page_job_count = 0
                for card in cards:
                    if len(jobs_data) >= max_jobs:
                        break

                    try:
                        link_el = card.query_selector('a[href*="/jobs/view/"]')
                        if not link_el:
                            continue

                        href = link_el.get_attribute("href") or ""
                        if not href:
                            continue

                        # Normalize URL
                        if href.startswith("/"):
                            href = "https://www.linkedin.com" + href
                        href = href.split("?")[0]

                        job_id = _extract_job_id(href)
                        if not job_id or job_id in seen_ids:
                            continue
                        seen_ids.add(job_id)

                        # --- Extract info from card text lines ---
                        # Structure (confirmed via debug):
                        #   LINE[0]: Job title
                        #   LINE[1]: Company (may have ", Verified" suffix)
                        #   LINE[2]: Location (e.g. "Brazil (Remote)")
                        #   LINE[3+]: noise ("Be an early applicant", "Posted Xd ago", "Easy Apply")
                        card_text = (card.inner_text() or "").strip()
                        lines = [l.strip() for l in card_text.split("\n") if l.strip()]

                        title = lines[0] if len(lines) > 0 else ""
                        title = " ".join(title.split())  # normalize whitespace

                        company = lines[1] if len(lines) > 1 else ""
                        # Clean up ", Verified" suffix
                        company = company.replace(", Verified", "").strip()
                        if company.startswith(","):
                            company = company[1:].strip()

                        location = lines[2] if len(lines) > 2 else ""

                        # Detect Easy Apply
                        easy_apply = False
                        card_lower = card_text.lower()
                        if "easy apply" in card_lower or "candidatura simplificada" in card_lower:
                            easy_apply = True

                        jobs_data.append({
                            "url": href,
                            "linkedin_job_id": job_id,
                            "job_title": title[:500],
                            "company": company[:200],
                            "location": location[:200],
                            "easy_apply": easy_apply,
                        })
                        page_job_count += 1

                    except Exception as e:
                        print(f"   ⚠️  Error parsing card: {e}")
                        continue

                print(f"   ✅ Page {page_num}: found {page_job_count} jobs")

                # --- Try to go to next page ---
                next_btn = page.query_selector(
                    'button[aria-label="Next"], '
                    'button[aria-label="Próximo"], '
                    'a[aria-label="Next"], '
                    'a[aria-label="Próximo"], '
                    'li.artdeco-pagination__indicator--next button, '
                    'button.artdeco-pagination__button--next'
                )

                if not next_btn:
                    # Try finding "Next" by text content
                    all_buttons = page.query_selector_all('button, a')
                    for btn in all_buttons:
                        btn_text = (btn.inner_text() or "").strip().lower()
                        if btn_text in ("next", "next >", "próximo", "próximo >"):
                            next_btn = btn
                            break

                if not next_btn or not next_btn.is_visible():
                    print(f"   📄 No more pages (total pages: {page_num})")
                    break

                # Check if the next button is disabled
                is_disabled = next_btn.get_attribute("disabled")
                aria_disabled = next_btn.get_attribute("aria-disabled")
                if is_disabled is not None or aria_disabled == "true":
                    print(f"   📄 Last page reached (total pages: {page_num})")
                    break

                next_btn.click()
                time.sleep(3)
                page_num += 1

            # --- Sync removals ---
            existing_ids = db.get_all_active_job_ids()
            scraped_ids = {j["linkedin_job_id"] for j in jobs_data}
            removed_ids = existing_ids - scraped_ids
            if removed_ids:
                db.mark_removed(list(removed_ids))
                print(f"   🗑️  Marked {len(removed_ids)} unsaved jobs as 'removed'.")

            # --- Insert new jobs ---
            new_count = 0
            for job in jobs_data:
                was_new = db.upsert_job(
                    url=job["url"],
                    linkedin_job_id=job["linkedin_job_id"],
                    job_title=job["job_title"],
                    company=job["company"],
                    location=job["location"],
                    easy_apply=job.get("easy_apply", False),
                )
                if was_new:
                    new_count += 1

            print(f"   📋 Total: {len(jobs_data)} saved jobs, {new_count} new.")
            return jobs_data

        finally:
            browser.close()


# ---------------------------------------------------------------------------
# Scrape individual job description
# ---------------------------------------------------------------------------

def scrape_job_description(url: str) -> tuple[str, str]:
    """
    Navigate to a job page and extract the full description.
    Returns (description_text, language).
    """
    with sync_playwright() as p:
        browser, context = _create_context(p, headless=True)
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            # Try multiple selectors for job description
            description = ""
            selectors = [
                'div.jobs-description__content',
                'div.jobs-box__html-content',
                'div[class*="description"]',
                'section[class*="description"]',
                'article',
            ]

            for sel in selectors:
                el = page.query_selector(sel)
                if el:
                    description = (el.inner_text() or "").strip()
                    if len(description) > 100:
                        break

            if not description:
                # Fallback: get all text from the main content
                main = page.query_selector('main') or page.query_selector('body')
                if main:
                    description = (main.inner_text() or "").strip()

            # Also try to get job title and company if not already known
            title = ""
            title_el = page.query_selector(
                'h1.jobs-unified-top-card__job-title, '
                'h1[class*="job-title"], '
                'h1'
            )
            if title_el:
                title = (title_el.inner_text() or "").strip()

            company = ""
            company_el = page.query_selector(
                'a.jobs-unified-top-card__company-name, '
                'span[class*="company-name"]'
            )
            if company_el:
                company = (company_el.inner_text() or "").strip()

            # Detect language
            language = _detect_language(description)

            return description[:20000], language

        finally:
            browser.close()


def _detect_language(text: str) -> str:
    """Detect if text is Portuguese or English based on keyword frequency."""
    lower = text.lower()

    pt_words = [
        'vaga', 'requisitos', 'experiência', 'empresa', 'responsabilidades',
        'benefícios', 'salário', 'conhecimento', 'desejável', 'obrigatório',
        'formação', 'superior', 'contratação', 'atuação',
    ]
    en_words = [
        'requirements', 'experience', 'company', 'responsibilities',
        'benefits', 'salary', 'qualifications', 'skills', 'team',
        'position', 'candidate', 'ability', 'degree',
    ]

    pt_score = sum(1 for w in pt_words if w in lower)
    en_score = sum(1 for w in en_words if w in lower)

    return 'pt' if pt_score > en_score else 'en'
