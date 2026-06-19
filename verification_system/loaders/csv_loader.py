"""CSV data loader for backtest results."""

import pandas as pd
from pathlib import Path
from typing import List
from ..models.exceptions import CSVFormatError, MissingColumnError


# Required columns for validation
REQUIRED_COLUMNS = [
    "Ticket",
    "Type",
    "EntryPrice",
    "ExitPrice",
    "SL",
    "TP",
    "Net_Profit",
    "Session",
    "EntryTime",
    "ExitTime",
    "Status",
    "Reject_Reason",
    "Swap"
]


def load_csv(file_path: str) -> pd.DataFrame:
    """Load and validate a single CSV backtest file.
    
    This function loads a CSV file containing backtest results and validates
    that all required columns are present. It handles missing files and
    invalid CSV formats with clear error messages.
    
    Args:
        file_path: Path to the CSV file to load
        
    Returns:
        DataFrame containing the validated CSV data
        
    Raises:
        FileNotFoundError: If the CSV file does not exist
        CSVFormatError: If the CSV file cannot be parsed correctly
        MissingColumnError: If required columns are missing
        
    Example:
        >>> df = load_csv("backtest_v7/Backtest_Results_XAUUSD_2023-12-29.csv")
        >>> print(df.shape)
        (120, 21)
    """
    # Check if file exists
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(
            f"CSV file not found: {file_path}\n"
            f"Please ensure the backtest results file exists at the specified path."
        )
    
    # Try to load CSV file
    try:
        df = pd.read_csv(file_path)
    except pd.errors.EmptyDataError:
        raise CSVFormatError(
            f"CSV file is empty: {file_path}",
            row_number=None
        )
    except pd.errors.ParserError as e:
        raise CSVFormatError(
            f"Failed to parse CSV file: {file_path}\n"
            f"Parser error: {str(e)}",
            row_number=None
        )
    except Exception as e:
        raise CSVFormatError(
            f"Unexpected error loading CSV file: {file_path}\n"
            f"Error: {str(e)}",
            row_number=None
        )
    
    # Validate required columns
    missing_columns = []
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            missing_columns.append(col)
    
    if missing_columns:
        raise MissingColumnError(
            f"CSV file is missing required columns: {file_path}",
            missing_columns=missing_columns
        )
    
    # Fill NaN values in Reject_Reason with 'N/A' (standard for EXECUTED signals)
    if 'Reject_Reason' in df.columns:
        df['Reject_Reason'] = df['Reject_Reason'].fillna('N/A')
    
    # Validate data types for critical columns
    try:
        # Ensure numeric columns are numeric
        numeric_columns = ["EntryPrice", "ExitPrice", "SL", "TP", "Net_Profit", "Swap"]
        for col in numeric_columns:
            if col in df.columns:
                # Try to convert to numeric, will raise if not possible
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Check if conversion resulted in NaN values (invalid data)
                if df[col].isna().any():
                    invalid_rows = df[df[col].isna()].index.tolist()
                    first_invalid = invalid_rows[0] + 2  # +2 for 0-indexing and header row
                    raise CSVFormatError(
                        f"Invalid numeric value in column '{col}' in file: {file_path}",
                        row_number=first_invalid
                    )
        
        # Validate Status column values
        valid_statuses = ["EXECUTED", "REJECTED"]
        if "Status" in df.columns:
            invalid_statuses = df[~df["Status"].isin(valid_statuses)]
            if not invalid_statuses.empty:
                first_invalid_row = invalid_statuses.index[0] + 2
                invalid_value = invalid_statuses.iloc[0]["Status"]
                raise CSVFormatError(
                    f"Invalid Status value '{invalid_value}' in file: {file_path}\n"
                    f"Valid values are: {', '.join(valid_statuses)}",
                    row_number=first_invalid_row
                )
        
        # Validate Type column values
        valid_types = ["BUY", "SELL"]
        if "Type" in df.columns:
            invalid_types = df[~df["Type"].isin(valid_types)]
            if not invalid_types.empty:
                first_invalid_row = invalid_types.index[0] + 2
                invalid_value = invalid_types.iloc[0]["Type"]
                raise CSVFormatError(
                    f"Invalid Type value '{invalid_value}' in file: {file_path}\n"
                    f"Valid values are: {', '.join(valid_types)}",
                    row_number=first_invalid_row
                )
        
    except CSVFormatError:
        # Re-raise our custom errors
        raise
    except Exception as e:
        raise CSVFormatError(
            f"Data validation failed for file: {file_path}\n"
            f"Error: {str(e)}",
            row_number=None
        )
    
    return df


