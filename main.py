import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from twilio.rest import Client

# Load credentials from GitHub Secrets (environment variables)
COLLEGE_USER = os.getenv("COLLEGE_USER")
COLLEGE_PASS = os.getenv("COLLEGE_PASS")
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE_NUMBER")
MY_PHONE = os.getenv("MY_PHONE_NUMBER")

def get_attendance():
    """Login to MGIT Winnou and scrape attendance percentage."""
    print("🌐 Opening MGIT Winnou site...")

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    browser = webdriver.Chrome(options=options)
    browser.set_page_load_timeout(90)

    try:
        browser.get("https://mgit.winnou.net/")

        print("🔐 Logging in...")
        user_field = browser.find_element(By.NAME, "username")
        pass_field = browser.find_element(By.NAME, "passwd")
        user_field.send_keys(COLLEGE_USER)
        pass_field.send_keys(COLLEGE_PASS)
        browser.find_element(By.NAME, "SubmitL").click()
        time.sleep(3)

        print("📄 Navigating to Student Info...")
        try:
            student_info_link = browser.find_element(By.XPATH, "//a[contains(text(),'Student Info')]")
            student_info_link.click()
            time.sleep(3)
        except Exception:
            pass  # already on page

        # Look for Attendance text
        cells = browser.find_elements(By.TAG_NAME, "td")
        attendance = "Not Found"
        for i, cell in enumerate(cells):
            if "Attendance" in cell.text:
                if i + 1 < len(cells):
                    attendance = cells[i + 1].text.strip()
                break

        print("🎯 Attendance Extracted:", attendance)
        return attendance + "%" if "%" not in attendance else attendance

    except Exception as e:
        print("❌ Error scraping attendance:", e)
        return "Error"
    finally:
        browser.quit()

def send_whatsapp_message(body):
    """Send a WhatsApp message using Twilio."""
    print("📩 Sending WhatsApp message...")
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    message = client.messages.create(
        from_=TWILIO_PHONE,
        to=MY_PHONE,
        body=body
    )
    print("✅ Message sent! SID:", message.sid)

def main():
    attendance = get_attendance()
    if "Error" not in attendance:
        body = f"🎓 Your current attendance: {attendance}"
        send_whatsapp_message(body)
    else:
        send_whatsapp_message("⚠️ Failed to fetch attendance today.")

if __name__ == "__main__":
    main()
