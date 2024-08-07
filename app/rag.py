import logging
from .process_document import extract_products, setup_conversational_agent, get_product_info, load_embeddings
import json
from langchain_core.messages import HumanMessage
import time
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

# Load environment variables
load_dotenv()

PRE_SHARED_KEY = config['pre_shared_key']
WEBHOOK_URL = config['webhook_url']

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize these as None
agent = None
safe_retrieval_chain = None
is_initialized = False

def format_product_response(product):
    return {
        "title": product.get("title", ""),
        "link": product.get("permalink", ""),
        "image": product.get("image_url", ""),
        "price": product.get("price", ""),
        "stock_status": product.get("stock_status", ""),
        "sale_price": product.get("sale_price", "")
    }

def handle_query(question, session_memory, session_id, session_products):
    logging.debug(f"Preparing to handle query: {question}, session_memory: {session_memory}, session_products: {session_products}")

    try:
        config_info = {
            "configurable": {
                "thread_id": session_id,
                "thread_ts": str(int(time.time())),
                "session_products": session_products
            }
        }
        
        customer_name = ""
        for msg in reversed(session_memory):
            if isinstance(msg, HumanMessage) and len(msg.content.split()) == 1:
                customer_name = msg.content
                break

        chat_history = [{"content": msg.content, "type": "human" if isinstance(msg, HumanMessage) else "ai"} for msg in session_memory]

        response_chain_input = {
            "input": question,
            "chat_history": chat_history,
            "session_products": session_products,
            "customer_name": customer_name,
            "config": config_info
        }

        response = agent.run(response_chain_input)
        logging.debug(f"Agent response type: {type(response)}")
        logging.debug(f"Agent response content: {response}")

        # Extract product information from the response
        product_mentions = extract_products(response)
        
        # Format the product responses
        formatted_products = []
        for product in product_mentions:
            product_id = product.get('id')
            if product_id:
                product_info = get_product_info(int(product_id))
                if product_info:
                    formatted_product = format_product_response(product_info)
                    formatted_products.append(formatted_product)

        # Prepare the final response
        formatted_response = {
            "response": response,
            "products": formatted_products
        }

        return formatted_response

    except Exception as e:
        logging.error(f"Error processing the AI response: {str(e)}")
        logging.error("Full error details: ", exc_info=True)
        return {
            "response": "I apologize, but I encountered an error while processing your request. The issue has been logged for our development team to investigate.",
            "products": []
        }
    
def chat_with_bot(question, session_id):
    thread = client.beta.threads.create()
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=question
    )
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id="asst_RPpg13jrshEESBjAmIjKkpSD"
    )
    
    while True:
        run_status = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
        )
        if run_status.status == 'completed':
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            for message in messages.data:
                if message.role == "assistant":
                    return {
                        "response": message.content[0].text.value,
                        "products": []  # You may need to implement product extraction separately
                    }
        elif run_status.status in ['failed', 'cancelled', 'expired']:
            return {
                "response": f"An error occurred: Run {run_status.status}",
                "products": []
            }
        time.sleep(0.5)
    