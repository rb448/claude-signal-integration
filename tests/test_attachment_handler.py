"""Tests for Signal attachment handling."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.signal.attachment_handler import AttachmentHandler


@pytest.fixture
def handler():
    """Create AttachmentHandler instance for testing."""
    return AttachmentHandler(signal_api_url="http://localhost:8080")


@pytest.fixture
def sample_code():
    """Sample code content for testing."""
    return """def hello_world():
    print("Hello, World!")
    return 42

if __name__ == "__main__":
    hello_world()
"""


class TestAttachmentHandler:
    """Test AttachmentHandler for Signal file uploads."""

    @pytest.mark.asyncio
    async def test_send_code_file_creates_temp_file(self, handler, sample_code):
        """Test that send_code_file creates temp file with code content."""
        with patch.object(handler, '_upload_attachment', new_callable=AsyncMock) as mock_upload:
            mock_upload.return_value = "mock_attachment_id"

            # Track temp file creation
            temp_files_created = []
            original_create = handler._create_temp_file

            def track_temp_file(content, suffix):
                path = original_create(content, suffix)
                temp_files_created.append(path)
                return path

            with patch.object(handler, '_create_temp_file', side_effect=track_temp_file):
                result = await handler.send_code_file(
                    recipient="+12345678900",
                    code=sample_code,
                    filename="test.py"
                )

                # Verify temp file was created
                assert len(temp_files_created) == 1
                temp_path = temp_files_created[0]

                # Verify content was written (file should be deleted by now)
                # We'll verify through the upload call instead
                mock_upload.assert_called_once()
                assert mock_upload.call_args[0][0] == temp_path

    @pytest.mark.asyncio
    async def test_send_code_file_uploads_to_signal_api(self, handler, sample_code):
        """Test that send_code_file uploads to Signal via REST API."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"timestamp": "123456789"})

        with patch('src.signal.attachment_handler.aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_post_cm = AsyncMock()
            mock_post_cm.__aenter__.return_value = mock_response
            mock_session.post.return_value = mock_post_cm

            mock_session_cm = AsyncMock()
            mock_session_cm.__aenter__.return_value = mock_session
            mock_session_class.return_value = mock_session_cm

            result = await handler.send_code_file(
                recipient="+12345678900",
                code=sample_code,
                filename="test.py"
            )

            # Verify API was called
            mock_session.post.assert_called_once()
            call_args = mock_session.post.call_args

            # Verify correct endpoint
            assert call_args[0][0] == "http://localhost:8080/v2/send"

            # Verify result is timestamp
            assert result == "123456789"

    @pytest.mark.asyncio
    async def test_send_code_file_includes_filename(self, handler, sample_code):
        """Test that send_code_file includes filename in upload."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"timestamp": "123456789"})

        with patch('src.signal.attachment_handler.aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_post_cm = AsyncMock()
            mock_post_cm.__aenter__.return_value = mock_response
            mock_session.post.return_value = mock_post_cm

            mock_session_cm = AsyncMock()
            mock_session_cm.__aenter__.return_value = mock_session
            mock_session_class.return_value = mock_session_cm

            await handler.send_code_file(
                recipient="+12345678900",
                code=sample_code,
                filename="user.py"
            )

            # Verify filename appears in message/caption
            call_args = mock_session.post.call_args
            json_data = call_args[1]['json']
            assert "user.py" in json_data.get('message', '')

    @pytest.mark.asyncio
    async def test_send_code_file_cleans_up_temp_file(self, handler, sample_code):
        """Test that send_code_file cleans up temp file after upload."""
        temp_path_created = None

        # Track temp file creation
        original_create = handler._create_temp_file
        def track_temp_file(content, suffix):
            nonlocal temp_path_created
            path = original_create(content, suffix)
            temp_path_created = path
            return path

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"timestamp": "123456789"})

        with patch.object(handler, '_create_temp_file', side_effect=track_temp_file):
            with patch('src.signal.attachment_handler.aiohttp.ClientSession') as mock_session_class:
                mock_session = MagicMock()
                mock_post_cm = AsyncMock()
                mock_post_cm.__aenter__.return_value = mock_response
                mock_session.post.return_value = mock_post_cm

                mock_session_cm = AsyncMock()
                mock_session_cm.__aenter__.return_value = mock_session
                mock_session_class.return_value = mock_session_cm

                await handler.send_code_file(
                    recipient="+12345678900",
                    code=sample_code,
                    filename="test.py"
                )

                # Verify temp file was deleted
                assert temp_path_created is not None
                assert not os.path.exists(temp_path_created)

    @pytest.mark.asyncio
    async def test_send_code_file_cleans_up_on_error(self, handler, sample_code):
        """Test that send_code_file cleans up temp file even on upload error."""
        temp_path_created = None

        # Track temp file creation
        original_create = handler._create_temp_file
        def track_temp_file(content, suffix):
            nonlocal temp_path_created
            path = original_create(content, suffix)
            temp_path_created = path
            return path

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Server error")

        with patch.object(handler, '_create_temp_file', side_effect=track_temp_file):
            with patch('src.signal.attachment_handler.aiohttp.ClientSession') as mock_session_class:
                mock_session = MagicMock()
                mock_post_cm = AsyncMock()
                mock_post_cm.__aenter__.return_value = mock_response
                mock_session.post.return_value = mock_post_cm

                mock_session_cm = AsyncMock()
                mock_session_cm.__aenter__.return_value = mock_session
                mock_session_class.return_value = mock_session_cm

                result = await handler.send_code_file(
                    recipient="+12345678900",
                    code=sample_code,
                    filename="test.py"
                )

                # Verify temp file was deleted even though upload failed
                assert temp_path_created is not None
                assert not os.path.exists(temp_path_created)
                # Verify result is None on failure
                assert result is None

    @pytest.mark.asyncio
    async def test_send_code_file_handles_upload_failures(self, handler, sample_code):
        """Test that send_code_file handles upload failures gracefully."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Server error")

        with patch('src.signal.attachment_handler.aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_post_cm = AsyncMock()
            mock_post_cm.__aenter__.return_value = mock_response
            mock_session.post.return_value = mock_post_cm

            mock_session_cm = AsyncMock()
            mock_session_cm.__aenter__.return_value = mock_session
            mock_session_class.return_value = mock_session_cm

            result = await handler.send_code_file(
                recipient="+12345678900",
                code=sample_code,
                filename="test.py"
            )

            # Verify returns None on failure (doesn't crash)
            assert result is None

    @pytest.mark.asyncio
    async def test_send_code_file_returns_attachment_id(self, handler, sample_code):
        """Test that send_code_file returns attachment ID from Signal API."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"timestamp": "987654321"})

        with patch('src.signal.attachment_handler.aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_post_cm = AsyncMock()
            mock_post_cm.__aenter__.return_value = mock_response
            mock_session.post.return_value = mock_post_cm

            mock_session_cm = AsyncMock()
            mock_session_cm.__aenter__.return_value = mock_session
            mock_session_class.return_value = mock_session_cm

            result = await handler.send_code_file(
                recipient="+12345678900",
                code=sample_code,
                filename="test.py"
            )

            # Verify returns timestamp as attachment ID
            assert result == "987654321"

    @pytest.mark.asyncio
    async def test_send_code_file_handles_empty_code(self, handler):
        """Test that send_code_file handles empty code gracefully."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"timestamp": "123456789"})

        with patch('src.signal.attachment_handler.aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_post_cm = AsyncMock()
            mock_post_cm.__aenter__.return_value = mock_response
            mock_session.post.return_value = mock_post_cm

            mock_session_cm = AsyncMock()
            mock_session_cm.__aenter__.return_value = mock_session
            mock_session_class.return_value = mock_session_cm

            result = await handler.send_code_file(
                recipient="+12345678900",
                code="",
                filename="empty.txt"
            )

            # Should still work (empty file is valid)
            assert result == "123456789"

    @pytest.mark.asyncio
    async def test_send_code_file_handles_large_files(self, handler):
        """Test that send_code_file handles large code files."""
        # Create large code content (1MB)
        large_code = "# Line\n" * 100000

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"timestamp": "123456789"})

        with patch('src.signal.attachment_handler.aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_post_cm = AsyncMock()
            mock_post_cm.__aenter__.return_value = mock_response
            mock_session.post.return_value = mock_post_cm

            mock_session_cm = AsyncMock()
            mock_session_cm.__aenter__.return_value = mock_session
            mock_session_class.return_value = mock_session_cm

            result = await handler.send_code_file(
                recipient="+12345678900",
                code=large_code,
                filename="large.py"
            )

            # Should handle large files
            assert result == "123456789"

    @pytest.mark.asyncio
    async def test_send_code_file_handles_special_chars_in_filename(self, handler, sample_code):
        """Test that send_code_file handles filenames with special characters."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"timestamp": "123456789"})

        with patch('src.signal.attachment_handler.aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_post_cm = AsyncMock()
            mock_post_cm.__aenter__.return_value = mock_response
            mock_session.post.return_value = mock_post_cm

            mock_session_cm = AsyncMock()
            mock_session_cm.__aenter__.return_value = mock_session
            mock_session_class.return_value = mock_session_cm

            result = await handler.send_code_file(
                recipient="+12345678900",
                code=sample_code,
                filename="my-file_v2.0.py"
            )

            # Should handle special chars
            assert result == "123456789"
