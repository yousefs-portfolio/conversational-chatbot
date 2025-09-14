"""Personalization service for user preference management and adaptive responses."""

import json
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
from sqlalchemy.orm import selectinload

from ..models import (
    PersonalizationProfile, CommunicationStyle, User,
    Conversation, Message, AnalyticsEvent, EventType
)
from ..database import AsyncSessionLocal


class PersonalizationService:
    """Service for managing user personalization and adaptive responses."""

    def __init__(self):
        self.default_profile = {
            "communication_style": CommunicationStyle.BALANCED,
            "response_length_preference": "medium",
            "technical_level": "intermediate",
            "topics_of_interest": [],
            "preferred_features": [],
            "interaction_preferences": {
                "use_examples": True,
                "include_context": True,
                "show_step_by_step": False,
                "prefer_detailed_explanations": False
            }
        }
        self.learning_weight_decay = 0.95  # Decay factor for older interactions

    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Retrieve user's personalization profile.

        Args:
            user_id: User ID

        Returns:
            User's personalization profile
        """
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(PersonalizationProfile)
                    .where(PersonalizationProfile.user_id == user_id)
                )
                profile = result.scalar_one_or_none()

                if not profile:
                    # Create default profile
                    profile_id = await self._create_default_profile(db, user_id)
                    profile = await db.get(PersonalizationProfile, profile_id)

                return {
                    "id": str(profile.id),
                    "user_id": str(profile.user_id),
                    "communication_style": profile.communication_style.value,
                    "response_length_preference": profile.response_length_preference,
                    "technical_level": profile.technical_level,
                    "topics_of_interest": profile.topics_of_interest,
                    "preferred_features": profile.preferred_features,
                    "interaction_preferences": profile.interaction_preferences,
                    "learning_metadata": profile.learning_metadata,
                    "created_at": profile.created_at.isoformat(),
                    "updated_at": profile.updated_at.isoformat(),
                    "last_learned_at": profile.last_learned_at.isoformat() if profile.last_learned_at else None
                }

        except Exception as e:
            raise Exception(f"Error getting user profile: {str(e)}")

    async def update_profile(
        self,
        user_id: str,
        communication_style: Optional[CommunicationStyle] = None,
        response_length_preference: Optional[str] = None,
        technical_level: Optional[str] = None,
        topics_of_interest: Optional[List[str]] = None,
        preferred_features: Optional[List[str]] = None,
        interaction_preferences: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update user's personalization preferences.

        Args:
            user_id: User ID
            communication_style: Preferred communication style
            response_length_preference: Preference for response length
            technical_level: User's technical expertise level
            topics_of_interest: List of topics the user is interested in
            preferred_features: List of preferred features
            interaction_preferences: Interaction preference settings

        Returns:
            True if updated successfully
        """
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(PersonalizationProfile)
                    .where(PersonalizationProfile.user_id == user_id)
                )
                profile = result.scalar_one_or_none()

                if not profile:
                    # Create profile if doesn't exist
                    profile_id = await self._create_default_profile(db, user_id)
                    profile = await db.get(PersonalizationProfile, profile_id)

                # Update profile fields
                if communication_style is not None:
                    profile.communication_style = communication_style

                if response_length_preference is not None:
                    profile.response_length_preference = response_length_preference

                if technical_level is not None:
                    profile.technical_level = technical_level

                if topics_of_interest is not None:
                    profile.topics_of_interest = topics_of_interest

                if preferred_features is not None:
                    profile.preferred_features = preferred_features

                if interaction_preferences is not None:
                    current_prefs = profile.interaction_preferences or {}
                    current_prefs.update(interaction_preferences)
                    profile.interaction_preferences = current_prefs

                await db.commit()
                return True

        except Exception as e:
            raise Exception(f"Error updating profile: {str(e)}")

    async def apply_personalization(
        self,
        user_id: str,
        base_response: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Apply personalization to adapt a response for the user.

        Args:
            user_id: User ID
            base_response: Base response to personalize
            context: Optional context about the interaction

        Returns:
            Personalized response with metadata
        """
        try:
            profile = await self.get_user_profile(user_id)

            # Start with base response
            personalized_response = base_response

            # Apply communication style
            personalized_response = await self._apply_communication_style(
                personalized_response, profile["communication_style"], context
            )

            # Apply length preference
            personalized_response = await self._apply_length_preference(
                personalized_response, profile["response_length_preference"]
            )

            # Apply technical level
            personalized_response = await self._apply_technical_level(
                personalized_response, profile["technical_level"]
            )

            # Apply interaction preferences
            personalized_response = await self._apply_interaction_preferences(
                personalized_response, profile["interaction_preferences"], context
            )

            # Generate personalization metadata
            personalization_applied = []
            if profile["communication_style"] != self.default_profile["communication_style"].value:
                personalization_applied.append(f"communication_style:{profile['communication_style']}")
            if profile["response_length_preference"] != self.default_profile["response_length_preference"]:
                personalization_applied.append(f"length:{profile['response_length_preference']}")
            if profile["technical_level"] != self.default_profile["technical_level"]:
                personalization_applied.append(f"tech_level:{profile['technical_level']}")

            return {
                "original_response": base_response,
                "personalized_response": personalized_response,
                "personalization_applied": personalization_applied,
                "profile_id": profile["id"],
                "applied_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            raise Exception(f"Error applying personalization: {str(e)}")

    async def learn_from_interactions(
        self,
        user_id: str,
        interaction_data: Dict[str, Any],
        feedback_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Learn from user interactions to improve personalization.

        Args:
            user_id: User ID
            interaction_data: Data about the interaction
            feedback_score: Optional explicit feedback score

        Returns:
            Learning results and updated preferences
        """
        try:
            async with AsyncSessionLocal() as db:
                profile = await db.execute(
                    select(PersonalizationProfile)
                    .where(PersonalizationProfile.user_id == user_id)
                )
                profile = profile.scalar_one_or_none()

                if not profile:
                    profile_id = await self._create_default_profile(db, user_id)
                    profile = await db.get(PersonalizationProfile, profile_id)

                # Extract learning signals from interaction
                learning_signals = await self._extract_learning_signals(
                    user_id, interaction_data, feedback_score
                )

                # Update profile based on learning
                updates_made = []

                # Learn communication style preferences
                style_update = await self._learn_communication_style(profile, learning_signals)
                if style_update:
                    updates_made.extend(style_update)

                # Learn length preferences
                length_update = await self._learn_length_preferences(profile, learning_signals)
                if length_update:
                    updates_made.extend(length_update)

                # Learn technical level
                tech_update = await self._learn_technical_level(profile, learning_signals)
                if tech_update:
                    updates_made.extend(tech_update)

                # Learn topic interests
                topic_update = await self._learn_topic_interests(profile, learning_signals)
                if topic_update:
                    updates_made.extend(topic_update)

                # Learn feature preferences
                feature_update = await self._learn_feature_preferences(profile, learning_signals)
                if feature_update:
                    updates_made.extend(feature_update)

                # Update learning metadata
                profile.learning_metadata = profile.learning_metadata or {}
                profile.learning_metadata["total_interactions"] = profile.learning_metadata.get("total_interactions", 0) + 1
                profile.learning_metadata["last_interaction"] = interaction_data
                profile.last_learned_at = datetime.utcnow()

                await db.commit()

                return {
                    "user_id": user_id,
                    "updates_made": updates_made,
                    "total_interactions": profile.learning_metadata["total_interactions"],
                    "learned_at": profile.last_learned_at.isoformat()
                }

        except Exception as e:
            raise Exception(f"Error learning from interactions: {str(e)}")

    async def get_personalization_insights(
        self,
        user_id: str,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get insights about user's personalization and learning progress.

        Args:
            user_id: User ID
            period_days: Period for analysis

        Returns:
            Personalization insights
        """
        try:
            profile = await self.get_user_profile(user_id)
            start_date = datetime.utcnow() - timedelta(days=period_days)

            async with AsyncSessionLocal() as db:
                # Get user's recent interactions
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

                # Analyze personalization effectiveness
                total_messages = sum(len(c.messages) for c in conversations)
                personalized_interactions = profile["learning_metadata"].get("total_interactions", 0)

                # Calculate adaptation score
                adaptation_score = min(10, personalized_interactions / 10) if personalized_interactions else 0

                # Identify learning trends
                learning_trends = self._analyze_learning_trends(profile["learning_metadata"])

                # Generate recommendations
                recommendations = await self._generate_personalization_recommendations(
                    profile, conversations
                )

                return {
                    "user_id": user_id,
                    "period_days": period_days,
                    "current_profile": {
                        "communication_style": profile["communication_style"],
                        "technical_level": profile["technical_level"],
                        "topics_count": len(profile["topics_of_interest"]),
                        "preferred_features_count": len(profile["preferred_features"])
                    },
                    "learning_progress": {
                        "total_interactions": personalized_interactions,
                        "recent_messages": total_messages,
                        "adaptation_score": round(adaptation_score, 1),
                        "last_learned": profile["last_learned_at"]
                    },
                    "trends": learning_trends,
                    "recommendations": recommendations,
                    "generated_at": datetime.utcnow().isoformat()
                }

        except Exception as e:
            raise Exception(f"Error getting personalization insights: {str(e)}")

    async def _create_default_profile(self, db: AsyncSession, user_id: str) -> str:
        """Create a default personalization profile for a user."""
        profile = PersonalizationProfile(
            user_id=user_id,
            communication_style=self.default_profile["communication_style"],
            response_length_preference=self.default_profile["response_length_preference"],
            technical_level=self.default_profile["technical_level"],
            topics_of_interest=self.default_profile["topics_of_interest"],
            preferred_features=self.default_profile["preferred_features"],
            interaction_preferences=self.default_profile["interaction_preferences"],
            learning_metadata={"created_with_defaults": True}
        )

        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        return str(profile.id)

    async def _apply_communication_style(
        self, response: str, style: str, context: Optional[Dict[str, Any]]
    ) -> str:
        """Apply communication style to response."""
        if style == CommunicationStyle.FORMAL.value:
            # Make response more formal (simplified implementation)
            return response.replace("you're", "you are").replace("don't", "do not")
        elif style == CommunicationStyle.CASUAL.value:
            # Make response more casual
            if not response.startswith(("Hey", "Hi", "Hello")):
                return f"Hey! {response}"
        elif style == CommunicationStyle.CONCISE.value:
            # Make response more concise (simplified)
            sentences = response.split('. ')
            if len(sentences) > 3:
                return '. '.join(sentences[:3]) + '.'
        elif style == CommunicationStyle.DETAILED.value:
            # Add more detail (simplified)
            return response + " Let me know if you need any clarification or have follow-up questions!"

        return response

    async def _apply_length_preference(self, response: str, length_pref: str) -> str:
        """Apply length preference to response."""
        if length_pref == "short":
            sentences = response.split('. ')
            if len(sentences) > 2:
                return '. '.join(sentences[:2]) + '.'
        elif length_pref == "long":
            # Add more context (simplified)
            return response + " This approach ensures comprehensive coverage of your needs."

        return response

    async def _apply_technical_level(self, response: str, tech_level: str) -> str:
        """Apply technical level adjustments to response."""
        if tech_level == "beginner":
            # Simplify technical terms (simplified implementation)
            return response.replace("API", "programming interface").replace("database", "data storage")
        elif tech_level == "expert":
            # Keep or add technical terms
            pass

        return response

    async def _apply_interaction_preferences(
        self, response: str, preferences: Dict[str, Any], context: Optional[Dict[str, Any]]
    ) -> str:
        """Apply interaction preferences to response."""
        if preferences.get("use_examples", True) and context and context.get("add_examples"):
            response += "\n\nFor example: " + context.get("example_text", "...")

        if preferences.get("show_step_by_step", False):
            # Convert response to step-by-step format (simplified)
            if ":" in response and len(response) > 100:
                response = response.replace(". ", ".\n\nStep: ")

        return response

    async def _extract_learning_signals(
        self, user_id: str, interaction_data: Dict[str, Any], feedback_score: Optional[float]
    ) -> Dict[str, Any]:
        """Extract learning signals from interaction data."""
        signals = {
            "feedback_score": feedback_score,
            "response_length": len(interaction_data.get("response", "")),
            "user_message_length": len(interaction_data.get("user_message", "")),
            "technical_terms_used": self._count_technical_terms(interaction_data.get("response", "")),
            "conversation_length": interaction_data.get("conversation_length", 1),
            "features_used": interaction_data.get("features_used", []),
            "topics_mentioned": interaction_data.get("topics", [])
        }

        return signals

    async def _learn_communication_style(
        self, profile: PersonalizationProfile, signals: Dict[str, Any]
    ) -> List[str]:
        """Learn communication style preferences from signals."""
        updates = []

        # If user gives positive feedback to detailed responses, prefer detailed style
        if signals.get("feedback_score", 0) > 0.7 and signals.get("response_length", 0) > 500:
            if profile.communication_style != CommunicationStyle.DETAILED:
                profile.communication_style = CommunicationStyle.DETAILED
                updates.append("communication_style:detailed")

        # If user gives negative feedback to long responses, prefer concise
        elif signals.get("feedback_score", 0) < 0.3 and signals.get("response_length", 0) > 300:
            if profile.communication_style != CommunicationStyle.CONCISE:
                profile.communication_style = CommunicationStyle.CONCISE
                updates.append("communication_style:concise")

        return updates

    async def _learn_length_preferences(
        self, profile: PersonalizationProfile, signals: Dict[str, Any]
    ) -> List[str]:
        """Learn length preferences from signals."""
        updates = []

        response_length = signals.get("response_length", 0)
        feedback = signals.get("feedback_score", 0.5)

        if feedback > 0.7:
            if response_length > 800 and profile.response_length_preference != "long":
                profile.response_length_preference = "long"
                updates.append("length_preference:long")
            elif response_length < 200 and profile.response_length_preference != "short":
                profile.response_length_preference = "short"
                updates.append("length_preference:short")

        return updates

    async def _learn_technical_level(
        self, profile: PersonalizationProfile, signals: Dict[str, Any]
    ) -> List[str]:
        """Learn technical level from signals."""
        updates = []

        technical_terms = signals.get("technical_terms_used", 0)
        feedback = signals.get("feedback_score", 0.5)

        if feedback > 0.7 and technical_terms > 5 and profile.technical_level != "expert":
            profile.technical_level = "expert"
            updates.append("technical_level:expert")
        elif feedback < 0.3 and technical_terms > 3 and profile.technical_level != "beginner":
            profile.technical_level = "beginner"
            updates.append("technical_level:beginner")

        return updates

    async def _learn_topic_interests(
        self, profile: PersonalizationProfile, signals: Dict[str, Any]
    ) -> List[str]:
        """Learn topic interests from signals."""
        updates = []

        topics = signals.get("topics_mentioned", [])
        feedback = signals.get("feedback_score", 0.5)

        if feedback > 0.6 and topics:
            current_topics = set(profile.topics_of_interest)
            for topic in topics:
                if topic not in current_topics and len(current_topics) < 20:
                    profile.topics_of_interest.append(topic)
                    current_topics.add(topic)
                    updates.append(f"topic_interest:+{topic}")

        return updates

    async def _learn_feature_preferences(
        self, profile: PersonalizationProfile, signals: Dict[str, Any]
    ) -> List[str]:
        """Learn feature preferences from signals."""
        updates = []

        features = signals.get("features_used", [])
        feedback = signals.get("feedback_score", 0.5)

        if feedback > 0.6 and features:
            current_features = set(profile.preferred_features)
            for feature in features:
                if feature not in current_features and len(current_features) < 10:
                    profile.preferred_features.append(feature)
                    current_features.add(feature)
                    updates.append(f"feature_preference:+{feature}")

        return updates

    def _count_technical_terms(self, text: str) -> int:
        """Count technical terms in text (simplified implementation)."""
        technical_terms = {
            'api', 'database', 'algorithm', 'function', 'variable', 'class',
            'method', 'object', 'array', 'json', 'http', 'server', 'client',
            'framework', 'library', 'repository', 'deployment', 'authentication'
        }
        words = text.lower().split()
        return sum(1 for word in words if word in technical_terms)

    def _analyze_learning_trends(self, learning_metadata: Dict[str, Any]) -> List[str]:
        """Analyze learning trends from metadata."""
        trends = []

        total_interactions = learning_metadata.get("total_interactions", 0)
        if total_interactions > 50:
            trends.append("High engagement - profile is well-adapted")
        elif total_interactions > 10:
            trends.append("Moderate learning - profile is adapting")
        else:
            trends.append("Early stage - collecting preferences")

        return trends

    async def _generate_personalization_recommendations(
        self, profile: Dict[str, Any], conversations: List[Conversation]
    ) -> List[str]:
        """Generate recommendations for improving personalization."""
        recommendations = []

        if len(profile["topics_of_interest"]) < 3:
            recommendations.append("Engage in more varied conversations to improve topic personalization")

        if len(profile["preferred_features"]) < 2:
            recommendations.append("Try different features to help us learn your preferences")

        if not profile["last_learned_at"]:
            recommendations.append("Provide feedback on responses to improve personalization")

        return recommendations


# Global personalization service instance
personalization_service = PersonalizationService()