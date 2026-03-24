import asyncio
import json
import sys
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI()

# Enable CORS so the browser allows the connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScrapeRequest(BaseModel):
    url: str

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    # Paths are relative to this file's location
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/scrape")
async def scrape(req: ScrapeRequest):
    url = req.url.strip()
    # Locate the scraper.py script in the same folder
    scraper_script = os.path.join(os.path.dirname(__file__), "scraper.py")
    
    try:
        # This mimics you typing "python scraper.py <url>" in the terminal
        process = await asyncio.create_subprocess_exec(
            sys.executable, scraper_script, url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            raise HTTPException(status_code=500, detail=f"Scraper Error: {error_msg}")

        # Capture the JSON string printed by scraper.py
        output = stdout.decode().strip()
        
        # In case scraper.py outputs an error dictionary instead of a list
        data = json.loads(output)
        if isinstance(data, dict) and "error" in data:
            raise HTTPException(status_code=400, detail=data["error"])

        # Return exactly what your index.html expects
        return JSONResponse({"count": len(data), "shows": data})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backend failed: {str(e)}")

if __name__ == "__main__":
    # Use 127.0.0.1 to prevent the ERR_ADDRESS_INVALID browser error
    uvicorn.run(app, host="127.0.0.1", port=8000)