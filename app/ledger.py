"""Run ledger service for recording sandbox executions in PostgreSQL."""

import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from app.models import RunModel
from app.schemas import RunCreate

logger = logging.getLogger(__name__)


class RunLedger:
    @staticmethod
    def list_runs(db: Session) -> list[dict]:
        """Return all recorded runs from the ledger."""
        runs = db.query(RunModel).order_by(RunModel.created_at.asc()).all()
        return [run.to_dict() for run in runs]

    @staticmethod
    def get_run(db: Session, run_id: str) -> dict | None:
        """Return a single run record by ID."""
        run = db.query(RunModel).filter(RunModel.run_id == run_id).first()
        return run.to_dict() if run else None

    @staticmethod
    def create_run(db: Session, run_in: RunCreate) -> dict:
        """Create a new run record in the ledger."""
        existing = db.query(RunModel).filter(RunModel.run_id == run_in.run_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Run with id '{run_in.run_id}' already exists.",
            )

        run_model = RunModel(
            run_id=run_in.run_id,
            sandbox_name=run_in.sandbox_name,
            problem_id=run_in.problem_id,
            state=run_in.state,
            execution_target=run_in.execution_target,
        )

        try:
            db.add(run_model)
            db.commit()
            db.refresh(run_model)
            return run_model.to_dict()
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error recording run {run_in.run_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Database constraint error: {str(e)}",
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error recording run {run_in.run_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to record run: {str(e)}",
            )

    @staticmethod
    def update_state(db: Session, run_id: str, new_state: str) -> dict | None:
        """Update the lifecycle state of a run."""
        run = db.query(RunModel).filter(RunModel.run_id == run_id).first()
        if not run:
            return None
        run.state = new_state
        db.commit()
        db.refresh(run)
        return run.to_dict()
