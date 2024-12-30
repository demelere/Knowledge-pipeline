import tweepy
from openai import OpenAI
import time
import re

def get_tweet_id(url):
    match = re.search(r'status/(\d+)', url)
    return match.group(1) if match else None

def classify_twitter_links(filepath):
    # Twitter API setup
    client = tweepy.Client(bearer_token='YOUR_BEARER_TOKEN')
    
    # OpenAI setup
    openai_client = OpenAI()
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Find sections
    twitter_start = -1
    categories = []
    for i, line in enumerate(lines):
        if line.strip().lower() == "twitter":
            twitter_start = i
        elif twitter_start == -1 and line.strip():
            categories.append(line.strip())
    
    # Get twitter links
    twitter_links = []
    i = twitter_start + 1
    while i < len(lines) and ("twitter.com" in lines[i].lower() or "x.com" in lines[i].lower()):
        if lines[i].strip():
            twitter_links.append(lines[i].strip())
        i += 1
    
    classified_links = {}
    
    # Process in batches of 25
    for i in range(0, len(twitter_links), 25):
        batch = twitter_links[i:i+25]
        contents = []
        
        # Get tweet contents
        for url in batch:
            tweet_id = get_tweet_id(url)
            try:
                tweet = client.get_tweet(tweet_id, expansions=['author_id'], 
                                      tweet_fields=['text', 'context_annotations'])
                contents.append(tweet.data.text)
            except:
                contents.append("")
            time.sleep(1)
        
        # Classify with OpenAI
        prompt = f"""Given these categories:
{', '.join(categories)}

Classify each tweet into exactly one category. Return as:
URL1: category1
URL2: category2
etc.

Tweets:
""" + "\n\n".join([f"URL{j+1}: {c}" for j,c in enumerate(contents)])

        response = openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[{"role": "user", "content": prompt}]
        )
        
        results = response.choices[0].message.content.split('\n')
        for j, result in enumerate(results):
            if ':' in result:
                category = result.split(':')[1].strip()
                if category in categories:
                    classified_links.setdefault(category, []).append(batch[j])
    
    # Reconstruct file
    new_content = []
    current_category = None
    
    for line in lines:
        line_stripped = line.strip()
        if line_stripped in categories:
            current_category = line_stripped
            new_content.append(line)
            if current_category in classified_links:
                new_content.extend(['\n'] + classified_links[current_category])
        elif line_stripped != "twitter":
            new_content.append(line)
            
    with open('classified_' + filepath, 'w') as f:
        f.writelines(new_content)