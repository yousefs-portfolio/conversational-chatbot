"""File processing service for document and image upload, processing, and management."""

import os
import uuid
import asyncio
import mimetypes
from typing import Dict, Optional, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from PIL import Image
import magic

from ..models import UploadedFile, FileType, ProcessingStatus, User
from ..database import AsyncSessionLocal
from ..config import settings


class FileService:
    """Service for handling file upload and processing operations."""

    def __init__(self):
        self.supported_document_types = {
            '.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt',
            '.ppt', '.pptx', '.xls', '.xlsx', '.csv'
        }
        self.supported_image_types = {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg'
        }
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        self.max_image_size = 20 * 1024 * 1024  # 20MB for images

    async def upload_file(
        self,
        user_id: str,
        file_path: str,
        filename: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle file upload and initiate processing.

        Args:
            user_id: User ID uploading the file
            file_path: Path to the uploaded file
            filename: Original filename
            content_type: MIME type of the file
            metadata: Additional metadata for the file

        Returns:
            Dict containing file details and processing status
        """
        try:
            # Validate file exists
            if not os.path.exists(file_path):
                raise ValueError("File does not exist")

            # Get file info
            file_size = os.path.getsize(file_path)
            file_ext = os.path.splitext(filename)[1].lower()

            # Determine file type and validate
            if content_type is None:
                content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

            file_type = self._determine_file_type(file_ext, content_type)

            # Validate file size based on type
            max_size = self.max_image_size if file_type == FileType.IMAGE else self.max_file_size
            if file_size > max_size:
                raise ValueError(f"File size exceeds maximum limit of {max_size} bytes for {file_type.value} files")

            # Validate file type
            if file_type == FileType.DOCUMENT and file_ext not in self.supported_document_types:
                raise ValueError(f"Unsupported document format: {file_ext}")
            elif file_type == FileType.IMAGE and file_ext not in self.supported_image_types:
                raise ValueError(f"Unsupported image format: {file_ext}")

            # Generate secure filename and move file
            secure_filename = f"{uuid.uuid4()}{file_ext}"
            upload_dir = os.path.join(settings.UPLOAD_DIR, file_type.value.lower())
            os.makedirs(upload_dir, exist_ok=True)
            secure_path = os.path.join(upload_dir, secure_filename)

            # Move file to secure location
            os.rename(file_path, secure_path)

            async with AsyncSessionLocal() as db:
                # Create file record
                uploaded_file = UploadedFile(
                    user_id=user_id,
                    original_filename=filename,
                    stored_filename=secure_filename,
                    file_path=secure_path,
                    file_type=file_type,
                    mime_type=content_type,
                    file_size=file_size,
                    status=ProcessingStatus.UPLOADED,
                    metadata=metadata or {}
                )

                db.add(uploaded_file)
                await db.commit()
                await db.refresh(uploaded_file)

                # Start processing
                uploaded_file.status = ProcessingStatus.PROCESSING
                await db.commit()

                # Start async processing
                asyncio.create_task(self._process_file(str(uploaded_file.id)))

                return {
                    "file_id": str(uploaded_file.id),
                    "filename": filename,
                    "file_type": file_type.value,
                    "file_size": file_size,
                    "status": uploaded_file.status.value,
                    "created_at": uploaded_file.created_at.isoformat()
                }

        except Exception as e:
            # Cleanup file if processing failed
            try:
                if 'secure_path' in locals() and os.path.exists(secure_path):
                    os.remove(secure_path)
            except:
                pass

            raise Exception(f"Error uploading file: {str(e)}")

    async def process_document(self, file_id: str, user_id: str) -> Dict[str, Any]:
        """
        Process document to extract text content.

        Args:
            file_id: File ID to process
            user_id: User ID (for authorization)

        Returns:
            Processing results with extracted text
        """
        async with AsyncSessionLocal() as db:
            file_record = await db.get(UploadedFile, file_id)
            if not file_record or str(file_record.user_id) != user_id:
                raise ValueError("File not found")

            if file_record.file_type != FileType.DOCUMENT:
                raise ValueError("File is not a document")

            try:
                # Extract text based on file extension
                extracted_text = await self._extract_text_from_document(file_record.file_path)

                # Update file record
                file_record.extracted_text = extracted_text
                file_record.status = ProcessingStatus.COMPLETED
                file_record.processed_at = datetime.utcnow()

                await db.commit()

                return {
                    "file_id": file_id,
                    "extracted_text": extracted_text,
                    "word_count": len(extracted_text.split()) if extracted_text else 0,
                    "processed_at": file_record.processed_at.isoformat()
                }

            except Exception as e:
                file_record.status = ProcessingStatus.FAILED
                file_record.error_message = str(e)
                await db.commit()
                raise Exception(f"Error processing document: {str(e)}")

    async def process_image(self, file_id: str, user_id: str) -> Dict[str, Any]:
        """
        Process image to analyze content and extract metadata.

        Args:
            file_id: File ID to process
            user_id: User ID (for authorization)

        Returns:
            Processing results with image analysis
        """
        async with AsyncSessionLocal() as db:
            file_record = await db.get(UploadedFile, file_id)
            if not file_record or str(file_record.user_id) != user_id:
                raise ValueError("File not found")

            if file_record.file_type != FileType.IMAGE:
                raise ValueError("File is not an image")

            try:
                # Analyze image
                analysis_result = await self._analyze_image(file_record.file_path)

                # Update file record
                file_record.extracted_text = analysis_result.get('description', '')
                file_record.status = ProcessingStatus.COMPLETED
                file_record.processed_at = datetime.utcnow()
                file_record.metadata.update({
                    'image_analysis': analysis_result,
                    'dimensions': analysis_result.get('dimensions'),
                    'objects_detected': analysis_result.get('objects', [])
                })

                await db.commit()

                return {
                    "file_id": file_id,
                    "analysis": analysis_result,
                    "description": analysis_result.get('description', ''),
                    "objects": analysis_result.get('objects', []),
                    "processed_at": file_record.processed_at.isoformat()
                }

            except Exception as e:
                file_record.status = ProcessingStatus.FAILED
                file_record.error_message = str(e)
                await db.commit()
                raise Exception(f"Error processing image: {str(e)}")

    async def get_file_details(self, file_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve file details with extracted content.

        Args:
            file_id: File ID
            user_id: User ID (for authorization)

        Returns:
            File details or None if not found
        """
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UploadedFile)
                .where(
                    UploadedFile.id == file_id,
                    UploadedFile.user_id == user_id
                )
            )
            file_record = result.scalar_one_or_none()

            if not file_record:
                return None

            return {
                "id": str(file_record.id),
                "user_id": str(file_record.user_id),
                "original_filename": file_record.original_filename,
                "file_type": file_record.file_type.value,
                "mime_type": file_record.mime_type,
                "file_size": file_record.file_size,
                "status": file_record.status.value,
                "extracted_text": file_record.extracted_text,
                "error_message": file_record.error_message,
                "metadata": file_record.metadata,
                "created_at": file_record.created_at.isoformat(),
                "updated_at": file_record.updated_at.isoformat(),
                "processed_at": file_record.processed_at.isoformat() if file_record.processed_at else None
            }

    async def delete_file(self, file_id: str, user_id: str) -> bool:
        """
        Delete file and cleanup associated storage.

        Args:
            file_id: File ID to delete
            user_id: User ID (for authorization)

        Returns:
            True if deleted successfully
        """
        async with AsyncSessionLocal() as db:
            file_record = await db.get(UploadedFile, file_id)
            if not file_record or str(file_record.user_id) != user_id:
                return False

            # Cleanup physical file
            try:
                if os.path.exists(file_record.file_path):
                    os.remove(file_record.file_path)
            except Exception as e:
                print(f"Error cleaning up file {file_record.file_path}: {e}")

            # Delete from database
            await db.delete(file_record)
            await db.commit()
            return True

    async def list_files(
        self,
        user_id: str,
        file_type: Optional[FileType] = None,
        status: Optional[ProcessingStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List files for a user with optional filters.

        Args:
            user_id: User ID
            file_type: Optional file type filter
            status: Optional status filter
            limit: Maximum number of files to return
            offset: Number of files to skip

        Returns:
            List of file summaries
        """
        async with AsyncSessionLocal() as db:
            query = select(UploadedFile).where(UploadedFile.user_id == user_id)

            if file_type:
                query = query.where(UploadedFile.file_type == file_type)

            if status:
                query = query.where(UploadedFile.status == status)

            query = query.order_by(UploadedFile.created_at.desc()).limit(limit).offset(offset)

            result = await db.execute(query)
            files = result.scalars().all()

            return [
                {
                    "id": str(file.id),
                    "original_filename": file.original_filename,
                    "file_type": file.file_type.value,
                    "file_size": file.file_size,
                    "status": file.status.value,
                    "has_extracted_text": bool(file.extracted_text),
                    "created_at": file.created_at.isoformat(),
                    "processed_at": file.processed_at.isoformat() if file.processed_at else None
                }
                for file in files
            ]

    def _determine_file_type(self, file_ext: str, mime_type: str) -> FileType:
        """Determine file type based on extension and MIME type."""
        if file_ext in self.supported_document_types:
            return FileType.DOCUMENT
        elif file_ext in self.supported_image_types:
            return FileType.IMAGE
        elif mime_type.startswith('image/'):
            return FileType.IMAGE
        elif mime_type.startswith('text/') or 'document' in mime_type:
            return FileType.DOCUMENT
        else:
            return FileType.OTHER

    async def _process_file(self, file_id: str):
        """Internal method to process uploaded files."""
        try:
            async with AsyncSessionLocal() as db:
                file_record = await db.get(UploadedFile, file_id)
                if not file_record:
                    return

                if file_record.file_type == FileType.DOCUMENT:
                    await self.process_document(file_id, str(file_record.user_id))
                elif file_record.file_type == FileType.IMAGE:
                    await self.process_image(file_id, str(file_record.user_id))
                else:
                    # Mark as completed for other file types
                    file_record.status = ProcessingStatus.COMPLETED
                    file_record.processed_at = datetime.utcnow()
                    await db.commit()

        except Exception as e:
            # Update file record with error
            try:
                async with AsyncSessionLocal() as db:
                    file_record = await db.get(UploadedFile, file_id)
                    if file_record:
                        file_record.status = ProcessingStatus.FAILED
                        file_record.error_message = str(e)
                        await db.commit()
            except:
                pass

    async def _extract_text_from_document(self, file_path: str) -> str:
        """Extract text from document files."""
        file_ext = os.path.splitext(file_path)[1].lower()

        try:
            if file_ext == '.txt':
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            elif file_ext == '.pdf':
                # Mock PDF text extraction (replace with actual PDF library like PyPDF2)
                return f"Mock extracted text from PDF: {os.path.basename(file_path)}"
            elif file_ext in ['.doc', '.docx']:
                # Mock Word document text extraction (replace with python-docx)
                return f"Mock extracted text from Word document: {os.path.basename(file_path)}"
            elif file_ext in ['.xls', '.xlsx']:
                # Mock Excel text extraction (replace with openpyxl or pandas)
                return f"Mock extracted text from Excel file: {os.path.basename(file_path)}"
            else:
                return f"Text extraction not implemented for {file_ext} files"

        except Exception as e:
            raise Exception(f"Error extracting text from {file_ext}: {str(e)}")

    async def _analyze_image(self, file_path: str) -> Dict[str, Any]:
        """Analyze image content and extract metadata."""
        try:
            # Get basic image info using PIL
            with Image.open(file_path) as img:
                width, height = img.size
                format_name = img.format
                mode = img.mode

            # Mock image analysis (replace with actual computer vision service)
            analysis = {
                "dimensions": {"width": width, "height": height},
                "format": format_name,
                "mode": mode,
                "description": f"An image with dimensions {width}x{height} in {format_name} format",
                "objects": ["mock_object_1", "mock_object_2"],  # Replace with actual object detection
                "colors": ["#FF0000", "#00FF00", "#0000FF"],  # Replace with actual color analysis
                "confidence": 0.85
            }

            return analysis

        except Exception as e:
            raise Exception(f"Error analyzing image: {str(e)}")


# Global file service instance
file_service = FileService()