"""Tenant management API endpoints."""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session

from ...auth import get_current_active_user
from ...database import get_db
from ...models import User
from ...services.tenant_service import TenantService
from ...services.quota_service import QuotaService

router = APIRouter(prefix="/tenants", tags=["tenants"])
tenant_service = TenantService()
quota_service = QuotaService()


class TenantCreateRequest(BaseModel):
    """Request model for creating a tenant."""
    name: str = Field(..., description="Tenant name")
    description: Optional[str] = Field(None, description="Tenant description")
    settings: Optional[Dict[str, Any]] = Field(None, description="Tenant-specific settings")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional tenant metadata")


class TenantUpdateRequest(BaseModel):
    """Request model for updating a tenant."""
    name: Optional[str] = Field(None, description="Updated tenant name")
    description: Optional[str] = Field(None, description="Updated tenant description")
    settings: Optional[Dict[str, Any]] = Field(None, description="Updated tenant settings")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated tenant metadata")
    is_active: Optional[bool] = Field(None, description="Tenant active status")


class TenantUserCreateRequest(BaseModel):
    """Request model for adding a user to a tenant."""
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., description="Username")
    full_name: Optional[str] = Field(None, description="User's full name")
    role: str = Field("member", description="User role within tenant")
    permissions: Optional[List[str]] = Field(None, description="Specific permissions")


class QuotaCreateRequest(BaseModel):
    """Request model for creating tenant quotas."""
    resource_type: str = Field(..., description="Type of resource (e.g., 'api_calls', 'storage')")
    limit_value: int = Field(..., description="Quota limit value")
    period: str = Field("month", description="Quota period: day, week, month, year")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional quota metadata")


@router.post("")
async def create_tenant(
    request: TenantCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new tenant.

    Args:
        request: Tenant creation request
        current_user: Authenticated user (must be admin)
        db: Database session

    Returns:
        Created tenant details
    """
    try:
        # Check if user has permission to create tenants
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to create tenant"
            )

        tenant_data = await tenant_service.create_tenant(
            name=request.name,
            description=request.description,
            created_by=str(current_user.id),
            settings=request.settings,
            metadata=request.metadata
        )

        return {
            "tenant_id": tenant_data["tenant_id"],
            "name": tenant_data["name"],
            "description": tenant_data["description"],
            "settings": tenant_data["settings"],
            "created_at": tenant_data["created_at"],
            "is_active": tenant_data["is_active"]
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create tenant: {str(e)}"
        )


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get tenant details.

    Args:
        tenant_id: ID of the tenant
        current_user: Authenticated user
        db: Database session

    Returns:
        Tenant details and configuration
    """
    try:
        tenant_data = await tenant_service.get_tenant_details(
            tenant_id=tenant_id,
            user_id=str(current_user.id)
        )

        if not tenant_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found or access denied"
            )

        return tenant_data

    except Exception as e:
        if "not found" in str(e).lower() or "access denied" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found or access denied"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tenant details: {str(e)}"
        )


@router.put("/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    request: TenantUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update tenant details.

    Args:
        tenant_id: ID of the tenant to update
        request: Tenant update request
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated tenant details
    """
    try:
        success = await tenant_service.update_tenant(
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            name=request.name,
            description=request.description,
            settings=request.settings,
            metadata=request.metadata,
            is_active=request.is_active
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found or insufficient permissions"
            )

        return {"success": True, "message": "Tenant updated successfully"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        if "not found" in str(e).lower() or "permission" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found or insufficient permissions"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update tenant: {str(e)}"
        )


@router.get("/{tenant_id}/users")
async def get_tenant_users(
    tenant_id: str,
    limit: int = Query(50, le=100, description="Maximum number of users to return"),
    offset: int = Query(0, ge=0, description="Number of users to skip"),
    role: Optional[str] = Query(None, description="Filter by user role"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get users associated with a tenant.

    Args:
        tenant_id: ID of the tenant
        limit: Maximum number of users to return
        offset: Number of users to skip for pagination
        role: Filter by user role
        current_user: Authenticated user
        db: Database session

    Returns:
        List of tenant users with their roles and permissions
    """
    try:
        users_data = await tenant_service.get_tenant_users(
            tenant_id=tenant_id,
            requesting_user_id=str(current_user.id),
            limit=limit,
            offset=offset,
            role_filter=role
        )

        if not users_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found or access denied"
            )

        return {
            "users": users_data["users"],
            "total": users_data["total"],
            "limit": limit,
            "offset": offset,
            "role_filter": role
        }

    except Exception as e:
        if "not found" in str(e).lower() or "access denied" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found or access denied"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tenant users: {str(e)}"
        )


@router.post("/{tenant_id}/users")
async def add_tenant_user(
    tenant_id: str,
    request: TenantUserCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Add a user to a tenant.

    Args:
        tenant_id: ID of the tenant
        request: User creation request
        current_user: Authenticated user
        db: Database session

    Returns:
        Added user details and tenant association
    """
    try:
        user_data = await tenant_service.add_tenant_user(
            tenant_id=tenant_id,
            email=request.email,
            username=request.username,
            full_name=request.full_name,
            role=request.role,
            permissions=request.permissions,
            added_by=str(current_user.id)
        )

        return {
            "user_id": user_data["user_id"],
            "email": user_data["email"],
            "username": user_data["username"],
            "role": user_data["role"],
            "permissions": user_data["permissions"],
            "added_at": user_data["added_at"],
            "tenant_id": tenant_id
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        if "permission" in str(e).lower() or "access denied" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to add users to tenant"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add user to tenant: {str(e)}"
        )


@router.get("/{tenant_id}/quotas")
async def get_tenant_quotas(
    tenant_id: str,
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get tenant quotas and usage information.

    Args:
        tenant_id: ID of the tenant
        resource_type: Filter by specific resource type
        current_user: Authenticated user
        db: Database session

    Returns:
        Tenant quotas and current usage
    """
    try:
        quotas_data = await quota_service.get_tenant_quotas(
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            resource_type=resource_type
        )

        if not quotas_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found or access denied"
            )

        return {
            "tenant_id": tenant_id,
            "quotas": quotas_data["quotas"],
            "usage": quotas_data["usage"],
            "alerts": quotas_data.get("alerts", []),
            "last_updated": quotas_data["last_updated"]
        }

    except Exception as e:
        if "not found" in str(e).lower() or "access denied" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found or access denied"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tenant quotas: {str(e)}"
        )


@router.post("/{tenant_id}/quotas")
async def create_tenant_quota(
    tenant_id: str,
    request: QuotaCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create or update a tenant quota.

    Args:
        tenant_id: ID of the tenant
        request: Quota creation request
        current_user: Authenticated user
        db: Database session

    Returns:
        Created quota details
    """
    try:
        # Validate period
        if request.period not in ["day", "week", "month", "year"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Period must be one of: day, week, month, year"
            )

        quota_data = await quota_service.create_tenant_quota(
            tenant_id=tenant_id,
            resource_type=request.resource_type,
            limit_value=request.limit_value,
            period=request.period,
            created_by=str(current_user.id),
            metadata=request.metadata
        )

        return {
            "quota_id": quota_data["quota_id"],
            "tenant_id": tenant_id,
            "resource_type": quota_data["resource_type"],
            "limit_value": quota_data["limit_value"],
            "period": quota_data["period"],
            "created_at": quota_data["created_at"],
            "is_active": quota_data["is_active"]
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        if "permission" in str(e).lower() or "access denied" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to create quota"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create tenant quota: {str(e)}"
        )