import base64
import time
import os
import json
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
from openai import OpenAI

# Load the OpenAI API key from environment variables (make sure you replace this with your actual API key)
openai_api_key = os.getenv("OPENAI_API_KEY")

# Alternatively, set the API key here if you're not using environment variables (use cautiously)
openai_api_key = "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"

def ocr_from_image(image_path):
    """Extract text from an image file using OCR"""
    with Image.open(image_path) as img:
        text = pytesseract.image_to_string(img)
    return text.strip()

def ocr_from_pdf(pdf_path):
    """Extract text from a PDF file using OCR"""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    try:
        pages = convert_from_path(
            pdf_path, 
            dpi=300,
            poppler_path=r"C:\Users\hp\Downloads\Release-24.08.0-0\poppler-24.08.0\Library\bin"
            # poppler_path=r"C:\path\to\poppler\bin"  # Adjust the path for your poppler installation
        )
    except Exception as e:
        raise RuntimeError(f"PDF conversion failed: {e}") from e

    if not pages:
        raise ValueError("PDF file is empty or could not be processed")
    
    return "\n".join(pytesseract.image_to_string(page).strip() for page in pages)

# Helper function to log time
def log_time(start_time, process_name):
    elapsed_time = time.time() - start_time
    print(f"{process_name} took {elapsed_time:.2f} seconds")

# Function to convert PDF to image
def convert_pdf_to_image(pdf_path):
    """Convert PDF to an image"""
    images = convert_from_path(pdf_path)
    image_path = "converted_page.jpg"
    images[0].save(image_path, "JPEG")
    return image_path

