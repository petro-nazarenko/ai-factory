"""FastAPI route handlers — control plane for the swarm."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class CycleRequest(BaseModel):
    sources: list[str] | None = None
    limit: int = 40


class CycleResponse(BaseModel):
    task_id: str
    status: str = "queued"


class ConversionEvent(BaseModel):
    tracking_id: str
    event_type: str        # click | signup | payment | reply
    platform: str
    value: float = 0.0
    metadata: dict = {}


class WeightResponse(BaseModel):
    feature: str
    weight: float


# ---------------------------------------------------------------------------
# Cycle control
# ---------------------------------------------------------------------------

@router.post("/cycles/start", response_model=CycleResponse, tags=["cycles"])
async def start_cycle(req: CycleRequest) -> CycleResponse:
    """Launch a full mine → generate → score → build → deploy → distribute pipeline."""
    from workers.tasks import run_cycle

    result = run_cycle(sources=req.sources, limit=req.limit)
    return CycleResponse(task_id=str(result.id))


@router.get("/cycles/{task_id}", tags=["cycles"])
async def get_cycle_status(task_id: str) -> dict:
    """Poll the status of a running pipeline chain."""
    from celery.result import AsyncResult
    from workers.celery_app import app

    result = AsyncResult(task_id, app=app)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }


# ---------------------------------------------------------------------------
# Conversion webhook
# ---------------------------------------------------------------------------

@router.post("/conversions", tags=["conversions"])
async def record_conversion(event: ConversionEvent) -> dict:
    """Record a conversion event (from Stripe webhook, analytics pixel, etc.).

    Triggers weight update if event_type == 'payment'.
    """
    from infra.db import get_session
    from core.schema import MetricRecord, IdeaRecord
    from sqlalchemy import select

    async with get_session() as session:
        # Find idea by tracking_id
        row = await session.execute(
            select(IdeaRecord)
            .join(MetricRecord, MetricRecord.idea_id == IdeaRecord.id, isouter=True)
            .where(MetricRecord.tracking_id == event.tracking_id)
            .limit(1)
        )
        idea = row.scalar_one_or_none()

        # Upsert metric row
        metric_row = await session.execute(
            select(MetricRecord).where(MetricRecord.tracking_id == event.tracking_id).limit(1)
        )
        metric = metric_row.scalar_one_or_none()
        if metric is None:
            metric = MetricRecord(
                idea_id=idea.id if idea else 0,
                tracking_id=event.tracking_id,
            )
            session.add(metric)

        if event.event_type == "click":
            metric.clicks += 1
        elif event.event_type == "signup":
            metric.signups += 1
        elif event.event_type == "payment":
            metric.payments += 1
            metric.revenue += event.value
        elif event.event_type == "reply":
            pass  # tracked but not aggregated here

        await session.commit()

    # Trigger weight update on payment
    if event.event_type == "payment" and idea:
        from workers.tasks import update_weights_task

        update_weights_task.delay(
            idea_id=idea.id,
            metrics={
                "payments": 1,
                "mrr": event.value,
                "signups": 0,
                "time_to_first_payment": 0,
            },
        )

    return {"ok": True, "tracking_id": event.tracking_id, "event_type": event.event_type}


# ---------------------------------------------------------------------------
# Weights / learning state
# ---------------------------------------------------------------------------

@router.get("/weights", response_model=list[WeightResponse], tags=["learning"])
async def get_weights() -> list[WeightResponse]:
    """Return current feature weights used by the scoring agent."""
    from infra.db import get_session
    from core.schema import WeightRecord
    from sqlalchemy import select

    async with get_session() as session:
        rows = await session.execute(select(WeightRecord).order_by(WeightRecord.weight.desc()))
        return [WeightResponse(feature=r.feature, weight=r.weight) for r in rows.scalars()]


# ---------------------------------------------------------------------------
# Ideas history
# ---------------------------------------------------------------------------

@router.get("/ideas", tags=["ideas"])
async def list_ideas(limit: int = 50, passed_only: bool = False) -> list[dict]:
    """Return recent ideas with their filter outcomes and metrics."""
    from infra.db import get_session
    from core.schema import IdeaRecord
    from sqlalchemy import select

    async with get_session() as session:
        q = select(IdeaRecord).order_by(IdeaRecord.created_at.desc()).limit(limit)
        if passed_only:
            q = q.where(IdeaRecord.passed == 1)
        rows = await session.execute(q)
        return [
            {
                "id": r.id,
                "run_id": r.run_id,
                "source": r.source,
                "problem": r.problem,
                "passed": bool(r.passed),
                "score": r.score,
                "reject_reason": r.reject_reason,
                "mvp_format": r.mvp_format,
                "deployed_url": r.deployed_url,
            }
            for r in rows.scalars()
        ]
