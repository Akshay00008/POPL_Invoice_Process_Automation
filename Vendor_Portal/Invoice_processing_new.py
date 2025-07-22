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
                   {'''Extract invoice fields from the text below with strict accuracy. Follow these guidelines:
1. Preserve EXACT original formatting including special characters and case sensitivity
2. Handle alternative field name variations (see mappings below)
3. Return JSON with null for missing fields

Field Specifications:
- Invoice Number: Extract exactly as shown (alphanumeric with possible special characters: /-.#) (aliases : Invoice Number, Invoice NO.) Please extract correct value donot get confused between 2,5,6,9,3 and 4 ,1
- Date: Convert to YYYY-MM-DD format (aliases : Invoice Date , Invoice date, DATE, date, DATED,dated),
- CUIN: Extract as written (usually alphanumeric) (aliases : @ KRA Inv. No. , CUIN, CU INVOICE NUMBER, CU INVOICE N, KRA Receipt NO, Number  beneath the QR Code starting with NO) 
- Vendor Name: Full legal name (Be specific between L and l dont take it as i ,) you are reading all pack as salipack or ali pack please be correct.
- Vendor Address: Multi-line format if available
- Vendor Contact: Phone/email if available
- PO Number: (aliases: LPO Number,L.P.O. No., PO No., Order Number, Purchase Order)(take only the first 8 numbers not anything else for example :24004078R7 PO number will be 24004078 )
- Delivery Note/Challan Number: Extract with original formatting
- SubTotal: Numeric value only (aliases : sub total , SUB TOTAL, Amount,Total Net Value, @price, )
- Total Amount: Numeric value only  (aliases  : TOTAL, TOTAL(Incl), TOTAL AMOUNT,)
- Currency: 3-letter code (default to KES if missing)
- Total Tax Amount: Numeric value
- Goods/Services Details: List of objects with:
  - description: Exact item text 
  - quantity: Numeric value (also referred to by aliases such as Quantity, Qty, QTY, QUANTITY). This field accepts values corresponding to any of these aliases and should be interpreted correctly based on the provided input.
  - unit_price: Numeric value (aliases : @ price, @price, Unit Price, unity price, Rate, rate) 
- Tax Details: List of objects with:
  - tax_type: (e.g., VAT, GST, Sales Tax)
  - rate: Percentage (e.g., 16%)
  - amount: Numeric VAlue only (aliases : VAT, VAT AMOUNT, V.A.T,VALUE ADDED TAX, VAT@, OUTPUT VAT)
- Tax ID: Government-issued tax identifier
- vat pin: PIN on invoice

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
}}'''}
                    ,
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
