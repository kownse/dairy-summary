"""
文件存储和缓存管理模块
处理日记和摘要的读写、缓存管理
"""
import re
from datetime import datetime
from .config import OUTPUT_DIR
from .parsers import natural_sort_key


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
