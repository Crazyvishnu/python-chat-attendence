import os
import time
from dotenv import load_dotenv
from twilio.rest import Client
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

load_dotenv()

# --- Twilio setup ---
account_sid = os.getenv("TWILIO_SID")
auth_token = os.getenv("TWILIO_TOKEN")
from_whatsapp = os.getenv("TWILIO_PHONE")
to_whatsapp = os.getenv("MY_PHONE")

client = Client(account_sid, auth_token)

# --- Attendance scraper ---
def get_attendance():
    options = Options()
    options.add_argument("--headless")  # run in background
    driver = webdriver.Chrome(options=options)

    try:
        driver.get("https://winnou.net/MGIT/")

        # Login
        driver.find_element(By.NAME, "username").send_keys(os.getenv("COLLEGE_USER"))
        driver.find_element(By.NAME, "passwd").send_keys(os.getenv("COLLEGE_PASS"))
        driver.find_element(By.NAME, "SubmitL").click()
        time.sleep(3)

        # Go to student info
        link = driver.find_element(By.LINK_TEXT, "Student Info")
        link.click()
        time.sleep(3)

        # Extract attendance
        html = driver.page_source
        percent = None

        import re
        match = re.search(r'(\d{2,3}\.\d{1,2})\s*%', html)
        if match:
            percent = match.group(1)
        else:
            percent = "Not Found"

        driver.quit()
        return percent

    except Exception as e:
        driver.quit()
        print("Error:", e)
        return "Error"

# --- Send WhatsApp ---
def send_message(msg):
    message = client.messages.create(
        from_=from_whatsapp,
        to=to_whatsapp,
        body=msg
    )
    print("✅ WhatsApp Message Sent:", message.sid)

# --- Main job ---
def run_attendance_bot():
    percent = get_attendance()
    msg = f"📊 Attendance Update: {percent}%\nHave a nice day, Sahitya!"
    send_message(msg)

if __name__ == "__main__":
    run_attendance_bot()
