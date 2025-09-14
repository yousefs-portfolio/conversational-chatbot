"""Tenant management service for multi-tenant organization support."""

import uuid
from typing import Dict, Optional, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func
from sqlalchemy.orm import selectinload

from ..models import TenantConfiguration, DataIsolationLevel, User, Conversation, Message
from ..database import AsyncSessionLocal


class TenantService:
    """Service for managing tenant organizations and multi-tenancy."""

    def __init__(self):
        self.default_settings = {
            "max_users": 100,
            "storage_limit_gb": 10,
            "api_rate_limit": 1000,
            "features_enabled": [
                "conversations",
                "file_upload",
                "voice_processing",
                "analytics"
            ],
            "data_retention_days": 90,
            "branding": {
                "allow_custom_theme": False,
                "allow_custom_logo": False
            }
        }

    async def create_tenant(
        self,
        name: str,
        admin_user_id: str,
        domain: Optional[str] = None,
        data_isolation_level: DataIsolationLevel = DataIsolationLevel.LOGICAL,
        settings: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new tenant organization.

        Args:
            name: Tenant name
            admin_user_id: User ID of the tenant admin
            domain: Optional custom domain
            data_isolation_level: Level of data isolation
            settings: Custom tenant settings
            metadata: Additional metadata

        Returns:
            Tenant ID
        """
        try:
            async with AsyncSessionLocal() as db:
                # Check if domain is already taken
                if domain:
                    existing = await db.execute(
                        select(TenantConfiguration).where(TenantConfiguration.domain == domain)
                    )
                    if existing.scalar_one_or_none():
                        raise ValueError(f"Domain '{domain}' is already taken")

                # Check if admin user exists and is not already a tenant admin
                admin_user = await db.get(User, admin_user_id)
                if not admin_user:
                    raise ValueError("Admin user not found")

                # Merge default settings with custom settings
                tenant_settings = {**self.default_settings, **(settings or {})}

                # Create tenant configuration
                tenant = TenantConfiguration(
                    name=name,
                    domain=domain,
                    admin_user_id=admin_user_id,
                    data_isolation_level=data_isolation_level,
                    settings=tenant_settings,
                    metadata=metadata or {},
                    is_active=True
                )

                db.add(tenant)
                await db.commit()
                await db.refresh(tenant)

                # Update admin user's tenant association
                admin_user.metadata = admin_user.metadata or {}
                admin_user.metadata["tenant_id"] = str(tenant.id)
                admin_user.metadata["tenant_role"] = "admin"
                await db.commit()

                return str(tenant.id)

        except Exception as e:
            raise Exception(f"Error creating tenant: {str(e)}")

    async def update_tenant_settings(
        self,
        tenant_id: str,
        admin_user_id: str,
        settings: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None
    ) -> bool:
        """
        Update tenant configuration settings.

        Args:
            tenant_id: Tenant ID to update
            admin_user_id: Admin user ID (for authorization)
            settings: Updated settings
            metadata: Updated metadata
            is_active: Updated active status

        Returns:
            True if updated successfully
        """
        try:
            async with AsyncSessionLocal() as db:
                tenant = await db.get(TenantConfiguration, tenant_id)
                if not tenant:
                    return False

                # Verify admin privileges
                if str(tenant.admin_user_id) != admin_user_id:
                    raise ValueError("Unauthorized: Only tenant admin can update settings")

                # Update settings
                if settings is not None:
                    # Merge with existing settings
                    current_settings = tenant.settings or {}
                    tenant.settings = {**current_settings, **settings}

                if metadata is not None:
                    # Merge with existing metadata
                    current_metadata = tenant.metadata or {}
                    tenant.metadata = {**current_metadata, **metadata}

                if is_active is not None:
                    tenant.is_active = is_active

                await db.commit()
                return True

        except Exception as e:
            raise Exception(f"Error updating tenant settings: {str(e)}")

    async def add_user_to_tenant(
        self,
        tenant_id: str,
        user_id: str,
        admin_user_id: str,
        role: str = "member",
        permissions: Optional[List[str]] = None
    ) -> bool:
        """
        Add a user to a tenant organization.

        Args:
            tenant_id: Tenant ID
            user_id: User ID to add
            admin_user_id: Admin user ID (for authorization)
            role: User role in the tenant
            permissions: Optional specific permissions

        Returns:
            True if added successfully
        """
        try:
            async with AsyncSessionLocal() as db:
                # Verify tenant exists and admin has privileges
                tenant = await db.get(TenantConfiguration, tenant_id)
                if not tenant:
                    raise ValueError("Tenant not found")

                if str(tenant.admin_user_id) != admin_user_id:
                    raise ValueError("Unauthorized: Only tenant admin can add users")

                if not tenant.is_active:
                    raise ValueError("Cannot add users to inactive tenant")

                # Check user limit
                current_users = await self._get_tenant_user_count(db, tenant_id)
                max_users = tenant.settings.get("max_users", self.default_settings["max_users"])
                if current_users >= max_users:
                    raise ValueError(f"Tenant user limit reached ({max_users})")

                # Get user and update their tenant association
                user = await db.get(User, user_id)
                if not user:
                    raise ValueError("User not found")

                # Check if user is already associated with another tenant
                user_metadata = user.metadata or {}
                if "tenant_id" in user_metadata and user_metadata["tenant_id"] != tenant_id:
                    raise ValueError("User is already associated with another tenant")

                # Add user to tenant
                user.metadata = user_metadata
                user.metadata["tenant_id"] = tenant_id
                user.metadata["tenant_role"] = role
                if permissions:
                    user.metadata["tenant_permissions"] = permissions

                # Update tenant user list
                tenant_metadata = tenant.metadata or {}
                user_list = tenant_metadata.get("users", [])
                if user_id not in user_list:
                    user_list.append(user_id)
                    tenant_metadata["users"] = user_list
                    tenant.metadata = tenant_metadata

                await db.commit()
                return True

        except Exception as e:
            raise Exception(f"Error adding user to tenant: {str(e)}")

    async def remove_user_from_tenant(
        self,
        tenant_id: str,
        user_id: str,
        admin_user_id: str
    ) -> bool:
        """
        Remove a user from a tenant organization.

        Args:
            tenant_id: Tenant ID
            user_id: User ID to remove
            admin_user_id: Admin user ID (for authorization)

        Returns:
            True if removed successfully
        """
        try:
            async with AsyncSessionLocal() as db:
                # Verify tenant and admin privileges
                tenant = await db.get(TenantConfiguration, tenant_id)
                if not tenant or str(tenant.admin_user_id) != admin_user_id:
                    raise ValueError("Unauthorized")

                # Cannot remove the admin user
                if user_id == admin_user_id:
                    raise ValueError("Cannot remove tenant admin user")

                # Update user
                user = await db.get(User, user_id)
                if user and user.metadata:
                    user.metadata.pop("tenant_id", None)
                    user.metadata.pop("tenant_role", None)
                    user.metadata.pop("tenant_permissions", None)

                # Update tenant user list
                tenant_metadata = tenant.metadata or {}
                user_list = tenant_metadata.get("users", [])
                if user_id in user_list:
                    user_list.remove(user_id)
                    tenant_metadata["users"] = user_list
                    tenant.metadata = tenant_metadata

                await db.commit()
                return True

        except Exception as e:
            raise Exception(f"Error removing user from tenant: {str(e)}")

    async def check_data_isolation(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str
    ) -> Dict[str, Any]:
        """
        Check if a user has access to a resource based on tenant data isolation.

        Args:
            user_id: User ID requesting access
            resource_type: Type of resource (conversation, message, file, etc.)
            resource_id: ID of the resource

        Returns:
            Access decision with reasoning
        """
        try:
            async with AsyncSessionLocal() as db:
                # Get user's tenant information
                user = await db.get(User, user_id)
                if not user:
                    return {"allowed": False, "reason": "User not found"}

                user_metadata = user.metadata or {}
                user_tenant_id = user_metadata.get("tenant_id")

                if not user_tenant_id:
                    # User not in a tenant - check if resource is tenant-specific
                    resource_tenant = await self._get_resource_tenant(db, resource_type, resource_id)
                    return {
                        "allowed": resource_tenant is None,
                        "reason": "Non-tenant user can only access non-tenant resources" if resource_tenant else "Access allowed",
                        "user_tenant": None,
                        "resource_tenant": resource_tenant
                    }

                # Get tenant configuration
                tenant = await db.get(TenantConfiguration, user_tenant_id)
                if not tenant or not tenant.is_active:
                    return {"allowed": False, "reason": "User's tenant is inactive or not found"}

                # Get resource tenant
                resource_tenant = await self._get_resource_tenant(db, resource_type, resource_id)

                # Check isolation level
                if tenant.data_isolation_level == DataIsolationLevel.STRICT:
                    allowed = resource_tenant == user_tenant_id
                    reason = "Strict isolation: access only to same tenant resources"
                elif tenant.data_isolation_level == DataIsolationLevel.LOGICAL:
                    allowed = resource_tenant is None or resource_tenant == user_tenant_id
                    reason = "Logical isolation: access to non-tenant and same tenant resources"
                else:  # SHARED
                    allowed = True
                    reason = "Shared isolation: access to all resources"

                return {
                    "allowed": allowed,
                    "reason": reason,
                    "user_tenant": user_tenant_id,
                    "resource_tenant": resource_tenant,
                    "isolation_level": tenant.data_isolation_level.value
                }

        except Exception as e:
            return {"allowed": False, "reason": f"Error checking data isolation: {str(e)}"}

    async def get_tenant_details(
        self,
        tenant_id: str,
        requesting_user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a tenant.

        Args:
            tenant_id: Tenant ID
            requesting_user_id: User ID making the request

        Returns:
            Tenant details or None if not authorized
        """
        try:
            async with AsyncSessionLocal() as db:
                tenant = await db.get(TenantConfiguration, tenant_id)
                if not tenant:
                    return None

                # Check if requesting user has access to tenant info
                user = await db.get(User, requesting_user_id)
                if not user:
                    return None

                user_metadata = user.metadata or {}
                user_tenant_id = user_metadata.get("tenant_id")
                user_role = user_metadata.get("tenant_role")

                # Only allow access if user is part of the tenant or is a system admin
                if user_tenant_id != tenant_id and user_role != "admin":
                    return None

                # Get tenant statistics
                user_count = await self._get_tenant_user_count(db, tenant_id)

                # Get resource counts
                conversation_count = await self._get_tenant_resource_count(db, "conversation", tenant_id)

                return {
                    "id": str(tenant.id),
                    "name": tenant.name,
                    "domain": tenant.domain,
                    "admin_user_id": str(tenant.admin_user_id),
                    "data_isolation_level": tenant.data_isolation_level.value,
                    "is_active": tenant.is_active,
                    "settings": tenant.settings,
                    "metadata": tenant.metadata,
                    "created_at": tenant.created_at.isoformat(),
                    "updated_at": tenant.updated_at.isoformat(),
                    "statistics": {
                        "user_count": user_count,
                        "max_users": tenant.settings.get("max_users", self.default_settings["max_users"]),
                        "conversation_count": conversation_count,
                        "storage_used_gb": 0,  # Would calculate from actual usage
                        "storage_limit_gb": tenant.settings.get("storage_limit_gb", self.default_settings["storage_limit_gb"])
                    }
                }

        except Exception as e:
            raise Exception(f"Error getting tenant details: {str(e)}")

    async def list_tenant_users(
        self,
        tenant_id: str,
        admin_user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List users in a tenant organization.

        Args:
            tenant_id: Tenant ID
            admin_user_id: Admin user ID (for authorization)
            limit: Maximum users to return
            offset: Number of users to skip

        Returns:
            List of tenant users
        """
        try:
            async with AsyncSessionLocal() as db:
                # Verify admin privileges
                tenant = await db.get(TenantConfiguration, tenant_id)
                if not tenant or str(tenant.admin_user_id) != admin_user_id:
                    raise ValueError("Unauthorized")

                # Get users associated with tenant
                result = await db.execute(
                    select(User)
                    .where(User.metadata.op('->>')('tenant_id') == tenant_id)
                    .limit(limit)
                    .offset(offset)
                )
                users = result.scalars().all()

                return [
                    {
                        "id": str(user.id),
                        "email": user.email,
                        "full_name": user.full_name,
                        "tenant_role": (user.metadata or {}).get("tenant_role", "member"),
                        "tenant_permissions": (user.metadata or {}).get("tenant_permissions", []),
                        "is_active": user.is_active,
                        "created_at": user.created_at.isoformat(),
                        "last_active": user.last_active.isoformat() if user.last_active else None
                    }
                    for user in users
                ]

        except Exception as e:
            raise Exception(f"Error listing tenant users: {str(e)}")

    async def _get_tenant_user_count(self, db: AsyncSession, tenant_id: str) -> int:
        """Get the number of users in a tenant."""
        result = await db.execute(
            select(func.count(User.id))
            .where(User.metadata.op('->>')('tenant_id') == tenant_id)
        )
        return result.scalar() or 0

    async def _get_resource_tenant(self, db: AsyncSession, resource_type: str, resource_id: str) -> Optional[str]:
        """Get the tenant ID that owns a resource."""
        try:
            if resource_type == "conversation":
                result = await db.execute(
                    select(Conversation.user_id).where(Conversation.id == resource_id)
                )
                user_id = result.scalar_one_or_none()
                if user_id:
                    user_result = await db.execute(
                        select(User.metadata).where(User.id == user_id)
                    )
                    user_metadata = user_result.scalar_one_or_none()
                    return (user_metadata or {}).get("tenant_id")

            elif resource_type == "message":
                result = await db.execute(
                    select(Conversation.user_id)
                    .join(Message)
                    .where(Message.id == resource_id)
                )
                user_id = result.scalar_one_or_none()
                if user_id:
                    user_result = await db.execute(
                        select(User.metadata).where(User.id == user_id)
                    )
                    user_metadata = user_result.scalar_one_or_none()
                    return (user_metadata or {}).get("tenant_id")

            # Add more resource types as needed

            return None

        except Exception:
            return None

    async def _get_tenant_resource_count(self, db: AsyncSession, resource_type: str, tenant_id: str) -> int:
        """Get count of resources owned by a tenant."""
        try:
            if resource_type == "conversation":
                # Get conversations from users in this tenant
                result = await db.execute(
                    select(func.count(Conversation.id))
                    .join(User)
                    .where(User.metadata.op('->>')('tenant_id') == tenant_id)
                )
                return result.scalar() or 0

            # Add more resource types as needed
            return 0

        except Exception:
            return 0


# Global tenant service instance
tenant_service = TenantService()