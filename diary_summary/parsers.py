"""
路径和日期解析工具模块
提供文件路径解析、年月提取、分组和排序功能
"""
import re
from collections import defaultdict


def natural_sort_key(text):
    """
    生成用于自然排序的key
    将字符串中的数字部分转换为整数，以实现正确的数字排序
    例如: "2024年1月" < "2024年2月" < "2024年10月"
    """
    def convert(part):
        return int(part) if part.isdigit() else part.lower()

    return [convert(c) for c in re.split(r'(\d+)', text)]


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
