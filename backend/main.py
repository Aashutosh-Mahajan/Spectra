"""
FastAPI application entry point.
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.api.routes import audit, report

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    storage_path = os.environ.get("JOB_STORAGE_PATH", "./storage/jobs")
    os.makedirs(storage_path, exist_ok=True)
    logger.info(f"Storage directory ready: {storage_path}")
    logger.info("Codebase Audit Agent System — Backend started")
    yield
    # Shutdown
    logger.info("Codebase Audit Agent System — Backend shutting down")


# Create FastAPI app
app = FastAPI(
    title="Codebase Audit Agent System",
    description="Multi-agent AI pipeline that audits GitHub repositories and generates structured reports",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware — allow Streamlit frontend to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to Streamlit origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(audit.router, tags=["Audit"])
app.include_router(report.router, tags=["Report"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Codebase Audit Agent System",
        "version": "1.0.0",
    }
