"""
Contract test for GET /files/{file_id} endpoint.

This test validates the API contract for retrieving a specific file with extracted content.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
import uuid


class TestFilesGetByIdContract:
    """Test contract compliance for file retrieval endpoint."""

    @pytest.fixture
    def sample_file_id(self):
        """Sample file ID for testing."""
        return "550e8400-e29b-41d4-a716-446655440000"

    @pytest.fixture
    def sample_conversation_id(self):
        """Sample conversation ID for testing."""
        return "550e8400-e29b-41d4-a716-446655440001"

    @pytest.mark.asyncio
    async def test_get_file_by_id_success(self, client: AsyncClient, auth_headers: dict, sample_file_id: str):
        """Test successful file retrieval returns 200."""
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers)

        # Assert - This MUST FAIL initially
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_file_id

    @pytest.mark.asyncio
    async def test_get_file_response_format(self, client: AsyncClient, auth_headers: dict, sample_file_id: str):
        """Test file retrieval response has correct format."""
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        required_fields = [
            "id", "filename", "content_type", "size", "conversation_id",
            "user_id", "processing_status", "extracted_content",
            "created_at", "updated_at"
        ]
        for field in required_fields:
            assert field in data

        # Validate data types
        assert isinstance(data["id"], str)
        assert isinstance(data["filename"], str)
        assert isinstance(data["content_type"], str)
        assert isinstance(data["size"], int)
        assert isinstance(data["conversation_id"], str)
        assert isinstance(data["user_id"], str)
        assert data["processing_status"] in ["pending", "processing", "completed", "failed"]

    @pytest.mark.asyncio
    async def test_get_file_with_extracted_content_completed(self, client: AsyncClient, auth_headers: dict,
                                                           sample_file_id: str):
        """Test file retrieval with completed processing includes extracted content."""
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        if data["processing_status"] == "completed":
            assert "extracted_content" in data
            # For completed files, extracted_content should not be null
            assert data["extracted_content"] is not None
            assert isinstance(data["extracted_content"], (str, dict))

    @pytest.mark.asyncio
    async def test_get_file_with_extracted_content_pending(self, client: AsyncClient, auth_headers: dict,
                                                         sample_file_id: str):
        """Test file retrieval with pending processing has null extracted content."""
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        if data["processing_status"] == "pending":
            # For pending files, extracted_content should be null
            assert data["extracted_content"] is None

    @pytest.mark.asyncio
    async def test_get_file_with_extracted_content_failed(self, client: AsyncClient, auth_headers: dict,
                                                        sample_file_id: str):
        """Test file retrieval with failed processing has null extracted content."""
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        if data["processing_status"] == "failed":
            # For failed files, extracted_content should be null
            assert data["extracted_content"] is None
            # Should include error information
            assert "error" in data or "error_message" in data

    @pytest.mark.asyncio
    async def test_get_document_file_extracted_content_format(self, client: AsyncClient, auth_headers: dict,
                                                            sample_file_id: str):
        """Test document file extracted content has correct format."""
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # For document files with completed processing
        if (data["processing_status"] == "completed" and
            data["content_type"] in ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain"]):

            extracted_content = data["extracted_content"]
            assert extracted_content is not None

            if isinstance(extracted_content, dict):
                # Structured content format
                expected_fields = ["text", "metadata"]
                for field in expected_fields:
                    assert field in extracted_content
                assert isinstance(extracted_content["text"], str)
            else:
                # Simple text format
                assert isinstance(extracted_content, str)

    @pytest.mark.asyncio
    async def test_get_image_file_extracted_content_format(self, client: AsyncClient, auth_headers: dict,
                                                         sample_file_id: str):
        """Test image file extracted content has correct format."""
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # For image files with completed processing
        if (data["processing_status"] == "completed" and
            data["content_type"].startswith("image/")):

            extracted_content = data["extracted_content"]

            if extracted_content is not None:
                if isinstance(extracted_content, dict):
                    # Structured content format for images
                    expected_fields = ["description", "metadata", "dimensions"]
                    available_fields = [field for field in expected_fields if field in extracted_content]
                    assert len(available_fields) > 0  # At least one field should be present
                else:
                    # Simple description format
                    assert isinstance(extracted_content, str)

    @pytest.mark.asyncio
    async def test_get_file_includes_metadata(self, client: AsyncClient, auth_headers: dict, sample_file_id: str):
        """Test file retrieval includes metadata."""
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Check for optional metadata fields
        optional_fields = ["metadata", "tags", "description", "upload_source"]
        for field in optional_fields:
            # These fields should be present (even if null)
            assert field in data

    @pytest.mark.asyncio
    async def test_get_file_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test file retrieval with non-existent ID returns 404."""
        non_existent_id = str(uuid.uuid4())
        response = await client.get(f"/files/{non_existent_id}", headers=auth_headers)

        assert response.status_code == 404
        error_data = response.json()
        assert "detail" in error_data
        assert "file" in error_data["detail"].lower() or "not found" in error_data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_file_invalid_uuid_format(self, client: AsyncClient, auth_headers: dict):
        """Test file retrieval with invalid UUID format returns 422."""
        invalid_id = "not-a-valid-uuid"
        response = await client.get(f"/files/{invalid_id}", headers=auth_headers)

        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data

    @pytest.mark.asyncio
    async def test_get_file_without_auth_unauthorized(self, client: AsyncClient, sample_file_id: str):
        """Test file retrieval without authentication returns 401."""
        response = await client.get(f"/files/{sample_file_id}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_file_invalid_token_unauthorized(self, client: AsyncClient, sample_file_id: str):
        """Test file retrieval with invalid token returns 401."""
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        response = await client.get(f"/files/{sample_file_id}", headers=invalid_headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_file_forbidden_access_control(self, client: AsyncClient, auth_headers: dict,
                                                   sample_file_id: str):
        """Test file retrieval for file not owned by user returns 403."""
        # This test assumes the file exists but belongs to another user
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers)

        # Could be 404 (not found) or 403 (forbidden) - both are acceptable for access control
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_get_file_with_conversation_context(self, client: AsyncClient, auth_headers: dict,
                                                    sample_file_id: str, sample_conversation_id: str):
        """Test file retrieval includes conversation context."""
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # File should include conversation information
        assert "conversation_id" in data
        assert isinstance(data["conversation_id"], str)

    @pytest.mark.asyncio
    async def test_get_file_processing_timestamps(self, client: AsyncClient, auth_headers: dict, sample_file_id: str):
        """Test file retrieval includes processing timestamps."""
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Standard timestamps should be present
        assert "created_at" in data
        assert "updated_at" in data
        assert isinstance(data["created_at"], str)
        assert isinstance(data["updated_at"], str)

        # Processing-specific timestamps
        processing_fields = ["processing_started_at", "processing_completed_at"]
        for field in processing_fields:
            if field in data and data[field] is not None:
                assert isinstance(data[field], str)

    @pytest.mark.asyncio
    async def test_get_file_size_and_type_validation(self, client: AsyncClient, auth_headers: dict, sample_file_id: str):
        """Test file retrieval validates size and type information."""
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Size should be positive integer
        assert isinstance(data["size"], int)
        assert data["size"] > 0

        # Content type should be valid MIME type
        assert isinstance(data["content_type"], str)
        assert "/" in data["content_type"]  # Basic MIME type format check

        # Filename should not be empty
        assert isinstance(data["filename"], str)
        assert len(data["filename"]) > 0

    @pytest.mark.asyncio
    async def test_get_file_with_query_params(self, client: AsyncClient, auth_headers: dict, sample_file_id: str):
        """Test file retrieval with query parameters for content inclusion."""
        params = {"include_content": "true"}
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # Should include all standard fields
        assert "extracted_content" in data

    @pytest.mark.asyncio
    async def test_get_file_exclude_content(self, client: AsyncClient, auth_headers: dict, sample_file_id: str):
        """Test file retrieval with content exclusion for performance."""
        params = {"include_content": "false"}
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # Should still include basic file information but may exclude large content
        required_basic_fields = ["id", "filename", "content_type", "size", "processing_status"]
        for field in required_basic_fields:
            assert field in data

    @pytest.mark.asyncio
    async def test_get_file_error_details_for_failed_processing(self, client: AsyncClient, auth_headers: dict,
                                                              sample_file_id: str):
        """Test file retrieval includes error details for failed processing."""
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        if data["processing_status"] == "failed":
            # Should include error information
            error_fields = ["error", "error_message", "error_details"]
            error_field_present = any(field in data for field in error_fields)
            assert error_field_present

            # Error information should not be empty if present
            for field in error_fields:
                if field in data and data[field] is not None:
                    assert isinstance(data[field], (str, dict))
                    if isinstance(data[field], str):
                        assert len(data[field]) > 0

    @pytest.mark.asyncio
    async def test_get_file_download_url(self, client: AsyncClient, auth_headers: dict, sample_file_id: str):
        """Test file retrieval includes download URL when applicable."""
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Optional download URL field
        if "download_url" in data:
            assert isinstance(data["download_url"], str)
            assert data["download_url"].startswith(("http://", "https://"))

    @pytest.mark.asyncio
    async def test_get_file_with_version_info(self, client: AsyncClient, auth_headers: dict, sample_file_id: str):
        """Test file retrieval includes version/revision information."""
        response = await client.get(f"/files/{sample_file_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Optional version fields
        version_fields = ["version", "revision", "checksum"]
        for field in version_fields:
            if field in data and data[field] is not None:
                assert isinstance(data[field], (str, int))