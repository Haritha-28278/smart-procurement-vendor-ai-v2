"""
Main FastAPI Application for Smart Procurement Vendor AI
Integrates Auth, Vendor Registry, RFQ Management, Quotes, and Claude AI Analysis.
Mounts Frontend static assets for seamless single-server operation and testing.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

load_dotenv()

from backend.db.connection import init_db
from backend.routes.auth import router as auth_router
from backend.routes.vendors import router as vendors_router
from backend.routes.rfq import router as rfq_router
from backend.routes.quotes import router as quotes_router
from backend.routes.ai_analysis import router as ai_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema & seed on startup if needed
    print("[Startup] Initializing Database & Seed Data...")
    try:
        init_db(force=False)
        print("[Startup] Database ready.")
    except Exception as e:
        print(f"[Startup] Warning during DB initialization: {e}")
    yield
    print("[Shutdown] Cleaning up resources.")


app = FastAPI(
    title="Smart Procurement Vendor AI",
    description="Intelligent AI-powered procurement assistant for vendor discovery, RFQ evaluation, and negotiation.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local development and cross-origin fetch
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth_router)
app.include_router(vendors_router)
app.include_router(rfq_router)
app.include_router(quotes_router)
app.include_router(ai_router)

# Mount frontend directory for direct browser viewing
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

if os.path.exists(FRONTEND_DIR):
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    # Also mount subfolders directly for easy relative path resolution
    app.mount("/pages", StaticFiles(directory=os.path.join(FRONTEND_DIR, "pages"), html=True), name="pages")
    app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")


@app.get("/")
def root():
    """Redirect root path to login page."""
    return RedirectResponse(url="/pages/login.html")


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": "Smart Procurement Vendor AI",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"Starting Smart Procurement Vendor AI on http://localhost:{port}")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
