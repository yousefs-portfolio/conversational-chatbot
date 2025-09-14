"""Application configuration management."""

import os
from typing import Optional, List


class Settings:
    """Application settings with environment variable support."""

    def __init__(self):
        self._load_from_env()

    def _load_from_env(self):
        """Load settings from environment variables."""
        # Application
        self.APP_NAME: str = os.getenv("APP_NAME", "Conversational AI")
        self.APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
        self.DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
        self.API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")

        # Security
        self.SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
        self.ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        self.ALGORITHM: str = os.getenv("ALGORITHM", "HS256")

        # Database
        self.POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
        self.POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
        self.POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "password")
        self.POSTGRES_DB: str = os.getenv("POSTGRES_DB", "conversational_ai")
        self.POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
        self.DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")

        # Build database URL
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

        # Redis
        self.REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
        self.REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
        self.REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
        self.REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
        self.REDIS_URL: Optional[str] = os.getenv("REDIS_URL")

        # Build Redis URL
        if not self.REDIS_URL:
            auth_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
            self.REDIS_URL = f"redis://{auth_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

        # Celery
        self.CELERY_BROKER_URL: Optional[str] = os.getenv("CELERY_BROKER_URL") or self.REDIS_URL
        self.CELERY_RESULT_BACKEND: Optional[str] = os.getenv("CELERY_RESULT_BACKEND") or self.REDIS_URL


        # LLM Providers
        self.OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
        self.ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
        self.GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")

        # Vector Store
        self.EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.VECTOR_DIMENSION: int = int(os.getenv("VECTOR_DIMENSION", "1536"))

        # WebSocket
        self.WS_MESSAGE_QUEUE_SIZE: int = int(os.getenv("WS_MESSAGE_QUEUE_SIZE", "100"))
        self.WS_HEARTBEAT_INTERVAL: int = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))

        # CORS
        cors_origins = os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:3000,http://localhost:8000")
        if isinstance(cors_origins, str) and not cors_origins.startswith("["):
            self.BACKEND_CORS_ORIGINS = [i.strip() for i in cors_origins.split(",")]
        else:
            self.BACKEND_CORS_ORIGINS = ["http://localhost:3000", "http://localhost:8000"]

        # Logging
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FORMAT: str = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        # File uploads (T003)
        self.MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", str(100 * 1024 * 1024)))  # 100MB for documents
        self.MAX_IMAGE_SIZE_MB: int = int(os.getenv("MAX_IMAGE_SIZE_MB", "25"))
        self.MAX_DOCUMENT_SIZE_MB: int = int(os.getenv("MAX_DOCUMENT_SIZE_MB", "100"))
        self.UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/tmp/uploads")
        self.AUDIO_UPLOAD_DIR: str = os.getenv("AUDIO_UPLOAD_DIR", "/tmp/uploads/audio")
        self.DOCUMENT_UPLOAD_DIR: str = os.getenv("DOCUMENT_UPLOAD_DIR", "/tmp/uploads/documents")
        self.IMAGE_UPLOAD_DIR: str = os.getenv("IMAGE_UPLOAD_DIR", "/tmp/uploads/images")
        self.SUPPORTED_DOCUMENT_FORMATS: List[str] = os.getenv("SUPPORTED_DOCUMENT_FORMATS", "pdf,docx,txt").split(",")
        self.SUPPORTED_IMAGE_FORMATS: List[str] = os.getenv("SUPPORTED_IMAGE_FORMATS", "jpg,jpeg,png,gif").split(",")

        # Audio Processing (T002)
        self.MAX_AUDIO_FILE_SIZE_MB: int = int(os.getenv("MAX_AUDIO_FILE_SIZE_MB", "25"))
        self.SUPPORTED_AUDIO_FORMATS: List[str] = os.getenv("SUPPORTED_AUDIO_FORMATS", "wav,mp3,m4a,ogg,flac").split(",")
        self.AUDIO_SAMPLE_RATE: int = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
        self.AUDIO_PROCESSING_TIMEOUT: int = int(os.getenv("AUDIO_PROCESSING_TIMEOUT", "60"))
        self.SPEECH_RECOGNITION_LANGUAGE: str = os.getenv("SPEECH_RECOGNITION_LANGUAGE", "en-US")
        self.SPEECH_RECOGNITION_ACCURACY_THRESHOLD: float = float(os.getenv("SPEECH_RECOGNITION_ACCURACY_THRESHOLD", "0.9"))
        self.TTS_VOICE_SPEED: float = float(os.getenv("TTS_VOICE_SPEED", "1.0"))
        self.TTS_VOICE_ID: str = os.getenv("TTS_VOICE_ID", "default")



settings = Settings()