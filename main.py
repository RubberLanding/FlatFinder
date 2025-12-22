import os
import json
import random
import time
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests

# Debug prints (Remove after fixing!)
print(f"DEBUG: Token length: {len(TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else 'None'}")
print(f"DEBUG: Chat ID: {TELEGRAM_CHAT_ID}")

# --- CONFIGURATION ---
SEARCH_URL = "https://www.wg-gesucht.de/wg-zimmer-in-Koeln.73.0.1.0.html?csrf_token=65bb4395273cedb934d75e5e1f6c0a87b568ae82&offer_filter=1&city_id=73&sort_order=0&noDeact=1&dFr=1764586800&categories%5B%5D=0&rent_types%5B%5D=2&sMin=10&rMax=600&ot%5B%5D=1635&ot%5B%5D=1636&ot%5B%5D=1637&ot%5B%5D=1638&ot%5B%5D=1639&ot%5B%5D=1648&ot%5B%5D=1650&ot%5B%5D=85030&ot%5B%5D=1665&ot%5B%5D=1668&ot%5B%5D=1669&ot%5B%5D=1673&ot%5B%5D=1682&ot%5B%5D=1684&ot%5B%5D=1686&ot%5B%5D=1687&ot%5B%5D=1689&ot%5B%5D=1690&ot%5B%5D=1695&ot%5B%5D=1696&ot%5B%5D=1704&ot%5B%5D=1719&wgMnF=2&wgMxT=5&wgAge=25"
SEEN_FILENAME = "seen_ads.json"

# --- TELEGRAM CONFIGURATION ---
# WARNING: Do not commit this file to a public repository with real tokens!
# This works both locally (if you have a .env file) and on GitHub Actions (if you have stored it as secrets)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("Error: Telegram tokens not found in environment variables!")

def load_seen_ids():
    if os.path.exists(SEEN_FILENAME):
        try:
            with open(SEEN_FILENAME, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_seen_ids(ids):
    with open(SEEN_FILENAME, 'w') as f:
        json.dump(list(ids), f)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        response = requests.post(url, json=payload)
        # Check for HTTP errors (4xx, 5xx)
        response.raise_for_status() 
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to send Telegram message: {e}")
        # PRINT THE ACTUAL RESPONSE FROM TELEGRAM
        if 'response' in locals(): 
            print(f"Telegram API Response: {response.text}")
            
def check_for_ads(page, seen_ids):
    print(f"Loading page...")
    try:
        page.goto(SEARCH_URL, timeout=60000)
        page.wait_for_timeout(3000) 
    except Exception as e:
        print(f"Error loading page: {e}")
        return False

    soup = BeautifulSoup(page.content(), 'html.parser')
    cards = soup.find_all("div", id=re.compile(r"^liste-details-ad-\d+"))
    
    print(f"Found {len(cards)} cards on page.")
    new_ids_found = False

    # Process from bottom up (oldest to newest on page)
    for card in reversed(cards):
        ad_id = card['id'].replace('liste-details-ad-', '')
        
        if ad_id not in seen_ids:
            seen_ids.add(ad_id)
            new_ids_found = True
            
            title_elem = card.find("h3", class_="headline")
            title = title_elem.get_text(strip=True) if title_elem else "WG Zimmer"
            
            link_elem = card.find("a", class_="detailansicht")
            link = "https://www.wg-gesucht.de" + link_elem['href'] if link_elem else SEARCH_URL
            
            # Simplified alert without AI
            print(f"🚨 New Ad: {title}")
            
            alert_msg = (
                f"🏠 **NEW FLAT ALERT!**\n\n"
                f"{title}\n\n"
                f"🔗 {link}"
            )
            send_telegram(alert_msg)
            time.sleep(2)
            
    return new_ids_found

def run_scraper():
    seen_ids = load_seen_ids()
    ids_changed_total = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # --- LOOP STRATEGY ---
        # GitHub Actions runs this script every 20 minutes.
        # We loop 9 times with a 70-140s sleep to cover the gap.

        n_iter = 9
        for i in range(n_iter):
            print(f"--- Check iteration {i+1}/3 ---")
            found_new = check_for_ads(page, seen_ids)
            
            if found_new:
                ids_changed_total = True
                save_seen_ids(seen_ids) # Save immediately so we don't lose data if crash
            
            if i < n_iter: # Don't sleep after the last check
                sleep_sec = random.randint(70, 140)
                print(f"Sleeping {sleep_sec}s before next check...")
                time.sleep(sleep_sec)

        browser.close()

    if not ids_changed_total:
        print("No new ads found in this run.")

if __name__ == "__main__":
    run_scraper()
