import base64
import time
import requests
from openai import OpenAI
import os
from pdf2image import convert_from_path
import json  # Import the json module for parsing

# Load the OpenAI API key from environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")

# Helper function to log time
def log_time(start_time, process_name):
    elapsed_time = time.time() - start_time
    print(f"{process_name} took {elapsed_time:.2f} seconds")

# Function to convert PDF to image
def convert_pdf_to_image(pdf_path):
    # Convert the PDF to images
    images = convert_from_path(pdf_path)
    # Save the first page as an image (you can modify this if needed to handle more pages)
    image_path = "converted_page.jpg"
    images[0].save(image_path, "JPEG")
    return image_path

# Function to send invoice image to LLM for extraction
def send_to_llm_single_page(pdf_path):
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
            model='gpt-4.1-mini-2025-04-14',
            messages=[{
                "role": "system",
                "content": (
                    "You are an invoice extraction assistant. Extract the requested fields from the invoice image "
                    "and return the output ONLY in the exact following JSON structure. Do not add any commentary or explanation. "
                    "All keys must be present, even if values are 'Not provided.' or 'Not explicitly listed.'"
                )
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract the following details from the invoice image."},
                    {"type": "text", "text": "Required fields:"},
                    {"type": "text", "text": "Invoice Number (Extract exactly as shown (alphanumeric with possible special characters: /-.#) (aliases : Invoice Number, Invoice NO.))"},
                    {"type": "text", "text": "date (format YYYY-MM-DD), (aliases : Invoice Date , Invoice date, DATE, date, DATED,dated)"},
                    {"type": "text", "text": "CUIN (Extract as written (usually alphanumeric) (aliases : @ KRA Inv. No. , CUIN, CU INVOICE NUMBER, CU INVOICE N, KRA Receipt NO, Number  beneath the QR Code starting with NO))"},
                    {"type": "text", "text": "Vendor Name (This will never be PWANI or PWANI OIL PRODUCTS LTD or PWANI LTD or any other information related to PWANI details like address, Contact) (Extract the vendor name from the invoice, which is located in the header of the document, specifically under or near the company logo.)"},
                    {"type": "text", "text": "Vendor Address"},
                    {"type": "text", "text": "Vendor Contact (Phone/Email) (Extract the vendor name from the invoice, which is located in the header of the document, specifically under or near the company logo.)"},
                    {"type": "text", "text": "PO Number (first 8 alphanumeric digits), (aliases: LPO Number,L.P.O. No., PO No., Order Number, Purchase Order)(take only the first 8 numbers not anything else for example :24004078R7 PO number will be 24004078 )"},
                    {"type": "text", "text": "Delivery Note/Challan Number"},
                    {"type": "text", "text": "SubTotal (numeric value), (aliases : sub total , SUB TOTAL, Amount,Total Net Value, @price, )"},
                    {"type": "text", "text": "Total Amount (numeric value),(aliases  : TOTAL, TOTAL(Incl), TOTAL AMOUNT, Taxable amount In KSH) "},
                    {"type": "text", "text": "Currency (3-letter code, default KES if missing)"},
                    {"type": "text", "text": "Total Tax Amount (numeric value), VAT Total, Total VAT Amount in KSH"},
                    {"type": "text", "text": "Goods/Services Details "
                    "(Goods/Services Details: description: Exact item text as it appears. Ensure the correct extraction of the item description without altering or skipping any characters."
                    "quantity: Numeric value extracted from any of the following aliases: 'Quantity', 'Qty', 'QTY', 'QUANTITY'. This value can include decimals (e.g., 464.00 you are extracting 2990.3 as 2909  resolve this) and should not be confused with unit price. Ensure that the correct number is extracted from the column names or labels provided in aliases, and make sure it corresponds accurately to the description. Avoid interpreting decimal values as unit prices. "
                    "Unit Price: Numeric value extracted from any of the following aliases: '@ price', '@price', 'Unit Price', 'unit/price', 'UNIT/PRICE', 'Unit/Price', 'Unity Price', 'Rate', 'rate'. Ensure that the extracted value represents the actual unit price without any alterations. Pay particular attention to digit accuracy, especially when characters resemble each other (e.g., '4' vs. '5', '6' vs. '9', '0' vs. '9')."
                    "Avoid confusion where similar-looking characters could lead to misinterpretation. For instance:"
                    "'475' should not be mistaken for '550'."
                    "'6' must not be confused with '5'."
                    "'9' should not be read as '0'."
                    "'4' should not be interpreted as '1'."
                    "Ensure the extracted value is precise, reflecting the true unit price as written.."},
                    {"type": "text", "text": "Tax Details (List of objects with: - tax_type: (e.g., VAT, GST, Sales Tax Total VAT Amount in KSH) - rate: Percentage (e.g., 16%)- amount: Numeric VAlue only (aliases : VAT, VAT AMOUNT, V.A.T,VALUE ADDED TAX, VAT@, OUTPUT VAT))"},
                    {"type": "text", "text": "Tax ID"},
                    {"type": "text", "text": "VAT PIN"},
                    {"type": "text", "text": "Return the response exactly in this JSON format:"},
                    {"type": "text", "text": '''
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
                    '''},
                       {
                "type": "text", "text": "Important Instructions for Number Extraction:"
            },
            {
               "type": "text", "text": "Donot use comma  , inplace of decimal . when extracting numbers" 
            },
            {
                "type": "text", "text": "1. Ensure that numbers are extracted as they are written. Do not confuse similar-looking characters. For example: '6' should not be interpreted as '5', '9' should not be interpreted as '0', '4' should not be interpreted as '1', etc."
            },
            {
                "type": "text", "text": "2. Do not replace or misinterpret alphanumeric characters. Ensure that numbers such as '24004078' are extracted as is, without modifying or truncating them."
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

        # Check for valid response
        if not response or not response.choices or not response.choices[0].message.content:
            return {"error": "No content returned"}

        # Parse the response into a dictionary
        content = response.choices[0].message.content.strip()

        # Fix JSON backslash error
        safe_json_string = content.replace('\\', '\\\\')

        return json.loads(safe_json_string)

    except Exception as e:
        return {"error": str(e)}

# Example usage
# pdf_path = "path_to_pdf.pdf"
# extracted_data = send_to_llm_single_page(pdf_path)
# print(extracted_data)
