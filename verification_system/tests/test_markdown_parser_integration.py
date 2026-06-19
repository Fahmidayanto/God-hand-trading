"""Integration tests for markdown parser with actual 2023.md file."""

import pytest
import os
from pathlib import Path
from verification_system.parsers.markdown_parser import parse_markdown_file


class TestMarkdownParserIntegration:
    """Integration tests for parsing actual markdown files."""
    
    @pytest.fixture
    def actual_2023_file_path(self):
        """Fixture to get the path to actual 2023.md file."""
        # Path relative to project root
        project_root = Path(__file__).parent.parent.parent
        file_path = project_root / "Dokumen" / "2023.md"
        return str(file_path)
    
    def test_parse_actual_2023_file(self, actual_2023_file_path):
        """Test parsing the actual 2023.md file if it exists."""
        # Skip if file doesn't exist (for CI/CD environments)
        if not os.path.exists(actual_2023_file_path):
            pytest.skip(f"Actual 2023.md file not found at: {actual_2023_file_path}")
        
        # Parse the file
        content = parse_markdown_file(actual_2023_file_path)
        
        # Basic assertions
        assert isinstance(content, str)
        assert len(content) > 1000  # Should be a substantial document
        
        # Check for expected sections based on requirements
        assert "RINGKASAN KOMPARATIF" in content or "2023" in content
        
        # Verify UTF-8 encoding works (check for Indonesian text)
        assert any(word in content for word in ["Instrumen", "Dokumen", "Analisa", "Trading"])
    
    def test_parse_actual_2023_file_has_signal_log(self, actual_2023_file_path):
        """Test that actual 2023.md contains the signal log section."""
        # Skip if file doesn't exist
        if not os.path.exists(actual_2023_file_path):
            pytest.skip(f"Actual 2023.md file not found at: {actual_2023_file_path}")
        
        # Parse the file
        content = parse_markdown_file(actual_2023_file_path)
        
        # Check for signal log section (based on requirements Section 11.0b)
        # The exact section name may vary, so we check for common elements
        has_table_structure = "|" in content and "---" in content
        assert has_table_structure, "File should contain markdown tables"
    
    def test_parse_actual_2023_file_preserves_utf8(self, actual_2023_file_path):
        """Test that UTF-8 special characters are preserved when parsing 2023.md."""
        # Skip if file doesn't exist
        if not os.path.exists(actual_2023_file_path):
            pytest.skip(f"Actual 2023.md file not found at: {actual_2023_file_path}")
        
        # Parse the file
        content = parse_markdown_file(actual_2023_file_path)
        
        # Check for common trading symbols that should be preserved
        # These are based on the requirements (status symbols)
        expected_utf8_chars = ["✅", "❌", "🚫"]
        found_utf8 = [char for char in expected_utf8_chars if char in content]
        
        # At least some UTF-8 symbols should be present
        assert len(found_utf8) > 0, f"Expected UTF-8 symbols not found. Looking for: {expected_utf8_chars}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
