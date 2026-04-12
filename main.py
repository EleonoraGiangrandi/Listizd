import asyncio
import json
import sys
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

app = FastAPI()
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class ScrapeRequest(BaseModel):
    url: str

def minutes_to_dhm(total_minutes: int) -> dict:
    days = total_minutes // (60 * 24)
    hours = (total_minutes % (60 * 24)) // 60
    minutes = total_minutes % 60
    return {"days": days, "hours": hours, "minutes": minutes}

#Convert short app links to full serializd.com URLs
def normalize_url(url: str) -> str:
    import re
    match = re.match(r'^https?://srlzd\.com/l/([a-zA-Z0-9]+)', url)
    if match:
        return f"https://www.serializd.com/list/{match.group(1)}?isHexId=true"
    return url

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/scrape")
async def scrape(req: ScrapeRequest):
    url = normalize_url(req.url.strip())
    if "serializd.com" not in url:
        raise HTTPException(status_code=400, detail="Fornire un URL Serializd valido.")

    scraper_script = os.path.join(os.path.dirname(__file__), "scraper.py")
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, scraper_script, url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=600.0)

        stderr_text = stderr.decode().strip()
        if stderr_text:
            print("SCRAPER STDERR:", stderr_text, flush=True) 

        if process.returncode != 0:
            print("SCRAPER FAILED with code:", process.returncode, flush=True)  
            raise HTTPException(status_code=500, detail=f"Scraper Error: {stderr_text}")

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
        raise HTTPException(status_code=504, detail="Timeout.")
    except HTTPException:
        raise
    except Exception as e:
        print("UNEXPECTED ERROR:", traceback.format_exc(), flush=True)
        raise HTTPException(status_code=500, detail=f"Errore: {str(e)}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)