def create_signal_key(entry_time: str, trade_type: str, entry_price: float) -> str:
    """Create a unique key for a trading signal.
    
    This function generates a unique identifier for a trading signal by combining
    the entry time (truncated to minute precision), trade type, and entry price.
    The key format is: "{EntryTime}_{Type}_{EntryPrice}"
    
    Args:
        entry_time: Entry timestamp in format "YYYY.MM.DD HH:MM:SS" or "YYYY.MM.DD HH:MM"
        trade_type: Trade type, either "BUY" or "SELL"
        entry_price: Entry price as a float
        
    Returns:
        Unique signal key string in format "YYYY.MM.DD HH:MM_TYPE_PRICE"
        
    Example:
        >>> create_signal_key("2023.01.04 09:15:30", "BUY", 1851.18)
        '2023.01.04 09:15_BUY_1851.18'
        >>> create_signal_key("2023.01.04 09:15", "SELL", 1850.50)
        '2023.01.04 09:15_SELL_1850.5'
    """
    # Parse EntryTime and truncate to minute precision
    # Input format: "YYYY.MM.DD HH:MM:SS" or "YYYY.MM.DD HH:MM"
    # Output format: "YYYY.MM.DD HH:MM"
    
    # Split by space to separate date and time
    parts = entry_time.strip().split()
    
    if len(parts) >= 2:
        date_part = parts[0]  # "YYYY.MM.DD"
        time_part = parts[1]  # "HH:MM:SS" or "HH:MM"
        
        # Truncate time to HH:MM by taking first 5 characters
        time_truncated = time_part[:5]  # "HH:MM"
        
        # Combine date and truncated time
        entry_time_formatted = f"{date_part} {time_truncated}"
    else:
        # If format is unexpected, use as-is
        entry_time_formatted = entry_time.strip()
    
    # Format the signal key
    signal_key = f"{entry_time_formatted}_{trade_type}_{entry_price}"
    
    return signal_key


