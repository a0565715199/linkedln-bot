import praw
from bs4 import BeautifulSoup
import requests
import logging
from config import Config
from database import db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ExternalScraper:
    def __init__(self):
        self.reddit = None
        if Config.REDDIT_CLIENT_ID and Config.REDDIT_CLIENT_SECRET and Config.REDDIT_USERNAME and Config.REDDIT_PASSWORD:
            try:
                self.reddit = praw.Reddit(
                    client_id=Config.REDDIT_CLIENT_ID,
                    client_secret=Config.REDDIT_CLIENT_SECRET,
                    username=Config.REDDIT_USERNAME,
                    password=Config.REDDIT_PASSWORD,
                    user_agent=Config.SCRAPER_USER_AGENT
                )
                logging.info("Reddit API initialized successfully.")
            except Exception as e:
                logging.error(f"Failed to initialize Reddit API: {e}")
                logging.warning("Continuing without Reddit API access. Reddit scraping will be skipped.")
        else:
            logging.warning("Reddit credentials not found. Reddit scraping will be skipped.")

    def scrape_reddit(self, subreddit='programming', limit=5):
        if not self.reddit:
            logging.warning("Reddit API not available. Cannot scrape Reddit.")
            return []

        logging.info(f"Scraping top {limit} posts from r/{subreddit}...")
        scraped_data = []
        try:
            for submission in self.reddit.subreddit(subreddit).hot(limit=limit):
                if submission.is_self: # Only process self-text posts for simplicity or external links
                    continue
                
                title = submission.title
                url = submission.url
                # Optionally fetch full text if it's a self-post or from external link
                content = submission.selftext if submission.is_self else self._fetch_content_from_url(url)
                
                if content and db.insert_scraped_content("Reddit", title, url, content):
                    scraped_data.append({"title": title, "url": url, "content": content})
                    logging.info(f"Scraped Reddit: {title}")
            logging.info(f"Successfully scraped {len(scraped_data)} posts from Reddit.")
        except Exception as e:
            logging.error(f"Error scraping Reddit: {e}")
        return scraped_data

    def scrape_medium(self, query='programming', limit=5):
        logging.info(f"Scraping top {limit} articles from Medium for query '{query}'...")
        scraped_data = []
        # Medium is complex to scrape without proper APIs/RSS. This is a basic attempt.
        # Real-world scraping might need a dedicated tool or API.
        search_url = f"https://medium.com/search?q={query}"
        headers = {'User-Agent': Config.SCRAPER_USER_AGENT}
        try:
            response = requests.get(search_url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            # This is a highly simplified selector and might break.
            # Look for article titles and links.
            for i, article in enumerate(soup.select('h2 a')[:limit]):
                title = article.get_text(strip=True)
                url = article['href']
                content = self._fetch_content_from_url(url) # Attempt to get full content

                if content and db.insert_scraped_content("Medium", title, url, content):
                    scraped_data.append({"title": title, "url": url, "content": content})
                    logging.info(f"Scraped Medium: {title}")
            logging.info(f"Successfully scraped {len(scraped_data)} articles from Medium.")
        except Exception as e:
            logging.error(f"Error scraping Medium: {e}")
        return scraped_data

    def scrape_hackernews(self, limit=5):
        logging.info(f"Scraping top {limit} posts from Hacker News...")
        scraped_data = []
        hn_url = "https://news.ycombinator.com/"
        headers = {'User-Agent': Config.SCRAPER_USER_AGENT}
        try:
            response = requests.get(hn_url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            # Selectors for Hacker News articles
            for i, item in enumerate(soup.select('.athing')[:limit]):
                title_tag = item.select_one('.titleline a')
                if not title_tag:
                    continue
                
                title = title_tag.get_text(strip=True)
                url = title_tag['href']
                content = self._fetch_content_from_url(url)

                if content and db.insert_scraped_content("HackerNews", title, url, content):
                    scraped_data.append({"title": title, "url": url, "content": content})
                    logging.info(f"Scraped Hacker News: {title}")
            logging.info(f"Successfully scraped {len(scraped_data)} posts from Hacker News.")
        except Exception as e:
            logging.error(f"Error scraping Hacker News: {e}")
        return scraped_data

    def _fetch_content_from_url(self, url):
        """Helper to fetch content from a given URL."""
        if not url or not url.startswith(('http://', 'https://')):
            return None
        try:
            headers = {'User-Agent': Config.SCRAPER_USER_AGENT}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
            soup = BeautifulSoup(response.text, 'lxml')
            # Attempt to extract main article content (simplified)
            # This needs to be robust for various website structures
            text_content = ""
            for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'li']):
                text_content += tag.get_text(separator=' ', strip=True) + "\n"
            
            # Basic cleanup
            text_content = ' '.join(text_content.split()) # Remove extra whitespace
            return text_content[:2000] # Limit content length for database/AI
        except requests.exceptions.RequestException as e:
            logging.warning(f"Failed to fetch content from {url}: {e}")
            return None
        except Exception as e:
            logging.warning(f"Error parsing content from {url}: {e}")
            return None
