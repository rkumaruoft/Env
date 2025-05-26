import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']


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


def list_pdf_metadata():
    service = get_drive_service()
    page_token = None

    while True:
        response = service.files().list(
            q="mimeType='application/pdf'",
            spaces='drive',
            fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, size, owners, description, md5Checksum, webViewLink)",
            pageToken=page_token
        ).execute()

        for file in response.get('files', []):
            print("=" * 80)
            print(f"Name          : {file.get('name')}")
            print(f"ID            : {file.get('id')}")
            print(f"Created       : {file.get('createdTime')}")
            print(f"Modified      : {file.get('modifiedTime')}")
            print(f"Size          : {file.get('size')} bytes")
            print(f"MIME Type     : {file.get('mimeType')}")
            print(f"Owner(s)      : {', '.join([o.get('displayName', 'Unknown') for o in file.get('owners', [])])}")
            print(f"Description   : {file.get('description', 'None')}")
            print(f"MD5 Checksum  : {file.get('md5Checksum', 'N/A')}")
            print(f"Web View Link : {file.get('webViewLink')}")

        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break


if __name__ == '__main__':
    list_pdf_metadata()
