import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime
from twilio.rest import Client
import re

# Environment variables from GitHub Secrets
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_FROM = os.environ.get('TWILIO_WHATSAPP_FROM')
YOUR_WHATSAPP_NUMBER = os.environ.get('YOUR_WHATSAPP_NUMBER')
MGIT_USERNAME = os.environ.get('MGIT_USERNAME')
MGIT_PASSWORD = os.environ.get('MGIT_PASSWORD')

BASE_URL = "https://mgit.winnou.net"

def send_whatsapp_message(message):
    """Send message via Twilio WhatsApp"""
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        msg = client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            body=message,
            to=YOUR_WHATSAPP_NUMBER
        )
        
        print(f"✅ WhatsApp sent! SID: {msg.sid}")
        return True
    except Exception as e:
        print(f"❌ WhatsApp failed: {e}")
        return False

def get_attendance():
    """Fetch attendance from MGIT portal"""
    try:
        session = requests.Session()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        
        print("📡 Accessing MGIT portal...")
        
        # Step 1: Get login page
        response = session.get(BASE_URL, headers=headers, timeout=20)
        
        if response.status_code != 200:
            return "❌ Cannot reach MGIT portal"
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Step 2: Find login form and hidden fields
        form = soup.find('form')
        hidden_fields = {}
        
        if form:
            for inp in form.find_all('input', type='hidden'):
                name = inp.get('name')
                value = inp.get('value')
                if name:
                    hidden_fields[name] = value
        
        print("🔐 Logging in...")
        
        # Step 3: Try multiple common field name combinations
        login_data = {
            # Common variations for username
            'username': MGIT_USERNAME,
            'user': MGIT_USERNAME,
            'userid': MGIT_USERNAME,
            'user_id': MGIT_USERNAME,
            'userName': MGIT_USERNAME,
            'rollno': MGIT_USERNAME,
            'roll_no': MGIT_USERNAME,
            'rollNo': MGIT_USERNAME,
            'studentid': MGIT_USERNAME,
            'student_id': MGIT_USERNAME,
            'login': MGIT_USERNAME,
            'uname': MGIT_USERNAME,
            
            # Common variations for password
            'password': MGIT_PASSWORD,
            'pass': MGIT_PASSWORD,
            'passwd': MGIT_PASSWORD,
            'pwd': MGIT_PASSWORD,
            'user_pass': MGIT_PASSWORD,
            'userpass': MGIT_PASSWORD,
            
            # Hidden fields
            **hidden_fields
        }
        
        # Find form action
        if form:
            action = form.get('action', '/login')
        else:
            action = '/login'
        
        if not action.startswith('http'):
            login_url = BASE_URL + action
        else:
            login_url = action
        
        # Submit login
        login_resp = session.post(
            login_url,
            data=login_data,
            headers=headers,
            timeout=20,
            allow_redirects=True
        )
        
        print(f"Login status: {login_resp.status_code}")
        
        # Step 4: Find attendance page
        soup = BeautifulSoup(login_resp.text, 'html.parser')
        
        # Look for attendance link
        attendance_url = None
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            text = link.get_text().lower()
            if 'attendance' in href or 'attendance' in text:
                attendance_url = link.get('href')
                break
        
        if not attendance_url:
            # Try common URLs
            attendance_url = '/student/attendance'
        
        if not attendance_url.startswith('http'):
            attendance_url = BASE_URL + attendance_url
        
        print(f"📊 Fetching: {attendance_url}")
        
        # Get attendance page
        att_resp = session.get(attendance_url, headers=headers, timeout=20)
        
        # Step 5: Parse attendance data
        soup = BeautifulSoup(att_resp.text, 'html.parser')
        
        # Method 1: Find spans with percentages (like your portal)
        spans = soup.find_all('span')
        attendance_data = []
        
        for span in spans:
            text = span.get_text(strip=True)
            # Look for pattern like (74.6) or 74.6% or 74.6
            match = re.search(r'\((\d+\.?\d*)\)|\b(\d+\.?\d*)\s*%', text)
            if match:
                percentage = match.group(1) or match.group(2)
                
                # Try to find subject name nearby
                parent = span.find_parent()
                if parent:
                    onclick = span.get('onclick', '')
                    # Extract subject from onclick or nearby text
                    subject = "Subject"
                    
                    # Look for subject in onclick parameter
                    name_match = re.search(r"'([A-Z\s]+[A-Z])'", onclick)
                    if name_match:
                        subject = name_match.group(1).strip()
                    
                    attendance_data.append({
                        'subject': subject,
                        'percentage': float(percentage)
                    })
        
        # Method 2: Find tables with percentages
        if not attendance_data:
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:  # Skip header
                    cols = row.find_all(['td', 'th'])
                    if len(cols) >= 2:
                        subject = cols[0].get_text(strip=True)
                        last_col = cols[-1].get_text(strip=True)
                        
                        # Extract percentage
                        pct_match = re.search(r'(\d+\.?\d*)\s*%?', last_col)
                        if pct_match and subject:
                            attendance_data.append({
                                'subject': subject,
                                'percentage': float(pct_match.group(1))
                            })
        
        # Method 3: Regex on entire page
        if not attendance_data:
            text = soup.get_text()
            # Find patterns like "Subject Name: 75%" or "Subject Name - 75%"
            matches = re.findall(r'([A-Za-z\s&]+?)[\s:-]+(\d+\.?\d*)\s*%', text)
            for subject, pct in matches[:15]:
                attendance_data.append({
                    'subject': subject.strip(),
                    'percentage': float(pct)
                })
        
        # Format message
        if attendance_data:
            message = "📚 *MGIT Attendance Report*\n"
            message += f"⏰ {datetime.now().strftime('%d-%b-%Y %I:%M %p')} IST\n"
            message += f"👤 {MGIT_USERNAME}\n"
            message += "━━━━━━━━━━━━━━━━━━\n\n"
            
            for item in attendance_data[:20]:  # Limit to 20
                pct = item['percentage']
                subject = item['subject'][:30]  # Truncate long names
                
                # Emoji based on percentage
                if pct >= 75:
                    emoji = "✅"
                elif pct >= 65:
                    emoji = "⚠️"
                else:
                    emoji = "🔴"
                
                message += f"{emoji} *{subject}*: {pct}%\n"
            
            message += "\n━━━━━━━━━━━━━━━━━━\n"
            message += "✅ ≥75% | ⚠️ 65-74% | 🔴 <65%"
            
            return message
        else:
            return "⚠️ Could not extract attendance. Please check portal manually."
    
    except Exception as e:
        return f"❌ Error: {str(e)[:200]}"

def main():
    print("\n" + "="*60)
    print("🎓 MGIT ATTENDANCE BOT")
    print("="*60)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST")
    print(f"👤 User: {MGIT_USERNAME}")
    print("="*60 + "\n")
    
    print("STEP 1: Fetching attendance...")
    attendance = get_attendance()
    
    print("\nSTEP 2: Sending WhatsApp...")
    success = send_whatsapp_message(attendance)
    
    if success:
        print("\n✅ SUCCESS! Check your WhatsApp")
    else:
        print("\n⚠️ WhatsApp send failed")
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()
