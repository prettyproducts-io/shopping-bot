import redis
from urllib.parse import urlparse
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

redis_url = urlparse(os.environ.get("REDIS_URL"))

# Determine if we're running locally
is_local = redis_url.hostname in ['localhost', '127.0.0.1']

redis_connection = redis.Redis(
    host=redis_url.hostname,
    port=redis_url.port,
    username=redis_url.username,
    password=redis_url.password,
    ssl=not is_local,  # Use SSL only when not running locally
    ssl_cert_reqs=None if is_local else 'required'
)

# Print connection details for debugging
print(f"Redis connection details:")
print(f"Host: {redis_url.hostname}")
print(f"Port: {redis_url.port}")
print(f"Using SSL: {not is_local}")

# Test the connection
try:
    redis_connection.ping()
    print("Successfully connected to Redis")
except redis.ConnectionError as e:
    print(f"Failed to connect to Redis: {str(e)}")