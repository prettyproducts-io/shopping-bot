import argparse
from redis import Redis
import os
from dotenv import load_dotenv
from initialize import client

# Load environment variables
load_dotenv()

# Initialize Redis connection
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
redis_connection = Redis.from_url(redis_url)

def delete_thread(thread_id):
    try:
        # Delete the thread from OpenAI
        client.beta.threads.delete(thread_id)
        print(f"Deleted thread {thread_id} from OpenAI.")

        # Remove the thread_id from Redis
        deleted = False
        for key in redis_connection.keys('thread:*'):
            if redis_connection.get(key).decode('utf-8') == thread_id:
                redis_connection.delete(key)
                deleted = True
                print(f"Deleted thread {thread_id} from Redis.")
                break
        
        if not deleted:
            print(f"Thread {thread_id} was not found in Redis.")

    except Exception as e:
        print(f"Error deleting thread {thread_id}: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delete a specific thread by ID")
    parser.add_argument("thread_id", help="The ID of the thread to delete")
    args = parser.parse_args()

    delete_thread(args.thread_id)