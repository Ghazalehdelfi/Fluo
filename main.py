"""
Language Learning App — slim application entry point.

IMPORTANT: aws_config.load_secrets() MUST be called before any other
imports that read environment variables (e.g. routers that set
stripe.api_key at module level).
"""

import asyncio
import os
from contextlib import asynccontextmanager

from aws_config import load_secrets

load_secrets()

# --- All other imports happen AFTER secrets are loaded ---

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from database import init_db
from agents.logging_utils import setup_logging, get_logger, print_startup_banner
from rate_limiter import limiter, user_limiter
from session_store import purge_expired_sessions

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


async def _session_cleanup_loop() -> None:
    """Background task: purge expired in-memory sessions every 10 minutes."""
    while True:
        await asyncio.sleep(600)
        purged = purge_expired_sessions()
        if purged:
            logger.info(f"Session cleanup: purged {purged} expired session(s).")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(_session_cleanup_loop())
    yield
    task.cancel()
    # Flush any pending Langfuse events before the process exits
    from cost_tracker import _get_langfuse
    lf = _get_langfuse()
    if lf:
        try:
            lf.flush()
        except Exception:
            pass


app = FastAPI(title="Language Learning App", lifespan=lifespan)

# ── Rate limiting ─────────────────────────────────────────────────
app.state.limiter = limiter
app.state.user_limiter = user_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

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


@app.get("/healthz", include_in_schema=False)
async def healthz():
    """Container health check — returns 200 when the process is alive."""
    return JSONResponse({"status": "ok"})


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
