import json
from threading import Lock
from .redis_config import redis_connection
from langchain_core.messages import HumanMessage, AIMessage
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

# Load environment variables
load_dotenv()

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def get_session_memory(session_id):
    memory = redis_connection.get(f"memory:{session_id}")
    if memory:
        memory_list = json.loads(memory)
        return [
            HumanMessage(content=msg['content']) if msg['type'] == 'human' else AIMessage(content=msg['content'])
            for msg in memory_list
        ]
    return []

def update_session_memory(session_id, memory):
    serializable_memory = [
        {'type': 'human' if isinstance(msg, HumanMessage) else 'ai', 'content': msg.content}
        for msg in memory
    ]
    redis_connection.set(f"memory:{session_id}", json.dumps(serializable_memory))

def get_session_products(session_id):
    products = redis_connection.get(f"products:{session_id}")
    return json.loads(products) if products else []

def update_session_products(session_id, products):
    redis_connection.set(f"products:{session_id}", json.dumps(products))

def get_or_create_thread(session_id):
    thread_id = redis_connection.get(f"thread:{session_id}")
    if not thread_id:
        thread = client.beta.threads.create()
        redis_connection.set(f"thread:{session_id}", thread.id)
        return thread.id
    return ensure_str(thread_id)

def add_message_to_thread(thread_id, role, content):
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role=role,
        content=content
    )

def ensure_str(val):
    if val is None:
        return ''
    if isinstance(val, bytes):
        try:
            return val.decode('utf-8')
        except UnicodeDecodeError:
            return val.decode('latin-1')  # Fallback encoding
    return str(val)