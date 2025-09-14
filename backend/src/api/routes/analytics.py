"""Analytics API endpoints."""

from typing import Dict, Any, Optional, List
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...auth import get_current_active_user
from ...database import get_db
from ...models import User
from ...services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])
analytics_service = AnalyticsService()


class AnalyticsEvent(BaseModel):
    """Analytics event model."""
    event_type: str = Field(..., description="Type of event (e.g., 'user_action', 'system_event')")
    category: str = Field(..., description="Event category")
    action: str = Field(..., description="Specific action performed")
    label: Optional[str] = Field(None, description="Optional event label")
    value: Optional[float] = Field(None, description="Optional numeric value")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional event metadata")


class AnalyticsExportRequest(BaseModel):
    """Analytics export request model."""
    start_date: date = Field(..., description="Start date for export")
    end_date: date = Field(..., description="End date for export")
    event_types: Optional[List[str]] = Field(None, description="Filter by event types")
    format: str = Field("csv", description="Export format (csv, json)")
    include_metadata: bool = Field(False, description="Include metadata in export")


@router.get("/dashboard")
async def get_analytics_dashboard(
    start_date: Optional[date] = Query(None, description="Start date for analytics data"),
    end_date: Optional[date] = Query(None, description="End date for analytics data"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get analytics dashboard data for the current user.

    Args:
        start_date: Optional start date for filtering data
        end_date: Optional end date for filtering data
        current_user: Authenticated user
        db: Database session

    Returns:
        Dashboard analytics data including metrics and visualizations
    """
    try:
        # Set default date range if not provided (last 30 days)
        if not start_date or not end_date:
            from datetime import timedelta
            end_date = date.today()
            start_date = end_date - timedelta(days=30)

        dashboard_data = await analytics_service.get_user_dashboard(
            user_id=str(current_user.id),
            start_date=start_date,
            end_date=end_date
        )

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "metrics": dashboard_data["metrics"],
            "charts": dashboard_data["charts"],
            "insights": dashboard_data.get("insights", []),
            "last_updated": datetime.utcnow().isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard data: {str(e)}"
        )


@router.post("/events")
async def track_analytics_event(
    event: AnalyticsEvent,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Track a new analytics event.

    Args:
        event: Analytics event data
        current_user: Authenticated user
        db: Database session

    Returns:
        Event tracking confirmation
    """
    try:
        event_id = await analytics_service.track_event(
            user_id=str(current_user.id),
            event_type=event.event_type,
            category=event.category,
            action=event.action,
            label=event.label,
            value=event.value,
            metadata=event.metadata
        )

        return {
            "event_id": event_id,
            "tracked_at": datetime.utcnow().isoformat(),
            "success": True
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track event: {str(e)}"
        )


@router.get("/events")
async def get_analytics_events(
    limit: int = Query(100, le=1000, description="Maximum number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    start_date: Optional[date] = Query(None, description="Filter events from this date"),
    end_date: Optional[date] = Query(None, description="Filter events until this date"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get analytics events for the current user.

    Args:
        limit: Maximum number of events to return
        offset: Number of events to skip for pagination
        event_type: Filter by event type
        category: Filter by category
        start_date: Filter events from this date
        end_date: Filter events until this date
        current_user: Authenticated user
        db: Database session

    Returns:
        List of analytics events with pagination info
    """
    try:
        events_data = await analytics_service.get_user_events(
            user_id=str(current_user.id),
            limit=limit,
            offset=offset,
            event_type=event_type,
            category=category,
            start_date=start_date,
            end_date=end_date
        )

        return {
            "events": events_data["events"],
            "total": events_data["total"],
            "limit": limit,
            "offset": offset,
            "filters": {
                "event_type": event_type,
                "category": category,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch events: {str(e)}"
        )


@router.get("/usage")
async def get_usage_analytics(
    period: str = Query("month", description="Usage period: day, week, month, year"),
    metric: Optional[str] = Query(None, description="Specific metric to retrieve"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get usage analytics for the current user.

    Args:
        period: Time period for usage data
        metric: Specific metric to retrieve (optional)
        current_user: Authenticated user
        db: Database session

    Returns:
        Usage analytics data
    """
    try:
        if period not in ["day", "week", "month", "year"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Period must be one of: day, week, month, year"
            )

        usage_data = await analytics_service.get_usage_analytics(
            user_id=str(current_user.id),
            period=period,
            metric=metric
        )

        return {
            "period": period,
            "metric": metric,
            "usage_data": usage_data["usage"],
            "summary": usage_data["summary"],
            "trends": usage_data.get("trends", {}),
            "generated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch usage analytics: {str(e)}"
        )


@router.post("/export")
async def export_analytics_data(
    request: AnalyticsExportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Export analytics data for the current user.

    Args:
        request: Export request parameters
        background_tasks: Background task queue
        current_user: Authenticated user
        db: Database session

    Returns:
        Export job details and download information
    """
    try:
        # Validate date range
        if request.start_date > request.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date must be before end date"
            )

        # Validate format
        if request.format not in ["csv", "json"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Format must be 'csv' or 'json'"
            )

        # Start export job
        export_job = await analytics_service.export_analytics_data(
            user_id=str(current_user.id),
            start_date=request.start_date,
            end_date=request.end_date,
            event_types=request.event_types,
            format=request.format,
            include_metadata=request.include_metadata
        )

        # Add background task to process export
        background_tasks.add_task(
            analytics_service.process_export_job,
            export_job["job_id"]
        )

        return {
            "job_id": export_job["job_id"],
            "status": "processing",
            "estimated_completion": export_job.get("estimated_completion"),
            "download_url": export_job.get("download_url"),
            "expires_at": export_job.get("expires_at")
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start export job: {str(e)}"
        )