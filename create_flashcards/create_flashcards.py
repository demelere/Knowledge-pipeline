import os
from typing import List, Tuple
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain.agents import Tool, AgentExecutor, LLMSingleActionAgent
from langchain.chains import LLMChain
from langchain.llms import OpenAI
from langchain.prompts import StringPromptTemplate
from langchain.schema import AgentAction, AgentFinish
from langchain.memory import ConversationBufferMemory
import genanki

# Set up Google Docs API
SCOPES = ['https://www.googleapis.com/auth/documents.readonly']
creds = Credentials.from_authorized_user_file('path/to/your/credentials.json', SCOPES)
service = build('docs', 'v1', credentials=creds)

# Set up OpenAI API
os.environ["OPENAI_API_KEY"] = "your-openai-api-key"
llm = OpenAI(temperature=0.7)

def get_document_content(document_id: str) -> dict:
    document = service.documents().get(documentId=document_id).execute()
    return document

def extract_text_with_comments(document: dict) -> List[Tuple[str, str]]:
    content = document.get('body', {}).get('content', [])
    text_with_comments = []
    current_text = ""
    current_segment_id = None

    # First, extract all the comments
    comments = {}
    for comment in document.get('comments', []):
        comment_id = comment['id']
        comment_text = comment['content']
        comments[comment_id] = comment_text

    # Now, process the document content
    for element in content:
        if 'paragraph' in element:
            for run in element['paragraph']['elements']:
                if 'textRun' in run:
                    text = run['textRun']['content']
                    current_text += text
                    
                    # Check if this text run has a comment reference
                    if 'textStyle' in run['textRun']:
                        if 'commentIds' in run['textRun']['textStyle']:
                            comment_id = run['textRun']['textStyle']['commentIds'][0]
                            comment = comments.get(comment_id, "")
                            
                            # Add the text and comment to our list
                            text_with_comments.append((text, comment))
                            current_text = ""  # Reset current text
    
    # Add any remaining text
    if current_text:
        text_with_comments.append((current_text, ""))

    return text_with_comments

def group_text_by_identifier(text_with_comments: List[Tuple[str, str]]) -> dict:
    grouped_text = {}
    for text, comment in text_with_comments:
        if comment:
            identifier = comment.split()[0]  # Assume the first word is the identifier
            if identifier not in grouped_text:
                grouped_text[identifier] = []
            grouped_text[identifier].append(text)
    return grouped_text

def create_flashcard(text: str) -> Tuple[str, str]:
    prompt = f"Create a question and answer pair for an Anki flashcard based on the following text:\n\n{text}\n\nQuestion:"
    question = llm(prompt)
    
    answer_prompt = f"Now provide a concise answer to the following question:\n\nQuestion: {question}\n\nAnswer:"
    answer = llm(answer_prompt)
    
    return question.strip(), answer.strip()

def create_anki_deck(flashcards: List[Tuple[str, str]], deck_name: str) -> genanki.Deck:
    model = genanki.Model(
        1607392319,
        'Simple Model',
        fields=[
            {'name': 'Question'},
            {'name': 'Answer'},
        ],
        templates=[
            {
                'name': 'Card 1',
                'qfmt': '{{Question}}',
                'afmt': '{{FrontSide}}<hr id="answer">{{Answer}}',
            },
        ])

    deck = genanki.Deck(2059400110, deck_name)

    for question, answer in flashcards:
        note = genanki.Note(
            model=model,
            fields=[question, answer])
        deck.add_note(note)

    return deck

class GoogleDocsAnkiAgent(StringPromptTemplate):
    def format(self, **kwargs) -> str:
        return "You are an AI assistant that helps create Anki flashcards from Google Docs content."

    def _extract_tool_and_input(self, text: str) -> Tuple[str, str]:
        parts = text.split(":", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        else:
            return "", text.strip()

    def parse(self, output: str) -> AgentAction:
        action, action_input = self._extract_tool_and_input(output)
        return AgentAction(tool=action, tool_input=action_input, log=output)

def run_agent(document_id: str, deck_name: str):
    document = get_document_content(document_id)
    text_with_comments = extract_text_with_comments(document)
    grouped_text = group_text_by_identifier(text_with_comments)
    
    flashcards = []
    for identifier, texts in grouped_text.items():
        combined_text = " ".join(texts)
        question, answer = create_flashcard(combined_text)
        flashcards.append((question, answer))
    
    deck = create_anki_deck(flashcards, deck_name)
    genanki.Package(deck).write_to_file(f"{deck_name}.apkg")

    print(f"Anki deck '{deck_name}' has been created with {len(flashcards)} flashcards.")

if __name__ == "__main__":
    document_id = "your-google-doc-id"
    deck_name = "My Anki Deck"
    run_agent(document_id, deck_name)