import sys
import json
import time
import os
import requests
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()
TMDB_KEY = os.environ.get("TMDB_API_KEY", "")

LANGUAGE_NAMES = {
    "en": "English", "it": "Italian", "ja": "Japanese", "ko": "Korean",
    "fr": "French", "de": "German", "es": "Spanish", "pt": "Portuguese",
    "zh": "Chinese", "ru": "Russian", "ar": "Arabic", "hi": "Hindi",
    "tr": "Turkish", "sv": "Swedish", "da": "Danish", "nl": "Dutch",
    "pl": "Polish", "fi": "Finnish", "no": "Norwegian", "th": "Thai",
}

def get_show_info(title: str) -> dict:
    """Fetch enriched data from TMDB."""
    result = {
        "tmdb_id": "",           # ← stored so /recommend can use it
        "runtime_minutes": 0,
        "year": "",
        "tmdb_rating": "",
        "seasons": "",
        "episodes": "",
        "genres": "",
        "country": "",
        "network": "",
        "original_language": "",
    }
    if not TMDB_KEY:
        return result

    try:
        search = requests.get(
            "https://api.themoviedb.org/3/search/tv",
            params={"query": title, "language": "en-US", "page": 1, "api_key": TMDB_KEY},
            timeout=8,
        ).json()

        results = search.get("results", [])
        if not results:
            return result

        show_id = results[0]["id"]
        detail = requests.get(
            f"https://api.themoviedb.org/3/tv/{show_id}",
            params={"language": "en-US", "api_key": TMDB_KEY},
            timeout=8,
        ).json()

        n_episodes  = detail.get("number_of_episodes", 0)
        n_seasons   = detail.get("number_of_seasons", 0)
        runtimes    = detail.get("episode_run_time", [])
        avg_runtime = runtimes[0] if runtimes else 0

        if not avg_runtime and n_episodes > 0:
            ep = requests.get(
                f"https://api.themoviedb.org/3/tv/{show_id}/season/1/episode/1",
                params={"language": "en-US", "api_key": TMDB_KEY},
                timeout=8,
            ).json()
            avg_runtime = ep.get("runtime") or 0

        first_air_date = detail.get("first_air_date", "")
        tmdb_rating    = detail.get("vote_average", "")

        result.update({
            "tmdb_id":           str(show_id),   # ← saved here
            "runtime_minutes":   n_episodes * avg_runtime,
            "year":              first_air_date[:4] if first_air_date else "",
            "tmdb_rating":       round(float(tmdb_rating), 1) if tmdb_rating else "",
            "seasons":           n_seasons,
            "episodes":          n_episodes,
            "genres":            ", ".join(g["name"] for g in detail.get("genres", [])),
            "country":           ", ".join(detail.get("origin_country", [])),
            "network":           detail["networks"][0]["name"] if detail.get("networks") else "",
            "original_language": LANGUAGE_NAMES.get(
                detail.get("original_language", ""),
                detail.get("original_language", "").upper()
            ),
        })
    except Exception:
        pass

    return result


def enrich(show: dict) -> dict:
    info = get_show_info(show["title"])
    return {**show, **info}


def extract_cards_from_page(page):
    found = []
    cards = page.query_selector_all(".show-card-v2-container")
    for card in cards:
        title_el = card.query_selector(".card-title h3")
        if title_el:
            title   = title_el.inner_text().strip()
            img_el  = card.query_selector("img.card-img")
            poster  = img_el.get_attribute("src") if img_el else ""
            href    = card.evaluate("el => el.closest('a')?.getAttribute('href') ?? ''")
            found.append({
                "title":         title,
                "poster":        poster,
                "serializd_url": "https://www.serializd.com" + href if href else "",
            })
    return found


def scrape(url: str) -> list[dict]:
    all_raw_shows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_selector(".show-card-v2-container", timeout=20000)

        has_see_more   = page.query_selector("button:has-text('See more')")
        has_pagination = page.query_selector(".pagination-item")

        if has_see_more:
            while True:
                see_more_btn = page.query_selector("button:has-text('See more')")
                if see_more_btn and see_more_btn.is_visible():
                    see_more_btn.click()
                    time.sleep(2)
                else:
                    break
            all_raw_shows = extract_cards_from_page(page)

        elif has_pagination:
            while True:
                all_raw_shows.extend(extract_cards_from_page(page))
                next_page = page.query_selector(".pagination-item-selected + .pagination-item")
                if next_page:
                    next_page.click()
                    time.sleep(2.5)
                else:
                    break
        else:
            all_raw_shows = extract_cards_from_page(page)

        browser.close()

    unique_dict  = {s["serializd_url"] or s["title"]: s for s in all_raw_shows}
    unique_shows = list(unique_dict.values())

    with ThreadPoolExecutor(max_workers=8) as executor:
        shows = list(executor.map(enrich, unique_shows))

    return shows


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No URL provided"}))
        sys.exit(1)

    try:
        result = scrape(sys.argv[1])
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)