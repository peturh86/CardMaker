"""Unit tests for AD Service input sanitization (OData injection prevention)."""
import pytest
from app.ad_service import ADService


class TestSanitizeQuery:
    """Tests for _sanitize_query method — OData injection prevention.
    
    The _sanitize_query method is a pure function (no dependencies on MSAL/network),
    so we can test it by calling it as an unbound method on a dummy instance.
    """

    @pytest.fixture
    def sanitize(self):
        """Get the _sanitize_query method without needing a full ADService instance."""
        # Call the unbound method directly — it only uses `self` for method dispatch
        return lambda query: ADService._sanitize_query(None, query)

    def test_no_special_characters(self, sanitize):
        """Normal input without single quotes passes through unchanged."""
        assert sanitize("John") == "John"

    def test_single_quote_escaped(self, sanitize):
        """A single quote is doubled to prevent OData injection."""
        assert sanitize("O'Brien") == "O''Brien"

    def test_multiple_single_quotes(self, sanitize):
        """Multiple single quotes are all escaped."""
        assert sanitize("O'Bri'en") == "O''Bri''en"

    def test_injection_attempt_escaped(self, sanitize):
        """An OData injection attempt is neutralized by escaping quotes."""
        # Attacker tries: ') or displayName ne null or startsWith(displayName,'
        malicious = "') or displayName ne null or startsWith(displayName,'"
        expected = "'') or displayName ne null or startsWith(displayName,''"
        assert sanitize(malicious) == expected

    def test_empty_string(self, sanitize):
        """Empty string returns empty string."""
        assert sanitize("") == ""

    def test_only_single_quotes(self, sanitize):
        """String of only single quotes gets fully doubled."""
        assert sanitize("'''") == "''''''"

    def test_unicode_characters_preserved(self, sanitize):
        """Non-ASCII characters (Icelandic names) pass through unchanged."""
        assert sanitize("Jón Þórsson") == "Jón Þórsson"

    def test_sanitized_query_used_in_filter(self, sanitize):
        """Verify that sanitized input produces a safe OData filter string."""
        sanitized = sanitize("O'Brien")
        odata_filter = f"startsWith(displayName,'{sanitized}')"
        # The filter should contain the properly escaped value
        assert odata_filter == "startsWith(displayName,'O''Brien')"
