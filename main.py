#!/usr/bin/env python3
"""
Robust MGIT attendance scraper for https://mgit.winnou.net/

- Tries many common login selectors automatically
- Supports overriding selectors via env vars:
    USERNAME_SELECTOR, PASSWORD_SELECTOR, SUBMIT_SELECTOR, ATTENDANCE_SELECTOR
  (selectors should be CSS selectors)
- If attendance not found, dumps a safe HTML snippet to logs to help create a precise selector.
- Sends WhatsApp via Twilio (same secrets as before).
"""

import os
import re
import time
import logging
from typing import Optional, List
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from twilio.rest import Client

# Config (defaults)
LOGIN_URL = os.getenv("LOGIN_URL", "https://mgit.winnou.net/")
ATTENDANCE_URL = os.getenv("ATTENDANCE_URL", "https://mgit.winnou.net/StudentInfo.aspx")
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "3"))
RETRY_BACKOFF = int(os.getenv("RETRY_BACKOFF", "5"))
DRIVER_TIMEOUT = int(os.getenv("DRIVER_TIMEOUT", "15"))

# Optional manual selectors (CSS); if set, code will prefer them
USERNAME_SELECTOR = os.getenv("USERNAME_SELECTOR")
PASSWORD_SELECTOR = os.getenv("PASSWORD_SELECTOR")
SUBMIT_SELECTOR = os.getenv("SUBMIT_SELECTOR")
ATTENDANCE_SELECTOR = os.getenv("ATTENDANCE_SELECTOR")  # CSS or XPath if starts with //

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("attendance-bot")

# Utility: candidate selector sets to try (CSS)
COMMON_USERNAME_SELECTORS = [
    "#txtusername", "#username", "input[name='username']", "input[type='text']",
    "input[id*='user']", "input[name*='user']"
]
COMMON_PASSWORD_SELECTORS = [
    "#txtpassword", "#password", "input[name='password']", "input[type='password']",
    "input[id*='pass']", "input[name*='pass']"
]
COMMON_SUBMIT_SELECTORS = [
    "#btnSubmit", "button[type='submit']", "input[type='submit']", "button[id*='login']",
    "button[name*='login']"
]

# Attendance guess selectors (common patterns)
COMMON_ATTENDANCE_SELECTORS = [
    "span.attendance", "div.attendance", "td.attendance", "span[data-attr*='attendance']",
    "table#attendance", "//span[contains(.,'%')]", "//td[contains(.,'%')]"
]


def create_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/115.0 Safari/537.36"
    )
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=opts)
    return driver


def extract_attendance_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%?", text)
    if m:
        try:
            val = float(m.group(1))
            if 0 <= val <= 100:
                return f"{val:.2f}".rstrip("0").rstrip(".")
        except ValueError:
            return None
    return None


