import os
import re
import json
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright
from src.utils import export_results, load_config

def run_price_guard_audit(urls_list=None, log_callback=print, stop_checker=None, headless=False, export_format="Excel (.xlsx)", item_callback=None, progress_callback=None):
    """
    Advanced Stealth Price & Stock Intelligence Engine for PriceGuard v0.1.0.
    Handles B&H Photo sticky price headers, 'No Longer Available' stock flags, & 404 error captures.
    """
    config = load_config()
    output_file = config.get("output_file", "output.xlsx")

    if not urls_list:
        urls_list = config.get("test_urls", [])

    total_urls = len(urls_list)
    log_callback(f"[INIT] Loaded {total_urls} target endpoints for audit.")
    extracted_records = []

    with sync_playwright() as p:
        log_callback(f"[BROWSER] Launching Stealth Chromium engine (Headless={headless})...")
        
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1"
            }
        )
        
        page = context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            window.chrome = { runtime: {} };
        """)

        for idx, url in enumerate(urls_list, 1):
            if stop_checker and stop_checker():
                log_callback("[STOP] Audit pipeline cancelled by user.")
                break

            if progress_callback:
                progress_callback(idx, total_urls)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            timestamp_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_callback(f"[AUDIT] [{idx}/{total_urls}] Checking endpoint: {url}")

            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=20000)
                
                # 1. Catch 404 / HTTP Error status
                if response and response.status >= 400:
                    status_code = response.status
                    log_callback(f"[ERROR {status_code}] Target endpoint returned HTTP {status_code} Error!")
                    
                    shot_path = os.path.join("screenshots", f"error_{status_code}_{timestamp_id}.png")
                    page.screenshot(path=shot_path)

                    record = {
                        "Target_URL": url,
                        "Product_Title": f"HTTP {status_code} Error - Item Not Found",
                        "Price_USD": 0.0,
                        "Stock_Status": f"NOT FOUND ({status_code})",
                        "Timestamp": timestamp,
                        "Extraction_Status": f"FAILED ({status_code})"
                    }
                    extracted_records.append(record)

                    if item_callback:
                        item_callback(idx, record["Product_Title"], 0.0, record["Stock_Status"])
                    continue

                page.wait_for_timeout(1500)

                # Auto-scroll 600px to trigger sticky header with price ($2,499.00)
                page.mouse.wheel(0, 600)
                page.wait_for_timeout(1000)

                # Obliterate promo popups via CSS
                try:
                    page.add_style_tag(content="""
                        .modal, .popup, [class*='popup'], [id*='popup'], [class*='subscribe'], .mfp-bg, .mfp-wrap { 
                            display: none !important; 
                            visibility: hidden !important; 
                            opacity: 0 !important; 
                        }
                    """)
                except Exception:
                    pass

                # 2. Extract Product Title
                title = "N/A"
                title_elem = page.locator('h1, [class*="title"], [class*="heading"], .product-title').first
                if title_elem.count() > 0:
                    title = title_elem.inner_text().strip().replace('\n', ' ')

                # 3. Stock Status Detection
                raw_body = page.locator("body").inner_text().lower()
                stock_status = "IN STOCK"
                if any(phrase in raw_body for phrase in ["out of stock", "sold out", "currently unavailable", "no longer available", "not available", "discontinued"]):
                    stock_status = "OUT OF STOCK"

                # 4. Deep Price Extraction (Ignores tiny $2.00 shipping fees)
                price_val = 0.0

                # Strategy A: B&H Sticky Header & Pricing Selectors
                price_elems = page.locator('[data-selenium="pricingPrice"], [data-selenium="price"], [class*="pricingPrice"], [class*="price"]').all()
                for p_elem in price_elems:
                    try:
                        p_text = p_elem.inner_text().strip()
                        matches = re.findall(r'[\d,]+\.?\d{0,2}', p_text)
                        if matches:
                            clean_p = float(matches[0].replace(',', ''))
                            if clean_p > price_val:
                                price_val = clean_p
                    except Exception:
                        pass

                # Strategy B: JSON-LD Schema
                if price_val == 0.0:
                    try:
                        json_scripts = page.locator('script[type="application/ld+json"]').all()
                        for script in json_scripts:
                            script_text = script.inner_text().strip()
                            found_prices = re.findall(r'"price"\s*:\s*"?([\d\.]+)"?', script_text)
                            for p_str in found_prices:
                                try:
                                    p_float = float(p_str)
                                    if p_float > price_val:
                                        price_val = p_float
                                except ValueError:
                                    pass
                    except Exception:
                        pass

                # Strategy C: Full page USD Regex (Filters out small $2.00 fees if real product price exists)
                if price_val == 0.0:
                    raw_text = page.locator("body").inner_text()
                    price_matches = re.findall(r'\$\s?([\d,]+\.?\d{0,2})', raw_text)
                    valid_prices = []
                    for pm in price_matches:
                        try:
                            val = float(pm.replace(',', ''))
                            if val > 5.0: # Skip small shipping/promo fees
                                valid_prices.append(val)
                        except ValueError:
                            pass
                    if valid_prices:
                        price_val = max(valid_prices)

                record = {
                    "Target_URL": url,
                    "Product_Title": title[:80],
                    "Price_USD": price_val,
                    "Stock_Status": stock_status,
                    "Timestamp": timestamp,
                    "Extraction_Status": "SUCCESS"
                }
                extracted_records.append(record)

                if item_callback:
                    item_callback(idx, record["Product_Title"], price_val, stock_status)

                shot_path = os.path.join("screenshots", f"success_{timestamp_id}.png")
                page.screenshot(path=shot_path)
                log_callback(f"[SUCCESS] Extracted '${price_val:.2f}' | Status: {stock_status}")

            except Exception as e:
                log_callback(f"[ERROR] Endpoint navigation failure: {e}")
                shot_path = os.path.join("screenshots", f"failure_{timestamp_id}.png")
                try:
                    page.screenshot(path=shot_path)
                except Exception:
                    pass

                record = {
                    "Target_URL": url,
                    "Product_Title": "Page Navigation Timeout / Error",
                    "Price_USD": 0.0,
                    "Stock_Status": "NOT FOUND (TIMEOUT)",
                    "Timestamp": timestamp,
                    "Extraction_Status": "FAILED (TIMEOUT)"
                }
                extracted_records.append(record)

                if item_callback:
                    item_callback(idx, "Page Navigation Timeout", 0.0, "NOT FOUND")

        browser.close()
        log_callback("[BROWSER] Closed Playwright Chromium session.")

    final_file = export_results(extracted_records, output_file, export_format)
    log_callback(f"[COMPLETE] Audit finished! Dataset saved: '{final_file}'")
    return final_file