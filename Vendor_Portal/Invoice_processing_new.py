import base64
import time
import os
import json
from dotenv import load_dotenv
from pdf2image import convert_from_path
from openai import OpenAI  # Import OpenAI client

# Load environment variables
load_dotenv()

# Load OpenAI API key
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OpenAI API key is not set. Please set it in the .env file.")

# Initialize OpenAI client once
client = OpenAI(api_key=openai_api_key)

# Log duration helper
def log_time(start_time, process_name):
    elapsed_time = time.time() - start_time
    print(f"{process_name} took {elapsed_time:.2f} seconds")

# Convert first page of PDF to image
def convert_pdf_to_image(pdf_path):
    images = convert_from_path(pdf_path)
    image_path = "converted_page.jpg"
    images[0].save(image_path, "JPEG")
    return image_path

# Function to send invoice to LLM
def send_to_llm_single_page(pdf_path):
    try:
        # Convert PDF to image if needed
        if pdf_path.lower().endswith(".pdf"):
            image_path = convert_pdf_to_image(pdf_path)
        else:
            image_path = pdf_path

        # Convert image to base64
        with open(image_path, "rb") as image_file:
            start_time = time.time()
            image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
            log_time(start_time, "Image encoding")

        # Prepare the chat message with the image
        messages = [
            {
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
                    {"type": "text", "text": "Invoice Number (may include special characters like /-.#)"},
                    {"type": "text", "text": "Invoice Date (format YYYY-MM-DD)"},
                    {"type": "text", "text": "CUIN (Invoice Number)"},
                    {"type": "text", "text": "Vendor Name"},
                    {"type": "text", "text": "Vendor Address"},
                    {"type": "text", "text": "Vendor Contact (Phone/Email)"},
                    {"type": "text", "text": "PO Number (first 8 alphanumeric digits)"},
                    {"type": "text", "text": "Delivery Note/Challan Number"},
                    {"type": "text", "text": "SubTotal (numeric value)"},
                    {"type": "text", "text": "Total Amount (numeric value)"},
                    {"type": "text", "text": "Currency (3-letter code, default KES if missing)"},
                    {"type": "text", "text": "Total Tax Amount (numeric value)"},
                    {"type": "text", "text": "Goods/Services Details (list with description, quantity, unit_price)"},
                    {"type": "text", "text": "Tax Details (list with tax_type, rate, amount)"},
                    {"type": "text", "text": "Tax ID"},
                    {"type": "text", "text": "VAT PIN"},
                    {"type": "text", "text": "Return the response exactly in this JSON format:"},
                    {"type": "text", "text": '''
{
    "invoice_number": "Not provided.",
    "invoice_date": "Not provided.",
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
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ]

        # Call OpenAI API
        start_time = time.time()
        response = client.chat.completions.create(
            model="gpt-4.1-mini-2025-04-14",
            messages=messages,
            max_tokens=1500
        )
        log_time(start_time, "OpenAI API call")

        # Check and parse response
        if not response or not response.choices or not response.choices[0].message.content:
            return {"error": "No content returned from OpenAI"}

        content = response.choices[0].message.content.strip()
        return json.loads(content)

    except Exception as e:
        return {"error": str(e)}

# Example usage:
# result = send_to_llm_single_page("path_to_invoice.pdf")
# print(result)
