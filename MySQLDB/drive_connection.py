import os
import io
from typing import List, Dict, Tuple
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


class GoogleDriveHandler:
    SCOPES = ['https://www.googleapis.com/auth/drive']

    def __init__(self, creds_path: str = 'credentials.json', token_path: str = 'token.json'):
        self.creds_path = creds_path
        self.token_path = token_path
        self.service = self._authenticate()

    def _authenticate(self):
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.creds_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        return build('drive', 'v3', credentials=creds)

    def download_pdfs(self, folder_id: str) -> Tuple[List[Dict], List[Dict]]:
        """
        Recursively download all PDFs in the specified Google Drive folder and subfolders.

        Returns:
            Tuple containing:
            - pdf_files: List of dicts with keys 'id', 'name', 'content' (BytesIO).
            - skipped_files: List of dicts with keys 'id', 'name', 'error'.
        """
        pdf_files = []
        skipped_files = []
        self._download_pdfs_recursive(folder_id, pdf_files, skipped_files)
        return pdf_files, skipped_files

    def _download_pdfs_recursive(self, folder_id: str, pdf_files: List[Dict], skipped_files: List[Dict]):
        """
        Helper method to recursively scan and download PDF files from a given folder.
        """
        response = self.service.files().list(
            q=f"'{folder_id}' in parents",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            spaces='drive',
            fields="files(id, name, mimeType)"
        ).execute()

        items = response.get('files', [])

        for item in items:
            file_id = item['id']
            name = item['name']
            mime_type = item['mimeType']

            if mime_type == 'application/pdf':
                try:
                    request = self.service.files().get_media(fileId=file_id, supportsAllDrives=True)
                    fh = io.BytesIO()
                    downloader = MediaIoBaseDownload(fh, request)

                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                    fh.seek(0)

                    pdf_files.append({
                        'id': file_id,
                        'name': name,
                        'content': fh
                    })
                    print(f"✅ Downloaded: {name}")

                except Exception as e:
                    print(f"❌ Skipped: {name} ({file_id}) — {e}")
                    skipped_files.append({
                        'id': file_id,
                        'name': name,
                        'error': str(e)
                    })

            elif mime_type == 'application/vnd.google-apps.folder':
                self._download_pdfs_recursive(file_id, pdf_files, skipped_files)
