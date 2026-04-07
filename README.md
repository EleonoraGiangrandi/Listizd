---
title: Listizd
emoji: 📺
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Listizd

This **vibe coded** project lets you extract and export any public [Serializd](https://www.serializd.com) list in seconds. Paste a URL and get every show with titles, posters, TMDB metadata, and total watch time.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Hugging%20Face-yellow?logo=huggingface)](https://huggingface.co/spaces/Eleonora705/Listizd)

---
## 📸 Screenshots

![Listizd homepage](assets/screenshots/hero.png)

<p align="center">
  <img src="assets/screenshots/display.png" width="48%" alt="Display of all shows" />
  <img src="assets/screenshots/modal.png" width="48%" alt="Show detail modal" />
</p>
---

## Features

- 🔗 **Paste any public Serializd list URL** and scrape it automatically
- 🖼️ **Poster grid view** with lazy-loaded images and smooth animations
- ⏱️ **Total watch time** calculated across your entire list
- 📊 **Rich metadata per show** — year, TMDB rating, seasons, episodes, genres, country, network
- 📋 **Export as text** — numbered list copied straight to clipboard
- 📁 **Export as CSV** — full metadata spreadsheet, ready for Notion, Excel, or Sheets
- 🌗 **Dark / light theme** toggle with localStorage persistence
- ⚡ **Parallel TMDB enrichment** — up to 8 concurrent API calls via `ThreadPoolExecutor`

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vanilla HTML/CSS/JS + Tailwind CDN |
| Backend | FastAPI + Uvicorn |
| Scraping | Playwright (Chromium, headless) |
| Enrichment | TMDB REST API |
| E2E Tests | Playwright Test (TypeScript) |
| CI | GitHub Actions |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ *(for Playwright tests only)*
- A free [TMDB API key](https://www.themoviedb.org/settings/api)

### 1. Clone the repo

```bash
git clone https://github.com/EleonoraGiangrandi/Listizd.git
cd listizd
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Playwright browsers

```bash
playwright install chromium
```

### 4. Set up your environment

Create a `.env` file in the root directory:

```env
TMDB_API_KEY=your_tmdb_api_key_here
```

### 5. Run the app

```bash
python main.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## ⚙️ How It Works

1. The user pastes a Serializd list URL into the frontend.
2. The frontend POSTs it to the `/scrape` FastAPI endpoint.
3. The backend spawns `scraper.py` as a subprocess (isolated from uvicorn's event loop).
4. Playwright launches a headless Chromium browser, navigates to the list, and scrolls to trigger lazy loading.
5. All show titles, posters, and Serializd URLs are extracted from `.show-card-v2-container` elements.
6. Up to 8 TMDB API calls run in parallel to enrich each show with metadata and calculate runtime.
7. The enriched JSON is returned to the frontend, which renders the grid and totals.

---

## 🔑 TMDB API

This project uses the [<img src="https://www.themoviedb.org/assets/2/v4/logos/v2/blue_short-8e7b30f73a4020692ccca9c88bafe5dcb6f8a62a4c6bc55cd9ba82bb2cd95f6c.svg" width="100" /> API](https://developer.themoviedb.org/docs) for show metadata. You'll need to register for a free API key. The app degrades gracefully if no key is provided — it will still show titles and posters, just without the enriched metadata or runtime calculations.

---

## ⚠️ Disclaimer

This tool is not affiliated with, endorsed by, or connected to Serializd in any way. It only works with **public** lists. Please be respectful of rate limits and don't use this to hammer Serializd's servers.
