# playwright_attendance.py
# Python (async) Playwright + Twilio script.
# Reads secrets from environment:
# COLLEGE_USER, COLLEGE_PASS, MY_PHONE_NUMBER, TWILIO_PHONE_NUMBER, TWILIO_SID, TWILIO_TOKEN

import os
import asyncio
import re
import sys
from pathlib import Path
from twilio.rest import Client
from playwright.async_api import async_playwright

LOGIN_URL = "https://mgit.winnou.net/index.php"
DASHBOARD_URL = "https://mgit.winnou.net/index.php"

COLLEGE_USER = os.getenv("COLLEGE_USER")
COLLEGE_PASS = os.getenv("COLLEGE_PASS")
MY_PHONE_NUMBER = os.getenv("MY_PHONE_NUMBER")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")

DIAG_SCREEN = Path("diagnostic_screenshot.png")
DIAG_HTML = Path("diagnostic_page.html")
FATAL_SCREEN = Path("fatal_error_screenshot.png")
FATAL_HTML = Path("fatal_error_page.html")


def enough_env():
    return all([COLLEGE_USER, COLLEGE_PASS, MY_PHONE_NUMBER, TWILIO_PHONE_NUMBER, TWILIO_SID, TWILIO_TOKEN])


async def run():
    if not enough_env():
        print("Missing required environment variables. Exiting.", file=sys.stderr)
        sys.exit(1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()

        try:
            print("🔵 Opening login page...")
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)

            # Try to find username/password inputs using multiple selectors
            username_selectors = [
                'input[name*=user]', 'input[id*=user]', 'input[name*=roll]', 'input[id*=roll]',
                'input[type="text"]', 'input[type="email"]'
            ]
            password_selectors = [
                'input[type="password"]', 'input[name*=pass]', 'input[id*=pass]', 'input[name*=pwd]', 'input[id*=pwd]'
            ]

            user_found = False
            pass_found = False

            for sel in username_selectors:
                el = await page.query_selector(sel)
                if el:
                    await el.fill(COLLEGE_USER)
                    user_found = True
                    break

            for sel in password_selectors:
                el = await page.query_selector(sel)
                if el:
                    await el.fill(COLLEGE_PASS)
                    pass_found = True
                    break

            # fallback scanning inputs by attributes
            if not user_found or not pass_found:
                inputs = await page.query_selector_all("input")
                for inp in inputs:
                    try:
                        placeholder = (await inp.get_attribute("placeholder") or "").lower()
                        name = (await inp.get_attribute("name") or "").lower()
                        _id = (await inp.get_attribute("id") or "").lower()
                        _type = (await inp.get_attribute("type") or "").lower()
                    except Exception:
                        continue
                    if not user_found and ("user" in placeholder or "roll" in placeholder or "user" in name or "user" in _id or "roll" in name or "roll" in _id):
                        await inp.fill(COLLEGE_USER)
                        user_found = True
                    if not pass_found and (_type == "password" or "pass" in name or "pass" in _id or "password" in placeholder):
                        await inp.fill(COLLEGE_PASS)
                        pass_found = True
                    if user_found and pass_found:
                        break

            if not user_found or not pass_found:
                print("❌ Could not locate login fields reliably. Saving screenshot for debugging.")
                await page.screenshot(path=DIAG_SCREEN, full_page=True)
                await browser.close()
                sys.exit(2)

            print("🔑 Credentials entered. Attempting login...")
            # submit: Enter then try clicking submit buttons if needed
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(1200)

            if "index.php" in page.url:
                submit_btn = await page.query_selector('button[type="submit"], input[type="submit"], button:has-text("Login"), button:has-text("Sign in"), a:has-text("Login")')
                if submit_btn:
                    try:
                        await submit_btn.click()
                    except Exception:
                        pass

            # wait for load/render
            try:
                await page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            await page.wait_for_timeout(1500)

            # Click "Student Info" explicitly
            nav_clicked = None
            try:
                exact = await page.query_selector('text="Student Info"')
                if exact:
                    await exact.click()
                    try:
                        await page.wait_for_load_state("networkidle", timeout=8000)
                    except Exception:
                        pass
                    await page.wait_for_timeout(900)
                    body = (await page.inner_text("body")).lower()
                    if "present term" in body or "attendance" in body:
                        nav_clicked = "Student Info (exact)"
            except Exception:
                pass

            if not nav_clicked:
                # try partial matches
                elems = await page.query_selector_all("a,button,li,span")
                for el in elems:
                    try:
                        txt = (await el.inner_text()).strip()
                    except Exception:
                        continue
                    if not txt:
                        continue
                    if "student info" in txt.lower():
                        try:
                            await el.click()
                        except Exception:
                            pass
                        try:
                            await page.wait_for_load_state("networkidle", timeout=8000)
                        except Exception:
                            pass
                        await page.wait_for_timeout(900)
                        body = (await page.inner_text("body")).lower()
                        if "present term" in body or "attendance" in body:
                            nav_clicked = f"Student Info (partial: {txt[:40]})"
                            break

            if not nav_clicked:
                # last resort: reload dashboard url
                try:
                    await page.goto(DASHBOARD_URL, wait_until="domcontentloaded")
                except Exception:
                    pass
                await page.wait_for_timeout(900)
                body = (await page.inner_text("body")).lower()
                if "present term" in body or "attendance" in body:
                    nav_clicked = "direct-dashboard"

            print("NAV_CLICKED:", nav_clicked or "none")
            await page.wait_for_timeout(900)

            # Use a JS DOM-aware extractor (runs in page context) — returns a dict-like object
            extractor_js = r'''
            () => {
              function stripZeros(s){ return s.replace(/\.?0+$/,''); }
              function isDateContext(text, idx, len){
                const before = text.slice(Math.max(0, idx - 6), idx);
                const after = text.slice(idx + len, idx + len + 6);
                return before.includes('-') || after.includes('-') || before.includes('/') || after.includes('/');
              }

              // 1) Present Term container
              const presentNodes = Array.from(document.querySelectorAll('body *')).filter(n => {
                try { return /\bPresent Term\b/i.test(n.innerText || ''); } catch(e){ return false; }
              });
              for (const pn of presentNodes) {
                const container = pn.closest('div') || pn.parentElement;
                if (!container) continue;
                const text = container.innerText || '';
                const pct = text.match(/(\d{1,3}(?:\.\d{1,2})?)\s*%/);
                if (pct && Number(pct[1]) <= 100) return {found:true, value: stripZeros(pct[1]) + '%', method:'presentterm-percent'};
                const par = text.match(/\((\d{1,3}(?:\.\d{1,2})?)\)/);
                if (par && Number(par[1]) <= 100) return {found:true, value: stripZeros(par[1]) + '%', method:'presentterm-paren'};
                const re = /(\d{1,3}(?:\.\d{1,2})?)/g;
                let m;
                while ((m = re.exec(text)) !== null) {
                  if (isDateContext(text, m.index, m[1].length)) continue;
                  const n = Number(m[1]);
                  if (!isNaN(n) && n>=0 && n<=100) return {found:true, value: stripZeros(String(n))+'%', method:'presentterm-token'};
                }
              }

              // 2) Attendance label vicinity
              const attNodes = Array.from(document.querySelectorAll('body *')).filter(n => {
                try { return /\bAttendance\b/i.test(n.innerText || ''); } catch(e){ return false; }
              });
              for (const node of attNodes) {
                const parent = node.parentElement;
                const candidates = [];
                if (parent) {
                  candidates.push(parent);
                  const grand = parent.parentElement;
                  if (grand) candidates.push(...Array.from(grand.children || []));
                }
                const closest = node.closest('td,div,section,table') || parent;
                if (closest) candidates.push(closest);
                for (const c of Array.from(new Set(candidates))) {
                  try {
                    const txt = c.innerText || '';
                    let m = txt.match(/(\d{1,3}(?:\.\d{1,2})?)\s*%/);
                    if (m && Number(m[1]) <=100) return {found:true, value: stripZeros(m[1]) + '%', method:'attendance-sibling-percent'};
                    m = txt.match(/\((\d{1,3}(?:\.\d{1,2})?)\)/);
                    if (m && Number(m[1]) <=100) return {found:true, value: stripZeros(m[1]) + '%', method:'attendance-sibling-paren'};
                    const re = /(\d{1,3}(?:\.\d{1,2})?)/g; let mm;
                    while ((mm = re.exec(txt)) !== null) {
                      if (isDateContext(txt, mm.index, mm[1].length)) continue;
                      const n = Number(mm[1]);
                      if (!isNaN(n) && n>=0 && n<=100) return {found:true, value: stripZeros(String(n)) + '%', method:'attendance-sibling-token'};
                    }
                  } catch(e){}
                }
              }

              // 3) parentheses anywhere near Attendance
              const pageText = document.body.innerText || '';
              const parenAll = Array.from(pageText.matchAll(/\((\d{1,3}(?:\.\d{1,2})?)\)/g)).map(m=>({v:m[1], idx:m.index}));
              if (parenAll.length) {
                const attIdx = pageText.toLowerCase().indexOf('attendance');
                if (attIdx >= 0) {
                  parenAll.sort((a,b)=> Math.abs(a.idx-attIdx) - Math.abs(b.idx-attIdx));
                  for (const p of parenAll) {
                    if (!isDateContext(pageText, p.idx, String(p.v).length)) {
                      const n = Number(p.v); if (!isNaN(n) && n>=0 && n<=100) return {found:true, value: stripZeros(String(n))+'%', method:'paren-near-att'};
                    }
                  }
                }
              }

              // 4) explicit percent anywhere
              const pctAll = Array.from(pageText.matchAll(/(\d{1,3}(?:\.\d{1,2})?)\s*%/g)).map(m=>({v:m[1], idx:m.index}));
              if (pctAll.length) {
                const attIdx = pageText.toLowerCase().indexOf('attendance');
                if (attIdx >= 0) {
                  pctAll.sort((a,b)=> Math.abs(a.idx-attIdx)-Math.abs(b.idx-attIdx));
                  const n = Number(pctAll[0].v); if (!isNaN(n) && n>=0 && n<=100) return {found:true, value: stripZeros(String(n))+'%', method:'pct-near-att'};
                } else {
                  const nums = pctAll.map(x=>Number(x.v)).filter(x=>!isNaN(x) && x>=0 && x<=100);
                  if (nums.length) { const n = Math.max(...nums); return {found:true, value: stripZeros(String(n))+'%', method:'pct-any'}; }
                }
              }

              return {found:false, snippet: pageText.slice(0,2000)};
            }
            '''

            extraction = await page.evaluate(extractor_js)

            if extraction and extraction.get("found"):
                value = extraction.get("value")
                method = extraction.get("method", "unknown")
                print(f"EXTRACTED_ATTENDANCE {value} method={method}")
                # send WhatsApp via Twilio
                client = Client(TWILIO_SID, TWILIO_TOKEN)
                body = f"📢 College Attendance Update\nYour current attendance is: {value}\n🕒 Have a great day!"
                msg = client.messages.create(body=body, from_=f"whatsapp:{TWILIO_PHONE_NUMBER}", to=f"whatsapp:{MY_PHONE_NUMBER}")
                print("SENT_SID", msg.sid)
                await browser.close()
                sys.exit(0)
            else:
                print("DEBUG: Unable to extract attendance automatically.")
                snippet = extraction.get("snippet") if extraction else None
                if snippet:
                    print("PAGE_SNIPPET:", snippet)
                # save diagnostics
                await page.screenshot(path=DIAG_SCREEN, full_page=True)
                content = await page.content()
                DIAG_HTML.write_text(content, encoding="utf-8")
                print("DIAGNOSTIC_SCREENSHOT:", str(DIAG_SCREEN))
                print("DIAGNOSTIC_HTML:", str(DIAG_HTML))
                await browser.close()
                sys.exit(2)

        except Exception as e:
            print("ERROR:", e, file=sys.stderr)
            try:
                await page.screenshot(path=FATAL_SCREEN, full_page=True)
            except Exception:
                pass
            try:
                content = await page.content()
                FATAL_HTML.write_text(content, encoding="utf-8")
            except Exception:
                pass
            await browser.close()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
