"""Proactive assistance service for analyzing patterns and generating suggestions."""

import json
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, or_
from sqlalchemy.orm import selectinload

from ..models import (
    ProactiveSuggestion, SuggestionType, UserResponse, User,
    Conversation, Message, AnalyticsEvent, EventType
)
from ..database import AsyncSessionLocal


class ProactiveService:
    """Service for proactive assistance and intelligent suggestions."""

    def __init__(self):
        self.min_pattern_occurrences = 3
        self.suggestion_cooldown_hours = 24
        self.max_suggestions_per_session = 5

    async def analyze_user_patterns(
        self,
        user_id: str,
        analysis_period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze user behavior patterns to identify opportunities for assistance.

        Args:
            user_id: User ID to analyze
            analysis_period_days: Number of days to look back for pattern analysis

        Returns:
            Dict containing identified patterns and insights
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=analysis_period_days)

            async with AsyncSessionLocal() as db:
                # Get user's conversations and messages
                conversations_result = await db.execute(
                    select(Conversation)
                    .options(selectinload(Conversation.messages))
                    .where(
                        and_(
                            Conversation.user_id == user_id,
                            Conversation.created_at >= start_date
                        )
                    )
                )
                conversations = conversations_result.scalars().all()

                # Get user's analytics events
                events_result = await db.execute(
                    select(AnalyticsEvent)
                    .where(
                        and_(
                            AnalyticsEvent.user_id == user_id,
                            AnalyticsEvent.timestamp >= start_date
                        )
                    )
                    .order_by(AnalyticsEvent.timestamp)
                )
                events = events_result.scalars().all()

                # Analyze patterns
                patterns = {
                    "conversation_patterns": await self._analyze_conversation_patterns(conversations),
                    "timing_patterns": self._analyze_timing_patterns(events),
                    "feature_usage_patterns": self._analyze_feature_usage(events),
                    "topic_patterns": self._analyze_topic_patterns(conversations),
                    "difficulty_patterns": self._analyze_difficulty_patterns(conversations, events)
                }

                # Generate insights
                insights = self._generate_pattern_insights(patterns)

                return {
                    "user_id": user_id,
                    "analysis_period": {
                        "start_date": start_date.isoformat(),
                        "end_date": datetime.utcnow().isoformat(),
                        "days": analysis_period_days
                    },
                    "patterns": patterns,
                    "insights": insights,
                    "analyzed_at": datetime.utcnow().isoformat()
                }

        except Exception as e:
            raise Exception(f"Error analyzing user patterns: {str(e)}")

    async def generate_suggestions(
        self,
        user_id: str,
        context: Optional[Dict[str, Any]] = None,
        suggestion_types: Optional[List[SuggestionType]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate contextual suggestions based on user patterns and current context.

        Args:
            user_id: User ID to generate suggestions for
            context: Current context (conversation, session, etc.)
            suggestion_types: Optional filter for suggestion types

        Returns:
            List of generated suggestions
        """
        try:
            async with AsyncSessionLocal() as db:
                # Get recent suggestions to avoid duplicates
                recent_suggestions = await self._get_recent_suggestions(db, user_id)
                recent_suggestion_texts = {s.suggestion_text for s in recent_suggestions}

                # Analyze patterns
                patterns = await self.analyze_user_patterns(user_id)

                # Generate different types of suggestions
                suggestions = []

                # Feature discovery suggestions
                if not suggestion_types or SuggestionType.FEATURE_DISCOVERY in suggestion_types:
                    feature_suggestions = await self._generate_feature_suggestions(
                        patterns, context, recent_suggestion_texts
                    )
                    suggestions.extend(feature_suggestions)

                # Workflow optimization suggestions
                if not suggestion_types or SuggestionType.WORKFLOW_OPTIMIZATION in suggestion_types:
                    workflow_suggestions = await self._generate_workflow_suggestions(
                        patterns, context, recent_suggestion_texts
                    )
                    suggestions.extend(workflow_suggestions)

                # Learning assistance suggestions
                if not suggestion_types or SuggestionType.LEARNING_ASSISTANCE in suggestion_types:
                    learning_suggestions = await self._generate_learning_suggestions(
                        patterns, context, recent_suggestion_texts
                    )
                    suggestions.extend(learning_suggestions)

                # Efficiency tips
                if not suggestion_types or SuggestionType.EFFICIENCY_TIP in suggestion_types:
                    efficiency_suggestions = await self._generate_efficiency_suggestions(
                        patterns, context, recent_suggestion_texts
                    )
                    suggestions.extend(efficiency_suggestions)

                # Store suggestions in database
                suggestion_ids = []
                for suggestion in suggestions[:self.max_suggestions_per_session]:
                    suggestion_id = await self._store_suggestion(db, user_id, suggestion, context)
                    suggestion_ids.append(suggestion_id)
                    suggestion["id"] = suggestion_id

                return suggestions[:self.max_suggestions_per_session]

        except Exception as e:
            raise Exception(f"Error generating suggestions: {str(e)}")

    async def record_response(
        self,
        suggestion_id: str,
        user_id: str,
        response: UserResponse,
        feedback: Optional[str] = None
    ) -> bool:
        """
        Record user response to a proactive suggestion.

        Args:
            suggestion_id: ID of the suggestion
            user_id: User ID (for authorization)
            response: User's response to the suggestion
            feedback: Optional textual feedback

        Returns:
            True if recorded successfully
        """
        try:
            async with AsyncSessionLocal() as db:
                suggestion = await db.get(ProactiveSuggestion, suggestion_id)
                if not suggestion or str(suggestion.user_id) != user_id:
                    return False

                # Update suggestion with user response
                suggestion.user_response = response
                suggestion.feedback = feedback
                suggestion.responded_at = datetime.utcnow()

                # Update effectiveness metrics
                if response == UserResponse.ACCEPTED:
                    suggestion.effectiveness_score = 1.0
                elif response == UserResponse.DISMISSED:
                    suggestion.effectiveness_score = 0.0
                elif response == UserResponse.NOT_RELEVANT:
                    suggestion.effectiveness_score = -0.5

                await db.commit()

                # Learn from response for future suggestions
                await self._update_suggestion_model(db, suggestion, response, feedback)

                return True

        except Exception as e:
            raise Exception(f"Error recording suggestion response: {str(e)}")

    async def calculate_effectiveness(
        self,
        user_id: Optional[str] = None,
        suggestion_type: Optional[SuggestionType] = None,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate effectiveness metrics for proactive suggestions.

        Args:
            user_id: Optional user ID to filter by
            suggestion_type: Optional suggestion type to filter by
            period_days: Period for calculation

        Returns:
            Effectiveness metrics
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=period_days)

            async with AsyncSessionLocal() as db:
                # Build query
                query = select(ProactiveSuggestion).where(
                    ProactiveSuggestion.created_at >= start_date
                )

                if user_id:
                    query = query.where(ProactiveSuggestion.user_id == user_id)

                if suggestion_type:
                    query = query.where(ProactiveSuggestion.suggestion_type == suggestion_type)

                result = await db.execute(query)
                suggestions = result.scalars().all()

                if not suggestions:
                    return {
                        "period_days": period_days,
                        "total_suggestions": 0,
                        "metrics": {}
                    }

                # Calculate metrics
                total_suggestions = len(suggestions)
                responded_suggestions = [s for s in suggestions if s.user_response is not None]
                accepted_suggestions = [s for s in suggestions if s.user_response == UserResponse.ACCEPTED]
                dismissed_suggestions = [s for s in suggestions if s.user_response == UserResponse.DISMISSED]

                response_rate = len(responded_suggestions) / total_suggestions if total_suggestions > 0 else 0
                acceptance_rate = len(accepted_suggestions) / len(responded_suggestions) if responded_suggestions else 0
                dismissal_rate = len(dismissed_suggestions) / len(responded_suggestions) if responded_suggestions else 0

                # Calculate effectiveness by type
                type_effectiveness = {}
                for stype in SuggestionType:
                    type_suggestions = [s for s in suggestions if s.suggestion_type == stype]
                    if type_suggestions:
                        type_accepted = [s for s in type_suggestions if s.user_response == UserResponse.ACCEPTED]
                        type_responded = [s for s in type_suggestions if s.user_response is not None]
                        type_effectiveness[stype.value] = {
                            "total": len(type_suggestions),
                            "responded": len(type_responded),
                            "accepted": len(type_accepted),
                            "acceptance_rate": len(type_accepted) / len(type_responded) if type_responded else 0
                        }

                # Average effectiveness score
                scored_suggestions = [s for s in suggestions if s.effectiveness_score is not None]
                avg_effectiveness_score = (
                    sum(s.effectiveness_score for s in scored_suggestions) / len(scored_suggestions)
                    if scored_suggestions else 0
                )

                return {
                    "period_days": period_days,
                    "total_suggestions": total_suggestions,
                    "metrics": {
                        "response_rate": round(response_rate, 3),
                        "acceptance_rate": round(acceptance_rate, 3),
                        "dismissal_rate": round(dismissal_rate, 3),
                        "avg_effectiveness_score": round(avg_effectiveness_score, 3),
                        "responded_count": len(responded_suggestions),
                        "accepted_count": len(accepted_suggestions),
                        "dismissed_count": len(dismissed_suggestions)
                    },
                    "by_type": type_effectiveness,
                    "calculated_at": datetime.utcnow().isoformat()
                }

        except Exception as e:
            raise Exception(f"Error calculating effectiveness: {str(e)}")

    async def _analyze_conversation_patterns(self, conversations: List[Conversation]) -> Dict[str, Any]:
        """Analyze conversation patterns for insights."""
        if not conversations:
            return {"total_conversations": 0}

        # Basic statistics
        total_conversations = len(conversations)
        avg_messages = sum(len(c.messages) for c in conversations) / total_conversations

        # Conversation length patterns
        lengths = [len(c.messages) for c in conversations]
        short_conversations = len([l for l in lengths if l <= 5])
        medium_conversations = len([l for l in lengths if 5 < l <= 20])
        long_conversations = len([l for l in lengths if l > 20])

        # Time patterns
        creation_hours = [c.created_at.hour for c in conversations]
        peak_hour = Counter(creation_hours).most_common(1)[0][0] if creation_hours else 0

        return {
            "total_conversations": total_conversations,
            "avg_messages_per_conversation": round(avg_messages, 2),
            "length_distribution": {
                "short": short_conversations,
                "medium": medium_conversations,
                "long": long_conversations
            },
            "peak_creation_hour": peak_hour,
            "models_used": list(set(c.model for c in conversations))
        }

    def _analyze_timing_patterns(self, events: List[AnalyticsEvent]) -> Dict[str, Any]:
        """Analyze timing patterns in user activity."""
        if not events:
            return {"total_events": 0}

        # Hour of day patterns
        hours = [e.timestamp.hour for e in events]
        hour_counts = Counter(hours)
        most_active_hours = [hour for hour, count in hour_counts.most_common(3)]

        # Day of week patterns
        weekdays = [e.timestamp.weekday() for e in events]
        weekday_counts = Counter(weekdays)
        most_active_weekdays = [day for day, count in weekday_counts.most_common(3)]

        # Session patterns (approximate)
        sessions = []
        current_session = []
        for event in sorted(events, key=lambda x: x.timestamp):
            if not current_session or (event.timestamp - current_session[-1].timestamp).seconds < 3600:
                current_session.append(event)
            else:
                sessions.append(current_session)
                current_session = [event]
        if current_session:
            sessions.append(current_session)

        avg_session_length = sum(len(s) for s in sessions) / len(sessions) if sessions else 0

        return {
            "total_events": len(events),
            "most_active_hours": most_active_hours,
            "most_active_weekdays": most_active_weekdays,
            "estimated_sessions": len(sessions),
            "avg_events_per_session": round(avg_session_length, 2)
        }

    def _analyze_feature_usage(self, events: List[AnalyticsEvent]) -> Dict[str, Any]:
        """Analyze feature usage patterns."""
        if not events:
            return {"total_events": 0}

        # Event type distribution
        event_types = [e.event_type.value for e in events]
        type_counts = Counter(event_types)

        # Event name distribution
        event_names = [e.event_name for e in events]
        name_counts = Counter(event_names)

        # Unused features (features that appear in few events)
        underused_features = [name for name, count in name_counts.items() if count < 3]

        return {
            "total_events": len(events),
            "event_type_distribution": dict(type_counts),
            "top_features": dict(name_counts.most_common(10)),
            "underused_features": underused_features[:5]
        }

    def _analyze_topic_patterns(self, conversations: List[Conversation]) -> Dict[str, Any]:
        """Analyze conversation topic patterns (simplified)."""
        if not conversations:
            return {"total_conversations": 0}

        # Simple keyword extraction from conversation titles
        titles = [c.title.lower() for c in conversations if c.title]
        all_words = ' '.join(titles).split()
        common_words = [word for word, count in Counter(all_words).most_common(10) if len(word) > 3]

        return {
            "total_conversations_with_titles": len(titles),
            "common_topics": common_words[:5]
        }

    def _analyze_difficulty_patterns(self, conversations: List[Conversation], events: List[AnalyticsEvent]) -> Dict[str, Any]:
        """Analyze patterns indicating user difficulty or confusion."""
        difficulty_indicators = 0

        # Long conversations might indicate complexity
        long_conversations = len([c for c in conversations if len(c.messages) > 20])
        difficulty_indicators += long_conversations

        # Repeated similar questions (simplified check)
        error_events = [e for e in events if 'error' in e.event_name.lower()]
        difficulty_indicators += len(error_events)

        return {
            "long_conversations": long_conversations,
            "error_events": len(error_events),
            "difficulty_score": min(10, difficulty_indicators)  # Cap at 10
        }

    def _generate_pattern_insights(self, patterns: Dict[str, Any]) -> List[str]:
        """Generate human-readable insights from patterns."""
        insights = []

        # Conversation insights
        conv_patterns = patterns.get("conversation_patterns", {})
        if conv_patterns.get("avg_messages_per_conversation", 0) > 15:
            insights.append("You tend to have detailed, in-depth conversations")

        # Timing insights
        timing_patterns = patterns.get("timing_patterns", {})
        most_active_hours = timing_patterns.get("most_active_hours", [])
        if most_active_hours:
            if all(hour < 9 or hour > 17 for hour in most_active_hours[:2]):
                insights.append("You're most active outside typical work hours")

        # Feature usage insights
        feature_patterns = patterns.get("feature_usage_patterns", {})
        underused_features = feature_patterns.get("underused_features", [])
        if underused_features:
            insights.append(f"You might benefit from exploring: {', '.join(underused_features[:2])}")

        # Difficulty insights
        difficulty_patterns = patterns.get("difficulty_patterns", {})
        if difficulty_patterns.get("difficulty_score", 0) > 5:
            insights.append("Consider using help features or tutorials for complex tasks")

        return insights

    async def _generate_feature_suggestions(
        self, patterns: Dict[str, Any], context: Optional[Dict[str, Any]], recent_texts: set
    ) -> List[Dict[str, Any]]:
        """Generate feature discovery suggestions."""
        suggestions = []

        underused_features = patterns.get("feature_usage_patterns", {}).get("underused_features", [])
        for feature in underused_features[:2]:
            suggestion_text = f"Try the {feature} feature to enhance your workflow"
            if suggestion_text not in recent_texts:
                suggestions.append({
                    "type": SuggestionType.FEATURE_DISCOVERY,
                    "title": f"Discover {feature}",
                    "suggestion_text": suggestion_text,
                    "priority": 0.7,
                    "context_data": {"feature": feature}
                })

        return suggestions

    async def _generate_workflow_suggestions(
        self, patterns: Dict[str, Any], context: Optional[Dict[str, Any]], recent_texts: set
    ) -> List[Dict[str, Any]]:
        """Generate workflow optimization suggestions."""
        suggestions = []

        # Suggest shortcuts for frequent actions
        top_features = patterns.get("feature_usage_patterns", {}).get("top_features", {})
        for feature, count in list(top_features.items())[:2]:
            if count > 10:
                suggestion_text = f"Create shortcuts for {feature} - you use it frequently"
                if suggestion_text not in recent_texts:
                    suggestions.append({
                        "type": SuggestionType.WORKFLOW_OPTIMIZATION,
                        "title": "Optimize Your Workflow",
                        "suggestion_text": suggestion_text,
                        "priority": 0.8,
                        "context_data": {"feature": feature, "usage_count": count}
                    })

        return suggestions

    async def _generate_learning_suggestions(
        self, patterns: Dict[str, Any], context: Optional[Dict[str, Any]], recent_texts: set
    ) -> List[Dict[str, Any]]:
        """Generate learning assistance suggestions."""
        suggestions = []

        difficulty_score = patterns.get("difficulty_patterns", {}).get("difficulty_score", 0)
        if difficulty_score > 3:
            suggestion_text = "Check out our help documentation for tips on complex tasks"
            if suggestion_text not in recent_texts:
                suggestions.append({
                    "type": SuggestionType.LEARNING_ASSISTANCE,
                    "title": "Need Help?",
                    "suggestion_text": suggestion_text,
                    "priority": 0.9,
                    "context_data": {"difficulty_score": difficulty_score}
                })

        return suggestions

    async def _generate_efficiency_suggestions(
        self, patterns: Dict[str, Any], context: Optional[Dict[str, Any]], recent_texts: set
    ) -> List[Dict[str, Any]]:
        """Generate efficiency tip suggestions."""
        suggestions = []

        avg_messages = patterns.get("conversation_patterns", {}).get("avg_messages_per_conversation", 0)
        if avg_messages > 20:
            suggestion_text = "Try breaking complex questions into smaller parts for more focused answers"
            if suggestion_text not in recent_texts:
                suggestions.append({
                    "type": SuggestionType.EFFICIENCY_TIP,
                    "title": "Efficiency Tip",
                    "suggestion_text": suggestion_text,
                    "priority": 0.6,
                    "context_data": {"avg_messages": avg_messages}
                })

        return suggestions

    async def _get_recent_suggestions(self, db: AsyncSession, user_id: str) -> List[ProactiveSuggestion]:
        """Get recent suggestions to avoid duplicates."""
        cutoff_date = datetime.utcnow() - timedelta(hours=self.suggestion_cooldown_hours)
        result = await db.execute(
            select(ProactiveSuggestion)
            .where(
                and_(
                    ProactiveSuggestion.user_id == user_id,
                    ProactiveSuggestion.created_at >= cutoff_date
                )
            )
        )
        return result.scalars().all()

    async def _store_suggestion(
        self, db: AsyncSession, user_id: str, suggestion: Dict[str, Any], context: Optional[Dict[str, Any]]
    ) -> str:
        """Store a suggestion in the database."""
        suggestion_record = ProactiveSuggestion(
            user_id=user_id,
            suggestion_type=suggestion["type"],
            title=suggestion["title"],
            suggestion_text=suggestion["suggestion_text"],
            priority=suggestion["priority"],
            context_data=suggestion.get("context_data", {}),
            session_context=context or {}
        )

        db.add(suggestion_record)
        await db.commit()
        await db.refresh(suggestion_record)
        return str(suggestion_record.id)

    async def _update_suggestion_model(
        self, db: AsyncSession, suggestion: ProactiveSuggestion, response: UserResponse, feedback: Optional[str]
    ):
        """Update suggestion model based on user feedback (placeholder for ML model updates)."""
        # In a real implementation, this would update ML models or recommendation algorithms
        # based on user feedback to improve future suggestions
        pass


# Global proactive service instance
proactive_service = ProactiveService()