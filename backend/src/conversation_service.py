"""Conversation management service."""

import json
from typing import List, Dict, Optional, Any, AsyncGenerator
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from .models import Conversation, Message, User
from .database import AsyncSessionLocal
from .llm_service import llm_service, LLMMessage, LLMStreamChunk
from .memory_service import memory_service
from .tool_service import tool_service


class ConversationService:
    """Service for managing conversations and messages."""

    def __init__(self):
        self.default_system_prompt = """You are a helpful, harmless, and honest AI assistant. You have access to various tools that you can use to help users with their requests. Always be clear about what you're doing and ask for clarification when needed."""

    async def create_conversation(
        self,
        user_id: str,
        title: str,
        system_prompt: Optional[str] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new conversation."""
        async with AsyncSessionLocal() as db:
            conversation = Conversation(
                user_id=user_id,
                title=title,
                system_prompt=system_prompt or self.default_system_prompt,
                model=model,
                temperature=str(temperature),
                max_tokens=max_tokens,
                metadata=metadata or {}
            )

            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)

            # Add system message if system prompt is provided
            if conversation.system_prompt:
                await self.add_message(
                    conversation_id=str(conversation.id),
                    role="system",
                    content=conversation.system_prompt
                )

            return str(conversation.id)

    async def get_conversation(self, conversation_id: str, user_id: str) -> Optional[Dict]:
        """Get a conversation with its messages."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Conversation)
                .options(selectinload(Conversation.messages))
                .where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id
                )
            )
            conversation = result.scalar_one_or_none()

            if not conversation:
                return None

            return {
                "id": str(conversation.id),
                "title": conversation.title,
                "system_prompt": conversation.system_prompt,
                "model": conversation.model,
                "temperature": float(conversation.temperature),
                "max_tokens": conversation.max_tokens,
                "metadata": conversation.metadata,
                "is_active": conversation.is_active,
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat(),
                "messages": [
                    {
                        "id": str(msg.id),
                        "role": msg.role,
                        "content": msg.content,
                        "tool_calls": msg.tool_calls,
                        "tool_call_id": msg.tool_call_id,
                        "metadata": msg.metadata,
                        "token_count": msg.token_count,
                        "model": msg.model,
                        "created_at": msg.created_at.isoformat(),
                    }
                    for msg in sorted(conversation.messages, key=lambda m: m.created_at)
                ]
            }

    async def list_conversations(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = True
    ) -> List[Dict]:
        """List conversations for a user."""
        async with AsyncSessionLocal() as db:
            query = select(Conversation).where(Conversation.user_id == user_id)

            if active_only:
                query = query.where(Conversation.is_active == True)

            query = query.order_by(Conversation.updated_at.desc()).limit(limit).offset(offset)

            result = await db.execute(query)
            conversations = result.scalars().all()

            return [
                {
                    "id": str(conv.id),
                    "title": conv.title,
                    "model": conv.model,
                    "is_active": conv.is_active,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "message_count": len(conv.messages) if conv.messages else 0,
                }
                for conv in conversations
            ]

    async def update_conversation(
        self,
        conversation_id: str,
        user_id: str,
        title: Optional[str] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None
    ) -> bool:
        """Update a conversation."""
        async with AsyncSessionLocal() as db:
            conversation = await db.get(Conversation, conversation_id)
            if not conversation or str(conversation.user_id) != user_id:
                return False

            if title is not None:
                conversation.title = title
            if system_prompt is not None:
                conversation.system_prompt = system_prompt
            if model is not None:
                conversation.model = model
            if temperature is not None:
                conversation.temperature = str(temperature)
            if max_tokens is not None:
                conversation.max_tokens = max_tokens
            if metadata is not None:
                conversation.metadata = metadata
            if is_active is not None:
                conversation.is_active = is_active

            await db.commit()
            return True

    async def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Delete a conversation and all its messages."""
        async with AsyncSessionLocal() as db:
            conversation = await db.get(Conversation, conversation_id)
            if not conversation or str(conversation.user_id) != user_id:
                return False

            await db.delete(conversation)
            await db.commit()
            return True

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict]] = None,
        tool_call_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        token_count: Optional[int] = None,
        model: Optional[str] = None
    ) -> str:
        """Add a message to a conversation."""
        async with AsyncSessionLocal() as db:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
                metadata=metadata or {},
                token_count=token_count,
                model=model
            )

            db.add(message)
            await db.commit()
            await db.refresh(message)

            return str(message.id)

    async def get_conversation_messages(
        self,
        conversation_id: str,
        user_id: str,
        limit: Optional[int] = None,
        include_system: bool = True
    ) -> List[LLMMessage]:
        """Get messages from a conversation in LLM format."""
        async with AsyncSessionLocal() as db:
            # Verify user owns the conversation
            conversation = await db.get(Conversation, conversation_id)
            if not conversation or str(conversation.user_id) != user_id:
                return []

            query = select(Message).where(Message.conversation_id == conversation_id)

            if not include_system:
                query = query.where(Message.role != "system")

            query = query.order_by(Message.created_at)

            if limit:
                query = query.limit(limit)

            result = await db.execute(query)
            messages = result.scalars().all()

            return [
                LLMMessage(
                    role=msg.role,
                    content=msg.content,
                    tool_calls=msg.tool_calls,
                    tool_call_id=msg.tool_call_id
                )
                for msg in messages
            ]

    async def generate_response(
        self,
        conversation_id: str,
        user_id: str,
        user_message: str,
        use_tools: bool = True,
        use_memory: bool = True,
        stream: bool = False
    ) -> Dict[str, Any] | AsyncGenerator[Dict[str, Any], None]:
        """Generate AI response for a conversation."""
        # Get conversation
        conversation = await self.get_conversation(conversation_id, user_id)
        if not conversation:
            raise ValueError("Conversation not found")

        # Add user message
        user_message_id = await self.add_message(
            conversation_id=conversation_id,
            role="user",
            content=user_message
        )

        # Retrieve relevant memories if enabled
        relevant_memories = []
        if use_memory:
            try:
                relevant_memories = await memory_service.retrieve_relevant_memories(
                    query=user_message,
                    user_id=user_id,
                    limit=3,
                    threshold=0.7,
                    conversation_id=conversation_id
                )
            except Exception as e:
                print(f"Memory retrieval error: {e}")

        # Build context with memories
        context_content = user_message
        if relevant_memories:
            memory_context = "\n\nRelevant context from previous conversations:\n"
            for memory in relevant_memories:
                memory_context += f"- {memory['content']}\n"
            context_content = memory_context + "\n\nCurrent message: " + user_message

        # Get conversation messages
        messages = await self.get_conversation_messages(conversation_id, user_id)

        # Update the last user message with context
        if messages and messages[-1].role == "user":
            messages[-1].content = context_content

        # Get available tools if enabled
        tools = None
        if use_tools:
            try:
                available_tools = await tool_service.list_tools(user_id)
                if available_tools:
                    tools = [
                        {
                            "type": "function",
                            "function": {
                                "name": tool["name"],
                                "description": tool["description"],
                                "parameters": tool["schema"]
                            }
                        }
                        for tool in available_tools
                    ]
            except Exception as e:
                print(f"Tool loading error: {e}")

        if stream:
            return self._stream_response(
                conversation, messages, tools, conversation_id, user_id, user_message_id, use_memory
            )
        else:
            return await self._generate_single_response(
                conversation, messages, tools, conversation_id, user_id, user_message_id, use_memory
            )

    async def _generate_single_response(
        self,
        conversation: Dict,
        messages: List[LLMMessage],
        tools: Optional[List[Dict]],
        conversation_id: str,
        user_id: str,
        user_message_id: str,
        use_memory: bool
    ) -> Dict[str, Any]:
        """Generate a single response (non-streaming)."""
        try:
            # Generate response
            response = await llm_service.generate_response(
                messages=messages,
                model=conversation["model"],
                temperature=conversation["temperature"],
                max_tokens=conversation["max_tokens"],
                tools=tools
            )

            # Handle tool calls
            if response.tool_calls:
                # Add assistant message with tool calls
                assistant_message_id = await self.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=response.content or "",
                    tool_calls=response.tool_calls,
                    model=response.model,
                    token_count=response.usage.get("completion_tokens")
                )

                # Execute tools
                tool_results = []
                for tool_call in response.tool_calls:
                    try:
                        result = await tool_service.execute_tool(
                            tool_name=tool_call["function"]["name"],
                            parameters=json.loads(tool_call["function"]["arguments"]),
                            user_id=user_id,
                            conversation_id=conversation_id,
                            message_id=assistant_message_id
                        )

                        tool_results.append({
                            "tool_call_id": tool_call["id"],
                            "result": result
                        })

                        # Add tool result message
                        await self.add_message(
                            conversation_id=conversation_id,
                            role="tool",
                            content=json.dumps(result),
                            tool_call_id=tool_call["id"]
                        )

                    except Exception as e:
                        error_result = {"success": False, "error": str(e)}
                        tool_results.append({
                            "tool_call_id": tool_call["id"],
                            "result": error_result
                        })

                        await self.add_message(
                            conversation_id=conversation_id,
                            role="tool",
                            content=json.dumps(error_result),
                            tool_call_id=tool_call["id"]
                        )

                # Generate final response with tool results
                updated_messages = await self.get_conversation_messages(conversation_id, user_id)
                final_response = await llm_service.generate_response(
                    messages=updated_messages,
                    model=conversation["model"],
                    temperature=conversation["temperature"],
                    max_tokens=conversation["max_tokens"]
                )

                # Add final assistant message
                final_message_id = await self.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=final_response.content,
                    model=final_response.model,
                    token_count=final_response.usage.get("completion_tokens")
                )

                response_content = final_response.content
                total_tokens = response.usage.get("total_tokens", 0) + final_response.usage.get("total_tokens", 0)
            else:
                # Add assistant message
                assistant_message_id = await self.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=response.content,
                    model=response.model,
                    token_count=response.usage.get("completion_tokens")
                )

                response_content = response.content
                total_tokens = response.usage.get("total_tokens", 0)

            # Store in memory if enabled
            if use_memory and response_content:
                try:
                    await memory_service.store_memory(
                        content=response_content,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        memory_type="episodic",
                        importance=3
                    )
                except Exception as e:
                    print(f"Memory storage error: {e}")

            return {
                "message_id": assistant_message_id if not response.tool_calls else final_message_id,
                "content": response_content,
                "model": response.model,
                "token_usage": {
                    "total_tokens": total_tokens,
                    "prompt_tokens": response.usage.get("prompt_tokens", 0),
                    "completion_tokens": response.usage.get("completion_tokens", 0)
                },
                "tool_calls": response.tool_calls,
                "finish_reason": response.finish_reason
            }

        except Exception as e:
            # Add error message
            error_message = f"Error generating response: {str(e)}"
            error_message_id = await self.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=error_message
            )

            return {
                "message_id": error_message_id,
                "content": error_message,
                "error": str(e),
                "token_usage": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
            }

    async def _stream_response(
        self,
        conversation: Dict,
        messages: List[LLMMessage],
        tools: Optional[List[Dict]],
        conversation_id: str,
        user_id: str,
        user_message_id: str,
        use_memory: bool
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate streaming response."""
        try:
            accumulated_content = ""
            message_id = None

            async for chunk in llm_service.stream_response(
                messages=messages,
                model=conversation["model"],
                temperature=conversation["temperature"],
                max_tokens=conversation["max_tokens"],
                tools=tools
            ):
                accumulated_content += chunk.content

                # Create message on first chunk
                if message_id is None and chunk.content:
                    message_id = await self.add_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content="",
                        model=conversation["model"]
                    )

                yield {
                    "type": "content",
                    "content": chunk.content,
                    "message_id": message_id,
                    "finish_reason": chunk.finish_reason
                }

                # Handle completion
                if chunk.finish_reason:
                    # Update message with full content
                    if message_id:
                        async with AsyncSessionLocal() as db:
                            await db.execute(
                                update(Message)
                                .where(Message.id == message_id)
                                .values(content=accumulated_content)
                            )
                            await db.commit()

                    # Store in memory if enabled
                    if use_memory and accumulated_content:
                        try:
                            await memory_service.store_memory(
                                content=accumulated_content,
                                user_id=user_id,
                                conversation_id=conversation_id,
                                memory_type="episodic",
                                importance=3
                            )
                        except Exception as e:
                            print(f"Memory storage error: {e}")

                    yield {
                        "type": "done",
                        "message_id": message_id,
                        "content": accumulated_content,
                        "finish_reason": chunk.finish_reason
                    }
                    break

        except Exception as e:
            error_message = f"Error generating response: {str(e)}"
            error_message_id = await self.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=error_message
            )

            yield {
                "type": "error",
                "message_id": error_message_id,
                "content": error_message,
                "error": str(e)
            }


# Global conversation service instance
conversation_service = ConversationService()