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
            model='gpt-4.1-2025-04-14',
            messages=[{
                "role": "system",
                "content": (
                    "You are an expert invoice extraction assistant. You help extract structured data from invoice images. "
                    "Extract only the specific fields listed below from the invoice image and return the results as a JSON object." 
                    "Do NOT include any comments, preamble, or additional explanation. If a value is missing or not visible, use 'Not provided.' for strings and 0.0 for numbers."
                    "Do not infer or guess. ALL fields must be present in your response. "
                    "Be very careful to preserve numbers, codes, and text exactly as shown - do not add, remove, or alter any characters. "
                    "Follow the extraction rules, supported aliases, and output sample JSON."
                )
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract these fields from the invoice image and return exactly as instructed:"},

                    {"type": "text", "text": "Required fields:"},

                    {"type": "text", "text": "invoice_number: Extract exactly as written, preserving any special characters (e.g., /-.#). Aliases: Invoice Number, Invoice NO."},

                    {"type": "text", "text": "\ndate: Extract in YYYY-MM-DD format. Aliases: Invoice Date, DATE, DATED. If not found, return 'Not provided.'"},

                    {"type": "text", "text": "\ncuin: As written, usually alphanumeric or under/near QR code. Aliases: @ KRA Inv. No., CUIN, CU INVOICE NUMBER, KRA Receipt NO, Number beneath QR code starting with NO"},

                    {"type": "text", "text": "\nvendor_name: Extract vendor name from header, under/near logo. MUST NOT be any variant of 'PWANI' (e.g., PWANI, PWANI OIL PRODUCTS LTD, etc.)"
                                                },

                    {"type": "text", "text": "\nvendor_address: Extract as is."},

                    {"type": "text", "text": "Vendor Contact (Phone/Email) (Extract the vendor name from the invoice, which is located in the header of the document, specifically under or near the company logo.)"},

                    {"type": "text", "text": "PO Number (first 8 alphanumeric digits), (aliases: LPO Number,L.P.O. No., PO No., Order Number, Purchase Order)(take only the first 8 numbers not anything else for example :24004078R7 PO number will be 24004078 )"},


                    {"type": "text", "text": "Delivery Note/Challan Number"},

                    {"type": "text", "text": "SubTotal (numeric value), (aliases : sub total , SUB TOTAL, Amount,Total Net Value, @price, )"},

                    {"type": "text", "text": "Total Amount (numeric value),(aliases  : TOTAL, TOTAL(Incl), TOTAL AMOUNT, Taxable amount In KSH) "},

                    {"type": "text", "text": "Currency (3-letter code, default KES if missing)"},

                    {"type": "text", "text": "Total Tax Amount (numeric value), VAT Total, Total VAT Amount in KSH"},

                    {"type": "text", "text": "(Goods/Services Details: "
                    "goods_services_details: List each item with:"
                    "\n  - description: Exact item description as on invoice; do not alter or skip characters."
                    "\n  - quantity: Numeric, including decimals (e.g., 464.00). Do not include packaging info. Aliases: Quantity, Qty, QTY, QUANTITY."
                    "\n  - unit_price: Numeric. Aliases: @ price, @price, Unit Price, unit/price, Unity Price, Rate, rate."
                    },

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
