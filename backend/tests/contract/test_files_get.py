"""
Contract test for GET /files endpoint.

This test validates the API contract for listing user's files with various filters.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
import uuid


class TestFilesGetContract:
    """Test contract compliance for files listing endpoint."""

    @pytest.fixture
    def sample_conversation_id(self):
        """Sample conversation ID for filtering."""
        return "550e8400-e29b-41d4-a716-446655440000"

    @pytest.fixture
    def another_conversation_id(self):
        """Another conversation ID for filtering tests."""
        return "550e8400-e29b-41d4-a716-446655440001"

    @pytest.mark.asyncio
    async def test_list_user_files_success(self, client: AsyncClient, auth_headers: dict):
        """Test successful file listing returns 200."""
        response = await client.get("/files", headers=auth_headers)

        # Assert - This MUST FAIL initially
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert isinstance(data["files"], list)

    @pytest.mark.asyncio
    async def test_list_files_response_format(self, client: AsyncClient, auth_headers: dict):
        """Test files listing response has correct format."""
        response = await client.get("/files", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        required_fields = ["files", "total", "page", "per_page", "total_pages"]
        for field in required_fields:
            assert field in data

        # Validate data types
        assert isinstance(data["files"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["page"], int)
        assert isinstance(data["per_page"], int)
        assert isinstance(data["total_pages"], int)

        # If files exist, validate file structure
        if data["files"]:
            file_item = data["files"][0]
            required_file_fields = [
                "id", "filename", "content_type", "size", "conversation_id",
                "user_id", "processing_status", "created_at", "updated_at"
            ]
            for field in required_file_fields:
                assert field in file_item

            # Validate file data types
            assert isinstance(file_item["id"], str)
            assert isinstance(file_item["filename"], str)
            assert isinstance(file_item["size"], int)
            assert file_item["processing_status"] in ["pending", "processing", "completed", "failed"]

    @pytest.mark.asyncio
    async def test_list_files_empty_result(self, client: AsyncClient, auth_headers: dict):
        """Test files listing when user has no files."""
        response = await client.get("/files", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["files"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_filter_by_conversation_id(self, client: AsyncClient, auth_headers: dict,
                                           sample_conversation_id: str):
        """Test filtering files by conversation_id."""
        params = {"conversation_id": sample_conversation_id}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()
        assert "files" in data

        # All returned files should belong to the specified conversation
        for file_item in data["files"]:
            assert file_item["conversation_id"] == sample_conversation_id

    @pytest.mark.asyncio
    async def test_filter_by_multiple_conversation_ids(self, client: AsyncClient, auth_headers: dict,
                                                     sample_conversation_id: str, another_conversation_id: str):
        """Test filtering files by multiple conversation_ids."""
        conversation_ids = f"{sample_conversation_id},{another_conversation_id}"
        params = {"conversation_id": conversation_ids}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # All returned files should belong to one of the specified conversations
        allowed_ids = [sample_conversation_id, another_conversation_id]
        for file_item in data["files"]:
            assert file_item["conversation_id"] in allowed_ids

    @pytest.mark.asyncio
    async def test_filter_by_file_type_document(self, client: AsyncClient, auth_headers: dict):
        """Test filtering files by file_type = document."""
        params = {"file_type": "document"}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # All returned files should be documents
        document_types = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain"]
        for file_item in data["files"]:
            assert file_item["content_type"] in document_types

    @pytest.mark.asyncio
    async def test_filter_by_file_type_image(self, client: AsyncClient, auth_headers: dict):
        """Test filtering files by file_type = image."""
        params = {"file_type": "image"}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # All returned files should be images
        for file_item in data["files"]:
            assert file_item["content_type"].startswith("image/")

    @pytest.mark.asyncio
    async def test_filter_by_processing_status_pending(self, client: AsyncClient, auth_headers: dict):
        """Test filtering files by processing_status = pending."""
        params = {"processing_status": "pending"}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # All returned files should have pending status
        for file_item in data["files"]:
            assert file_item["processing_status"] == "pending"

    @pytest.mark.asyncio
    async def test_filter_by_processing_status_completed(self, client: AsyncClient, auth_headers: dict):
        """Test filtering files by processing_status = completed."""
        params = {"processing_status": "completed"}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # All returned files should have completed status
        for file_item in data["files"]:
            assert file_item["processing_status"] == "completed"

    @pytest.mark.asyncio
    async def test_filter_by_processing_status_failed(self, client: AsyncClient, auth_headers: dict):
        """Test filtering files by processing_status = failed."""
        params = {"processing_status": "failed"}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # All returned files should have failed status
        for file_item in data["files"]:
            assert file_item["processing_status"] == "failed"

    @pytest.mark.asyncio
    async def test_combined_filters(self, client: AsyncClient, auth_headers: dict, sample_conversation_id: str):
        """Test combining multiple filters."""
        params = {
            "conversation_id": sample_conversation_id,
            "file_type": "document",
            "processing_status": "completed"
        }
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # All returned files should match all criteria
        document_types = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain"]
        for file_item in data["files"]:
            assert file_item["conversation_id"] == sample_conversation_id
            assert file_item["content_type"] in document_types
            assert file_item["processing_status"] == "completed"

    @pytest.mark.asyncio
    async def test_pagination_default(self, client: AsyncClient, auth_headers: dict):
        """Test pagination with default values."""
        response = await client.get("/files", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["per_page"] >= 10  # Default should be reasonable
        assert len(data["files"]) <= data["per_page"]

    @pytest.mark.asyncio
    async def test_pagination_custom_page_size(self, client: AsyncClient, auth_headers: dict):
        """Test pagination with custom page size."""
        params = {"per_page": 5, "page": 1}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()
        assert data["per_page"] == 5
        assert len(data["files"]) <= 5

    @pytest.mark.asyncio
    async def test_pagination_second_page(self, client: AsyncClient, auth_headers: dict):
        """Test getting second page of results."""
        params = {"per_page": 5, "page": 2}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["per_page"] == 5

    @pytest.mark.asyncio
    async def test_pagination_invalid_page_number(self, client: AsyncClient, auth_headers: dict):
        """Test pagination with invalid page number."""
        params = {"page": 0}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data

    @pytest.mark.asyncio
    async def test_pagination_invalid_per_page(self, client: AsyncClient, auth_headers: dict):
        """Test pagination with invalid per_page value."""
        params = {"per_page": -1}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data

    @pytest.mark.asyncio
    async def test_pagination_per_page_too_large(self, client: AsyncClient, auth_headers: dict):
        """Test pagination with per_page value too large."""
        params = {"per_page": 1000}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data

    @pytest.mark.asyncio
    async def test_sort_by_created_at_desc(self, client: AsyncClient, auth_headers: dict):
        """Test sorting files by created_at descending (newest first)."""
        params = {"sort_by": "created_at", "sort_order": "desc"}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # Verify sorting if there are multiple files
        if len(data["files"]) > 1:
            for i in range(len(data["files"]) - 1):
                current_time = data["files"][i]["created_at"]
                next_time = data["files"][i + 1]["created_at"]
                assert current_time >= next_time

    @pytest.mark.asyncio
    async def test_sort_by_filename_asc(self, client: AsyncClient, auth_headers: dict):
        """Test sorting files by filename ascending."""
        params = {"sort_by": "filename", "sort_order": "asc"}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # Verify sorting if there are multiple files
        if len(data["files"]) > 1:
            for i in range(len(data["files"]) - 1):
                current_name = data["files"][i]["filename"]
                next_name = data["files"][i + 1]["filename"]
                assert current_name <= next_name

    @pytest.mark.asyncio
    async def test_sort_by_size_desc(self, client: AsyncClient, auth_headers: dict):
        """Test sorting files by size descending (largest first)."""
        params = {"sort_by": "size", "sort_order": "desc"}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # Verify sorting if there are multiple files
        if len(data["files"]) > 1:
            for i in range(len(data["files"]) - 1):
                current_size = data["files"][i]["size"]
                next_size = data["files"][i + 1]["size"]
                assert current_size >= next_size

    @pytest.mark.asyncio
    async def test_invalid_sort_field(self, client: AsyncClient, auth_headers: dict):
        """Test sorting with invalid sort field."""
        params = {"sort_by": "invalid_field"}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data

    @pytest.mark.asyncio
    async def test_invalid_sort_order(self, client: AsyncClient, auth_headers: dict):
        """Test sorting with invalid sort order."""
        params = {"sort_by": "created_at", "sort_order": "invalid"}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data

    @pytest.mark.asyncio
    async def test_search_by_filename(self, client: AsyncClient, auth_headers: dict):
        """Test searching files by filename."""
        params = {"search": "test"}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # All returned files should have search term in filename
        for file_item in data["files"]:
            assert "test" in file_item["filename"].lower()

    @pytest.mark.asyncio
    async def test_search_empty_query(self, client: AsyncClient, auth_headers: dict):
        """Test search with empty query returns all files."""
        params = {"search": ""}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()
        assert "files" in data

    @pytest.mark.asyncio
    async def test_list_files_without_auth_unauthorized(self, client: AsyncClient):
        """Test files listing without authentication returns 401."""
        response = await client.get("/files")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_files_invalid_token_unauthorized(self, client: AsyncClient):
        """Test files listing with invalid token returns 401."""
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        response = await client.get("/files", headers=invalid_headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_conversation_id_filter(self, client: AsyncClient, auth_headers: dict):
        """Test filtering with invalid conversation_id format."""
        params = {"conversation_id": "invalid-uuid"}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data

    @pytest.mark.asyncio
    async def test_invalid_file_type_filter(self, client: AsyncClient, auth_headers: dict):
        """Test filtering with invalid file_type value."""
        params = {"file_type": "invalid_type"}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data

    @pytest.mark.asyncio
    async def test_invalid_processing_status_filter(self, client: AsyncClient, auth_headers: dict):
        """Test filtering with invalid processing_status value."""
        params = {"processing_status": "invalid_status"}
        response = await client.get("/files", headers=auth_headers, params=params)

        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data

    @pytest.mark.asyncio
    async def test_list_files_includes_metadata(self, client: AsyncClient, auth_headers: dict):
        """Test that files listing includes metadata when available."""
        response = await client.get("/files", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Check if files have optional metadata fields
        for file_item in data["files"]:
            optional_fields = ["metadata", "extracted_content", "tags"]
            for field in optional_fields:
                # These fields should be present (even if null/empty)
                assert field in file_item