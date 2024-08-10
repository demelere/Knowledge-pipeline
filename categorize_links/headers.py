from __future__ import print_function
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os.path
import sys
from dotenv import load_dotenv

load_dotenv()

print(f"GOOGLE_CREDENTIALS_PATH: {os.environ.get('GOOGLE_CREDENTIALS_PATH')}")

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/documents.readonly']

def get_credentials():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            credentials_path = os.environ.get('GOOGLE_CREDENTIALS_PATH')
            if not credentials_path:
                raise ValueError("GOOGLE_CREDENTIALS_PATH is not set in the environment variables")
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"The file {credentials_path} does not exist")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def get_document_headers(document_id):
    creds = get_credentials()
    service = build('docs', 'v1', credentials=creds)

    document = service.documents().get(documentId=document_id).execute()
    content = document.get('body').get('content')
    headers = []

    for element in content:
        if 'paragraph' in element:
            paragraph = element.get('paragraph')
            if 'paragraphStyle' in paragraph:
                style = paragraph.get('paragraphStyle')
                if 'namedStyleType' in style:
                    named_style = style.get('namedStyleType')
                    if 'HEADING' in named_style:
                        text_run = paragraph.get('elements')[0].get('textRun')
                        if text_run:
                            headers.append({
                                'level': int(named_style[-1]),
                                'text': text_run.get('content').strip()
                            })

    return headers

# Replace with your Google Doc ID
DOCUMENT_ID = os.environ.get('GOOGLE_DOC_ID')

headers = get_document_headers(DOCUMENT_ID)
for header in headers:
    print(f"Level {header['level']}: {header['text']}")