import tweepy
import csv
import os
import requests
import json
from tenacity import retry, stop_after_attempt, wait_fixed

# Get Twitter API credentials from environment variables
consumer_key = os.environ.get('TWITTER_API_KEY')
consumer_secret = os.environ.get('TWITTER_API_KEY_SECRET')
bearer_token = os.environ.get('TWITTER_BEARER_TOKEN')
access_token = os.environ.get('TWITTER_ACCESS_TOKEN')
access_token_secret = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')

def create_url():
    # Tweet fields are adjustable.
    # Options include:
    # attachments, author_id, context_annotations,
    # conversation_id, created_at, entities, geo, id,
    # in_reply_to_user_id, lang, non_public_metrics, organic_metrics,
    # possibly_sensitive, promoted_metrics, public_metrics, referenced_tweets,
    # source, text, and withheld
    tweet_fields = "tweet.fields=lang,author_id"
    # Be sure to replace your-user-id with your own user ID or one of an authenticating user
    # You can find a user ID by using the user lookup endpoint
    id = "your-user-id"
    # You can adjust ids to include a single Tweets.
    # Or you can add to up to 100 comma-separated IDs
    url = "https://api.twitter.com/2/users/{}/liked_tweets".format(id)
    return url, tweet_fields


def bearer_oauth(r):
    """
    Method required by bearer token authentication.
    """

    r.headers["Authorization"] = f"Bearer {bearer_token}"
    r.headers["User-Agent"] = "v2LikedTweetsPython"
    return r


def connect_to_endpoint(url, tweet_fields):
    response = requests.request(
        "GET", url, auth=bearer_oauth, params=tweet_fields)
    print(response.status_code)
    if response.status_code != 200:
        raise Exception(
            "Request returned an error: {} {}".format(
                response.status_code, response.text
            )
        )
    return response.json()


def main():
    url, tweet_fields = create_url()
    json_response = connect_to_endpoint(url, tweet_fields)
    print(json.dumps(json_response, indent=4, sort_keys=True))


if __name__ == "__main__":
    main()

# # Authenticate with Twitter API using bearer token
# auth = tweepy.AppAuthHandler(consumer_key, consumer_secret)
# # api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

# try: 
#     api = tweepy.API(auth)
#     user = api.verify_credentials()
#     print("Authentication OK")
# except tweepy.TweepError as e:
#     print("Error during authentication")

# Define a function to retrieve liked Tweets
# @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
# def get_liked_tweets(user_id, max_tweets=3200):
#     tweets = []
#     for tweet in tweepy.Cursor(api.favorites, id=user_id, tweet_mode="extended").items(max_tweets):
#         tweets.append({
#             'Date': tweet.created_at,
#             'User': tweet.user.screen_name,
#             'Tweet Text': tweet.full_text,
#             'URL': f'https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}',
#         })
#     return tweets

# # Your Twitter user ID (you can find it at https://tweeterid.com/)
# your_user_id = 'Perandex'

# # Retrieve liked Tweets
# liked_tweets = get_liked_tweets(your_user_id)

# # Write to a CSV file
# csv_file = 'liked_tweets.csv'
# with open(csv_file, 'w', newline='', encoding='utf-8') as file:
#     fieldnames = ['Date', 'User', 'Tweet Text', 'URL']
#     writer = csv.DictWriter(file, fieldnames=fieldnames)
#     writer.writeheader()
#     writer.writerows(liked_tweets)

# print(f"Retrieved and saved {len(liked_tweets)} liked Tweets to {csv_file}")

####################################################################################################

# import tweepy
# import json
# from tenacity import retry, stop_after_attempt, wait_exponential
# from dotenv import dotenv_values

# env_vars = dotenv_values('.env')
# key = env_vars['KEY']
# token = env_vars['TOKEN']
# secret = env_vars['SECRET']

# def get_favorited_tweets(user_id, consumer_key, consumer_secret, access_token, access_token_secret):
#     auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
#     auth.set_access_token(access_token, access_token_secret)
#     api = tweepy.API(auth)

#     @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
#     def get_tweets():
#         return api.favorites(id=user_id, tweet_mode='extended')

#     tweets = get_tweets()

#     with open('favorited_tweets.json', 'w') as f:
#         json.dump(tweets, f)

#     print("Favorited tweets written to favorited_tweets.json")

# get_favorited_tweets()
