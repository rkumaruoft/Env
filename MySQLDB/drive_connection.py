import os
import io
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive']


def get_drive_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)


def download_pdfs(folder_id, service, pdf_files=None, skipped_files=None):
    if pdf_files is None:
        pdf_files = []
    if skipped_files is None:
        skipped_files = []

    # List all items in the folder
    response = service.files().list(
        q=f"'{folder_id}' in parents",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        spaces='drive',
        fields="files(id, name, mimeType)"
    ).execute()

    items = response.get('files', [])

    for item in items:
        if item['mimeType'] == 'application/pdf':
            try:
                request = service.files().get_media(
                    fileId=item['id'],
                    supportsAllDrives=True
                )

                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)

                done = False
                while not done:
                    status, done = downloader.next_chunk()

                fh.seek(0)
                pdf_files.append({
                    'id': item['id'],
                    'name': item['name'],
                    'content': fh
                })

                print(f"✅ Downloaded: {item['name']}")

            except Exception as e:
                print(f"❌ Skipped (cannot access): {item['name']} ({item['id']}) — {e}")
                skipped_files.append({'id': item['id'], 'name': item['name'], 'error': str(e)})

        elif item['mimeType'] == 'application/vnd.google-apps.folder':
            # Recurse into sub-folder
            download_pdfs(item['id'], service, pdf_files, skipped_files)

    return pdf_files, skipped_files

