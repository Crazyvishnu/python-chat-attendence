// playwright_attendance.js
// Node script: uses Playwright to render the page, extract attendance and send via Twilio.

const { chromium } = require('playwright');
const twilio = require('twilio');

const LOGIN_URL = 'https://mgit.winnou.net/index.php';
const DASHBOARD_URL = 'https://mgit.winnou.net/index.php';

const COLLEGE_USER = process.env.COLLEGE_USER;
const COLLEGE_PASS = process.env.COLLEGE_PASS;
const MY_PHONE_NUMBER = process.env.MY_PHONE_NUMBER;           // e.g. +91XXXXXXXXXX
const TWILIO_PHONE_NUMBER = process.env.TWILIO_PHONE_NUMBER; // e.g. +1415XXXXXXX
const TWILIO_SID = process.env.TWILIO_SID;
const TWILIO_TOKEN = process.env.TWILIO_TOKEN;

if (!COLLEGE_USER || !COLLEGE_PASS || !MY_PHONE_NUMBER || !TWILIO_PHONE_NUMBER || !TWILIO_SID || !TWILIO_TOKEN) {
  console.error('Missing required environment variables. Exiting.');
  process.exit(1);
}

function findClosestMatchToAttendance(text, matches) {
  const attIndex = text.toLowerCase().indexOf('attendance');
  if (attIndex === -1) {
    // pick the most sensible match (prefer decimals, prefer <=100)
    let dec = matches.filter(m => m.includes('.')).map(m => parseFloat(m));
    dec = dec.filter(n => !isNaN(n) && n >= 0 && n <= 100);
    if (dec.length) return dec.sort((a,b)=>b-a)[0] + '%';
    const nums = matches.map(m => parseFloat(m)).filter(n => !isNaN(n) && n >= 0 && n <= 100);
    if (nums.length) return nums.sort((a,b)=>b-a)[0] + '%';
    return null;
  }
  // choose match whose index is closest to attIndex
  let best = null;
  let bestDist = Infinity;
  for (const m of matches) {
    const idx = text.indexOf(m);
    if (idx === -1) continue;
    const dist = Math.abs(idx - attIndex);
    if (dist < bestDist) {
      bestDist = dist;
      best = m;
    }
  }
  if (!best) return null;
  const n = parseFloat(best);
  if (isNaN(n) || n < 0 || n > 100) return null;
  return (best.includes('.') ? String(parseFloat(best)) : String(Math.round(parseFloat(best)))) + '%';
}

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    await page.goto(LOGIN_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });

    // Try to find username and password fields and fill them.
    // Use several selectors to be robust.
    const usernameSelectors = [
      'input[type="text"]',
      'input[type="email"]',
      'input[name*=user]',
      'input[name*=email]',
      'input[id*=user]',
      'input[id*=email]'
    ];
    const passwordSelectors = [
      'input[type="password"]',
      'input[name*=pass]',
      'input[id*=pass]'
    ];

    let filledUser = false;
    for (const sel of usernameSelectors) {
      const el = await page.$(sel);
      if (el) {
        await el.fill(COLLEGE_USER);
        filledUser = true;
        break;
      }
    }

    let filledPass = false;
    for (const sel of passwordSelectors) {
      const el = await page.$(sel);
      if (el) {
        await el.fill(COLLEGE_PASS);
        filledPass = true;
        break;
      }
    }

    // If password field found, press Enter on it to submit; else try generic submit buttons
    if (filledPass) {
      // try to press Enter on password field
      try {
        await page.keyboard.press('Enter');
      } catch (e) {
        // ignore
      }
    } else {
      // try basic submit buttons
      const submitSel = await page.$('button[type="submit"], input[type="submit"], button');
      if (submitSel) {
        await submitSel.click();
      }
    }

    // Wait for possible navigation / JS rendering
    await page.waitForTimeout(3000);
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(()=>{});

    // If still on login page (no change), try clicking the first anchor or reload dashboard URL
    const currentUrl = page.url();
    if (currentUrl.includes('index.php') && currentUrl === LOGIN_URL) {
      // try to navigate to dashboard explicitly
      await page.goto(DASHBOARD_URL, { waitUntil: 'domcontentloaded' }).catch(()=>{});
      await page.waitForTimeout(2000);
    }

    // get page text (rendered)
    const renderedText = await page.textContent('body');

    // 1) find explicit percentages like '72.29%' or '72%'
    const pctRegex = /(\d{1,3}(?:\.\d{1,2})?)\s*%/g;
    const pctMatches = [];
    let m;
    while ((m = pctRegex.exec(renderedText)) !== null) {
      pctMatches.push(m[1]); // numeric part
    }
    if (pctMatches.length) {
      // choose one closest to "Attendance"
      const chosen = findClosestMatchToAttendance(renderedText, pctMatches);
      if (chosen) {
        console.log('EXTRACTED_ATTENDANCE', chosen);
        // send via Twilio
        const client = twilio(TWILIO_SID, TWILIO_TOKEN);
        const body = `📢 College Attendance Update\nYour current attendance is: ${chosen}\n🕒 Have a great day!`;
        const msg = await client.messages.create({
          body,
          from: `whatsapp:${TWILIO_PHONE_NUMBER}`,
          to: `whatsapp:${MY_PHONE_NUMBER}`
        });
        console.log('SENT_SID', msg.sid);
        await browser.close();
        process.exit(0);
      }
    }

    // 2) find numbers inside parentheses like (72.29)
    const parenRegex = /\((\d{1,3}(?:\.\d{1,2})?)\)/g;
    const parenMatches = [];
    while ((m = parenRegex.exec(renderedText)) !== null) {
      parenMatches.push(m[1]);
    }
    if (parenMatches.length) {
      const chosen = findClosestMatchToAttendance(renderedText, parenMatches);
      if (chosen) {
        console.log('EXTRACTED_ATTENDANCE', chosen);
        const client = twilio(TWILIO_SID, TWILIO_TOKEN);
        const body = `📢 College Attendance Update\nYour current attendance is: ${chosen}\n🕒 Have a great day!`;
        const msg = await client.messages.create({
          body,
          from: `whatsapp:${TWILIO_PHONE_NUMBER}`,
          to: `whatsapp:${MY_PHONE_NUMBER}`
        });
        console.log('SENT_SID', msg.sid);
        await browser.close();
        process.exit(0);
      }
    }

    // 3) fallback: locate 'Attendance' text node and search nearby DOM text
    const attendanceHandles = await page.$$('text=/Attendance/i');
    if (attendanceHandles.length) {
      // get full page HTML and find the nearest numeric token programmatically
      const html = await page.content();
      // strip tags to get text with positions
      const plain = await page.textContent('body');
      const numRegex = /(\d{1,3}(?:\.\d{1,2})?)/g;
      const nums = [];
      while ((m = numRegex.exec(plain)) !== null) {
        // simple date check: avoid tokens that are part of date pattern (like 07-11-2025)
        const start = m.index;
        const before = plain.slice(Math.max(0, start-6), start);
        const after = plain.slice(start + m[1].length, start + m[1].length + 6);
        if (before.includes('-') || after.includes('-') || before.includes('/') || after.includes('/')) continue;
        nums.push({token: m[1], index: start});
      }
      // choose token nearest to 'attendance'
      const attIndex = plain.toLowerCase().indexOf('attendance');
      if (nums.length && attIndex !== -1) {
        nums.sort((a,b)=>Math.abs(a.index-attIndex)-Math.abs(b.index-attIndex));
        const n = parseFloat(nums[0].token);
        if (!isNaN(n) && n >= 0 && n <= 100) {
          const chosen = (String(n).includes('.') ? String(parseFloat(n)) : String(Math.round(n))) + '%';
          console.log('EXTRACTED_ATTENDANCE', chosen);
          const client = twilio(TWILIO_SID, TWILIO_TOKEN);
          const body = `📢 College Attendance Update\nYour current attendance is: ${chosen}\n🕒 Have a great day!`;
          const msg = await client.messages.create({
            body,
            from: `whatsapp:${TWILIO_PHONE_NUMBER}`,
            to: `whatsapp:${MY_PHONE_NUMBER}`
          });
          console.log('SENT_SID', msg.sid);
          await browser.close();
          process.exit(0);
        }
      }
    }

    // Nothing found: debug output
    console.error('DEBUG: Unable to extract attendance automatically.');
    console.error('PAGE_SNIPPET:', renderedText.slice(0, 1500));
    // Optionally send a debug message to you (comment out if you don't want page content sent)
    // const client = twilio(TWILIO_SID, TWILIO_TOKEN);
    // await client.messages.create({ body: `Attendance extractor failed. Check logs.`, from: `whatsapp:${TWILIO_PHONE_NUMBER}`, to: `whatsapp:${MY_PHONE_NUMBER}` });

    await browser.close();
    process.exit(2);

  } catch (err) {
    console.error('ERROR:', err);
    await browser.close();
    process.exit(1);
  }
})();
