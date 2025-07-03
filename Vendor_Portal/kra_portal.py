import logging
from datetime import datetime
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import requests
from bs4 import BeautifulSoup
import re
from pyzxing import BarCodeReader
from tempfile import NamedTemporaryFile
import cv2
import numpy as np
from pdf2image import convert_from_path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()

# Extracting the database connection details from the environment variables
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))  # Convert DB_PORT to integer
DB_NAME = os.getenv("DB_NAME")

# Create a connection string for SQLAlchemy
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create an SQLAlchemy engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Creating a sessionmaker to interact with the database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = SessionLocal()

# Function to check if the QR code contains a valid KRA portal URL
def is_valid_kra_url(url):
    kra_url_pattern = re.compile(r'https://(www\.)?itax\.kra\.go\.ke/KRA-Portal/invoiceChk\.htm\?actionCode=loadPage&invoiceNo=\d+')
    return bool(kra_url_pattern.match(url))

# Function to save extracted invoice details to MySQL database
def save_to_database(data):
    try:
        query = text('''
        INSERT INTO kra_portal (control_unit_invoice_number, invoice_date, total_taxable_amount, 
                                total_tax_amount, total_invoice_amount, supplier_name, invoice_number)
        VALUES (:control_unit_invoice_number, :invoice_date, :total_taxable_amount, 
                :total_tax_amount, :total_invoice_amount, :supplier_name, :invoice_number)
        ''')
        session.execute(query, data)
        session.commit()
        logger.info("Data successfully saved to the database.")
        return {"status": "success", "message": "Data successfully saved to the database."}
    except Exception as e:
        logger.error(f"Error saving data: {e}")
        session.rollback()
        return {"status": "error", "message": f"Error saving data: {e}"}

# Function to extract invoice details from the KRA portal
def extract_invoice_details(url):
    response = requests.get(url)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        try:
            control_unit_invoice_no = soup.find('td', string='Control Unit Invoice Number').find_next('td').text.strip() if soup.find('td', string='Control Unit Invoice Number') else 'Not Found'
            invoice_date = soup.find('td', string='Invoice Date').find_next('td').text.strip() if soup.find('td', string='Invoice Date') else None
            if invoice_date:
                try:
                    invoice_date = datetime.strptime(invoice_date, '%d/%m/%Y').strftime('%Y-%m-%d')
                except ValueError:
                    logger.error(f"Invalid date format: '{invoice_date}'")
                    invoice_date = None

            total_taxable_amount = soup.find('td', string='Total Taxable Amount').find_next('td').text.strip() if soup.find('td', string='Total Taxable Amount') else 0
            total_tax_amount = soup.find('td', string='Total Tax Amount').find_next('td').text.strip() if soup.find('td', string='Total Tax Amount') else 0
            total_invoice_amount = soup.find('td', string='Total Invoice Amount').find_next('td').text.strip() if soup.find('td', string='Total Invoice Amount') else 0
            supplier_name = soup.find('td', string='Supplier Name').find_next('td').text.strip() if soup.find('td', string='Supplier Name') else None
            invoice_number = soup.find('td', string='Trader System Invoice No').find_next('td').text.strip() if soup.find('td', string='Trader System Invoice No') else 'Not Found'

            data = {
                'control_unit_invoice_number': 0 if not control_unit_invoice_no or control_unit_invoice_no.strip() == "" else control_unit_invoice_no,
                'invoice_date': None if not invoice_date or invoice_date.strip() == "" else invoice_date,
                'total_taxable_amount': 0 if not total_taxable_amount or total_taxable_amount.strip() == "" else total_taxable_amount,
                'total_tax_amount': 0 if not total_tax_amount or total_tax_amount.strip() == "" else total_tax_amount,
                'total_invoice_amount': 0 if not total_invoice_amount or total_invoice_amount.strip() == "" else total_invoice_amount,
                'supplier_name': None if not supplier_name or supplier_name.strip() == "" else supplier_name,
                'invoice_number': 0 if not invoice_number or invoice_number.strip() == "" else invoice_number
            }

            result = save_to_database(data)
            return result

        except AttributeError as e:
            logger.error(f"Error: Unable to extract all details, some fields might be missing. {e}")
            return {"status": "error", "message": "Error extracting invoice details."}
    else:
        logger.error(f"Error: Failed to retrieve the page. Status code: {response.status_code}")
        return {"status": "error", "message": f"Error: Failed to retrieve the page. Status code: {response.status_code}"}

# Function to extract images from a PDF file
def extract_images_from_pdf(pdf_path):
    try:
        images = convert_from_path(pdf_path, dpi=300)
        return images
    except Exception as e:
        logger.error(f"Error extracting images from PDF: {e}")
        return None

# Function to check for QR codes in the PDF and validate KRA URL
def check_qr_code_in_pdf(pdf_path):
    images = extract_images_from_pdf(pdf_path)

    if not images:
        logger.error("No images extracted from the PDF.")
        return {"status": "error", "message": "Error extracting images from the PDF."}

    for page_num, image in enumerate(images, start=1):
        open_cv_image = np.array(image)
        open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)

        with NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
            temp_image_path = temp_file.name
            cv2.imwrite(temp_image_path, open_cv_image)

            reader = BarCodeReader()
            decoded_objects = reader.decode(temp_image_path)
            print("line 133")

            if decoded_objects:
                print("136")
                obj = decoded_objects[0]  # Process the first decoded object
                if 'parsed' in obj:
                    qr_data = obj['parsed'].decode('utf-8')
                    logger.info(f"Found QR Code on page {page_num}: {qr_data}")

                    if is_valid_kra_url(qr_data):
                        logger.info(f"Valid KRA URL found in QR code: {qr_data}")
                        result = extract_invoice_details(qr_data)
                        return result
                    else:
                        logger.error(f"Incorrect URL or not pointing to KRA portal: {qr_data}")
                        return {"status": "error", "message": "QR code or Link not found"}
            else:
                logger.error(f"No QR code found on page {page_num}.")
                return {"status": "error", "message": "QR code or Link not found"}

    return {"status": "error", "message": "No QR code found in the PDF"}

# Test the function with a PDF path (provide the correct path to your PDF)
# pdf_path = 'C:\\Users\\hp\\Desktop\\pwani_finance_01-07-2025\\Invoices\\JALARAM 126757.pdf'
# result = check_qr_code_in_pdf(pdf_path)


# Test the function with a PDF path
# pdf_path = 'C:\\Users\\hp\\Desktop\\pwani_finance_01-07-2025\\Invoices\\JALARAM 126757.pdf'  # Replace with the path to your PDF

