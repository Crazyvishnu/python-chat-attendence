# playwright_scripts/playwright_attendance.py
import os
import asyncio
import json
import time
import traceback
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# output files
DIAGNOSTIC_HTML = Path("diagnostic_page.html")
DIAGNOSTIC_SCREENSHOT = Path("diagnostic_screenshot.png")
FATAL_HTML = Path("fatal_error_page.html")
FATAL_SCREENSHOT = Path("fatal_error_screenshot.png")
RESULT_JSON = Path("result.json")

COL_USER = os.getenv("COLLEGE_USER")
COL_PASS = os.getenv("COLLEGE_PASS")
BASE_URL = os.getenv("COLLEGE_URL", "https://mgit.winnou.net/index.php")
MAX_RETRIES = 3

async def fetch_attendance():
    # basic result template
    result = {"success": False, "attendance": None, "error": None}
    if not COL_USER or not COL_PASS:
        result["error"] = "Missing COLLEGE_USER or COLLEGE_PASS environment variables"
        RESULT_JSON.write_text(json.dumps(result))
        return result

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        try:
            # Try a few attempts for flaky network/pages
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    await page.goto(BASE_URL, timeout=90000)  # 90s
                    await page.wait_for_load_state("networkidle", timeout=45000)
                    break
                except PWTimeout:
                    if attempt == MAX_RETRIES:
                        raise
                    else:
                        await page.screenshot(path=f"retry_nav_{attempt}.png")
                        time.sleep(2 ** attempt)
            # Save initial diagnostic HTML + screenshot
            DIAGNOSTIC_HTML.write_text(await page.content(), encoding="utf-8")
            await page.screenshot(path=str(DIAGNOSTIC_SCREENSHOT), full_page=True)

            # Detect simple CAPTCHA / challenge markers
            # (the login page includes #captcha input; also look for 'captcha' keywords)
            content_lower = (await page.content()).lower()
            if ("captcha" in content_lower) or (await page.query_selector("#captcha") is not None):
                result["error"] = "CAPTCHA detected on login page; cannot automate."
                RESULT_JSON.write_text(json.dumps(result))
                return result

            # Fill login form (selectors observed in diagnostic HTML)
            # update these selectors if site changes
            await page.fill("#username", COL_USER)
            await page.fill("#modlgn_passwd", COL_PASS)

            # Click sign-in button (class 'signinbutton' in uploaded HTML)
            sign_button = await page.query_selector("input.signinbutton") or await page.query_selector("input[type=submit]")
            if not sign_button:
                raise Exception("Sign-in button not found; selector may have changed.")

            # Submit and wait
            await sign_button.click()
            # Wait for navigation / dashboard to load
            try:
                await page.wait_for_load_state("networkidle", timeout=45000)
            except PWTimeout:
                # allow extra time for slow pages
                await page.wait_for_timeout(5000)

            # Save post-login HTML for debugging
            post_html = await page.content()
            Path("after_login_page.html").write_text(post_html, encoding="utf-8")
            await page.screenshot(path="after_login_screenshot.png", full_page=True)

            # Now try to find attendance element — you must replace the selector below
            # with the actual selector shown on the logged-in page.
            # Example strategies:
            # - Search for text "attendance" in the page
            # - Look for a known CSS id/class
            page_text = (await page.inner_text("body")).lower()

            # Heuristic: look for percent numbers near 'attendance'
            if "attendance" in page_text:
                # crude extract: find substring around 'attendance'
                idx = page_text.find("attendance")
                snippet = page_text[max(0, idx-200): idx+200]
                # try to find a number like 85% in snippet
                import re
                m = re.search(r"(\d{1,3}\s*%|\d{1,3}\.\d\s*%)", snippet)
                attendance_val = m.group(0) if m else None
                if not attendance_val:
                    # fallback: return the snippet so you can inspect manually
                    attendance_val = "attendance found in snippet: " + snippet.strip().replace("\n"," ")
                result.update({"success": True, "attendance": attendance_val})
                RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False))
                return result
            else:
                # No attendance text found — maybe we need to navigate to "Attendance" page
                # try clicking the 'Attendance' link that appears in diagnostic tags (if present)
                att_link = await page.query_selector("a:has-text('Attendance')")
                if att_link:
                    await att_link.click()
                    await page.wait_for_load_state("networkidle")
                    await page.screenshot(path="attendance_page_screenshot.png", full_page=True)
                    page_text2 = (await page.inner_text("body")).lower()
                    idx = page_text2.find("attendance")
                    snippet = page_text2[max(0, idx-200): idx+200] if idx!=-1 else page_text2[:400]
                    import re
                    m = re.search(r"(\d{1,3}\s*%|\d{1,3}\.\d\s*%)", snippet)
                    attendance_val = m.group(0) if m else "attendance page loaded but no percent found"
                    result.update({"success": True, "attendance": attendance_val})
                    RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False))
                    return result

            # nothing found
            result["error"] = "Unable to locate attendance text after login. See after_login_page.html and screenshots."
            RESULT_JSON.write_text(json.dumps(result))
            return result

        except Exception as e:
            # fatal: save everything for diagnostics
            err = traceback.format_exc()
            FATAL_HTML.write_text(await page.content() if page else str(err), encoding="utf-8")
            with open("fatal_error.txt", "w", encoding="utf-8") as f:
                f.write(err)
            try:
                await page.screenshot(path=str(FATAL_SCREENSHOT), full_page=True)
            except Exception:
                pass
            result["error"] = f"Exception: {str(e)}; see fatal_error.txt"
            RESULT_JSON.write_text(json.dumps(result))
            return result
        finally:
            await browser.close()

if __name__ == "__main__":
    res = asyncio.run(fetch_attendance())
    print(json.dumps(res, ensure_ascii=False))
    if not res.get("success"):
        # non-zero exit to indicate Playwright failure
        raise SystemExit(2)
    else:
        # success
        raise SystemExit(0)
