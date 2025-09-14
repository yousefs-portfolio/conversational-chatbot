"""Embedding service for vector similarity search and semantic operations."""

import asyncio
from typing import List, Optional, Dict, Any
import numpy as np
from openai import AsyncOpenAI
import tiktoken
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pgvector.sqlalchemy import Vector

from .config import settings
from .models import Memory, User, Conversation
from .database import AsyncSessionLocal


class EmbeddingService:
    """Service for generating and managing embeddings."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key is required for embeddings")

        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = settings.EMBEDDING_MODEL
        self.dimension = settings.VECTOR_DIMENSION
        self.encoding = tiktoken.encoding_for_model("text-embedding-3-small")

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise Exception(f"Error generating embedding: {str(e)}")

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            raise Exception(f"Error generating embeddings: {str(e)}")

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))

    def chunk_text(self, text: str, max_tokens: int = 8000, overlap: int = 200) -> List[str]:
        """Split text into chunks for embedding."""
        tokens = self.encoding.encode(text)
        chunks = []

        for i in range(0, len(tokens), max_tokens - overlap):
            chunk_tokens = tokens[i:i + max_tokens]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(chunk_text)

        return chunks

    async def similarity_search(
        self,
        query_embedding: List[float],
        user_id: str,
        limit: int = 10,
        threshold: float = 0.7,
        memory_type: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Perform similarity search using cosine similarity."""
        async with AsyncSessionLocal() as db:
            # Build query
            query = select(
                Memory.id,
                Memory.content,
                Memory.memory_type,
                Memory.importance,
                Memory.metadata,
                Memory.created_at,
                func.cosine_distance(Memory.embedding, query_embedding).label("distance")
            ).where(
                Memory.user_id == user_id
            )

            if memory_type:
                query = query.where(Memory.memory_type == memory_type)

            if conversation_id:
                query = query.where(Memory.conversation_id == conversation_id)

            # Order by similarity (lower distance = higher similarity)
            query = query.order_by("distance").limit(limit)

            result = await db.execute(query)
            memories = result.fetchall()

            # Filter by threshold and convert to dicts
            similar_memories = []
            for memory in memories:
                similarity = 1 - memory.distance  # Convert distance to similarity
                if similarity >= threshold:
                    similar_memories.append({
                        "id": str(memory.id),
                        "content": memory.content,
                        "memory_type": memory.memory_type,
                        "importance": memory.importance,
                        "metadata": memory.metadata,
                        "created_at": memory.created_at,
                        "similarity": similarity,
                    })

            return similar_memories


class MemoryService:
    """Service for managing conversational memory with embeddings."""

    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service

    async def store_memory(
        self,
        content: str,
        user_id: str,
        memory_type: str = "episodic",
        importance: int = 1,
        conversation_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a new memory with embedding."""
        # Generate embedding
        embedding = await self.embedding_service.generate_embedding(content)

        # Create memory record
        async with AsyncSessionLocal() as db:
            memory = Memory(
                user_id=user_id,
                conversation_id=conversation_id,
                content=content,
                embedding=embedding,
                memory_type=memory_type,
                importance=importance,
                tags=tags or [],
                metadata=metadata or {}
            )

            db.add(memory)
            await db.commit()
            await db.refresh(memory)

            return str(memory.id)

    async def retrieve_relevant_memories(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
        threshold: float = 0.7,
        memory_type: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve memories relevant to a query."""
        # Generate query embedding
        query_embedding = await self.embedding_service.generate_embedding(query)

        # Search for similar memories
        memories = await self.embedding_service.similarity_search(
            query_embedding=query_embedding,
            user_id=user_id,
            limit=limit,
            threshold=threshold,
            memory_type=memory_type,
            conversation_id=conversation_id
        )

        # Update access count and last_accessed
        if memories:
            memory_ids = [memory["id"] for memory in memories]
            async with AsyncSessionLocal() as db:
                await db.execute(
                    Memory.__table__.update()
                    .where(Memory.id.in_(memory_ids))
                    .values(
                        access_count=Memory.access_count + 1,
                        last_accessed=func.now()
                    )
                )
                await db.commit()

        return memories

    async def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        importance: Optional[int] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update an existing memory."""
        async with AsyncSessionLocal() as db:
            memory = await db.get(Memory, memory_id)
            if not memory:
                return False

            if content is not None:
                memory.content = content
                # Regenerate embedding for new content
                memory.embedding = await self.embedding_service.generate_embedding(content)

            if importance is not None:
                memory.importance = importance

            if tags is not None:
                memory.tags = tags

            if metadata is not None:
                memory.metadata = metadata

            await db.commit()
            return True

    async def delete_memory(self, memory_id: str, user_id: str) -> bool:
        """Delete a memory."""
        async with AsyncSessionLocal() as db:
            memory = await db.get(Memory, memory_id)
            if not memory or str(memory.user_id) != user_id:
                return False

            await db.delete(memory)
            await db.commit()
            return True

    async def get_memory_stats(self, user_id: str) -> Dict[str, Any]:
        """Get memory statistics for a user."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(
                    func.count(Memory.id).label("total_memories"),
                    func.avg(Memory.importance).label("avg_importance"),
                    func.count(Memory.id).filter(Memory.memory_type == "episodic").label("episodic_count"),
                    func.count(Memory.id).filter(Memory.memory_type == "semantic").label("semantic_count"),
                    func.count(Memory.id).filter(Memory.memory_type == "procedural").label("procedural_count"),
                ).where(Memory.user_id == user_id)
            )

            stats = result.fetchone()
            return {
                "total_memories": stats.total_memories or 0,
                "average_importance": float(stats.avg_importance or 0),
                "episodic_memories": stats.episodic_count or 0,
                "semantic_memories": stats.semantic_count or 0,
                "procedural_memories": stats.procedural_count or 0,
            }

    async def cleanup_old_memories(
        self,
        user_id: str,
        days_old: int = 30,
        min_importance: int = 3
    ) -> int:
        """Clean up old, low-importance memories."""
        async with AsyncSessionLocal() as db:
            from datetime import datetime, timedelta

            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            result = await db.execute(
                Memory.__table__.delete()
                .where(
                    Memory.user_id == user_id,
                    Memory.created_at < cutoff_date,
                    Memory.importance < min_importance,
                    Memory.access_count == 0
                )
            )

            await db.commit()
            return result.rowcount


# Global services
embedding_service = EmbeddingService()
memory_service = MemoryService(embedding_service)