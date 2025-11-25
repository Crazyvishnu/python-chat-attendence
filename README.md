# MGIT Attendance WhatsApp Bot

Automated attendance notifications via WhatsApp.

## Setup

1. Create Twilio account: https://twilio.com/try-twilio
2. Join WhatsApp sandbox: Send `join <code>` to +1 415 523 8886
3. Add GitHub Secrets (6 required):
   - TWILIO_ACCOUNT_SID
   - TWILIO_AUTH_TOKEN
   - TWILIO_WHATSAPP_FROM (e.g., whatsapp:+14155238886)
   - YOUR_WHATSAPP_NUMBER (e.g., whatsapp:+919876543210)
   - MGIT_USERNAME (your roll number)
   - MGIT_PASSWORD (your password)

4. Enable GitHub Actions
5. Test: Actions → Run workflow

## Schedule
- 8:00 AM IST
- 4:00 PM IST

## Test
Go to Actions tab → Select workflow → Run workflow

Check your WhatsApp for the message!
