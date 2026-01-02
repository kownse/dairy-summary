#!/usr/bin/env python3
"""
日记汇总工具 - 从Google Drive获取日记并生成年度AI摘要
"""

import os
import re
import time
from datetime import datetime
from collections import defaultdict
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from anthropic import Anthropic
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# Google Drive API 权限范围
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# Google Drive 文件夹 ID（从环境变量读取）
FOLDER_ID = os.getenv('FOLDER_ID')

# 输出目录
OUTPUT_DIR = Path('output')


def natural_sort_key(text):
    """
    生成用于自然排序的key
    将字符串中的数字部分转换为整数，以实现正确的数字排序
    例如: "2024年1月" < "2024年2月" < "2024年10月"
    """
    def convert(part):
        return int(part) if part.isdigit() else part.lower()

    return [convert(c) for c in re.split(r'(\d+)', text)]


def get_google_credentials():
    """获取Google API认证凭证"""
    creds = None

    # 检查是否存在token.json
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # 如果没有有效凭证，则进行登录
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError(
                    "找不到credentials.json文件。请按照README.md中的说明创建Google Cloud项目并下载凭证。"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # 保存凭证供下次使用
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds


def get_folder_path(service, file_id, visited=None):
    """获取文件或文件夹的完整路径"""
    if visited is None:
        visited = set()

    if file_id in visited:
        return ""
    visited.add(file_id)

    try:
        file_metadata = service.files().get(
            fileId=file_id,
            fields="name, parents"
        ).execute()

        name = file_metadata.get('name', '')
        parents = file_metadata.get('parents', [])

        if not parents or parents[0] == FOLDER_ID:
            return name

        parent_path = get_folder_path(service, parents[0], visited)
        if parent_path:
            return f"{parent_path}/{name}"
        return name

    except HttpError:
        return ""


def list_all_files_recursively(service, folder_id, current_path=""):
    """递归列出文件夹及其子文件夹中的所有Google Docs文件"""
    all_files = []

    try:
        # 获取当前文件夹中的所有项目（文件和子文件夹）
        query = f"'{folder_id}' in parents and trashed=false"

        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType, createdTime, modifiedTime, parents)",
            pageSize=1000
        ).execute()

        items = results.get('files', [])

        # 使用自然排序对文件和文件夹进行排序
        items.sort(key=lambda x: natural_sort_key(x['name']))

        for item in items:
            item_name = item['name']
            item_path = f"{current_path}/{item_name}" if current_path else item_name

            # 如果是文件夹，递归处理
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                print(f"正在扫描文件夹: {item_path}")
                sub_files = list_all_files_recursively(service, item['id'], item_path)
                all_files.extend(sub_files)

            # 如果是Google Docs文件，添加到列表
            elif item['mimeType'] == 'application/vnd.google-apps.document':
                item['path'] = item_path
                all_files.append(item)

        return all_files

    except HttpError as error:
        print(f"获取文件列表时发生错误: {error}")
        return all_files


def extract_year_from_path(file_path):
    """从文件路径中提取年份

    支持的格式：
    - 2024年/2024年1月/2024年1月1日
    - 2024/01/2024-01-01
    - 其他包含年份的路径
    """
    # 尝试匹配各种常见的日期格式
    patterns = [
        r'(\d{4})年',  # 年份后跟"年"字
        r'^(\d{4})/',  # 路径开头的四位数年份
        r'/(\d{4})/',  # 路径中间的四位数年份
        r'(\d{4})[-_]',  # 年份后跟分隔符
        r'(\d{4})',  # 任何四位数年份
    ]

    for pattern in patterns:
        match = re.search(pattern, file_path)
        if match:
            year = int(match.group(1))
            # 验证年份是否合理（1900-2100）
            if 1900 <= year <= 2100:
                return year

    return None


