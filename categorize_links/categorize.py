import re
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from dotenv import load_dotenv
import os
import pickle
import logging
import difflib

# Load environment variables
load_dotenv()

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up OpenAI API key

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
            elif 'elements' in paragraph:
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

def find_closest_heading(returned_category, existing_headings):
    closest_match = difflib.get_close_matches(returned_category, existing_headings, n=1)
    if closest_match:
        return closest_match[0]
    return None

def batch_categorize_and_summarize(links, headings):
    prompt = (
        f"Categorize the following texts into one of these categories exactly as they are written: "
        f"{', '.join(headings)}. If it doesn't fit any category, categorize it as 'Unsorted'. "
        f"Then provide a brief summary (max 100 words) for each.\n\n"
    )
    for i, link in enumerate(links):
        prompt += f"Link {i+1}: {link['text'][:1000]}\n\n"

    response = client.chat.completions.create(model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": "You are a helpful assistant that categorizes and summarizes text."},
        {"role": "user", "content": prompt}
    ])
    result = response.choices[0].message.content
    
    # Parse the structured response
    categorized_links = []
    for i, link in enumerate(links):
        link_prompt = f"Link {i+1}:"
        if link_prompt in result:
            start_idx = result.index(link_prompt) + len(link_prompt)
            end_idx = result.find(f"Link {i+2}:", start_idx) if i+2 <= len(links) else len(result)
            link_result = result[start_idx:end_idx].strip()
            if '\n\n' in link_result:
                category, summary = link_result.split('\n\n', 1)
                category = category.split(': ')[1]
                categorized_links.append({
                    'url': link['url'],
                    'category': category,
                    'summary': summary
                })
            else:
                logger.error(f"Unexpected response format for link {i+1}: {link_result}")
                categorized_links.append({
                    'url': link['url'],
                    'category': 'Unsorted',
                    'summary': 'Unable to categorize and summarize this link.'
                })
        else:
            logger.error(f"Link {i+1} not found in response.")
            categorized_links.append({
                'url': link['url'],
                'category': 'Unsorted',
                'summary': 'Unable to categorize and summarize this link.'
            })
    
    return categorized_links

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
        link_batches = [links[i:i + 15] for i in range(0, len(links), 15)]
        for batch in link_batches:
            link_texts = [{'url': link, 'text': extract_text_from_url(link)} for link in batch]
            categorized_links = batch_categorize_and_summarize(link_texts, headings_and_links.keys())

            for link_info in categorized_links:
                link = link_info['url']
                category = link_info['category']
                summary = link_info['summary']

                if category == "Unsorted":
                    logger.info(f"Link {link} remains under Unsorted.")
                    continue

                closest_heading = find_closest_heading(category, headings_and_links.keys())
                if not closest_heading:
                    logger.error(f"Category '{category}' not found in document headings. Skipping link: {link}")
                    continue

                # Find the start and end indices of the link in the document content
                start_index = end_index = None
                for element in content:
                    if 'paragraph' in element:
                        paragraph = element['paragraph']
                        if 'elements' in paragraph:
                            for elem in paragraph['elements']:
                                if 'textRun' in elem and link in elem['textRun']['content']:
                                    start_index = elem['startIndex']
                                    end_index = elem['endIndex']
                                    logger.info(f"Found link at indices: start={start_index}, end={end_index}")
                                    break
                    if start_index and end_index:
                        break

                if not start_index or not end_index:
                    logger.warning(f"Link not found in document: {link}")
                    continue

                logger.info(f"Preparing to move link from {heading} to {closest_heading}")

                # Find the insert index for the new category
                if headings_and_links[closest_heading]:
                    insert_index = headings_and_links[closest_heading][-1].end() + 1
                else:
                    # Find the end index of the heading itself
                    for element in content:
                        if 'paragraph' in element:
                            paragraph = element['paragraph']
                            if 'elements' in paragraph and 'textRun' in paragraph['elements'][0]:
                                text = paragraph['elements'][0]['textRun']['content'].strip()
                                if text == closest_heading:
                                    insert_index = paragraph['elements'][0]['endIndex']
                                    break

                updates.append({
                    'deleteContentRange': {
                        'range': {
                            'startIndex': start_index,
                            'endIndex': end_index
                        }
                    }
                })
                updates.append({
                    'insertText': {
                        'location': {
                            'index': insert_index
                        },
                        'text': f"\n{link}\n• {summary}\n"
                    }
                })
                logger.info(f"Prepared update for link: {link} with summary: {summary}")

    update_document(document_id, updates)

if __name__ == "__main__":
    document_id = os.getenv('GOOGLE_DOC_ID')
    logger.info(f"Starting categorization for document ID: {document_id}")
    main(document_id)
    logger.info("Categorization process completed.")