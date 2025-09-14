"""Background tasks using Celery."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from celery import Celery
from celery.schedules import crontab
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal, AsyncSessionLocal
from .models import Memory, ToolExecution, Message, Conversation, User
from .embedding_service import memory_service
from .llm_service import llm_service, LLMMessage


# Create Celery app
celery_app = Celery(
    "conversational_ai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["src.tasks"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
)

# Periodic tasks
celery_app.conf.beat_schedule = {
    "cleanup-old-memories": {
        "task": "src.tasks.cleanup_old_memories",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    "cleanup-failed-executions": {
        "task": "src.tasks.cleanup_failed_executions",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    "generate-conversation-summaries": {
        "task": "src.tasks.generate_conversation_summaries",
        "schedule": crontab(hour=1, minute=0),  # Daily at 1 AM
    },
}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_long_running_tool(self, tool_name: str, parameters: Dict[str, Any], user_id: str, execution_id: str):
    """Process long-running tool execution."""
    try:
        from .tool_service import tool_service

        # This would be implemented for tools that need background processing
        # For now, we'll just simulate the process

        result = {
            "success": True,
            "message": f"Background processing completed for {tool_name}",
            "parameters": parameters,
            "processed_at": datetime.utcnow().isoformat()
        }

        # Update execution record
        with SessionLocal() as db:
            from .models import ToolExecution
            execution = db.query(ToolExecution).filter(ToolExecution.id == execution_id).first()
            if execution:
                execution.result = result
                execution.status = "completed"
                execution.execution_time = 5000  # 5 seconds
                db.commit()

        return result

    except Exception as exc:
        # Retry the task
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        # Mark as failed
        with SessionLocal() as db:
            from .models import ToolExecution
            execution = db.query(ToolExecution).filter(ToolExecution.id == execution_id).first()
            if execution:
                execution.status = "failed"
                execution.error = str(exc)
                db.commit()

        raise exc


@celery_app.task(bind=True)
def generate_embeddings_batch(self, texts: list[str], user_id: str, conversation_id: Optional[str] = None):
    """Generate embeddings for a batch of texts."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        from .embedding_service import embedding_service

        # Generate embeddings
        embeddings = loop.run_until_complete(
            embedding_service.generate_embeddings(texts)
        )

        # Store memories
        memory_ids = []
        for text, embedding in zip(texts, embeddings):
            memory_id = loop.run_until_complete(
                memory_service.store_memory(
                    content=text,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    memory_type="episodic",
                    importance=2
                )
            )
            memory_ids.append(memory_id)

        return {
            "success": True,
            "memory_ids": memory_ids,
            "count": len(memory_ids)
        }

    except Exception as exc:
        return {
            "success": False,
            "error": str(exc)
        }
    finally:
        if loop.is_running():
            loop.close()


@celery_app.task
def cleanup_old_memories():
    """Clean up old, low-importance memories."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        with SessionLocal() as db:
            users = db.query(User).all()
            total_cleaned = 0

            for user in users:
                cleaned_count = loop.run_until_complete(
                    memory_service.cleanup_old_memories(
                        user_id=str(user.id),
                        days_old=30,
                        min_importance=3
                    )
                )
                total_cleaned += cleaned_count

        return {
            "success": True,
            "memories_cleaned": total_cleaned
        }

    except Exception as exc:
        return {
            "success": False,
            "error": str(exc)
        }
    finally:
        if loop.is_running():
            loop.close()


@celery_app.task
def cleanup_failed_executions():
    """Clean up old failed tool executions."""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=7)

        with SessionLocal() as db:
            result = db.execute(
                delete(ToolExecution).where(
                    ToolExecution.status == "failed",
                    ToolExecution.created_at < cutoff_date
                )
            )
            deleted_count = result.rowcount
            db.commit()

        return {
            "success": True,
            "executions_cleaned": deleted_count
        }

    except Exception as exc:
        return {
            "success": False,
            "error": str(exc)
        }


@celery_app.task(bind=True)
def generate_conversation_summaries(self):
    """Generate summaries for long conversations."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        with SessionLocal() as db:
            # Find conversations with many messages that don't have summaries
            conversations = db.query(Conversation).join(Message).group_by(Conversation.id).having(
                db.func.count(Message.id) > 20
            ).filter(
                ~Conversation.metadata.has_key('summary')
            ).limit(10).all()

            summarized_count = 0

            for conversation in conversations:
                try:
                    # Get messages
                    messages = db.query(Message).filter(
                        Message.conversation_id == conversation.id
                    ).order_by(Message.created_at).all()

                    # Create context for summarization
                    conversation_text = "\n".join([
                        f"{msg.role}: {msg.content}"
                        for msg in messages
                        if msg.role in ["user", "assistant"]
                    ])

                    # Generate summary using LLM
                    summary_prompt = f"""Please provide a concise summary of this conversation:

{conversation_text}

Summary should be 2-3 sentences focusing on the main topics discussed and outcomes."""

                    summary_messages = [
                        LLMMessage(role="user", content=summary_prompt)
                    ]

                    response = loop.run_until_complete(
                        llm_service.generate_response(
                            messages=summary_messages,
                            model="gpt-3.5-turbo",
                            temperature=0.3,
                            max_tokens=200
                        )
                    )

                    # Store summary in metadata
                    if not conversation.metadata:
                        conversation.metadata = {}

                    conversation.metadata['summary'] = {
                        'content': response.content,
                        'generated_at': datetime.utcnow().isoformat(),
                        'message_count': len(messages)
                    }

                    db.commit()
                    summarized_count += 1

                except Exception as e:
                    print(f"Error summarizing conversation {conversation.id}: {e}")
                    continue

        return {
            "success": True,
            "conversations_summarized": summarized_count
        }

    except Exception as exc:
        return {
            "success": False,
            "error": str(exc)
        }
    finally:
        if loop.is_running():
            loop.close()


