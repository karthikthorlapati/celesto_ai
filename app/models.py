"""SQLAlchemy database models for SentinelLab run ledger."""

from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from app.database import Base


class RunModel(Base):
    __tablename__ = "runs"

    run_id = Column(String(128), primary_key=True, index=True)
    sandbox_name = Column(String(128), nullable=False, index=True)
    problem_id = Column(String(128), nullable=False)
    state = Column(String(32), nullable=False)
    execution_target = Column(String(64), nullable=False, default="celesto_sandbox")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "sandbox_name": self.sandbox_name,
            "problem_id": self.problem_id,
            "state": self.state,
            "execution_target": self.execution_target,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
