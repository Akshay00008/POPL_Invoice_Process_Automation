import cv2
from pdf2image import convert_from_path
import numpy as np
import os

# from pyzbar.pyzbar import decode
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import nest_asyncio
import cv2
import pytesseract
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from skimage.filters import threshold_sauvola
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


class QRCodeExtractor:
    def __init__(self, input_path, dpi_list=None):
        self.input_path = input_path
        self.dpi_list = dpi_list or [400, 500, 600, 700, 800]
        self.pdf_list = self._get_pdf_list()

    def _get_pdf_list(self):
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

class QRCodePDFProcessor:

    def __init__(self, input_path, dpi_list=None):
        self.input_path = input_path
        self.dpi_list = dpi_list if dpi_list else [400, 500, 600,700]
        self.qr_detector = cv2.QRCodeDetector()
        self.results = {}  # NEW: dictionary to store multiple QR codes per file
        if os.path.isfile(self.input_path) and self.input_path.lower().endswith('.pdf'):
            self.pdf_list = [self.input_path]
        elif os.path.isdir(self.input_path):
            self.pdf_list = [
                os.path.join(self.input_path, f)
                for f in os.listdir(self.input_path)
                if f.lower().endswith('.pdf')
            ]
        else:
            raise ValueError("❌ Input path must be a .pdf file or folder.")

    @staticmethod
    def rotate_image(img, angle):
        (h, w) = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        cos, sin = np.abs(M[0, 0]), np.abs(M[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))
        M[0, 2] += (new_w / 2) - center[0]
        M[1, 2] += (new_h / 2) - center[1]
        return cv2.warpAffine(img, M, (new_w, new_h))

    def detect_qr(self, img):
        data, bbox, _ = self.qr_detector.detectAndDecode(img)
        if data:
            return data
        qr_codes = decode(img)
        if qr_codes:
            return qr_codes[0].data.decode('utf-8')
        return None

    def process(self):
        for pdf_path in self.pdf_list:
            print(f"\n📄 Processing PDF: {os.path.basename(pdf_path)}")
            found = False

            for dpi in self.dpi_list:
                print(f"   🔍 Trying DPI: {dpi}")
                try:
                    image = convert_from_path(pdf_path, dpi=dpi)[0]
                except Exception as e:
                    print(f"   ❌ Failed at {dpi} DPI: {e}")
                    continue

                img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                # Remove text
                thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                               cv2.THRESH_BINARY_INV, 15, 10)
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
                dilated = cv2.dilate(thresh, kernel, iterations=1)
                contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                mask_img = img.copy()
                for cnt in contours:
                    x, y, w, h = cv2.boundingRect(cnt)
                    if 20 < w < 700 and 10 < h < 200:
                        cv2.rectangle(mask_img, (x, y), (x + w, y + h), (255, 255, 255), -1)

                # Thresholding
                gray_masked = cv2.cvtColor(mask_img, cv2.COLOR_BGR2GRAY)
                clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
                clahe_applied = clahe.apply(gray_masked)
                sauvola_thresh = threshold_sauvola(clahe_applied, window_size=71)
                binary = (clahe_applied > sauvola_thresh).astype(np.uint8) * 255
                blurred = cv2.GaussianBlur(binary, (7, 7), 0)

                # Full image QR detection
                qr_data = self.detect_qr(blurred)
                if qr_data:
                    print(f"   ✅ QR detected in full image: {qr_data}")
                    pdf_key = os.path.basename(pdf_path)
                    if pdf_key not in self.results:
                        self.results[pdf_key] = []
                    self.results[pdf_key].append(qr_data)
                    found = True
                    break

                # Lower-left zoomed region
                print("   🧭 Trying lower-left region...")
                h, w = blurred.shape[:2]
                roi_crop = blurred[h - h // 4:h, 0:w // 4]
                zoomed = cv2.resize(roi_crop, None, fx=1.0, fy=1.0, interpolation=cv2.INTER_CUBIC)
                unsharp = cv2.addWeighted(zoomed, 1.5, cv2.GaussianBlur(zoomed, (7, 7), 0), -0.5, 0)

                qr_data = self.detect_qr(unsharp)
                if qr_data:
                    print(f"   ✅ QR detected in lower-left zoomed: {qr_data}")
                    pdf_key = os.path.basename(pdf_path)
                    if pdf_key not in self.results:
                        self.results[pdf_key] = []
                    self.results[pdf_key].append(qr_data)
                    found = True
                    break

                # Brute force
                print("   🔄 Trying brute-force rotation & scale...")
                angles = list(range(0, 120, 15))
                scales = [1.0,1.5, 2.0, 2.5, 3.0,3.5]
                interpolation=cv2.INTER_CUBIC

                for angle in angles:
                    rotated = self.rotate_image(unsharp, angle)
                    for scale in scales:
                        resized = cv2.resize(rotated, None, fx=scale, fy=scale, interpolation=interpolation)
                        qr_data = self.detect_qr(resized)
                        if qr_data:
                            print(f"   ✅ Brute Force Detected - angle={angle}°, scale={scale}: {qr_data}")
                            pdf_key = os.path.basename(pdf_path)
                            if pdf_key not in self.results:
                                self.results[pdf_key] = []
                            self.results[pdf_key].append(qr_data)
                            found = True
                            break
                    if found: break

                if found:
                    break

            if not found:
                print(f"❌ No QR code found in: {os.path.basename(pdf_path)}")

        if not self.results:
            print("\n🚫 No QR code found in any PDF.")

        return self.results  # ⬅️ Return extracted QR data


def detect_sanpac_by_ocr(pdf_path, dpi=500):
    try:
        image = convert_from_path(pdf_path, dpi=dpi)[0]
        gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        text = pytesseract.image_to_string(gray)
        lines = text.splitlines()

        for line in lines:
            if "sanpac" in line.lower():
                return True
    except Exception as e:
        print(f"⚠️ OCR detection failed for {pdf_path}: {e}")
    return False
def extract_all_qr_codes(path):
    results = {}

    if os.path.isfile(path) and path.lower().endswith('.pdf'):
        pdf_list = [path]
    elif os.path.isdir(path):
        pdf_list = [
            os.path.join(path, f)
            for f in os.listdir(path)
            if f.lower().endswith('.pdf')
        ]
    else:
        raise ValueError("❌ Input path must be a .pdf file or folder.")

    for pdf in pdf_list:
        print(f"\n🔎 OCR Scanning first page of: {os.path.basename(pdf)}")
        is_sanpac = detect_sanpac_by_ocr(pdf)

        qr_data = {}
        # Try primary method based on OCR detection
        if is_sanpac:
            print(f"🔧 Detected 'SANPAC' by OCR → Using QRCodePDFProcessor for: {os.path.basename(pdf)}")
            qr_extractor = QRCodePDFProcessor(input_path=pdf)
            qr_data = qr_extractor.process()
            
            if not qr_data:  # Fallback to alternate method
                print(f"⚠️ QRCodePDFProcessor failed. Trying fallback QRCodeExtractor...")
                fallback_extractor = QRCodeExtractor(input_path=pdf)
                qr_data = fallback_extractor.extract_qr_codes()

        else:
            print(f"🔧 Did not detect 'SANPAC' → Using QRCodeExtractor for: {os.path.basename(pdf)}")
            qr_extractor = QRCodeExtractor(input_path=pdf)
            qr_data = qr_extractor.extract_qr_codes()

            if not qr_data:  # Fallback to alternate method
                print(f"⚠️ QRCodeExtractor failed. Trying fallback QRCodePDFProcessor...")
                fallback_extractor = QRCodePDFProcessor(input_path=pdf)
                qr_data = fallback_extractor.process()

        if qr_data:
            results.update(qr_data)
        else:
            print(f"❌ No QR code found in: {os.path.basename(pdf)} after both attempts.")

    return results


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


async def process_invoice_ocr_kra_portal(path):
    # 📥 Step 1: Extract QR codes from PDFs
    qr_data=extract_all_qr_codes(path)
   
    invoice_data_updated={}
    # 🌐 Step 2: If any QR found, fetch the URL
    for pdf_file, urls in qr_data.items():
        for url in urls:
            print(f"\n🌍 Fetching HTML for URL from {pdf_file}: {url}")
            scraper = WebPageScraper(url)
            try:
                html = await scraper.fetch_html()
            except Exception as e:
                print(f"❌ Failed to fetch HTML: {e}")
                continue

            # 📊 Step 3: Extract invoice details from HTML
            parser = KRAInvoiceParser(html)
            invoice_data = parser.extract_data()
            
            save_invoice_data_to_db(invoice_data)
            
            invoice_data_updated[pdf_file] = {
            "invoice_data": invoice_data,
            "urls": urls
        }

            # print("✅ Extracted Invoice Data:")
            # for key, value in invoice_data.items():
            #     print(f"{key}: {value}")
    return invoice_data_updated

# if __name__ == "__main__":
#     asyncio.run(main_qr("INVOICES/SANPAC"))
