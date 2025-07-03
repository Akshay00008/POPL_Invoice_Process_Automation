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
    # Updated regex to check if the URL belongs to the KRA portal, including itax subdomain
    kra_url_pattern = re.compile(r'https://(www\.)?itax\.kra\.go\.ke/KRA-Portal/invoiceChk\.htm\?actionCode=loadPage&invoiceNo=\d+')
    return bool(kra_url_pattern.match(url))

# Function to save extracted invoice details to MySQL database
def save_to_database(data):
    try:
        # Prepare the SQL insert query using SQLAlchemy's text() function
        query = text('''
        INSERT INTO kra_portal (control_unit_invoice_number, invoice_date, total_taxable_amount, 
                                total_tax_amount, total_invoice_amount, supplier_name, invoice_number)
        VALUES (:control_unit_invoice_number, :invoice_date, :total_taxable_amount, 
                :total_tax_amount, :total_invoice_amount, :supplier_name, :invoice_number)
        ''')

        # Execute the query using the session with parameters
        session.execute(query, data)
        session.commit()
        print("Data successfully saved to the database.")
    except Exception as e:
        print(f"Error saving data: {e}")
        session.rollback()

# Function to extract invoice details from the KRA portal
def extract_invoice_details(url):
    response = requests.get(url)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extracting specific details from the table in HTML
        try:
            control_unit_invoice_no = soup.find('td', string='Control Unit Invoice Number').find_next('td').text.strip() if soup.find('td', string='Control Unit Invoice Number') else 'Not Found'
            
            # Handle missing invoice date and convert to proper format (if exists)
            invoice_date = soup.find('td', string='Invoice Date').find_next('td').text.strip() if soup.find('td', string='Invoice Date') else None
            if invoice_date:
                try:
                    invoice_date = datetime.strptime(invoice_date, '%d/%m/%Y').strftime('%Y-%m-%d')
                except ValueError:
                    print(f"Error: Invalid date format '{invoice_date}'")
                    invoice_date = None

            # Handle numeric fields and missing values
            total_taxable_amount = soup.find('td', string='Total Taxable Amount').find_next('td').text.strip() if soup.find('td', string='Total Taxable Amount') else 0
            total_tax_amount = soup.find('td', string='Total Tax Amount').find_next('td').text.strip() if soup.find('td', string='Total Tax Amount') else 0
            total_invoice_amount = soup.find('td', string='Total Invoice Amount').find_next('td').text.strip() if soup.find('td', string='Total Invoice Amount') else 0
            
            # Handle missing supplier name
            supplier_name = soup.find('td', string='Supplier Name').find_next('td').text.strip() if soup.find('td', string='Supplier Name') else None
            
            invoice_number = soup.find('td', string='Trader System Invoice No').find_next('td').text.strip() if soup.find('td', string='Trader System Invoice No') else 'Not Found'

            # Create a dictionary with the extracted data
        
            data = {
    'control_unit_invoice_number': 0 if not control_unit_invoice_no or control_unit_invoice_no.strip() == "" else control_unit_invoice_no,  
    'invoice_date': None if not invoice_date or invoice_date.strip() == "" else invoice_date,  # Assuming invoice_date can be None if missing or empty
    'total_taxable_amount': 0 if not total_taxable_amount or total_taxable_amount.strip() == "" else total_taxable_amount,  
    'total_tax_amount': 0 if not total_tax_amount or total_tax_amount.strip() == "" else total_tax_amount,  
    'total_invoice_amount': 0 if not total_invoice_amount or total_invoice_amount.strip() == "" else total_invoice_amount,  
    'supplier_name': None if not supplier_name or supplier_name.strip() == "" else supplier_name,  # If missing or empty, set it to None
    'invoice_number': 0 if not invoice_number or invoice_number.strip() == "" else invoice_number  # If missing or empty, set it to 0
}


            # Save to MySQL database
            save_to_database(data)

            # Print or return the details
            print(f"Control Unit Invoice Number: {control_unit_invoice_no}")
            print(f"Invoice Date: {invoice_date}")
            print(f"Total Taxable Amount: {total_taxable_amount}")
            print(f"Total Tax Amount: {total_tax_amount}")
            print(f"Total Invoice Amount: {total_invoice_amount}")
            print(f"Supplier Name: {supplier_name}")
            print(f"Invoice Number: {invoice_number}")
        except AttributeError as e:
            print("Error: Unable to extract all details, some fields might be missing.")
            print(f"Exception: {e}")
    else:
        print(f"Error: Failed to retrieve the page. Status code: {response.status_code}")

# Function to extract images from a PDF file
def extract_images_from_pdf(pdf_path):
    images = convert_from_path(pdf_path, dpi=300)
    return images

# Function to check for QR codes in the PDF and validate KRA URL
def check_qr_code_in_pdf(pdf_path):
    images = extract_images_from_pdf(pdf_path)

    for page_num, image in enumerate(images, start=1):
        # Convert the PIL image to OpenCV format (numpy array)
        open_cv_image = np.array(image)
        open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)

        # Save the image as a temporary file
        with NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
            temp_image_path = temp_file.name
            cv2.imwrite(temp_image_path, open_cv_image)

            # Use pyzxing (Zxing's Python wrapper) to decode QR codes
            reader = BarCodeReader()
            decoded_objects = reader.decode(temp_image_path)

            if decoded_objects:
                for obj in decoded_objects:
                    # Extract the QR code data (URL), decoding bytes to string
                    qr_data = obj['parsed'].decode('utf-8')
                    print(f"Found QR Code on page {page_num}: {qr_data}")

                    # Check if the QR code contains a valid KRA portal URL
                    if is_valid_kra_url(qr_data):
                        print(f"Valid KRA URL found in QR code: {qr_data}")
                        # If URL is valid, extract invoice details
                        extract_invoice_details(qr_data)
                    else:
                        print(f"Incorrect URL or not pointing to KRA portal: {qr_data}")
                    return {"Success"}    
            else:
                print(f"No QR code found on page {page_num}.")
                return {"QR code or Link not found"}

        










# Test the function with a PDF path
pdf_path = 'C:\\Users\\hp\\Desktop\\pwani_finance_01-07-2025\\Invoices\\JALARAM 126757.pdf'  # Replace with the path to your PDF

