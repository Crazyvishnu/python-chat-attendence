import schedule
import time
import subprocess

def run_bot():
    subprocess.run(["python", "main.py"])

# Schedule times (IST)
schedule.every().day.at("08:30").do(run_bot)
schedule.every().day.at("16:30").do(run_bot)

print("✅ Attendance scheduler started...")

while True:
    schedule.run_pending()
    time.sleep(60)