def extract_year_month_from_path(file_path):
    """从文件路径中提取年份和月份

    支持的格式：
    - 2024年/2024年1月/2024年1月1日 -> (2024, 1)
    - 2024/01/2024-01-01 -> (2024, 1)
    - 2024年1月 -> (2024, 1)

    返回: (year, month) 元组，如果无法提取则返回 (None, None)
    """
    # 优先匹配"年月"格式
    patterns = [
        r'(\d{4})年(\d{1,2})月',  # 2024年1月
        r'(\d{4})[/-](\d{1,2})[/-]',  # 2024/01/ 或 2024-01-
        r'(\d{4})年/(\d{1,2})月',  # 2024年/1月
    ]

    for pattern in patterns:
        match = re.search(pattern, file_path)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            # 验证年份和月份是否合理
            if 1900 <= year <= 2100 and 1 <= month <= 12:
                return (year, month)

    # 如果只能提取年份，返回 (year, None)
    year = extract_year_from_path(file_path)
    if year:
        return (year, None)

    return (None, None)


def get_document_content(service, file_id):
    """获取Google Docs文档的纯文本内容"""
    try:
        # 使用export方法导出为纯文本
        request = service.files().export_media(
            fileId=file_id,
            mimeType='text/plain'
        )
        content = request.execute()
        return content.decode('utf-8')

    except HttpError as error:
        print(f"获取文档内容时发生错误: {error}")
        return ""


def group_files_by_year(files):
    """按年份分组文件（不读取内容）"""
    files_by_year = defaultdict(list)

    for file in files:
        filename = file['name']
        file_path = file.get('path', filename)

        # 从路径中提取年份
        year = extract_year_from_path(file_path)
        if year is None:
            print(f"警告: 无法从路径 '{file_path}' 中提取年份，跳过该文件")
            continue

        files_by_year[year].append(file)

    return files_by_year


def group_files_by_year_month(files):
    """按年月分组文件（不读取内容）

    返回: 嵌套字典 {year: {month: [files]}}
    """
    files_by_year_month = defaultdict(lambda: defaultdict(list))

    for file in files:
        filename = file['name']
        file_path = file.get('path', filename)

        # 从路径中提取年份和月份
        year, month = extract_year_month_from_path(file_path)
        if year is None:
            print(f"警告: 无法从路径 '{file_path}' 中提取年份，跳过该文件")
            continue

        if month is None:
            print(f"警告: 无法从路径 '{file_path}' 中提取月份，跳过该文件")
            continue

        files_by_year_month[year][month].append(file)

    return files_by_year_month


def read_year_diaries_from_drive(year, files, drive_service):
    """从Google Drive读取指定年份的所有日记"""
    diaries = []

    print(f"从Google Drive读取 {year} 年的日记...")
    for file in files:
        filename = file['name']
        file_id = file['id']
        file_path = file.get('path', filename)

        print(f"  正在读取: {file_path}")

        # 获取文档内容
        content = get_document_content(drive_service, file_id)

        if content:
            diaries.append({
                'filename': filename,
                'path': file_path,
                'content': content,
                'created_time': file.get('createdTime', ''),
                'modified_time': file.get('modifiedTime', '')
            })

    # 按照路径进行自然排序
    diaries.sort(key=lambda x: natural_sort_key(x['path']))

    return diaries


def estimate_tokens(text):
    """粗略估算文本的token数量（中文按字符计算，英文按单词计算）"""
    # 粗略估算：中文1个字符约1个token，英文1个单词约1.3个token
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    return chinese_chars + int(english_words * 1.3)


def split_diaries_into_batches(diaries, max_tokens=25000):
    """将日记分批，确保每批不超过最大token限制

    默认25,000 tokens是为了符合速率限制（每分钟30,000 tokens）
    """
    batches = []
    current_batch = []
    current_tokens = 0

    for diary in diaries:
        diary_content = f"=== {diary.get('path', diary['filename'])} ===\n{diary['content']}"
        diary_tokens = estimate_tokens(diary_content)

        # 如果当前批次加上新日记会超限，则开始新批次
        if current_tokens + diary_tokens > max_tokens and current_batch:
            batches.append(current_batch)
            current_batch = [diary]
            current_tokens = diary_tokens
        else:
            current_batch.append(diary)
            current_tokens += diary_tokens

    # 添加最后一批
    if current_batch:
        batches.append(current_batch)

    return batches


