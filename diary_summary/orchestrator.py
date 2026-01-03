"""
Workflow Orchestration Module
Coordinates all modules to complete the full diary summary generation workflow
"""
import os
from collections import defaultdict
from anthropic import Anthropic
from googleapiclient.discovery import build

from .config import FOLDER_ID, OUTPUT_DIR
from .drive import get_google_credentials, list_all_files_recursively, get_document_content
from .parsers import extract_year_month_from_path, group_files_by_year_month, natural_sort_key
from .summarizer import generate_monthly_summary, generate_yearly_summary_from_monthly
from .storage import (
    save_summary_to_file, save_monthly_summary_to_file, load_monthly_summary_from_file,
    save_original_diaries_to_file, check_cached_years, prompt_user_for_mode, load_diaries_from_cache
)


def read_year_diaries_from_drive(year, files, drive_service):
    """Read all diaries for a specified year from Google Drive"""
    diaries = []

    print(f"Reading diaries for year {year} from Google Drive...")
    for file in files:
        filename = file['name']
        file_id = file['id']
        file_path = file.get('path', filename)

        print(f"  Reading: {file_path}")

        # Get document content
        content = get_document_content(drive_service, file_id)

        if content:
            diaries.append({
                'filename': filename,
                'path': file_path,
                'content': content,
                'created_time': file.get('createdTime', ''),
                'modified_time': file.get('modifiedTime', '')
            })

    # Sort by path using natural sort order
    diaries.sort(key=lambda x: natural_sort_key(x['path']))

    return diaries


def read_diaries_from_drive_for_month(drive_service, files):
    """Read content from Google Drive for a specified list of files

    Args:
        drive_service: Google Drive service object
        files: List of files

    Returns: List of diary entries
    """
    diaries = []
    for file in files:
        filename = file['name']
        file_id = file['id']
        file_path = file.get('path', filename)

        print(f"    Reading: {file_path}")
        content = get_document_content(drive_service, file_id)

        if content:
            diaries.append({
                'filename': filename,
                'path': file_path,
                'content': content,
                'created_time': file.get('createdTime', ''),
                'modified_time': file.get('modifiedTime', '')
            })

    # Sort by path using natural sort order
    diaries.sort(key=lambda x: natural_sort_key(x['path']))
    return diaries


def load_diaries_from_drive():
    """Scan and load diaries from Google Drive

    Returns: Tuple of (diaries_by_year, diaries_by_year_month)
    """
    print("\n1. Connecting to Google Drive...")
    creds = get_google_credentials()
    drive_service = build('drive', 'v3', credentials=creds)

    print("2. Recursively scanning folders and subfolders...")
    files = list_all_files_recursively(drive_service, FOLDER_ID)

    if not files:
        print("No files found, exiting program")
        return None, None

    print(f"\nTotal of {len(files)} Google Docs files found")

    # Group files by year and month
    print(f"\n3. Grouping files by year and month...")
    files_by_year_month = group_files_by_year_month(files)

    if not files_by_year_month:
        print("No processable files found, exiting program")
        return None, None

    total_months = sum(len(months) for months in files_by_year_month.values())
    print(f"Found diaries for {len(files_by_year_month)} years, {total_months} months")

    # Read diary content for each month
    print(f"\n4. Reading diary content...")

    diaries_by_year = {}
    diaries_by_year_month = defaultdict(dict)

    for year in sorted(files_by_year_month.keys()):
        print(f"\nProcessing year {year}...")

        for month in sorted(files_by_year_month[year].keys()):
            print(f"  Processing month {month}...")
            files = files_by_year_month[year][month]

            # Read diaries for this month
            diaries = read_diaries_from_drive_for_month(drive_service, files)

            if diaries:
                diaries_by_year_month[year][month] = diaries

                # Also update yearly diary list
                if year not in diaries_by_year:
                    diaries_by_year[year] = []
                diaries_by_year[year].extend(diaries)

        # Save original text for this year
        if year in diaries_by_year:
            print(f"  Saving original text for year {year} to file...")
            save_original_diaries_to_file(year, diaries_by_year[year])

    return diaries_by_year, diaries_by_year_month


