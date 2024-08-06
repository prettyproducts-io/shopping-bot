from .celery_config import celery, create_celery_app
from celery import chord
from celery.exceptions import Ignore
from flask import current_app
import logging
import time
import os
from dotenv import load_dotenv
import json

load_dotenv()

def get_flask_app():
    """Ensure Flask app context is available."""
    if current_app:
        return current_app._get_current_object()
    else:
        return create_celery_app().flask_app

@celery.task(bind=True)
def process_embeddings_task(self, text_blocks):
    logger = logging.getLogger(__name__)
    logger.info(f"Starting embedding process for {len(text_blocks)} blocks")

    app = get_flask_app()

    with app.app_context():
        from .process_document import get_embedding

        total_blocks = len(text_blocks)
        for i, block in enumerate(text_blocks):
            if 'embedding' not in block:
                try:
                    block['embedding'] = get_embedding(block['text'])
                    progress = (i + 1) / total_blocks * 100
                    self.update_state(state='PROGRESS', meta={
                        'current': i + 1,
                        'total': total_blocks,
                        'progress': progress,
                        'stage': 'embeddings'
                    })
                    logger.debug(f"Processed block {i + 1}/{total_blocks}")
                except Exception as e:
                    logger.error(f"Error generating embedding for block {i}: {str(e)}")

        logger.info("Embedding process complete")
        return {'current': total_blocks, 'total': total_blocks, 'progress': 100}

@celery.task(bind=True)
def generate_catalog_task(self):
    logger = logging.getLogger(__name__)
    logger.info("Starting catalog generation")

    app = get_flask_app()

    with app.app_context():
        from .xml_to_pdf import generate_pdf
        from .process_document import process_document, save_embeddings
        from .rag import initialize_rag

        def load_config():
            with open('config.json', 'r') as f:
                return json.load(f)

        config = load_config()
        app.config.update(config)

        if 'catalog_xml_url' not in app.config:
            self.update_state(state='FAILURE', meta={'status': 'error', 'message': 'catalog_xml_url missing in config'})
            raise Ignore()

        self.update_state(state='PROGRESS', meta={'status': 'Generating PDF from XML...'})
        pdf_content = generate_pdf(app.config['catalog_xml_url'])
        if pdf_content is None:
            self.update_state(state='FAILURE', meta={'status': 'error', 'message': 'Failed to generate PDF'})
            raise Ignore()
        
        self.update_state(state='PROGRESS', meta={'status': 'PDF generated successfully'})

        self.update_state(state='PROGRESS', meta={'status': 'Processing document...'})
        _, _, text_blocks, pdf_mod_date = process_document()
        self.update_state(state='PROGRESS', meta={'status': f'Document processed. {len(text_blocks)} text blocks extracted'})

        self.update_state(state='PROGRESS', meta={'status': 'Starting embedding generation...'})
        embedding_task = process_embeddings_task.delay(text_blocks)
        
        while not embedding_task.ready():
            time.sleep(2)
            task_result = embedding_task.result
            if isinstance(task_result, dict) and 'progress' in task_result:
                self.update_state(state='PROGRESS', meta={'status': 'Generating embeddings', 'progress': task_result['progress']})

        embeddings_result = embedding_task.result
        if isinstance(embeddings_result, dict) and 'embeddings' in embeddings_result:
            embeddings = embeddings_result['embeddings']
            save_embeddings({'text_blocks': text_blocks, 'embeddings': embeddings, 'pdf_mod_date': pdf_mod_date})
            self.update_state(state='PROGRESS', meta={'status': 'Embeddings generation complete and saved'})
        else:
            self.update_state(state='FAILURE', meta={'status': 'error', 'message': 'Failed to generate embeddings'})
            raise Ignore()

        self.update_state(state='PROGRESS', meta={'status': 'Reinitializing RAG system...'})
        try:
            initialize_rag()
            self.update_state(state='PROGRESS', meta={'status': 'RAG system reinitialized successfully'})
        except Exception as e:
            logger.error(f"Error reinitializing RAG system: {str(e)}")
            self.update_state(state='FAILURE', meta={'status': 'error', 'message': f'Error reinitializing RAG system: {str(e)}'})
            raise Ignore()

        self.update_state(state='SUCCESS', meta={'status': 'Catalog generation complete'})
        return {'status': 'complete'}