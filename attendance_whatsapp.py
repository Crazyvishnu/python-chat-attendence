import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime
from twilio.rest import Client

# Get credentials from environment variables
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
        # Validate credentials
        if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, YOUR_WHATSAPP_NUMBER]):
            print("❌ Missing Twilio credentials!")
            print(f"   SID: {'✓' if TWILIO_ACCOUNT_SID else '✗'}")
            print(f"   Token: {'✓' if TWILIO_AUTH_TOKEN else '✗'}")
            print(f"   From: {TWILIO_WHATSAPP_FROM if TWILIO_WHATSAPP_FROM else '✗'}")
            print(f"   To: {YOUR_WHATSAPP_NUMBER if YOUR_WHATSAPP_NUMBER else '✗'}")
            return False
        
        # Ensure proper WhatsApp formatting
        from_number = TWILIO_WHATSAPP_FROM if TWILIO_WHATSAPP_FROM.startswith('whatsapp:') else f'whatsapp:{TWILIO_WHATSAPP_FROM}'
        to_number = YOUR_WHATSAPP_NUMBER if YOUR_WHATSAPP_NUMBER.startswith('whatsapp:') else f'whatsapp:{YOUR_WHATSAPP_NUMBER}'
        
        print(f"📱 Sending from: {from_number}")
        print(f"📱 Sending to: {to_number}")
        
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        message_obj = client.messages.create(
            from_=from_number,
            body=message,
            to=to_number
        )
        
        print(f"✅ WhatsApp message sent! SID: {message_obj.sid}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send WhatsApp: {e}")
        print("\n💡 Troubleshooting tips:")
        print("   1. Check if your Twilio number matches your account")
        print("   2. For Sandbox: Send 'join <your-code>' to the Twilio number first")
        print("   3. Verify numbers include country code (e.g., +91 for India)")
        print("   4. Check https://console.twilio.com/us1/develop/sms/settings/whatsapp-sender")
        return False

