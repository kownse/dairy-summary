"""
Google Drive 操作模块
处理 Google Drive API 认证、文件列表和内容获取
"""
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import SCOPES, FOLDER_ID
from .parsers import natural_sort_key


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
