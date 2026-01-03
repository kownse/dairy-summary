"""
AI Summary Generation Module
Handles Claude API calls and summary generation logic
"""
import re
import time
from .config import CLAUDE_MODEL, MAX_TOKENS


def estimate_tokens(text):
    """Roughly estimate the token count of text (Chinese by character, English by word)"""
    # Rough estimate: 1 Chinese character ≈ 1 token, 1 English word ≈ 1.3 tokens
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    return chinese_chars + int(english_words * 1.3)


def split_diaries_into_batches(diaries, max_tokens=25000):
    """Split diaries into batches, ensuring each batch does not exceed max token limit

    Default 25,000 tokens is to comply with rate limits (30,000 tokens per minute)
    """
    batches = []
    current_batch = []
    current_tokens = 0

    for diary in diaries:
        diary_content = f"=== {diary.get('path', diary['filename'])} ===\n{diary['content']}"
        diary_tokens = estimate_tokens(diary_content)

        # If adding the new diary to current batch would exceed limit, start a new batch
        if current_tokens + diary_tokens > max_tokens and current_batch:
            batches.append(current_batch)
            current_batch = [diary]
            current_tokens = diary_tokens
        else:
            current_batch.append(diary)
            current_tokens += diary_tokens

    # Add the last batch
    if current_batch:
        batches.append(current_batch)

    return batches


def call_claude_with_retry(anthropic_client, prompt, max_retries=3):
    """Call Claude API with retry mechanism to handle rate limits"""
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

            # If it's a rate limit error
            if "rate_limit_error" in error_str or "429" in error_str:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 30  # 30s, 60s, 90s
                    print(f"  Encountered rate limit, waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Exceeded maximum retries: {error}")

            # Raise other errors directly
            raise error


def generate_monthly_summary(year, month, diaries, anthropic_client):
    """Generate a summary for diaries of a specific month using Claude API

    Args:
        year: Year
        month: Month
        diaries: List of diaries for the month
        anthropic_client: Claude API client

    Returns:
        Monthly summary text
    """
    print(f"Generating AI summary for {year} Year {month} Month...")

    # Concatenate all diary content
    total_content = "\n\n".join([
        f"=== {diary.get('path', diary['filename'])} ===\n{diary['content']}"
        for diary in diaries
    ])

    total_tokens = estimate_tokens(total_content)
    print(f"  Approximately {total_tokens:,} tokens, {len(diaries)} diary entries")

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
        time.sleep(2)  # Request interval to avoid rate limits
        return summary

    except Exception as error:
        print(f"Error occurred while generating monthly summary: {error}")
        return f"Failed to generate summary: {str(error)}"


def generate_yearly_summary(year, diaries, anthropic_client):
    """Generate a summary for diaries of a specific year using Claude API (supports batch processing)"""

    print(f"Generating AI summary for {year} Year...")

    # Estimate total token count
    total_content = "\n\n".join([
        f"=== {diary.get('path', diary['filename'])} ===\n{diary['content']}"
        for diary in diaries
    ])
    total_tokens = estimate_tokens(total_content)

    print(f"  Total approximately {total_tokens:,} tokens, {len(diaries)} diary entries")

    try:
        # If content doesn't exceed rate limit, can be completed in reasonable time
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
            time.sleep(2)  # Request interval to avoid rate limits
            return summary

        # Content too long, needs batch processing
        else:
            print(f"  Content is large, will process in batches (each batch <25,000 tokens)...")
            batches = split_diaries_into_batches(diaries, max_tokens=25000)
            print(f"  Split into {len(batches)} batches")
            print(f"  Note: Due to API rate limits (30,000 tokens per minute), need to wait 65 seconds between batches")

            batch_summaries = []

            # Generate summary for each batch
            for i, batch in enumerate(batches, 1):
                print(f"  Processing batch {i}/{len(batches)} ({len(batch)} diary entries)...")

                batch_content = "\n\n".join([
                    f"=== {diary.get('path', diary['filename'])} ===\n{diary['content']}"
                    for diary in batch
                ])

                # Display token estimate for current batch
                batch_tokens = estimate_tokens(batch_content)
                print(f"    Approximately {batch_tokens:,} tokens")

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

                # Delay 65 seconds between batches to ensure rate limit of 30,000 tokens per minute is not exceeded
                if i < len(batches):
                    wait_time = 65
                    print(f"    Waiting {wait_time} seconds to avoid rate limits...")
                    time.sleep(wait_time)

            # Merge all batch summaries to generate final yearly summary
            print(f"  Merging all batch summaries to generate final yearly summary...")

            combined_summaries = "\n\n".join([
                f"【Part {i} Summary】\n{summary}"
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
        print(f"Error occurred while generating summary: {error}")
        return f"Failed to generate summary: {str(error)}"


def generate_yearly_summary_from_monthly(year, monthly_summaries, anthropic_client):
    """Generate yearly summary based on monthly summaries, including periodic psychological pattern analysis

    Args:
        year: Year
        monthly_summaries: Dictionary {month: summary_text}
        anthropic_client: Claude API client

    Returns:
        Yearly summary text
    """
    print(f"Generating yearly summary for {year} Year (based on monthly summaries)...")

    # Organize summaries in month order
    combined_summaries = ""
    for month in sorted(monthly_summaries.keys()):
        combined_summaries += f"\n\n【{year} Year {month} Month】\n{monthly_summaries[month]}"

    total_tokens = estimate_tokens(combined_summaries)
    print(f"  Monthly summaries total approximately {total_tokens:,} tokens")

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
        print(f"Error occurred while generating yearly summary: {error}")
        return f"Failed to generate yearly summary: {str(error)}"