def call_claude_with_retry(anthropic_client, prompt, max_retries=3):
    """调用Claude API，带有重试机制处理速率限制"""
    for attempt in range(max_retries):
        try:
            message = anthropic_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text

        except Exception as error:
            error_str = str(error)

            # 如果是速率限制错误
            if "rate_limit_error" in error_str or "429" in error_str:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 30  # 30秒、60秒、90秒
                    print(f"  遇到速率限制，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"超过最大重试次数: {error}")

            # 其他错误直接抛出
            raise error


def generate_monthly_summary(year, month, diaries, anthropic_client):
    """使用Claude API为指定月份的日记生成摘要

    参数:
        year: 年份
        month: 月份
        diaries: 该月的日记列表
        anthropic_client: Claude API客户端

    返回:
        月度摘要文本
    """
    print(f"正在为 {year} 年 {month} 月生成AI摘要...")

    # 拼接所有日记内容
    total_content = "\n\n".join([
        f"=== {diary.get('path', diary['filename'])} ===\n{diary['content']}"
        for diary in diaries
    ])

    total_tokens = estimate_tokens(total_content)
    print(f"  约 {total_tokens:,} tokens，{len(diaries)} 篇日记")

    try:
        prompt = f"""请为以下{year}年{month}月的日记内容生成摘要。

要求：
1. 总结这个月的主要事件和经历
2. 提炼出关键的情感和思考
3. 识别重要的变化和发展
4. 保持客观和准确
5. 使用中文输出
6. 摘要长度控制在200-400字

日记内容：

{total_content}

请生成月度摘要："""

        summary = call_claude_with_retry(anthropic_client, prompt)
        time.sleep(2)  # 请求间隔，避免速率限制
        return summary

    except Exception as error:
        print(f"生成月度摘要时发生错误: {error}")
        return f"生成摘要失败: {str(error)}"


def generate_yearly_summary(year, diaries, anthropic_client):
    """使用Claude API为指定年份的日记生成摘要（支持分批处理）"""

    print(f"正在为 {year} 年生成AI摘要...")

    # 估算总token数
    total_content = "\n\n".join([
        f"=== {diary.get('path', diary['filename'])} ===\n{diary['content']}"
        for diary in diaries
    ])
    total_tokens = estimate_tokens(total_content)

    print(f"  总计约 {total_tokens:,} tokens，{len(diaries)} 篇日记")

    try:
        # 如果内容不超过速率限制，可以在合理时间内完成
        if total_tokens < 25000:
            prompt = f"""请为以下{year}年的日记内容生成一个全面的年度摘要。

要求：
1. 总结这一年的主要事件和经历
2. 提炼出关键的情感和思考
3. 识别重要的成长和变化
4. 保持客观和准确
5. 使用中文输出
6. 摘要长度控制在500-1000字

日记内容：

{total_content}

请生成年度摘要："""

            summary = call_claude_with_retry(anthropic_client, prompt)
            time.sleep(2)  # 请求间隔，避免速率限制
            return summary

        # 内容过长，需要分批处理
        else:
            print(f"  内容较多，将分批处理（每批<25,000 tokens）...")
            batches = split_diaries_into_batches(diaries, max_tokens=25000)
            print(f"  分为 {len(batches)} 批处理")
            print(f"  注意：由于API速率限制（每分钟30,000 tokens），批次间需要等待65秒")

            batch_summaries = []

            # 为每批生成摘要
            for i, batch in enumerate(batches, 1):
                print(f"  处理第 {i}/{len(batches)} 批 ({len(batch)} 篇日记)...")

                batch_content = "\n\n".join([
                    f"=== {diary.get('path', diary['filename'])} ===\n{diary['content']}"
                    for diary in batch
                ])

                # 显示当前批次的token估算
                batch_tokens = estimate_tokens(batch_content)
                print(f"    约 {batch_tokens:,} tokens")

                prompt = f"""请为以下{year}年的部分日记内容生成摘要。

要求：
1. 总结这段时期的主要事件和经历
2. 提炼出关键的情感和思考
3. 保持客观和准确
4. 使用中文输出
5. 摘要长度控制在300-500字

日记内容：

{batch_content}

请生成摘要："""

                batch_summary = call_claude_with_retry(anthropic_client, prompt)
                batch_summaries.append(batch_summary)

                # 批次间延迟65秒，确保不超过每分钟30,000 tokens的速率限制
                if i < len(batches):
                    wait_time = 65
                    print(f"    等待 {wait_time} 秒以避免速率限制...")
                    time.sleep(wait_time)

            # 合并所有批次摘要，生成最终年度摘要
            print(f"  合并所有批次摘要，生成最终年度总结...")

            combined_summaries = "\n\n".join([
                f"【第{i}部分摘要】\n{summary}"
                for i, summary in enumerate(batch_summaries, 1)
            ])

            final_prompt = f"""以下是{year}年日记的分段摘要，请基于这些摘要生成一个完整的年度总结。

要求：
1. 整合所有分段摘要的内容
2. 总结这一年的主要事件和经历
3. 提炼出关键的情感和思考
4. 识别重要的成长和变化
5. 保持客观和准确
6. 使用中文输出
7. 摘要长度控制在800-1200字

分段摘要：

{combined_summaries}

请生成完整的年度总结："""

            final_summary = call_claude_with_retry(anthropic_client, final_prompt)
            time.sleep(2)

            return final_summary

    except Exception as error:
        print(f"生成摘要时发生错误: {error}")
        return f"生成摘要失败: {str(error)}"


def generate_yearly_summary_from_monthly(year, monthly_summaries, anthropic_client):
    """基于月度摘要生成年度总结，包括周期性心理活动分析

    参数:
        year: 年份
        monthly_summaries: 字典 {month: summary_text}
        anthropic_client: Claude API客户端

    返回:
        年度总结文本
    """
    print(f"正在为 {year} 年生成年度总结（基于月度摘要）...")

    # 按月份顺序组织摘要
    combined_summaries = ""
    for month in sorted(monthly_summaries.keys()):
        combined_summaries += f"\n\n【{year}年{month}月】\n{monthly_summaries[month]}"

    total_tokens = estimate_tokens(combined_summaries)
    print(f"  月度摘要总计约 {total_tokens:,} tokens")

    try:
        prompt = f"""以下是{year}年每个月的日记摘要，请基于这些月度摘要生成一个完整的年度总结。

要求：
1. 整合所有月度摘要的内容，总结这一年的主要事件和经历
2. 提炼出关键的情感和思考
3. 识别重要的成长和变化
4. **重点分析：发现周期性的心理活动模式**
   - 识别在不同月份中重复出现的情绪、思考或行为模式
   - 分析这些周期性模式可能的触发因素（季节、特定事件、时间节点等）
   - 总结这些周期性心理活动的特点和演变趋势
5. 保持客观和准确
6. 使用中文输出
7. 摘要长度控制在1000-1500字

月度摘要：
{combined_summaries}

请生成完整的年度总结（包含周期性心理活动分析）："""

        summary = call_claude_with_retry(anthropic_client, prompt)
        time.sleep(2)
        return summary

    except Exception as error:
        print(f"生成年度总结时发生错误: {error}")
        return f"生成年度总结失败: {str(error)}"


def save_summary_to_file(year, summary):
    """将年度摘要保存到文件"""
    OUTPUT_DIR.mkdir(exist_ok=True)

    output_file = OUTPUT_DIR / f"{year}_summary.txt"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"{year}年日记摘要\n")
        f.write("=" * 50 + "\n\n")
        f.write(summary)
        f.write("\n\n" + "=" * 50 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    print(f"摘要已保存到: {output_file}")


def save_monthly_summary_to_file(year, month, summary):
    """将月度摘要保存到文件"""
    OUTPUT_DIR.mkdir(exist_ok=True)

    # 创建年份子目录
    year_dir = OUTPUT_DIR / str(year)
    year_dir.mkdir(exist_ok=True)

    output_file = year_dir / f"{year}年{month}月_summary.txt"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"{year}年{month}月日记摘要\n")
        f.write("=" * 50 + "\n\n")
        f.write(summary)
        f.write("\n\n" + "=" * 50 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    print(f"月度摘要已保存到: {output_file}")


def load_monthly_summary_from_file(year, month):
    """从文件加载月度摘要

    返回: 摘要文本，如果文件不存在则返回None
    """
    year_dir = OUTPUT_DIR / str(year)
    output_file = year_dir / f"{year}年{month}月_summary.txt"

    if not output_file.exists():
        return None

    with open(output_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取摘要部分（去掉标题和时间戳）
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
    """将年度所有日记原文拼接并保存到文件"""
    OUTPUT_DIR.mkdir(exist_ok=True)

    output_file = OUTPUT_DIR / f"{year}年日记原文.txt"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"{year}年日记原文合集\n")
        f.write("=" * 60 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"共 {len(diaries)} 篇日记\n")
        f.write("=" * 60 + "\n\n")

        for diary in diaries:
            # 写入日记路径作为标题
            diary_path = diary.get('path', diary['filename'])
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"【{diary_path}】\n")
            f.write("=" * 60 + "\n\n")

            # 写入日记内容
            f.write(diary['content'])
            f.write("\n\n")

    print(f"原文已保存到: {output_file}")


