"""
Configuration Management Module
Contains all constants and environment variable configurations
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Google Drive API scope
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# Google Drive folder ID (loaded from environment variable)
FOLDER_ID = os.getenv('FOLDER_ID')

# Output directory
OUTPUT_DIR = Path('output')

# Claude API configuration
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4096

# Rate limit configuration
RATE_LIMIT_TOKENS_PER_MINUTE = 30000
BATCH_TOKEN_LIMIT = 25000
