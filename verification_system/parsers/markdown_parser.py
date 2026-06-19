"""Markdown parser for 2023.md trading analysis document."""

import os
import re
from typing import Optional, List

from verification_system.models.exceptions import SectionNotFoundError


def parse_markdown_file(file_path: str) -> str:
    """Parse markdown file and return its content.
    
    Reads the entire file content with UTF-8 encoding. This is the first step
    in processing the trading analysis document before extracting specific sections.
    
    Args:
        file_path: Absolute path to the markdown file to parse
        
    Returns:
        Complete file content as a string
        
    Raises:
        FileNotFoundError: If the file does not exist at the specified path
        
    Examples:
        >>> content = parse_markdown_file("d:/Project/Dokumen/2023.md")
        >>> "# Requirements Document" in content
        True
    """
    # Check if file exists and provide clear error message
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Markdown file not found at path: {file_path}. "
            f"Please verify the file path and ensure the file exists."
        )
    
    # Read entire file content with UTF-8 encoding
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except PermissionError as e:
        raise PermissionError(
            f"Permission denied when reading file: {file_path}. "
            f"Please check file permissions."
        ) from e
    except Exception as e:
        raise IOError(
            f"Error reading file {file_path}: {str(e)}"
        ) from e
    
    return content


def extract_signal_log_entries(markdown_content: str) -> list:
    """Extract trading signal entries from Section 11.0b table.
    
    Searches for Section 11.0b in the markdown content, locates the signal log
    table, and extracts all table rows between the header and the next section.
    
    Args:
        markdown_content: Full markdown file content as a string
        
    Returns:
        List of raw table row strings (excluding header and separator rows)
        
    Raises:
        SectionNotFoundError: If Section 11.0b or the signal log table is not found
        
    Examples:
        >>> content = parse_markdown_file("2023.md")
        >>> entries = extract_signal_log_entries(content)
        >>> len(entries) >= 90  # Should have at least 90 trading entries
        True
    """
    # Look for Section 11.0b header
    section_pattern = r'###\s+11\.0b\s+Signal Log Lengkap'
    section_match = re.search(section_pattern, markdown_content, re.IGNORECASE)
    
    if not section_match:
        raise SectionNotFoundError(
            "Section 11.0b (Signal Log Lengkap) not found in markdown content",
            section_name="11.0b Signal Log Lengkap"
        )
    
    # Find the start of content after the section header
    section_start = section_match.end()
    
    # Look for the table header row (starts with | # | Entry Time |)
    table_header_pattern = r'\|\s*#\s*\|\s*Entry Time\s*\|'
    table_match = re.search(table_header_pattern, markdown_content[section_start:], re.IGNORECASE)
    
    if not table_match:
        raise SectionNotFoundError(
            "Signal log table header not found in Section 11.0b",
            section_name="11.0b Table Header"
        )
    
    # Calculate absolute position of table header
    table_start = section_start + table_match.start()
    
    # Find the end of the table header line
    table_content_start = markdown_content.find('\n', table_start)
    if table_content_start == -1:
        raise SectionNotFoundError(
            "Malformed table structure - no content after header",
            section_name="11.0b Table Content"
        )
    
    # Skip the separator line (e.g., |---|---|---|...)
    separator_end = markdown_content.find('\n', table_content_start + 1)
    if separator_end == -1:
        raise SectionNotFoundError(
            "Malformed table structure - no separator line",
            section_name="11.0b Table Separator"
        )
    
    # Start extracting rows after the separator
    current_pos = separator_end + 1
    
    # Find the end of the table (next section header or end of file)
    # Next section would typically start with ## or ### or end of file
    next_section_pattern = r'\n#{1,4}\s+\S'
    next_section_match = re.search(next_section_pattern, markdown_content[current_pos:])
    
    if next_section_match:
        table_end = current_pos + next_section_match.start()
    else:
        # No next section found, use end of file
        table_end = len(markdown_content)
    
    # Extract table content
    table_content = markdown_content[current_pos:table_end]
    
    # Split into lines and filter for valid table rows
    lines = table_content.split('\n')
    entries = []
    
    for line in lines:
        # Remove leading/trailing whitespace
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
        
        # Valid table row should start with | and contain multiple |
        if line.startswith('|') and line.count('|') >= 10:  # At least 11 columns
            entries.append(line)
    
    if not entries:
        raise SectionNotFoundError(
            "No signal entries found in Section 11.0b table",
            section_name="11.0b Table Rows"
        )
    
    return entries
