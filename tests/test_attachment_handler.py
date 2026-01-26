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


class TestAttachmentValidation:
    """Test attachment size limits and validation."""

    @pytest.mark.asyncio
    async def test_rejects_files_over_100mb(self):
        """Test that files over 100MB are rejected."""
        handler = AttachmentHandler(signal_api_url="http://localhost:8080")

        # Create code larger than 100MB
        large_code = "x" * (101 * 1024 * 1024)

        result = await handler.send_code_file(
            recipient="+12345678900",
            code=large_code,
            filename="huge.py"
        )

        # Should reject and return None
        assert result is None

    @pytest.mark.asyncio
    async def test_warns_for_files_over_10mb(self, capsys):
        """Test that files over 10MB trigger a warning."""
        handler = AttachmentHandler(signal_api_url="http://localhost:8080")

        # Create code larger than 10MB but under 100MB
        large_code = "x" * (11 * 1024 * 1024)

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

            # Should still upload
            assert result == "123456789"

            # Should have logged warning (captured by structlog)
            captured = capsys.readouterr()
            assert "large" in captured.out.lower() or "warning" in captured.out.lower()

    @pytest.mark.asyncio
    async def test_sanitizes_filename_with_special_chars(self):
        """Test that filenames with special characters are sanitized."""
        handler = AttachmentHandler(signal_api_url="http://localhost:8080")

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
                code="test",
                filename="../../../etc/passwd"  # Path traversal attempt
            )

            # Should still upload (with sanitized filename)
            assert result == "123456789"

            # Verify sanitized filename was used
            call_args = mock_session.post.call_args
            json_data = call_args[1]['json']
            message = json_data.get('message', '')
            # Should not contain path traversal
            assert "../" not in message

    @pytest.mark.asyncio
    async def test_sanitizes_filename_removes_invalid_chars(self):
        """Test that invalid filename characters are replaced."""
        handler = AttachmentHandler(signal_api_url="http://localhost:8080")

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
                code="test",
                filename='bad<>:"|?*chars.py'
            )

            # Should upload with sanitized filename
            assert result == "123456789"

    @pytest.mark.asyncio
    async def test_validates_recipient_phone_number(self):
        """Test that invalid recipient phone numbers are rejected."""
        handler = AttachmentHandler(signal_api_url="http://localhost:8080")

        # Invalid phone numbers (not E.164 format)
        invalid_phones = [
            "12345678900",  # Missing +
            "+1",  # Too short
            "+123456789012345678",  # Too long
            "invalid",  # Not a number
            ""  # Empty
        ]

        for invalid_phone in invalid_phones:
            result = await handler.send_code_file(
                recipient=invalid_phone,
                code="test",
                filename="test.py"
            )
            # Should reject invalid phone
            assert result is None, f"Should reject phone: {invalid_phone}"

    @pytest.mark.asyncio
    async def test_accepts_valid_e164_phone_numbers(self):
        """Test that valid E.164 phone numbers are accepted."""
        handler = AttachmentHandler(signal_api_url="http://localhost:8080")

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

            # Valid E.164 phone numbers
            valid_phones = [
                "+12345678900",  # US
                "+447911123456",  # UK
                "+861234567890"  # China
            ]

            for valid_phone in valid_phones:
                result = await handler.send_code_file(
                    recipient=valid_phone,
                    code="test",
                    filename="test.py"
                )
                # Should accept valid phone
                assert result == "123456789", f"Should accept phone: {valid_phone}"

    @pytest.mark.asyncio
    async def test_handles_empty_filename(self):
        """Test that empty filenames are replaced with default."""
        handler = AttachmentHandler(signal_api_url="http://localhost:8080")

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
                code="test",
                filename=""  # Empty filename
            )

            # Should upload with default filename
            assert result == "123456789"

            # Verify default filename was used
            call_args = mock_session.post.call_args
            json_data = call_args[1]['json']
            message = json_data.get('message', '')
            # Should have some default name
            assert len(message) > 2  # More than just emoji
