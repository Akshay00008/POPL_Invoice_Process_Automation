import logging
from datetime import datetime
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import requests
from bs4 import BeautifulSoup
import re
from pyzbar.pyzbar import decode as pyzbar_decode
from tempfile import NamedTemporaryFile
import cv2
import numpy as np
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
from ctypes import CDLL

# Load the DLL (make sure to provide the correct path)
libzbar_path = r"/usr/lib/x86_64-linux-gnu/libzbar.so.0"
libzbar = CDLL(libzbar_path)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()

# Extracting the database connection details
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME")

# Create database engine
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = SessionLocal()

# Configure Tesseract path if needed
# pytesseract.pytesseract.tesseract_cmd = r'<full_path_to_tesseract_executable>'

def is_valid_kra_url(url):
    """Validate KRA URL pattern with improved regex"""
    kra_url_pattern = re.compile(
        r'https?://(www\.)?itax\.kra\.go\.ke/KRA-Portal/invoiceChk\.htm\?actionCode=loadPage&invoiceNo=\d+'
    )
    return bool(kra_url_pattern.match(url))

def save_to_database(data):
    """Save extracted invoice details to database"""
    try:
        query = text('''INSERT INTO kra_portal (control_unit_invoice_number, invoice_date, total_taxable_amount, 
                        total_tax_amount, total_invoice_amount, supplier_name, invoice_number)
                        VALUES (:control_unit_invoice_number, :invoice_date, :total_taxable_amount, 
                        :total_tax_amount, :total_invoice_amount, :supplier_name, :invoice_number)''')
        session.execute(query, data)
        session.commit()
        logger.info("Data successfully saved to database.")
        return {"status": "success", "message": "Data saved to database."}
    except Exception as e:
        logger.error(f"Database error: {e}")
        session.rollback()
        return {"status": "error", "message": f"Database error: {e}"}

def extract_invoice_details(url):
    """Extract invoice details from KRA portal with improved error handling"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Create mapping of field names to their values
        field_map = {
            'Control Unit Invoice Number': 'control_unit_invoice_number',
            'Invoice Date': 'invoice_date',
            'Total Taxable Amount': 'total_taxable_amount',
            'Total Tax Amount': 'total_tax_amount',
            'Total Invoice Amount': 'total_invoice_amount',
            'Supplier Name': 'supplier_name',
            'Trader System Invoice No': 'invoice_number'
        }
        
        data = {v: None for v in field_map.values()}
        
        for field, key in field_map.items():
            element = soup.find('td', string=field)
            if element:
                value = element.find_next('td').text.strip()
                if key == 'invoice_date' and value:
                    try:
                        value = datetime.strptime(value, '%d/%m/%Y').strftime('%Y-%m-%d')
                    except ValueError:
                        logger.warning(f"Invalid date format: '{value}'")
                data[key] = value
        
        # Convert numeric fields
        for field in ['total_taxable_amount', 'total_tax_amount', 'total_invoice_amount']:
            if data[field]:
                try:
                    # Remove any non-numeric characters
                    data[field] = float(re.sub(r'[^\d.]', '', data[field]))
                except ValueError:
                    data[field] = 0.0
            else:
                data[field] = 0.0
        
        return save_to_database(data)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error: {e}")
        return {"status": "error", "message": f"Network error: {e}"}
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        return {"status": "error", "message": f"Extraction error: {e}"}

def preprocess_image(image):
    """Enhance image for better QR/text detection"""
    # Convert to OpenCV format
    open_cv_image = np.array(image)
    img = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply adaptive thresholding
    thresh = cv2.adaptiveThreshold(
        gray, 255, 
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    
    # Apply morphological operations
    kernel = np.ones((3, 3), np.uint8)
    processed = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    
    return processed

def extract_text_from_image(image):
    """Extract text from image using OCR"""
    try:
        # Preprocess image specifically for OCR
        gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        text = pytesseract.image_to_string(gray)
        return text
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return ""

def find_kra_url_in_text(text):
    """Search for KRA URL pattern in extracted text"""
    kra_url_pattern = re.compile(
        r'https?://(www\.)?itax\.kra\.go\.ke/KRA-Portal/invoiceChk\.htm\?actionCode=loadPage&invoiceNo=\d+'
    )
    match = kra_url_pattern.search(text)
    return match.group(0) if match else None

def extract_images_from_pdf(pdf_path):
    """Extract images from PDF with error handling"""
    try:
        return convert_from_path(pdf_path, dpi=300, poppler_path=r'/usr/bin')
    except Exception as e:
        logger.error(f"PDF conversion error: {e}")
        return []

def detect_qr_codes(image):
    """Detect QR codes using multiple methods"""
    # Method 1: PyZbar (fastest)
    decoded_objects = pyzbar_decode(image)
    if decoded_objects:
        return [obj.data.decode('utf-8') for obj in decoded_objects]
    
    # Method 2: OpenCV QRCodeDetector (if available)
    if hasattr(cv2, 'QRCodeDetector'):
        detector = cv2.QRCodeDetector()
        retval, decoded_info, _, _ = detector.detectAndDecodeMulti(np.array(image))
        if retval and decoded_info:
            return [info for info in decoded_info if info]
    
    return []

def check_qr_code_in_pdf(pdf_path):
    """Process PDF to find KRA URLs via QR codes or text"""
    try:
        images = extract_images_from_pdf(pdf_path)
        if not images:
            return {"status": "error", "message": "Failed to extract images from PDF"}

        for page_num, image in enumerate(images, 1):
            # Try QR code detection first
            processed_img = preprocess_image(image)
            qr_codes = detect_qr_codes(processed_img)
            
            for qr_data in qr_codes:
                logger.info(f"Found QR Code on page {page_num}: {qr_data}")
                if is_valid_kra_url(qr_data):
                    logger.info(f"Valid KRA URL found: {qr_data}")
                    return extract_invoice_details(qr_data)
            
            # Fallback to OCR text extraction
            logger.info(f"No QR found on page {page_num}, trying OCR...")
            text = extract_text_from_image(image)
            url = find_kra_url_in_text(text)
            
            if url:
                logger.info(f"Found KRA URL in text: {url}")
                return extract_invoice_details(url)
        
        return {"status": "error", "message": "No valid KRA URL found in document"}
    
    except Exception as e:
        logger.error(f"PDF processing failed: {e}")
        return {"status": "error", "message": f"Processing error: {e}"}

# Example usage
# result = check_qr_code_in_pdf('path/to/your/document.pdf')

# Example usage
result = check_qr_code_in_pdf('/apps/POPL_Invoice_Process_Automation/Invoices/FRIGITEC INV134506.pdf')


# from ctypes.util import find_library
# libzbar_path = find_library('zbar')
# print(f"Library found at: {libzbar_path}")

