"""Voice processing service for audio upload, transcription, and text-to-speech."""

import asyncio
import os
import uuid
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from ..models import VoiceSession, VoiceSessionStatus, User
from ..database import AsyncSessionLocal
from ..config import settings


class VoiceService:
    """Service for handling voice processing operations."""

    def __init__(self):
        self.supported_audio_formats = {'.mp3', '.wav', '.m4a', '.ogg', '.webm'}
        self.max_file_size = 25 * 1024 * 1024  # 25MB
        self.transcription_timeout = 300  # 5 minutes

    async def process_audio_upload(
        self,
        user_id: str,
        audio_file_path: str,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle audio file upload and initiate transcription process.

        Args:
            user_id: User ID uploading the audio
            audio_file_path: Path to the uploaded audio file
            filename: Original filename
            metadata: Additional metadata for the session

        Returns:
            Dict containing session details and status
        """
        try:
            # Validate file format
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext not in self.supported_audio_formats:
                raise ValueError(f"Unsupported audio format: {file_ext}")

            # Validate file size
            file_size = os.path.getsize(audio_file_path)
            if file_size > self.max_file_size:
                raise ValueError(f"File size exceeds maximum limit of {self.max_file_size} bytes")

            async with AsyncSessionLocal() as db:
                # Create voice session
                session = VoiceSession(
                    user_id=user_id,
                    original_filename=filename,
                    file_path=audio_file_path,
                    file_size=file_size,
                    status=VoiceSessionStatus.UPLOADING,
                    metadata=metadata or {}
                )

                db.add(session)
                await db.commit()
                await db.refresh(session)

                # Update status to processing
                session.status = VoiceSessionStatus.PROCESSING
                await db.commit()

                # Start transcription process (async)
                asyncio.create_task(self._process_transcription(str(session.id)))

                return {
                    "session_id": str(session.id),
                    "status": session.status.value,
                    "filename": filename,
                    "file_size": file_size,
                    "created_at": session.created_at.isoformat()
                }

        except Exception as e:
            # Update session status to failed if session was created
            try:
                async with AsyncSessionLocal() as db:
                    if 'session' in locals():
                        session.status = VoiceSessionStatus.FAILED
                        session.error_message = str(e)
                        await db.commit()
            except:
                pass

            raise Exception(f"Error processing audio upload: {str(e)}")

    async def get_voice_session(self, session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve voice session details.

        Args:
            session_id: Voice session ID
            user_id: User ID (for authorization)

        Returns:
            Session details or None if not found
        """
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(VoiceSession)
                .where(
                    VoiceSession.id == session_id,
                    VoiceSession.user_id == user_id
                )
            )
            session = result.scalar_one_or_none()

            if not session:
                return None

            return {
                "id": str(session.id),
                "user_id": str(session.user_id),
                "original_filename": session.original_filename,
                "file_size": session.file_size,
                "status": session.status.value,
                "transcription": session.transcription,
                "language": session.language,
                "confidence_score": float(session.confidence_score) if session.confidence_score else None,
                "duration_seconds": float(session.duration_seconds) if session.duration_seconds else None,
                "error_message": session.error_message,
                "metadata": session.metadata,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "completed_at": session.completed_at.isoformat() if session.completed_at else None
            }

    async def text_to_speech(
        self,
        text: str,
        user_id: str,
        voice: str = "alloy",
        speed: float = 1.0,
        output_format: str = "mp3"
    ) -> Dict[str, Any]:
        """
        Convert text to audio speech.

        Args:
            text: Text to convert to speech
            user_id: User ID for the request
            voice: Voice model to use
            speed: Speech speed (0.25 to 4.0)
            output_format: Audio output format

        Returns:
            Dict containing audio file path and metadata
        """
        try:
            # Validate input parameters
            if not text.strip():
                raise ValueError("Text cannot be empty")

            if len(text) > 4096:
                raise ValueError("Text exceeds maximum length of 4096 characters")

            if not (0.25 <= speed <= 4.0):
                raise ValueError("Speed must be between 0.25 and 4.0")

            # Generate unique filename
            audio_id = str(uuid.uuid4())
            output_filename = f"tts_{audio_id}.{output_format}"
            output_path = os.path.join(settings.UPLOAD_DIR, "audio", output_filename)

            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Simulate TTS processing (replace with actual TTS API call)
            await asyncio.sleep(1)  # Simulate processing time

            # For now, create a placeholder file (replace with actual audio generation)
            with open(output_path, 'w') as f:
                f.write(f"TTS audio file for: {text[:50]}...")

            return {
                "audio_id": audio_id,
                "file_path": output_path,
                "filename": output_filename,
                "text": text,
                "voice": voice,
                "speed": speed,
                "format": output_format,
                "created_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            raise Exception(f"Error in text-to-speech conversion: {str(e)}")

    async def poll_transcription_status(self, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        Check transcription progress for a voice session.

        Args:
            session_id: Voice session ID
            user_id: User ID (for authorization)

        Returns:
            Status and progress information
        """
        session = await self.get_voice_session(session_id, user_id)
        if not session:
            raise ValueError("Voice session not found")

        return {
            "session_id": session_id,
            "status": session["status"],
            "progress": self._calculate_progress(session["status"]),
            "transcription": session["transcription"],
            "error_message": session["error_message"],
            "updated_at": session["updated_at"]
        }

    async def _process_transcription(self, session_id: str):
        """
        Internal method to process audio transcription.

        Args:
            session_id: Voice session ID to process
        """
        try:
            async with AsyncSessionLocal() as db:
                session = await db.get(VoiceSession, session_id)
                if not session:
                    return

                # Simulate transcription processing
                await asyncio.sleep(5)  # Simulate processing time

                # Mock transcription result (replace with actual transcription service)
                mock_transcription = f"This is a mock transcription for file: {session.original_filename}"

                # Update session with transcription results
                session.transcription = mock_transcription
                session.language = "en"
                session.confidence_score = 0.95
                session.duration_seconds = 30.0
                session.status = VoiceSessionStatus.COMPLETED
                session.completed_at = datetime.utcnow()

                await db.commit()

        except Exception as e:
            # Update session with error
            try:
                async with AsyncSessionLocal() as db:
                    session = await db.get(VoiceSession, session_id)
                    if session:
                        session.status = VoiceSessionStatus.FAILED
                        session.error_message = str(e)
                        await db.commit()
            except:
                pass

    def _calculate_progress(self, status: str) -> int:
        """Calculate progress percentage based on status."""
        progress_map = {
            VoiceSessionStatus.UPLOADING.value: 20,
            VoiceSessionStatus.PROCESSING.value: 60,
            VoiceSessionStatus.COMPLETED.value: 100,
            VoiceSessionStatus.FAILED.value: 0
        }
        return progress_map.get(status, 0)

    async def list_voice_sessions(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        status_filter: Optional[VoiceSessionStatus] = None
    ) -> List[Dict[str, Any]]:
        """
        List voice sessions for a user.

        Args:
            user_id: User ID
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip
            status_filter: Optional status filter

        Returns:
            List of voice session summaries
        """
        async with AsyncSessionLocal() as db:
            query = select(VoiceSession).where(VoiceSession.user_id == user_id)

            if status_filter:
                query = query.where(VoiceSession.status == status_filter)

            query = query.order_by(VoiceSession.created_at.desc()).limit(limit).offset(offset)

            result = await db.execute(query)
            sessions = result.scalars().all()

            return [
                {
                    "id": str(session.id),
                    "original_filename": session.original_filename,
                    "file_size": session.file_size,
                    "status": session.status.value,
                    "language": session.language,
                    "duration_seconds": float(session.duration_seconds) if session.duration_seconds else None,
                    "created_at": session.created_at.isoformat(),
                    "completed_at": session.completed_at.isoformat() if session.completed_at else None
                }
                for session in sessions
            ]

    async def delete_voice_session(self, session_id: str, user_id: str) -> bool:
        """
        Delete a voice session and cleanup associated files.

        Args:
            session_id: Voice session ID
            user_id: User ID (for authorization)

        Returns:
            True if deleted successfully
        """
        async with AsyncSessionLocal() as db:
            session = await db.get(VoiceSession, session_id)
            if not session or str(session.user_id) != user_id:
                return False

            # Cleanup file if exists
            try:
                if session.file_path and os.path.exists(session.file_path):
                    os.remove(session.file_path)
            except Exception as e:
                print(f"Error cleaning up file {session.file_path}: {e}")

            # Delete session from database
            await db.delete(session)
            await db.commit()
            return True


# Global voice service instance
voice_service = VoiceService()