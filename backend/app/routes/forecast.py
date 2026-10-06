"""Predictive Research Intelligence & Forecasting Router.

Exposes:
- GET /api/forecast/overview: Macro outlook, emerging frontiers, declining areas, breakout researchers.
- GET /api/forecast/topic/{topic_id}: Granular 5-signal forecast for a single research field.
- GET /api/forecast/breakout-researchers: Rising high-velocity researchers in high-opportunity areas.
"""
from fastapi import APIRouter, HTTPException, Path, Query
from ..schemas.models import (
    ForecastOverviewResponse, TopicForecast, BreakoutResearcher
)
from ..services.forecasting_service import (
    get_forecast_overview, get_topic_forecast_detail, get_breakout_researchers
)

router = APIRouter(prefix='/api/forecast', tags=['Research Forecasting'])


@router.get('/overview', response_model=ForecastOverviewResponse)
def forecast_overview():
    """Retrieve 3-year predictive forecast across computer science disciplines."""
    return get_forecast_overview()


@router.get('/topic/{topic_id}', response_model=TopicForecast)
def topic_forecast(topic_id: int = Path(ge=1)):
    """Retrieve 5-signal predictive forecast for a specific research area."""
    data = get_topic_forecast_detail(topic_id)
    if not data:
        raise HTTPException(404, f"Topic {topic_id} not found or forecasting signals unavailable.")
    return data


@router.get('/breakout-researchers', response_model=list[BreakoutResearcher])
def breakout_researchers(limit: int = Query(10, ge=1, le=50)):
    """Discover rising scholars with rapidest career acceleration in high-opportunity domains."""
    return get_breakout_researchers(limit=limit)

