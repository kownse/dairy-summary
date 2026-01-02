# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a diary summarization tool that fetches diary entries from Google Drive and generates yearly AI summaries using the Claude API. The tool processes diaries organized in a hierarchical folder structure by year and date.

## Development Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python diary_summary.py
# or
./run.sh
```

### Configuration
Before running, ensure these files are configured:
- `credentials.json` - Google OAuth 2.0 credentials (download from Google Cloud Console)
- `.env` - Contains `ANTHROPIC_API_KEY` (see `.env.example` for template)

## Architecture

### Single-File Application
The entire application logic is contained in `diary_summary.py`. The script follows a hierarchical summarization pipeline:

1. **Authentication** (`get_google_credentials`): OAuth 2.0 flow with Google Drive, stores tokens in `token.json`
2. **File Discovery** (`list_all_files_recursively`): Recursively scans Google Drive folder for Google Docs files
3. **Year-Month Extraction** (`extract_year_month_from_path`, `group_files_by_year_month`): Parses file paths to identify diary year and month using regex patterns. Returns nested dict `{year: {month: [files]}}`
4. **Content Retrieval**: Two modes:
   - Cache mode (`load_diaries_from_file`): Reads from local `output/*年日记原文.txt` files, then groups by month
   - Drive mode: Fetches content via Google Drive API export, organized by year-month
5. **Monthly Summarization** (`generate_monthly_summary`): Generates 200-400 word summaries for each month
6. **Yearly Summarization** (`generate_yearly_summary_from_monthly`): Synthesizes monthly summaries into yearly summary with **periodic psychological pattern analysis**
7. **Output Generation**:
   - Monthly summaries: `output/{year}/{year}年{month}月_summary.txt`
   - Yearly summaries: `output/{year}_summary.txt`
   - Original text: `output/{year}年日记原文.txt`

### Key Design Patterns

**Natural Sorting**: The `natural_sort_key` function ensures chronological ordering of files (e.g., "2024年1月" before "2024年10月")

**Hierarchical Summarization**: Two-tier summarization approach:
- Tier 1: Individual months → monthly summaries (200-400 words each)
- Tier 2: All monthly summaries → yearly summary (1000-1500 words) with periodic pattern analysis

**Periodic Pattern Analysis**: The yearly summary specifically identifies:
- Recurring emotions, thoughts, or behaviors across different months
- Potential triggers (seasonal, event-based, temporal)
- Evolution trends of these cyclical patterns

**Caching System**: Three levels of caching:
1. Original diary text: `output/{year}年日记原文.txt`
2. Monthly summaries: `output/{year}/{year}年{month}月_summary.txt` (checked before regeneration)
3. Yearly summaries: `output/{year}_summary.txt` (checked before regeneration)

On startup, users can choose between:
- Cache-only mode: Processes from `output/*年日记原文.txt`, reuses cached monthly summaries
- Drive scan mode: Fetches fresh content, reuses cached monthly summaries when available

**Retry Logic**: `call_claude_with_retry` handles rate limit errors (429) with exponential backoff (30s, 60s, 90s)

### Google Drive Folder Structure
The tool expects diaries in a specific folder (hardcoded `FOLDER_ID = '1C9IymUfrsp_vbijFraI_beogFDsqlp05'`) with year-month-based organization. Path extraction supports multiple formats:
- `2024年/2024年1月/2024年1月1日` → year=2024, month=1
- `2024/01/2024-01-01` → year=2024, month=1
- `2024年1月` → year=2024, month=1
- Paths without month info are skipped during processing

### Token Estimation
The `estimate_tokens` function provides rough estimates:
- Chinese characters: 1 char ≈ 1 token
- English words: 1 word ≈ 1.3 tokens

Used for monitoring API usage in monthly and yearly summaries.

## Important Notes

- The Google Drive folder ID is hardcoded in `FOLDER_ID` constant
- The Claude model is hardcoded to `claude-sonnet-4-5-20250929`
- Output directory is always `output/` relative to script location
- Interactive prompts ask users to choose between cache-only or drive scan modes
- Monthly and yearly summaries are cached and reused if they already exist
- Files without extractable month information in their paths will be skipped
- Monthly summaries are stored in year-specific subdirectories: `output/{year}/`