# Function to send invoice image to LLM for extraction
def send_to_llm_single_page(pdf_path, text):
    try:
        # If the file is a PDF, convert it to an image first
        if pdf_path.lower().endswith(".pdf"):
            image_path = convert_pdf_to_image(pdf_path)
        else:
            image_path = pdf_path  # If it's already an image, use it as is

        # Load the image and convert it to base64
        with open(image_path, "rb") as image_file:
            start_time = time.time()
            image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
            log_time(start_time, "image64")

        # Initialize OpenAI client
        client = OpenAI(api_key=openai_api_key)

        # Make API call to OpenAI for extraction
        response = client.chat.completions.create(
            model='gpt-4.1-2025-04-14',
            messages=[{
                "role": "system",
                "content": (
                    "You are an expert invoice extraction assistant. Your task is to extract specific fields from invoice images accurately. "
                    "Only extract the required fields listed below and return them in a structured JSON format. Do NOT include any comments, preambles, or additional explanation. "
                    "If a field is missing or not visible, use 'Not provided' for strings and 0.0 for numbers. Be very careful to preserve numbers, codes, and text exactly as they appear without alteration. "
                    "Your response must be fully structured and must adhere to the extraction rules for the following details."
                )
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract the following fields from the invoice image:"},
                    {"type": "text", "text": "Invoice Number (Extract exactly as shown (alphanumeric with possible special characters: /-.#) (aliases : Invoice Number, Invoice NO.)), Invoice numbers may contain special characters or alphanumeric codes like 'INV-123/AB45'. Ensure that all characters in the invoice number are preserved exactly as they appear, including any dashes, slashes, or other symbols." ("Seal No. is not invoice number")},
                    {"type": "text", "text": "Date (Format: YYYY-MM-DD)"},
                    {"type": "text", "text": "CUIN (Extract as written (usually alphanumeric) (aliases : @ KRA Inv. No. , CUIN, CU INVOICE NUMBER, CU INVOICE N, KRA Receipt NO, Number  beneath the QR Code starting with NO))"},
                    {"type": "text", "text": "Vendor Name (This will never be PWANI or PWANI OIL PRODUCTS LTD or PWANI LTD or any other information related to PWANI details like address, Contact) (Extract the vendor name from the invoice, which is located in the header of the document, specifically under or near the company logo.)"},
                    {"type": "text", "text": "Vendor Address"},
                    {"type": "text", "text": "Vendor Contact (Phone/Email) (Extract the vendor name from the invoice, which is located in the header of the document, specifically under or near the company logo.)"},
                    {"type": "text", "text": "PO Number (first 8 alphanumeric digits), (aliases: LPO Number,L.P.O. No., PO No., Order Number, Purchase Order)(take only the first 8 numbers not anything else for example :24004078R7 PO number will be 24004078 )"},
                    {"type": "text", "text": "Delivery Note/Challan Number"},
                    {"type": "text", "text": "SubTotal (Numeric value, aliases: SUBTOTAL, Amount, Total Net Value)"},
                    {"type": "text", "text": "Total Amount (Numeric value, aliases: TOTAL, TOTAL AMOUNT, Taxable Amount)"},
                    {"type": "text", "text": "Currency (3-letter code, default KES)"},
                    {"type": "text", "text": "Total Tax Amount (Numeric value, aliases: VAT Total, Total VAT Amount)"},
                    {"type": "text", "text": "Goods/Services Details: Extract item description, quantity, and unit price accurately. Ensure correct formatting of quantities and unit prices (handle decimals properly)."},
                    {"type": "text", "text": "Tax Details (List of objects with tax_type, rate, amount for VAT, GST, Sales Tax)"},
                    {"type": "text", "text": "Tax ID"},
                    {"type": "text", "text": "VAT PIN"},
                    {"type": "text", "text": "Return the extracted data in the following JSON format:"},
                    {
                        "type": "text", 
                        "text": '''
                        {
                            "invoice_number": "Not provided.",
                            "date": "Not provided.",
                            "cuin": "Not provided.",
                            "vendor_name": "Not provided.",
                            "vendor_address": "Not provided.",
                            "vendor_contact": "Not provided.",
                            "po_number": "Not provided.",
                            "delivery_note_number": "Not provided.",
                            "sub_total": 0.0,
                            "total_amount": 0.0,
                            "currency": "KES",
                            "total_tax_amount": 0.0,
                            "goods_services_details": [],
                            "tax_details": [],
                            "tax_id": "Not provided.",
                            "vat_pin": "Not provided."
                        }
                        '''
                    },
                    {"type": "text", "text": "Important Notes for Accurate Extraction:"},
                    {"type": "text", "text": "1. Do not replace commas with decimals when extracting numbers."},
                    {"type": "text", "text": "2. Ensure that numbers are extracted accurately, especially similar-looking digits (e.g., '6' vs '5', '9' vs '0')."},
                    {"type": "text", "text": "3. Always capture alphanumeric characters exactly as they appear on the invoice."},
                    {"type": "text", "text": "4. **Do not confuse quantity with packaging. Any quantity like '240x25 pcs' refers to packaging, not the actual quantity. Quantities will be numeric values like 460.00 or 4639.00 or 4,3000.**"},
                    
                    {
                        "type": "text", "text": f"Extract data based on the following OCR text result from pytesseract:\n{text}"
                    },

                    # Comparison and best result combining logic:
                    {
                        "type": "text", "text": """
                            Now, compare the OCR results provided by pytesseract with the result that you extract from the image using your model. 
                            Select the best possible values from both the results, ensuring that numbers, text, and fields are accurate.
                            The goal is to combine the most accurate results from both the OCR data and your own extraction.
                            Please ensure no incorrect data is included and no data is omitted. You should select the better result from the OCR and your extraction method.
                        """
                    },

                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }]

        )

        # Log time taken for OpenAI request
        log_time(start_time, "openai")

        print (response)

        # Check for valid response
        if not response or not response.choices or not response.choices[0].message.content:
            return {"error": "No content returned"}

        # Parse the response into a string, replacing single quotes with double quotes for JSON
        content = response.choices[0].message.content.strip()

        # Replace single quotes with double quotes if necessary for proper JSON formatting
        safe_json_string = content.replace("'", '"')

        # Try parsing the cleaned string as JSON
        try:
            return json.loads(safe_json_string)
        except json.JSONDecodeError as e:
            return {"error": f"JSON parsing error: {str(e)}"}

    except Exception as e:
        return {"error": str(e)}

def process_file(filepath):
    """Process a file and return extracted invoice data"""
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
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

        return send_to_llm_single_page(filepath, text)

    except Exception as e:
        print(f"Error processing {filepath}: {str(e)}")
        raise

# Example usage
# pdf_path = "path_to_pdf.pdf"
# extracted_data = process_file(pdf_path)
# print(extracted_data)
