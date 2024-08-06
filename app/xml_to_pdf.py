import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.units import inch
from io import BytesIO
import html
import requests
import logging

def parse_xml(xml_content):
    root = ET.fromstring(xml_content)
    return root.findall('.//post')

def clean_html(content):
    if content is None:
        return ""
    soup = BeautifulSoup(content, 'html.parser')
    return soup.get_text(separator=' ', strip=True)

def create_page(post, story, styles):
    for child in post:
        if child.tag == 'Content':
            content = clean_html(html.unescape(child.text or ""))
            story.append(Paragraph(f"Content: {content}", styles['BodyText']))
        else:
            text = child.text or ""
            story.append(Paragraph(f"{child.tag}: {text}", styles['BodyText']))
        story.append(Spacer(1, 0.2*inch))

def generate_pdf(xml_url):
    try:
        response = requests.get(xml_url)
        response.raise_for_status()
        
        xml_content = response.content
        posts = parse_xml(xml_content)
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY))
        styles['BodyText'].fontSize = 10
        styles['BodyText'].leading = 12
        
        story = []
        
        for post in posts:
            create_page(post, story, styles)
            story.append(PageBreak())

        doc.build(story)
        
        buffer.seek(0)
        return buffer.getvalue()
    
    except requests.RequestException as e:
        logging.error(f"Error fetching XML: {e}")
        return None
    except ET.ParseError as e:
        logging.error(f"Error parsing XML: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error in generate_pdf: {e}", exc_info=True)
        return None