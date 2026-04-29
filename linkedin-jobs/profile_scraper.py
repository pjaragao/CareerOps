"""
LinkedIn Profile Scraper — scrapes the user's own profile in PT and EN.

Uses the existing authenticated session (linkedin_session.json).
Returns structured data: headline, about, experience, skills per language.
Does NOT modify resume_base.md — data is returned for UI display only.
"""
import re
import time
from playwright.sync_api import sync_playwright, Page
from config import SESSION_FILE


def _session_exists() -> bool:
    return SESSION_FILE.exists() and SESSION_FILE.stat().st_size > 100


def _create_context(playwright, headless=True):
    """Create a browser context with the saved session."""
    if not _session_exists():
        raise RuntimeError(
            "No LinkedIn session found. Click 'LinkedIn Login' in the Job Scraper first."
        )
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context(storage_state=str(SESSION_FILE))
    return browser, context


def _clean(text: str) -> str:
    """Normalize whitespace in extracted text."""
    return " ".join(text.split()).strip() if text else ""


def _extract_profile(page: Page) -> dict:
    """
    Extract all profile sections from the current page.
    Returns a dict with: headline, about, experience, skills.
    """
    profile = {
        "headline": "",
        "about": "",
        "experience": [],
        "skills": [],
    }

    # --- Headline ---
    try:
        headline_el = (
            page.query_selector("div.text-body-medium.break-words")
            or page.query_selector("div.pv-text-details__left-panel div")
        )
        if headline_el:
            profile["headline"] = _clean(headline_el.inner_text())
    except Exception as e:
        print(f"   Warning: Could not extract headline: {e}")

    # --- About / Summary ---
    try:
        # Step 1: Scroll down fully to ensure all sections are loaded
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)

        # Step 2: Debug — dump section counts
        debug_info = page.evaluate("""() => {
            const sections = Array.from(document.querySelectorAll('section'));
            const h2s = Array.from(document.querySelectorAll('h2')).map(h => h.innerText.trim());
            return { count: sections.length, h2s };
        }""")
        # Only log if it's very low (indicating a load failure)
        if debug_info.get('count', 0) < 3:
            print(f"   ⚠️ Warning: few sections found ({debug_info.get('count')}). Possible dynamic load issue.")

        # Step 3: Click ALL visible 'see more' / 'ver mais' buttons (not just one)
        try:
            buttons = page.query_selector_all(
                'button[aria-label*="more"], button[aria-label*="mais"], '
                '.lt-line-clamp__more, .inline-show-more-text__button, '
                '.pv-shared-text-with-see-more button'
            )
            for btn in buttons:
                try:
                    if btn.is_visible():
                        btn.click()
                        time.sleep(0.5)
                except Exception:
                    pass
        except Exception:
            pass

        # Step 4: Run all extraction strategies
        about_text = page.evaluate(r"""() => {
            const ABOUT_KEYWORDS = ['About', 'Sobre', 'Summary', 'Resumo'];

            const strategies = [
                // S1: section with matching aria-label — innerText of first div with content
                () => {
                    for (const section of document.querySelectorAll('section')) {
                        const aria = (section.getAttribute('aria-label') || '').trim();
                        if (ABOUT_KEYWORDS.includes(aria)) {
                            // Walk children for a div with substantial text
                            for (const el of section.querySelectorAll('div, p, span')) {
                                const txt = (el.innerText || '').trim();
                                if (txt.length > 50 && !ABOUT_KEYWORDS.includes(txt)) return txt;
                            }
                            return (section.innerText || '').trim();
                        }
                    }
                    return null;
                },
                // S2: h2 with About keyword → walk siblings for text
                () => {
                    for (const h2 of document.querySelectorAll('h2')) {
                        if (ABOUT_KEYWORDS.includes((h2.innerText || '').trim())) {
                            // Try parent section first
                            const section = h2.closest('section');
                            if (section) {
                                for (const el of section.querySelectorAll('div[dir], div.pv-shared-text-with-see-more, div.inline-show-more-text, span.visually-hidden')) {
                                    const txt = (el.innerText || '').trim();
                                    if (txt.length > 50) return txt;
                                }
                                // fallback: whole section minus h2
                                const full = (section.innerText || '').trim();
                                return full.replace(h2.innerText.trim(), '').trim();
                            }
                        }
                    }
                    return null;
                },
                // S3: id or data attribute containing 'about'
                () => {
                    const el = document.querySelector(
                        '#about, section[data-section="summary"], [data-view-name="profile-about-card"]'
                    );
                    if (el) {
                        for (const child of el.querySelectorAll('div[dir], div.pv-shared-text-with-see-more, p')) {
                            const txt = (child.innerText || '').trim();
                            if (txt.length > 50) return txt;
                        }
                        return (el.innerText || '').trim();
                    }
                    return null;
                },
                // S4: any span.visually-hidden with substantial content
                () => {
                    for (const span of document.querySelectorAll('span.visually-hidden')) {
                        const txt = (span.innerText || '').trim();
                        if (txt.length > 100 && !ABOUT_KEYWORDS.includes(txt)) return txt;
                    }
                    return null;
                },
                // S5: full-page text fallback — find "About"/"Sobre" heading and grab next block
                () => {
                    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                    while (walker.nextNode()) {
                        const txt = (walker.currentNode.textContent || '').trim();
                        if (ABOUT_KEYWORDS.includes(txt)) {
                            // The about text is usually the next substantial sibling text node or parent's child
                            let el = walker.currentNode.parentElement;
                            for (let i = 0; i < 6 && el; i++) {
                                const sibling = el.nextElementSibling;
                                if (sibling) {
                                    const sibTxt = (sibling.innerText || '').trim();
                                    if (sibTxt.length > 50) return sibTxt;
                                }
                                el = el.parentElement;
                            }
                        }
                    }
                    return null;
                },
            ];

            for (let i = 0; i < strategies.length; i++) {
                try {
                    const result = strategies[i]();
                    if (result && result.trim().length > 20) {
                        return { text: result.trim(), strategy: i + 1 };
                    }
                } catch(e) {}
            }
            return { text: '', strategy: 0 };
        }""")

        about_raw = about_text.get("text", "")
        about_strategy = about_text.get("strategy", 0)
        print(f"   🔍 About — strategy used: {about_strategy}, chars: {len(about_raw)}")

        if about_raw:
            # Clean heading prefix and trailing "see more" artifacts
            cleaned = re.sub(r'^(About|Sobre|Summary|Resumo)\s*\n?', '', about_raw)
            cleaned = re.sub(r'\s*(see more|ver mais|show more|mostrar mais)\s*$', '', cleaned, flags=re.IGNORECASE)
            profile["about"] = cleaned.strip()
        else:
            print("   ⚠️ About section: all strategies returned empty.")
    except Exception as e:
        print(f"   Warning: Could not extract about: {e}")

    # --- Experience ---
    try:
        experience_items = page.evaluate("""() => {
            const results = [];
            const sections = document.querySelectorAll('section');
            for (const section of sections) {
                const heading = section.querySelector('h2, div[aria-label]');
                if (!heading) continue;
                const headingText = (heading.innerText || heading.getAttribute('aria-label') || '').trim();
                if (/^(Experience|Experiência|Experiencia)$/i.test(headingText) || headingText.includes('Experience') || headingText.includes('Experiência')) {
                    // Get all experience items
                    const items = section.querySelectorAll('li.artdeco-list__item');
                    for (const item of items) {
                        const lines = (item.innerText || '')
                            .split('\\n')
                            .map(l => l.trim())
                            .filter(l => l.length > 1);
                        if (lines.length >= 2) {
                            results.push({
                                title: lines[0] || '',
                                company: lines[1] || '',
                                period: lines[2] || '',
                                description: lines.slice(3).join(' ')
                            });
                        }
                    }
                    break;
                }
            }
            return results;
        }""")
        if experience_items:
            profile["experience"] = experience_items
    except Exception as e:
        print(f"   Warning: Could not extract experience: {e}")

    # --- Skills ---
    try:
        skills_items = page.evaluate("""() => {
            const results = [];
            const sections = document.querySelectorAll('section');
            for (const section of sections) {
                const heading = section.querySelector('h2, div[aria-label]');
                if (!heading) continue;
                const headingText = (heading.innerText || heading.getAttribute('aria-label') || '').trim();
                if (/^(Skills|Competências|Habilidades)$/i.test(headingText) || headingText.includes('Skills') || headingText.includes('Competências')) {
                    const items = section.querySelectorAll('li.artdeco-list__item');
                    for (const item of items) {
                        const name = item.querySelector('div.t-bold span[aria-hidden]');
                        if (name && name.innerText.trim()) {
                            results.push(name.innerText.trim());
                        }
                    }
                    break;
                }
            }
            return results;
        }""")
        if skills_items:
            profile["skills"] = skills_items
    except Exception as e:
        print(f"   Warning: Could not extract skills: {e}")

    return profile


