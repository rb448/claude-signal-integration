"""Tests for phone number authentication."""

import json
import tempfile
from pathlib import Path

import pytest

from src.auth.phone_verifier import PhoneVerifier


@pytest.fixture
def temp_config():
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config = {
            "authorized_number": "+1234567890",
            "log_level": "INFO"
        }
        json.dump(config, f)
        config_path = f.name

    yield config_path

    # Cleanup
    Path(config_path).unlink(missing_ok=True)


@pytest.fixture
def verifier(temp_config):
    """Create PhoneVerifier with temporary config."""
    return PhoneVerifier(config_path=temp_config)


def test_authorized_number_returns_true(verifier):
    """Test that authorized number returns True."""
    assert verifier.verify("+1234567890") is True


def test_unauthorized_number_returns_false(verifier):
    """Test that unauthorized number returns False."""
    assert verifier.verify("+9999999999") is False


def test_empty_number_returns_false(verifier):
    """Test that empty number returns False."""
    assert verifier.verify("") is False


def test_invalid_format_returns_false(verifier):
    """Test that invalid format returns False."""
    assert verifier.verify("not-a-phone") is False


def test_none_number_returns_false(verifier):
    """Test that None returns False (edge case)."""
    # PhoneVerifier.verify expects string, but handles None gracefully
    # None is falsy, so it's caught by the empty check
    assert verifier.verify(None) is False


def test_loads_config_on_init(temp_config):
    """Test that PhoneVerifier loads config on initialization."""
    verifier = PhoneVerifier(config_path=temp_config)
    assert verifier.authorized_number == "+1234567890"


def test_missing_config_raises_error():
    """Test that missing config file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        PhoneVerifier(config_path="/nonexistent/path/daemon.json")


def test_invalid_json_raises_error():
    """Test that invalid JSON in config raises ValueError."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{ invalid json }")
        config_path = f.name

    try:
        with pytest.raises(ValueError, match="Invalid JSON"):
            PhoneVerifier(config_path=config_path)
    finally:
        Path(config_path).unlink(missing_ok=True)


def test_missing_authorized_number_field_raises_error():
    """Test that missing authorized_number field raises ValueError."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config = {"log_level": "INFO"}
        json.dump(config, f)
        config_path = f.name

    try:
        with pytest.raises(ValueError, match="missing 'authorized_number'"):
            PhoneVerifier(config_path=config_path)
    finally:
        Path(config_path).unlink(missing_ok=True)


def test_empty_authorized_number_raises_error():
    """Test that empty authorized_number raises ValueError."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config = {"authorized_number": ""}
        json.dump(config, f)
        config_path = f.name

    try:
        with pytest.raises(ValueError, match="must be a non-empty string"):
            PhoneVerifier(config_path=config_path)
    finally:
        Path(config_path).unlink(missing_ok=True)


def test_partial_match_returns_false(verifier):
    """Test that partial phone number match returns False (exact match required)."""
    assert verifier.verify("+123456789") is False  # Missing one digit
    assert verifier.verify("+12345678900") is False  # Extra digit


def test_case_sensitivity(verifier):
    """Test that phone numbers are case-sensitive (though E.164 is numeric only)."""
    # E.164 format should only contain +, digits, but test string comparison
    assert verifier.verify("+1234567890") is True
    # This shouldn't happen in practice, but validates exact string matching
    assert verifier.verify("+1234567890 ") is False  # Extra space
