import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime
from twilio.rest import Client

# Get credentials from environment variables (GitHub Secrets)
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_FROM = os.environ.get('TWILIO_WHATSAPP_FROM')  # e.g., whatsapp:+14155238886
YOUR_WHATSAPP_NUMBER = os.environ.get('YOUR_WHATSAPP_NUMBER')  # e.g., whatsapp:+919876543210

MGIT_USERNAME = os.environ.get('MGIT_USERNAME')
MGIT_PASSWORD = os.environ.get('MGIT_PASSWORD')

BASE_URL = "https://mgit.winnou.net"

def send_whatsapp_message(message):
    """Send message via Twilio WhatsApp"""
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        message_obj = client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            body=message,
            to=YOUR_WHATSAPP_NUMBER
        )
        
        print(f"✅ WhatsApp message sent! SID: {message_obj.sid}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send WhatsApp: {e}")
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
        login_page = session.get(BASE_URL, headers=headers, timeout=15)
        
        if login_page.status_code != 200:
            return "❌ Cannot reach MGIT portal. Please check later."
        
        # Parse login page
        soup = BeautifulSoup(login_page.text, 'html.parser')
        login_form = soup.find('form')
        
        # Collect hidden fields (CSRF tokens, etc.)
        hidden_inputs = {}
        if login_form:
            for hidden in login_form.find_all('input', type='hidden'):
                name = hidden.get('name')
                value = hidden.get('value')
                if name:
                    hidden_inputs[name] = value
        
        print("🔐 Attempting login...")
        
        # Try multiple common field name variations
        login_data = {
            'username': MGIT_USERNAME,
            'password': MGIT_PASSWORD,
            'user_id': MGIT_USERNAME,
            'user_pass': MGIT_PASSWORD,
            'userid': MGIT_USERNAME,
            'passwd': MGIT_PASSWORD,
            'rollno': MGIT_USERNAME,
            'roll_no': MGIT_USERNAME,
            'pwd': MGIT_PASSWORD,
            **hidden_inputs
        }
        
        login_url = f"{BASE_URL}/login"
        login_response = session.post(login_url, data=login_data, headers=headers, timeout=15, allow_redirects=True)
        
        print(f"Login response URL: {login_response.url}")
        
        # Find attendance page
        soup = BeautifulSoup(login_response.text, 'html.parser')
        
        # Look for attendance link
        attendance_link = soup.find('a', href=lambda x: x and 'attendance' in x.lower())
        
        if attendance_link:
            attendance_url = attendance_link.get('href')
            if not attendance_url.startswith('http'):
                attendance_url = BASE_URL + attendance_url
        else:
            # Try common attendance URLs
            attendance_url = f"{BASE_URL}/student/attendance"
        
        print(f"📊 Fetching attendance from: {attendance_url}")
        attendance_response = session.get(attendance_url, headers=headers, timeout=15)
        
        # Parse attendance data
        soup = BeautifulSoup(attendance_response.text, 'html.parser')
        
        # Try to find attendance table
        attendance_table = soup.find('table', class_=lambda x: x and 'attendance' in x.lower() if x else False)
        if not attendance_table:
            attendance_table = soup.find('table')
        
        if attendance_table:
            message = "📚 *MGIT Attendance Report*\n"
            message += f"⏰ {datetime.now().strftime('%d-%m-%Y %I:%M %p')} IST\n"
            message += "━━━━━━━━━━━━━━━━━━\n\n"
            
            rows = attendance_table.find_all('tr')
            
            for row in rows[1:]:  # Skip header row
                cols = row.find_all(['td', 'th'])
                if len(cols) >= 2:
                    subject = cols[0].get_text(strip=True)
                    
                    # Find percentage (usually last column)
                    percentage = cols[-1].get_text(strip=True)
                    
                    # Add emoji based on percentage
                    if '%' in percentage:
                        try:
                            pct = float(percentage.replace('%', '').strip())
                            if pct >= 75:
                                emoji = "✅"
                            elif pct >= 65:
                                emoji = "⚠️"
                            else:
                                emoji = "🔴"
                        except:
                            emoji = "📌"
                    else:
                        emoji = "📌"
                    
                    message += f"{emoji} *{subject}*: {percentage}\n"
            
            # Add summary
            message += f"\n━━━━━━━━━━━━━━━━━━\n"
            message += "✅ >= 75% | ⚠️ 65-74% | 🔴 < 65%"
            
            return message
        else:
            # Fallback: extract text
            text_content = soup.get_text(separator='\n', strip=True)
            
            # Look for percentage patterns
            import re
            percentages = re.findall(r'(\w+[\w\s]*?)[\s:]+(\d+\.?\d*%)', text_content)
            
            if percentages:
                message = "📚 *MGIT Attendance Report*\n"
                message += f"⏰ {datetime.now().strftime('%d-%m-%Y %I:%M %p')} IST\n"
                message += "━━━━━━━━━━━━━━━━━━\n\n"
                
                for subject, pct in percentages:
                    try:
                        pct_val = float(pct.replace('%', ''))
                        emoji = "✅" if pct_val >= 75 else "⚠️" if pct_val >= 65 else "🔴"
                    except:
                        emoji = "📌"
                    
                    message += f"{emoji} *{subject.strip()}*: {pct}\n"
                
                return message
            else:
                return f"📊 *Attendance Data*\n\n{text_content[:700]}"
    
    except requests.exceptions.Timeout:
        return "⏱️ Request timed out. MGIT portal might be slow. Will retry next scheduled time."
    except requests.exceptions.ConnectionError:
        return "🌐 Connection error. Please check internet connectivity."
    except Exception as e:
        return f"❌ Error occurred: {str(e)}\n\nPlease verify your credentials and try again."

def main():
    """Main execution"""
    print("\n" + "="*60)
    print(f"🔄 MGIT Attendance Check Started")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST")
    print("="*60 + "\n")
    
    attendance_data = get_attendance()
    
    print("\n" + "-"*60)
    print("📤 Sending to WhatsApp...")
    print("-"*60 + "\n")
    
    success = send_whatsapp_message(attendance_data)
    
    if success:
        print("\n✅ Job completed successfully!")
    else:
        print("\n⚠️ Message sending failed. Check Twilio credentials.")
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()
