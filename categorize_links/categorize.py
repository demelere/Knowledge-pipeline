import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import re
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GOOGLE_DOC_ID = os.getenv('GOOGLE_DOC_ID')
GOOGLE_CREDENTIALS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH')

if not all([OPENAI_API_KEY, GOOGLE_DOC_ID, GOOGLE_CREDENTIALS_PATH]):
    raise ValueError("Missing required environment variables. Please check your .env file.")

os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY

SCOPES = ['https://www.googleapis.com/auth/documents']
creds = Credentials.from_authorized_user_file(GOOGLE_CREDENTIALS_PATH, SCOPES)
docs_service = build('docs', 'v1', credentials=creds)

llm = OpenAI(temperature=0.7)

def get_document_content(doc_id):
    document = docs_service.documents().get(documentId=doc_id).execute()
    return document

def update_document(doc_id, requests):
    docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()

def extract_links_and_headers(content):
    links = []
    headers = []
    unsorted_section = False
    unsorted_start_index = None
    
    for element in content['body']['content']:
        if 'paragraph' in element:
            para = element['paragraph']
            if 'elements' in para:
                for elem in para['elements']:
                    if 'textRun' in elem:
                        text = elem['textRun']['content'].strip()
                        if para.get('paragraphStyle', {}).get('namedStyleType', '').startswith('HEADING'):
                            headers.append((text, elem['startIndex']))
                            if text.lower() == "unsorted":
                                unsorted_section = True
                                unsorted_start_index = elem['startIndex']
                            elif unsorted_section:
                                unsorted_section = False
                        elif 'link' in elem['textRun'] and unsorted_section:
                            links.append((text, elem['startIndex'], elem['endIndex']))
    
    return links, headers, unsorted_start_index

def categorize_and_summarize(link, headers):
    prompt = PromptTemplate(
        input_variables=["link", "headers"],
        template="Categorize the following link under one of these headers: {headers}\n\nLink: {link}\n\nCategory:"
    )
    chain = LLMChain(llm=llm, prompt=prompt)
    category = chain.run(link=link, headers=", ".join([h[0] for h in headers if h[0].lower() != "unsorted"]))

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

def process_document(doc_id):
    content = get_document_content(doc_id)
    links, headers, unsorted_start_index = extract_links_and_headers(content)

    requests = []
    for link_text, start_index, end_index in links:
        category, summary = categorize_and_summarize(link_text, headers)
        
        target_header = next((h for h in headers if h[0].lower() == category.lower() and h[0].lower() != "unsorted"), None)
        
        if target_header:
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
            
            requests.append({
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