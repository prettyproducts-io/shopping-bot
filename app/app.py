print("Starting app initialization...")
import logging
from openai import OpenAI, OpenAIError
from flask import Flask, request, jsonify, render_template, send_from_directory, session, Response, stream_with_context, current_app
from flask_session import Session
import segment.analytics as analytics
from flask_wtf import FlaskForm, CSRFProtect
from flask_wtf.csrf import generate_csrf, validate_csrf
from flask_basicauth import BasicAuth
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv
import json
import os
from wtforms import TextAreaField
from wtforms.validators import DataRequired
import datetime
import time
from .session_manager import get_or_create_thread, add_message_to_thread, ensure_str
from .process_document import get_product_info
from .redis_config import redis_connection
print("Imports complete")

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

try:
    # Load environment variables
    load_dotenv()
    print("Environment variables loaded")

    # Add this function to load the config
    def load_config():
        with open('config.json', 'r') as f:
            return json.load(f)

    config = load_config()
    print("Configuration loaded")

    # Initialize OpenAI client
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
    print("Creating Flask app")
    app = Flask(__name__, template_folder='templates', static_folder='static')
    print("Flask app created")

    print("Setting up CORS")
    CORS(app, resources={
        r"/*": {
            "origins": ["https://epona.eqbay.co", "https://*.eqbay.co", "http://localhost:*", "http://127.0.0.1:*"],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "X-CSRFToken"]
        }
    })
    print("CORS setup complete")

    print("Loading Segment configuration")
    analytics.write_key = config['segment_write_key']
    print("Segment configuration loaded")

    print("Updating Flask configuration")
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY'),
        SESSION_TYPE='redis',
        SESSION_PERMANENT=False,
        SESSION_USE_SIGNER=True,
        SESSION_REDIS=redis_connection,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,  # Ensure cookies are sent over HTTPS only
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_KEY_PREFIX='session:',
        REMEMBER_COOKIE_SECURE=True, # Ensure 'remember me' cookies are sent over HTTPS
        WTF_CSRF_ENABLED=True,
        WTF_CSRF_SECRET_KEY=os.environ.get("SECRET_KEY"),
        WTF_CSRF_SSL_STRICT=True     # Ensure CSRF protection is strict for HTTPS
    )
    print("Flask configuration updated")

    print("Setting additional Flask config options")
    app.config['BASIC_AUTH_USERNAME'] = os.getenv('BASIC_AUTH_USERNAME')
    app.config['BASIC_AUTH_PASSWORD'] = os.getenv('BASIC_AUTH_PASSWORD')
    app.config['CELERY_BROKER_URL'] = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    app.config['CELERY_RESULT_BACKEND'] = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    app.config['ASSISTANT_ID'] = config['assistant_id']
    app.config['DEBUG'] = True
    app.config['PREFERRED_URL_SCHEME'] = 'https'
    print("Additional Flask config options set")

    # Initialize extensions
    print("Initializing Flask extensions")
    Session(app)
    print("Session initialized")
    csrf = CSRFProtect(app)
    print("CSRF Protection initialized")
    basic_auth = BasicAuth(app)
    print("Basic Auth initialized")
    jwt = JWTManager(app)
    print("JWT Manager initialized")
    limiter = Limiter(
        get_remote_address,
        app=app,
        storage_uri=os.getenv("REDIS_URL"),
        storage_options={"socket_connect_timeout": 30},
        strategy="fixed-window", # or "moving-window"
    )
    print("Rate Limiter initialized")

    print("Checking Redis connection")
    try:
        redis_connection.ping()
        print("Successfully connected to Redis")
    except redis_connection.ConnectionError as e:
        print(f"Failed to connect to Redis. Error: {str(e)}")
        print("Make sure Redis is running and the REDIS_URL in your .env file is correct.")
    except Exception as e:
        print(f"An unexpected error occurred while connecting to Redis: {str(e)}")

    class ChatForm(FlaskForm):
        question = TextAreaField('Question', validators=[DataRequired()])

    @app.before_request
    def before_request():
        app.logger.debug(f"Session before request: {session.items()}")
        if 'sid' not in session:
            session['sid'] = os.urandom(16).hex()
        app.logger.debug(f"Session after potential sid assignment: {session.items()}")

    @app.after_request
    def add_csrf_token_to_response(response):
        response.headers.set('X-CSRFToken', generate_csrf())
        return response

    @app.route('/')
    def home():
        try:
            form = ChatForm()
            if 'sid' not in session:
                session['sid'] = os.urandom(16).hex()
            session_id = ensure_str(session['sid'])
            app.logger.debug(f"Home route: session_id: {session_id}")
            
            # Identify the user (if you have the anonymous_id)
            anonymous_id = request.args.get('anonymous_id')  # Get from query parameter
            if anonymous_id:
                analytics.identify(session_id, {
                    'anonymous_id': anonymous_id
                })
            
            return render_template('index.html', form=form, session_id=session_id)
        except Exception as e:
            app.logger.error(f"Error in home route: {str(e)}")
            return "An error occurred. Please try again later.", 500

    @app.route('/token', methods=['POST'])
    def generate_token():
        app.logger.debug(f"Token route: session.sid type: {type(session.sid)}")
        token = create_access_token(identity=str(session.sid))
        return jsonify(access_token=token)

    @app.route('/ask', methods=['POST'])
    def ask():
        try:
            app.logger.debug("Entered the /ask endpoint")
            app.logger.debug(f"Received request: {request.method} {request.url}")
            app.logger.debug(f"Form data: {request.form}")

            question = request.form.get('question')
            csrf_token = request.form.get('csrf_token')

            app.logger.debug(f"Extracted form fields - question: {question}, csrf_token: {csrf_token}")

            if not question or not csrf_token:
                app.logger.debug("Missing question or CSRF token")
                return jsonify({"error": "Missing question or CSRF token"}), 400

            try:
                app.logger.debug("Validating CSRF token")
                validate_csrf(csrf_token)
                app.logger.debug("CSRF token validated")
            except Exception as e:
                app.logger.error(f"CSRF validation failed: {str(e)}")
                return jsonify({"error": "Invalid CSRF token"}), 400

            form = ChatForm(request.form)
            app.logger.debug(f"Form validation status: {form.validate()}")
            if form.validate():
                question = form.question.data
                app.logger.debug(f"Validated question: {question}")

                session_id = ensure_str(session.get('sid', os.urandom(16).hex()))

                # Track chat session start (if it's a new session)
                if 'chat_session_started' not in session:
                    analytics.track(session_id, 'Chat Session Started', {
                        'session_id': session_id
                    })
                    session['chat_session_started'] = True
                
                # Track user message
                analytics.track(session_id, 'User Message Sent', {
                    'question': question
                })

                app.logger.debug(f"Session ID: {session_id}")
                thread_id = ensure_str(get_or_create_thread(session_id))
                app.logger.debug(f"Thread ID: {thread_id}")

                try:
                    app.logger.debug(f"Thread ID: {thread_id}")
                    # Add the user's message to the thread
                    client.beta.threads.messages.create(
                        thread_id=thread_id,
                        role="user",
                        content=question
                    )
                    app.logger.debug("User message added to thread")

                    # Create a new run
                    run = client.beta.threads.runs.create(
                        thread_id=thread_id,
                        assistant_id=app.config['ASSISTANT_ID']
                    )
                    app.logger.debug(f"Run created with ID: {run.id}")

                    def generate():
                        start_time = time.time()
                        timeout = 60  # Increased timeout to 60 seconds
                        max_retries = 30  # Maximum number of status checks

                        app.logger.debug(f"Starting status check loop with timeout={timeout}s and max_retries={max_retries}")
                        for attempt in range(max_retries):
                            if time.time() - start_time > timeout:
                                app.logger.debug("Request timed out.")
                                yield f"data: {json.dumps({'error': 'Request timed out'})}\n\n"
                                break

                            try:
                                run_status = client.beta.threads.runs.retrieve(
                                    thread_id=thread_id,
                                    run_id=run.id
                                )
                                app.logger.debug(f"Attempt {attempt}: Run status: {run_status.status}")
                                app.logger.debug(f"Full run status: {run_status}")

                                if run_status.status == 'completed':
                                    app.logger.debug(f"Run completed in attempt {attempt}")
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
                                    app.logger.error(f"Run status is {run_status.status}. Ending loop.")
                                    yield f"data: {json.dumps({'error': f'Run {run_status.status}'})}\n\n"
                                    break
                                elif run_status.status == 'requires_action':
                                    app.logger.warning(f"Run requires action: {run_status.required_action}")
                                    if handle_required_action(run_status, thread_id):
                                        app.logger.debug("Handled required action, retrying status check.")
                                        time.sleep(2)  # Wait a bit before checking again
                                        continue
                                    else:
                                        app.logger.error("Unable to handle required action. Ending loop.")
                                        yield f"data: {json.dumps({'error': 'Unable to handle required action'})}\n\n"
                                        break
                                else:
                                    app.logger.debug(f"Run status not final. Sleeping before next attempt.")
                                    time.sleep(2)  # Increased wait time between checks

                            except Exception as e:
                                app.logger.error(f"Error checking run status: {str(e)}")
                                yield f"data: {json.dumps({'error': f'Error checking run status: {str(e)}'})}\n\n"
                                break

                        else:
                            app.logger.debug("Maximum retries reached.")
                            yield f"data: {json.dumps({'error': 'Maximum retries reached'})}\n\n"

                    app.logger.debug("Returning response stream")
                    return Response(stream_with_context(generate()), content_type='text/event-stream')

                except OpenAIError as e:
                    app.logger.error(f"OpenAI API error: {str(e)}")
                    return jsonify({"error": f"An error occurred: {str(e)}"}), 500

            else:
                app.logger.debug(f"Form validation errors: {form.errors}")
                return jsonify({"error": "Invalid form submission"}), 400

        except Exception as e:
            app.logger.error(f"An error occurred in /ask endpoint: {str(e)}")
            return jsonify({"error": "An unexpected error occurred"}), 500
            
    def format_response(content):
        try:
            # First, try to parse the entire content as JSON
            response_data = json.loads(content)
            
            # If successful, check if the response is wrapped in a code block
            if 'response' in response_data and isinstance(response_data['response'], str):
                # Try to parse the response as JSON if it's a string
                try:
                    inner_json = json.loads(response_data['response'].strip('`').strip())
                    if isinstance(inner_json, dict) and 'response' in inner_json:
                        response_data = inner_json
                except json.JSONDecodeError:
                    pass  # If inner parsing fails, use the outer JSON as is
            
            # Ensure the response follows the expected format
            if 'response' not in response_data or 'products' not in response_data:
                raise ValueError("Invalid response format")

            # Return the JSON as a string
            return json.dumps(response_data)
        except json.JSONDecodeError:
            # If the response is not valid JSON, wrap it in the expected format
            return json.dumps({
                "response": content,
                "products": []
            })

        
    def handle_required_action(run, thread_id):
        if run.required_action and run.required_action.type == "submit_tool_outputs":
            tool_outputs = []
            for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                if tool_call.function.name == "get_product_info":
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                        product_info = get_product_info(arguments['id'], arguments['pre_shared_key'])
                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": json.dumps(product_info)
                        })
                    except Exception as e:
                        app.logger.error(f"Error in get_product_info: {str(e)}")
                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": json.dumps({"error": str(e)})
                        })
            
            client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )
            return True
        return False

    @app.route('/welcome', methods=['GET'])
    def get_welcome_message():
        welcome_message = config.get('welcome_message', '')
        csrf_token = generate_csrf()
        return jsonify({"welcome_message": welcome_message, "csrf_token": csrf_token})

    @app.route('/static/<path:filename>')
    def serve_static(filename):
        return send_from_directory(app.static_folder, filename)

    @app.route('/clear_session', methods=['POST'])
    @basic_auth.required
    def clear_session():
        try:
            redis_connection.flushall()
            return "Session cache cleared", 200
        except Exception as e:
            app.logger.error(f"Error clearing session: {str(e)}")
            return "Error clearing session", 500
        
    @app.route('/test_json', methods=['GET', 'POST'])
    def test_json():
        return jsonify({"status": "success", "message": "Test JSON response"})
        
    @app.route('/chat_widget')
    def chat_widget():
        form = ChatForm()
        session_id = ensure_str(session.get('sid', os.urandom(16).hex()))
        
        # Get anonymous_id from query parameters
        anonymous_id = request.args.get('anonymous_id')
        
        if anonymous_id:
            analytics.track(anonymous_id, 'Epona Widget Opened', {
                'session_id': session_id
            })
        
        return render_template('chat_widget.html', form=form)

    @app.route('/embed_chat.js')
    def embed_chat():
        session_id = ensure_str(session.get('sid', os.urandom(16).hex()))
        
        # Get session info from query parameters instead of JSON
        anonymous_id = request.args.get('anonymous_id')
        
        if anonymous_id:
            analytics.identify(session_id, {
                'anonymous_id': anonymous_id
            })
        
        return send_from_directory(app.static_folder, 'embed_chat.js')
    
    @app.route('/end_chat', methods=['POST'])
    def end_chat():
        session_id = ensure_str(session.get('sid', os.urandom(16).hex()))
        analytics.track(session_id, 'Chat Session Ended', {
            'session_id': session_id
        })
        session.pop('chat_session_started', None)
        return jsonify({"status": "success"})
        
    @app.route('/update_session_info', methods=['POST'])
    @csrf.exempt  # Temporarily exempt this route from CSRF protection for testing
    def update_session_info():
        try:
            app.logger.debug(f"Received request to /update_session_info: {request.data}")
            session_info = request.json
            if not session_info:
                app.logger.error("No JSON data received in /update_session_info")
                return jsonify({"status": "error", "message": "No data provided"}), 400

            app.logger.debug(f"Received session info: {session_info}")

            session['client_session_info'] = session_info

            analytics.identify(session.sid, {
                'anonymous_id': session_info.get('ajs_anonymous_id'),
                'first_session': session_info.get('first_session'),
                'cart_data': session_info.get('_pmw_session_data_cart'),
                'pages_visit_count': session_info.get('klaviyoPagesVisitCount')
            })

            return jsonify({"status": "success"})
        except Exception as e:
            app.logger.error(f"Error in /update_session_info: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500

except Exception as e:
    print(f"An error occurred during initialization: {str(e)}")
    import traceback
    traceback.print_exc()

if __name__ == '__main__':
    print("Starting Flask development server...")
    app.run(debug=True, ssl_context=('cert.pem', 'key.pem'))
    print("Flask server stopped.")