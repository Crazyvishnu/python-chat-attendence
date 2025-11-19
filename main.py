from scraper import login_and_get_attendance
from whatsapp import send_whatsapp

def handler():
    data = login_and_get_attendance()
    message = f"Attendance Update:\n\n{data}"
    return send_whatsapp(message)

if __name__ == "__main__":
    print(handler())
