# attendance_bot.py
# Run by GitHub Actions
# Requires: requests, beautifulsoup4, twilio

import os
import re
import requests
from bs4 import BeautifulSoup
from twilio.rest import Client

# Read secrets from GitHub environment
COLLEGE_USER = os.getenv("COLLEGE_USER")
COLLEGE_PASS = os.getenv("COLLEGE_PASS")
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
MY_PHONE_NUMBER = os.getenv("MY_PHONE_NUMBER")

# Portal URLs
LOGIN_URL = "https://mgit.winnou.net/index.php"
DASHBOARD_URL = "https://mgit.winnou.net/index.php"

def login_and_get_html():
    session = requests.Session()
    r = session.get(LOGIN_URL, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Build payload using form inputs (best-effort)
    payload = {}
    form = soup.find("form")
    action = LOGIN_URL
    if form:
        action = form.get("action") or LOGIN_URL
        for inp in form.find_all("input"):
            name = inp.get("name")
            if not name:
                continue
            payload[name] = inp.get("value", "")

    # guess names
    user_key = None
    pass_key = None
    for k in payload.keys():
        lk = k.lower()
        if "user" in lk or "email" in lk or "roll" in lk:
            user_key = k
        if "pass" in lk or "pwd" in lk:
            pass_key = k

    if not user_key:
        user_key = "username"
    if not pass_key:
        pass_key = "password"

    payload[user_key] = COLLEGE_USER
    payload[pass_key] = COLLEGE_PASS

    if action.startswith("/"):
        from urllib.parse import urljoin
        action = urljoin(LOGIN_URL, action)

    resp = session.post(action, data=payload, timeout=20)
    resp.raise_for_status()

    dash = session.get(DASHBOARD_URL, timeout=20)
    dash.raise_for_status()
    return dash.text, session

def is_part_of_date(text, match_start, match_end):
    before = text[max(0, match_start-6):match_start]
    after = text[match_end:match_end+6]
    if "-" in before or "-" in after or "/" in before or "/" in after:
        return True
    return False

def extract_attendance(html):
    soup = BeautifulSoup(html, "html.parser")
    full_text = soup.get_text(" ", strip=True)

    # 1) Look for explicit percent formats anywhere first (72.29% or 72%)
    pct_matches = list(re.finditer(r"(\d{1,3}(?:\.\d{1,2})?)\s*%", full_text))
    if pct_matches:
        # pick the percent closest to the "Attendance" word if present
        att_idx = full_text.lower().find("attendance")
        if att_idx != -1:
            best = min(pct_matches, key=lambda m: abs(m.start() - att_idx))
            val = float(best.group(1))
            if 0 <= val <= 100:
                return (str(val).rstrip('0').rstrip('.') if '.' in str(val) else str(int(val))) + "%"
        else:
            # fallback: choose the largest reasonable percent <=100
            values = [float(m.group(1)) for m in pct_matches if float(m.group(1)) <= 100]
            if values:
                val = max(values)
                return (str(val).rstrip('0').rstrip('.') if '.' in str(val) else str(int(val))) + "%"

    # 2) Look specifically near "Attendance" labels in the DOM
    attendance_tags = soup.find_all(text=re.compile(r"\bAttendance\b", re.I))
    candidates = []
    for tag in attendance_tags:
        parent = tag.parent
        # search parent text and siblings for patterns
        scope_text = parent.get_text(" ", strip=True) if parent else tag
        # 2a) pattern like (72.29)
        paren = re.search(r"\((\d{1,3}(?:\.\d{1,2})?)\)", scope_text)
        if paren:
            val = float(paren.group(1))
            if 0 <= val <= 100:
                return (str(val).rstrip('0').rstrip('.') if '.' in str(val) else str(int(val))) + "%"

        # 2b) explicit percent in scope
        pct = re.search(r"(\d{1,3}(?:\.\d{1,2})?)\s*%", scope_text)
        if pct:
            val = float(pct.group(1))
            if 0 <= val <= 100:
                return (str(val).rstrip('0').rstrip('.') if '.' in str(val) else str(int(val))) + "%"

        # 2c) any number token in scope (filter out dates)
        for m in re.finditer(r"(\d{1,3}(?:\.\d{1,2})?)", scope_text):
            token = m.group(1)
            # find token position in full_text (approx)
            idx = full_text.find(token)
            if idx != -1 and not is_part_of_date(full_text, idx, idx+len(token)):
                val = float(token)
                if 0 <= val <= 100:
                    candidates.append((abs(full_text.lower().find("attendance") - idx), val))

    if candidates:
        # choose closest candidate to the word 'Attendance'
        candidates.sort(key=lambda x: x[0])
        val = candidates[0][1]
        return (str(val).rstrip('0').rstrip('.') if '.' in str(val) else str(int(val))) + "%"

    # 3) Special targeted search: numbers in parentheses anywhere (portal shows (72.29) style)
    paren_all = list(re.finditer(r"\((\d{1,3}(?:\.\d{1,2})?)\)", full_text))
    if paren_all:
        # try to pick the one nearest to 'Attendance' word
        att_idx = full_text.lower().find("attendance")
        if att_idx != -1:
            best = min(paren_all, key=lambda m: abs(m.start() - att_idx))
            val = float(best.group(1))
            if 0 <= val <= 100:
                return (str(val).rstrip('0').rstrip('.') if '.' in str(val) else str(int(val))) + "%"
        else:
            # choose the decimal value if present (prefer decimals)
            decimals = [float(m.group(1)) for m in paren_all if '.' in m.group(1) and 0 <= float(m.group(1)) <= 100]
            if decimals:
                val = max(decimals)
                return (str(val).rstrip('0').rstrip('.') if '.' in str(val) else str(int(val))) + "%"

    # 4) Fallback: scan page for numbers not part of dates and pick sensible candidate
    all_nums = []
    for m in re.finditer(r"(\d{1,3}(?:\.\d{1,2})?)", full_text):
        s,e = m.start(), m.end()
        if is_part_of_date(full_text, s, e):
            continue
        val = float(m.group(1))
        if 0 <= val <= 100:
            all_nums.append(val)

    if all_nums:
        # prefer decimal numbers (attendance often has decimals)
        decimals = [n for n in all_nums if not n.is_integer()]
        if decimals:
            val = max(decimals)
        else:
            val = max(all_nums)
        return (str(val).rstrip('0').rstrip('.') if '.' in str(val) else str(int(val))) + "%"

    # 5) Nothing found — print debug snippet for troubleshooting
    print("DEBUG: Couldn't find attendance automatically.")
    print("PAGE_SNIPPET:", full_text[:1200])
    return "Not Found"

def send_whatsapp_message(attendance):
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    message = (
        f"📢 College Attendance Update\n"
        f"Your current attendance is: {attendance}\n"
        f"🕒 Have a great day!"
    )
    msg = client.messages.create(
        body=message,
        from_=f"whatsapp:{TWILIO_PHONE_NUMBER}",
        to=f"whatsapp:{MY_PHONE_NUMBER}"
    )
    print("Message sent:", msg.sid)

def main():
    try:
        html, session = login_and_get_html()
        att = extract_attendance(html)
        print("Fetched attendance:", att)
        send_whatsapp_message(att)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
