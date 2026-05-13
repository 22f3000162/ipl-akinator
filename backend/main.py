"""
main.py — FastAPI application entry point.

Run locally:
  uvicorn backend.main:app --reload --port 8000

Or with venv:
  venv/bin/uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import game, feedback

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Startup / shutdown
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🏏 IPL Akinator API starting up...")
    logger.info("GEMINI_API_KEY set: %s", bool(os.getenv("GEMINI_API_KEY")))
    logger.info("GOOGLE_APPLICATION_CREDENTIALS: %s", os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "not set"))
    yield
    logger.info("IPL Akinator API shutting down.")


# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="IPL Akinator API",
    description=(
        "AI-powered IPL player guessing system. "
        "Hybrid Bayesian reasoning engine + Gemini language models."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for hackathon; tighten for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(game.router)
app.include_router(feedback.router)


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "firebase_configured": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
    }


@app.get("/")
async def root():
    return {
        "message": "IPL Akinator API",
        "docs": "/docs",
        "health": "/health",
    }
