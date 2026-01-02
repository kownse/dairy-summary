"""
AI 摘要生成模块
处理 Claude API 调用和摘要生成逻辑
"""
import re
import time
from .config import CLAUDE_MODEL, MAX_TOKENS


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
                model=CLAUDE_MODEL,
                max_tokens=MAX_TOKENS,
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
