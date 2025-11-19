import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os

MGIT_URL = "https://mgit.winnou.net/"
LOGIN_PATH = "/index.php"
USERNAME_FIELD = "txtusername"
PASSWORD_FIELD = "txtpassword"

def login_and_get_attendance():

    username = os.getenv("MGIT_USERNAME")
    password = os.getenv("MGIT_PASSWORD")

    if not username or not password:
        return "Username/password not set"

    login_url = urljoin(MGIT_URL, LOGIN_PATH)

    s = requests.Session()

    # Load login page
    r = s.get(login_url, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    # collect hidden inputs
    form = {}
    for inp in soup.select("input[type=hidden]"):
        if inp.get("name"):
            form[inp.get("name")] = inp.get("value", "")

    # add credentials
    form[USERNAME_FIELD] = username
    form[PASSWORD_FIELD] = password

    # form action
    form_tag = soup.find("form")
    post_url = urljoin(login_url, form_tag.get("action"))

    # login request
    resp = s.post(post_url, data=form)
    resp.raise_for_status()

    # go to attendance page
    att_url = urljoin(MGIT_URL, "/Student/Attendance.aspx")
    att_page = s.get(att_url)
    att_page.raise_for_status()

    soup2 = BeautifulSoup(att_page.text, "lxml")
    table = soup2.find("table")

    if not table:
        return "Attendance not found."

    rows = []
    for tr in table.find_all("tr"):
        cols = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if cols:
            rows.append(" | ".join(cols))

    return "\n".join(rows)
