print("Starting app initialization...")
import logging
from openai import OpenAIError
from flask import Flask, request, jsonify, render_template, send_from_directory, session, Response, stream_with_context, make_response
from flask_session import Session
from flask_wtf import FlaskForm, CSRFProtect
from flask_wtf.csrf import CSRFProtect, generate_csrf, validate_csrf
from flask_basicauth import BasicAuth
from flask_jwt_extended import JWTManager, create_access_token
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from .initialize import client, analytics, config
from .session_manager import get_or_create_thread, ensure_str
from .redis_config import redis_connection
from .ask_helpers import ChatForm, generate_responses
from dotenv import load_dotenv
import os
from wtforms import TextAreaField
from wtforms.validators import DataRequired

print("Imports complete")

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

try:
    # Load environment variables
    load_dotenv()
    print("Environment variables loaded")
        
    print("Creating Flask app")
    app = Flask(__name__, template_folder='templates', static_folder='static')
    print("Flask app created")

    print("Setting up CORS")
    CORS(app, resources={
        r"/*": {
            "origins": ["https://www.eqbay.co", "https://eqbay.co", "https://epona.eqbay.co", "http://localhost:*", "http://127.0.0.1:*"],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "X-CSRFToken"],
            "supports_credentials": True
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
    def log_request_info():
        app.logger.debug('Headers: %s', request.headers)
        app.logger.debug('Body: %s', request.get_data())
        app.logger.debug('URL: %s', request.url)
        app.logger.debug('Method: %s', request.method)
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
    @csrf.exempt
    def ask():
        try:
            logger.debug("Entered the /ask endpoint")
            logger.debug(f"Received request: {request.method} {request.url}")
            logger.debug(f"Form data: {request.form}")

            question = request.form.get('question')
            csrf_token = request.form.get('csrf_token')

            logger.debug(f"Extracted form fields - question: {question}, csrf_token: {csrf_token}")

            if not question or not csrf_token:
                logger.debug("Missing question or CSRF token")
                return jsonify({"error": "Missing question or CSRF token"}), 400

            try:
                logger.debug("Validating CSRF token")
                validate_csrf(csrf_token)
                logger.debug("CSRF token validated")
            except Exception as e:
                logger.error(f"CSRF validation failed: {str(e)}")
                return jsonify({"error": "Invalid CSRF token"}), 400

            form = ChatForm(request.form)
            logger.debug(f"Form validation status: {form.validate()}")
            if form.validate():
                question = form.question.data
                logger.debug(f"Validated question: {question}")

                session_id = ensure_str(session.get('sid', os.urandom(16).hex()))

                if 'chat_session_started' not in session:
                    analytics.track(session_id, 'Chat Session Started', {
                        'session_id': session_id
                    })
                    session['chat_session_started'] = True
                
                analytics.track(session_id, 'User Message Sent', {
                    'question': question
                })

                logger.debug(f"Session ID: {session_id}")
                thread_id = ensure_str(get_or_create_thread(session_id))
                logger.debug(f"Thread ID: {thread_id}")

                try:
                    logger.debug(f"Thread ID: {thread_id}")
                    client.beta.threads.messages.create(
                        thread_id=thread_id,
                        role="user",
                        content=question
                    )
                    logger.debug("User message added to thread")

                    run = client.beta.threads.runs.create(
                        thread_id=thread_id,
                        assistant_id=app.config['ASSISTANT_ID']
                    )
                    logger.debug(f"Run created with ID: {run.id}")

                    return Response(stream_with_context(generate_responses(thread_id, run)), content_type='text/event-stream')

                except OpenAIError as e:
                    logger.error(f"OpenAI API error: {str(e)}")
                    return jsonify({"error": f"An error occurred: {str(e)}"}), 500

            else:
                logger.debug(f"Form validation errors: {form.errors}")
                return jsonify({"error": "Invalid form submission"}), 400

        except Exception as e:
            logger.error(f"An error occurred in /ask endpoint: {str(e)}")
            return jsonify({"error": "An unexpected error occurred"}), 500

    @app.route('/welcome', methods=['GET', 'OPTIONS'])
    def get_welcome_message():
        if request.method == 'OPTIONS':
            response = make_response()
            response.headers.add('Access-Control-Allow-Origin', 'https://www.eqbay.co')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
            response.headers.add('Access-Control-Allow-Methods', 'GET,OPTIONS')
            response.headers.add('Access-Control-Allow-Credentials', 'true')
            return response

        welcome_message = config.get('welcome_message', '')
        csrf_token = generate_csrf()
        response = jsonify({
            "response": welcome_message,
            "csrf_token": csrf_token
        })
        response.headers.add('Access-Control-Allow-Origin', 'https://www.eqbay.co')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response

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
        
    @app.route('/update_session_info', methods=['POST', 'OPTIONS'])
    @csrf.exempt
    def update_session_info():
        if request.method == 'OPTIONS':
            response = make_response()
            response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin'))
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type, X-CSRFToken')
            response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
            response.headers.add('Access-Control-Allow-Credentials', 'true')
            return response

        try:
            origin = request.headers.get('Origin')
            app.logger.debug(f"Origin: {origin}")
            
            allowed_origins = ['https://www.eqbay.co', 'https://eqbay.co', 'https://epona.eqbay.co']
            if not origin or origin not in allowed_origins:
                app.logger.error(f"Invalid or missing origin: Origin={origin}")
                return jsonify({"status": "error", "message": "Invalid or missing origin"}), 400

            # Parse the JSON data from the request body
            session_info = request.json
            app.logger.debug(f"Received session info: {session_info}")

            if not session_info:
                return jsonify({"status": "error", "message": "No session info provided"}), 400

            # Store session info
            session['client_session_info'] = session_info

            # Identify user (adjust this based on your analytics setup)
            if hasattr(app, 'analytics'):
                app.analytics.identify(session.get('sid', 'unknown'), {
                    'anonymous_id': session_info.get('ajs_anonymous_id'),
                    'first_session': session_info.get('first_session'),
                    'cart_data': session_info.get('_pmw_session_data_cart'),
                    'pages_visit_count': session_info.get('klaviyoPagesVisitCount')
                })

            response = jsonify({"status": "success", "message": "Session info updated"})
            response.headers.add('Access-Control-Allow-Origin', origin)
            response.headers.add('Access-Control-Allow-Credentials', 'true')
            return response
        
        except Exception as e:
            app.logger.error(f"Error in /update_session_info: {str(e)}")
            response = jsonify({"status": "error", "message": str(e)})
            response.headers["Access-Control-Allow-Origin"] = origin if origin else 'https://www.eqbay.co'
            response.headers["Access-Control-Allow-Credentials"] = "true"
            return response

except Exception as e:
    print(f"An error occurred during initialization: {str(e)}")
    import traceback
    traceback.print_exc()

if __name__ == '__main__':
    print("Starting Flask development server...")
    app.run(debug=True, ssl_context=('cert.pem', 'key.pem'))
    print("Flask server stopped.")