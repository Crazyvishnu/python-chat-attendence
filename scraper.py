import os
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://mgit.winnou.net"
LOGIN_URL = f"{BASE_URL}/index.php?option=com_user&view=login"
ATTENDANCE_URL = "https://mgit.winnou.net/index.php?option=com_base_studentinfo&task=details&schoolid=1&Itemid=324"

def login_and_get_attendance():
    username = os.getenv("MGIT_USERNAME")
    password = os.getenv("MGIT_PASSWORD")

    if not username or not password:
        return "Missing username or password secret!"

    session = requests.Session()

    # STEP 1 – Open login page to get hidden form fields
    login_page = session.get(LOGIN_URL)
    login_page.raise_for_status()

    soup = BeautifulSoup(login_page.text, "lxml")

    form = soup.find("form", {"id": "login-form"})
    if form is None:
        return "Unable to find login form!"

    data = {}
    for field in form.find_all("input"):
        name = field.get("name")
        value = field.get("value", "")
        if name:
            data[name] = value

    # Insert credentials into form
    data["username"] = username
    data["passwd"] = password

    # STEP 2 – Submit login form
    post_url = form.get("action")
    if not post_url.startswith("http"):
        post_url = BASE_URL + "/" + post_url.lstrip("/")

    login_response = session.post(post_url, data=data)
    login_response.raise_for_status()

    # STEP 3 – Access attendance page
    att_page = session.get(ATTENDANCE_URL)
    att_page.raise_for_status()

    soup = BeautifulSoup(att_page.text, "lxml")

    # Extract attendance table
    table = soup.find("table")
    if not table:
        return "Attendance table not found!"

    rows = table.find_all("tr")

    result = []
    for tr in rows:
        cols = [td.text.strip() for td in tr.find_all(["td", "th"])]
        if cols:
            result.append(" | ".join(cols))

    return "\n".join(result)
