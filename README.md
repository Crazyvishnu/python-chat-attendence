# 🎓 MGIT Attendance Tracker

Automated attendance tracking system for MGIT that sends WhatsApp notifications twice daily via Twilio.

## 🚀 Features

- ✅ Automated login to MGIT portal
- 📊 Scrapes attendance data for all subjects
- 📱 Sends formatted WhatsApp notifications
- ⏰ Runs automatically at 8:00 AM and 4:00 PM IST
- 🔒 Secure credential management via GitHub Secrets
- 🤖 Completely free using GitHub Actions

## 📋 Prerequisites

1. **MGIT Portal Account**
   - Username (Roll Number)
   - Password

2. **Twilio Account** (Free tier works!)
   - Sign up at [twilio.com](https://www.twilio.com/try-twilio)
   - Get Account SID and Auth Token
   - Set up WhatsApp Sandbox

3. **GitHub Account**
   - Fork or create this repository

## 🔧 Setup Instructions

### Step 1: Fork/Clone Repository
```bash
git clone https://github.com/YOUR_USERNAME/mgit-attendance-tracker.git
cd mgit-attendance-tracker
```

### Step 2: Set Up Twilio WhatsApp

1. Go to [Twilio Console](https://console.twilio.com)
2. Navigate to: **Messaging → Try it out → Send a WhatsApp message**
3. Send `join <your-sandbox-code>` to the Twilio number (+1 415 523 8886)
4. You'll receive a confirmation message

### Step 3: Add GitHub Secrets

Go to your repository: **Settings → Secrets and variables → Actions → New repository secret**

Add these 6 secrets:

| Secret Name | Description | Example |
|------------|-------------|---------|
| `MGIT_USERNAME` | Your MGIT roll number | `21BD1A0501` |
| `MGIT_PASSWORD` | Your MGIT portal password | `YourPassword123` |
| `TWILIO_ACCOUNT_SID` | From Twilio Console | `ACxxxx...` |
| `TWILIO_AUTH_TOKEN` | From Twilio Console | `abcd1234...` |
| `TWILIO_WHATSAPP_NUMBER` | Twilio's WhatsApp number | `+14155238886` |
| `MY_WHATSAPP_NUMBER` | Your WhatsApp with country code | `+919876543210` |

### Step 4: Enable GitHub Actions

1. Go to **Actions** tab in your repository
2. Click "I understand my workflows, go ahead and enable them"
3. The workflow will run automatically at scheduled times

### Step 5: Test It!

**Manual Test:**
1. Go to **Actions** tab
2. Click on "MGIT Attendance Tracker" workflow
3. Click "Run workflow" → "Run workflow"
4. Check the logs and your WhatsApp!

## 📱 Sample WhatsApp Message
