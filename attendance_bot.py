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
    # check 5 chars before and after for - or / which indicates a date like 07-11-2025
    before = text[max(0, match_start-5):match_start]
    after = text[match_end:match_end+5]
    if "-" in before or "-" in after or "/" in before or "/" in after:
        return True
    return False

def extract_attendance(html):
    soup = BeautifulSoup(html, "html.parser")
    full_text = soup.get_text(" ", strip=True)

    # 1) Prefer explicit percentages (e.g., 72.29% or 72%) anywhere on page
    pct_matches = list(re.finditer(r"(\d{1,3}(?:\.\d{1,2})?)\s*%", full_text))
    if pct_matches:
        # if multiple, try to pick the one closest to the word "Attendance"
        attendance_positions = [m for m in pct_matches]
        # find index of "attendance" if exist
        att_idx = full_text.lower().find("attendance")
        if att_idx != -1:
            best = min(attendance_positions, key=lambda m: abs(m.start() - att_idx))
            return best.group(1) + "%"
        else:
            # pick first or the largest sensible percent <= 100
            cand_vals = [float(m.group(1)) for m in attendance_positions if float(m.group(1)) <= 100]
            if cand_vals:
                # pick the largest sensible percent (helps if stray small numbers exist)
                val = max(cand_vals)
                return (str(val).rstrip('0').rstrip('.') if '.' in str(val) else str(int(val))) + "%"

    # 2) If no explicit %, search numbers near "Attendance" in the DOM
    # find occurrences of the word "Attendance" (case-insensitive)
    att_tags = []
    for tag in soup.find_all(text=re.compile(r"Attendance", re.I)):
        att_tags.append(tag)

    candidates = []

    # Search in the nearby text (parent and siblings)
    for tag in att_tags:
        parent = tag.parent
        search_scope = parent.get_text(" ", strip=True) if parent else tag
        # find numeric candidates in that scope
        for m in re.finditer(r"(\d{1,3}(?:\.\d{1,2})?)", search_scope):
            start, end = m.start(), m.end()
            # map to positions in full_text by searching substring (approx)
            # we'll use the matched string and check if it's part of a date
            matched_text = m.group(1)
            # crude check: if matched_text appears in full_text near the 'attendance' index
            idx = full_text.find(matched_text)
            if idx != -1 and not is_part_of_date(full_text, idx, idx+len(matched_text)):
                val = float(matched_text)
                if 0 <= val <= 100:
                    candidates.append((abs(full_text.lower().find("attendance") - idx), val))

    if candidates:
        # pick the closest candidate to "Attendance"
        candidates.sort(key=lambda x: x[0])
        val = candidates[0][1]
        return (str(val).rstrip('0').rstrip('.') if '.' in str(val) else str(int(val))) + "%"

    # 3) As a fallback, scan whole page for numbers that look like percents (no % present)
    # collect numeric tokens that are not part of dates and are sensible percentages
    all_nums = []
    for m in re.finditer(r"(\d{1,3}(?:\.\d{1,2})?)", full_text):
        s,e = m.start(), m.end()
        if is_part_of_date(full_text, s, e):
            continue
        num = float(m.group(1))
        if 0 <= num <= 100:
            all_nums.append(num)

    if all_nums:
        # prefer a decimal value (attendance often has decimals), otherwise prefer the largest reasonable
        decimals = [n for n in all_nums if not n.is_integer()]
        if decimals:
            val = max(decimals)
        else:
            val = max(all_nums)
        return (str(val).rstrip('0').rstrip('.') if '.' in str(val) else str(int(val))) + "%"

    # nothing found
    # debug output to aid troubleshooting
    print("DEBUG: Couldn't find attendance automatically.")
    # Print some context to logs (first 800 chars)
    print("PAGE_SNIPPET:", full_text[:800])
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
