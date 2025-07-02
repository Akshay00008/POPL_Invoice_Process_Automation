import os
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from openai import OpenAI  # Using OpenAI class for initialization
import json
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Retrieve OpenAI API Key from environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")  # Use the key stored in .env

# Check if the API key is loaded correctly
if not openai_api_key:
    raise ValueError("OpenAI API key is not set. Please set it in the .env file.")

# Initialize OpenAI client using the loaded API key
client = OpenAI(api_key=openai_api_key)

# Configure Tesseract path if needed (uncomment and modify if necessary)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def ocr_from_image(image_path):
    """Extract text from an image file using OCR"""
    with Image.open(image_path) as img:
        text = pytesseract.image_to_string(img)
    return text.strip()

def ocr_from_pdf(pdf_path):
    """Extract text from a PDF file using OCR"""
    try:
        pages = convert_from_path(
            pdf_path, 
            dpi=300,
            poppler_path="\home\bramhesh_srivastav\POPL_Invoice_Process_Automation\Release-24.08.0-0\poppler-24.08.0\Library\bin"
        )
    except Exception as e:
        raise RuntimeError(f"PDF conversion failed: {e}") from e
    
    if not pages:
        raise ValueError("PDF file is empty or could not be processed")
    
    return "\n".join(pytesseract.image_to_string(page).strip() for page in pages)

def extract_invoice_data_with_llm(text):
    """Extract structured data from invoice text using LLM"""
    if not text.strip():
        raise ValueError("No text provided for LLM processing")
    
    prompt = f"""
Extract invoice fields from the text below with strict accuracy. Follow these guidelines:
1. Preserve EXACT original formatting including special characters and case sensitivity
2. Handle alternative field name variations (see mappings below)
3. Return JSON with null for missing fields

Field Specifications:
- Invoice Number: Extract exactly as shown (alphanumeric with possible special characters: /-.#)
- Date: Convert to YYYY-MM-DD format
- CUIN: Extract as written (usually alphanumeric)
- Vendor Name: Full legal name
- Vendor Address: Multi-line format if available
- Vendor Contact: Phone/email if available
- PO Number: (aliases: LPO Number,L.P.O. No., PO No., Order Number, Purchase Order)(take only the first 8 numbers not anything else for example :24004078R7 PO number will be 24004078 )
- Delivery Note/Challan Number: Extract with original formatting
- SubTotal: Numeric value only
- Total Amount: Numeric value only  
- Currency: 3-letter code (default to KES if missing)
- Total Tax Amount: Numeric value
- Goods/Services Details: List of objects with:
  - description: Exact item text 
  - quantity: Numeric value (also referred to by aliases such as Quantity, Qty, QTY, QUANTITY). This field accepts values corresponding to any of these aliases and should be interpreted correctly based on the provided input.
  - unit_price: Numeric value (aliases : @ price, @price, Unit Price, unity price, Rate, rate) 
- Tax Details: List of objects with:
  - tax_type: (e.g., VAT, GST, Sales Tax)
  - rate: Percentage (e.g., 16%)
  - amount: Numeric value
- Tax ID: Government-issued tax identifier

Special Handling Instructions:

Invoice Number:
Invoice numbers may contain special characters or alphanumeric codes like "INV-123/AB45". Ensure that all characters in the invoice number are preserved exactly as they appear, including any dashes, slashes, or other symbols.

PO Number:
Purchase order (PO) numbers may be written in various formats, such as "LPO: 2345-XYZ". When processing these, extract only the alphanumeric portion of the PO number after "LPO:". For example, from "LPO: 2345-XYZ", extract "2345-XYZ".

Amounts with Currency Symbols:
When processing amounts with currency symbols like "KES 1,500.00", you should remove the currency symbol and extract only the numeric value. In this case, "KES 1,500.00" should be converted to the value 1500.0. If the amount includes commas, remove them, and ensure the value is in a float format.

Quantity:
The quantity can sometimes be written with a comma or multiple decimal places. Here’s how to handle it:
If the quantity appears as "1,488.00", treat it as 1488.
If the quantity is written as "3.00000", treat it as 3 (ignore extra decimals).
If the quantity is "60.00", treat it as 60.
Essentially, remove any commas and round decimals where applicable, keeping the integer value as the quantity.

Unit Price:
Unit prices can also be written in different formats, such as:
"2,400.00" → This should be treated as 2400.
"8.00000" → This should be treated as 8.
"196.50000" → This should be treated as 196.5.
if none the it should be treated as 0
Remove commas, and convert the value to a float, ensuring only significant digits are included (i.e., no unnecessary decimal places).

Example Format:
{{
  "invoice_number": "INV-2023/ABC#456",
  "po_number": "LPO-789-X2",
  "currency": "KES"
  "cuin" : "KRAMW"
  "sub_total" : 12345
}}

Text Source:
{text[:15000]}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[ 
                {"role": "system", "content": "You are a JSON output machine. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=2000,
        )
        
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError as e:
        raise ValueError("Failed to parse LLM response as JSON") from e
    except Exception as e:
        raise RuntimeError(f"LLM processing failed: {e}") from e

def process_file(filepath):
    """Process a file and return extracted invoice data"""
    if not os.path.exists(filepath):
        print("File not found: {filepath}")
        raise FileNotFoundError(f"File not found: {filepath}")
    
    ext = filepath.lower().split('.')[-1]
    try:
        if ext == 'pdf':
            text = ocr_from_pdf(filepath)
        elif ext in {'png', 'jpg', 'jpeg', 'tiff', 'bmp'}:
            text = ocr_from_image(filepath)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
        
        print(f"Extracted {len(text)} characters from OCR")
        return extract_invoice_data_with_llm(text)
    
    except Exception as e:
        print(f"Error processing {filepath}: {str(e)}")
        raise
