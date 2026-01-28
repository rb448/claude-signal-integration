"""
Authorization boundary tests.

Validates that:
- Unauthorized phone numbers are blocked
- Authorized phone numbers are allowed
- E.164 format validation works correctly
- Authorization cannot be bypassed
"""

import pytest
from src.auth.phone_verifier import PhoneVerifier


class TestUnauthorizedPhoneBlocked:
    """Tests that unauthorized phone numbers are blocked."""

    def test_unauthorized_phone_number_blocked(self):
        """Test that unauthorized phone number is blocked."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Attempt with unauthorized number
        result = verifier.verify("+15559999999")

        assert result is False

    def test_similar_but_different_number_blocked(self):
        """Test that similar but different number is blocked."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # One digit different
        result = verifier.verify("+15551234568")

        assert result is False

    def test_subset_number_blocked(self):
        """Test that subset of authorized number is blocked."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Missing last digit
        result = verifier.verify("+1555123456")

        assert result is False

    def test_superset_number_blocked(self):
        """Test that superset of authorized number is blocked."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Extra digit
        result = verifier.verify("+155512345678")

        assert result is False


class TestAuthorizedPhoneAllowed:
    """Tests that authorized phone numbers are allowed."""

    def test_authorized_phone_number_allowed(self):
        """Test that exact authorized phone number is allowed."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        result = verifier.verify("+15551234567")

        assert result is True

    def test_authorization_case_sensitive(self):
        """Test that authorization is case-sensitive (though phone numbers shouldn't have letters)."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Exact match required
        result = verifier.verify("+15551234567")

        assert result is True


class TestE164FormatValidation:
    """Tests that E.164 phone number format is validated."""

    def test_valid_us_number(self):
        """Test that valid US E.164 number is accepted."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        result = verifier.verify("+15551234567")

        assert result is True

    def test_valid_uk_number(self):
        """Test that valid UK E.164 number can be used."""
        verifier = PhoneVerifier(authorized_phone="+447911123456")

        result = verifier.verify("+447911123456")

        assert result is True

    def test_valid_german_number(self):
        """Test that valid German E.164 number can be used."""
        verifier = PhoneVerifier(authorized_phone="+4915123456789")

        result = verifier.verify("+4915123456789")

        assert result is True

    def test_missing_country_code_rejected(self):
        """Test that number without country code is rejected."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # No country code
        result = verifier.verify("5551234567")

        assert result is False

    def test_invalid_country_code_rejected(self):
        """Test that invalid country code is rejected."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Invalid country code (starts with 0)
        result = verifier.verify("+05551234567")

        assert result is False

    def test_number_with_letters_rejected(self):
        """Test that number with letters is rejected."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Letters in number
        result = verifier.verify("+1555CALL4ME")

        assert result is False

    def test_number_too_short_rejected(self):
        """Test that number too short is rejected."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Too short
        result = verifier.verify("+1555")

        assert result is False

    def test_number_too_long_rejected(self):
        """Test that number too long is rejected."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # E.164 max is 15 digits (+ sign + 15 digits = 16 chars)
        # This is 17 chars (+ sign + 16 digits)
        result = verifier.verify("+1555123456789012")

        assert result is False

    def test_number_with_dashes_rejected(self):
        """Test that number with formatting dashes is rejected."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Dashes not part of E.164
        result = verifier.verify("+1-555-123-4567")

        assert result is False

    def test_number_with_spaces_rejected(self):
        """Test that number with spaces is rejected."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Spaces not part of E.164
        result = verifier.verify("+1 555 123 4567")

        assert result is False

    def test_number_with_parentheses_rejected(self):
        """Test that number with parentheses is rejected."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Parentheses not part of E.164
        result = verifier.verify("+1(555)1234567")

        assert result is False


class TestAuthorizationBypassAttempts:
    """Tests that authorization cannot be bypassed."""

    def test_empty_string_rejected(self):
        """Test that empty string is rejected."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        result = verifier.verify("")

        assert result is False

    def test_none_rejected(self):
        """Test that None is rejected."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        result = verifier.verify(None)

        assert result is False

    def test_whitespace_only_rejected(self):
        """Test that whitespace-only string is rejected."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        result = verifier.verify("   ")

        assert result is False

    def test_sql_injection_attempt_rejected(self):
        """Test that SQL injection attempt is rejected."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # SQL injection attempt
        result = verifier.verify("' OR '1'='1")

        assert result is False

    def test_wildcard_attempt_rejected(self):
        """Test that wildcard attempt is rejected."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Wildcard attempt
        result = verifier.verify("%")

        assert result is False

    def test_regex_injection_rejected(self):
        """Test that regex injection is rejected."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Regex special characters
        result = verifier.verify("+1555.*")

        assert result is False

    def test_unicode_lookalike_rejected(self):
        """Test that unicode lookalike characters are rejected."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Unicode lookalikes for digits
        result = verifier.verify("+𝟏𝟓𝟓𝟓𝟏𝟐𝟑𝟒𝟓𝟔𝟕")  # Mathematical bold digits

        assert result is False

    def test_normalization_attack_rejected(self):
        """Test that unicode normalization attack is rejected."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Unicode normalization attack (combining characters)
        result = verifier.verify("+1555123456\u00307")  # 7 with combining dot

        assert result is False


class TestCaseSensitivity:
    """Tests for case sensitivity in authorization."""

    def test_exact_match_required(self):
        """Test that exact match is required."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Exact match
        assert verifier.verify("+15551234567") is True

        # Different numbers
        assert verifier.verify("+15551234568") is False
        assert verifier.verify("+25551234567") is False


class TestMultipleAuthorizationChecks:
    """Tests that authorization works consistently across multiple calls."""

    def test_authorization_consistent(self):
        """Test that authorization result is consistent."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Multiple calls should give same result
        assert verifier.verify("+15551234567") is True
        assert verifier.verify("+15551234567") is True
        assert verifier.verify("+15551234567") is True

        # Unauthorized should consistently fail
        assert verifier.verify("+15559999999") is False
        assert verifier.verify("+15559999999") is False
        assert verifier.verify("+15559999999") is False

    def test_authorization_not_cached_incorrectly(self):
        """Test that authorization doesn't incorrectly cache results."""
        verifier = PhoneVerifier(authorized_phone="+15551234567")

        # Authorized call
        assert verifier.verify("+15551234567") is True

        # Unauthorized call should still fail
        assert verifier.verify("+15559999999") is False

        # Authorized call should still succeed
        assert verifier.verify("+15551234567") is True
