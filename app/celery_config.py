from celery import Celery
from flask import Flask
from dotenv import load_dotenv
import os

load_dotenv()  # This will load the environment variables from .env

def create_flask_app():
    app = Flask(__name__)
    
    # Load configurations from environment variables
    app.config['CELERY_BROKER_URL'] = os.getenv('CELERY_BROKER_URL')
    app.config['CELERY_RESULT_BACKEND'] = os.getenv('CELERY_RESULT_BACKEND')
    
    return app

def create_celery_app(app=None):
    if app is None:
        app = create_flask_app()

    celery = Celery(
        app.import_name,
        broker=app.config['CELERY_BROKER_URL'],
        backend=app.config['CELERY_RESULT_BACKEND'],
        include=['app.celery_worker']
    )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    celery.flask_app = app
    return celery

flask_app = create_flask_app()
celery = create_celery_app(flask_app)

def configure_celery(app):
    celery.conf.update(app.config)
    return celery