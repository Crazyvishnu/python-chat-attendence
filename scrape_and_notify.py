# scrape_and_notify.py
import json
import os
import hashlib
import time
from pathlib import Path
from twilio.rest import Client
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()  # local testing support with .env

# Config from env
USER = os.getenv("COLLEGE_USER")
PASS = os.getenv("COLLEGE_PASS")
ATTENDANCE_URL = os.getenv("ATTENDANCE_URL", "https://college.example.com/login")
TW_SID = os.getenv("TWILIO_ACCOUNT_SID")
TW_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TW_FROM = os.getenv("TWILIO_WHATSAPP_FROM")
TW_TO = os.getenv("USER_WHATSAPP_TO")

CACHE_FILE = Path("last_sent.json")
CURRENT_FILE = Path("attendance.json")

def hash_obj(obj):
    s = json.dumps(obj, sort_keys=True)
    return hashlib.sha256(s.encode()).hexdigest()

def read_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}

def write_cache(obj):
    CACHE_FILE.write_text(json.dumps(obj, indent=2))

def send_whatsapp(body: str):
    if not all([TW_SID, TW_TOKEN, TW_FROM, TW_TO]):
        print("Twilio env vars not fully set, skipping send.")
        return False
    client = Client(TW_SID, TW_TOKEN)
    try:
        msg = client.messages.create(
            from_=TW_FROM,
            body=body,
            to=TW_TO
        )
        print("Sent message SID:", msg.sid)
        return True
    except Exception as e:
        print("Twilio send error:", e)
        return False

def scrape_attendance():
    """Return a python dict describing attendance retrieved from the portal."""
    data = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        # 1) login page
        page.goto(ATTENDANCE_URL, timeout=30000)
        # Adapt selectors below to your college website.
        # Example:
        page.fill("input[name='username']", USER)
        page.fill("input[name='password']", PASS)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle", timeout=20000)
        time.sleep(1)

        # 2) Navigate to attendance section if needed:
        # page.click("a#attendance-link")
        # page.wait_for_load_state("networkidle")

        # 3) Extract attendance table. Update selector to match the real page.
        # This example expects rows with subject, present, total, percentage.
        rows = page.query_selector_all("table#attendance-table tbody tr")
        subjects = []
        for r in rows:
            cols = r.query_selector_all("td")
            if len(cols) < 3:
                continue
            subject = cols[0].inner_text().strip()
            present = cols[1].inner_text().strip()
            total = cols[2].inner_text().strip()
            percent = cols[3].inner_text().strip() if len(cols) > 3 else ""
            subjects.append({
                "subject": subject,
                "present": present,
                "total": total,
                "percent": percent
            })
        # fallback simple view: if no table, attempt to read a summary element
        if not subjects:
            # try selector by reading key-values
            summary_items = page.query_selector_all(".attendance-item")
            for it in summary_items:
                title = it.query_selector(".title").inner_text().strip()
                value = it.query_selector(".value").inner_text().strip()
                subjects.append({"subject": title, "value": value})
        browser.close()
        data = {
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "items": subjects
        }
    return data

def format_message(att_data):
    lines = []
    lines.append(f"Attendance update ({att_data.get('scraped_at')})")
    for it in att_data.get("items", [])[:10]:  # limit to first 10 subjects for brevity
        if "percent" in it and it["percent"]:
            lines.append(f"{it['subject']}: {it['percent']} ({it['present']}/{it['total']})")
        elif "value" in it:
            lines.append(f"{it['subject']}: {it['value']}")
        else:
            lines.append(f"{it['subject']}: {it.get('present','')}/{it.get('total','')}")
    return "\n".join(lines)

def main():
    try:
        att = scrape_attendance()
    except Exception as e:
        print("Scrape failed:", e)
        raise

    # write current snapshot
    CURRENT_FILE.write_text(json.dumps(att, indent=2))

    # compute hash and compare to cache
    new_hash = hash_obj(att)
    cache = read_cache()
    last_hash = cache.get("last_hash")

    print("new_hash:", new_hash, "last_hash:", last_hash)

    # decide if send: send if changed OR if no last_hash (first run)
    if new_hash != last_hash:
        body = format_message(att)
        ok = send_whatsapp(body)
        if ok:
            cache["last_hash"] = new_hash
            cache["last_sent_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            cache["last_payload"] = att
            write_cache(cache)
        else:
            print("Message not sent; not updating cache.")
    else:
        print("No change in attendance; not sending message.")

if __name__ == "__main__":
    main()