def try_fill_by_selectors(driver, username, password) -> bool:
    """
    Try multiple selector strategies to locate inputs and submit.
    Returns True if submit action was attempted.
    """
    wait = WebDriverWait(driver, DRIVER_TIMEOUT)

    # 1) If explicit selectors provided, try them first
    if USERNAME_SELECTOR and PASSWORD_SELECTOR:
        try:
            logger.info("Trying provided selectors: %s / %s", USERNAME_SELECTOR, PASSWORD_SELECTOR)
            el_u = driver.find_element(By.CSS_SELECTOR, USERNAME_SELECTOR)
            el_p = driver.find_element(By.CSS_SELECTOR, PASSWORD_SELECTOR)
            el_u.clear(); el_u.send_keys(username)
            el_p.clear(); el_p.send_keys(password)
            # Try provided submit selector too
            if SUBMIT_SELECTOR:
                try:
                    s = driver.find_element(By.CSS_SELECTOR, SUBMIT_SELECTOR)
                    s.click()
                except Exception:
                    try:
                        driver.find_element(By.CSS_SELECTOR, PASSWORD_SELECTOR).submit()
                    except Exception:
                        pass
            else:
                try:
                    driver.find_element(By.CSS_SELECTOR, PASSWORD_SELECTOR).submit()
                except Exception:
                    # fallback: press enter via JS
                    driver.execute_script("arguments[0].dispatchEvent(new KeyboardEvent('keydown', {'key':'Enter'}));", el_p)
            return True
        except Exception as e:
            logger.info("Provided selectors failed: %s", e)

    # 2) Try common ID/name selectors
    for su in ([USERNAME_SELECTOR] if USERNAME_SELECTOR else COMMON_USERNAME_SELECTORS):
        for sp in ([PASSWORD_SELECTOR] if PASSWORD_SELECTOR else COMMON_PASSWORD_SELECTORS):
            try:
                el_u = driver.find_element(By.CSS_SELECTOR, su) if su.startswith("#") or "input" in su or "[" in su else driver.find_element(By.NAME, su)
                el_p = driver.find_element(By.CSS_SELECTOR, sp) if sp.startswith("#") or "input" in sp or "[" in sp else driver.find_element(By.NAME, sp)
                el_u.clear(); el_u.send_keys(username)
                el_p.clear(); el_p.send_keys(password)
                # submit
                submitted = False
                # try submit selectors list
                for ss in COMMON_SUBMIT_SELECTORS:
                    try:
                        s = driver.find_element(By.CSS_SELECTOR, ss)
                        s.click()
                        submitted = True
                        break
                    except Exception:
                        pass
                if not submitted:
                    try:
                        el_p.submit()
                        submitted = True
                    except Exception:
                        pass
                return submitted
            except Exception:
                continue
    # 3) Try generic form detection: find a form with a password input
    try:
        forms = driver.find_elements(By.TAG_NAME, "form")
        for f in forms:
            try:
                pwd = f.find_element(By.CSS_SELECTOR, "input[type='password']")
                txt_candidates = f.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='email'], input:not([type])")
                if not txt_candidates:
                    continue
                txt = txt_candidates[0]
                txt.clear(); txt.send_keys(username)
                pwd.clear(); pwd.send_keys(password)
                # try form submit
                try:
                    f.submit()
                except Exception:
                    try:
                        btn = f.find_element(By.CSS_SELECTOR, "button[type='submit']")
                        btn.click()
                    except Exception:
                        pass
                return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def find_attendance_on_page(driver) -> Optional[str]:
    # 1) If ATTENDANCE_SELECTOR given: support XPath (prefix //) or CSS
    if ATTENDANCE_SELECTOR:
        try:
            if ATTENDANCE_SELECTOR.strip().startswith("//"):
                els = driver.find_elements(By.XPATH, ATTENDANCE_SELECTOR)
            else:
                els = driver.find_elements(By.CSS_SELECTOR, ATTENDANCE_SELECTOR)
            for el in els:
                txt = (el.text or "").strip()
                candidate = extract_attendance_from_text(txt)
                if candidate:
                    return candidate
        except Exception:
            logger.info("Given ATTENDANCE_SELECTOR failed, continuing to generic heuristics.")

    # 2) Scan span/td elements for percent-like text
    try:
        candidates = driver.find_elements(By.XPATH, "//span|//td|//div|//p")
        for el in candidates:
            txt = (el.text or "").strip()
            if not txt:
                continue
            if "%" in txt or re.search(r"\d{1,3}\.\d", txt) or ("(" in txt and ")" in txt):
                candidate = extract_attendance_from_text(txt)
                if candidate:
                    return candidate
    except Exception:
        pass

    # 3) fallback: search page source
    try:
        page = driver.page_source
        m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", page)
        if m:
            return extract_attendance_from_text(m.group(0))
    except Exception:
        pass

    return None


def dump_page_snippet(driver, max_bytes: int = 40000):
    """
    Dump a truncated page source to logs to help create a selector.
    This will not include credentials but *may* include user-visible info from the page.
    """
    try:
        page = driver.page_source or ""
        snippet = page[:max_bytes]
        logger.info("==== BEGIN StudentInfo HTML SNIPPET (truncated) ====")
        logger.info(snippet)
        logger.info("==== END StudentInfo HTML SNIPPET ====")
    except Exception as e:
        logger.error("Failed to dump page snippet: %s", e)


