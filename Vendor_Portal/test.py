import os
from sqlalchemy import create_engine
import pandas as pd
import cv2
from pdf2image import convert_from_path
import numpy as np
from pyzbar.pyzbar import decode
from flask import request, jsonify
import nest_asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# Apply nest_asyncio to allow running asyncio event loop in Jupyter or other async event loops
nest_asyncio.apply()

# Database connection setup using environment variables
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))  # Default to 3306 if not provided
DB_NAME = os.getenv("DB_NAME")

# Create a connection string for SQLAlchemy
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create an SQLAlchemy engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

class QRCodeExtractor:
    def __init__(self, input_path, dpi_list=None):
        self.input_path = input_path
        self.dpi_list = dpi_list or [400, 500, 600, 700, 800]
        self.pdf_list = self._get_pdf_list()

    def _get_pdf_list(self):
        """Get list of PDFs from the provided path"""
        if os.path.isfile(self.input_path) and self.input_path.lower().endswith('.pdf'):
            return [self.input_path]
        elif os.path.isdir(self.input_path):
            return [
                os.path.join(self.input_path, f)
                for f in os.listdir(self.input_path)
                if f.lower().endswith('.pdf')
            ]
        else:
            raise ValueError("❌ Input path must be a .pdf file or a folder containing .pdf files.")

    def extract_qr_codes(self):
        """Extract QR codes from the PDFs"""
        extracted_data = {}
        for pdf_path in self.pdf_list:
            print(f"\n📄 Processing PDF: {os.path.basename(pdf_path)}")
            found = False

            for dpi in self.dpi_list:
                print(f"   🔍 Trying DPI: {dpi}")
                try:
                    images = convert_from_path(pdf_path, dpi=dpi)
                    image = images[0]
                except Exception as e:
                    print(f"   ❌ Failed to read PDF at {dpi} DPI: {e}")
                    continue

                qr_data = self._process_image(image)
                if qr_data:
                    extracted_data[pdf_path] = qr_data
                    found = True
                    break

            if not found:
                print(f"   ❌ No QR code found in '{os.path.basename(pdf_path)}' at any DPI.")
        return extracted_data

    def _process_image(self, image):
        """Process the image to detect QR codes"""
        open_cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)
        blurred = cv2.GaussianBlur(binary, (7, 7), 0)

        qr_codes = decode(blurred)
        if qr_codes:
            return [qr.data.decode('utf-8') for qr in qr_codes]
        return None


class WebPageScraper:
    def __init__(self, url):
        self.url = url

    async def fetch_html(self):
        """Fetch HTML content from a URL using Playwright"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(self.url, timeout=20000)
                await page.wait_for_selector("body")
                html = await page.content()
                await browser.close()
                return html
        except Exception as e:
            print(f"❌ Failed to fetch HTML from {self.url}: {e}")
            return None


class KRAInvoiceParser:
    def __init__(self, html):
        self.html = html

    def extract_data(self):
        """Extract invoice data from HTML content"""
        soup = BeautifulSoup(self.html, "html.parser")
        result = {
            "control_unit_invoice_number": None,
            "invoice_number": None,
            "invoice_date": None,
            "total_taxable_amount": None,
            "total_tax_amount": None,
            "total_invoice_amount": None,
            "supplier_name": None
        }

        key_map = {
            "control unit invoice number": "control_unit_invoice_number",
            "trader system invoice no": "invoice_number",
            "invoice date": "invoice_date",
            "total taxable amount": "total_taxable_amount",
            "total tax amount": "total_tax_amount",
            "total invoice amount": "total_invoice_amount",
            "supplier name": "supplier_name"
        }

        tables = soup.find_all("table", {"width": "100%"})
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                i = 0
                while i < len(cells):
                    cell = cells[i]
                    key_text = cell.get_text(strip=True).lower()
                    mapped_key = key_map.get(key_text)
                    if mapped_key:
                        j = i + 1
                        while j < len(cells):
                            value = cells[j].get_text(strip=True)
                            if value:
                                result[mapped_key] = value
                                break
                            j += 1
                        i = j
                    i += 1
        return result


async def process_invoice_ocr_kra_portal(file_path):
    """Process the invoice using OCR and validate the fields."""
    try:
        # Extract QR codes and data
        qr_extractor = QRCodeExtractor(input_path=file_path)  
        qr_data = qr_extractor.extract_qr_codes()

        if not qr_data:
            return {"message": "No QR code found in the PDF"}

        # If QR code found, scrape the web page using the URL from QR
        extracted_data = []
        for pdf_file, urls in qr_data.items():
            for url in urls:
                print(f"\n🌍 Fetching HTML for URL from {pdf_file}: {url}")
                scraper = WebPageScraper(url)
                html = await scraper.fetch_html()

                if html:
                    # Extract invoice data from HTML
                    parser = KRAInvoiceParser(html)
                    invoice_data = parser.extract_data()
                    extracted_data.append(invoice_data)

        if extracted_data:
            # Convert extracted data to a DataFrame
            df = pd.DataFrame(extracted_data)

            # Save the data into the SQL table kra_portal
            df.to_sql('kra_portal', engine, if_exists='replace', index=False)
            return {"message": "Invoice data successfully processed and saved to SQL."}
        else:
            return {"message": "No invoice data found in the web page."}

    except Exception as e:
        print(f"❌ Invoice processing failed: {e}")
        return {"message": f"Invoice processing failed: {str(e)}"}



