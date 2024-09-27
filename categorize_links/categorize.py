import re
import requests
from bs4 import BeautifulSoup
import openai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Set up OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY')

# Set up Google Docs API
SCOPES = ['https://www.googleapis.com/auth/documents']
creds = Credentials.from_authorized_user_file(os.getenv('GOOGLE_CREDENTIALS_PATH'), SCOPES)
docs_service = build('docs', 'v1', credentials=creds)

def get_document_content(document_id):
    try:
        document = docs_service.documents().get(documentId=document_id).execute()
        return document['body']['content']
    except HttpError as error:
        print(f"An error occurred: {error}")
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
            elif 'bullet' in paragraph:
                text = paragraph['elements'][0]['textRun']['content']
                match = re.search(r'(https?://\S+)', text)
                if match:
                    headings[current_heading].append(match.group(1))
    return headings

def extract_text_from_url(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text()
    except Exception as e:
        print(f"Error extracting text from {url}: {e}")
        return ""

def categorize_and_summarize(text, headings):
    prompt = f"Categorize the following text into one of these categories: {', '.join(headings)}. If it doesn't fit any category or is a YouTube link, categorize it as 'Unsorted'. Then provide a brief summary (max 100 words).\n\nText: {text[:1000]}"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that categorizes and summarizes text."},
            {"role": "user", "content": prompt}
        ]
    )
    result = response.choices[0].message.content
    category, summary = result.split('\n\n', 1)
    return category.split(': ')[1], summary

def update_document(document_id, updates):
    try:
        docs_service.documents().batchUpdate(documentId=document_id, body={'requests': updates}).execute()
    except HttpError as error:
        print(f"An error occurred: {error}")

def main(document_id):
    content = get_document_content(document_id)
    if not content:
        return

    headings_and_links = extract_headings_and_links(content)
    updates = []

    for heading, links in headings_and_links.items():
        for link in links:
            if heading != "Unsorted" or "youtube.com" in link:
                continue

            text = extract_text_from_url(link)
            category, summary = categorize_and_summarize(text, headings_and_links.keys())

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

    update_document(document_id, updates)

if __name__ == "__main__":
    document_id = os.getenv('GOOGLE_DOC_ID')
    main(document_id)