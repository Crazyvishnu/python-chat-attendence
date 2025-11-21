"""
MGIT Attendance Tracker with WhatsApp Notifications
Tracks attendance from mgit.winnou.net and sends daily updates via Twilio
GitHub Actions Version
"""

import os
import requests
from bs4 import BeautifulSoup
from twilio.rest import Client
from datetime import datetime

class MGITAttendanceTracker:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://mgit.winnou.net"
        
        # Get credentials from environment variables
        self.username = os.environ.get('MGIT_USERNAME')
        self.password = os.environ.get('MGIT_PASSWORD')
        
        # Twilio credentials
        self.twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        self.twilio_token = os.environ.get('TWILIO_AUTH_TOKEN')
        self.twilio_whatsapp = os.environ.get('TWILIO_WHATSAPP_NUMBER')
        self.my_whatsapp = os.environ.get('MY_WHATSAPP_NUMBER')
        
        # Validate required environment variables
        required_vars = [
            'MGIT_USERNAME', 'MGIT_PASSWORD', 
            'TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN',
            'TWILIO_WHATSAPP_NUMBER', 'MY_WHATSAPP_NUMBER'
        ]
        
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        if missing_vars:
            raise ValueError(f"Missing environment variables: {', '.join(missing_vars)}")
        
        self.client = Client(self.twilio_sid, self.twilio_token)
    
    def login(self):
        """Login to MGIT portal"""
        try:
            print("Attempting to login to MGIT portal...")
            login_url = f"{self.base_url}/login"
            
            # Get login page
            response = self.session.get(login_url, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Prepare login payload
            payload = {
                'username': self.username,
                'password': self.password
            }
            
            # Check for CSRF token or other hidden fields
            csrf_input = soup.find('input', {'name': '_token'})
            if csrf_input:
                payload['_token'] = csrf_input.get('value')
            
            # Post login credentials
            login_response = self.session.post(
                login_url, 
                data=payload,
                timeout=30,
                allow_redirects=True
            )
            
            # Check if login was successful
            if login_response.status_code == 200 and 'logout' in login_response.text.lower():
                print("✓ Login successful")
                return True
            else:
                print("✗ Login failed - Invalid credentials or portal structure changed")
                return False
                
        except requests.exceptions.Timeout:
            print("✗ Login timeout - Portal may be down")
            return False
        except Exception as e:
            print(f"✗ Login error: {str(e)}")
            return False
    
    def get_attendance(self):
        """Scrape attendance data from portal"""
        try:
            print("Fetching attendance data...")
            attendance_url = f"{self.base_url}/attendance"
            response = self.session.get(attendance_url, timeout=30)
            
            if response.status_code != 200:
                print(f"Failed to fetch attendance page - Status: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try multiple possible table selectors
            table = (
                soup.find('table', class_='attendance-table') or
                soup.find('table', class_='table') or
                soup.find('table', {'id': 'attendance'}) or
                soup.find('table')
            )
            
            if not table:
                print("No attendance table found on page")
                return None
            
            attendance_data = []
            rows = table.find_all('tr')[1:]  # Skip header row
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    subject = cols[0].text.strip()
                    present = cols[1].text.strip()
                    total = cols[2].text.strip()
                    percentage = cols[3].text.strip() if len(cols) > 3 else "N/A"
                    
                    # Skip empty rows
                    if subject and present and total:
                        attendance_data.append({
                            'subject': subject,
                            'present': present,
                            'total': total,
                            'percentage': percentage
                        })
            
            if attendance_data:
                print(f"✓ Found attendance data for {len(attendance_data)} subjects")
                return attendance_data
            else:
                print("No attendance records found")
                return None
            
        except requests.exceptions.Timeout:
            print("✗ Timeout fetching attendance data")
            return None
        except Exception as e:
            print(f"✗ Error fetching attendance: {str(e)}")
            return None
    
    def format_message(self, attendance_data):
        """Format attendance data into WhatsApp message"""
        if not attendance_data:
            return "❌ Unable to fetch attendance data from MGIT portal"
        
        # Determine time of day
        current_hour = datetime.now().hour
        if current_hour < 12:
            time_of_day = "Morning"
            greeting = "Good Morning! 🌅"
        elif current_hour < 17:
            time_of_day = "Afternoon"
            greeting = "Good Afternoon! ☀️"
        else:
            time_of_day = "Evening"
            greeting = "Good Evening! 🌆"
        
        # Build message
        message = f"{greeting}\n\n"
        message += f"📚 *MGIT Attendance Update*\n"
        message += f"📅 {datetime.now().strftime('%d %B %Y, %I:%M %p')}\n"
        message += f"{'='*30}\n\n"
        
        # Add each subject
        for item in attendance_data:
            try:
                percentage_value = float(item['percentage'].rstrip('%'))
                if percentage_value >= 75:
                    emoji = "✅"
                elif percentage_value >= 65:
                    emoji = "⚠️"
                else:
                    emoji = "🔴"
            except:
                emoji = "📊"
            
            message += f"{emoji} *{item['subject']}*\n"
            message += f"   Classes: {item['present']}/{item['total']}\n"
            message += f"   Percentage: {item['percentage']}\n\n"
        
        # Calculate overall percentage
        try:
            total_present = sum(int(item['present']) for item in attendance_data)
            total_classes = sum(int(item['total']) for item in attendance_data)
            overall = (total_present / total_classes * 100) if total_classes > 0 else 0
            
            message += f"{'='*30}\n"
            message += f"📊 *Overall Attendance: {overall:.2f}%*\n"
            
            if overall < 75:
                classes_needed = int((0.75 * total_classes - total_present) / 0.25) + 1
                message += f"\n⚠️ *Alert:* Below 75%!\n"
                message += f"Need {classes_needed} more classes to reach 75%\n"
            elif overall >= 90:
                message += f"\n🎉 Excellent attendance! Keep it up!\n"
            
        except Exception as e:
            print(f"Error calculating overall percentage: {e}")
        
        message += f"\n_Powered by MGIT Tracker_ 🤖"
        
        return message
    
    def send_whatsapp(self, message):
        """Send WhatsApp message via Twilio"""
        try:
            print("Sending WhatsApp message...")
            msg = self.client.messages.create(
                from_=f'whatsapp:{self.twilio_whatsapp}',
                body=message,
                to=f'whatsapp:{self.my_whatsapp}'
            )
            print(f"✓ WhatsApp message sent successfully!")
            print(f"  Message SID: {msg.sid}")
            return True
        except Exception as e:
            print(f"✗ WhatsApp error: {str(e)}")
            return False
    
    def run_attendance_check(self):
        """Main function to check and send attendance"""
        print("\n" + "="*60)
        print(f"🎓 MGIT ATTENDANCE TRACKER")
        print(f"⏰ Running at: {datetime.now().strftime('%d %B %Y, %I:%M:%S %p IST')}")
        print("="*60 + "\n")
        
        # Step 1: Login
        if not self.login():
            error_msg = "❌ Failed to login to MGIT portal. Please check your credentials."
            print(error_msg)
            self.send_whatsapp(error_msg)
            return False
        
        # Step 2: Get attendance
        attendance = self.get_attendance()
        
        # Step 3: Format and send message
        if attendance:
            message = self.format_message(attendance)
            print("\n" + "-"*60)
            print("MESSAGE TO BE SENT:")
            print("-"*60)
            print(message)
            print("-"*60 + "\n")
            
            success = self.send_whatsapp(message)
            if success:
                print("\n✅ Attendance check completed successfully!\n")
                return True
            else:
                print("\n❌ Failed to send WhatsApp message\n")
                return False
        else:
            error_msg = "❌ Failed to retrieve attendance data from portal. The portal may be down or the HTML structure may have changed."
            print(error_msg)
            self.send_whatsapp(error_msg)
            return False

def main():
    """Main entry point"""
    try:
        tracker = MGITAttendanceTracker()
        tracker.run_attendance_check()
    except ValueError as e:
        print(f"\n❌ Configuration Error: {str(e)}")
        print("Please check your GitHub Secrets are properly set.\n")
    except Exception as e:
        print(f"\n❌ Unexpected Error: {str(e)}\n")

if __name__ == "__main__":
    main()
