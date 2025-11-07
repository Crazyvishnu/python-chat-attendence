import os
import time
import re
from twilio.rest import Client
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

def get_attendance():
    """Scrape attendance from college site."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)

    try:
        driver.get("https://winnou.net/MGIT/")
        time.sleep(2)

        driver.find_element(By.NAME, "username").send_keys(os.getenv("COLLEGE_USER"))
        driver.find_element(By.NAME, "passwd").send_keys(os.getenv("COLLEGE_PASS"))
        driver.find_element(By.NAME, "SubmitL").click()
        time.sleep(3)

        # Navigate to attendance
        driver.find_element(By.LINK_TEXT, "Student Info").click()
        time.sleep(2)

        html = driver.page_source
        match = re.search(r'(\d{2,3}\.\d{1,2})\s*%', html)
        percent = match.group(1) if match else "Not Found"

        return percent

    except Exception as e:
        print("Error scraping attendance:", e)
        return "Error"
    finally:
        driver.quit()

def send_whatsapp_message(body):
    """Send WhatsApp message using Twilio."""
    sid = os.getenv("TWILIO_SID")
    token = os.getenv("TWILIO_TOKEN")
    from_whatsapp = os.getenv("TWILIO_PHONE_NUMBER", "whatsapp:+14155238886")
    to_whatsapp = os.getenv("MY_PHONE_NUMBER")

    client = Client(sid, token)
    message = client.messages.create(from_=from_whatsapp, to=to_whatsapp, body=body)
    print("✅ Message sent:", message.sid)

def main():
    attendance = get_attendance()
    if attendance == "Error":
        body = "❌ Failed to fetch attendance. Please check manually."
    else:
        body = f"🎓 Your current attendance: {attendance}%"

    send_whatsapp_message(body)

if __name__ == "__main__":
    main()
