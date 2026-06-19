"""Unit tests for CSV loader functionality."""

import pytest
import pandas as pd
import tempfile
import os
from pathlib import Path
from verification_system.loaders.csv_loader import load_csv, validate_csv_structure, create_signal_key, merge_all_versions, REQUIRED_COLUMNS
from verification_system.models.exceptions import CSVFormatError, MissingColumnError


class TestLoadCSV:
    """Tests for load_csv function."""
    
    def test_load_valid_csv(self):
        """Test loading a valid CSV file with all required columns."""
        # Create a temporary valid CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            # Write header
            f.write(','.join(REQUIRED_COLUMNS) + '\n')
            # Write a sample row
            f.write('12345,BUY,1851.18,1898.23,1848.50,1898.00,146.70,Tokyo_London_Overlap,2023.01.04 09:15:00,2023.01.09 16:48:40,EXECUTED,N/A,-3.15\n')
            temp_path = f.name
        
        try:
            # Test loading
            df = load_csv(temp_path)
            
            # Assertions
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 1
            assert all(col in df.columns for col in REQUIRED_COLUMNS)
            assert df.iloc[0]['Type'] == 'BUY'
            assert df.iloc[0]['Status'] == 'EXECUTED'
            assert df.iloc[0]['EntryPrice'] == 1851.18
            
        finally:
            # Clean up
            os.unlink(temp_path)
    
    def test_load_csv_file_not_found(self):
        """Test that FileNotFoundError is raised for non-existent file."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_csv("nonexistent_file.csv")
        
        assert "CSV file not found" in str(exc_info.value)
    
    def test_load_csv_empty_file(self):
        """Test that CSVFormatError is raised for empty CSV file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name
        
        try:
            with pytest.raises(CSVFormatError) as exc_info:
                load_csv(temp_path)
            
            assert "CSV file is empty" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
    
    def test_load_csv_missing_columns(self):
        """Test that MissingColumnError is raised when required columns are missing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            # Write header with only some columns
            f.write('Ticket,Type,EntryPrice\n')
            f.write('12345,BUY,1851.18\n')
            temp_path = f.name
        
        try:
            with pytest.raises(MissingColumnError) as exc_info:
                load_csv(temp_path)
            
            assert "missing required columns" in str(exc_info.value).lower()
            assert exc_info.value.missing_columns  # Should have list of missing columns
        finally:
            os.unlink(temp_path)
    
    def test_load_csv_invalid_numeric_value(self):
        """Test that CSVFormatError is raised for invalid numeric values."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            # Write header
            f.write(','.join(REQUIRED_COLUMNS) + '\n')
            # Write a row with invalid EntryPrice
            f.write('12345,BUY,INVALID,1898.23,1848.50,1898.00,146.70,Tokyo_London_Overlap,2023.01.04 09:15:00,2023.01.09 16:48:40,EXECUTED,N/A,-3.15\n')
            temp_path = f.name
        
        try:
            with pytest.raises(CSVFormatError) as exc_info:
                load_csv(temp_path)
            
            assert "Invalid numeric value" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
    
    def test_load_csv_invalid_status(self):
        """Test that CSVFormatError is raised for invalid Status values."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            # Write header
            f.write(','.join(REQUIRED_COLUMNS) + '\n')
            # Write a row with invalid Status
            f.write('12345,BUY,1851.18,1898.23,1848.50,1898.00,146.70,Tokyo_London_Overlap,2023.01.04 09:15:00,2023.01.09 16:48:40,INVALID_STATUS,N/A,-3.15\n')
            temp_path = f.name
        
        try:
            with pytest.raises(CSVFormatError) as exc_info:
                load_csv(temp_path)
            
            assert "Invalid Status value" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
    
    def test_load_csv_invalid_type(self):
        """Test that CSVFormatError is raised for invalid Type values."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            # Write header
            f.write(','.join(REQUIRED_COLUMNS) + '\n')
            # Write a row with invalid Type
            f.write('12345,INVALID_TYPE,1851.18,1898.23,1848.50,1898.00,146.70,Tokyo_London_Overlap,2023.01.04 09:15:00,2023.01.09 16:48:40,EXECUTED,N/A,-3.15\n')
            temp_path = f.name
        
        try:
            with pytest.raises(CSVFormatError) as exc_info:
                load_csv(temp_path)
            
            assert "Invalid Type value" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
    
    def test_load_csv_rejected_signal(self):
        """Test loading a CSV with REJECTED signal."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            # Write header
            f.write(','.join(REQUIRED_COLUMNS) + '\n')
            # Write a rejected signal row
            f.write('12346,SELL,1900.50,0.0,1903.00,1895.00,0.0,New_York,2023.01.05 15:30:00,1970.01.01 00:00:00,REJECTED,H1 EMA200 Filter,0.0\n')
            temp_path = f.name
        
        try:
            # Test loading
            df = load_csv(temp_path)
            
            # Assertions
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 1
            assert df.iloc[0]['Status'] == 'REJECTED'
            assert df.iloc[0]['Reject_Reason'] == 'H1 EMA200 Filter'
            assert df.iloc[0]['ExitPrice'] == 0.0
            
        finally:
            os.unlink(temp_path)


class TestValidateCSVStructure:
    """Tests for validate_csv_structure function."""
    
    def test_validate_rejected_signal_structure(self):
        """Test that validation passes for properly formatted REJECTED signal."""
        data = {
            'Ticket': [12346],
            'Type': ['SELL'],
            'EntryPrice': [1900.50],
            'ExitPrice': [0.0],
            'SL': [1903.00],
            'TP': [1895.00],
            'Net_Profit': [0.0],
            'Session': ['New_York'],
            'EntryTime': ['2023.01.05 15:30:00'],
            'ExitTime': ['1970.01.01 00:00:00'],
            'Status': ['REJECTED'],
            'Reject_Reason': ['H1 EMA200 Filter'],
            'Swap': [0.0]
        }
        df = pd.DataFrame(data)
        
        # Should not raise any exception
        validate_csv_structure(df, "test.csv")
    
    def test_validate_executed_signal_structure(self):
        """Test that validation passes for properly formatted EXECUTED signal."""
        data = {
            'Ticket': [12345],
            'Type': ['BUY'],
            'EntryPrice': [1851.18],
            'ExitPrice': [1898.23],
            'SL': [1848.50],
            'TP': [1898.00],
            'Net_Profit': [146.70],
            'Session': ['Tokyo_London_Overlap'],
            'EntryTime': ['2023.01.04 09:15:00'],
            'ExitTime': ['2023.01.09 16:48:40'],
            'Status': ['EXECUTED'],
            'Reject_Reason': ['N/A'],
            'Swap': [-3.15]
        }
        df = pd.DataFrame(data)
        
        # Should not raise any exception
        validate_csv_structure(df, "test.csv")
    
    def test_validate_invalid_rejected_signal(self):
        """Test that validation fails for REJECTED signal with non-zero ExitPrice."""
        data = {
            'Ticket': [12346],
            'Type': ['SELL'],
            'EntryPrice': [1900.50],
            'ExitPrice': [1905.00],  # Invalid: should be 0
            'SL': [1903.00],
            'TP': [1895.00],
            'Net_Profit': [0.0],
            'Session': ['New_York'],
            'EntryTime': ['2023.01.05 15:30:00'],
            'ExitTime': ['2023.01.05 16:00:00'],  # Invalid: should be 1970.01.01 00:00:00
            'Status': ['REJECTED'],
            'Reject_Reason': ['H1 EMA200 Filter'],
            'Swap': [0.0]
        }
        df = pd.DataFrame(data)
        
        with pytest.raises(CSVFormatError) as exc_info:
            validate_csv_structure(df, "test.csv")
        
        assert "REJECTED signal has non-zero ExitPrice" in str(exc_info.value)
    
    def test_validate_invalid_executed_signal(self):
        """Test that validation fails for EXECUTED signal with invalid Reject_Reason."""
        data = {
            'Ticket': [12345],
            'Type': ['BUY'],
            'EntryPrice': [1851.18],
            'ExitPrice': [1898.23],
            'SL': [1848.50],
            'TP': [1898.00],
            'Net_Profit': [146.70],
            'Session': ['Tokyo_London_Overlap'],
            'EntryTime': ['2023.01.04 09:15:00'],
            'ExitTime': ['2023.01.09 16:48:40'],
            'Status': ['EXECUTED'],
            'Reject_Reason': ['H1 EMA200 Filter'],  # Invalid: should be 'N/A'
            'Swap': [-3.15]
        }
        df = pd.DataFrame(data)
        
        with pytest.raises(CSVFormatError) as exc_info:
            validate_csv_structure(df, "test.csv")
        
        assert "EXECUTED signal has Reject_Reason" in str(exc_info.value)


class TestCreateSignalKey:
    """Tests for create_signal_key function."""
    
    def test_create_signal_key_with_seconds(self):
        """Test signal key creation from timestamp with seconds."""
        key = create_signal_key("2023.01.04 09:15:30", "BUY", 1851.18)
        assert key == "2023.01.04 09:15_BUY_1851.18"
    
    def test_create_signal_key_without_seconds(self):
        """Test signal key creation from timestamp without seconds."""
        key = create_signal_key("2023.01.04 09:15", "SELL", 1850.50)
        assert key == "2023.01.04 09:15_SELL_1850.5"
    
    def test_create_signal_key_buy_signal(self):
        """Test signal key creation for BUY signal."""
        key = create_signal_key("2023.03.15 14:30:00", "BUY", 1920.75)
        assert key == "2023.03.15 14:30_BUY_1920.75"
    
    def test_create_signal_key_sell_signal(self):
        """Test signal key creation for SELL signal."""
        key = create_signal_key("2023.06.20 08:45:15", "SELL", 1950.25)
        assert key == "2023.06.20 08:45_SELL_1950.25"
    
    def test_create_signal_key_with_integer_price(self):
        """Test signal key creation with integer price."""
        key = create_signal_key("2023.02.10 12:00:00", "BUY", 1900.0)
        assert key == "2023.02.10 12:00_BUY_1900.0"
    
    def test_create_signal_key_with_high_precision_price(self):
        """Test signal key creation with high precision price."""
        key = create_signal_key("2023.05.18 16:20:45", "SELL", 1875.12345)
        assert key == "2023.05.18 16:20_SELL_1875.12345"
    
    def test_create_signal_key_truncates_to_minutes(self):
        """Test that signal key truncates seconds from timestamp."""
        # Different seconds should produce the same key
        key1 = create_signal_key("2023.01.04 09:15:00", "BUY", 1851.18)
        key2 = create_signal_key("2023.01.04 09:15:30", "BUY", 1851.18)
        key3 = create_signal_key("2023.01.04 09:15:59", "BUY", 1851.18)
        
        assert key1 == key2 == key3 == "2023.01.04 09:15_BUY_1851.18"
    
    def test_create_signal_key_with_whitespace(self):
        """Test signal key creation handles extra whitespace."""
        key = create_signal_key("  2023.01.04 09:15:30  ", "BUY", 1851.18)
        assert key == "2023.01.04 09:15_BUY_1851.18"
    
    def test_create_signal_key_uniqueness(self):
        """Test that different signals produce different keys."""
        key1 = create_signal_key("2023.01.04 09:15:00", "BUY", 1851.18)
        key2 = create_signal_key("2023.01.04 09:16:00", "BUY", 1851.18)  # Different minute
        key3 = create_signal_key("2023.01.04 09:15:00", "SELL", 1851.18)  # Different type
        key4 = create_signal_key("2023.01.04 09:15:00", "BUY", 1851.19)  # Different price
        
        assert key1 != key2
        assert key1 != key3
        assert key1 != key4
        assert key2 != key3
        assert key2 != key4
        assert key3 != key4


class TestMergeAllVersions:
    """Tests for merge_all_versions function."""
    
    def test_merge_single_signal_all_versions(self):
        """Test merging a single signal that exists in all 4 versions."""
        # Create identical signal in all 4 versions with different outcomes
        v7_data = {
            'Ticket': [12345],
            'Type': ['BUY'],
            'EntryPrice': [1851.18],
            'ExitPrice': [1898.23],
            'SL': [1848.50],
            'TP': [1898.00],
            'Net_Profit': [146.70],
            'Session': ['Tokyo_London_Overlap'],
            'EntryTime': ['2023.01.04 09:15:00'],
            'ExitTime': ['2023.01.09 16:48:40'],
            'Status': ['EXECUTED'],
            'Reject_Reason': ['N/A'],
            'Swap': [-3.15]
        }
        
        v8_data = v7_data.copy()
        v8_data['Net_Profit'] = [145.50]  # Slightly different profit
        
        v9_data = v7_data.copy()
        v9_data['Status'] = ['REJECTED']
        v9_data['Reject_Reason'] = ['H4 EMA Filter']
        v9_data['ExitPrice'] = [0.0]
        v9_data['ExitTime'] = ['1970.01.01 00:00:00']
        v9_data['Net_Profit'] = [0.0]
        v9_data['Swap'] = [0.0]
        
        v10_data = v9_data.copy()
        
        v7_df = pd.DataFrame(v7_data)
        v8_df = pd.DataFrame(v8_data)
        v9_df = pd.DataFrame(v9_data)
        v10_df = pd.DataFrame(v10_data)
        
        # Merge all versions
        result = merge_all_versions(v7_df, v8_df, v9_df, v10_df)
        
        # Assertions
        assert len(result) == 1  # Only one unique signal
        
        signal_key = "2023.01.04 09:15_BUY_1851.18"
        assert signal_key in result
        
        signal = result[signal_key]
        assert signal["EntryTime"] == "2023.01.04 09:15"
        assert signal["Type"] == "BUY"
        assert signal["EntryPrice"] == 1851.18
        assert signal["Session"] == "Tokyo_London_Overlap"
        
        # Check V7 data
        assert signal["v7"] is not None
        assert signal["v7"]["Status"] == "EXECUTED"
        assert signal["v7"]["Net_Profit"] == 146.70
        assert signal["v7"]["Swap"] == -3.15
        assert signal["v7"]["Reject_Reason"] == "N/A"
        
        # Check V8 data
        assert signal["v8"] is not None
        assert signal["v8"]["Status"] == "EXECUTED"
        assert signal["v8"]["Net_Profit"] == 145.50
        
        # Check V9 data (rejected)
        assert signal["v9"] is not None
        assert signal["v9"]["Status"] == "REJECTED"
        assert signal["v9"]["Reject_Reason"] == "H4 EMA Filter"
        assert signal["v9"]["Net_Profit"] == 0.0
        
        # Check V10 data (rejected)
        assert signal["v10"] is not None
        assert signal["v10"]["Status"] == "REJECTED"
    
    def test_merge_different_signals_across_versions(self):
        """Test merging when different versions have different signals (union set)."""
        # V7 has signal A
        v7_data = {
            'Ticket': [12345],
            'Type': ['BUY'],
            'EntryPrice': [1851.18],
            'ExitPrice': [1898.23],
            'SL': [1848.50],
            'TP': [1898.00],
            'Net_Profit': [146.70],
            'Session': ['Tokyo_London_Overlap'],
            'EntryTime': ['2023.01.04 09:15:00'],
            'ExitTime': ['2023.01.09 16:48:40'],
            'Status': ['EXECUTED'],
            'Reject_Reason': ['N/A'],
            'Swap': [-3.15]
        }
        
        # V8 has signal A and signal B
        v8_data = {
            'Ticket': [12345, 12346],
            'Type': ['BUY', 'SELL'],
            'EntryPrice': [1851.18, 1900.50],
            'ExitPrice': [1898.23, 0.0],
            'SL': [1848.50, 1903.00],
            'TP': [1898.00, 1895.00],
            'Net_Profit': [146.70, 0.0],
            'Session': ['Tokyo_London_Overlap', 'New_York'],
            'EntryTime': ['2023.01.04 09:15:00', '2023.01.05 15:30:00'],
            'ExitTime': ['2023.01.09 16:48:40', '1970.01.01 00:00:00'],
            'Status': ['EXECUTED', 'REJECTED'],
            'Reject_Reason': ['N/A', 'Body Ratio Filter'],
            'Swap': [-3.15, 0.0]
        }
        
        # V9 has only signal B
        v9_data = {
            'Ticket': [12346],
            'Type': ['SELL'],
            'EntryPrice': [1900.50],
            'ExitPrice': [0.0],
            'SL': [1903.00],
            'TP': [1895.00],
            'Net_Profit': [0.0],
            'Session': ['New_York'],
            'EntryTime': ['2023.01.05 15:30:00'],
            'ExitTime': ['1970.01.01 00:00:00'],
            'Status': ['REJECTED'],
            'Reject_Reason': ['H4 EMA Filter'],
            'Swap': [0.0]
        }
        
        # V10 has signal C only
        v10_data = {
            'Ticket': [12347],
            'Type': ['BUY'],
            'EntryPrice': [1920.00],
            'ExitPrice': [1915.00],
            'SL': [1917.50],
            'TP': [1925.00],
            'Net_Profit': [-50.00],
            'Session': ['London'],
            'EntryTime': ['2023.02.10 12:00:00'],
            'ExitTime': ['2023.02.10 14:30:00'],
            'Status': ['EXECUTED'],
            'Reject_Reason': ['N/A'],
            'Swap': [-1.50]
        }
        
        v7_df = pd.DataFrame(v7_data)
        v8_df = pd.DataFrame(v8_data)
        v9_df = pd.DataFrame(v9_data)
        v10_df = pd.DataFrame(v10_data)
        
        # Merge all versions
        result = merge_all_versions(v7_df, v8_df, v9_df, v10_df)
        
        # Should have 3 unique signals (union of A, B, C)
        assert len(result) == 3
        
        # Check signal A (exists in V7 and V8 only)
        signal_a_key = "2023.01.04 09:15_BUY_1851.18"
        assert signal_a_key in result
        assert result[signal_a_key]["v7"] is not None
        assert result[signal_a_key]["v8"] is not None
        assert result[signal_a_key]["v9"] is None
        assert result[signal_a_key]["v10"] is None
        
        # Check signal B (exists in V8 and V9 only)
        signal_b_key = "2023.01.05 15:30_SELL_1900.5"
        assert signal_b_key in result
        assert result[signal_b_key]["v7"] is None
        assert result[signal_b_key]["v8"] is not None
        assert result[signal_b_key]["v9"] is not None
        assert result[signal_b_key]["v10"] is None
        assert result[signal_b_key]["v8"]["Reject_Reason"] == "Body Ratio Filter"
        assert result[signal_b_key]["v9"]["Reject_Reason"] == "H4 EMA Filter"
        
        # Check signal C (exists in V10 only)
        signal_c_key = "2023.02.10 12:00_BUY_1920.0"
        assert signal_c_key in result
        assert result[signal_c_key]["v7"] is None
        assert result[signal_c_key]["v8"] is None
        assert result[signal_c_key]["v9"] is None
        assert result[signal_c_key]["v10"] is not None
        assert result[signal_c_key]["v10"]["Net_Profit"] == -50.00
    
    def test_merge_empty_dataframes(self):
        """Test merging when one or more dataframes are empty."""
        # Create valid but empty dataframes
        columns = REQUIRED_COLUMNS
        v7_df = pd.DataFrame(columns=columns)
        v8_df = pd.DataFrame(columns=columns)
        v9_df = pd.DataFrame(columns=columns)
        
        # V10 has one signal
        v10_data = {
            'Ticket': [12345],
            'Type': ['BUY'],
            'EntryPrice': [1851.18],
            'ExitPrice': [1898.23],
            'SL': [1848.50],
            'TP': [1898.00],
            'Net_Profit': [146.70],
            'Session': ['Tokyo_London_Overlap'],
            'EntryTime': ['2023.01.04 09:15:00'],
            'ExitTime': ['2023.01.09 16:48:40'],
            'Status': ['EXECUTED'],
            'Reject_Reason': ['N/A'],
            'Swap': [-3.15]
        }
        v10_df = pd.DataFrame(v10_data)
        
        # Merge all versions
        result = merge_all_versions(v7_df, v8_df, v9_df, v10_df)
        
        # Should have 1 signal from V10 only
        assert len(result) == 1
        
        signal_key = "2023.01.04 09:15_BUY_1851.18"
        assert signal_key in result
        assert result[signal_key]["v7"] is None
        assert result[signal_key]["v8"] is None
        assert result[signal_key]["v9"] is None
        assert result[signal_key]["v10"] is not None
    
    def test_merge_extracts_all_required_fields(self):
        """Test that merge extracts all required fields from CSV."""
        v7_data = {
            'Ticket': [12345],
            'Type': ['BUY'],
            'EntryPrice': [1851.18],
            'ExitPrice': [1898.23],
            'SL': [1848.50],
            'TP': [1898.00],
            'Net_Profit': [146.70],
            'Session': ['Tokyo_London_Overlap'],
            'EntryTime': ['2023.01.04 09:15:00'],
            'ExitTime': ['2023.01.09 16:48:40'],
            'Status': ['EXECUTED'],
            'Reject_Reason': ['N/A'],
            'Swap': [-3.15]
        }
        
        v7_df = pd.DataFrame(v7_data)
        v8_df = pd.DataFrame(columns=REQUIRED_COLUMNS)
        v9_df = pd.DataFrame(columns=REQUIRED_COLUMNS)
        v10_df = pd.DataFrame(columns=REQUIRED_COLUMNS)
        
        result = merge_all_versions(v7_df, v8_df, v9_df, v10_df)
        
        signal_key = "2023.01.04 09:15_BUY_1851.18"
        signal = result[signal_key]
        
        # Check all required version data fields are present
        v7_data_dict = signal["v7"]
        assert "Status" in v7_data_dict
        assert "Net_Profit" in v7_data_dict
        assert "ExitTime" in v7_data_dict
        assert "Swap" in v7_data_dict
        assert "Reject_Reason" in v7_data_dict
        assert "SL" in v7_data_dict
        assert "TP" in v7_data_dict
        
        # Check values match
        assert v7_data_dict["Status"] == "EXECUTED"
        assert v7_data_dict["Net_Profit"] == 146.70
        assert v7_data_dict["ExitTime"] == "2023.01.09 16:48:40"
        assert v7_data_dict["Swap"] == -3.15
        assert v7_data_dict["Reject_Reason"] == "N/A"
        assert v7_data_dict["SL"] == 1848.50
        assert v7_data_dict["TP"] == 1898.00


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

