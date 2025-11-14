# tolerant debug save
def _save_debug(page, prefix="failure"):
    ss = Path(f"{prefix}_screenshot.png")
    html = Path(f"{prefix}_page.html")
    # Save HTML first (fast, safe)
    try:
        html.write_text(page.content())
        print(f"Saved page HTML: {html}")
    except Exception as e:
        print("Failed to save page HTML:", e)

    # Screenshot may fail on some pages (fonts, huge resources) - attempt but don't raise
    try:
        # increase timeout to 60s for screenshot
        page.screenshot(path=str(ss), full_page=True, timeout=60000)
        print(f"Saved screenshot: {ss}")
    except Exception as e:
        print("Screenshot failed (non-fatal):", e)
        # Optionally try a smaller partial screenshot fallback
        try:
            page.screenshot(path=str(ss), full_page=False, timeout=15000)
            print("Saved fallback screenshot (viewport):", ss)
        except Exception as e2:
            print("Fallback screenshot also failed:", e2)

# robust scrape with load wait and extra logging
def scrape_attendance(max_retries=4):
    from playwright.sync_api import sync_playwright
    last_err = None
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"})
        for attempt in range(1, max_retries + 1):
            try:
                print(f"[scrape] attempt {attempt} -> goto {ATTENDANCE_URL}")
                # use load which is less strict than networkidle, and longer timeout
                page.goto(ATTENDANCE_URL, timeout=180000, wait_until="load")
                # small pause for JS rendering
                page.wait_for_timeout(2000)

                # Insert login flow here if needed (uncomment and adjust)
                # page.fill("input[name='username']", USER)
                # page.fill("input[name='password']", PASS)
                # page.click("button[type='submit']")
                # page.wait_for_load_state("load")

                # parse attendance
                subjects = []
                elements = page.query_selector_all("table#attendance-table tbody tr, table.attendance tbody tr, .attendance-table tr")
                if elements:
                    for r in elements:
                        cols = r.query_selector_all("td")
                        if len(cols) < 1:
                            continue
                        subject = cols[0].inner_text().strip()
                        present = cols[1].inner_text().strip() if len(cols) > 1 else ""
                        total = cols[2].inner_text().strip() if len(cols) > 2 else ""
                        percent = cols[3].inner_text().strip() if len(cols) > 3 else ""
                        subjects.append({"subject": subject, "present": present, "total": total, "percent": percent})
                if not subjects:
                    subjects = parse_tables_for_attendance(page)

                print(f"[scrape] parsed {len(subjects)} attendance items.")

                data = {
                    "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    "items": subjects
                }
                CURRENT_FILE.write_text(json.dumps(data, indent=2))
                browser.close()
                return data

            except Exception as e:
                last_err = e
                print(f"[scrape] attempt {attempt} failed: {e}")
                try:
                    _save_debug(page, prefix=f"failure_attempt_{attempt}")
                except Exception as se:
                    print("debug save err:", se)
                # exponential backoff (cap at 30s)
                backoff = min(2 ** attempt, 30)
                print(f"Retrying in {backoff}s...")
                time.sleep(backoff)
        browser.close()
    print("All scrape attempts failed. Raising last exception.")
    raise last_err
