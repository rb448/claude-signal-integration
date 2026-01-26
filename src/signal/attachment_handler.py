"""Signal attachment handling for code file uploads."""

import os
import tempfile
from pathlib import Path
from typing import Optional

import aiohttp
import structlog

logger = structlog.get_logger(__name__)


class AttachmentHandler:
    """Handle Signal file attachments for code display."""

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
        temp_path = None
        try:
            # Create temp file with code content
            suffix = Path(filename).suffix or ".txt"
            temp_path = self._create_temp_file(code, suffix)

            # Upload to Signal via REST API
            attachment_id = await self._upload_attachment(
                temp_path, recipient, filename
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
