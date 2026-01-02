# 日记汇总工具

这个Python脚本从Google Drive中读取日记文档，按年份组织，并使用AI生成年度摘要。

## 功能

- 从指定的Google Drive文件夹中获取所有Google Docs日记文件
- 从文件名中提取年份信息
- 按年份组织日记内容
- 使用Claude API为每年的日记生成智能摘要
- 将摘要保存到文本文件

## 前置要求

### 1. 设置Google Cloud项目和API凭证

#### 步骤1：创建Google Cloud项目

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 点击顶部的项目选择器，然后点击"新建项目"
3. 输入项目名称（如"diary-summary"），点击"创建"

#### 步骤2：启用Google Drive API

1. 在项目中，前往"API和服务" > "库"
2. 搜索"Google Drive API"
3. 点击进入，然后点击"启用"
4. 同样搜索并启用"Google Docs API"

#### 步骤3：创建OAuth 2.0凭证

1. 前往"API和服务" > "凭据"
2. 点击"创建凭据" > "OAuth客户端ID"
3. 如果提示配置同意屏幕，选择"外部"用户类型，填写基本信息
4. 应用类型选择"桌面应用"
5. 输入名称（如"Diary Summary App"），点击"创建"
6. 下载凭证JSON文件，将其重命名为 `credentials.json`
7. 将 `credentials.json` 放在本项目的根目录

### 2. 获取Claude API密钥

1. 访问 [Anthropic Console](https://console.anthropic.com/)
2. 注册或登录账号
3. 前往"API Keys"页面
4. 创建新的API密钥
5. 复制API密钥，妥善保存

### 3. 配置环境变量

创建 `.env` 文件在项目根目录：

```
ANTHROPIC_API_KEY=your_api_key_here
```

将 `your_api_key_here` 替换为您的Claude API密钥。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

1. 确保 `credentials.json` 和 `.env` 文件已正确配置
2. 运行脚本：

```bash
python diary_summary.py
```

3. 首次运行时，会打开浏览器要求您授权访问Google Drive
4. 授权后，脚本会：
   - 从指定的Google Drive文件夹获取所有日记文件
   - 按年份组织内容
   - 为每年生成AI摘要
   - 将结果保存到 `output/` 目录下的文本文件中

## 输出格式

脚本会在 `output/` 目录下创建按年份命名的文本文件，例如：
- `output/2024_summary.txt`
- `output/2023_summary.txt`

每个文件包含该年度所有日记的AI生成摘要。

## 注意事项

- 首次运行时会生成 `token.json` 文件，用于存储授权令牌
- 不要将 `credentials.json`、`token.json` 和 `.env` 文件提交到版本控制系统
- Google Drive文件夹ID已在代码中硬编码，如需更改，请修改 `diary_summary.py` 中的 `FOLDER_ID` 变量
