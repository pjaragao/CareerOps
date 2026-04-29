"""
LinkedIn Profile Updater — automates updating the user's Headline and About sections.
Uses the existing authenticated session.
"""
import time
import re
from playwright.sync_api import sync_playwright, Page
from config import SESSION_FILE

def _create_context(playwright, headless=True):
    if not SESSION_FILE.exists() or SESSION_FILE.stat().st_size < 100:
        raise RuntimeError("No LinkedIn session found.")
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context(storage_state=str(SESSION_FILE))
    return browser, context

def update_linkedin_profile(profile_data: dict, headless: bool = True):
    """
    Update LinkedIn headline and about sections.
    profile_data: {"headline": "...", "about": "..."}
    """
    print(f"🚀 Starting LinkedIn profile update...")
    
    with sync_playwright() as p:
        browser, context = _create_context(p, headless=headless)
        page = context.new_page()
        
        try:
            # Go to profile edit page directly or /in/me/
            page.goto("https://www.linkedin.com/in/me/edit/forms/intro/desktop/", wait_until="domcontentloaded")
            time.sleep(5)
            
            if "login" in page.url:
                raise RuntimeError("Session expired during update.")

            # --- Update Headline ---
            if profile_data.get("headline"):
                print("   Updating headline...")
                # The ID for headline is usually fixed but let's be safe
                headline_field = page.query_selector('input[name="headline"]') or page.query_selector('textarea[name="headline"]')
                if headline_field:
                    headline_field.fill("")
                    headline_field.fill(profile_data["headline"][:220])
                else:
                    print("   ⚠️ Could not find headline field.")

            # Save intro changes
            save_btn = page.query_selector('button.artdeco-button--primary')
            if save_btn:
                save_btn.click()
                time.sleep(3)
                print("   ✅ Intro/Headline saved.")

            # --- Update About ---
            if profile_data.get("about"):
                print("   Updating About section...")
                page.goto("https://www.linkedin.com/in/me/edit/forms/about/desktop/", wait_until="domcontentloaded")
                time.sleep(5)
                
                about_field = page.query_selector('textarea[name="summary"]') or page.query_selector('#about-description')
                if about_field:
                    # Clear and fill
                    # Some LinkedIn fields are tricky with fill(), might need sequences
                    about_field.click()
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    about_field.fill(profile_data["about"][:2600])
                    
                    save_btn = page.query_selector('button.artdeco-button--primary')
                    if save_btn:
                        save_btn.click()
                        time.sleep(3)
                        print("   ✅ About section saved.")
                else:
                    print("   ⚠️ Could not find About field.")

            print("🎉 LinkedIn update complete!")
            return True
            
        except Exception as e:
            print(f"   ❌ Error updating profile: {e}")
            raise
        finally:
            browser.close()
