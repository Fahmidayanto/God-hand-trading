"""Custom exceptions for verification system."""


class CSVFormatError(Exception):
    """Raised when CSV file has invalid format.
    
    This exception is raised when a CSV file cannot be parsed correctly
    due to formatting issues, such as invalid data types or malformed rows.
    
    Attributes:
        message: Error message describing the format issue
        row_number: Optional row number where the error occurred
    """
    
    def __init__(self, message: str, row_number: int = None):
        self.message = message
        self.row_number = row_number
        if row_number is not None:
            super().__init__(f"{message} (row {row_number})")
        else:
            super().__init__(message)


class MissingColumnError(Exception):
    """Raised when required columns are missing from CSV file.
    
    This exception is raised when a CSV file is missing one or more
    required columns needed for processing.
    
    Attributes:
        message: Error message describing the missing columns
        missing_columns: List of column names that are missing
    """
    
    def __init__(self, message: str, missing_columns: list = None):
        self.message = message
        self.missing_columns = missing_columns or []
        if missing_columns:
            super().__init__(f"{message}: {', '.join(missing_columns)}")
        else:
            super().__init__(message)


class SectionNotFoundError(Exception):
    """Raised when expected section is not found in markdown file.
    
    This exception is raised when parsing a markdown file and an expected
    section (e.g., Section 11.0b) cannot be found.
    
    Attributes:
        message: Error message describing the missing section
        section_name: Name of the section that was not found
    """
    
    def __init__(self, message: str, section_name: str = None):
        self.message = message
        self.section_name = section_name
        if section_name:
            super().__init__(f"{message}: {section_name}")
        else:
            super().__init__(message)
