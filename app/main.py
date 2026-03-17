"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import gateway, logs, settings, templates, webhook
from app.routers.templates import seed_default_templates
from app.services.scheduler import start_scheduler, stop_scheduler
from app.utils.logger import get_logger

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await seed_default_templates()
    start_scheduler()
    await logger.info("Application started")
    yield
    # Shutdown
    stop_scheduler()
    await logger.info("Application stopped")


app = FastAPI(
    title="kwtSMS Ecwid Plugin",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: allow all origins (required for Ecwid iframe embedding)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Routers
app.include_router(webhook.router, prefix="/webhook")
app.include_router(settings.router, prefix="/api/settings")
app.include_router(templates.router, prefix="/api/templates")
app.include_router(logs.router, prefix="/api/logs")
app.include_router(gateway.router, prefix="/api/gateway")


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/iframe")
async def iframe_page():
    index_path = static_dir / "iframe" / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return JSONResponse(status_code=404, content={"error": "Iframe page not found"})