def get_attendance_once() -> Optional[str]:
    driver = None
    try:
        driver = create_driver()
        logger.info("Opening login page: %s", LOGIN_URL)
        driver.get(LOGIN_URL)

        username = os.getenv("COLLEGE_USER")
        password = os.getenv("COLLEGE_PASS")
        if not username or not password:
            logger.error("Missing COLLEGE_USER / COLLEGE_PASS environment vars.")
            return None

        # Try login using best-effort selectors
        attempted = try_fill_by_selectors(driver, username, password)
        if attempted:
            logger.info("Login submit attempted; waiting for navigation...")
            time.sleep(2)  # short pause for redirect
        else:
            logger.warning("Automatic login attempts did not find fields. If you see a captcha or different selectors, set USERNAME_SELECTOR/PASSWORD_SELECTOR env vars and re-run.")

        # Navigate to attendance page in case login didn't redirect
        logger.info("Navigating to attendance page: %s", ATTENDANCE_URL)
        driver.get(ATTENDANCE_URL)

        # Wait for some content
        try:
            WebDriverWait(driver, DRIVER_TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException:
            logger.warning("Timeout waiting for StudentInfo page to load body.")

        attendance = find_attendance_on_page(driver)
        if attendance:
            logger.info("Attendance found: %s%%", attendance)
            return attendance

        # If not found, dump a snippet to logs to help create a precise selector
        logger.warning("Attendance not found automatically. Dumping StudentInfo HTML snippet to logs to help debug.")
        dump_page_snippet(driver)
        return None

    except TimeoutException as e:
        logger.error("Timeout: %s", e)
        return None
    except WebDriverException as e:
        logger.error("WebDriver error: %s", e)
        return None
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def get_attendance_with_retries() -> Optional[str]:
    attempt = 1
    while attempt <= MAX_ATTEMPTS:
        logger.info("Attempt %d/%d", attempt, MAX_ATTEMPTS)
        a = get_attendance_once()
        if a:
            return a
        sleep_for = RETRY_BACKOFF * (2 ** (attempt - 1))
        logger.info("Retrying after %d seconds...", sleep_for)
        time.sleep(sleep_for)
        attempt += 1
    logger.error("All attempts failed.")
    return None


def send_whatsapp_message(body: str) -> bool:
    logger.info("Preparing Twilio WhatsApp message.")
    account_sid = os.getenv("TWILIO_SID")
    auth_token = os.getenv("TWILIO_TOKEN")
    from_whatsapp = os.getenv("TWILIO_PHONE_NUMBER")
    my_phone = os.getenv("MY_PHONE_NUMBER")

    if not all([account_sid, auth_token, from_whatsapp, my_phone]):
        logger.error("Missing Twilio env vars.")
        return False

    if not from_whatsapp.startswith("whatsapp:"):
        from_whatsapp = f"whatsapp:{from_whatsapp}"
    to_whatsapp = f"whatsapp:{my_phone}" if not my_phone.startswith("whatsapp:") else my_phone

    client = Client(account_sid, auth_token)
    try:
        msg = client.messages.create(from_=from_whatsapp, to=to_whatsapp, body=body)
        logger.info("Message sent, SID: %s", getattr(msg, "sid", "<no-sid>"))
        return True
    except Exception as e:
        logger.exception("Twilio send failed: %s", e)
        return False


def main():
    attendance = get_attendance_with_retries()
    if attendance:
        body = f"📊 MGIT Attendance Update: {attendance}%"
    else:
        body = "⚠️ MGIT Attendance Bot: could not retrieve attendance. Check the workflow logs for an HTML snippet to help fix selectors."
    send_whatsapp_message(body)


if __name__ == "__main__":
    main()
