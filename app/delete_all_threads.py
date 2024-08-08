from alive_progress import alive_bar
import time
import json
from redis import Redis
import os
from dotenv import load_dotenv
from initialize import client

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
    client.beta.threads.delete(thread_id)
    # Remove the thread_id from Redis
    for key in redis_connection.keys('thread:*'):
        if redis_connection.get(key).decode('utf-8') == thread_id:
            redis_connection.delete(key)
            break

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