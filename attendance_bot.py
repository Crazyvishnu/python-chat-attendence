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

def get_attendance():
    session = requests.Session()

    # Step 1: Get login page
    r = session.get(LOGIN_URL, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Step 2: Build form payload
    payload = {}
    for inp in soup.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        payload[name] = inp.get("value", "")

    # Try to find username/password field names
    user_field = None
    pass_field = None
    for k in payload.keys():
        if "user" in k.lower() or "email" in k.lower() or "roll" in k.lower():
            user_field = k
        if "pass" in k.lower():
            pass_field = k

    if not user_field:
        user_field = "username"
    if not pass_field:
        pass_field = "password"

    payload[user_field] = COLLEGE_USER
    payload[pass_field] = COLLEGE_PASS

    # Step 3: Submit login
    login_resp = session.post(LOGIN_URL, data=payload, timeout=15)
    login_resp.raise_for_status()

    # Step 4: Fetch dashboard
    dash_resp = session.get(DASHBOARD_URL, timeout=15)
    dash_resp.raise_for_status()

    # Step 5: Extract attendance %
    html = dash_resp.text
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    match = re.search(r"(\d{1,3}(?:\.\d{1,2})?)\s*%?", text)
    attendance = match.group(1) + "%" if match else "Not Found"
    return attendance

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
        att = get_attendance()
        print("Fetched attendance:", att)
        send_whatsapp_message(att)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
