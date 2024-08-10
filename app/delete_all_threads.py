from alive_progress import alive_bar
from openai import OpenAIError
import logging
import time
import random
import json
from redis import Redis
import os
from dotenv import load_dotenv
from initialize import client

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


# Initialize Redis connection
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
redis_connection = Redis.from_url(redis_url)

def get_stored_thread_ids():
    keys = redis_connection.keys('thread:*')
    thread_ids = [redis_connection.get(key).decode('utf-8') for key in keys]
    return thread_ids

def delete_thread(thread_id):
    logger.debug(f"Attempting to delete thread {thread_id}")
    try:
        client.beta.threads.delete(thread_id, timeout=10)  # 10 seconds timeout
    except OpenAIError as e:
        logger.error(f"OpenAI API error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
    except Exception as e:
        logger.error(f"Error deleting thread {thread_id} from OpenAI: {str(e)}")
        raise

    # Remove the thread_id from Redis
    for key in redis_connection.keys('thread:*'):
        if redis_connection.get(key).decode('utf-8') == thread_id:
            redis_connection.delete(key)
            logger.debug(f"Deleted thread {thread_id} from Redis")
            break

def delete_thread_with_backoff(thread_id, max_retries=5):
    for attempt in range(max_retries):
        try:
            client.beta.threads.delete(thread_id, timeout=10)
            logger.debug(f"Successfully deleted thread {thread_id}")
            return
        except OpenAIError as e:
            wait_time = (2 ** attempt) + random.random()
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {wait_time:.2f} seconds.")
            time.sleep(wait_time)
    logger.error(f"Failed to delete thread {thread_id} after {max_retries} attempts")

def delete_all_threads():
    total_deleted = 0
    
    while True:
        try:
            thread_ids = get_stored_thread_ids()
            
            if not thread_ids:
                print(f"No more threads. Total deleted: {total_deleted}")
                break
            
            with alive_bar(len(thread_ids), force_tty=True) as bar:
                for thread_id in thread_ids:
                    try:
                        delete_thread(thread_id)
                        total_deleted += 1
                        print(f"Deleted thread {thread_id}. Total deleted: {total_deleted}")
                    except Exception as e:
                        print(f"Error deleting thread {thread_id}: {str(e)}")
                    finally:
                        bar()
                    time.sleep(0.5)  # Adjust rate limiting as needed
                    
        except Exception as e:
            print(f"Error fetching threads: {str(e)}")
            break

if __name__ == "__main__":
    delete_all_threads()