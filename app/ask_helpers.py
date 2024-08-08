import json
import time
import logging
import requests
import os
from flask import session
from flask_wtf import FlaskForm
from wtforms import TextAreaField
from wtforms.validators import DataRequired
from .initialize import client, analytics, config

logger = logging.getLogger(__name__)

class ChatForm(FlaskForm):
    question = TextAreaField('Question', validators=[DataRequired()])

def get_product_info(product_id, pre_shared_key, webhook_url):
    try:
        # Construct the URL with the correct scheme
        url = f"{webhook_url}/{product_id}?key={pre_shared_key}"
        logger.debug(f"Sending request to URL: {url}")

        response = requests.post(url)
        logger.debug(f"Received response from webhook: {response.status_code} - {response.content}")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching product info for ID {product_id}: {str(e)}")
        return {"error": str(e)}

def generate_responses(thread_id, run):
    session_id = session.get('sid', 'unknown')
    logger.debug(f"Session ID in generate_responses: {session_id}")

    start_time = time.time()
    timeout = 60  # Increased timeout to 60 seconds
    max_retries = 30  # Maximum number of status checks

    logger.debug(f"Starting status check loop with timeout={timeout}s and max_retries={max_retries}")
    for attempt in range(max_retries):
        if time.time() - start_time > timeout:
            logger.debug("Request timed out.")
            yield f"data: {json.dumps({'error': 'Request timed out'})}\n\n"
            break

        try:
            run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
            logger.debug(f"Attempt {attempt}: Run status: {run_status.status}")
            logger.debug(f"Full run status: {run_status}")

            if run_status.status == 'completed':
                logger.debug(f"Run completed in attempt {attempt}")
                messages = client.beta.threads.messages.list(thread_id=thread_id, limit=1)
                for message in messages.data:
                    if message.role == "assistant":
                        content = message.content[0].text.value
                        formatted_content = format_response(content)

                        # Track bot response
                        analytics.track(session_id, 'Bot Response Sent', {
                            'response': formatted_content
                        })

                        yield f"data: {formatted_content}\n\n"
                yield "event: DONE\ndata: [DONE]\n\n"
                break

            elif run_status.status in ['failed', 'cancelled', 'expired']:
                logger.error(f"Run status is {run_status.status}. Ending loop.")
                yield f"data: {json.dumps({'error': f'Run {run_status.status}'})}\n\n"
                break

            elif run_status.status == 'requires_action':
                logger.warning(f"Run requires action: {run_status.required_action}")
                if handle_required_action(run_status, thread_id):
                    logger.debug("Handled required action, retrying status check.")
                    time.sleep(2)  # Wait before checking again
                    continue
                else:
                    logger.error("Unable to handle required action. Ending loop.")
                    yield f"data: {json.dumps({'error': 'Unable to handle required action'})}\n\n"
                    break
            else:
                logger.debug(f"Run status not final. Sleeping before next attempt.")
                time.sleep(2)  # Increased wait time between checks

        except Exception as e:
            logger.error(f"Error checking run status: {str(e)}")
            yield f"data: {json.dumps({'error': f'Error checking run status: {str(e)}'})}\n\n"
            break
    else:
        logger.debug("Maximum retries reached.")
        yield f"data: {json.dumps({'error': 'Maximum retries reached'})}\n\n"

def format_response(content):
    try:
        response_data = json.loads(content)
        if 'response' in response_data and isinstance(response_data['response'], str):
            try:
                inner_json = json.loads(response_data['response'].strip('`').strip())
                if isinstance(inner_json, dict):
                    response_data = inner_json
            except json.JSONDecodeError:
                pass

        if 'response' not in response_data:
            raise ValueError("Invalid response format")

        # Ensure includes_products field is a boolean, and reflect correct state
        response_data['includes_products'] = bool(response_data.get('products', []))

        return json.dumps(response_data)
    except json.JSONDecodeError:
        return json.dumps({
            "response": content,
            "products": [],
            "includes_products": False
        })


def handle_required_action(run, thread_id):
    if run.required_action and run.required_action.type == "submit_tool_outputs":
        tool_outputs = []
        for tool_call in run.required_action.submit_tool_outputs.tool_calls:
            if tool_call.function.name == "get_product_info":
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    logger.debug(f"Handling required action for product ID {arguments['id']}")
                    product_info = get_product_info(
                        arguments['id'],
                        arguments['pre_shared_key'],
                        arguments['webhook_url']
                    )
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": json.dumps(product_info)
                    })
                except Exception as e:
                    logger.error(f"Error in get_product_info: {str(e)}")
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": json.dumps({"error": str(e)})
                    })

        logger.debug(f"Submitting tool outputs: {tool_outputs}")
        client.beta.threads.runs.submit_tool_outputs(thread_id=thread_id, run_id=run.id, tool_outputs=tool_outputs)
        return True
    return False