def _switch_language(page: Page, lang_code: str) -> bool:
    """
    Attempt to switch the profile language via LinkedIn's language selector.
    lang_code: 'pt' or 'en'.
    Returns True if language switch was successful.
    """
    try:
        # LinkedIn allows viewing the profile in different languages via URL param or menu
        current_url = page.url.split("?")[0]

        if lang_code == "en":
            target_url = f"{current_url}?locale=en_US"
        else:
            target_url = f"{current_url}?locale=pt_BR"

        page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)
        return True
    except Exception as e:
        print(f"   Warning: Could not switch language to {lang_code}: {e}")
        return False


def scrape_profile(profile_url: str = "https://www.linkedin.com/in/me/") -> dict:
    """
    Scrape the user's LinkedIn profile in PT and EN.

    Args:
        profile_url: The profile URL. Defaults to /in/me/ (currently logged-in user).

    Returns:
        {
            "profile_url": str,
            "name": str,
            "location": str,
            "en": { headline, about, experience, skills },
            "pt": { headline, about, experience, skills },
        }
    """
    print(f"\n🔍 Scraping LinkedIn profile...")
    print(f"   → Target: {profile_url}")

    result = {
        "profile_url": "",
        "name": "",
        "location": "",
        "en": {"headline": "", "about": "", "experience": [], "skills": []},
        "pt": {"headline": "", "about": "", "experience": [], "skills": []},
    }

    with sync_playwright() as p:
        browser, context = _create_context(p, headless=True)
        page = context.new_page()

        try:
            page.set_viewport_size({"width": 1280, "height": 1024})
            page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(4)

            # Check if redirected to login
            if "login" in page.url or "checkpoint" in page.url:
                print("   ❌ Session expired. Click 'LinkedIn Login' in the Job Scraper.")
                return result

            # Resolve the actual profile URL (in case /in/me/ was used)
            result["profile_url"] = page.url.split("?")[0]
            print(f"   ✅ Profile URL resolved: {result['profile_url']}")

            # --- Extract user name ---
            try:
                name_el = page.query_selector("h1.text-heading-xlarge")
                if name_el:
                    result["name"] = _clean(name_el.inner_text())
                    print(f"   👤 Name: {result['name']}")
            except Exception:
                pass

            # --- Extract location ---
            try:
                loc_el = page.query_selector(
                    "span.text-body-small.inline.t-black--light.break-words"
                )
                if loc_el:
                    result["location"] = _clean(loc_el.inner_text())
            except Exception:
                pass

            # --- Scrape in English ---
            print("   🌐 Scraping English version...")
            _switch_language(page, "en")
            result["en"] = _extract_profile(page)
            print(f"   ✅ EN: headline={bool(result['en']['headline'])}, "
                  f"about={bool(result['en']['about'])}, "
                  f"exp={len(result['en']['experience'])}, "
                  f"skills={len(result['en']['skills'])}")

            # --- Scrape in Portuguese ---
            print("   🇧🇷 Scraping Portuguese version...")
            _switch_language(page, "pt")
            result["pt"] = _extract_profile(page)
            print(f"   ✅ PT: headline={bool(result['pt']['headline'])}, "
                  f"about={bool(result['pt']['about'])}, "
                  f"exp={len(result['pt']['experience'])}, "
                  f"skills={len(result['pt']['skills'])}")

            # Fallback: if one language is empty, copy from the other
            for field in ["headline", "about"]:
                if not result["en"][field] and result["pt"][field]:
                    result["en"][field] = result["pt"][field]
                elif not result["pt"][field] and result["en"][field]:
                    result["pt"][field] = result["en"][field]

            if not result["en"]["experience"] and result["pt"]["experience"]:
                result["en"]["experience"] = result["pt"]["experience"]
            elif not result["pt"]["experience"] and result["en"]["experience"]:
                result["pt"]["experience"] = result["en"]["experience"]

            if not result["en"]["skills"] and result["pt"]["skills"]:
                result["en"]["skills"] = result["pt"]["skills"]

            print(f"\n🎉 Profile import complete for: {result['name']}")
            return result

        except Exception as e:
            print(f"   ❌ Error during profile scrape: {e}")
            raise
        finally:
            browser.close()