def merge_all_versions(v7_df: pd.DataFrame, v8_df: pd.DataFrame, 
                      v9_df: pd.DataFrame, v10_df: pd.DataFrame) -> dict:
    """Create unified signal dictionary with union of all signals across 4 versions.
    
    This function merges data from all 4 backtest CSV versions into a single
    unified dictionary. Each signal is uniquely identified by its entry time,
    type, and entry price. The function creates a union set of all signals
    across the 4 versions and builds a nested dictionary structure containing
    data for each version.
    
    Args:
        v7_df: DataFrame containing V7 backtest results
        v8_df: DataFrame containing V8 backtest results
        v9_df: DataFrame containing V9 backtest results
        v10_df: DataFrame containing V10 backtest results
        
    Returns:
        Dictionary mapping signal_key to unified signal data:
        {
            "2023.01.04 09:15_BUY_1851.18": {
                "EntryTime": "2023.01.04 09:15",
                "Type": "BUY",
                "EntryPrice": 1851.18,
                "Session": "Tokyo_London_Overlap",
                "v7": {
                    "Status": "EXECUTED",
                    "Net_Profit": 146.70,
                    "ExitTime": "2023.01.09 16:48:40",
                    "Swap": -3.15,
                    "Reject_Reason": "N/A",
                    "SL": 1848.50,
                    "TP": 1898.00
                },
                "v8": { ... },
                "v9": { ... },
                "v10": { ... }
            },
            ...
        }
        
    Example:
        >>> v7_df = load_csv("backtest_v7/Backtest_Results_XAUUSD_2023-12-29.csv")
        >>> v8_df = load_csv("backtest_v8/Backtest_Results_XAUUSD_2023-12-29.csv")
        >>> v9_df = load_csv("backtest_v9/Backtest_Results_XAUUSD_2023-12-29.csv")
        >>> v10_df = load_csv("backtest_v10/Backtest_Results_XAUUSD_2023-12-29.csv")
        >>> signal_dict = merge_all_versions(v7_df, v8_df, v9_df, v10_df)
        >>> print(len(signal_dict))
        95  # Union of all signals across versions
    """
    # Initialize unified signal dictionary
    unified_signals = {}
    
    # List of dataframes with their version labels
    versions = [
        ("v7", v7_df),
        ("v8", v8_df),
        ("v9", v9_df),
        ("v10", v10_df)
    ]
    
    # Process each version
    for version_name, df in versions:
        for idx, row in df.iterrows():
            # Create signal key for this row
            signal_key = create_signal_key(
                row["EntryTime"], 
                row["Type"], 
                row["EntryPrice"]
            )
            
            # If this is the first time we see this signal, initialize it
            if signal_key not in unified_signals:
                unified_signals[signal_key] = {
                    "EntryTime": signal_key.split("_")[0],  # Extract "YYYY.MM.DD HH:MM"
                    "Type": row["Type"],
                    "EntryPrice": row["EntryPrice"],
                    "Session": row["Session"],
                    "v7": None,
                    "v8": None,
                    "v9": None,
                    "v10": None
                }
            
            # Add version-specific data
            unified_signals[signal_key][version_name] = {
                "Status": row["Status"],
                "Net_Profit": row["Net_Profit"],
                "ExitTime": row["ExitTime"],
                "Swap": row["Swap"],
                "Reject_Reason": row["Reject_Reason"],
                "SL": row["SL"],
                "TP": row["TP"]
            }
    
    return unified_signals


def validate_csv_structure(df: pd.DataFrame, file_path: str) -> None:
    """Additional validation to ensure CSV structure integrity.
    
    This function performs additional validation checks beyond column presence,
    such as ensuring REJECTED signals have no ExitPrice, and EXECUTED signals
    have proper exit data.
    
    Args:
        df: DataFrame to validate
        file_path: Path to the CSV file (for error messages)
        
    Raises:
        CSVFormatError: If validation fails
    """
    # Check REJECTED signals have no meaningful ExitPrice
    rejected_signals = df[df["Status"] == "REJECTED"]
    if not rejected_signals.empty:
        # REJECTED signals should have ExitPrice = 0 or ExitTime = "1970.01.01 00:00:00"
        invalid_rejected = rejected_signals[
            (rejected_signals["ExitPrice"] > 0.0) & 
            (rejected_signals["ExitTime"] != "1970.01.01 00:00:00")
        ]
        if not invalid_rejected.empty:
            first_invalid_row = invalid_rejected.index[0] + 2
            raise CSVFormatError(
                f"REJECTED signal has non-zero ExitPrice in file: {file_path}\n"
                f"REJECTED signals should have ExitPrice=0 and ExitTime='1970.01.01 00:00:00'",
                row_number=first_invalid_row
            )
    
    # Check EXECUTED signals have proper Reject_Reason
    executed_signals = df[df["Status"] == "EXECUTED"]
    if not executed_signals.empty:
        # EXECUTED signals should have Reject_Reason = "N/A"
        invalid_executed = executed_signals[executed_signals["Reject_Reason"] != "N/A"]
        if not invalid_executed.empty:
            first_invalid_row = invalid_executed.index[0] + 2
            reject_reason = invalid_executed.iloc[0]["Reject_Reason"]
            raise CSVFormatError(
                f"EXECUTED signal has Reject_Reason='{reject_reason}' instead of 'N/A' in file: {file_path}",
                row_number=first_invalid_row
            )

