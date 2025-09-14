"""
Integration test for document upload and analysis journey.

This test validates the complete document processing pipeline from file upload
to content integration in conversations, ensuring multimodal capabilities work correctly.
According to TDD, this test MUST FAIL initially until all file processing endpoints are implemented.
"""
import pytest
from httpx import AsyncClient
import asyncio
import uuid
import io
import time
from typing import Dict, Any, List


class TestMultimodalJourney:
    """Test complete document upload and analysis journey."""

    @pytest.fixture
    def sample_pdf_data(self):
        """Generate mock PDF data for testing."""
        # Minimal PDF structure for testing
        pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Sample PDF content for testing) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f
0000000010 00000 n
0000000053 00000 n
0000000099 00000 n
0000000178 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
268
%%EOF"""
        return io.BytesIO(pdf_content)

    @pytest.fixture
    def sample_image_data(self):
        """Generate mock PNG image data for testing."""
        # Minimal PNG structure for testing
        png_header = b'\x89PNG\r\n\x1a\n'
        # IHDR chunk (13 bytes data)
        ihdr = b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
        # IDAT chunk (minimal data)
        idat = b'\x00\x00\x00\x0bIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\xe2!\xbc3'
        # IEND chunk
        iend = b'\x00\x00\x00\x00IEND\xaeB`\x82'

        png_data = png_header + ihdr + idat + iend
        return io.BytesIO(png_data)

    @pytest.fixture
    def sample_text_data(self):
        """Generate mock text document."""
        text_content = """Sample Document

This is a test document with multiple paragraphs.

Key Points:
1. Document processing capabilities
2. Text extraction and analysis
3. Content integration with conversations
4. Multi-format support testing

The document contains various formatting elements and should be properly extracted and indexed for conversation use.

