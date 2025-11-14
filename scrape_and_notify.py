# scrape_and_notify.py
import os
import sys
import json
import time
import hashlib
import traceback
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# envs
USER = os.getenv("COLLEGE_USER")
PASS = os.getenv("COLLEGE_PASS")
ATTENDANCE_URL = os.getenv("ATTENDANCE_URL")
TW_SID = os.getenv("TWILIO_ACCOUNT_SID")
TW_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TW_FROM = os.getenv("TWILIO_WHATSAPP_FROM")
TW_TO = os.getenv("USER_WHATSAPP_TO")

CACHE_FILE = Path("last_sent.json")
CURRENT_FILE = Path("attendance.json")

# validate required envs early
REQUIRED = {
    "ATTENDANCE_URL": ATTENDANCE_URL,
}
missing = [k for k, v in REQUIRED.items() if not v]
if missing:
    print("ERROR: Missing required environment variables:", ", ".join(missing))
    print("Set them in your GitHub repository secrets or local .env file.")
    sys.exit(2)

if not (ATTENDANCE_URL.startswith("http://") or ATTENDANCE_URL.startswith("https://")):
    print("ERROR: ATTENDANCE_URL must start with http:// or https://")
    sys.exit(3)

# helpers
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
    try:
        from twilio.rest import Client
        client = Client(TW_SID, TW_TOKEN)
        msg = client.messages.create(from_=TW_FROM, body=body, to=TW_TO)
        print("Sent message SID:", msg.sid)
        return True
    except Exception as e:
        print("Twilio send error:", e)
        return False

# debug save
def _save_debug(page, prefix="failure"):
    try:
        ss = Path(f"{prefix}_screenshot.png")
        html = Path(f"{prefix}_page.html")
        page.screenshot(path=str(ss), full_page=True)
        html.write_text(page.content())
        print(f"Saved debug files: {ss}, {html}")
    except Exception as e:
        print("Failed to save debug files:", e)

# generic table parsing fallback:
def parse_tables_for_attendance(page):
    """Try to find a table with headers that look like attendance and parse rows."""
    tables = page.query_selector_all("table")
    subjects = []
    for t in tables:
        try:
            headers = [h.inner_text().strip().lower() for h in t.query_selector_all("thead th")]
            # if no thead, try first row as header
            if not headers:
                first_row = t.query_selector("tr")
                if first_row:
                    headers = [c.inner_text().strip().lower() for c in first_row.query_selector_all("th,td")]
            # quick check for attendance-like headers
            if any(k in " ".join(headers) for k in ("subject", "attendance", "present", "percentage", "percent", "total", "absent")):
                rows = t.query_selector_all("tbody tr") or t.query_selector_all("tr")[1:]
                for r in rows:
                    cols = r.query_selector_all("td")
                    if not cols:
                        continue
                    texts = [c.inner_text().strip() for c in cols]
                    # heuristic: match by header names if present
                    subj = texts[0] if len(texts) >= 1 else ""
                    present = texts[1] if len(texts) >= 2 else ""
                    total = texts[2] if len(texts) >= 3 else ""
                    percent = ""
                    # try to find percent-looking column
                    for ttxt in texts:
                        if ttxt.endswith("%") or "percent" in ttxt.lower():
                            percent = ttxt
                            break
                    subjects.append({
                        "subject": subj,
                        "present": present,
                        "total": total,
                        "percent": percent
                    })
                if subjects:
                    return subjects
        except Exception as e:
            print("table parse error:", e)
    return subjects

# main scraping (robust)
def scrape_attendance(max_retries=3):
    from playwright.sync_api import sync_playwright
    last_err = None
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"})
        for attempt in range(1, max_retries + 1):
            try:
                print(f"[scrape] attempt {attempt} -> goto {ATTENDANCE_URL}")
                page.goto(ATTENDANCE_URL, timeout=120000, wait_until="networkidle")
                page.wait_for_timeout(1500)
                # If portal requires login flow, you must add login steps below:
                # Example (uncomment and adjust selectors if necessary):
                # page.fill("input[name='username']", USER)
                # page.fill("input[name='password']", PASS)
                # page.click("button[type='submit']")
                # page.wait_for_load_state("networkidle")

                # Try to parse known selectors first (adjust these selectors to the portal layout)
                subjects = []
                # Common: table with id or class
                elements = page.query_selector_all("table#attendance-table tbody tr, table.attendance tbody tr, .attendance-table tr")
                if elements:
                    for r in elements:
                        cols = r.query_selector_all("td")
                        if len(cols) < 1:
                            continue
                        subject = cols[0].inner_text().strip()
                        present = cols[1].inner_text().strip() if len(cols) > 1 else ""
                        total = cols[2].inner_text().strip() if len(cols) > 2 else ""
                        percent = cols[3].inner_text().strip() if len(cols) > 3 else ""
                        subjects.append({"subject": subject, "present": present, "total": total, "percent": percent})
                # fallback: generic table parser
                if not subjects:
                    subjects = parse_tables_for_attendance(page)

                # extra fallback: find any summary blocks
                if not subjects:
                    summary_items = page.query_selector_all(".attendance-item, .att-row, .att-entry")
                    for it in summary_items:
                        t_el = it.query_selector(".title") or it.query_selector("h4") or it.query_selector("label")
                        v_el = it.query_selector(".value") or it.query_selector("span") or it.query_selector("p")
                        if t_el and v_el:
                            subjects.append({"subject": t_el.inner_text().strip(), "value": v_el.inner_text().strip()})

                data = {
                    "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    "items": subjects
                }
                # save current snapshot
                CURRENT_FILE.write_text(json.dumps(data, indent=2))
                browser.close()
                return data
            except Exception as e:
                last_err = e
                print(f"[scrape] attempt {attempt} failed: {e}")
                try:
                    _save_debug(page, prefix=f"failure_attempt_{attempt}")
                except Exception as se:
                    print("debug save err:", se)
                backoff = 2 ** attempt
                print(f"Retrying in {backoff}s...")
                time.sleep(backoff)
        browser.close()
    print("All scrape attempts failed. Raising last exception.")
    print(traceback.format_exception_only(type(last_err), last_err))
    raise last_err

def format_message(att_data):
    lines = []
    lines.append(f"Attendance update ({att_data.get('scraped_at')})")
    for it in att_data.get("items", [])[:20]:
        if "percent" in it and it["percent"]:
            lines.append(f"{it['subject']}: {it['percent']} ({it.get('present','')}/{it.get('total','')})")
        elif "value" in it:
            lines.append(f"{it['subject']}: {it['value']}")
        else:
            lines.append(f"{it.get('subject','')}: {it.get('present','')}/{it.get('total','')}")
    return "\n".join(lines)

def main():
    try:
        att = scrape_attendance()
    except Exception as e:
        print("Scrape failed:", e)
        sys.exit(4)

    new_hash = hash_obj(att)
    cache = read_cache()
    last_hash = cache.get("last_hash")
    print("new_hash:", new_hash, "last_hash:", last_hash)

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


