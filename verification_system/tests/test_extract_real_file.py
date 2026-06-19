"""Test extract_signal_log_entries with actual 2023.md file."""

from verification_system.parsers.markdown_parser import parse_markdown_file, extract_signal_log_entries


def test_extract_from_real_2023_file():
    """Test extraction with actual 2023.md file."""
    # Parse the actual 2023.md file
    file_path = r"d:\Project\Project MT5\Dokumen\2023.md"
    
    try:
        content = parse_markdown_file(file_path)
        entries = extract_signal_log_entries(content)
        
        print(f"\nExtracted {len(entries)} entries from 2023.md")
        print(f"First entry: {entries[0][:100]}...")
        print(f"Last entry: {entries[-1][:100]}...")
        
        # Verify we have at least 90 entries as per requirements
        assert len(entries) >= 90, f"Expected at least 90 entries, got {len(entries)}"
        
        # Verify all entries are table rows
        for i, entry in enumerate(entries):
            assert entry.startswith('|'), f"Entry {i+1} doesn't start with |: {entry[:50]}"
            assert entry.count('|') >= 10, f"Entry {i+1} doesn't have enough columns: {entry[:50]}"
        
        print("\n✓ All validations passed!")
        
    except FileNotFoundError:
        print("Note: 2023.md file not found at expected location - skipping real file test")
        # Don't fail the test if file doesn't exist in test environment


if __name__ == "__main__":
    test_extract_from_real_2023_file()
