"""Configuration management for SentinelLab control plane."""

import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Base project paths
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)
REPORTS_DIR = BASE_DIR / "reports"
EVIDENCE_DIR = REPORTS_DIR / "evidence"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseModel):
    # Base paths
    base_dir: Path = BASE_DIR
    reports_dir: Path = REPORTS_DIR
    evidence_dir: Path = EVIDENCE_DIR
    logs_dir: Path = LOGS_DIR

    # Celesto Provider
    celesto_provider: str = Field(
        default_factory=lambda: os.getenv("CELESTO_PROVIDER", "cloud")
    )
    celesto_api_key: str = Field(
        default_factory=lambda: os.getenv("CELESTO_API_KEY", "")
    )
    celesto_backend: str = Field(
        default_factory=lambda: os.getenv("CELESTO_BACKEND", "firecracker")
    )

    # LLM Configuration
    llm_base_url: str = Field(
        default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    )
    llm_api_key: str = Field(
        default_factory=lambda: os.getenv("LLM_API_KEY", "")
    )
    llm_model: str = Field(
        default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini")
    )

    # Database Configuration
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "sqlite:///./sentinel_ledger.db",
        )
    )

    # API Configuration
    api_port: int = Field(
        default_factory=lambda: int(os.getenv("API_PORT", "8080"))
    )
    app_env: str = Field(
        default_factory=lambda: os.getenv("APP_ENV", "development")
    )

    # Audit & report file paths
    commands_log_path: Path = LOGS_DIR / "commands.jsonl"
    failure_trace_path: Path = REPORTS_DIR / "failure_trace.jsonl"


settings = Settings()
