"""File management API endpoints."""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...auth import get_current_active_user
from ...database import get_db
from ...models import User
from ...services.file_service import FileService

router = APIRouter(prefix="/files", tags=["files"])
file_service = FileService()


class FileMetadata(BaseModel):
    """File metadata model."""
    filename: str
    size: int
    content_type: str
    tags: Optional[List[str]] = None
    description: Optional[str] = None


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    description: Optional[str] = Query(None, description="File description"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Upload a file to the system.

    Args:
        file: File to upload
        tags: Optional comma-separated tags
        description: Optional file description
        current_user: Authenticated user
        db: Database session

    Returns:
        File upload details and processing status
    """
    try:
        # Parse tags
        parsed_tags = []
        if tags:
            parsed_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Validate file size
        content = await file.read()
        if len(content) > 100 * 1024 * 1024:  # 100MB limit
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File too large. Maximum size is 100MB"
            )

        # Save and process file
        file_data = await file_service.upload_file(
            user_id=str(current_user.id),
            filename=file.filename or "uploaded_file",
            content=content,
            content_type=file.content_type or "application/octet-stream",
            tags=parsed_tags,
            description=description
        )

        return {
            "file_id": file_data["file_id"],
            "filename": file_data["filename"],
            "size": file_data["size"],
            "content_type": file_data["content_type"],
            "status": file_data["status"],
            "upload_url": file_data.get("upload_url"),
            "created_at": file_data["created_at"],
            "tags": parsed_tags,
            "description": description
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )


@router.get("")
async def list_files(
    limit: int = Query(50, le=100, description="Maximum number of files to return"),
    offset: int = Query(0, ge=0, description="Number of files to skip"),
    tags: Optional[str] = Query(None, description="Filter by comma-separated tags"),
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    filename: Optional[str] = Query(None, description="Filter by filename (partial match)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List user's files with optional filtering.

    Args:
        limit: Maximum number of files to return
        offset: Number of files to skip for pagination
        tags: Filter by tags (comma-separated)
        content_type: Filter by content type
        filename: Filter by filename (partial match)
        current_user: Authenticated user
        db: Database session

    Returns:
        List of user's files with metadata
    """
    try:
        # Parse tags filter
        tag_filter = []
        if tags:
            tag_filter = [tag.strip() for tag in tags.split(",") if tag.strip()]

        files_data = await file_service.list_user_files(
            user_id=str(current_user.id),
            limit=limit,
            offset=offset,
            tags=tag_filter if tag_filter else None,
            content_type=content_type,
            filename_filter=filename
        )

        return {
            "files": files_data["files"],
            "total": files_data["total"],
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list files: {str(e)}"
        )


@router.get("/{file_id}")
async def get_file_details(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific file.

    Args:
        file_id: ID of the file
        current_user: Authenticated user
        db: Database session

    Returns:
        Detailed file information and metadata
    """
    try:
        file_data = await file_service.get_file_details(
            file_id=file_id,
            user_id=str(current_user.id)
        )

        if not file_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )

        return file_data

    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file details: {str(e)}"
        )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a file from the system.

    Args:
        file_id: ID of the file to delete
        current_user: Authenticated user
        db: Database session

    Returns:
        Deletion confirmation
    """
    try:
        success = await file_service.delete_file(
            file_id=file_id,
            user_id=str(current_user.id)
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )

        return {"success": True, "message": "File deleted successfully"}

    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Download a file from the system.

    Args:
        file_id: ID of the file to download
        current_user: Authenticated user
        db: Database session

    Returns:
        File content as streaming response
    """
    try:
        download_data = await file_service.get_file_download(
            file_id=file_id,
            user_id=str(current_user.id)
        )

        if not download_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )

        # Create streaming response
        def file_generator():
            with open(download_data["file_path"], "rb") as file:
                while chunk := file.read(8192):  # Read in 8KB chunks
                    yield chunk

        return StreamingResponse(
            file_generator(),
            media_type=download_data["content_type"],
            headers={
                "Content-Disposition": f"attachment; filename=\"{download_data['filename']}\"",
                "Content-Length": str(download_data["size"])
            }
        )

    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file: {str(e)}"
        )