"""
配置管理模块
包含所有常量和环境变量配置
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# Google Drive API 权限范围
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# Google Drive 文件夹 ID（从环境变量读取）
FOLDER_ID = os.getenv('FOLDER_ID')

# 输出目录
OUTPUT_DIR = Path('output')

# Claude API 配置
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4096

# 速率限制配置
RATE_LIMIT_TOKENS_PER_MINUTE = 30000
BATCH_TOKEN_LIMIT = 25000
