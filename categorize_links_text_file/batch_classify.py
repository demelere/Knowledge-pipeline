import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import time
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def extract_content(url):
    try:
        logging.info(f"Fetching content from: {url}")
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove scripts, styles, etc.
        for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()
            
        content = ' '.join(soup.stripped_strings)
        logging.info(f"Successfully extracted {len(content)} characters from {url}")
        return content
    except Exception as e:
        logging.error(f"Error extracting content from {url}: {str(e)}")
        return ""

def classify_links(filepath):
    logging.info(f"Starting classification for file: {filepath}")
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Find unsorted section
    logging.info("Looking for unsorted section...")
    unsorted_start = -1
    for i, line in enumerate(lines):
        if line.strip().lower() == "unsorted":
            unsorted_start = i
            break
            
    if unsorted_start == -1:
        raise ValueError("Could not find unsorted section")
    
    # Get valid categories
    categories = []
    for line in lines[:unsorted_start]:
        if line.strip() and not line.startswith('#'):
            categories.append(line.strip())
    
    logging.info(f"Found {len(categories)} categories: {categories}")
    
    # Process links in batches of 25
    links = [l for l in lines[unsorted_start+1:] if l.strip()]
    logging.info(f"Found {len(links)} links to process")
    classified_links = {}
    
    client = OpenAI()
    
    for i in range(0, len(links), 25):
        batch = links[i:i+25]
        contents = []
        
        logging.info(f"Processing batch {i//25 + 1} of {(len(links)-1)//25 + 1}")
        
        for j, link in enumerate(batch):
            logging.info(f"Processing link {i+j+1} of {len(links)}: {link.strip()}")
            content = extract_content(link.strip())
            contents.append(content[:1000])  # Truncate long content
            time.sleep(1)  # Rate limiting
            
        prompt = f"""Given these categories:
{', '.join(categories)}

Classify each content excerpt into exactly one of these categories. You must categorize each URL into exactly one of the following categories, using the exact text shown below:

- shipbuilding
- skilled trades and welding
- outreach, communication, sales, and pitching
- startup operating principles
- personal productivity system
- robotics, hardware, and electronics
- machine learning, deep learning, foundation models, artificial intelligence
- 3D, 3D reconstruction, and spatial computing
- unsorted

Do not create new categories or modify these category names. If a URL doesn't clearly fit into any category, use "unsorted".

Return results as:
URL1: category1
URL2: category2
etc.

Content excerpts:
""" + "\n\n".join([f"URL{j+1}: {c}" for j,c in enumerate(contents)])

        logging.info(f"Generated prompt: {prompt}")

        logging.info("Sending batch to OpenAI for classification...")
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse classifications
        results = response.choices[0].message.content.split('\n')
        logging.info(f"Received {len(results)} classifications from OpenAI")
        
        for j, result in enumerate(results):
            if ':' in result:
                url_index = int(result.split(':')[0].replace('URL', '')) - 1
                if url_index < len(batch):  # Ensure we have a valid index
                    category = result.split(':')[1].strip()
                    if category in categories:
                        classified_links.setdefault(category, []).append(batch[url_index].strip() + '\n')
                        logging.info(f"Classified {batch[url_index].strip()} as {category}")
                    else:
                        logging.warning(f"Received invalid category '{category}' for {batch[url_index].strip()}")
    
    # Reconstruct file
    logging.info("Reconstructing output file...")
    new_content = []
    current_category = None
    
    for line in lines:
        line_stripped = line.strip()
        if line_stripped in categories:
            current_category = line_stripped
            new_content.append(line)
            if current_category in classified_links:
                new_content.extend(['\n'] + classified_links[current_category])
        elif line_stripped == "unsorted":
            current_category = "unsorted"
            new_content.append(line)
            remaining = [l for l in links if not any(l in cat_links for cat_links in classified_links.values())]
            if remaining:
                logging.info(f"{len(remaining)} links remained unclassified")
                new_content.extend(['\n'] + remaining)
        elif current_category != "unsorted" or not line_stripped:
            new_content.append(line)
    
    output_file = 'classified_' + filepath
    logging.info(f"Writing results to {output_file}")
    with open(output_file, 'w') as f:
        f.writelines(new_content)
    
    logging.info("Classification complete!")

# Usage
if __name__ == "__main__":
    try:
        classify_links('test.txt')
    except Exception as e:
        logging.error(f"Program failed with error: {str(e)}")