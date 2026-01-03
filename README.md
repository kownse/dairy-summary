# Diary Summary Tool

This Python script reads diary documents from Google Drive, organizes them by year, and generates annual summaries using AI.

## Features

- Fetches all Google Docs diary files from a specified Google Drive folder
- Extracts year information from file names
- Organizes diary content by year
- Generates intelligent summaries for each year's diaries using Claude API
- Saves summaries to text files

## Prerequisites

### 1. Set Up Google Cloud Project and API Credentials

#### Step 1: Create a Google Cloud Project

1. Visit [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project selector at the top, then click "New Project"
3. Enter a project name (e.g., "diary-summary"), then click "Create"

#### Step 2: Enable Google Drive API

1. In your project, go to "APIs & Services" > "Library"
2. Search for "Google Drive API"
3. Click on it, then click "Enable"
4. Similarly, search for and enable "Google Docs API"

#### Step 3: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. If prompted to configure the consent screen, select "External" user type and fill in basic information
4. Select "Desktop app" as the application type
5. Enter a name (e.g., "Diary Summary App"), then click "Create"
6. Download the credentials JSON file and rename it to `credentials.json`
7. Place `credentials.json` in the root directory of this project

### 2. Obtain Claude API Key

1. Visit [Anthropic Console](https://console.anthropic.com/)
2. Register or log in to your account
3. Go to the "API Keys" page
4. Create a new API key
5. Copy the API key and save it securely

### 3. Configure Environment Variables

Create a `.env` file in the project root directory:

```
ANTHROPIC_API_KEY=your_api_key_here
```

Replace `your_api_key_here` with your Claude API key.

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Usage

1. Ensure `credentials.json` and `.env` files are properly configured
2. Run the script:

```bash
python diary_summary.py
```

3. On first run, a browser will open requesting authorization to access Google Drive
4. After authorization, the script will:
   - Fetch all diary files from the specified Google Drive folder
   - Organize content by year
   - Generate AI summaries for each year
   - Save results to text files in the `output/` directory

## Output Format

The script creates text files named by year in the `output/` directory, for example:
- `output/2024_summary.txt`
- `output/2023_summary.txt`

Each file contains an AI-generated summary of all diaries for that year.

## Notes

- On first run, a `token.json` file will be generated to store authorization tokens
- Do not commit `credentials.json`, `token.json`, and `.env` files to version control
- The Google Drive folder ID is hardcoded in the code. To change it, modify the `FOLDER_ID` variable in `diary_summary.py`
