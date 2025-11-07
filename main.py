import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from twilio.rest import Client

def get_attendance():
    print("🌐 Opening MGIT Winnou site...")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=chrome_options)
    driver.get("https://mgitwinnou.in/")

    print("🔐 Logging in...")
    username = os.getenv("COLLEGE_USER")
    password = os.getenv("COLLEGE_PASS")

    driver.find_element(By.ID, "txtusername").send_keys(username)
    driver.find_element(By.ID, "txtpassword").send_keys(password)
    driver.find_element(By.ID, "btnSubmit").click()
    time.sleep(3)

    print("📄 Navigating to Student Info...")
    driver.get("https://mgitwinnou.in/StudentInfo.aspx")
    time.sleep(3)

    attendance = "Not Found"
    try:
        spans = driver.find_elements(By.TAG_NAME, "span")
        for span in spans:
            text = span.text.strip()
            if text.startswith("(") and text.endswith(")") and "." in text:
                attendance = text.strip("()")
                break
    except Exception:
        pass

    print(f"🎯 Attendance Extracted: {attendance}%")
    driver.quit()
    return attendance


def send_whatsapp_message(body):
    print("📩 Sending WhatsApp message...")
    account_sid = os.getenv("TWILIO_SID")
    auth_token = os.getenv("TWILIO_TOKEN")
    from_whatsapp = f"whatsapp:{os.getenv('TWILIO_PHONE_NUMBER')}"
    to_whatsapp = f"whatsapp:{os.getenv('MY_PHONE_NUMBER')}"

    client = Client(account_sid, auth_token)
    message = client.messages.create(
        from_=from_whatsapp,
        to=to_whatsapp,
        body=body
    )
    print(f"✅ Message Sent! SID: {message.sid}")


def main():
    attendance = get_attendance()
    body = f"📊 MGIT Attendance Update: {attendance}%"
    send_whatsapp_message(body)


if __name__ == "__main__":
    main()
