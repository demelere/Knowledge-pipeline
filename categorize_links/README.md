# Link Categorization and Summarization

This project categorizes and summarizes links in a Google Document using OpenAI's GPT model.

## Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/your-repo-name.git
   cd your-repo-name
   ```

2. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   Create a `.env` file in the project root with the following content:
   ```
   OPENAI_API_KEY=your_openai_api_key
   GOOGLE_DOC_ID=your_google_doc_id
   GOOGLE_CREDENTIALS_PATH=path/to/your/credentials.json
   ```

4. Run the script:
   ```
   python categorize_links/categorize.py
   ```

## Note
Make sure to obtain the necessary API keys and credentials for OpenAI and Google Docs API before running the script.