@celery_app.task(bind=True)
def process_file_upload(self, file_path: str, user_id: str, file_type: str):
    """Process uploaded files for content extraction and embedding."""
    try:
        import os
        from .embedding_service import embedding_service

        # Read file content based on type
        content = ""
        if file_type == "text":
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        elif file_type == "pdf":
            # Would implement PDF extraction here
            content = "PDF content extraction not implemented"
        elif file_type == "docx":
            # Would implement DOCX extraction here
            content = "DOCX content extraction not implemented"

        # Chunk content for processing
        loop = asyncio.get_event_loop()
        chunks = embedding_service.chunk_text(content, max_tokens=500)

        # Store each chunk as memory
        memory_ids = []
        for i, chunk in enumerate(chunks):
            memory_id = loop.run_until_complete(
                memory_service.store_memory(
                    content=chunk,
                    user_id=user_id,
                    memory_type="semantic",
                    importance=4,
                    tags=["uploaded_file", file_type],
                    metadata={
                        "source_file": os.path.basename(file_path),
                        "chunk_index": i,
                        "total_chunks": len(chunks)
                    }
                )
            )
            memory_ids.append(memory_id)

        # Clean up temporary file
        try:
            os.remove(file_path)
        except:
            pass

        return {
            "success": True,
            "memory_ids": memory_ids,
            "chunks_processed": len(chunks)
        }

    except Exception as exc:
        return {
            "success": False,
            "error": str(exc)
        }


@celery_app.task(bind=True)
def analyze_user_patterns(self, user_id: str):
    """Analyze user interaction patterns and preferences."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        with SessionLocal() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "error": "User not found"}

            # Get user's conversations and messages
            conversations = db.query(Conversation).filter(Conversation.user_id == user_id).all()
            total_messages = 0
            total_tools_used = 0
            favorite_models = {}
            topics = []

            for conv in conversations:
                messages = db.query(Message).filter(Message.conversation_id == conv.id).all()
                total_messages += len(messages)

                # Count model usage
                if conv.model in favorite_models:
                    favorite_models[conv.model] += 1
                else:
                    favorite_models[conv.model] = 1

                # Count tool usage
                for msg in messages:
                    if msg.tool_calls:
                        total_tools_used += len(msg.tool_calls)

            # Update user preferences with analysis
            analysis = {
                "total_conversations": len(conversations),
                "total_messages": total_messages,
                "total_tools_used": total_tools_used,
                "favorite_models": favorite_models,
                "analysis_date": datetime.utcnow().isoformat()
            }

            if not user.preferences:
                user.preferences = {}

            user.preferences["usage_analysis"] = analysis
            db.commit()

            return {
                "success": True,
                "analysis": analysis
            }

    except Exception as exc:
        return {
            "success": False,
            "error": str(exc)
        }
    finally:
        if loop.is_running():
            loop.close()


# Task monitoring functions
def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get status of a Celery task."""
    result = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
        "traceback": result.traceback if result.failed() else None,
    }


def get_active_tasks() -> list[Dict[str, Any]]:
    """Get list of active tasks."""
    inspect = celery_app.control.inspect()
    active_tasks = inspect.active()

    if not active_tasks:
        return []

    all_active = []
    for worker, tasks in active_tasks.items():
        for task in tasks:
            all_active.append({
                "worker": worker,
                "task_id": task["id"],
                "name": task["name"],
                "args": task["args"],
                "kwargs": task["kwargs"],
            })

    return all_active


def cancel_task(task_id: str) -> bool:
    """Cancel a running task."""
    try:
        celery_app.control.revoke(task_id, terminate=True)
        return True
    except Exception:
        return False