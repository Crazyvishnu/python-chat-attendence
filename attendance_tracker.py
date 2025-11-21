import os
import re
from datetime import datetime, timedelta, timezone

from playwright.sync_api import sync_playwright
from twilio.rest import Client


def get_ist_now():
    # IST = UTC + 5:30
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)


def scrape_attendance(username: str, password: str) -> str:
    """
    Logs into mgit.winnou.net and returns a text summary like:
    'Attendance: 75.27% | Last attended date: 21-11-2025'
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Open login page
        page.goto("https://mgit.winnou.net/", wait_until="networkidle")

        # 2. Fill username & password
        page.fill('input[type="text"]', username)
        page.fill('input[type="password"]', password)

        # 3. Click login
        # try common selectors – if one fails, move to next
        clicked = False
        for selector in ['input[type="submit"]', 'button[type="submit"]', "button:has-text('Login')"]:
            try:
                page.click(selector)
                clicked = True
                break
            except Exception:
                pass

        if not clicked:
            browser.close()
            raise RuntimeError("Could not find login button. Check selector.")

        # Wait for home page after login
        page.wait_for_load_state("networkidle")

        # 4. Read whole page text and find Attendance + Attended Date
        body_text = page.text_content("body") or ""

        attendance_match = re.search(r"Attendance\s*:\s*\(([\d.]+)\)", body_text)
        date_match = re.search(r"Attended Date\s*:\s*([0-9\-\/]+)", body_text)

        browser.close()

        if not attendance_match:
            return "Could not find attendance on MGIT page."

        percent = attendance_match.group(1)
        date_str = date_match.group(1) if date_match else "Unknown"

        return f"Attendance: {percent}% | Last attended date: {date_str}"


def send_whatsapp(message: str):
    # Use your secret names
    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    from_num = os.environ["TWILIO_PHONE_NUMBER"]  # must be WhatsApp-enabled number
    to_num = os.environ["MY_PHONE_NUMBER"]        # your WhatsApp (with whatsapp: prefix)

    client = Client(account_sid, auth_token)

    client.messages.create(
        from_=from_num,
        to=to_num,
        body=message,
    )


def main():
    username = os.environ["MGIT_USERNAME"]
    password = os.environ["MGIT_PASSWORD"]

    ist_now = get_ist_now().strftime("%d-%m-%Y %H:%M")

    try:
        attendance_summary = scrape_attendance(username, password)
        msg = f"📚 MGIT Attendance Update\nTime (IST): {ist_now}\n\n{attendance_summary}"
    except Exception as e:
        msg = f"❌ Error while fetching MGIT attendance at {ist_now} (IST): {e}"

    send_whatsapp(msg)


if __name__ == "__main__":
    main()
    
