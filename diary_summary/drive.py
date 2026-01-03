"""
Google Drive Operations Module
Handles Google Drive API authentication, file listing, and content retrieval
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
    """Get Google API authentication credentials"""
    creds = None

    # Check if token.json exists
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If no valid credentials, perform login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError(
                    "credentials.json file not found. Please follow instructions in README.md to create a Google Cloud project and download credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for next use
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds


def get_folder_path(service, file_id, visited=None):
    """Get the full path of a file or folder"""
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
    """Recursively list all Google Docs files in a folder and its subfolders"""
    all_files = []

    try:
        # Get all items (files and subfolders) in current folder
        query = f"'{folder_id}' in parents and trashed=false"

        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType, createdTime, modifiedTime, parents)",
            pageSize=1000
        ).execute()

        items = results.get('files', [])

        # Sort files and folders using natural sorting
        items.sort(key=lambda x: natural_sort_key(x['name']))

        for item in items:
            item_name = item['name']
            item_path = f"{current_path}/{item_name}" if current_path else item_name

            # If it's a folder, process recursively
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                print(f"Scanning folder: {item_path}")
                sub_files = list_all_files_recursively(service, item['id'], item_path)
                all_files.extend(sub_files)

            # If it's a Google Docs file, add to list
            elif item['mimeType'] == 'application/vnd.google-apps.document':
                item['path'] = item_path
                all_files.append(item)

        return all_files

    except HttpError as error:
        print(f"Error occurred while fetching file list: {error}")
        return all_files


def get_document_content(service, file_id):
    """Get plain text content of a Google Docs document"""
    try:
        # Use export method to export as plain text
        request = service.files().export_media(
            fileId=file_id,
            mimeType='text/plain'
        )
        content = request.execute()
        return content.decode('utf-8')

    except HttpError as error:
        print(f"Error occurred while fetching document content: {error}")
        return ""
