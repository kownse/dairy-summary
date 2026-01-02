"""
流程编排模块
协调各个模块完成完整的日记摘要生成流程
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


def run():
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
