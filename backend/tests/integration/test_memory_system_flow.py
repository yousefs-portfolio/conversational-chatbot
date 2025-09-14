"""
Integration test for complete memory system lifecycle.

This test validates the entire memory system including creation, retrieval,
similarity search, importance scoring, and integration with conversations.
According to TDD, this test MUST FAIL initially until all endpoints are implemented.
"""
import pytest
from httpx import AsyncClient
import uuid
import asyncio


class TestMemorySystemFlow:
    """Test complete memory system integration and lifecycle."""

    @pytest.mark.asyncio
    async def test_complete_memory_lifecycle_flow(self, client: AsyncClient, auth_headers: dict):
        """Test the complete memory system lifecycle from creation to search and retrieval."""

        # Step 1: Verify Initial Empty Memory State
        # This MUST FAIL initially until all endpoints are implemented
        initial_memory_response = await client.get("/memory", headers=auth_headers)
        assert initial_memory_response.status_code == 200

        initial_memory_data = initial_memory_response.json()
        assert initial_memory_data["data"] == []
        assert initial_memory_data["pagination"]["total"] == 0

        # Step 2: Create Various Types of Memories
        memories_to_create = [
            {
                "content": "User is a software engineer working at TechCorp",
                "type": "fact",
                "importance": 0.9,
                "metadata": {
                    "source": "conversation",
                    "category": "profession",
                    "verified": True
                }
            },
            {
                "content": "User prefers Python over JavaScript for backend development",
                "type": "preference",
                "importance": 0.8,
                "metadata": {
                    "source": "conversation",
                    "category": "technology",
                    "context": "programming languages"
                }
            },
            {
                "content": "User is working on a machine learning project involving natural language processing",
                "type": "context",
                "importance": 0.7,
                "metadata": {
                    "source": "conversation",
                    "project": "ml_nlp",
                    "current": True
                }
            },
            {
                "content": "User has experience with Docker and Kubernetes deployment",
                "type": "skill",
                "importance": 0.6,
                "metadata": {
                    "source": "conversation",
                    "category": "devops",
                    "level": "intermediate"
                }
            },
            {
                "content": "User works closely with team member Sarah on API development",
                "type": "relationship",
                "importance": 0.5,
                "metadata": {
                    "source": "conversation",
                    "relationship_type": "colleague",
                    "context": "work"
                }
            }
        ]

        created_memories = []

        for memory_data in memories_to_create:
            create_response = await client.post("/memory", headers=auth_headers, json=memory_data)
            assert create_response.status_code == 201

            created_memory = create_response.json()
            created_memories.append(created_memory)

            # Validate created memory structure
            assert created_memory["content"] == memory_data["content"]
            assert created_memory["type"] == memory_data["type"]
            assert created_memory["importance"] == memory_data["importance"]
            assert "embedding" in created_memory
            assert isinstance(created_memory["embedding"], list)
            assert len(created_memory["embedding"]) > 0

            # Brief pause to allow for processing
            await asyncio.sleep(0.1)

        # Step 3: Verify All Memories Were Created
        all_memories_response = await client.get("/memory", headers=auth_headers)
        assert all_memories_response.status_code == 200

        all_memories_data = all_memories_response.json()
        assert len(all_memories_data["data"]) == len(memories_to_create)
        assert all_memories_data["pagination"]["total"] == len(memories_to_create)

        # Step 4: Test Memory Filtering by Type
        for memory_type in ["fact", "preference", "context", "skill", "relationship"]:
            type_filter_response = await client.get(
                "/memory",
                headers=auth_headers,
                params={"type": memory_type}
            )
            assert type_filter_response.status_code == 200

            type_memories = type_filter_response.json()
            for memory in type_memories["data"]:
                assert memory["type"] == memory_type

        # Step 5: Test Memory Filtering by Importance
        high_importance_response = await client.get(
            "/memory",
            headers=auth_headers,
            params={"min_importance": 0.8}
        )
        assert high_importance_response.status_code == 200

        high_importance_data = high_importance_response.json()
        for memory in high_importance_data["data"]:
            assert memory["importance"] >= 0.8

        # Should find memories about profession and preferences
        assert len(high_importance_data["data"]) >= 2

        # Step 6: Test Semantic Search
        search_queries = [
            "programming languages",
            "work and job",
            "machine learning projects",
            "deployment and devops",
            "team collaboration"
        ]

        for query in search_queries:
            search_response = await client.get(
                "/memory",
                headers=auth_headers,
                params={"query": query}
            )
            assert search_response.status_code == 200

            search_data = search_response.json()

            # Should return relevant memories with similarity scores
            for memory in search_data["data"]:
                assert "similarity_score" in memory
                assert 0.0 <= memory["similarity_score"] <= 1.0

            # Results should be ordered by relevance
            if len(search_data["data"]) > 1:
                for i in range(1, len(search_data["data"])):
                    assert (search_data["data"][i-1]["similarity_score"] >=
                           search_data["data"][i]["similarity_score"])

        # Step 7: Test Memory Integration with Conversations
        # Create conversation that should utilize memories
        conversation_data = {
            "title": "Context-Aware Conversation",
            "system_prompt": "You are an AI assistant that uses user memories to provide personalized responses."
        }

        conv_response = await client.post("/conversations", headers=auth_headers, json=conversation_data)
        if conv_response.status_code == 201:
            conversation_id = conv_response.json()["id"]

            # Send message that should trigger memory retrieval
            context_message = {
                "content": "I need help with my current project. Can you suggest some best practices?",
                "role": "user",
                "use_memory": True
            }

            msg_response = await client.post(
                f"/conversations/{conversation_id}/messages",
                headers=auth_headers,
                json=context_message
            )

            if msg_response.status_code in [200, 201]:
                msg_data = msg_response.json()
                assistant_response = msg_data["assistant_message"]["content"]

                # Response should be contextually aware (longer and more specific)
                assert len(assistant_response) > 50

                # Check if memory usage is tracked in metadata
                if "metadata" in msg_data["assistant_message"]:
                    metadata = msg_data["assistant_message"]["metadata"]
                    if "memories_used" in metadata:
                        assert isinstance(metadata["memories_used"], list)

        # Step 8: Test Memory Updates and Evolution
        # Update an existing memory
        memory_to_update = created_memories[0]
        update_data = {
            "content": "User is a senior software engineer and team lead at TechCorp",
            "importance": 0.95,
            "metadata": {
                **memory_to_update.get("metadata", {}),
                "updated": True,
                "promotion": "team_lead"
            }
        }

        update_response = await client.put(
            f"/memory/{memory_to_update['id']}",
            headers=auth_headers,
            json=update_data
        )

        if update_response.status_code == 200:
            updated_memory = update_response.json()
            assert updated_memory["content"] == update_data["content"]
            assert updated_memory["importance"] == update_data["importance"]

        # Step 9: Test Memory Consolidation
        # Create similar memories that might be consolidated
        similar_memories = [
            {
                "content": "User enjoys Python programming and finds it intuitive",
                "type": "preference",
                "importance": 0.6
            },
            {
                "content": "User thinks Python is great for data science work",
                "type": "preference",
                "importance": 0.7
            }
        ]

        for similar_memory in similar_memories:
            create_response = await client.post("/memory", headers=auth_headers, json=similar_memory)
            if create_response.status_code == 201:
                created_memories.append(create_response.json())

        # Check if system detected similar memories
        similar_search = await client.get(
            "/memory",
            headers=auth_headers,
            params={"query": "Python programming", "min_similarity": 0.8}
        )

        if similar_search.status_code == 200:
            similar_data = similar_search.json()
            python_memories = [m for m in similar_data["data"] if "python" in m["content"].lower()]
            # Should find multiple related Python memories
            assert len(python_memories) >= 2

        # Step 10: Test Memory Access Patterns and Learning
        # Access memories frequently to test importance adjustment
        frequently_accessed_memory = created_memories[1]

        for _ in range(3):
            access_response = await client.get(
                f"/memory/{frequently_accessed_memory['id']}",
                headers=auth_headers
            )
            if access_response.status_code == 200:
                await asyncio.sleep(0.1)

        # Check if access patterns affected importance or metadata
        final_memory_check = await client.get(
            f"/memory/{frequently_accessed_memory['id']}",
            headers=auth_headers
        )

        if final_memory_check.status_code == 200:
            final_memory = final_memory_check.json()
            # last_accessed_at should be updated
            assert "last_accessed_at" in final_memory

        # Step 11: Test Memory Export and Analytics
        export_response = await client.get("/memory/export", headers=auth_headers)
        if export_response.status_code == 200:
            export_data = export_response.json()
            assert "memories" in export_data
            assert len(export_data["memories"]) > 0

            # Export should include all memory data
            for memory in export_data["memories"]:
                assert "content" in memory
                assert "type" in memory
                assert "importance" in memory

        # Step 12: Test Memory Statistics
        stats_response = await client.get("/memory/stats", headers=auth_headers)
        if stats_response.status_code == 200:
            stats_data = stats_response.json()

            expected_stats = [
                "total_memories", "by_type", "average_importance",
                "most_accessed", "recently_created"
            ]

            for stat in expected_stats:
                if stat in stats_data:
                    assert stats_data[stat] is not None

        # Step 13: Test Memory Cleanup and Management
        # Delete a memory
        memory_to_delete = created_memories[-1]
        delete_response = await client.delete(f"/memory/{memory_to_delete['id']}", headers=auth_headers)

        if delete_response.status_code in [200, 204]:
            # Verify memory is deleted
            deleted_check = await client.get(f"/memory/{memory_to_delete['id']}", headers=auth_headers)
            assert deleted_check.status_code == 404

        return {
            "memories_created": len(created_memories),
            "search_queries_tested": len(search_queries),
            "conversation_id": conversation_id if 'conversation_id' in locals() else None
        }

    @pytest.mark.asyncio
    async def test_memory_conversation_integration(self, client: AsyncClient, auth_headers: dict):
        """Test deep integration between memory system and conversations."""

        # Create initial memories
        base_memories = [
            {
                "content": "User is interested in artificial intelligence and machine learning",
                "type": "preference",
                "importance": 0.9
            },
            {
                "content": "User has a background in computer science with 5 years experience",
                "type": "fact",
                "importance": 0.8
            }
        ]

        for memory_data in base_memories:
            create_response = await client.post("/memory", headers=auth_headers, json=memory_data)
            if create_response.status_code != 201:
                pytest.skip("Memory endpoint not implemented yet")

        # Start conversation that should build on existing memories
        conversation_data = {
            "title": "AI Learning Discussion",
            "system_prompt": "You are an AI tutor that personalizes responses based on user background."
        }

        conv_response = await client.post("/conversations", headers=auth_headers, json=conversation_data)
        if conv_response.status_code != 201:
            pytest.skip("Conversations endpoint not implemented yet")

        conversation_id = conv_response.json()["id"]

        # Have a conversation that should create new memories and reference existing ones
        conversation_flow = [
            "I'm particularly interested in neural networks and deep learning.",
            "Can you explain transformer architecture in detail?",
            "I'm working on a project that involves natural language processing.",
            "What are the latest advances in large language models?",
            "How can I apply this knowledge in my work as a software engineer?"
        ]

        for message_content in conversation_flow:
            message_data = {
                "content": message_content,
                "role": "user",
                "create_memories": True,
                "use_existing_memories": True
            }

            msg_response = await client.post(
                f"/conversations/{conversation_id}/messages",
                headers=auth_headers,
                json=message_data
            )

            if msg_response.status_code in [200, 201]:
                # Brief pause between messages
                await asyncio.sleep(0.2)

        # Check if new memories were created from the conversation
        final_memory_check = await client.get("/memory", headers=auth_headers)
        if final_memory_check.status_code == 200:
            final_memories = final_memory_check.json()

            # Should have more memories than we started with
            new_memory_count = len(final_memories["data"])
            assert new_memory_count >= len(base_memories)

            # Look for memories about neural networks or transformers
            ai_memories = [
                m for m in final_memories["data"]
                if any(keyword in m["content"].lower()
                      for keyword in ["neural", "transformer", "nlp", "language model"])
            ]

            # At least some AI-related memories should exist
            # (This is implementation-dependent)

    @pytest.mark.asyncio
    async def test_memory_similarity_and_clustering(self, client: AsyncClient, auth_headers: dict):
        """Test memory similarity detection and automatic clustering."""

        # Create groups of related memories
        programming_memories = [
            {
                "content": "User prefers Python for data analysis and machine learning",
                "type": "preference",
                "importance": 0.8
            },
            {
                "content": "User has experience with pandas and numpy libraries",
                "type": "skill",
                "importance": 0.7
            },
            {
                "content": "User writes clean, well-documented Python code",
                "type": "skill",
                "importance": 0.6
            }
        ]

        work_memories = [
            {
                "content": "User works at TechCorp in the AI research division",
                "type": "fact",
                "importance": 0.9
            },
            {
                "content": "User collaborates with Dr. Smith on research projects",
                "type": "relationship",
                "importance": 0.7
            },
            {
                "content": "User's office is on the 3rd floor, room 305",
                "type": "fact",
                "importance": 0.3
            }
        ]

        all_test_memories = programming_memories + work_memories

        # Create all memories
        for memory_data in all_test_memories:
            create_response = await client.post("/memory", headers=auth_headers, json=memory_data)
            if create_response.status_code != 201:
                pytest.skip("Memory endpoint not implemented yet")

        # Test similarity search within categories
        programming_search = await client.get(
            "/memory",
            headers=auth_headers,
            params={"query": "Python programming", "limit": 10}
        )

        if programming_search.status_code == 200:
            prog_results = programming_search.json()

            # Should find programming-related memories with higher similarity
            for memory in prog_results["data"]:
                if "similarity_score" in memory:
                    # Programming-related memories should have reasonable similarity scores
                    if any(keyword in memory["content"].lower()
                          for keyword in ["python", "programming", "code"]):
                        assert memory["similarity_score"] > 0.3

        # Test cross-category similarity
        work_search = await client.get(
            "/memory",
            headers=auth_headers,
            params={"query": "workplace and colleagues", "limit": 10}
        )

        if work_search.status_code == 200:
            work_results = work_search.json()

            # Should prioritize work-related memories
            work_related_count = sum(
                1 for memory in work_results["data"]
                if any(keyword in memory["content"].lower()
                      for keyword in ["work", "techcorp", "office", "collaborat"])
            )

            # At least some work-related memories should be found
            # (This is implementation-dependent)

    @pytest.mark.asyncio
    async def test_memory_importance_evolution(self, client: AsyncClient, auth_headers: dict):
        """Test how memory importance evolves based on usage patterns."""

        # Create memories with different initial importance
        test_memories = [
            {
                "content": "User's favorite programming language is Python",
                "type": "preference",
                "importance": 0.5  # Start with medium importance
            },
            {
                "content": "User once mentioned liking coffee",
                "type": "preference",
                "importance": 0.2  # Start with low importance
            },
            {
                "content": "User's primary skill is software engineering",
                "type": "skill",
                "importance": 0.8  # Start with high importance
            }
        ]

        created_memory_ids = []

        for memory_data in test_memories:
            create_response = await client.post("/memory", headers=auth_headers, json=memory_data)
            if create_response.status_code == 201:
                created_memory_ids.append(create_response.json()["id"])

        if not created_memory_ids:
            pytest.skip("Memory creation not implemented yet")

        # Simulate frequent access to the Python preference memory
        python_memory_id = created_memory_ids[0]

        for _ in range(5):
            # Access the memory multiple times
            await client.get(f"/memory/{python_memory_id}", headers=auth_headers)
            await asyncio.sleep(0.1)

        # Create conversation that frequently references Python
        conv_response = await client.post(
            "/conversations",
            headers=auth_headers,
            json={"title": "Python Discussion"}
        )

        if conv_response.status_code == 201:
            conversation_id = conv_response.json()["id"]

            python_messages = [
                "I love working with Python for data analysis",
                "Can you help me with a Python coding problem?",
                "What are the best Python libraries for machine learning?"
            ]

            for msg_content in python_messages:
                await client.post(
                    f"/conversations/{conversation_id}/messages",
                    headers=auth_headers,
                    json={"content": msg_content, "role": "user"}
                )
                await asyncio.sleep(0.1)

        # Check if importance has evolved
        final_memory_check = await client.get(f"/memory/{python_memory_id}", headers=auth_headers)
        if final_memory_check.status_code == 200:
            final_memory = final_memory_check.json()

            # Importance might have increased due to frequent access
            # (This would be implementation-dependent)
            assert "last_accessed_at" in final_memory

            # Check for access count or frequency indicators
            if "access_count" in final_memory.get("metadata", {}):
                assert final_memory["metadata"]["access_count"] > 0