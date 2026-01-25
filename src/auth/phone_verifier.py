"""Phone number authentication for Signal bot."""

import json
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


class PhoneVerifier:
    """Verifies incoming messages against authorized phone number.

    Only messages from the configured authorized phone number are processed.
    All other messages are logged and rejected.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """Initialize phone verifier.

        Args:
            config_path: Path to daemon.json config file (default: config/daemon.json)
        """
        if config_path is None:
            # Default to config/daemon.json relative to project root
            project_root = Path(__file__).parent.parent.parent
            config_path = str(project_root / "config" / "daemon.json")

        self.config_path = config_path
        self.authorized_number = self._load_authorized_number()

    def _load_authorized_number(self) -> str:
        """Load authorized phone number from config file.

        Returns:
            str: Authorized phone number in E.164 format

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid or missing authorized_number
        """
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)

            if 'authorized_number' not in config:
                raise ValueError("Config missing 'authorized_number' field")

            authorized = config['authorized_number']
            if not isinstance(authorized, str) or not authorized:
                raise ValueError("'authorized_number' must be a non-empty string")

            logger.debug("authorized_number_loaded", config_path=self.config_path)
            return authorized

        except FileNotFoundError:
            logger.error("config_file_not_found", config_path=self.config_path)
            raise
        except json.JSONDecodeError as e:
            logger.error("config_invalid_json", config_path=self.config_path, error=str(e))
            raise ValueError(f"Invalid JSON in config file: {e}")

    def verify(self, phone_number: str) -> bool:
        """Verify if phone number is authorized.

        Args:
            phone_number: Phone number to verify (E.164 format, e.g., +1234567890)

        Returns:
            bool: True if phone number matches authorized_number, False otherwise
        """
        if not phone_number:
            logger.warning("auth_failed_empty_number", phone_number=phone_number)
            return False

        is_authorized = phone_number == self.authorized_number

        if is_authorized:
            logger.info("auth_success", phone_number=phone_number)
        else:
            logger.warning(
                "auth_failed_unauthorized",
                phone_number=phone_number,
                authorized_number=self.authorized_number
            )

        return is_authorized