End of document."""
        return io.BytesIO(text_content.encode('utf-8'))

    @pytest.fixture
    def test_conversation_data(self):
        """Create test conversation for document analysis."""
        unique_id = str(uuid.uuid4())[:8]
        return {
            "title": f"Document Analysis Test {unique_id}",
            "metadata": {"document_test": True}
        }

    @pytest.mark.asyncio
    async def test_complete_document_upload_and_analysis_journey(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        sample_pdf_data: io.BytesIO,
        test_conversation_data: Dict[str, Any]
    ):
        """Test complete document upload, processing, and query journey."""

        # Step 1: Create a conversation for document analysis
        # This MUST FAIL initially until conversation endpoints are implemented
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        assert conversation_response.status_code == 201

        conversation_data = conversation_response.json()
        conversation_id = conversation_data["id"]

        # Step 2: Upload PDF document
        # This MUST FAIL initially until file upload endpoints are implemented
        file_data = {
            "file": ("test_document.pdf", sample_pdf_data, "application/pdf")
        }
        form_data = {
            "conversation_id": conversation_id,
            "description": "Test PDF document for analysis"
        }

        upload_response = await client.post(
            "/files/upload",
            headers=auth_headers,
            files=file_data,
            data=form_data
        )
        assert upload_response.status_code == 201

        upload_data = upload_response.json()
        file_id = upload_data["file_id"]

        # Verify initial file state
        assert upload_data["status"] == "processing"
        assert upload_data["filename"] == "test_document.pdf"
        assert upload_data["file_type"] == "application/pdf"
        assert "conversation_id" in upload_data
        assert upload_data["conversation_id"] == conversation_id

        # Step 3: Wait for processing completion
        max_wait_time = 30  # seconds for document processing
        start_time = time.time()
        processing_completed = False

        while time.time() - start_time < max_wait_time:
            file_status_response = await client.get(
                f"/files/{file_id}",
                headers=auth_headers
            )
            assert file_status_response.status_code == 200

            file_status_data = file_status_response.json()

            if file_status_data["status"] == "completed":
                processing_completed = True

                # Verify processing results
                assert "extracted_content" in file_status_data
                assert len(file_status_data["extracted_content"]) > 0
                assert "content_type" in file_status_data
                assert "processing_time_ms" in file_status_data
                assert "file_size" in file_status_data

                # Verify content extraction quality
                extracted_text = file_status_data["extracted_content"]
                assert "Sample PDF content for testing" in extracted_text or len(extracted_text) > 10

                break
            elif file_status_data["status"] == "error":
                pytest.fail(f"Document processing failed: {file_status_data.get('error_message', 'Unknown error')}")

            await asyncio.sleep(1)  # Wait before polling again

        assert processing_completed, "Document processing did not complete within timeout"

        # Step 4: Query document content through conversation
        query_start_time = time.time()

        message_response = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json={
                "content": "What are the key points mentioned in the uploaded document?",
                "metadata": {
                    "query_type": "document_analysis",
                    "referenced_file_id": file_id
                }
            }
        )
        assert message_response.status_code == 201

        message_data = message_response.json()
        response_content = message_data["response"]["content"]

        query_processing_time = (time.time() - query_start_time) * 1000

        # Step 5: Verify content integration
        # The AI should reference the document content in its response
        assert len(response_content) > 0
        # Look for evidence that document content was used
        document_keywords = ["document", "key points", "content", "uploaded", "file"]
        references_document = any(keyword in response_content.lower() for keyword in document_keywords)
        assert references_document, "AI response should reference the uploaded document"

        # Step 6: Test follow-up queries about the document
        followup_response = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json={
                "content": "Can you summarize the main content of the document?",
                "metadata": {"query_type": "document_summary"}
            }
        )
        assert followup_response.status_code == 201

        followup_data = followup_response.json()
        summary_content = followup_data["response"]["content"]
        assert len(summary_content) > 0

        # Step 7: Verify file is searchable in conversation context
        search_response = await client.get(
            f"/conversations/{conversation_id}/files",
            headers=auth_headers
        )
        assert search_response.status_code == 200

        files_data = search_response.json()
        assert len(files_data["files"]) >= 1

        uploaded_file = next(
            (f for f in files_data["files"] if f["id"] == file_id),
            None
        )
        assert uploaded_file is not None
        assert uploaded_file["status"] == "completed"

        # Step 8: Performance validation
        # Document processing should complete within reasonable time for 100MB files
        processing_time = file_status_data["processing_time_ms"]
        file_size = file_status_data["file_size"]

        # For small test files, should process quickly
        if file_size < 1024 * 1024:  # Less than 1MB
            assert processing_time < 10000, f"Small file processing took {processing_time}ms, should be < 10s"

        # Query response should be fast
        assert query_processing_time < 5000, f"Document query took {query_processing_time}ms, should be < 5s"

    @pytest.mark.asyncio
    async def test_multiple_file_formats_processing(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        sample_pdf_data: io.BytesIO,
        sample_image_data: io.BytesIO,
        sample_text_data: io.BytesIO,
        test_conversation_data: Dict[str, Any]
    ):
        """Test processing of multiple file formats in one conversation."""

        # Create conversation
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        assert conversation_response.status_code == 201
        conversation_id = conversation_response.json()["id"]

        # Upload different file types
        file_uploads = [
            ("test.pdf", sample_pdf_data, "application/pdf"),
            ("test.png", sample_image_data, "image/png"),
            ("test.txt", sample_text_data, "text/plain")
        ]

        file_ids = []
        for filename, file_data, content_type in file_uploads:
            file_data.seek(0)  # Reset stream position

            upload_response = await client.post(
                "/files/upload",
                headers=auth_headers,
                files={"file": (filename, file_data, content_type)},
                data={"conversation_id": conversation_id}
            )
            assert upload_response.status_code == 201

            file_ids.append(upload_response.json()["file_id"])

        # Wait for all files to process
        await asyncio.sleep(5)

        # Verify all files processed successfully
        for file_id in file_ids:
            file_status_response = await client.get(
                f"/files/{file_id}",
                headers=auth_headers
            )
            assert file_status_response.status_code == 200

            file_data = file_status_response.json()
            assert file_data["status"] in ["completed", "processing"]  # May still be processing

    @pytest.mark.asyncio
    async def test_large_file_handling(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        test_conversation_data: Dict[str, Any]
    ):
        """Test handling of large files (approaching 100MB limit)."""

        # Create conversation
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        assert conversation_response.status_code == 201
        conversation_id = conversation_response.json()["id"]

        # Create large file (10MB for testing - would use 100MB in real scenario)
        large_content = b"Large file content " * (10 * 1024 * 50)  # ~10MB
        large_file = io.BytesIO(large_content)

        upload_response = await client.post(
            "/files/upload",
            headers=auth_headers,
            files={"file": ("large_file.txt", large_file, "text/plain")},
            data={"conversation_id": conversation_id}
        )

        # Should either accept and process, or reject with proper error
        if upload_response.status_code == 201:
            file_id = upload_response.json()["file_id"]

            # Allow extra time for large file processing
            max_wait_time = 60  # 1 minute for large files
            start_time = time.time()

            while time.time() - start_time < max_wait_time:
                status_response = await client.get(
                    f"/files/{file_id}",
                    headers=auth_headers
                )
                status_data = status_response.json()

                if status_data["status"] in ["completed", "error"]:
                    break

                await asyncio.sleep(2)

            # File should eventually complete processing
            final_status = status_response.json()
            assert final_status["status"] == "completed", "Large file should process successfully"

        else:
            # Should reject with appropriate error code
            assert upload_response.status_code in [413, 422]  # Payload too large or validation error

    @pytest.mark.asyncio
    async def test_unsupported_file_format_handling(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        test_conversation_data: Dict[str, Any]
    ):
        """Test handling of unsupported file formats."""

        # Create conversation
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        assert conversation_response.status_code == 201
        conversation_id = conversation_response.json()["id"]

        # Try to upload unsupported file type (e.g., executable)
        binary_data = io.BytesIO(b'\x7fELF\x01\x01\x01\x00' + b'\x00' * 100)

        upload_response = await client.post(
            "/files/upload",
            headers=auth_headers,
            files={"file": ("test.exe", binary_data, "application/octet-stream")},
            data={"conversation_id": conversation_id}
        )

        # Should reject unsupported formats
        assert upload_response.status_code in [400, 415, 422]  # Bad request, unsupported media type, or validation error

        error_data = upload_response.json()
        assert "error" in error_data or "detail" in error_data

    @pytest.mark.asyncio
    async def test_file_deletion_and_cleanup(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        sample_text_data: io.BytesIO,
        test_conversation_data: Dict[str, Any]
    ):
        """Test file deletion and cleanup functionality."""

        # Create conversation and upload file
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        assert conversation_response.status_code == 201
        conversation_id = conversation_response.json()["id"]

        upload_response = await client.post(
            "/files/upload",
            headers=auth_headers,
            files={"file": ("test_delete.txt", sample_text_data, "text/plain")},
            data={"conversation_id": conversation_id}
        )
        assert upload_response.status_code == 201
        file_id = upload_response.json()["file_id"]

        # Wait for processing
        await asyncio.sleep(2)

        # Delete the file
        delete_response = await client.delete(
            f"/files/{file_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200

        # Verify file is marked as deleted
        status_response = await client.get(
            f"/files/{file_id}",
            headers=auth_headers
        )

        # Should either return 404 or show deleted status
        if status_response.status_code == 200:
            file_data = status_response.json()
            assert file_data["status"] == "deleted"
        else:
            assert status_response.status_code == 404