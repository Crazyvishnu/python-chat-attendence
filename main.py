import os
import re
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from twilio.rest import Client

# -------------------------------
# Scrape Attendance Function
# -------------------------------
def get_attendance():
    """Scrape attendance from MGIT Winnou"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    driver.set_window_size(1920, 1080)

    try:
        print("🌐 Opening MGIT Winnou site...")
        driver.get("https://mgit.winnou.net/")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.NAME, "username")))

        print("🔐 Logging in...")
        driver.find_element(By.NAME, "username").send_keys(os.getenv("COLLEGE_USER"))
        driver.find_element(By.NAME, "passwd").send_keys(os.getenv("COLLEGE_PASS"))
        driver.find_element(By.NAME, "SubmitL").click()
        time.sleep(3)

        print("📄 Navigating to Student Info...")
        driver.find_element(By.LINK_TEXT, "Student Info").click()
        time.sleep(3)

        html = driver.page_source
        match = re.search(r'(\d{2,3}\.\d{1,2})\s*%', html)
        percent = match.group(1) if match else "Not Found"
        print(f"🎯 Attendance Extracted: {percent}%")
        return percent

    except Exception as e:
        print("❌ Error scraping attendance:", e)
        return "Error"
    finally:
        driver.quit()

# -------------------------------
# Send WhatsApp Message via Twilio
# -------------------------------
def send_whatsapp_message(body):
    print("📩 Sending WhatsApp message...")
    client = Client(os.getenv("TWILIO_SID"), os.getenv("TWILIO_TOKEN"))
    message = client.messages.create(
        from_=os.getenv("TWILIO_PHONE_NUMBER"),
        to=os.getenv("MY_PHONE_NUMBER"),
        body=body
    )
    print("✅ WhatsApp Message Sent! SID:", message.sid)

# -------------------------------
# Main Logic
# -------------------------------
def main():
    now = datetime.now()
    current_hour = now.hour
    attendance = get_attendance()

    if attendance == "Error":
        body = "⚠️ Attendance scraping failed. Check MGIT portal manually."
    elif 5 <= current_hour < 12:
        body = f"☀️ Good morning Sahitya!\nYour current attendance is: {attendance}%"
    else:
        body = f"🌙 Evening update, Sahitya!\nYour current attendance is: {attendance}%"

    send_whatsapp_message(body)

if __name__ == "__main__":
    main()
