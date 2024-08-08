import json
import os
import logging
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Add this function to load the config
def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

config = load_config()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Configure Segment analytics
import segment.analytics as analytics
analytics.write_key = config['segment_write_key']