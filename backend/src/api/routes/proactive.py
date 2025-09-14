"""Proactive suggestions and personalization API endpoints."""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...auth import get_current_active_user
from ...database import get_db
from ...models import User
from ...services.proactive_service import ProactiveService
from ...services.personalization_service import PersonalizationService

# Create separate routers for different endpoint groups
proactive_router = APIRouter(prefix="/proactive", tags=["proactive"])
personalization_router = APIRouter(prefix="/personalization", tags=["personalization"])

# Service instances
proactive_service = ProactiveService()
personalization_service = PersonalizationService()


# Pydantic models
class ProactiveSuggestionRequest(BaseModel):
    """Request model for creating a proactive suggestion."""
    suggestion_type: str = Field(..., description="Type of suggestion")
    title: str = Field(..., description="Suggestion title")
    description: str = Field(..., description="Suggestion description")
    action_data: Optional[Dict[str, Any]] = Field(None, description="Action-specific data")
    priority: int = Field(1, ge=1, le=5, description="Suggestion priority (1-5)")
    expires_at: Optional[str] = Field(None, description="Expiration timestamp (ISO format)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class SuggestionResponseRequest(BaseModel):
    """Request model for responding to a suggestion."""
    action: str = Field(..., description="Response action: accept, dismiss, postpone")
    feedback: Optional[str] = Field(None, description="Optional feedback text")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional response metadata")


class PersonalizationProfileUpdate(BaseModel):
    """Request model for updating personalization profile."""
    preferences: Optional[Dict[str, Any]] = Field(None, description="User preferences")
    interests: Optional[List[str]] = Field(None, description="User interests")
    goals: Optional[List[str]] = Field(None, description="User goals")
    communication_style: Optional[str] = Field(None, description="Preferred communication style")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional profile metadata")


# Proactive suggestions endpoints
@proactive_router.get("/suggestions")
async def get_proactive_suggestions(
    limit: int = Query(20, le=100, description="Maximum number of suggestions to return"),
    offset: int = Query(0, ge=0, description="Number of suggestions to skip"),
    suggestion_type: Optional[str] = Query(None, description="Filter by suggestion type"),
    priority: Optional[int] = Query(None, ge=1, le=5, description="Filter by priority"),
    active_only: bool = Query(True, description="Return only active suggestions"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get proactive suggestions for the current user.

    Args:
        limit: Maximum number of suggestions to return
        offset: Number of suggestions to skip for pagination
        suggestion_type: Filter by suggestion type
        priority: Filter by priority level
        active_only: Return only active suggestions
        current_user: Authenticated user
        db: Database session

    Returns:
        List of proactive suggestions with metadata
    """
    try:
        suggestions_data = await proactive_service.get_user_suggestions(
            user_id=str(current_user.id),
            limit=limit,
            offset=offset,
            suggestion_type=suggestion_type,
            priority=priority,
            active_only=active_only
        )

        return {
            "suggestions": suggestions_data["suggestions"],
            "total": suggestions_data["total"],
            "limit": limit,
            "offset": offset,
            "filters": {
                "suggestion_type": suggestion_type,
                "priority": priority,
                "active_only": active_only
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch suggestions: {str(e)}"
        )


@proactive_router.post("/suggestions")
async def create_proactive_suggestion(
    request: ProactiveSuggestionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new proactive suggestion.

    Args:
        request: Suggestion creation request
        current_user: Authenticated user
        db: Database session

    Returns:
        Created suggestion details
    """
    try:
        # Parse expiration timestamp if provided
        expires_at = None
        if request.expires_at:
            from datetime import datetime
            try:
                expires_at = datetime.fromisoformat(request.expires_at.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid expires_at timestamp format. Use ISO format."
                )

        suggestion_data = await proactive_service.create_suggestion(
            user_id=str(current_user.id),
            suggestion_type=request.suggestion_type,
            title=request.title,
            description=request.description,
            action_data=request.action_data,
            priority=request.priority,
            expires_at=expires_at,
            metadata=request.metadata
        )

        return {
            "suggestion_id": suggestion_data["suggestion_id"],
            "suggestion_type": suggestion_data["suggestion_type"],
            "title": suggestion_data["title"],
            "description": suggestion_data["description"],
            "priority": suggestion_data["priority"],
            "status": suggestion_data["status"],
            "created_at": suggestion_data["created_at"],
            "expires_at": suggestion_data.get("expires_at")
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create suggestion: {str(e)}"
        )


@proactive_router.post("/suggestions/{suggestion_id}/respond")
async def respond_to_suggestion(
    suggestion_id: str,
    request: SuggestionResponseRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Respond to a proactive suggestion.

    Args:
        suggestion_id: ID of the suggestion to respond to
        request: Response details
        current_user: Authenticated user
        db: Database session

    Returns:
        Response confirmation and updated suggestion status
    """
    try:
        # Validate action
        if request.action not in ["accept", "dismiss", "postpone"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action must be one of: accept, dismiss, postpone"
            )

        response_data = await proactive_service.respond_to_suggestion(
            suggestion_id=suggestion_id,
            user_id=str(current_user.id),
            action=request.action,
            feedback=request.feedback,
            metadata=request.metadata
        )

        if not response_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Suggestion not found"
            )

        return {
            "suggestion_id": suggestion_id,
            "action": request.action,
            "status": response_data["status"],
            "responded_at": response_data["responded_at"],
            "feedback_recorded": bool(request.feedback),
            "success": True
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Suggestion not found"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to respond to suggestion: {str(e)}"
        )


# Personalization endpoints
@personalization_router.get("/profile")
async def get_personalization_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get the current user's personalization profile.

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        User's personalization profile and preferences
    """
    try:
        profile_data = await personalization_service.get_user_profile(
            user_id=str(current_user.id)
        )

        if not profile_data:
            # Create default profile if none exists
            profile_data = await personalization_service.create_user_profile(
                user_id=str(current_user.id)
            )

        return {
            "user_id": str(current_user.id),
            "profile": profile_data["profile"],
            "preferences": profile_data["preferences"],
            "interests": profile_data["interests"],
            "goals": profile_data["goals"],
            "communication_style": profile_data["communication_style"],
            "last_updated": profile_data["last_updated"],
            "insights": profile_data.get("insights", [])
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch personalization profile: {str(e)}"
        )


@personalization_router.put("/profile")
async def update_personalization_profile(
    request: PersonalizationProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update the current user's personalization profile.

    Args:
        request: Profile update request
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated profile confirmation
    """
    try:
        success = await personalization_service.update_user_profile(
            user_id=str(current_user.id),
            preferences=request.preferences,
            interests=request.interests,
            goals=request.goals,
            communication_style=request.communication_style,
            metadata=request.metadata
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )

        return {
            "success": True,
            "message": "Profile updated successfully",
            "updated_at": "2024-01-01T00:00:00Z"  # Would use datetime.utcnow().isoformat()
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update personalization profile: {str(e)}"
        )


@personalization_router.get("/insights")
async def get_personalization_insights(
    period: str = Query("month", description="Insights period: week, month, quarter, year"),
    category: Optional[str] = Query(None, description="Filter by insight category"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get personalization insights for the current user.

    Args:
        period: Time period for insights
        category: Filter by insight category
        current_user: Authenticated user
        db: Database session

    Returns:
        Personalization insights and recommendations
    """
    try:
        # Validate period
        if period not in ["week", "month", "quarter", "year"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Period must be one of: week, month, quarter, year"
            )

        insights_data = await personalization_service.get_user_insights(
            user_id=str(current_user.id),
            period=period,
            category=category
        )

        return {
            "period": period,
            "category": category,
            "insights": insights_data["insights"],
            "trends": insights_data["trends"],
            "recommendations": insights_data["recommendations"],
            "score": insights_data.get("personalization_score"),
            "generated_at": insights_data["generated_at"]
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch personalization insights: {str(e)}"
        )


# Export both routers for inclusion in main application
# The main application will need to include both routers
router = proactive_router  # Primary router for proactive suggestions
# personalization_router is also available for separate inclusion