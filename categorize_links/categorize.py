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
                # logger.info(f"Found heading: {current_heading}")
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
        extracted_text = soup.get_text()
        # logger.info(f"Extracted text from {url}: {extracted_text[:10]}...")  # Log the first 500 characters of the extracted text
        return extracted_text
    except Exception as e:
        logger.error(f"Error extracting text from {url}: {e}")
        return ""

def batch_categorize_and_summarize(links, headings):
    prompt = (
        f"Categorize each of the following texts into one of these categories exactly as they are written: "
        f"{', '.join(headings)}. If it doesn't fit any category, categorize it as 'Unsorted'. "
        f"Then provide a brief summary (max 100 words) for each. Bias the summary towards towards unique, actionable, new insights.  Do not waste time beginning the summary with phrases like 'this blog,' 'this article', 'this post', 'this content', 'this site', etc.  Skip to the insights "
        f"For each text, always summarize and categorize in given format: \n\n"
        f"[number]:\nCategory: [category]\nSummary: [summary]\n\n"
        f"Always use the brackets [] to wrap the number "
    )
    for i, link in enumerate(links):
        prompt += f"Link {i+1}: {link['text'][:1000]}\n\n"

    # logger.info(f"OpenAI API prompt: {prompt}")  # Log the prompt sent to OpenAI

    response = client.chat.completions.create(model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": "You are a helpful assistant that categorizes and summarizes text."},
        {"role": "user", "content": prompt}
    ])
    result = response.choices[0].message.content
    logger.info(f"OpenAI API response: {result}")

    # Parse the structured response
    categorized_links = []
    response_blocks = re.split(r'\[\d+\]:', result)
    response_blocks = [block.strip() for block in response_blocks if block.strip()]
    logger.info(f"Split response into {len(response_blocks)} blocks")

    for i, block in enumerate(response_blocks):
        if i >= len(links):
            break

        lines = block.split('\n')
        category = None
        summary = None

        for line in lines:
            if line.startswith("Category:"):
                category = line.split("Category:")[1].strip()
                logger.info(f"Found category for link {i+1}: {category}")
            elif line.startswith("Summary:"):
                summary = line.split("Summary:")[1].strip()
                logger.info(f"Found summary for link {i+1}: {summary}")

        if category and summary:
            categorized_link = {
                'url': links[i]['url'],
                'category': category,
                'summary': summary
            }
            logger.info(f"Successfully parsed link {i+1}: category: {category}, summary: {summary[:50]}...")
            categorized_links.append(categorized_link)
        else:
            logger.error(f"Unexpected response format for link {i+1}")
            categorized_link = {
                'url': links[i]['url'],
                'category': 'Unsorted',
                'summary': 'Unable to categorize and summarize this link.'
            }
            categorized_links.append(categorized_link)

    logger.info(f"Total categorized links: {len(categorized_links)}")
    return categorized_links

