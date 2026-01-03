"""
Path and Date Parsing Utilities Module
Provides file path parsing, year/month extraction, grouping, and sorting functions
"""
import re
from collections import defaultdict


def natural_sort_key(text):
    """
    Generate key for natural sorting
    Converts numeric parts in strings to integers for correct numerical sorting
    Example: "2024年1月" < "2024年2月" < "2024年10月"
    """
    def convert(part):
        return int(part) if part.isdigit() else part.lower()

    return [convert(c) for c in re.split(r'(\d+)', text)]


def extract_year_from_path(file_path):
    """Extract year from file path

    Supported formats:
    - 2024年/2024年1月/2024年1月1日
    - 2024/01/2024-01-01
    - Other paths containing year
    """
    # Try to match various common date formats
    patterns = [
        r'(\d{4})年',  # Year followed by "年"
        r'^(\d{4})/',  # Four-digit year at path beginning
        r'/(\d{4})/',  # Four-digit year in middle of path
        r'(\d{4})[-_]',  # Year followed by separator
        r'(\d{4})',  # Any four-digit year
    ]

    for pattern in patterns:
        match = re.search(pattern, file_path)
        if match:
            year = int(match.group(1))
            # Validate year is reasonable (1900-2100)
            if 1900 <= year <= 2100:
                return year

    return None


def extract_year_month_from_path(file_path):
    """Extract year and month from file path

    Supported formats:
    - 2024年/2024年1月/2024年1月1日 -> (2024, 1)
    - 2024/01/2024-01-01 -> (2024, 1)
    - 2024年1月 -> (2024, 1)

    Returns: (year, month) tuple, or (None, None) if unable to extract
    """
    # Prioritize matching "year-month" format
    patterns = [
        r'(\d{4})年(\d{1,2})月',  # 2024年1月
        r'(\d{4})[/-](\d{1,2})[/-]',  # 2024/01/ or 2024-01-
        r'(\d{4})年/(\d{1,2})月',  # 2024年/1月
    ]

    for pattern in patterns:
        match = re.search(pattern, file_path)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            # Validate year and month are reasonable
            if 1900 <= year <= 2100 and 1 <= month <= 12:
                return (year, month)

    # If only year can be extracted, return (year, None)
    year = extract_year_from_path(file_path)
    if year:
        return (year, None)

    return (None, None)


def group_files_by_year(files):
    """Group files by year (without reading content)"""
    files_by_year = defaultdict(list)

    for file in files:
        filename = file['name']
        file_path = file.get('path', filename)

        # Extract year from path
        year = extract_year_from_path(file_path)
        if year is None:
            print(f"Warning: Unable to extract year from path '{file_path}', skipping file")
            continue

        files_by_year[year].append(file)

    return files_by_year


def group_files_by_year_month(files):
    """Group files by year and month (without reading content)

    Returns: Nested dictionary {year: {month: [files]}}
    """
    files_by_year_month = defaultdict(lambda: defaultdict(list))

    for file in files:
        filename = file['name']
        file_path = file.get('path', filename)

        # Extract year and month from path
        year, month = extract_year_month_from_path(file_path)
        if year is None:
            print(f"Warning: Unable to extract year from path '{file_path}', skipping file")
            continue

        if month is None:
            print(f"Warning: Unable to extract month from path '{file_path}', skipping file")
            continue

        files_by_year_month[year][month].append(file)

    return files_by_year_month
