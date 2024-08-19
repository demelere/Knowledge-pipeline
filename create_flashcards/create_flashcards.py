import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from openai import OpenAI
import genanki
import random

# Set up Google Docs API
SCOPES = ['https://www.googleapis.com/auth/documents.readonly']

def get_google_docs_service():
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    return build('docs', 'v1', credentials=creds)

def extract_text_with_comments(document_id):
    service = get_google_docs_service()
    doc = service.documents().get(documentId=document_id).execute()
    content = doc.get('body').get('content')

    text_by_comment = {}
    current_text = ""
    current_comment = None

    for element in content:
        if 'paragraph' in element:
            for run in element['paragraph']['elements']:
                if 'textRun' in run:
                    current_text += run['textRun']['content']
                if 'footnoteReference' in run:
                    footnote_id = run['footnoteReference']['footnoteId']
                    footnote = doc['footnotes'][footnote_id]
                    comment_content = footnote['content'][0]['paragraph']['elements'][0]['textRun']['content']
                    if comment_content.strip().isdigit():
                        if current_comment:
                            text_by_comment.setdefault(current_comment, []).append(current_text.strip())
                        current_comment = comment_content.strip()
                        current_text = ""

    if current_comment:
        text_by_comment.setdefault(current_comment, []).append(current_text.strip())

    return text_by_comment

def generate_qa_pair(text, openai_client):
    prompt = f"Create a concise question-answer pair based on the following text:\n\n{text}\n\nQuestion: "
    response = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100
    )
    qa_pair = response.choices[0].message.content.strip().split("\n")
    return qa_pair[0][10:], qa_pair[1][8:]  # Remove "Question: " and "Answer: " prefixes

def create_anki_deck(qa_pairs):
    model_id = random.randrange(1 << 30, 1 << 31)
    model = genanki.Model(
        model_id,
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

    deck_id = random.randrange(1 << 30, 1 << 31)
    deck = genanki.Deck(deck_id, "Google Docs Flashcards")

    for question, answer in qa_pairs:
        note = genanki.Note(
            model=model,
            fields=[question, answer]
        )
        deck.add_note(note)

    return deck

def main():
    document_id = input("Enter the Google Doc ID: ")
    openai_api_key = input("Enter your OpenAI API key: ")

    openai_client = OpenAI(api_key=openai_api_key)

    text_by_comment = extract_text_with_comments(document_id)
    qa_pairs = []

    for comment, texts in text_by_comment.items():
        full_text = " ".join(texts)
        question, answer = generate_qa_pair(full_text, openai_client)
        qa_pairs.append((question, answer))

    deck = create_anki_deck(qa_pairs)
    genanki.Package(deck).write_to_file('google_docs_flashcards.apkg')
    print("Anki deck created: google_docs_flashcards.apkg")

if __name__ == "__main__":
    main()