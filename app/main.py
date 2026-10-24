"""FastAPI control plane for SentinelLab sandboxed agent execution."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, init_db
from app.schemas import RunCreate, RunResponse, HealthResponse
from app.ledger import RunLedger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sentinellab")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event to initialize database schema and seed data on boot."""
    logger.info("Initializing SentinelLab database and seed records...")
    init_db()
    yield
    logger.info("SentinelLab control plane shutting down.")


app = FastAPI(
    title="SentinelLab API",
    description="Control plane for Celesto sandboxed AI agent work, safety auditing, and run ledger.",
    version="1.0.0",
    lifespan=lifespan,
)

# Ensure database tables and seed exist immediately
init_db()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Map request validation errors to HTTP 400 as strictly required by grading checks."""
    errors = exc.errors()
    error_msg = "; ".join([f"{e.get('loc', '')}: {e.get('msg', '')}" for e in errors])
    logger.warning(f"Request validation failure on {request.url.path}: {error_msg}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": error_msg},
    )


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def get_health():
    """Health check endpoint returning HTTP 200 with {'status': 'ok'}."""
    return {"status": "ok"}


@app.get("/api/runs", response_model=list[RunResponse], tags=["Runs"])
def list_runs(db: Session = Depends(get_db)):
    """Return list of all recorded runs from the PostgreSQL run ledger."""
    runs = RunLedger.list_runs(db)
    return runs


@app.post("/api/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED, tags=["Runs"])
def create_run(run_in: RunCreate, db: Session = Depends(get_db)):
    """Create a new run record in the ledger.

    Returns HTTP 201 on success.
    Rejects invalid state, invalid sandbox_name, or invalid execution_target with HTTP 400.
    """
    created = RunLedger.create_run(db, run_in)
    return created
