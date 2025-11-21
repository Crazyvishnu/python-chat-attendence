# MGIT Attendance WhatsApp Bot 📱

Automated attendance notifications via WhatsApp using Twilio API and GitHub Actions.

## ✨ Features
- ✅ Automatic WhatsApp messages at 8 AM & 4 PM IST
- ✅ Real-time attendance updates from MGIT portal
- ✅ Color-coded attendance percentages
- ✅ 100% automated using GitHub Actions
- ✅ Secure (credentials stored in GitHub Secrets)

## 🚀 Setup Instructions

### 1. Twilio Setup
1. Create account at https://www.twilio.com/try-twilio
2. Go to Messaging → WhatsApp → Sandbox
3. Send `join <code>` to +1 415 523 8886 from your WhatsApp
4. Get your Account SID and Auth Token from Console

### 2. GitHub Secrets
Add these 6 secrets in Settings → Secrets → Actions:

| Secret Name | Example Value |
|------------|---------------|
| `TWILIO_ACCOUNT_SID` | ACxxxxxxxxxxxxxxxx |
| `TWILIO_AUTH_TOKEN` | your_auth_token |
| `TWILIO_WHATSAPP_FROM` | whatsapp:+14155238886 |
| `YOUR_WHATSAPP_NUMBER` | whatsapp:+919876543210 |
| `MGIT_USERNAME` | your_roll_number |
| `MGIT_PASSWORD` | your_password |

### 3. Activate
1. Go to Actions tab
2. Click "MGIT Attendance WhatsApp Bot"
3. Click "Run workflow" to test

## ⏰ Schedule
- **8:00 AM IST** - Morning update
- **4:00 PM IST** - Evening update

## 📊 Message Format
