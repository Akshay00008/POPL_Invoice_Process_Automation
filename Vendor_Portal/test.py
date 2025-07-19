import os
import cv2
import numpy as np
import asyncio
from pdf2image import convert_from_path
from pyzbar.pyzbar import decode
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import nest_asyncio
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

nest_asyncio.apply()

# Load DB credentials
load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME")

# SQLAlchemy engine
engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# ---------- DB Save Function ----------
def save_invoice_data_to_db(invoice_data):
    try:
        query = text('''
            INSERT INTO kra_portal (
                control_unit_invoice_number, invoice_date, total_taxable_amount,
                total_tax_amount, total_invoice_amount, supplier_name, invoice_number
            )
            VALUES (
                :control_unit_invoice_number, :invoice_date, :total_taxable_amount,
                :total_tax_amount, :total_invoice_amount, :supplier_name, :invoice_number
            )
        ''')
        with engine.begin() as conn:
            conn.execute(query, invoice_data)
        print("✅ Data saved to database.")
    except Exception as e:
        print(f"❌ Error saving data: {e}")

# ---------- QR Code Extractor ----------
class QRCodeExtractor:
    def __init__(self, input_path, dpi_list=None):
        self.input_path = input_path
        self.dpi_list = dpi_list or [400, 500, 600, 700, 800]
        self.pdf_list = self._get_pdf_list()

    def _get_pdf_list(self):
        if os.path.isfile(self.input_path) and self.input_path.lower().endswith('.pdf'):
            return [self.input_path]
        elif os.path.isdir(self.input_path):
            return [os.path.join(self.input_path, f) for f in os.listdir(self.input_path) if f.lower().endswith('.pdf')]
        else:
            raise ValueError("❌ Input path must be a .pdf file or a folder containing .pdf files.")

    def extract_qr_codes(self):
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

# ---------- Web Page Scraper ----------
class WebPageScraper:
    def __init__(self, url):
        self.url = url

    async def fetch_html(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(self.url, timeout=20000)
            await page.wait_for_selector("body")
            html = await page.content()
            await browser.close()
            return html

# ---------- KRA Invoice Parser ----------
class KRAInvoiceParser:
    def __init__(self, html):
        self.html = html

    def extract_data(self):
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

# ---------- Main Async Handler ----------
async def process_invoice_ocr_kra_portal(path):
    qr_extractor = QRCodeExtractor(input_path=path)  
    qr_data = qr_extractor.extract_qr_codes()
    invoice_data_updated = {}

    for pdf_file, urls in qr_data.items():
        for url in urls:
            print(f"\n🌍 Fetching HTML for URL from {pdf_file}: {url}")
            scraper = WebPageScraper(url)
            try:
                html = await scraper.fetch_html()
            except Exception as e:
                print(f"❌ Failed to fetch HTML: {e}")
                continue

            parser = KRAInvoiceParser(html)
            invoice_data = parser.extract_data()

            save_invoice_data_to_db(invoice_data)  # Save to DB

            invoice_data_updated[pdf_file] = {
                "invoice_data": invoice_data,
                "urls": urls
            }

    return invoice_data_updated

# ---------- Optional Runner ----------
if __name__ == "__main__":
    path_to_pdf_or_folder = "path/to/your/pdf_or_folder"
    asyncio.run(process_invoice_ocr_kra_portal(path_to_pdf_or_folder))
