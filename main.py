import asyncio
import json
import sys
import os
import traceback
import requests as req_lib
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn
from scraper import LANGUAGE_NAMES

load_dotenv()

TMDB_KEY = os.environ.get("TMDB_API_KEY", "")

app = FastAPI()
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    url: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def minutes_to_dhm(total_minutes: int) -> dict:
    days    = total_minutes // (60 * 24)
    hours   = (total_minutes % (60 * 24)) // 60
    minutes = total_minutes % 60
    return {"days": days, "hours": hours, "minutes": minutes}


def normalize_url(url: str) -> str:
    """Convert short srlzd.com links to full serializd.com URLs."""
    import re
    match = re.match(r'^https?://srlzd\.com/l/([a-zA-Z0-9]+)', url)
    if match:
        return f"https://www.serializd.com/list/{match.group(1)}?isHexId=true"
    return url


def generate_insight(shows: list) -> str:
    genres    = Counter()
    countries = Counter()
    languages = Counter()
    ratings   = []
    years     = []

    for s in shows:
        for g in (s.get("genres") or "").split(", "):
            if g.strip():
                genres[g.strip()] += 1
        for c in (s.get("country") or "").split(", "):
            if c.strip():
                countries[c.strip()] += 1
        lang = s.get("original_language", "").strip()
        if lang:
            languages[lang] += 1
        if s.get("tmdb_rating"):
            try:
                ratings.append(float(s["tmdb_rating"]))
            except (ValueError, TypeError):
                pass
        if s.get("year"):
            try:
                years.append(int(s["year"]))
            except (ValueError, TypeError):
                pass

    parts = []

    # Genres
    if genres:
        top_genres = [g for g, _ in genres.most_common(3)]
        parts.append(f"Your list leans into {', '.join(top_genres)}")

    # Countries
    if countries:
        top_countries = [c for c, _ in countries.most_common(2)]
        label = " and ".join(top_countries)
        parts.append(f"with a taste for {label} productions")

    # Non-English languages
    non_english = [(l, n) for l, n in languages.most_common() if l.lower() != "english"]
    if non_english:
        top_lang = non_english[0][0]
        parts.append(f"including a fondness for {top_lang}-language content")

    # Average TMDB rating
    if ratings:
        avg = round(sum(ratings) / len(ratings), 1)
        if avg >= 8.0:
            parts.append(f"and you clearly have high standards (avg rating: {avg})")
        elif avg >= 7.0:
            parts.append(f"with a solid average rating of {avg}")

    # Era
    if years:
        avg_year = int(sum(years) / len(years))
        if avg_year >= 2020:
            parts.append("You mostly watch recent releases")
        elif avg_year <= 2010:
            parts.append("You appreciate older classics too")

    if not parts:
        return ""

    sentence = ". ".join(parts) + "."
    return sentence[0].upper() + sentence[1:]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@app.post("/scrape")
async def scrape(req: ScrapeRequest):
    url = normalize_url(req.url.strip())
    if "serializd.com" not in url:
        raise HTTPException(status_code=400, detail="Please provide a valid Serializd URL.")

    scraper_script = os.path.join(os.path.dirname(__file__), "scraper.py")
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, scraper_script, url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=600.0)

        stderr_text = stderr.decode().strip()
        if stderr_text:
            print("SCRAPER STDERR:", stderr_text, flush=True)

        if process.returncode != 0:
            print("SCRAPER FAILED with code:", process.returncode, flush=True)
            raise HTTPException(status_code=500, detail=f"Scraper error: {stderr_text}")

        data = json.loads(stdout.decode().strip())
        if isinstance(data, dict) and "error" in data:
            raise HTTPException(status_code=400, detail=data["error"])

        total_min = sum(s.get("runtime_minutes", 0) for s in data)
        return JSONResponse({
            "count": len(data),
            "shows": data,
            "total_runtime": minutes_to_dhm(total_min),
        })

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Request timed out.")
    except HTTPException:
        raise
    except Exception as e:
        print("UNEXPECTED ERROR:", traceback.format_exc(), flush=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


def fetch_full_details(tmdb_id: str):
    """Fetch all metadata for a specific TV show by ID."""
    if not TMDB_KEY: return {}
    try:
        detail = req_lib.get(
            f"https://api.themoviedb.org/3/tv/{tmdb_id}",
            params={"language": "en-US", "api_key": TMDB_KEY},
            timeout=8,
        ).json()

        n_episodes  = detail.get("number_of_episodes", 0)
        n_seasons   = detail.get("number_of_seasons", 0)
        runtimes    = detail.get("episode_run_time", [])
        avg_runtime = runtimes[0] if runtimes else 0

        # Optional: very detailed runtime fetch if avg is 0 but we have episodes
        if not avg_runtime and n_episodes > 0:
            try:
                ep = req_lib.get(
                    f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/1/episode/1",
                    params={"language": "en-US", "api_key": TMDB_KEY},
                    timeout=5,
                ).json()
                avg_runtime = ep.get("runtime") or 0
            except: pass

        lang_code = detail.get("original_language", "").lower()
        lang_name = LANGUAGE_NAMES.get(lang_code, lang_code.upper())

        return {
            "runtime_minutes":   n_episodes * avg_runtime,
            "seasons":           n_seasons,
            "episodes":          n_episodes,
            "genres":            ", ".join(g["name"] for g in detail.get("genres", [])),
            "country":           ", ".join(detail.get("origin_country", [])),
            "network":           detail["networks"][0]["name"] if detail.get("networks") else "",
            "original_language": lang_name,
        }
    except Exception:
        return {}


@app.post("/recommend")
async def recommend(payload: dict):
    shows = payload.get("shows", [])
    if not shows:
        raise HTTPException(status_code=400, detail="No shows provided.")
    if not TMDB_KEY:
        raise HTTPException(status_code=400, detail="TMDB API key not configured.")

    existing_ids = {str(s.get("tmdb_id")) for s in shows if s.get("tmdb_id")}

    score_map   = defaultdict(int)   # tmdb_id → how many list-shows recommend it
    details_map = {}                 # tmdb_id → show metadata

    def fetch_recs(show):
        tid = show.get("tmdb_id")
        if not tid:
            return
        try:
            r = req_lib.get(
                f"https://api.themoviedb.org/3/tv/{tid}/recommendations",
                params={"api_key": TMDB_KEY, "language": "en-US", "page": 1},
                timeout=8,
            ).json()
            for item in r.get("results", []):
                iid = str(item["id"])
                if iid in existing_ids:
                    continue
                score_map[iid] += 1
                if iid not in details_map:
                    details_map[iid] = {
                        "tmdb_id":     iid,
                        "title":       item.get("name", ""),
                        "year":        (item.get("first_air_date") or "")[:4],
                        "tmdb_rating": round(item.get("vote_average", 0), 1) or "",
                        "poster": (
                            f"https://image.tmdb.org/t/p/w300{item['poster_path']}"
                            if item.get("poster_path") else ""
                        ),
                        "overview":    item.get("overview", ""),
                    }
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(fetch_recs, shows))

    # Sort by score (how many shows in the list recommend this), take top 20
    top = sorted(
        details_map.values(),
        key=lambda x: score_map[x["tmdb_id"]],
        reverse=True,
    )[:20]

    for item in top:
        item["score"] = score_map[item["tmdb_id"]]

    # Now fetch full details for these top results
    def enrich_rec(item):
        extra = fetch_full_details(item["tmdb_id"])
        item.update(extra)

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(enrich_rec, top))

    insight = generate_insight(shows)

    return JSONResponse({"recommendations": top, "insight": insight})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)