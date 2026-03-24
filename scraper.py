"""
scraper.py — runs as a standalone subprocess.
Receives the URL as argv[1], prints JSON to stdout.
Completely isolated from uvicorn's asyncio event loop.
"""
import sys
import json
import time
from playwright.sync_api import sync_playwright


def scrape(url: str) -> list[dict]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until="networkidle", timeout=30_000)
        except Exception:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        try:
            page.wait_for_selector(".show-card-v2-container", timeout=20_000)
        except Exception:
            browser.close()
            print(json.dumps({"error": "No show cards found. Make sure this is a valid public Serializd list."}))
            sys.exit(1)

        # Scroll to trigger lazy loading
        prev_count = 0
        for _ in range(20):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.2)
            count = page.eval_on_selector_all(".show-card-v2-container", "els => els.length")
            if count == prev_count:
                break
            prev_count = count

        cards = page.query_selector_all(".show-card-v2-container")
        shows = []
        for card in cards:
            title_el = card.query_selector(".card-title h3")
            img_el   = card.query_selector("img.card-img")
            title    = title_el.inner_text().strip() if title_el else None
            poster   = img_el.get_attribute("src")   if img_el   else None
            if not title:
                continue
            shows.append({"title": title, "poster": poster or ""})

        browser.close()
        return shows


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No URL provided"}))
        sys.exit(1)

    result = scrape(sys.argv[1])
    print(json.dumps(result))