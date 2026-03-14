import pdfplumber
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_resume(pdf_path):
    """
    Parses the PDF resume into structured markdown/text format.
    """
    if not os.path.exists(pdf_path):
        logger.error(f"Resume file not found at {pdf_path}")
        return None
        
    logger.info(f"Parsing resume {pdf_path}")
    text_content = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                logger.info(f"Parsing page {i+1}")
                text = page.extract_text()
                if text:
                    text_content.append(text)
        
        full_text = "\n\n".join(text_content)
        return full_text
        
    except Exception as e:
        logger.error(f"Error parsing resume: {e}")
        return None

if __name__ == "__main__":
    output = "Phani_Kumar_Kolla_profile.pdf"
    if os.path.exists(output):
        text = parse_resume(output)
        print("--- EXTRACTED RESUME TEXT ---")
        print(text[:500] if text else "Failed to extract.")
    else:
        print(f"Test file {output} not found.")
