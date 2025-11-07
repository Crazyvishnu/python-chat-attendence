# attendance_bot.py
import os
import time
from twilio.rest import Client
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

load_dotenv()  # Load .env file

# === CONFIG ===
BASE_URL = "https://mgit.winnou.net/"
LAST_FILE = "last_attendance.txt"

COLLEGE_USER = os.getenv("COLLEGE_USER")
COLLEGE_PASS = os.getenv("COLLEGE_PASS")
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE_NUMBER", "whatsapp:+14155238886")
MY_PHONE = os.getenv("MY_PHONE_NUMBER")

# === Utilities ===
def read_last():
    if os.path.exists(LAST_FILE):
        with open(LAST_FILE, "r") as f:
            return f.read().strip()
    return None

def write_last(value):
    with open(LAST_FILE, "w") as f:
        f.write(value)

def send_whatsapp_message(body):
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    message = client.messages.create(
        from_=TWILIO_PHONE,
        to=MY_PHONE,
        body=body
    )
    print(f"✅ WhatsApp Message sent: SID={message.sid}")

# === Scrape Attendance ===
def get_attendance():
    print("🚀 Launching headless browser...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(BASE_URL)

    print("🔐 Logging in...")
    driver.find_element(By.NAME, "username").send_keys(COLLEGE_USER)
    driver.find_element(By.NAME, "passwd").send_keys(COLLEGE_PASS)
    driver.find_element(By.NAME, "SubmitL").click()
    time.sleep(5)

    # Click Student Info
    try:
        student_info = driver.find_element(By.LINK_TEXT, "Student Info")
        student_info.click()
        time.sleep(3)
    except Exception:
        print("⚠️ Couldn't click Student Info directly. Continuing...")

    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    # Try to locate attendance percentage
    print("🔎 Extracting attendance...")
    text = soup.get_text()
    import re
    match = re.search(r'Attendance[\s\S]{0,60}(\d{1,3}(?:\.\d{1,2})?)', text, re.I)
    percent = match.group(1) + "%" if match else None

    driver.quit()

    if percent:
        print("🎯 Attendance:", percent)
        return percent
    else:
        raise Exception("Could not find attendance percent on page")

# === Main Program ===
def main():
    if not all([COLLEGE_USER, COLLEGE_PASS, TWILIO_SID, TWILIO_TOKEN, MY_PHONE]):
        print("❌ Missing environment variables.")
        return

    attendance = get_attendance()
    last = read_last()

    if attendance == last:
        print("✅ Attendance unchanged, no message sent.")
        return

    message = f"🎓 Your current attendance: {attendance}"
    send_whatsapp_message(message)
    write_last(attendance)

if __name__ == "__main__":
    main()
