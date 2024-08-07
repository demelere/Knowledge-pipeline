import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import re
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GOOGLE_DOC_ID = os.getenv('GOOGLE_DOC_ID')

if not OPENAI_API_KEY or not GOOGLE_DOC_ID:
    raise ValueError("Missing required environment variables. Please check your .env file.")

os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY


# SCOPES = ['https://www.googleapis.com/auth/documents']
# creds = Credentials.from_authorized_user_file('path/to/your/credentials.json', SCOPES)
# docs_service = build('docs', 'v1', credentials=creds)
GOOGLE_CREDENTIALS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH')
if not GOOGLE_CREDENTIALS_PATH:
    raise ValueError("Missing GOOGLE_CREDENTIALS_PATH environment variable.")
creds = Credentials.from_authorized_user_file(GOOGLE_CREDENTIALS_PATH, SCOPES)

llm = OpenAI(temperature=0.7)

def get_document_content(doc_id):
    document = docs_service.documents().get(documentId=doc_id).execute()
    return document

def update_document(doc_id, requests):
    docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()

def extract_links_and_headers(content):
    links = []
    headers = []
    for element in content['body']['content']:
        if 'paragraph' in element:
            para = element['paragraph']
            if 'elements' in para:
                for elem in para['elements']:
                    if 'textRun' in elem:
                        text = elem['textRun']['content'].strip()
                        if 'link' in elem['textRun']:
                            links.append((text, elem['startIndex'], elem['endIndex']))
                        elif para.get('paragraphStyle', {}).get('namedStyleType', '').startswith('HEADING'):
                            headers.append((text, elem['startIndex']))
    return links, headers

def categorize_and_summarize(link, headers):
    prompt = PromptTemplate(
        input_variables=["link", "headers"],
        template="Categorize the following link under one of these headers: {headers}\n\nLink: {link}\n\nCategory:"
    )
    chain = LLMChain(llm=llm, prompt=prompt)
    category = chain.run(link=link, headers=", ".join([h[0] for h in headers]))

    if not any(link.startswith(prefix) for prefix in ['https://www.youtube.com', 'https://youtu.be']):
        summary_prompt = PromptTemplate(
            input_variables=["link"],
            template="Summarize the content of this link in one brief bullet point:\n\nLink: {link}\n\nSummary:"
        )
        summary_chain = LLMChain(llm=llm, prompt=summary_prompt)
        summary = summary_chain.run(link=link)
    else:
        summary = "• [YouTube video - not summarized]"

    return category.strip(), summary.strip()

def process_document(doc_id): # main fn
    content = get_document_content(doc_id)
    links, headers = extract_links_and_headers(content)

    requests = []
    for link_text, start_index, end_index in links:
        category, summary = categorize_and_summarize(link_text, headers)
        
        target_header = next((h for h in headers if h[0].lower() == category.lower()), None) # find the appropriate header
        
        if target_header: # move link under header
            requests.append({
                'cutPasteRange': {
                    'source': {
                        'startIndex': start_index,
                        'endIndex': end_index
                    },
                    'destination': {
                        'index': target_header[1]
                    }
                }
            })
            
            requests.append({ # insert bullet point summary
                'insertText': {
                    'location': {
                        'index': target_header[1]
                    },
                    'text': f"\n{summary}\n"
                }
            })

    update_document(doc_id, requests)

doc_id = GOOGLE_DOC_ID
process_document(doc_id)