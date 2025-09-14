"""
Contract test for POST /analytics/export endpoint.

This test validates the API contract for exporting analytics data.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta
import io
import csv
import json


class TestAnalyticsExportPostContract:
    """Test contract compliance for analytics export endpoint."""

    @pytest.fixture
    def sample_export_request_data(self):
        """Sample export request data for testing."""
        return {
            "format": "csv",
            "data_type": "events",
            "date_range": {
                "start_date": (datetime.now() - timedelta(days=30)).isoformat() + "Z",
                "end_date": datetime.now().isoformat() + "Z"
            },
            "filters": {
                "event_types": ["conversation_started", "message_sent"],
                "include_metadata": True
            }
        }

    @pytest.fixture
    def sample_full_export_request_data(self):
        """Sample full export request data for testing."""
        return {
            "format": "xlsx",
            "data_type": "all",
            "date_range": {
                "start_date": (datetime.now() - timedelta(days=90)).isoformat() + "Z",
                "end_date": datetime.now().isoformat() + "Z"
            },
            "filters": {
                "include_conversations": True,
                "include_usage": True,
                "include_events": True,
                "include_metadata": True
            }
        }

    @pytest.mark.asyncio
    async def test_export_csv_format_success(self, client: AsyncClient, auth_headers: dict, sample_export_request_data: dict):
        """Test successful CSV export returns correct response format."""
        # Arrange
        sample_export_request_data["format"] = "csv"

        # Act
        response = await client.post("/analytics/export", json=sample_export_request_data, headers=auth_headers)

        # Assert - This MUST FAIL initially (endpoint doesn't exist yet)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # Validate response headers for file download
        assert response.headers["content-type"] in ["text/csv", "application/csv", "application/octet-stream"]
        assert "content-disposition" in response.headers
        assert "attachment" in response.headers["content-disposition"]
        assert "filename" in response.headers["content-disposition"]

        # Validate CSV content structure
        content = response.content.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(content))
        rows = list(csv_reader)

        # Should have at least header row
        assert len(rows) >= 1
        header_row = rows[0]
        assert len(header_row) > 0

    @pytest.mark.asyncio
    async def test_export_json_format_success(self, client: AsyncClient, auth_headers: dict, sample_export_request_data: dict):
        """Test successful JSON export returns correct response format."""
        # Arrange
        sample_export_request_data["format"] = "json"

        # Act
        response = await client.post("/analytics/export", json=sample_export_request_data, headers=auth_headers)

        # Assert
        assert response.status_code == 200

        # Validate response headers for file download
        assert response.headers["content-type"] in ["application/json", "application/octet-stream"]
        assert "content-disposition" in response.headers
        assert "attachment" in response.headers["content-disposition"]

        # Validate JSON content structure
        if response.headers["content-type"] == "application/json":
            response_data = response.json()
            assert isinstance(response_data, (dict, list))
        else:
            # If octet-stream, validate it's valid JSON
            content = response.content.decode('utf-8')
            json_data = json.loads(content)
            assert isinstance(json_data, (dict, list))

    @pytest.mark.asyncio
    async def test_export_xlsx_format_success(self, client: AsyncClient, auth_headers: dict, sample_export_request_data: dict):
        """Test successful XLSX export returns correct response format."""
        # Arrange
        sample_export_request_data["format"] = "xlsx"

        # Act
        response = await client.post("/analytics/export", json=sample_export_request_data, headers=auth_headers)

        # Assert
        assert response.status_code == 200

        # Validate response headers for file download
        assert response.headers["content-type"] in [
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/octet-stream"
        ]
        assert "content-disposition" in response.headers
        assert "attachment" in response.headers["content-disposition"]
        assert ".xlsx" in response.headers["content-disposition"]

        # Validate binary content is present
        assert len(response.content) > 0
        # XLSX files start with PK (ZIP signature)
        assert response.content[:2] == b'PK'

    @pytest.mark.asyncio
    async def test_export_invalid_format(self, client: AsyncClient, auth_headers: dict, sample_export_request_data: dict):
        """Test export with invalid format returns validation error."""
        # Arrange
        sample_export_request_data["format"] = "invalid_format"

        # Act
        response = await client.post("/analytics/export", json=sample_export_request_data, headers=auth_headers)

        # Assert
        assert response.status_code == 400
        error_response = response.json()
        assert "error" in error_response
        assert "message" in error_response

    @pytest.mark.asyncio
    async def test_export_data_type_events(self, client: AsyncClient, auth_headers: dict, sample_export_request_data: dict):
        """Test export with events data type selection."""
        # Arrange
        sample_export_request_data["data_type"] = "events"

        # Act
        response = await client.post("/analytics/export", json=sample_export_request_data, headers=auth_headers)

        # Assert
        assert response.status_code == 200
        assert "events" in response.headers["content-disposition"].lower()

    @pytest.mark.asyncio
    async def test_export_data_type_conversations(self, client: AsyncClient, auth_headers: dict, sample_export_request_data: dict):
        """Test export with conversations data type selection."""
        # Arrange
        sample_export_request_data["data_type"] = "conversations"

        # Act
        response = await client.post("/analytics/export", json=sample_export_request_data, headers=auth_headers)

        # Assert
        assert response.status_code == 200
        assert "conversations" in response.headers["content-disposition"].lower()

    @pytest.mark.asyncio
    async def test_export_data_type_usage(self, client: AsyncClient, auth_headers: dict, sample_export_request_data: dict):
        """Test export with usage data type selection."""
        # Arrange
        sample_export_request_data["data_type"] = "usage"

        # Act
        response = await client.post("/analytics/export", json=sample_export_request_data, headers=auth_headers)

        # Assert
        assert response.status_code == 200
        assert "usage" in response.headers["content-disposition"].lower()

    @pytest.mark.asyncio
    async def test_export_data_type_all(self, client: AsyncClient, auth_headers: dict, sample_full_export_request_data: dict):
        """Test export with all data types selection."""
        # Act
        response = await client.post("/analytics/export", json=sample_full_export_request_data, headers=auth_headers)

        # Assert
        assert response.status_code == 200
        # For 'all' data type, filename might include 'complete' or 'full'
        content_disposition = response.headers["content-disposition"].lower()
        assert any(keyword in content_disposition for keyword in ["all", "complete", "full", "analytics"])

    @pytest.mark.asyncio
    async def test_export_invalid_data_type(self, client: AsyncClient, auth_headers: dict, sample_export_request_data: dict):
        """Test export with invalid data type returns validation error."""
        # Arrange
        sample_export_request_data["data_type"] = "invalid_type"

        # Act
        response = await client.post("/analytics/export", json=sample_export_request_data, headers=auth_headers)

        # Assert
        assert response.status_code == 400
        error_response = response.json()
        assert "error" in error_response

    @pytest.mark.asyncio
    async def test_export_date_range_validation_valid(self, client: AsyncClient, auth_headers: dict, sample_export_request_data: dict):
        """Test export with valid date range."""
        # Arrange
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        sample_export_request_data["date_range"] = {
            "start_date": start_date.isoformat() + "Z",
            "end_date": end_date.isoformat() + "Z"
        }

        # Act
        response = await client.post("/analytics/export", json=sample_export_request_data, headers=auth_headers)

        # Assert
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_export_date_range_validation_invalid(self, client: AsyncClient, auth_headers: dict, sample_export_request_data: dict):
        """Test export with invalid date range returns validation error."""
        # Arrange - End date before start date
        start_date = datetime.now()
        end_date = start_date - timedelta(days=1)

        sample_export_request_data["date_range"] = {
            "start_date": start_date.isoformat() + "Z",
            "end_date": end_date.isoformat() + "Z"
        }

        # Act
        response = await client.post("/analytics/export", json=sample_export_request_data, headers=auth_headers)

        # Assert
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_export_without_auth_unauthorized(self, client: AsyncClient, sample_export_request_data: dict):
        """Test export without authentication returns 401."""
        # Act
        response = await client.post("/analytics/export", json=sample_export_request_data)

        # Assert
        assert response.status_code == 401
        error_response = response.json()
        assert "error" in error_response
        assert error_response["error"] == "unauthorized"

    @pytest.mark.asyncio
    async def test_export_invalid_token_unauthorized(self, client: AsyncClient, sample_export_request_data: dict):
        """Test export with invalid token returns 401."""
        # Arrange
        invalid_headers = {"Authorization": "Bearer invalid-token"}

        # Act
        response = await client.post("/analytics/export", json=sample_export_request_data, headers=invalid_headers)

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_export_file_download_response(self, client: AsyncClient, auth_headers: dict, sample_export_request_data: dict):
        """Test export response is properly formatted for file download."""
        # Act
        response = await client.post("/analytics/export", json=sample_export_request_data, headers=auth_headers)

        # Assert
        assert response.status_code == 200

        # Validate response headers for proper file download
        assert "content-disposition" in response.headers
        content_disposition = response.headers["content-disposition"]
        assert "attachment" in content_disposition
        assert "filename=" in content_disposition

        # Validate filename format
        filename_part = content_disposition.split("filename=")[1].strip('"')
        assert len(filename_part) > 0
        assert "." in filename_part  # Should have file extension

        # Validate content length header
        if "content-length" in response.headers:
            content_length = int(response.headers["content-length"])
            assert content_length > 0
            assert content_length == len(response.content)

    @pytest.mark.asyncio
    async def test_export_validation_errors(self, client: AsyncClient, auth_headers: dict):
        """Test validation error responses for malformed export requests."""
        validation_test_cases = [
            # Missing required fields
            {
                "data": {"format": "csv"},
                "description": "missing data_type and date_range"
            },
            {
                "data": {"data_type": "events"},
                "description": "missing format and date_range"
            },
            # Invalid date formats
            {
                "data": {
                    "format": "csv",
                    "data_type": "events",
                    "date_range": {
                        "start_date": "invalid-date",
                        "end_date": datetime.now().isoformat() + "Z"
                    }
                },
                "description": "invalid start_date format"
            },
            # Missing date_range fields
            {
                "data": {
                    "format": "csv",
                    "data_type": "events",
                    "date_range": {
                        "start_date": datetime.now().isoformat() + "Z"
                    }
                },
                "description": "missing end_date"
            },
            # Invalid filters
            {
                "data": {
                    "format": "csv",
                    "data_type": "events",
                    "date_range": {
                        "start_date": (datetime.now() - timedelta(days=7)).isoformat() + "Z",
                        "end_date": datetime.now().isoformat() + "Z"
                    },
                    "filters": "not-an-object"
                },
                "description": "filters should be an object"
            }
        ]

        for test_case in validation_test_cases:
            # Act
            response = await client.post("/analytics/export", json=test_case["data"], headers=auth_headers)

            # Assert
            assert response.status_code == 400, f"Expected 400 for {test_case['description']}, got {response.status_code}"

            error_response = response.json()
            assert "error" in error_response
            assert "message" in error_response

    @pytest.mark.asyncio
    async def test_export_empty_request_body(self, client: AsyncClient, auth_headers: dict):
        """Test empty request body returns validation error."""
        # Act
        response = await client.post("/analytics/export", json={}, headers=auth_headers)

        # Assert
        assert response.status_code == 400
        error_response = response.json()
        assert "error" in error_response

    @pytest.mark.asyncio
    async def test_export_large_date_range_handling(self, client: AsyncClient, auth_headers: dict, sample_export_request_data: dict):
        """Test export handles large date ranges appropriately."""
        # Arrange - Very large date range (1 year)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)

        sample_export_request_data["date_range"] = {
            "start_date": start_date.isoformat() + "Z",
            "end_date": end_date.isoformat() + "Z"
        }

        # Act
        response = await client.post("/analytics/export", json=sample_export_request_data, headers=auth_headers)

        # Assert - Either succeeds or returns appropriate error for too large range
        assert response.status_code in [200, 400, 413]  # 413 = Request Entity Too Large

        if response.status_code == 400:
            error_response = response.json()
            assert "error" in error_response
            # Should indicate date range is too large
            assert "range" in error_response["message"].lower() or "large" in error_response["message"].lower()

    @pytest.mark.asyncio
    async def test_export_filters_support(self, client: AsyncClient, auth_headers: dict, sample_export_request_data: dict):
        """Test export supports various filtering options."""
        # Test different filter combinations
        filter_test_cases = [
            # Event type filtering
            {
                "event_types": ["conversation_started", "message_sent"],
                "include_metadata": True
            },
            # Date-based filtering with metadata
            {
                "include_metadata": False,
                "exclude_empty": True
            },
            # User-specific filtering
            {
                "user_ids": ["user-1", "user-2"],
                "include_metadata": True
            }
        ]

        for filters in filter_test_cases:
            # Arrange
            export_data = sample_export_request_data.copy()
            export_data["filters"] = filters

            # Act
            response = await client.post("/analytics/export", json=export_data, headers=auth_headers)

            # Assert
            assert response.status_code == 200, f"Failed for filters: {filters}"

    @pytest.mark.asyncio
    async def test_export_async_processing(self, client: AsyncClient, auth_headers: dict, sample_full_export_request_data: dict):
        """Test export supports asynchronous processing for large requests."""
        # Act
        response = await client.post("/analytics/export", json=sample_full_export_request_data, headers=auth_headers)

        # Assert - Either immediate download or async processing initiation
        assert response.status_code in [200, 202]  # 202 = Accepted (for async processing)

        if response.status_code == 202:
            # Async processing - should return job info
            response_data = response.json()
            assert "job_id" in response_data or "export_id" in response_data
            assert "status" in response_data
            assert response_data["status"] in ["queued", "processing", "pending"]

            # Should provide status endpoint URL
            assert "status_url" in response_data or "download_url" in response_data

    @pytest.mark.asyncio
    async def test_export_filename_generation(self, client: AsyncClient, auth_headers: dict, sample_export_request_data: dict):
        """Test export generates appropriate filenames."""
        # Test different format filename generation
        format_tests = [
            ("csv", ".csv"),
            ("json", ".json"),
            ("xlsx", ".xlsx")
        ]

        for file_format, expected_extension in format_tests:
            # Arrange
            export_data = sample_export_request_data.copy()
            export_data["format"] = file_format

            # Act
            response = await client.post("/analytics/export", json=export_data, headers=auth_headers)

            # Assert
            assert response.status_code == 200

            # Validate filename
            content_disposition = response.headers["content-disposition"]
            filename = content_disposition.split("filename=")[1].strip('"')

            # Should include data type and date
            assert export_data["data_type"] in filename.lower()
            assert filename.endswith(expected_extension)

            # Should include timestamp or date for uniqueness
            assert any(char.isdigit() for char in filename)

    @pytest.mark.asyncio
    async def test_export_content_encoding(self, client: AsyncClient, auth_headers: dict, sample_export_request_data: dict):
        """Test export supports content encoding for large files."""
        # Act
        response = await client.post("/analytics/export", json=sample_export_request_data, headers=auth_headers)

        # Assert
        assert response.status_code == 200

        # Check for compression headers
        encoding = response.headers.get("content-encoding", "")
        if encoding:
            assert encoding in ["gzip", "deflate", "br"]

        # Validate content is properly encoded/decoded
        assert len(response.content) > 0