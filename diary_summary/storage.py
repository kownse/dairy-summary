"""
File Storage and Cache Management Module
Handles reading/writing of diaries and summaries, cache management
"""
import re
from datetime import datetime
from .config import OUTPUT_DIR
from .parsers import natural_sort_key


def save_summary_to_file(year, summary):
    """Save yearly summary to file"""
    OUTPUT_DIR.mkdir(exist_ok=True)

    output_file = OUTPUT_DIR / f"{year}_summary.txt"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"{year}年日记摘要\n")
        f.write("=" * 50 + "\n\n")
        f.write(summary)
        f.write("\n\n" + "=" * 50 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    print(f"Summary saved to: {output_file}")


def save_monthly_summary_to_file(year, month, summary):
    """Save monthly summary to file"""
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Create year subdirectory
    year_dir = OUTPUT_DIR / str(year)
    year_dir.mkdir(exist_ok=True)

    output_file = year_dir / f"{year}年{month}月_summary.txt"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"{year}年{month}月日记摘要\n")
        f.write("=" * 50 + "\n\n")
        f.write(summary)
        f.write("\n\n" + "=" * 50 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    print(f"Monthly summary saved to: {output_file}")


def load_monthly_summary_from_file(year, month):
    """Load monthly summary from file

    Returns: summary text, or None if file doesn't exist
    """
    year_dir = OUTPUT_DIR / str(year)
    output_file = year_dir / f"{year}年{month}月_summary.txt"

    if not output_file.exists():
        return None

    with open(output_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract summary section (remove title and timestamp)
    lines = content.split('\n')
    summary_lines = []
    in_summary = False

    for line in lines:
        if line.startswith('='):
            if not in_summary:
                in_summary = True
                continue
            else:
                break
        elif in_summary:
            summary_lines.append(line)

    return '\n'.join(summary_lines).strip()


def save_original_diaries_to_file(year, diaries):
    """Concatenate and save all yearly diary entries to file"""
    OUTPUT_DIR.mkdir(exist_ok=True)

    output_file = OUTPUT_DIR / f"{year}年日记原文.txt"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"{year}年日记原文合集\n")
        f.write("=" * 60 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"共 {len(diaries)} 篇日记\n")
        f.write("=" * 60 + "\n\n")

        for diary in diaries:
            # Write diary path as title
            diary_path = diary.get('path', diary['filename'])
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"【{diary_path}】\n")
            f.write("=" * 60 + "\n\n")

            # Write diary content
            f.write(diary['content'])
            f.write("\n\n")

    print(f"Original text saved to: {output_file}")


def load_diaries_from_file(year):
    """Load diary content from saved original text file

    Returns: list of diaries, or None if file doesn't exist
    """
    output_file = OUTPUT_DIR / f"{year}年日记原文.txt"

    if not output_file.exists():
        return None

    print(f"Reading {year} diaries from cache file: {output_file}")

    diaries = []

    with open(output_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split diary entries using separator
    separator = "\n" + "=" * 60 + "\n【"
    parts = content.split(separator)

    # Skip first part (file header)
    for i, part in enumerate(parts[1:], 1):
        # Extract path and content
        lines = part.split("\n")
        if len(lines) < 1:
            continue

        # First line is path (remove trailing 】)
        path_line = lines[0].rstrip('】')

        # Find second separator, content follows
        try:
            content_start = part.index("=" * 60 + "\n\n") + len("=" * 60 + "\n\n")
            diary_content = part[content_start:].strip()

            diaries.append({
                'filename': path_line.split('/')[-1] if '/' in path_line else path_line,
                'path': path_line,
                'content': diary_content,
                'created_time': '',
                'modified_time': ''
            })
        except ValueError:
            continue

    print(f"Loaded {len(diaries)} diaries from cache")
    return diaries


def check_cached_years():
    """Check locally cached years

    Returns: list of cached years
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    cached_years = []

    if OUTPUT_DIR.exists():
        for file in OUTPUT_DIR.glob("*年日记原文.txt"):
            year_match = re.search(r'(\d{4})年日记原文\.txt', file.name)
            if year_match:
                cached_years.append(int(year_match.group(1)))

    return sorted(cached_years)


def prompt_user_for_mode(cached_years):
    """Prompt user to select processing mode

    Args:
        cached_years: list of cached years

    Returns: True for cache-only mode, False for Drive scan mode
    """
    if not cached_years:
        return False

    print(f"Found local cache: {len(cached_years)} years ({min(cached_years)}-{max(cached_years)})")
    print("Options:")
    print("  1. Use local cache only, skip Google Drive scan (fast)")
    print("  2. Scan Google Drive, find new diaries and update cache")

    while True:
        choice = input("Please choose (1/2): ").strip()
        if choice == '1':
            print("Using local cache mode")
            return True
        elif choice == '2':
            print("Will scan Google Drive")
            return False
        else:
            print("Invalid choice, please enter 1 or 2")


def load_diaries_from_cache(cached_years):
    """Load diaries from local cache

    Args:
        cached_years: list of cached years

    Returns: diaries_by_year dictionary
    """
    print("\n1. Loading diaries from local cache...")
    diaries_by_year = {}

    for year in cached_years:
        print(f"\nLoading year {year}...")
        cached_diaries = load_diaries_from_file(year)
        if cached_diaries:
            diaries_by_year[year] = cached_diaries

    return diaries_by_year