def load_diaries_from_file(year):
    """从已保存的原文文件中读取日记内容

    返回: diaries列表，如果文件不存在则返回None
    """
    output_file = OUTPUT_DIR / f"{year}年日记原文.txt"

    if not output_file.exists():
        return None

    print(f"从缓存文件读取 {year} 年日记: {output_file}")

    diaries = []

    with open(output_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 分割日记条目，使用分隔符
    separator = "\n" + "=" * 60 + "\n【"
    parts = content.split(separator)

    # 跳过第一部分（文件头信息）
    for i, part in enumerate(parts[1:], 1):
        # 提取路径和内容
        lines = part.split("\n")
        if len(lines) < 1:
            continue

        # 第一行是路径（去掉末尾的】）
        path_line = lines[0].rstrip('】')

        # 找到第二个分隔符，之后是内容
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

    print(f"从缓存读取了 {len(diaries)} 篇日记")
    return diaries


def check_cached_years():
    """检查本地缓存的年份

    返回: 缓存年份列表
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
    """提示用户选择处理模式

    参数:
        cached_years: 缓存的年份列表

    返回: True表示仅使用缓存，False表示扫描Drive
    """
    if not cached_years:
        return False

    print(f"发现本地缓存: {len(cached_years)} 个年份 ({min(cached_years)}-{max(cached_years)})")
    print("选项:")
    print("  1. 只使用本地缓存，跳过Google Drive扫描（快速）")
    print("  2. 扫描Google Drive，查找新日记并更新缓存")

    while True:
        choice = input("请选择 (1/2): ").strip()
        if choice == '1':
            print("使用本地缓存模式")
            return True
        elif choice == '2':
            print("将扫描Google Drive")
            return False
        else:
            print("无效选择，请输入 1 或 2")


def load_diaries_from_cache(cached_years):
    """从本地缓存加载日记

    参数:
        cached_years: 缓存的年份列表

    返回: diaries_by_year字典
    """
    print("\n1. 从本地缓存加载日记...")
    diaries_by_year = {}

    for year in cached_years:
        print(f"\n加载 {year} 年...")
        cached_diaries = load_diaries_from_file(year)
        if cached_diaries:
            diaries_by_year[year] = cached_diaries

    return diaries_by_year


def read_diaries_from_drive_for_month(drive_service, files):
    """从Google Drive读取指定文件列表的内容

    参数:
        drive_service: Google Drive服务对象
        files: 文件列表

    返回: 日记列表
    """
    diaries = []
    for file in files:
        filename = file['name']
        file_id = file['id']
        file_path = file.get('path', filename)

        print(f"    正在读取: {file_path}")
        content = get_document_content(drive_service, file_id)

        if content:
            diaries.append({
                'filename': filename,
                'path': file_path,
                'content': content,
                'created_time': file.get('createdTime', ''),
                'modified_time': file.get('modifiedTime', '')
            })

    # 按照路径进行自然排序
    diaries.sort(key=lambda x: natural_sort_key(x['path']))
    return diaries


def load_diaries_from_drive():
    """从Google Drive扫描并加载日记

    返回: (diaries_by_year, diaries_by_year_month) 元组
    """
    print("\n1. 正在连接Google Drive...")
    creds = get_google_credentials()
    drive_service = build('drive', 'v3', credentials=creds)

    print("2. 正在递归扫描文件夹及子文件夹...")
    files = list_all_files_recursively(drive_service, FOLDER_ID)

    if not files:
        print("没有找到任何文件，程序退出")
        return None, None

    print(f"\n总共找到 {len(files)} 个Google Docs文件")

    # 按年月分组文件
    print(f"\n3. 正在按年月分组文件...")
    files_by_year_month = group_files_by_year_month(files)

    if not files_by_year_month:
        print("没有找到任何可处理的文件，程序退出")
        return None, None

    total_months = sum(len(months) for months in files_by_year_month.values())
    print(f"共找到 {len(files_by_year_month)} 个年份，{total_months} 个月的日记")

    # 读取每个月的日记内容
    print(f"\n4. 正在读取日记内容...")

    diaries_by_year = {}
    diaries_by_year_month = defaultdict(dict)

    for year in sorted(files_by_year_month.keys()):
        print(f"\n处理 {year} 年...")

        for month in sorted(files_by_year_month[year].keys()):
            print(f"  处理 {month} 月...")
            files = files_by_year_month[year][month]

            # 读取该月的日记
            diaries = read_diaries_from_drive_for_month(drive_service, files)

            if diaries:
                diaries_by_year_month[year][month] = diaries

                # 同时更新年度日记列表
                if year not in diaries_by_year:
                    diaries_by_year[year] = []
                diaries_by_year[year].extend(diaries)

        # 保存该年的原文
        if year in diaries_by_year:
            print(f"  正在保存 {year} 年原文到文件...")
            save_original_diaries_to_file(year, diaries_by_year[year])

    return diaries_by_year, diaries_by_year_month


def generate_monthly_summaries_for_year(year, month_diaries, anthropic_client):
    """为一年中的所有月份生成或加载摘要

    参数:
        year: 年份
        month_diaries: 按月分组的日记 {month: [diaries]}
        anthropic_client: Claude API客户端

    返回: {month: summary} 字典
    """
    monthly_summaries = {}

    for month in sorted(month_diaries.keys()):
        # 检查月度总结是否已存在
        year_dir = OUTPUT_DIR / str(year)
        monthly_file = year_dir / f"{year}年{month}月_summary.txt"

        if monthly_file.exists():
            print(f"  {month} 月总结已存在，跳过生成: {monthly_file}")
            cached_monthly = load_monthly_summary_from_file(year, month)
            if cached_monthly:
                monthly_summaries[month] = cached_monthly
        else:
            print(f"  处理 {month} 月...")
            # 生成月度摘要
            summary = generate_monthly_summary(year, month, month_diaries[month], anthropic_client)
            monthly_summaries[month] = summary
            save_monthly_summary_to_file(year, month, summary)

    return monthly_summaries


def process_year_summaries(year, diaries_by_year, diaries_by_year_month, use_cache_only, anthropic_client):
    """处理一年的月度和年度摘要

    参数:
        year: 年份
        diaries_by_year: 按年分组的日记
        diaries_by_year_month: 按年月分组的日记
        use_cache_only: 是否仅使用缓存
        anthropic_client: Claude API客户端
    """
    print(f"\n处理 {year} 年...")

    # 检查年度摘要文件是否已存在
    yearly_summary_file = OUTPUT_DIR / f"{year}_summary.txt"
    if yearly_summary_file.exists():
        print(f"  {year} 年的年度摘要已存在，跳过: {yearly_summary_file}")
        return

    # 第一步：为每个月生成摘要
    if use_cache_only:
        # 从缓存加载的情况，需要先按月分组日记
        print(f"  正在按月分组 {year} 年的日记...")
        year_diaries = diaries_by_year[year]

        # 按月分组
        month_diaries = defaultdict(list)
        for diary in year_diaries:
            year_month, month = extract_year_month_from_path(diary.get('path', diary['filename']))
            if month:
                month_diaries[month].append(diary)

        monthly_summaries = generate_monthly_summaries_for_year(year, month_diaries, anthropic_client)
    else:
        # Drive扫描模式，已经按月分组
        if year in diaries_by_year_month:
            monthly_summaries = generate_monthly_summaries_for_year(
                year, diaries_by_year_month[year], anthropic_client
            )
        else:
            monthly_summaries = {}

    # 第二步：基于月度摘要生成年度总结
    if monthly_summaries:
        print(f"\n  基于 {len(monthly_summaries)} 个月的摘要生成年度总结...")
        yearly_summary = generate_yearly_summary_from_monthly(year, monthly_summaries, anthropic_client)
        save_summary_to_file(year, yearly_summary)
    else:
        print(f"  警告: {year} 年没有月度摘要，跳过年度总结生成")


def main():
    """主函数"""
    print("=" * 60)
    print("日记汇总工具")
    print("=" * 60)
    print()

    # 1. 检查环境变量
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("错误: 未找到ANTHROPIC_API_KEY环境变量")
        print("请在.env文件中设置您的Claude API密钥")
        return

    if not FOLDER_ID:
        print("错误: 未找到FOLDER_ID环境变量")
        print("请在.env文件中设置Google Drive文件夹ID")
        return

    # 2. 检查缓存并选择处理模式
    cached_years = check_cached_years()
    use_cache_only = prompt_user_for_mode(cached_years)

    # 3. 加载日记内容
    diaries_by_year_month = None
    if use_cache_only:
        diaries_by_year = load_diaries_from_cache(cached_years)
    else:
        diaries_by_year, diaries_by_year_month = load_diaries_from_drive()
        if diaries_by_year is None:
            return

    if not diaries_by_year:
        print("没有成功读取任何日记内容，程序退出")
        return

    # 4. 初始化Claude客户端
    next_step = 2 if use_cache_only else 5
    print(f"\n{next_step}. 初始化Claude客户端...")
    anthropic_client = Anthropic(api_key=api_key)

    # 5. 生成月度和年度摘要
    next_step += 1
    print(f"\n{next_step}. 开始生成月度和年度AI摘要...")

    for year in sorted(diaries_by_year.keys()):
        process_year_summaries(year, diaries_by_year, diaries_by_year_month, use_cache_only, anthropic_client)

    print("\n" + "=" * 60)
    print("所有处理完成！")
    print(f"输出目录: {OUTPUT_DIR.absolute()}")
    print("=" * 60)


if __name__ == '__main__':
    main()