def generate_monthly_summaries_for_year(year, month_diaries, anthropic_client):
    """Generate or load summaries for all months in a year

    Args:
        year: The year
        month_diaries: Diaries grouped by month {month: [diaries]}
        anthropic_client: Claude API client

    Returns: Dictionary of {month: summary}
    """
    monthly_summaries = {}

    for month in sorted(month_diaries.keys()):
        # Check if monthly summary already exists
        year_dir = OUTPUT_DIR / str(year)
        monthly_file = year_dir / f"{year}年{month}月_summary.txt"

        if monthly_file.exists():
            print(f"  Summary for month {month} already exists, skipping generation: {monthly_file}")
            cached_monthly = load_monthly_summary_from_file(year, month)
            if cached_monthly:
                monthly_summaries[month] = cached_monthly
        else:
            print(f"  Processing month {month}...")
            # Generate monthly summary
            summary = generate_monthly_summary(year, month, month_diaries[month], anthropic_client)
            monthly_summaries[month] = summary
            save_monthly_summary_to_file(year, month, summary)

    return monthly_summaries


def process_year_summaries(year, diaries_by_year, diaries_by_year_month, use_cache_only, anthropic_client):
    """Process monthly and yearly summaries for a given year

    Args:
        year: The year
        diaries_by_year: Diaries grouped by year
        diaries_by_year_month: Diaries grouped by year and month
        use_cache_only: Whether to use cache only
        anthropic_client: Claude API client
    """
    print(f"\nProcessing year {year}...")

    # Check if yearly summary file already exists
    yearly_summary_file = OUTPUT_DIR / f"{year}_summary.txt"
    if yearly_summary_file.exists():
        print(f"  Yearly summary for {year} already exists, skipping: {yearly_summary_file}")
        return

    # Step 1: Generate summaries for each month
    if use_cache_only:
        # When loading from cache, need to group diaries by month first
        print(f"  Grouping diaries for year {year} by month...")
        year_diaries = diaries_by_year[year]

        # Group by month
        month_diaries = defaultdict(list)
        for diary in year_diaries:
            year_month, month = extract_year_month_from_path(diary.get('path', diary['filename']))
            if month:
                month_diaries[month].append(diary)

        monthly_summaries = generate_monthly_summaries_for_year(year, month_diaries, anthropic_client)
    else:
        # Drive scan mode, already grouped by month
        if year in diaries_by_year_month:
            monthly_summaries = generate_monthly_summaries_for_year(
                year, diaries_by_year_month[year], anthropic_client
            )
        else:
            monthly_summaries = {}

    # Step 2: Generate yearly summary based on monthly summaries
    if monthly_summaries:
        print(f"\n  Generating yearly summary based on {len(monthly_summaries)} monthly summaries...")
        yearly_summary = generate_yearly_summary_from_monthly(year, monthly_summaries, anthropic_client)
        save_summary_to_file(year, yearly_summary)
    else:
        print(f"  Warning: No monthly summaries for year {year}, skipping yearly summary generation")


def run():
    """Main function"""
    print("=" * 60)
    print("Diary Summary Tool")
    print("=" * 60)
    print()

    # 1. Check environment variables
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not found")
        print("Please set your Claude API key in the .env file")
        return

    if not FOLDER_ID:
        print("Error: FOLDER_ID environment variable not found")
        print("Please set the Google Drive folder ID in the .env file")
        return

    # 2. Check cache and select processing mode
    cached_years = check_cached_years()
    use_cache_only = prompt_user_for_mode(cached_years)

    # 3. Load diary content
    diaries_by_year_month = None
    if use_cache_only:
        diaries_by_year = load_diaries_from_cache(cached_years)
    else:
        diaries_by_year, diaries_by_year_month = load_diaries_from_drive()
        if diaries_by_year is None:
            return

    if not diaries_by_year:
        print("Failed to read any diary content, exiting program")
        return

    # 4. Initialize Claude client
    next_step = 2 if use_cache_only else 5
    print(f"\n{next_step}. Initializing Claude client...")
    anthropic_client = Anthropic(api_key=api_key)

    # 5. Generate monthly and yearly summaries
    next_step += 1
    print(f"\n{next_step}. Starting to generate monthly and yearly AI summaries...")

    for year in sorted(diaries_by_year.keys()):
        process_year_summaries(year, diaries_by_year, diaries_by_year_month, use_cache_only, anthropic_client)

    print("\n" + "=" * 60)
    print("All processing complete!")
    print(f"Output directory: {OUTPUT_DIR.absolute()}")
    print("=" * 60)