def find_closest_heading(returned_category, existing_headings):
    # Define unique keywords for each category
    category_keywords = {
        'Shipbuilding': ['shipbuilding', 'ship', 'naval'],
        'Skilled Trades and Welding': ['skilled', 'trades', 'welding', 'weld', 'skilled trades'],
        'Outreach and Communication and Sales and Pitching': ['outreach', 'communication', 'sales', 'pitching', 'pitch'],
        'Startup Operating Principles': ['startup', 'operating', 'principles', 'startup operating'],
        'Personal Productivity System': ['personal', 'productivity', 'system', 'personal productivity'],
        'Robotics and Hardware and Electronics': ['robotics', 'hardware', 'electronics'],
        'Machine Learning and Deep Learning and Foundation Models and Artificial Intelligence': ['machine learning', 'deep learning', 'foundation models', 'artificial intelligence', 'ai', 'ml'],
        '3D and 3D reconstruction and Spatial Computing': ['3d', 'spatial', 'reconstruction', '3d reconstruction'],
        'Unsorted': ['unsorted']
    }

    # Convert returned category to lowercase for case-insensitive matching
    returned_category_lower = returned_category.lower()

    # Check if any of the keywords for each category are in the returned category
    for heading, keywords in category_keywords.items():
        if any(keyword in returned_category_lower for keyword in keywords):
            logger.info(f"Matched category '{returned_category}' to heading: {heading}")
            return heading

    # If no match found, use difflib as a fallback
    closest_match = difflib.get_close_matches(returned_category, existing_headings, n=1)
    if closest_match:
        logger.info(f"Closest match for category '{returned_category}': {closest_match[0]}")
        return closest_match[0]

    # If still no match, return 'Unsorted'
    logger.info(f"No match found for category '{returned_category}'. Categorizing as 'Unsorted'.")
    return 'Unsorted'

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
    logger.info(f"Extracted headings and links: {headings_and_links}")
    updates = []

    for heading, links in headings_and_links.items():
        link_batches = [links[i:i + 15] for i in range(0, len(links), 15)]
        for batch in link_batches:
            logger.info(f"Processing batch of links: {batch}")
            link_texts = [{'url': link, 'text': extract_text_from_url(link)} for link in batch]
            categorized_links = batch_categorize_and_summarize(link_texts, headings_and_links.keys())
            logger.info(f"Categorized links: {categorized_links}")

            for link_info in categorized_links:
                link = link_info['url']
                category = link_info['category']
                summary = link_info['summary']

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
                                    # logger.info(f"Found link at indices: start={start_index}, end={end_index}")
                                    break
                    if start_index and end_index:
                        break

                if not start_index or not end_index:
                    logger.warning(f"Link not found in document: {link}")
                    continue

                closest_heading = find_closest_heading(category, headings_and_links.keys())
                if not closest_heading:
                    logger.error(f"Category '{category}' not found in document headings. Skipping link: {link}")
                    continue

                logger.info(f"Preparing to move link from {heading} to {closest_heading}")

                # Find the insert index for the new category
                logger.info(f"Finding insert index for category: {closest_heading}")
                insert_index = None
                for element in content:
                    if 'paragraph' in element:
                        paragraph = element['paragraph']
                        if 'elements' in paragraph:
                            for elem in paragraph['elements']:
                                if 'textRun' in elem and closest_heading in elem['textRun']['content']:
                                    insert_index = elem['endIndex']
                                    # logger.info(f"Insert index found at end of heading: {insert_index}")
                                    break
                    if insert_index:
                        break
                
                if insert_index is None:
                    logger.warning(f"Could not find end index for heading: {closest_heading}")
                    continue

                # To Do: Copy the link to be on a new line under the new heading that it's categorized under, and make sure it's formatted as normal text
                # Insert its summary as a bullet point as a new line under that link, also formatted as normal text. And then just highlight the original link in red
                # Copy the link to a new line under the new heading
                updates.append({
                    'insertText': {
                        'location': {'index': insert_index},
                        'text': f'\n{link}\n'
                    }
                })
                insert_index += len(link) + 2  # +2 for the two newline characters

                # Insert the summary as a bullet point using Google Docs formatting
                updates.append({
                    'insertText': {
                        'location': {'index': insert_index},
                        'text': f'{summary}\n'
                    }
                })
                updates.append({
                    'createParagraphBullets': {
                        'range': {
                            'startIndex': insert_index,
                            'endIndex': insert_index + len(summary) + 1
                        },
                        'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                    }
                })
                insert_index += len(summary) + 1  # +1 for the newline

                # Format the copied link and summary as normal text
                updates.append({
                    'updateParagraphStyle': {
                        'range': {
                            'startIndex': insert_index - len(link) - len(summary) - 3,  # -3 for newlines
                            'endIndex': insert_index
                        },
                        'paragraphStyle': {'namedStyleType': 'NORMAL_TEXT'},
                        'fields': 'namedStyleType'
                    }
                })

                # Find the second occurrence of the link in the document
                # Search for the link under the Unsorted header
                unsorted_index = None
                link_index = None
                logger.info(f"Searching for link: {link} under Unsorted header")
                for element in content:
                    if 'paragraph' in element:
                        paragraph = element['paragraph']
                        if 'paragraphStyle' in paragraph and paragraph['paragraphStyle'].get('namedStyleType') == 'HEADING_1':
                            if paragraph['elements'][0]['textRun']['content'].strip() == "Unsorted":
                                unsorted_index = paragraph['elements'][0]['startIndex']
                                logger.info(f"Found Unsorted header at index: {unsorted_index}")
                        elif unsorted_index is not None:
                            for paragraph_element in paragraph.get('elements', []):
                                if 'textRun' in paragraph_element:
                                    text = paragraph_element['textRun'].get('content', '')
                                    # logger.debug(f"Checking text: {text[:50]}...")  # Log first 50 characters
                                    if link in text:
                                        link_index = paragraph_element['startIndex']
                                        logger.info(f"Found link at index: {link_index}")
                                        break
                    if link_index:
                        logger.info(f"Link found and processing complete")
                        break
                if not link_index:
                    logger.warning(f"Link not found under Unsorted header: {link}")

                if link_index:
                    # Highlight the original link in red
                    updates.append({
                        'updateTextStyle': {
                            'range': {
                                'startIndex': link_index,
                                'endIndex': link_index + len(link)
                            },
                            'textStyle': {
                                'foregroundColor': {
                                    'color': {
                                        'rgbColor': {
                                            'red': 1.0,
                                            'green': 0.0,
                                            'blue': 0.0
                                        }
                                    }
                                }
                            },
                            'fields': 'foregroundColor'
                        }
                    })
                else:
                    logger.warning(f"Could not find link under Unsorted header: {link}")
                

                # # Update the insert_index for the next iteration
                insert_index += len(summary) + len(link) + 2  # +2 for the two newline characters

    try:
        update_document(document_id, updates)
    except HttpError as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    document_id = os.getenv('GOOGLE_DOC_ID')
    logger.info(f"Starting categorization for document ID: {document_id}")
    main(document_id)
    logger.info("Categorization process completed.")