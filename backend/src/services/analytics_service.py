"""Analytics service for logging events, metrics collection, and dashboard data."""

import json
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload

from ..models import AnalyticsEvent, EventType, User, Conversation, Message
from ..database import AsyncSessionLocal


class AnalyticsService:
    """Service for handling analytics events and metrics."""

    def __init__(self):
        self.batch_size = 100
        self.retention_days = 365  # Keep analytics data for 1 year

    async def log_event(
        self,
        user_id: str,
        event_type: EventType,
        event_name: str,
        properties: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> str:
        """
        Log an analytics event.

        Args:
            user_id: User ID who triggered the event
            event_type: Type of event (USER_ACTION, SYSTEM_EVENT, etc.)
            event_name: Name of the specific event
            properties: Additional properties and metadata
            session_id: Optional session ID
            conversation_id: Optional conversation ID

        Returns:
            Event ID
        """
        try:
            async with AsyncSessionLocal() as db:
                event = AnalyticsEvent(
                    user_id=user_id,
                    event_type=event_type,
                    event_name=event_name,
                    properties=properties or {},
                    session_id=session_id,
                    conversation_id=conversation_id,
                    timestamp=datetime.utcnow()
                )

                db.add(event)
                await db.commit()
                await db.refresh(event)

                return str(event.id)

        except Exception as e:
            raise Exception(f"Error logging analytics event: {str(e)}")

    async def get_dashboard_data(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Aggregate metrics for dashboard display.

        Args:
            user_id: Optional user ID to filter by (admin can view all)
            start_date: Start date for metrics
            end_date: End date for metrics

        Returns:
            Dashboard metrics and charts data
        """
        try:
            if not start_date:
                start_date = datetime.utcnow() - timedelta(days=30)
            if not end_date:
                end_date = datetime.utcnow()

            async with AsyncSessionLocal() as db:
                # Base query
                base_query = select(AnalyticsEvent).where(
                    and_(
                        AnalyticsEvent.timestamp >= start_date,
                        AnalyticsEvent.timestamp <= end_date
                    )
                )

                if user_id:
                    base_query = base_query.where(AnalyticsEvent.user_id == user_id)

                # Total events
                total_events_result = await db.execute(
                    select(func.count(AnalyticsEvent.id)).where(
                        and_(
                            AnalyticsEvent.timestamp >= start_date,
                            AnalyticsEvent.timestamp <= end_date,
                            AnalyticsEvent.user_id == user_id if user_id else True
                        )
                    )
                )
                total_events = total_events_result.scalar()

                # Events by type
                events_by_type_result = await db.execute(
                    select(
                        AnalyticsEvent.event_type,
                        func.count(AnalyticsEvent.id).label('count')
                    )
                    .where(
                        and_(
                            AnalyticsEvent.timestamp >= start_date,
                            AnalyticsEvent.timestamp <= end_date,
                            AnalyticsEvent.user_id == user_id if user_id else True
                        )
                    )
                    .group_by(AnalyticsEvent.event_type)
                )
                events_by_type = {
                    row.event_type.value: row.count
                    for row in events_by_type_result
                }

                # Top events
                top_events_result = await db.execute(
                    select(
                        AnalyticsEvent.event_name,
                        func.count(AnalyticsEvent.id).label('count')
                    )
                    .where(
                        and_(
                            AnalyticsEvent.timestamp >= start_date,
                            AnalyticsEvent.timestamp <= end_date,
                            AnalyticsEvent.user_id == user_id if user_id else True
                        )
                    )
                    .group_by(AnalyticsEvent.event_name)
                    .order_by(desc('count'))
                    .limit(10)
                )
                top_events = [
                    {"event_name": row.event_name, "count": row.count}
                    for row in top_events_result
                ]

                # Daily activity
                daily_activity_result = await db.execute(
                    select(
                        func.date(AnalyticsEvent.timestamp).label('date'),
                        func.count(AnalyticsEvent.id).label('count')
                    )
                    .where(
                        and_(
                            AnalyticsEvent.timestamp >= start_date,
                            AnalyticsEvent.timestamp <= end_date,
                            AnalyticsEvent.user_id == user_id if user_id else True
                        )
                    )
                    .group_by(func.date(AnalyticsEvent.timestamp))
                    .order_by('date')
                )
                daily_activity = [
                    {"date": str(row.date), "count": row.count}
                    for row in daily_activity_result
                ]

                # Unique users (if not filtered by user_id)
                unique_users = 0
                if not user_id:
                    unique_users_result = await db.execute(
                        select(func.count(func.distinct(AnalyticsEvent.user_id)))
                        .where(
                            and_(
                                AnalyticsEvent.timestamp >= start_date,
                                AnalyticsEvent.timestamp <= end_date
                            )
                        )
                    )
                    unique_users = unique_users_result.scalar()

                return {
                    "period": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat()
                    },
                    "summary": {
                        "total_events": total_events,
                        "unique_users": unique_users,
                        "average_events_per_day": total_events / max(1, (end_date - start_date).days)
                    },
                    "events_by_type": events_by_type,
                    "top_events": top_events,
                    "daily_activity": daily_activity
                }

        except Exception as e:
            raise Exception(f"Error getting dashboard data: {str(e)}")

    async def get_user_usage(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate detailed usage statistics for a specific user.

        Args:
            user_id: User ID to analyze
            start_date: Start date for analysis
            end_date: End date for analysis

        Returns:
            Detailed user usage statistics
        """
        try:
            if not start_date:
                start_date = datetime.utcnow() - timedelta(days=30)
            if not end_date:
                end_date = datetime.utcnow()

            async with AsyncSessionLocal() as db:
                # Basic analytics events
                events_result = await db.execute(
                    select(
                        func.count(AnalyticsEvent.id).label('total_events'),
                        func.count(func.distinct(AnalyticsEvent.session_id)).label('total_sessions'),
                        func.count(func.distinct(AnalyticsEvent.conversation_id)).label('total_conversations')
                    )
                    .where(
                        and_(
                            AnalyticsEvent.user_id == user_id,
                            AnalyticsEvent.timestamp >= start_date,
                            AnalyticsEvent.timestamp <= end_date
                        )
                    )
                )
                events_stats = events_result.first()

                # Conversation statistics
                conversations_result = await db.execute(
                    select(
                        func.count(Conversation.id).label('total_conversations'),
                        func.avg(func.coalesce(Conversation.message_count, 0)).label('avg_messages_per_conversation')
                    )
                    .where(
                        and_(
                            Conversation.user_id == user_id,
                            Conversation.created_at >= start_date,
                            Conversation.created_at <= end_date
                        )
                    )
                )
                conv_stats = conversations_result.first()

                # Message statistics
                messages_result = await db.execute(
                    select(
                        func.count(Message.id).label('total_messages'),
                        func.sum(func.coalesce(Message.token_count, 0)).label('total_tokens')
                    )
                    .join(Conversation)
                    .where(
                        and_(
                            Conversation.user_id == user_id,
                            Message.created_at >= start_date,
                            Message.created_at <= end_date
                        )
                    )
                )
                msg_stats = messages_result.first()

                # Activity by hour
                hourly_activity_result = await db.execute(
                    select(
                        func.extract('hour', AnalyticsEvent.timestamp).label('hour'),
                        func.count(AnalyticsEvent.id).label('count')
                    )
                    .where(
                        and_(
                            AnalyticsEvent.user_id == user_id,
                            AnalyticsEvent.timestamp >= start_date,
                            AnalyticsEvent.timestamp <= end_date
                        )
                    )
                    .group_by(func.extract('hour', AnalyticsEvent.timestamp))
                    .order_by('hour')
                )
                hourly_activity = [
                    {"hour": int(row.hour), "count": row.count}
                    for row in hourly_activity_result
                ]

                # Feature usage
                feature_usage_result = await db.execute(
                    select(
                        AnalyticsEvent.event_name,
                        func.count(AnalyticsEvent.id).label('count')
                    )
                    .where(
                        and_(
                            AnalyticsEvent.user_id == user_id,
                            AnalyticsEvent.timestamp >= start_date,
                            AnalyticsEvent.timestamp <= end_date,
                            AnalyticsEvent.event_type == EventType.USER_ACTION
                        )
                    )
                    .group_by(AnalyticsEvent.event_name)
                    .order_by(desc('count'))
                )
                feature_usage = [
                    {"feature": row.event_name, "count": row.count}
                    for row in feature_usage_result
                ]

                return {
                    "user_id": user_id,
                    "period": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat()
                    },
                    "overview": {
                        "total_events": events_stats.total_events or 0,
                        "total_sessions": events_stats.total_sessions or 0,
                        "total_conversations": conv_stats.total_conversations or 0,
                        "total_messages": msg_stats.total_messages or 0,
                        "total_tokens": msg_stats.total_tokens or 0,
                        "avg_messages_per_conversation": float(conv_stats.avg_messages_per_conversation or 0)
                    },
                    "activity_patterns": {
                        "hourly_activity": hourly_activity,
                        "most_active_hour": max(hourly_activity, key=lambda x: x['count'], default={}).get('hour'),
                        "days_active": len(set(event.timestamp.date() for event in await self._get_user_events(user_id, start_date, end_date)))
                    },
                    "feature_usage": feature_usage[:10],  # Top 10 features
                    "engagement_score": self._calculate_engagement_score(events_stats.total_events or 0, (end_date - start_date).days)
                }

        except Exception as e:
            raise Exception(f"Error calculating user usage: {str(e)}")

    async def export_data(
        self,
        export_type: str = "events",
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format: str = "json"
    ) -> Dict[str, Any]:
        """
        Generate export files for analytics data.

        Args:
            export_type: Type of data to export (events, users, conversations)
            user_id: Optional user ID to filter by
            start_date: Start date for export
            end_date: End date for export
            format: Export format (json, csv)

        Returns:
            Export data and metadata
        """
        try:
            if not start_date:
                start_date = datetime.utcnow() - timedelta(days=30)
            if not end_date:
                end_date = datetime.utcnow()

            async with AsyncSessionLocal() as db:
                export_data = []

                if export_type == "events":
                    query = select(AnalyticsEvent).where(
                        and_(
                            AnalyticsEvent.timestamp >= start_date,
                            AnalyticsEvent.timestamp <= end_date
                        )
                    )
                    if user_id:
                        query = query.where(AnalyticsEvent.user_id == user_id)

                    result = await db.execute(query.order_by(AnalyticsEvent.timestamp))
                    events = result.scalars().all()

                    export_data = [
                        {
                            "id": str(event.id),
                            "user_id": str(event.user_id),
                            "event_type": event.event_type.value,
                            "event_name": event.event_name,
                            "properties": event.properties,
                            "session_id": event.session_id,
                            "conversation_id": event.conversation_id,
                            "timestamp": event.timestamp.isoformat()
                        }
                        for event in events
                    ]

                elif export_type == "user_summary":
                    # Export user summaries
                    if user_id:
                        users = [user_id]
                    else:
                        # Get all users who had activity in the period
                        users_result = await db.execute(
                            select(func.distinct(AnalyticsEvent.user_id))
                            .where(
                                and_(
                                    AnalyticsEvent.timestamp >= start_date,
                                    AnalyticsEvent.timestamp <= end_date
                                )
                            )
                        )
                        users = [str(row[0]) for row in users_result]

                    for uid in users:
                        user_stats = await self.get_user_usage(uid, start_date, end_date)
                        export_data.append(user_stats)

                # Format conversion
                if format == "csv" and export_type == "events":
                    # Convert to CSV format (simplified for this example)
                    csv_data = []
                    if export_data:
                        csv_data.append(",".join(export_data[0].keys()))  # Header
                        for row in export_data:
                            csv_data.append(",".join(str(v) for v in row.values()))
                    export_data = "\n".join(csv_data)

                return {
                    "export_id": str(datetime.utcnow().timestamp()),
                    "export_type": export_type,
                    "format": format,
                    "period": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat()
                    },
                    "record_count": len(export_data) if isinstance(export_data, list) else export_data.count('\n'),
                    "data": export_data,
                    "generated_at": datetime.utcnow().isoformat()
                }

        except Exception as e:
            raise Exception(f"Error exporting analytics data: {str(e)}")

    async def _get_user_events(self, user_id: str, start_date: datetime, end_date: datetime) -> List[AnalyticsEvent]:
        """Get all events for a user in the given period."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AnalyticsEvent)
                .where(
                    and_(
                        AnalyticsEvent.user_id == user_id,
                        AnalyticsEvent.timestamp >= start_date,
                        AnalyticsEvent.timestamp <= end_date
                    )
                )
            )
            return result.scalars().all()

    def _calculate_engagement_score(self, total_events: int, days: int) -> float:
        """Calculate engagement score based on activity."""
        if days <= 0:
            return 0.0

        avg_events_per_day = total_events / days

        # Simple engagement scoring algorithm
        if avg_events_per_day >= 50:
            return 10.0
        elif avg_events_per_day >= 20:
            return 8.0
        elif avg_events_per_day >= 10:
            return 6.0
        elif avg_events_per_day >= 5:
            return 4.0
        elif avg_events_per_day >= 1:
            return 2.0
        else:
            return 1.0

    async def cleanup_old_events(self, retention_days: Optional[int] = None) -> int:
        """
        Clean up old analytics events beyond retention period.

        Args:
            retention_days: Number of days to retain (default: self.retention_days)

        Returns:
            Number of events cleaned up
        """
        retention = retention_days or self.retention_days
        cutoff_date = datetime.utcnow() - timedelta(days=retention)

        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(func.count(AnalyticsEvent.id))
                    .where(AnalyticsEvent.timestamp < cutoff_date)
                )
                count = result.scalar()

                if count > 0:
                    await db.execute(
                        select(AnalyticsEvent)
                        .where(AnalyticsEvent.timestamp < cutoff_date)
                        .delete()
                    )
                    await db.commit()

                return count

        except Exception as e:
            raise Exception(f"Error cleaning up old events: {str(e)}")


# Global analytics service instance
analytics_service = AnalyticsService()