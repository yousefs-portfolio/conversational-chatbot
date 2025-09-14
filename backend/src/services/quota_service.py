"""Quota management service for tracking and enforcing usage limits."""

from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func
from sqlalchemy.orm import selectinload

from ..models import UsageQuota, EntityType, QuotaType, ResetPeriod, OveragePolicy, User
from ..database import AsyncSessionLocal


class QuotaExceededException(Exception):
    """Exception raised when quota is exceeded."""
    pass


class QuotaService:
    """Service for managing usage quotas and enforcement."""

    def __init__(self):
        self.default_quotas = {
            EntityType.USER: {
                QuotaType.API_CALLS: {"daily": 1000, "monthly": 30000},
                QuotaType.TOKENS: {"daily": 100000, "monthly": 3000000},
                QuotaType.STORAGE: {"monthly": 1024 * 1024 * 100},  # 100MB
                QuotaType.CONVERSATIONS: {"daily": 50, "monthly": 1500}
            },
            EntityType.ORGANIZATION: {
                QuotaType.API_CALLS: {"monthly": 1000000},
                QuotaType.TOKENS: {"monthly": 100000000},
                QuotaType.STORAGE: {"monthly": 1024 * 1024 * 1024 * 10},  # 10GB
                QuotaType.USERS: {"monthly": 100}
            }
        }

    async def check_quota(
        self,
        entity_id: str,
        entity_type: EntityType,
        quota_type: QuotaType,
        amount: int = 1
    ) -> Dict[str, Any]:
        """
        Check if an action is allowed within quota limits.

        Args:
            entity_id: Entity ID (user, organization, etc.)
            entity_type: Type of entity
            quota_type: Type of quota to check
            amount: Amount to be consumed (default: 1)

        Returns:
            Dict with quota status and remaining allowance
        """
        try:
            async with AsyncSessionLocal() as db:
                # Get all relevant quotas for this entity and type
                quotas = await self._get_quotas(db, entity_id, entity_type, quota_type)

                results = []
                for quota in quotas:
                    current_usage = await self._calculate_current_usage(db, quota)
                    remaining = max(0, quota.limit - current_usage)

                    is_allowed = (current_usage + amount) <= quota.limit
                    if not is_allowed and quota.overage_policy == OveragePolicy.STRICT:
                        results.append({
                            "quota_id": str(quota.id),
                            "period": quota.reset_period.value,
                            "allowed": False,
                            "current_usage": current_usage,
                            "limit": quota.limit,
                            "remaining": remaining,
                            "requested": amount,
                            "overage_policy": quota.overage_policy.value,
                            "would_exceed": True
                        })
                    else:
                        results.append({
                            "quota_id": str(quota.id),
                            "period": quota.reset_period.value,
                            "allowed": True,
                            "current_usage": current_usage,
                            "limit": quota.limit,
                            "remaining": remaining,
                            "requested": amount,
                            "overage_policy": quota.overage_policy.value,
                            "would_exceed": not is_allowed
                        })

                # Overall allowance (must pass all strict quotas)
                overall_allowed = all(
                    result["allowed"] for result in results
                    if result.get("overage_policy") == OveragePolicy.STRICT.value
                ) if results else True

                return {
                    "entity_id": entity_id,
                    "entity_type": entity_type.value,
                    "quota_type": quota_type.value,
                    "allowed": overall_allowed,
                    "quotas": results,
                    "checked_at": datetime.utcnow().isoformat()
                }

        except Exception as e:
            raise Exception(f"Error checking quota: {str(e)}")

    async def consume_quota(
        self,
        entity_id: str,
        entity_type: EntityType,
        quota_type: QuotaType,
        amount: int = 1,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Consume quota and update usage counts.

        Args:
            entity_id: Entity ID
            entity_type: Type of entity
            quota_type: Type of quota to consume
            amount: Amount to consume
            metadata: Additional metadata about the usage

        Returns:
            Dict with consumption result and updated usage
        """
        try:
            # First check if consumption is allowed
            quota_check = await self.check_quota(entity_id, entity_type, quota_type, amount)

            if not quota_check["allowed"]:
                # Find the first strict quota that would be exceeded
                exceeding_quota = next(
                    (q for q in quota_check["quotas"]
                     if not q["allowed"] and q["overage_policy"] == OveragePolicy.STRICT.value),
                    None
                )
                if exceeding_quota:
                    raise QuotaExceededException(
                        f"Quota exceeded for {quota_type.value}: {exceeding_quota['current_usage'] + amount}/{exceeding_quota['limit']} ({exceeding_quota['period']})"
                    )

            async with AsyncSessionLocal() as db:
                quotas = await self._get_quotas(db, entity_id, entity_type, quota_type)

                results = []
                for quota in quotas:
                    # Update usage
                    quota.current_usage += amount
                    quota.last_used_at = datetime.utcnow()

                    if metadata:
                        quota.metadata = {**(quota.metadata or {}), **metadata}

                    await db.commit()

                    results.append({
                        "quota_id": str(quota.id),
                        "period": quota.reset_period.value,
                        "consumed": amount,
                        "new_usage": quota.current_usage,
                        "limit": quota.limit,
                        "remaining": max(0, quota.limit - quota.current_usage)
                    })

                return {
                    "entity_id": entity_id,
                    "entity_type": entity_type.value,
                    "quota_type": quota_type.value,
                    "consumed": amount,
                    "quotas": results,
                    "consumed_at": datetime.utcnow().isoformat()
                }

        except QuotaExceededException:
            raise
        except Exception as e:
            raise Exception(f"Error consuming quota: {str(e)}")

    async def reset_quotas(
        self,
        entity_id: Optional[str] = None,
        entity_type: Optional[EntityType] = None,
        reset_period: Optional[ResetPeriod] = None
    ) -> Dict[str, Any]:
        """
        Reset quotas based on their reset periods.

        Args:
            entity_id: Optional entity ID to filter by
            entity_type: Optional entity type to filter by
            reset_period: Optional reset period to filter by

        Returns:
            Dict with reset statistics
        """
        try:
            async with AsyncSessionLocal() as db:
                # Build query
                query = select(UsageQuota)

                conditions = []
                if entity_id:
                    conditions.append(UsageQuota.entity_id == entity_id)
                if entity_type:
                    conditions.append(UsageQuota.entity_type == entity_type)
                if reset_period:
                    conditions.append(UsageQuota.reset_period == reset_period)

                # Add time-based conditions for periodic resets
                now = datetime.utcnow()
                time_conditions = []

                if not reset_period or reset_period == ResetPeriod.DAILY:
                    daily_cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    time_conditions.append(
                        and_(
                            UsageQuota.reset_period == ResetPeriod.DAILY,
                            or_(
                                UsageQuota.last_reset_at.is_(None),
                                UsageQuota.last_reset_at < daily_cutoff
                            )
                        )
                    )

                if not reset_period or reset_period == ResetPeriod.MONTHLY:
                    monthly_cutoff = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    time_conditions.append(
                        and_(
                            UsageQuota.reset_period == ResetPeriod.MONTHLY,
                            or_(
                                UsageQuota.last_reset_at.is_(None),
                                UsageQuota.last_reset_at < monthly_cutoff
                            )
                        )
                    )

                if time_conditions:
                    if conditions:
                        query = query.where(and_(and_(*conditions), or_(*time_conditions)))
                    else:
                        query = query.where(or_(*time_conditions))
                elif conditions:
                    query = query.where(and_(*conditions))

                result = await db.execute(query)
                quotas_to_reset = result.scalars().all()

                reset_count = 0
                for quota in quotas_to_reset:
                    quota.current_usage = 0
                    quota.last_reset_at = now
                    reset_count += 1

                await db.commit()

                return {
                    "reset_count": reset_count,
                    "reset_at": now.isoformat(),
                    "filters": {
                        "entity_id": entity_id,
                        "entity_type": entity_type.value if entity_type else None,
                        "reset_period": reset_period.value if reset_period else None
                    }
                }

        except Exception as e:
            raise Exception(f"Error resetting quotas: {str(e)}")

    async def handle_overage(
        self,
        entity_id: str,
        entity_type: EntityType,
        quota_type: QuotaType,
        overage_amount: int
    ) -> Dict[str, Any]:
        """
        Process quota overage based on policies.

        Args:
            entity_id: Entity ID that exceeded quota
            entity_type: Type of entity
            quota_type: Type of quota exceeded
            overage_amount: Amount by which quota was exceeded

        Returns:
            Dict with overage handling results
        """
        try:
            async with AsyncSessionLocal() as db:
                quotas = await self._get_quotas(db, entity_id, entity_type, quota_type)

                actions_taken = []
                for quota in quotas:
                    current_usage = await self._calculate_current_usage(db, quota)
                    if current_usage > quota.limit:
                        actual_overage = current_usage - quota.limit

                        if quota.overage_policy == OveragePolicy.STRICT:
                            actions_taken.append({
                                "quota_id": str(quota.id),
                                "action": "blocked",
                                "overage": actual_overage,
                                "message": "Request blocked due to strict quota policy"
                            })

                        elif quota.overage_policy == OveragePolicy.THROTTLE:
                            # Implement throttling logic
                            throttle_delay = min(actual_overage * 0.1, 5.0)  # Max 5 second delay
                            actions_taken.append({
                                "quota_id": str(quota.id),
                                "action": "throttled",
                                "overage": actual_overage,
                                "throttle_delay": throttle_delay,
                                "message": f"Request throttled for {throttle_delay} seconds"
                            })

                        elif quota.overage_policy == OveragePolicy.ALLOW:
                            actions_taken.append({
                                "quota_id": str(quota.id),
                                "action": "allowed",
                                "overage": actual_overage,
                                "message": "Overage allowed per policy"
                            })

                        # Record overage in metadata
                        quota.metadata = quota.metadata or {}
                        quota.metadata["overages"] = quota.metadata.get("overages", [])
                        quota.metadata["overages"].append({
                            "timestamp": datetime.utcnow().isoformat(),
                            "amount": actual_overage,
                            "action": actions_taken[-1]["action"]
                        })

                await db.commit()

                return {
                    "entity_id": entity_id,
                    "entity_type": entity_type.value,
                    "quota_type": quota_type.value,
                    "overage_amount": overage_amount,
                    "actions_taken": actions_taken,
                    "handled_at": datetime.utcnow().isoformat()
                }

        except Exception as e:
            raise Exception(f"Error handling overage: {str(e)}")

    async def create_quota(
        self,
        entity_id: str,
        entity_type: EntityType,
        quota_type: QuotaType,
        limit: int,
        reset_period: ResetPeriod,
        overage_policy: OveragePolicy = OveragePolicy.STRICT,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new quota for an entity.

        Args:
            entity_id: Entity ID
            entity_type: Type of entity
            quota_type: Type of quota
            limit: Quota limit
            reset_period: How often quota resets
            overage_policy: Policy for handling overages
            metadata: Additional metadata

        Returns:
            Quota ID
        """
        try:
            async with AsyncSessionLocal() as db:
                quota = UsageQuota(
                    entity_id=entity_id,
                    entity_type=entity_type,
                    quota_type=quota_type,
                    limit=limit,
                    current_usage=0,
                    reset_period=reset_period,
                    overage_policy=overage_policy,
                    metadata=metadata or {}
                )

                db.add(quota)
                await db.commit()
                await db.refresh(quota)

                return str(quota.id)

        except Exception as e:
            raise Exception(f"Error creating quota: {str(e)}")

    async def get_quota_status(
        self,
        entity_id: str,
        entity_type: Optional[EntityType] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive quota status for an entity.

        Args:
            entity_id: Entity ID
            entity_type: Optional entity type filter

        Returns:
            Complete quota status
        """
        try:
            async with AsyncSessionLocal() as db:
                query = select(UsageQuota).where(UsageQuota.entity_id == entity_id)
                if entity_type:
                    query = query.where(UsageQuota.entity_type == entity_type)

                result = await db.execute(query)
                quotas = result.scalars().all()

                quota_status = []
                for quota in quotas:
                    current_usage = await self._calculate_current_usage(db, quota)
                    remaining = max(0, quota.limit - current_usage)
                    utilization = (current_usage / quota.limit * 100) if quota.limit > 0 else 0

                    quota_status.append({
                        "id": str(quota.id),
                        "quota_type": quota.quota_type.value,
                        "limit": quota.limit,
                        "current_usage": current_usage,
                        "remaining": remaining,
                        "utilization_percent": round(utilization, 2),
                        "reset_period": quota.reset_period.value,
                        "overage_policy": quota.overage_policy.value,
                        "last_reset_at": quota.last_reset_at.isoformat() if quota.last_reset_at else None,
                        "last_used_at": quota.last_used_at.isoformat() if quota.last_used_at else None,
                        "is_exceeded": current_usage > quota.limit
                    })

                return {
                    "entity_id": entity_id,
                    "entity_type": entity_type.value if entity_type else None,
                    "quotas": quota_status,
                    "total_quotas": len(quota_status),
                    "exceeded_quotas": len([q for q in quota_status if q["is_exceeded"]]),
                    "checked_at": datetime.utcnow().isoformat()
                }

        except Exception as e:
            raise Exception(f"Error getting quota status: {str(e)}")

    async def _get_quotas(
        self,
        db: AsyncSession,
        entity_id: str,
        entity_type: EntityType,
        quota_type: QuotaType
    ) -> List[UsageQuota]:
        """Get all relevant quotas for an entity and type."""
        result = await db.execute(
            select(UsageQuota).where(
                and_(
                    UsageQuota.entity_id == entity_id,
                    UsageQuota.entity_type == entity_type,
                    UsageQuota.quota_type == quota_type
                )
            )
        )
        quotas = result.scalars().all()

        # If no quotas exist, create default ones
        if not quotas:
            quotas = await self._create_default_quotas(db, entity_id, entity_type, quota_type)

        return quotas

    async def _create_default_quotas(
        self,
        db: AsyncSession,
        entity_id: str,
        entity_type: EntityType,
        quota_type: QuotaType
    ) -> List[UsageQuota]:
        """Create default quotas for an entity."""
        quotas = []
        default_config = self.default_quotas.get(entity_type, {}).get(quota_type, {})

        for period, limit in default_config.items():
            reset_period = ResetPeriod.DAILY if period == "daily" else ResetPeriod.MONTHLY

            quota = UsageQuota(
                entity_id=entity_id,
                entity_type=entity_type,
                quota_type=quota_type,
                limit=limit,
                current_usage=0,
                reset_period=reset_period,
                overage_policy=OveragePolicy.STRICT,
                metadata={"auto_created": True}
            )

            db.add(quota)
            quotas.append(quota)

        await db.commit()
        return quotas

    async def _calculate_current_usage(self, db: AsyncSession, quota: UsageQuota) -> int:
        """Calculate current usage for a quota, considering reset periods."""
        # For this implementation, we use the stored current_usage
        # In a real implementation, you might want to calculate from actual usage logs

        # Check if quota needs to be reset based on time
        now = datetime.utcnow()
        should_reset = False

        if quota.reset_period == ResetPeriod.DAILY:
            last_reset = quota.last_reset_at or quota.created_at
            if now.date() > last_reset.date():
                should_reset = True

        elif quota.reset_period == ResetPeriod.MONTHLY:
            last_reset = quota.last_reset_at or quota.created_at
            if (now.year, now.month) > (last_reset.year, last_reset.month):
                should_reset = True

        if should_reset:
            quota.current_usage = 0
            quota.last_reset_at = now
            await db.commit()

        return quota.current_usage


# Global quota service instance
quota_service = QuotaService()