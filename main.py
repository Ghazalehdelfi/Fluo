"""
Language Learning App — slim application entry point.

IMPORTANT: aws_config.load_secrets() MUST be called before any other
imports that read environment variables (e.g. routers that set
stripe.api_key at module level).
"""

import os

from aws_config import load_secrets

load_secrets()

# --- All other imports happen AFTER secrets are loaded ---

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from database import init_db
from agents.logging_utils import setup_logging, get_logger, print_startup_banner

from routers import (
    auth,
    users,
    languages,
    upload,
    vocabulary,
    practice,
    conversations,
    history,
    placement,
    billing,
    classes,
)

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="Language Learning App")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for _router_module in [
    auth,
    users,
    languages,
    upload,
    vocabulary,
    practice,
    conversations,
    history,
    placement,
    billing,
    classes,
]:
    app.include_router(_router_module.router)

init_db()

# Mount static asset directories BEFORE the SPA catch-all so Vite-built
# assets (/assets/...) are served with correct MIME types.
os.makedirs("static/assets", exist_ok=True)
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the frontend HTML."""
    with open("static/index.html", "r") as f:
        return f.read()


@app.get("/favicon.svg")
async def serve_favicon():
    return FileResponse("static/favicon.svg", media_type="image/svg+xml")


@app.get("/iran.png")
async def serve_iran_flag():
    return FileResponse("static/iran.png", media_type="image/png")


@app.get("/{path:path}", response_class=HTMLResponse)
async def serve_spa(path: str):
    """Serve the frontend for any non-API route (SPA routing)."""
    if (
        path.startswith("api/")
        or path.startswith("static/")
        or path.startswith("assets/")
    ):
        raise HTTPException(status_code=404, detail="Not found")
    with open("static/index.html", "r") as f:
        return f.read()


if __name__ == "__main__":
    import uvicorn

    print_startup_banner()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
