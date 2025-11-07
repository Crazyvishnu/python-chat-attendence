// playwright_attendance.js
// Node + Playwright: improved DOM-aware extractor for the MGIT portal

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

function numericOk(n) {
  return !isNaN(n) && n >= 0 && n <= 100;
}

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    await page.goto(LOGIN_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });

    // Fill username/password by trying several selectors
    const usernameSelectors = [
      'input[type="text"]',
      'input[type="email"]',
      'input[name*=user]',
      'input[name*=email]',
      'input[id*=user]',
      'input[id*=email]',
      'input[name*=username]',
      'input[id*=username]'
    ];
    const passwordSelectors = [
      'input[type="password"]',
      'input[name*=pass]',
      'input[id*=pass]',
      'input[name*=pwd]',
      'input[id*=pwd]'
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

    // Submit: try pressing Enter then try clicking submit button if needed
    if (filledPass) {
      await page.keyboard.press('Enter').catch(()=>{});
    }
    // small wait for possible JS submit
    await page.waitForTimeout(1500);

    // If still on login page, try clicking submit buttons
    if ((await page.url()).includes('index.php')) {
      const submitBtn = await page.$('button[type="submit"], input[type="submit"], a[href*="login"], button:has-text("Login"), button:has-text("Sign in")');
      if (submitBtn) {
        await submitBtn.click().catch(()=>{});
      }
    }

    // Wait for navigation and rendering
    await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(()=>{});
    await page.waitForTimeout(1500);

    // Ensure dashboard loaded - try direct navigate if necessary
    if ((await page.url()).includes('index.php')) {
      await page.goto(DASHBOARD_URL, { waitUntil: 'domcontentloaded' }).catch(()=>{});
      await page.waitForTimeout(1500);
    }

    // --------- DOM-aware extraction ---------
    const result = await page.evaluate(() => {
      // helper inside page
      function isDateContext(text, idx, len) {
        const before = text.slice(Math.max(0, idx - 6), idx);
        const after = text.slice(idx + len, idx + len + 6);
        return before.includes('-') || after.includes('-') || before.includes('/') || after.includes('/');
      }

      function findNumericTokens(text) {
        const re = /(\d{1,3}(?:\.\d{1,2})?)/g;
        const out = [];
        let m;
        while ((m = re.exec(text)) !== null) {
          out.push({ token: m[1], index: m.index, len: m[1].length });
        }
        return out;
      }

      // 1) Try to find elements that contain the word "Attendance"
      const attNodes = Array.from(document.querySelectorAll('body *')).filter(n => {
        try {
          return /\bAttendance\b/i.test(n.innerText || '');
        } catch (e) { return false; }
      });

      const pageText = document.body.innerText || '';

      for (const node of attNodes) {
        // search inside closest meaningful container: node, node.parentElement, node.closest('td,div,section,table')
        const containers = [];
        containers.push(node);
        if (node.parentElement) containers.push(node.parentElement);
        const closest = node.closest('td,div,section,article,table,tbody') || node.parentElement;
        if (closest) containers.push(closest);

        // add siblings of parent to the search space (sometimes value is in sibling cell)
        if (node.parentElement && node.parentElement.parentElement) {
          const siblings = Array.from(node.parentElement.parentElement.children || []);
          containers.push(...siblings);
        }

        // dedupe containers
        const uniqContainers = Array.from(new Set(containers));

        for (const c of uniqContainers) {
          const text = c.innerText || '';
          // a) look for explicit percent first
          const pctMatch = text.match(/(\d{1,3}(?:\.\d{1,2})?)\s*%/);
          if (pctMatch && Number(pctMatch[1]) <= 100) {
            return { found: true, value: (pctMatch[1].replace(/\.?0+$/,'') + '%'), method: 'percent-in-container' };
          }
          // b) look for parentheses like (72.29)
          const parenMatch = text.match(/\((\d{1,3}(?:\.\d{1,2})?)\)/);
          if (parenMatch && Number(parenMatch[1]) <= 100) {
            return { found: true, value: (parenMatch[1].replace(/\.?0+$/,'') + '%'), method: 'paren-in-container' };
          }
          // c) find numeric tokens in container and pick sensible one not part of date
          const tokens = findNumericTokens(text);
          if (tokens.length) {
            for (const t of tokens) {
              if (isDateContext(text, t.index, t.len)) continue;
              const num = Number(t.token);
              if (!isNaN(num) && num >= 0 && num <= 100) {
                return { found: true, value: (String(num).replace(/\.?0+$/,'') + '%'), method: 'token-in-container' };
              }
            }
          }
        }
      }

      // 2) If not found via Attendance label, search for parentheses anywhere but avoid dates
      const allText = document.body.innerText || '';
      const parenAll = Array.from(allText.matchAll(/\((\d{1,3}(?:\.\d{1,2})?)\)/g)).map(m => ({v: m[1], idx: m.index}));
      if (parenAll.length) {
        for (const p of parenAll) {
          if (!isDateContext(allText, p.idx, String(p.v).length)) {
            const n = Number(p.v);
            if (!isNaN(n) && n >= 0 && n <= 100) {
              return { found: true, value: (String(n).replace(/\.?0+$/,'') + '%'), method: 'paren-anywhere' };
            }
          }
        }
      }

      // 3) search for explicit percent anywhere and choose one nearest to the word "Attendance"
      const pctAll = Array.from(allText.matchAll(/(\d{1,3}(?:\.\d{1,2})?)\s*%/g)).map(m => ({v: m[1], idx: m.index}));
      if (pctAll.length) {
        const attIdx = allText.toLowerCase().indexOf('attendance');
        if (attIdx >= 0) {
          pctAll.sort((a,b) => Math.abs(a.idx - attIdx) - Math.abs(b.idx - attIdx));
          const n = Number(pctAll[0].v);
          if (!isNaN(n) && n >= 0 && n <= 100) return { found: true, value: (String(n).replace(/\.?0+$/,'') + '%'), method: 'pct-anywhere-near-att' };
        } else {
          // fallback pick largest sensible pct
          const nums = pctAll.map(x => Number(x.v)).filter(x => !isNaN(x) && x >= 0 && x <= 100);
          if (nums.length) {
            const n = Math.max(...nums);
            return { found: true, value: (String(n).replace(/\.?0+$/,'') + '%'), method: 'pct-anywhere-largest' };
          }
        }
      }

      return { found: false, snippet: allText.slice(0, 2000) };
    });

    if (result && result.found) {
      console.log('EXTRACTED_ATTENDANCE', result.value, 'method=' + (result.method || 'unknown'));
      // send Twilio message
      const client = twilio(TWILIO_SID, TWILIO_TOKEN);
      const body = `📢 College Attendance Update\nYour current attendance is: ${result.value}\n🕒 Have a great day!`;
      const msg = await client.messages.create({
        body,
        from: `whatsapp:${TWILIO_PHONE_NUMBER}`,
        to: `whatsapp:${MY_PHONE_NUMBER}`
      });
      console.log('SENT_SID', msg.sid);
      await browser.close();
      process.exit(0);
    }

    // If extraction failed - log snippet for debugging
    console.error('DEBUG: Unable to extract attendance automatically.');
    if (result && result.snippet) {
      console.error('PAGE_SNIPPET:', result.snippet);
    } else {
      const txt = await page.textContent('body').catch(()=>'');
      console.error('PAGE_SNIPPET:', (txt || '').slice(0, 2000));
    }

    await browser.close();
    process.exit(2);
  } catch (err) {
    console.error('ERROR:', err);
    await browser.close();
    process.exit(1);
  }
})();
