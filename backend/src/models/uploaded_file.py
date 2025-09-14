"""Uploaded file model for document and image processing."""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
import uuid

from ..models import Base, TimestampMixin


class FileType(str, Enum):
    """Supported file types."""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    JPG = "jpg"
    PNG = "png"
    GIF = "gif"


class ProcessingStatus(str, Enum):
    """File processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadedFile(Base, TimestampMixin):
    """Document or image file with extracted content and processing status."""
    __tablename__ = "uploaded_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)

    # File details
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(
        ENUM(FileType, name="file_type"),
        nullable=False
    )
    file_size_bytes = Column(Integer, nullable=False)

    # Content processing
    extracted_content = Column(Text)
    processing_status = Column(
        ENUM(ProcessingStatus, name="processing_status"),
        default=ProcessingStatus.PENDING,
        nullable=False
    )
    content_hash = Column(String(64))  # For deduplication

    # Timestamps
    upload_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_timestamp = Column(DateTime)

    # Relationships
    user = relationship("User", backref="uploaded_files")
    conversation = relationship("Conversation", backref="uploaded_files")

    # Indexes for performance
    __table_args__ = (
        Index("idx_uploaded_file_user", "user_id"),
        Index("idx_uploaded_file_conversation", "conversation_id"),
        Index("idx_uploaded_file_status", "processing_status"),
        Index("idx_uploaded_file_type", "file_type"),
        Index("idx_uploaded_file_hash", "content_hash"),
        Index("idx_uploaded_file_upload_time", "upload_timestamp"),
    )

    def __repr__(self):
        return f"<UploadedFile(id={self.id}, filename='{self.original_filename}', status='{self.processing_status}')>"