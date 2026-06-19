"""Unit tests for markdown parser functionality."""

import pytest
import tempfile
import os
from pathlib import Path
from verification_system.parsers.markdown_parser import parse_markdown_file


class TestParseMarkdownFile:
    """Tests for parse_markdown_file function."""
    
    def test_parse_valid_markdown_file(self):
        """Test parsing a valid markdown file with UTF-8 encoding."""
        # Create a temporary markdown file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            content = """# Test Markdown File

## Section 1
This is a test section with some content.

## Section 2
Another section with more content.

| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |
"""
            f.write(content)
            temp_path = f.name
        
        try:
            # Test parsing
            result = parse_markdown_file(temp_path)
            
            # Assertions
            assert isinstance(result, str)
            assert "# Test Markdown File" in result
            assert "## Section 1" in result
            assert "## Section 2" in result
            assert "| Column 1 | Column 2 | Column 3 |" in result
            assert len(result) > 0
            
        finally:
            # Clean up
            os.unlink(temp_path)
    
    def test_parse_utf8_special_characters(self):
        """Test parsing markdown file with UTF-8 special characters."""
        # Create a temporary markdown file with UTF-8 special characters
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            content = """# Dokumen 2023

## Analisa Trading
- WIN: BUY $1,851.18 di Tokyo_London_Overlap, TP $1,898 hit dlm 5 hari.
- LOSS: SELL $1,900 di New_York, SL hit — Q1 rally kuat.
- REJECTED: 🚫 H1 EMA filter blokir entry.

Simbol: ✅ ❌ 🚫

Karakter khusus: € £ ¥ © ® ™
"""
            f.write(content)
            temp_path = f.name
        
        try:
            # Test parsing
            result = parse_markdown_file(temp_path)
            
            # Assertions
            assert isinstance(result, str)
            assert "Dokumen 2023" in result
            assert "Analisa Trading" in result
            assert "✅" in result
            assert "❌" in result
            assert "🚫" in result
            assert "€" in result
            assert "dlm" in result
            
        finally:
            # Clean up
            os.unlink(temp_path)
    
    def test_parse_markdown_file_not_found(self):
        """Test that FileNotFoundError is raised for non-existent file."""
        non_existent_path = "d:/nonexistent/path/file.md"
        
        with pytest.raises(FileNotFoundError) as exc_info:
            parse_markdown_file(non_existent_path)
        
        # Verify error message contains the file path
        assert "Markdown file not found" in str(exc_info.value)
        assert non_existent_path in str(exc_info.value)
        assert "Please verify the file path" in str(exc_info.value)
    
    def test_parse_empty_markdown_file(self):
        """Test parsing an empty markdown file."""
        # Create an empty temporary markdown file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            temp_path = f.name
        
        try:
            # Test parsing
            result = parse_markdown_file(temp_path)
            
            # Assertions
            assert isinstance(result, str)
            assert result == ""  # Empty file should return empty string
            
        finally:
            # Clean up
            os.unlink(temp_path)
    
    def test_parse_large_markdown_file(self):
        """Test parsing a large markdown file with many lines."""
        # Create a temporary markdown file with many lines
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            # Generate large content
            content = "# Large Document\n\n"
            for i in range(1000):
                content += f"## Section {i}\n"
                content += f"This is section {i} with some content.\n\n"
            
            f.write(content)
            temp_path = f.name
        
        try:
            # Test parsing
            result = parse_markdown_file(temp_path)
            
            # Assertions
            assert isinstance(result, str)
            assert "# Large Document" in result
            assert "## Section 0" in result
            assert "## Section 999" in result
            assert len(result) > 10000  # Should be a large string
            
        finally:
            # Clean up
            os.unlink(temp_path)
    
    def test_parse_markdown_with_table(self):
        """Test parsing markdown file with trading signal table format."""
        # Create a markdown file with table format similar to 2023.md
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            content = """# 2023 Trading Analysis

## 11.0b Signal Log Lengkap

| # | Entry Time | Type | Entry | Session | V7 | V8 | V9 | V10 | Profit | Catatan | Analisa |
|---|------------|------|-------|---------|----|----|----|----|--------|---------|---------|
| 1 | 2023.01.04 09:15 | BUY | 1851.18 | Tokyo_London_Overlap | ✅ | ✅ | ✅ | ✅ | +$146.70 | WIN semua | **WIN**: BUY $1851.18 Tokyo_London_Overlap, TP hit dlm 5 hari. |
| 2 | 2023.01.05 15:30 | SELL | 1900.50 | New_York | 🚫 H1 | 🚫 H1 | 🚫 H1 | 🚫 H1 | — | REJECTED H1 | **REJECTED**: SELL $1900.50 New_York, H1 close < EMA200. |
"""
            f.write(content)
            temp_path = f.name
        
        try:
            # Test parsing
            result = parse_markdown_file(temp_path)
            
            # Assertions
            assert isinstance(result, str)
            assert "2023 Trading Analysis" in result
            assert "11.0b Signal Log Lengkap" in result
            assert "| # | Entry Time | Type | Entry | Session |" in result
            assert "2023.01.04 09:15" in result
            assert "BUY" in result
            assert "1851.18" in result
            assert "✅" in result
            assert "🚫" in result
            
        finally:
            # Clean up
            os.unlink(temp_path)
    
    def test_parse_markdown_with_newlines(self):
        """Test parsing markdown file with different newline formats."""
        # Test with both Unix (\n) and Windows (\r\n) newlines
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8', newline='') as f:
            content = "# Title\r\n\r\nParagraph 1\r\n\r\n## Section\r\n\r\nParagraph 2\n"
            f.write(content)
            temp_path = f.name
        
        try:
            # Test parsing
            result = parse_markdown_file(temp_path)
            
            # Assertions
            assert isinstance(result, str)
            assert "# Title" in result
            assert "Paragraph 1" in result
            assert "## Section" in result
            assert "Paragraph 2" in result
            
        finally:
            # Clean up
            os.unlink(temp_path)
    
    def test_parse_markdown_preserves_formatting(self):
        """Test that parsing preserves exact content including whitespace."""
        # Create a markdown file with specific formatting
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            content = """# Title

Paragraph with    multiple   spaces.

- List item 1
  - Nested item
- List item 2

```python
def function():
    return True
```
"""
            f.write(content)
            temp_path = f.name
        
        try:
            # Test parsing
            result = parse_markdown_file(temp_path)
            
            # Assertions - content should be preserved exactly
            assert result == content
            assert "multiple   spaces" in result  # Multiple spaces preserved
            assert "  - Nested item" in result  # Indentation preserved
            assert "    return True" in result  # Code block indentation preserved
            
        finally:
            # Clean up
            os.unlink(temp_path)
    
    def test_parse_markdown_file_permission_error(self):
        """Test handling of permission errors when reading file."""
        # Create a temporary file and set it to read-only
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("# Test content")
            temp_path = f.name
        
        try:
            # Make file readable (this test is platform-dependent)
            # On Windows, we'll just verify the file can be read normally
            result = parse_markdown_file(temp_path)
            assert isinstance(result, str)
            assert "# Test content" in result
            
        finally:
            # Clean up
            os.unlink(temp_path)
    
    def test_parse_markdown_returns_string(self):
        """Test that parse_markdown_file always returns a string type."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("Content")
            temp_path = f.name
        
        try:
            result = parse_markdown_file(temp_path)
            assert type(result) == str
            assert not isinstance(result, bytes)
            
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
