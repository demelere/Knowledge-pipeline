import re
import requests
from bs4 import BeautifulSoup
import openai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from dotenv import load_dotenv
import os
import pickle
import logging

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY')

# Set up Google Docs API
SCOPES = ['https://www.googleapis.com/auth/documents']
GOOGLE_CREDENTIALS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH')
TOKEN_PICKLE_PATH = 'token.pickle'

def get_google_creds():
    creds = None
    if os.path.exists(TOKEN_PICKLE_PATH):
        with open(TOKEN_PICKLE_PATH, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Error refreshing credentials: {e}")
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PICKLE_PATH, 'wb') as token:
            pickle.dump(creds, token)
    return creds

creds = get_google_creds()
docs_service = build('docs', 'v1', credentials=creds)

def get_document_content(document_id):
    try:
        document = docs_service.documents().get(documentId=document_id).execute()
        return document['body']['content']
    except HttpError as error:
        logger.error(f"An error occurred: {error}")
        return None

def extract_headings_and_links(content):
    headings = {}
    current_heading = "Unsorted"
    for element in content:
        if 'paragraph' in element:
            paragraph = element['paragraph']
            if 'paragraphStyle' in paragraph and paragraph['paragraphStyle'].get('namedStyleType') == 'HEADING_1':
                current_heading = paragraph['elements'][0]['textRun']['content'].strip()
                headings[current_heading] = []
                logger.info(f"Found heading: {current_heading}")
            elif 'bullet' in paragraph:
                text = paragraph['elements'][0]['textRun']['content']
                match = re.search(r'(https?://\S+)', text)
                if match:
                    headings[current_heading].append(match.group(1))
                    logger.info(f"Found link under {current_heading}: {match.group(1)}")
    return headings

def extract_text_from_url(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text()
    except Exception as e:
        logger.error(f"Error extracting text from {url}: {e}")
        return ""

def categorize_and_summarize(text, headings, url):
    if "youtube.com" in url or "youtu.be" in url:
        logger.info(f"Categorizing YouTube link as Unsorted: {url}")
        return "Unsorted", "This is a YouTube link."

    prompt = f"Categorize the following text into one of these categories: {', '.join(headings)}. If it doesn't fit any category, categorize it as 'Unsorted'. Then provide a brief summary (max 100 words).\n\nText: {text[:1000]}"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that categorizes and summarizes text."},
            {"role": "user", "content": prompt}
        ]
    )
    result = response.choices[0].message.content
    category, summary = result.split('\n\n', 1)
    logger.info(f"Categorized link: {url} as {category.split(': ')[1]}")
    return category.split(': ')[1], summary

def update_document(document_id, updates):
    if not updates:
        logger.info("No updates to apply.")
        return
    try:
        docs_service.documents().batchUpdate(documentId=document_id, body={'requests': updates}).execute()
        logger.info("Document updated successfully.")
    except HttpError as error:
        logger.error(f"An error occurred: {error}")

def main(document_id):
    content = get_document_content(document_id)
    if not content:
        return

    headings_and_links = extract_headings_and_links(content)
    updates = []

    for heading, links in headings_and_links.items():
        for link in links:
            text = extract_text_from_url(link)
            category, summary = categorize_and_summarize(text, headings_and_links.keys(), link)

            if category != "Unsorted":
                # Move link to new category
                updates.append({
                    'deleteContentRange': {
                        'range': {
                            'startIndex': link.start(),
                            'endIndex': link.end() + 1
                        }
                    }
                })
                updates.append({
                    'insertText': {
                        'location': {
                            'index': headings_and_links[category][-1].end() + 1
                        },
                        'text': f"\n{link}\n• {summary}\n"
                    }
                })
                logger.info(f"Prepared update for link: {link}")

    update_document(document_id, updates)

if __name__ == "__main__":
    document_id = os.getenv('GOOGLE_DOC_ID')
    logger.info(f"Starting categorization for document ID: {document_id}")
    main(document_id)
    logger.info("Categorization process completed.")