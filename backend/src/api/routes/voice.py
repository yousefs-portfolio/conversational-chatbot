"""Voice API endpoints."""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...auth import get_current_active_user
from ...database import get_db
from ...models import User
from ...services.voice_service import VoiceService

router = APIRouter(prefix="/voice", tags=["voice"])
voice_service = VoiceService()


class VoiceSessionCreateRequest(BaseModel):
    """Request model for creating a voice session."""
    language: str = "en-US"
    metadata: Optional[Dict[str, Any]] = None


class TextToSpeechRequest(BaseModel):
    """Request model for text-to-speech conversion."""
    text: str
    voice: str = "default"
    language: str = "en-US"
    speed: float = 1.0


@router.post("/sessions")
async def create_voice_session(
    audio_file: UploadFile = File(...),
    language: str = Form("en-US"),
    metadata: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new voice session by uploading an audio file for transcription.

    Args:
        audio_file: Audio file to process
        language: Language for transcription (default: en-US)
        metadata: Optional metadata as JSON string
        current_user: Authenticated user
        db: Database session

    Returns:
        Voice session details with processing status
    """
    try:
        # Parse metadata if provided
        parsed_metadata = None
        if metadata:
            import json
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid metadata format"
                )

        # Save uploaded file temporarily
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{audio_file.filename}") as temp_file:
            content = await audio_file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        # Process audio file
        session_data = await voice_service.process_audio_upload(
            user_id=str(current_user.id),
            audio_file_path=temp_file_path,
            filename=audio_file.filename or "audio_file",
            metadata=parsed_metadata
        )

        return {
            "session_id": session_data["session_id"],
            "status": session_data["status"],
            "filename": audio_file.filename,
            "size": len(content),
            "language": language,
            "created_at": session_data.get("created_at")
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process audio file: {str(e)}"
        )


@router.get("/sessions/{session_id}")
async def get_voice_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get details of a specific voice session.

    Args:
        session_id: ID of the voice session
        current_user: Authenticated user
        db: Database session

    Returns:
        Voice session details including transcription results
    """
    try:
        session_data = await voice_service.get_session_details(
            session_id=session_id,
            user_id=str(current_user.id)
        )

        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice session not found"
            )

        return session_data

    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice session not found"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve voice session: {str(e)}"
        )


@router.post("/text-to-speech")
async def text_to_speech(
    request: TextToSpeechRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Convert text to speech audio.

    Args:
        request: Text-to-speech request parameters
        current_user: Authenticated user
        db: Database session

    Returns:
        Audio file URL or streaming response
    """
    try:
        # Validate text length
        if len(request.text) > 5000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text too long. Maximum 5000 characters allowed."
            )

        if not request.text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text cannot be empty"
            )

        # Generate speech
        audio_data = await voice_service.text_to_speech(
            text=request.text,
            user_id=str(current_user.id),
            voice=request.voice,
            language=request.language,
            speed=request.speed
        )

        return {
            "audio_url": audio_data["audio_url"],
            "duration": audio_data.get("duration"),
            "format": audio_data.get("format", "mp3"),
            "size": audio_data.get("size"),
            "expires_at": audio_data.get("expires_at")
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate speech: {str(e)}"
        )