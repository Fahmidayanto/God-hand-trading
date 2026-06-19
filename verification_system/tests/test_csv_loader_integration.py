"""Integration tests for CSV loader with actual project data."""

import pytest
import pandas as pd
from pathlib import Path
from verification_system.loaders.csv_loader import load_csv, validate_csv_structure, REQUIRED_COLUMNS


class TestCSVLoaderIntegration:
    """Integration tests using actual CSV files from the project."""
    
    @pytest.fixture
    def csv_files(self):
        """Return paths to actual CSV files if they exist."""
        base_path = Path(".")
        files = {
            'v7': base_path / 'backtest_v7' / 'Backtest_Results_XAUUSD_2023-12-29.csv',
            'v8': base_path / 'backtest_v8' / 'Backtest_Results_XAUUSD_2023-12-29.csv',
            'v9': base_path / 'backtest_v9' / 'Backtest_Results_XAUUSD_2023-12-29.csv',
            'v10': base_path / 'backtest_v10' / 'Backtest_Results_XAUUSD_2023-12-29.csv',
        }
        # Only return files that exist
        return {k: str(v) for k, v in files.items() if v.exists()}
    
    def test_load_all_versions(self, csv_files):
        """Test that all 4 CSV versions can be loaded successfully."""
        if not csv_files:
            pytest.skip("No CSV files found in project directory")
        
        for version, file_path in csv_files.items():
            df = load_csv(file_path)
            
            # Verify basic structure
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0, f"{version} should have entries"
            
            # Verify all required columns exist
            for col in REQUIRED_COLUMNS:
                assert col in df.columns, f"{version} missing column: {col}"
            
            # Verify valid Status values
            assert df['Status'].isin(['EXECUTED', 'REJECTED']).all()
            
            # Verify valid Type values
            assert df['Type'].isin(['BUY', 'SELL']).all()
    
    def test_rejection_counts_match_requirements(self, csv_files):
        """Test that rejection counts match the requirements specification.
        
        Requirements state:
        - V7: 17 rejections (H1 EMA200 Filter only)
        - V8: 27 rejections (17x H1 + 10x Body Ratio)
        - V9: 41 rejections (17x H1 + 24x H4)
        - V10: 55 rejections (17x H1 + 8x Body Ratio + 30x H4)
        """
        if not csv_files:
            pytest.skip("No CSV files found in project directory")
        
        expected_rejections = {
            'v7': 17,
            'v8': 27,
            'v9': 41,
            'v10': 55
        }
        
        for version, file_path in csv_files.items():
            df = load_csv(file_path)
            rejected_count = len(df[df['Status'] == 'REJECTED'])
            
            assert rejected_count == expected_rejections[version], \
                f"{version} has {rejected_count} rejections, expected {expected_rejections[version]}"
    
    def test_executed_signals_have_valid_data(self, csv_files):
        """Test that EXECUTED signals have valid profit and exit data."""
        if not csv_files:
            pytest.skip("No CSV files found in project directory")
        
        for version, file_path in csv_files.items():
            df = load_csv(file_path)
            executed_signals = df[df['Status'] == 'EXECUTED']
            
            if len(executed_signals) > 0:
                # EXECUTED signals should have non-zero ExitPrice (for WIN/LOSS trades)
                # Note: Some may have ExitPrice = 0 if they exited at breakeven
                # But they should have a valid ExitTime that's not the default rejected time
                assert not executed_signals['ExitTime'].str.startswith('1970.01.01').any(), \
                    f"{version} has EXECUTED signals with invalid ExitTime"
                
                # EXECUTED signals should have Reject_Reason = 'N/A'
                assert (executed_signals['Reject_Reason'] == 'N/A').all(), \
                    f"{version} has EXECUTED signals with non-N/A Reject_Reason"
    
    def test_rejected_signals_have_valid_data(self, csv_files):
        """Test that REJECTED signals have valid rejection reasons."""
        if not csv_files:
            pytest.skip("No CSV files found in project directory")
        
        valid_reject_reasons = [
            'H1 EMA200 Filter',
            'Body Ratio Filter',
            'H4 EMA Filter'
        ]
        
        for version, file_path in csv_files.items():
            df = load_csv(file_path)
            rejected_signals = df[df['Status'] == 'REJECTED']
            
            if len(rejected_signals) > 0:
                # REJECTED signals should have a valid Reject_Reason
                assert rejected_signals['Reject_Reason'].isin(valid_reject_reasons).all(), \
                    f"{version} has REJECTED signals with invalid Reject_Reason"
                
                # REJECTED signals should have ExitTime = '1970.01.01 00:00:00'
                assert (rejected_signals['ExitTime'] == '1970.01.01 00:00:00').all(), \
                    f"{version} has REJECTED signals with non-default ExitTime"
                
                # REJECTED signals should have Net_Profit = 0
                assert (rejected_signals['Net_Profit'] == 0.0).all(), \
                    f"{version} has REJECTED signals with non-zero Net_Profit"
    
    def test_v7_only_has_h1_rejections(self, csv_files):
        """Test that V7 only has H1 EMA200 Filter rejections (Requirement 7.1)."""
        if 'v7' not in csv_files:
            pytest.skip("V7 CSV file not found")
        
        df = load_csv(csv_files['v7'])
        rejected_signals = df[df['Status'] == 'REJECTED']
        
        # V7 should only have H1 EMA200 Filter rejections
        assert (rejected_signals['Reject_Reason'] == 'H1 EMA200 Filter').all(), \
            "V7 has rejections other than H1 EMA200 Filter"
    
    def test_v8_has_h1_and_body_ratio_rejections(self, csv_files):
        """Test that V8 has H1 and Body Ratio rejections (Requirement 7.2)."""
        if 'v8' not in csv_files:
            pytest.skip("V8 CSV file not found")
        
        df = load_csv(csv_files['v8'])
        rejected_signals = df[df['Status'] == 'REJECTED']
        
        # V8 should only have H1 or Body Ratio rejections
        valid_reasons = ['H1 EMA200 Filter', 'Body Ratio Filter']
        assert rejected_signals['Reject_Reason'].isin(valid_reasons).all(), \
            "V8 has rejections other than H1 EMA200 or Body Ratio Filter"
    
    def test_v9_has_h1_and_h4_rejections(self, csv_files):
        """Test that V9 has H1 and H4 rejections (Requirement 7.3)."""
        if 'v9' not in csv_files:
            pytest.skip("V9 CSV file not found")
        
        df = load_csv(csv_files['v9'])
        rejected_signals = df[df['Status'] == 'REJECTED']
        
        # V9 should only have H1 or H4 rejections
        valid_reasons = ['H1 EMA200 Filter', 'H4 EMA Filter']
        assert rejected_signals['Reject_Reason'].isin(valid_reasons).all(), \
            "V9 has rejections other than H1 EMA200 or H4 EMA Filter"
    
    def test_v10_has_all_three_filter_types(self, csv_files):
        """Test that V10 has all three filter types (Requirement 7.4)."""
        if 'v10' not in csv_files:
            pytest.skip("V10 CSV file not found")
        
        df = load_csv(csv_files['v10'])
        rejected_signals = df[df['Status'] == 'REJECTED']
        
        # V10 should only have H1, Body Ratio, or H4 rejections
        valid_reasons = ['H1 EMA200 Filter', 'Body Ratio Filter', 'H4 EMA Filter']
        assert rejected_signals['Reject_Reason'].isin(valid_reasons).all(), \
            "V10 has rejections other than the three valid filter types"
    
    def test_all_required_columns_present(self, csv_files):
        """Test that all required columns are present in all CSV files."""
        if not csv_files:
            pytest.skip("No CSV files found in project directory")
        
        for version, file_path in csv_files.items():
            df = load_csv(file_path)
            
            # Check that all required columns are present
            for col in REQUIRED_COLUMNS:
                assert col in df.columns, \
                    f"{version} missing required column: {col}"
    
    def test_numeric_columns_are_numeric(self, csv_files):
        """Test that numeric columns contain valid numeric data."""
        if not csv_files:
            pytest.skip("No CSV files found in project directory")
        
        numeric_columns = ['EntryPrice', 'ExitPrice', 'SL', 'TP', 'Net_Profit', 'Swap']
        
        for version, file_path in csv_files.items():
            df = load_csv(file_path)
            
            for col in numeric_columns:
                assert pd.api.types.is_numeric_dtype(df[col]), \
                    f"{version} column {col} is not numeric"
                assert not df[col].isna().any(), \
                    f"{version} column {col} contains NaN values"
    
    def test_entry_time_format(self, csv_files):
        """Test that EntryTime has the expected format."""
        if not csv_files:
            pytest.skip("No CSV files found in project directory")
        
        # Expected format: YYYY.MM.DD HH:MM:SS
        time_pattern = r'^\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}$'
        
        for version, file_path in csv_files.items():
            df = load_csv(file_path)
            
            # Check that all EntryTime values match the pattern
            assert df['EntryTime'].str.match(time_pattern).all(), \
                f"{version} has EntryTime values with incorrect format"
    
    def test_validate_structure_passes(self, csv_files):
        """Test that validate_csv_structure passes for all loaded CSV files."""
        if not csv_files:
            pytest.skip("No CSV files found in project directory")
        
        for version, file_path in csv_files.items():
            df = load_csv(file_path)
            
            # This should not raise any exception
            try:
                validate_csv_structure(df, file_path)
            except Exception as e:
                pytest.fail(f"{version} failed structure validation: {str(e)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
