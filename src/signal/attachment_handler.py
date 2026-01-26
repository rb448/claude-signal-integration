"""Signal attachment handling for code file uploads."""

import os
import re
import tempfile
from pathlib import Path
from typing import Optional

import aiohttp
import structlog

logger = structlog.get_logger(__name__)


class AttachmentHandler:
    """Handle Signal file attachments for code display."""

    MAX_SIZE_BYTES = 100 * 1024 * 1024  # 100MB Signal limit
    LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB warning threshold

    def __init__(self, signal_api_url: str):
        """Initialize attachment handler.

        Args:
            signal_api_url: Base URL for signal-cli-rest-api
        """
        self.signal_api_url = signal_api_url

    async def send_code_file(
        self,
        recipient: str,
        code: str,
        filename: str,
        language: str = None
    ) -> Optional[str]:
        """Send code as Signal attachment.

        Args:
            recipient: Phone number to send to (E.164 format)
            code: Code content
            filename: Display filename (e.g., "user.py")
            language: Optional language for syntax detection

        Returns:
            Attachment ID from Signal API (timestamp), or None if upload failed
        """
        # Validate size
        size_bytes = len(code.encode('utf-8'))
        if size_bytes > self.MAX_SIZE_BYTES:
            logger.error(
                "file_too_large",
                size_bytes=size_bytes,
                max_bytes=self.MAX_SIZE_BYTES,
                filename=filename
            )
            return None

        if size_bytes > self.LARGE_FILE_THRESHOLD:
            logger.warning(
                "large_file_warning",
                size_mb=size_bytes / 1024 / 1024,
                filename=filename
            )

        # Sanitize filename (remove path traversal, invalid chars)
        safe_filename = self._sanitize_filename(filename)

        # Validate recipient (E.164 format)
        if not self._is_valid_phone(recipient):
            logger.error(
                "invalid_recipient",
                recipient=recipient
            )
            return None

        temp_path = None
        try:
            # Create temp file with code content
            suffix = Path(safe_filename).suffix or ".txt"
            temp_path = self._create_temp_file(code, suffix)

            # Upload to Signal via REST API
            attachment_id = await self._upload_attachment(
                temp_path, recipient, safe_filename
            )

            return attachment_id

        finally:
            # Cleanup temp file (even if upload failed)
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
                logger.debug(
                    "temp_file_cleaned",
                    path=temp_path
                )

    def _create_temp_file(self, content: str, suffix: str) -> str:
        """Write content to temp file and return path.

        Args:
            content: Content to write
            suffix: File suffix (e.g., ".py")

        Returns:
            Path to created temp file
        """
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix=suffix,
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(content)
            path = f.name

        logger.debug(
            "temp_file_created",
            path=path,
            size_bytes=len(content.encode('utf-8'))
        )

        return path

    async def _upload_attachment(
        self,
        file_path: str,
        recipient: str,
        display_name: str
    ) -> Optional[str]:
        """Upload file to Signal via REST API.

        Args:
            file_path: Path to file to upload
            recipient: Phone number to send to
            display_name: Filename to display in Signal

        Returns:
            Timestamp from Signal API, or None if upload failed
        """
        url = f"{self.signal_api_url}/v2/send"
        data = {
            "recipients": [recipient],
            "message": f"📎 {display_name}",  # Caption with filename
            "attachments": [file_path]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        timestamp = result.get("timestamp")

                        logger.info(
                            "attachment_uploaded",
                            recipient=recipient,
                            filename=display_name,
                            timestamp=timestamp
                        )

                        return timestamp
                    else:
                        # Log error but don't crash
                        error_text = await response.text()
                        logger.error(
                            "attachment_upload_failed",
                            status=response.status,
                            error=error_text,
                            recipient=recipient,
                            filename=display_name
                        )
                        return None

        except Exception as e:
            logger.error(
                "attachment_upload_exception",
                error=str(e),
                error_type=type(e).__name__,
                recipient=recipient,
                filename=display_name
            )
            return None

    def _sanitize_filename(self, filename: str) -> str:
        """Remove path traversal and invalid characters.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename safe for cross-platform use
        """
        # Get basename (removes any directory path)
        safe = os.path.basename(filename)
        # Remove/replace invalid chars for cross-platform safety
        safe = re.sub(r'[<>:"/\\|?*]', '_', safe)
        # Ensure not empty
        return safe if safe else "code.txt"

    def _is_valid_phone(self, phone: str) -> bool:
        """Validate E.164 phone number format.

        Args:
            phone: Phone number to validate

        Returns:
            True if valid E.164 format, False otherwise
        """
        # E.164: +[country][number], 1-15 digits total
        pattern = r'^\+[1-9]\d{1,14}$'
        return bool(re.match(pattern, phone))
