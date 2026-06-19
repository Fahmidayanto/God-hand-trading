"""Test for extract_signal_log_entries function."""

import pytest
from verification_system.parsers.markdown_parser import extract_signal_log_entries
from verification_system.models.exceptions import SectionNotFoundError


def test_extract_signal_log_entries_basic():
    """Test basic extraction of signal log entries."""
    markdown_content = """# Trading Analysis 2023

### 11.0b Signal Log Lengkap (EXECUTED + REJECTED) — V7 vs V8 vs V9 vs V10

> **Format**: EntryTime | Type | Entry | Session → V7 Status | V8 Status | V9 Status | V10 Status | Net Profit

#### SIGNAL LOG (Sorted by Entry Time — All 4 Versions)

| # | Entry Time | Type | Entry | Session | V7 | V8 | V9 | V10 | Profit | Catatan | Analisa |
|---|-----------|------|-------|---------|----|----|----|-----|--------|---------|---------|
| 1 | 2023.01.04 09:15 | BUY | 1851.18 | Tokyo_London_Overlap | ✅ | ✅ | ✅ | ✅ | +$146.70 | WIN semua | **WIN**: BoS Bullish post-pivot Fed Jan, H1 & H4 EMA200 align bullish. |
| 2 | 2023.01.11 07:45 | BUY | 1884.38 | Sydney_Tokyo_Overlap | ✅ | ✅ | ✅ | ✅ | +$147.18 | WIN semua | **WIN**: BUY pre-London 07:45, momentum continuation Jan rally. |
| 3 | 2023.01.18 05:30 | SELL | 1902.18 | Sydney_Tokyo_Overlap | 🚫 H1 | 🚫 H1 | 🚫 H1 | 🚫 H1 | — | REJECTED H1 EMA | **REJECTED**: SELL counter-trend ditolak semua versi. |

## Next Section
Some other content.
"""
    
    entries = extract_signal_log_entries(markdown_content)
    
    # Should extract 3 entries
    assert len(entries) == 3
    assert all(line.startswith('|') for line in entries)
    assert '2023.01.04 09:15' in entries[0]
    assert '2023.01.11 07:45' in entries[1]
    assert '2023.01.18 05:30' in entries[2]


def test_extract_signal_log_entries_no_section():
    """Test that SectionNotFoundError is raised when section is missing."""
    markdown_content = """# Trading Analysis 2023

## Some Other Section

No signal log here.
"""
    
    with pytest.raises(SectionNotFoundError) as exc_info:
        extract_signal_log_entries(markdown_content)
    
    assert "Section 11.0b" in str(exc_info.value)


def test_extract_signal_log_entries_no_table():
    """Test that SectionNotFoundError is raised when table header is missing."""
    markdown_content = """# Trading Analysis 2023

### 11.0b Signal Log Lengkap

This section exists but has no table.
"""
    
    with pytest.raises(SectionNotFoundError) as exc_info:
        extract_signal_log_entries(markdown_content)
    
    assert "table header not found" in str(exc_info.value).lower()


def test_extract_signal_log_entries_empty_table():
    """Test that SectionNotFoundError is raised when table has no data rows."""
    markdown_content = """# Trading Analysis 2023

### 11.0b Signal Log Lengkap

| # | Entry Time | Type | Entry | Session | V7 | V8 | V9 | V10 | Profit | Catatan | Analisa |
|---|-----------|------|-------|---------|----|----|----|-----|--------|---------|---------|

## Next Section
"""
    
    with pytest.raises(SectionNotFoundError) as exc_info:
        extract_signal_log_entries(markdown_content)
    
    assert "No signal entries found" in str(exc_info.value)


def test_extract_signal_log_entries_multiple_entries():
    """Test extraction with multiple entries and special characters."""
    markdown_content = """### 11.0b Signal Log Lengkap

| # | Entry Time | Type | Entry | Session | V7 | V8 | V9 | V10 | Profit | Catatan | Analisa |
|---|-----------|------|-------|---------|----|----|----|-----|--------|---------|---------|
| 1 | 2023.01.04 09:15 | BUY | 1851.18 | Tokyo | ✅ | ✅ | ✅ | ✅ | +$146.70 | WIN | Analysis 1 |
| 2 | 2023.01.05 10:30 | SELL | 1900.50 | London | ❌ | ❌ | ❌ | ❌ | -$100.50 | LOSS | Analysis 2 |
| 3 | 2023.01.06 14:00 | BUY | 1875.25 | NewYork | 🚫 H1 | 🚫 H1 | 🚫 H1 | 🚫 H1 | — | REJECTED | Analysis 3 |
| 4 | 2023.01.07 08:15 | SELL | 1920.75 | Asia | ✅ | 🚫 BR | ✅ | 🚫 BR | +$150.25 | V7+V9 WIN | Analysis 4 |
"""
    
    entries = extract_signal_log_entries(markdown_content)
    
    assert len(entries) == 4
    assert '✅' in entries[0]
    assert '❌' in entries[1]
    assert '🚫' in entries[2]
    assert 'V7+V9 WIN' in entries[3]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