def get_attendance():
    """Fetch attendance from MGIT portal"""
    try:
        session = requests.Session()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        
        print("📡 Accessing MGIT portal...")
        login_page = session.get(BASE_URL, headers=headers, timeout=15)
        
        if login_page.status_code != 200:
            return "❌ Cannot reach MGIT portal. Please check later."
        
        # Save login page for debugging
        print(f"🔍 Login page size: {len(login_page.text)} bytes")
        
        # Parse login page
        soup = BeautifulSoup(login_page.text, 'html.parser')
        login_form = soup.find('form')
        
        if not login_form:
            print("⚠️ No login form found on page!")
            # Try to find what fields exist
            all_inputs = soup.find_all('input')
            print(f"Found {len(all_inputs)} input fields:")
            for inp in all_inputs[:10]:
                print(f"   - {inp.get('name', 'no-name')}: {inp.get('type', 'text')}")
            return "❌ Cannot find login form. Website structure may have changed."
        
        # Get form action URL
        form_action = login_form.get('action', '/login')
        if not form_action.startswith('http'):
            login_url = BASE_URL + form_action if form_action.startswith('/') else BASE_URL + '/' + form_action
        else:
            login_url = form_action
        
        print(f"🔐 Login URL: {login_url}")
        
        # Collect all form fields
        login_data = {}
        
        # Add hidden fields
        for hidden in login_form.find_all('input', type='hidden'):
            name = hidden.get('name')
            value = hidden.get('value', '')
            if name:
                login_data[name] = value
                print(f"   Hidden field: {name}")
        
        # Find username/password field names
        username_field = None
        password_field = None
        
        for inp in login_form.find_all('input'):
            inp_type = inp.get('type', '').lower()
            inp_name = inp.get('name', '').lower()
            
            if inp_type == 'text' or 'user' in inp_name or 'roll' in inp_name or 'id' in inp_name:
                username_field = inp.get('name')
                print(f"   Username field: {username_field}")
            elif inp_type == 'password' or 'pass' in inp_name or 'pwd' in inp_name:
                password_field = inp.get('name')
                print(f"   Password field: {password_field}")
        
        if not username_field or not password_field:
            print("⚠️ Could not identify login fields!")
            return "❌ Cannot identify login form fields. Please check website manually."
        
        # Set credentials
        login_data[username_field] = MGIT_USERNAME
        login_data[password_field] = MGIT_PASSWORD
        
        print(f"🔐 Attempting login with {username_field}/{password_field}...")
        
        login_response = session.post(
            login_url, 
            data=login_data, 
            headers=headers, 
            timeout=15, 
            allow_redirects=True
        )
        
        print(f"📍 After login URL: {login_response.url}")
        print(f"📄 Response size: {len(login_response.text)} bytes")
        
        # Check if login was successful
        if 'login' in login_response.url.lower():
            print("❌ Still on login page - credentials may be wrong!")
            soup = BeautifulSoup(login_response.text, 'html.parser')
            error_msg = soup.find(['div', 'span'], class_=lambda x: x and 'error' in x.lower() if x else False)
            if error_msg:
                print(f"⚠️ Error message: {error_msg.get_text(strip=True)}")
            return "❌ Login failed. Please verify your MGIT username and password."
        
        # After successful login, we're already on Student Info page
        # This page has the attendance data
        soup = BeautifulSoup(login_response.text, 'html.parser')
        
        # First, try to get overall attendance from Student Info page
        message = "📚 *MGIT Attendance Report*\n"
        message += f"⏰ {datetime.now().strftime('%d-%m-%Y %I:%M %p')} IST\n"
        message += "━━━━━━━━━━━━━━━━━━\n\n"
        
        # Look for attendance percentage in Present Term section
        present_term = soup.find(['div', 'td'], string=lambda x: x and 'Present Term' in str(x))
        if present_term:
            # Find the attendance row
            attendance_row = None
            for row in soup.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                for cell in cells:
                    if 'Attendance' in cell.get_text():
                        attendance_row = row
                        break
                if attendance_row:
                    break
            
            if attendance_row:
                # Extract percentage - look for pattern like (75.27)
                import re
                row_text = attendance_row.get_text()
                pct_match = re.search(r'\((\d+\.?\d*)\)', row_text)
                if pct_match:
                    overall_pct = float(pct_match.group(1))
                    emoji = "✅" if overall_pct >= 75 else "⚠️" if overall_pct >= 65 else "🔴"
                    message += f"{emoji} *Overall Attendance*: {overall_pct}%\n\n"
        
        # Now try to get detailed subject-wise attendance
        # Look for attendance link to click
        attendance_link = None
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True).lower()
            if 'attendance' in text.lower() or 'attendance' in href.lower():
                attendance_link = link
                break
        
        if attendance_link:
            attendance_url = attendance_link.get('href')
            if not attendance_url.startswith('http'):
                attendance_url = BASE_URL + attendance_url if attendance_url.startswith('/') else BASE_URL + '/' + attendance_url
            
            print(f"📊 Fetching detailed attendance from: {attendance_url}")
            attendance_response = session.get(attendance_url, headers=headers, timeout=15)
        else:
            # If no link found, use current page
            print("📊 Using Student Info page for attendance")
            attendance_response = login_response
        
        # Parse attendance data
        soup = BeautifulSoup(attendance_response.text, 'html.parser')
        
        # If we haven't added overall attendance yet, try to get it now
        if 'Overall Attendance' not in message:
            import re
            # Look for percentage pattern in the page
            page_text = soup.get_text()
            pct_match = re.search(r'Attendance.*?\((\d+\.?\d*)\)', page_text)
            if pct_match:
                overall_pct = float(pct_match.group(1))
                emoji = "✅" if overall_pct >= 75 else "⚠️" if overall_pct >= 65 else "🔴"
                message += f"{emoji} *Overall Attendance*: {overall_pct}%\n\n"
        
        # Try to find subject-wise attendance table
        attendance_table = soup.find('table')
        found_subjects = False
        
        if attendance_table:
            rows = attendance_table.find_all('tr')
            
            # Look for subject attendance rows
            for row in rows[1:]:  # Skip potential header
                cols = row.find_all(['td', 'th'])
                if len(cols) >= 3:  # Subject, classes, percentage
                    subject = cols[0].get_text(strip=True)
                    
                    # Skip empty or header rows
                    if not subject or subject.lower() in ['subject', 'course', 'name']:
                        continue
                    
                    # Look for percentage in any column
                    percentage = None
                    for col in cols[1:]:
                        col_text = col.get_text(strip=True)
                        if '%' in col_text:
                            percentage = col_text
                            break
                        # Also check for decimal numbers that might be percentages
                        import re
                        if re.match(r'^\d+\.?\d*
        
        # Fallback: Look for percentages in text
        import re
        text_content = soup.get_text(separator='\n', strip=True)
        percentages = re.findall(r'(\w+[\w\s]{2,30}?)[\s:]+(\d+\.?\d*%)', text_content)
        
        if percentages:
            message = "📚 *MGIT Attendance Report*\n"
            message += f"⏰ {datetime.now().strftime('%d-%m-%Y %I:%M %p')} IST\n"
            message += "━━━━━━━━━━━━━━━━━━\n\n"
            
            for subject, pct in percentages[:15]:  # Limit to 15 subjects
                try:
                    pct_val = float(pct.replace('%', ''))
                    emoji = "✅" if pct_val >= 75 else "⚠️" if pct_val >= 65 else "🔴"
                except:
                    emoji = "📌"
                
                message += f"{emoji} *{subject.strip()}*: {pct}\n"
            
            return message
        else:
            return "⚠️ Logged in successfully but couldn't parse attendance data. Website structure may have changed."
    
    except requests.exceptions.Timeout:
        return "⏱️ Request timed out. MGIT portal might be slow. Will retry next scheduled time."
    except requests.exceptions.ConnectionError:
        return "🌐 Connection error. Please check internet connectivity."
    except Exception as e:
        print(f"💥 Exception details: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"❌ Error occurred: {str(e)}"

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
    print(f"Message preview:\n{attendance_data[:200]}...\n")
    
    success = send_whatsapp_message(attendance_data)
    
    if success:
        print("\n✅ Job completed successfully!")
    else:
        print("\n⚠️ Message sending failed. Check Twilio credentials.")
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()
, col_text):
                            try:
                                pct_val = float(col_text)
                                if 0 <= pct_val <= 100:
                                    percentage = f"{pct_val}%"
                                    break
                            except:
                                pass
                    
                    if percentage:
                        found_subjects = True
                        # Add emoji based on percentage
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
                        
                        message += f"{emoji} *{subject}*: {percentage}\n"
        
        if found_subjects:
            message += f"\n━━━━━━━━━━━━━━━━━━\n"
            message += "✅ >= 75% | ⚠️ 65-74% | 🔴 < 65%"
            return message
        elif 'Overall Attendance' in message:
            # If we only have overall attendance, that's still useful
            message += "━━━━━━━━━━━━━━━━━━\n"
            message += "💡 Subject-wise details not available"
            return message
        
        # Fallback: Look for percentages in text
        import re
        text_content = soup.get_text(separator='\n', strip=True)
        percentages = re.findall(r'(\w+[\w\s]{2,30}?)[\s:]+(\d+\.?\d*%)', text_content)
        
        if percentages:
            message = "📚 *MGIT Attendance Report*\n"
            message += f"⏰ {datetime.now().strftime('%d-%m-%Y %I:%M %p')} IST\n"
            message += "━━━━━━━━━━━━━━━━━━\n\n"
            
            for subject, pct in percentages[:15]:  # Limit to 15 subjects
                try:
                    pct_val = float(pct.replace('%', ''))
                    emoji = "✅" if pct_val >= 75 else "⚠️" if pct_val >= 65 else "🔴"
                except:
                    emoji = "📌"
                
                message += f"{emoji} *{subject.strip()}*: {pct}\n"
            
            return message
        else:
            return "⚠️ Logged in successfully but couldn't parse attendance data. Website structure may have changed."
    
    except requests.exceptions.Timeout:
        return "⏱️ Request timed out. MGIT portal might be slow. Will retry next scheduled time."
    except requests.exceptions.ConnectionError:
        return "🌐 Connection error. Please check internet connectivity."
    except Exception as e:
        print(f"💥 Exception details: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"❌ Error occurred: {str(e)}"

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
    print(f"Message preview:\n{attendance_data[:200]}...\n")
    
    success = send_whatsapp_message(attendance_data)
    
    if success:
        print("\n✅ Job completed successfully!")
    else:
        print("\n⚠️ Message sending failed. Check Twilio credentials.")
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()
