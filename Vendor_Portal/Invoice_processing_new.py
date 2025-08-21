import base64
import time
import os
import json
import re
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
from openai import OpenAI

# Set your OpenAI API key
openai_api_key = os.getenv("OPENAI_API_KEY")
# Alternatively, hardcode it (use with caution)

# Clean malformed JSON returned by OpenAI
def clean_openai_json(raw_text):
    try:
        # Remove commas in numbers: "sub_total": 457,424.318 → 457424.318
        def remove_commas_in_numbers(match):
            return match.group(0).replace(',', '')

        raw_text = re.sub(
            r'(?<=":\s)(\d{1,3}(?:,\d{3})+(?:\.\d+)?)(?=[,\n\r}])',
            remove_commas_in_numbers,
            raw_text
        )

        # Replace single quotes with double quotes
        raw_text = raw_text.replace("'", '"')

        # Remove trailing commas before closing } or ]
        raw_text = re.sub(r',(\s*[}\]])', r'\1', raw_text)

        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        return {"error": f"JSON parsing error: {str(e)}", "raw_text": raw_text}
    except Exception as e:
        return {"error": f"Unexpected parsing error: {str(e)}", "raw_text": raw_text}

def ocr_from_image(image_path):
    with Image.open(image_path) as img:
        return pytesseract.image_to_string(img).strip()

def ocr_from_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    try:
        pages = convert_from_path(
            pdf_path,
            dpi=300,
            # poppler_path=r"C:\Users\hp\Downloads\Release-24.08.0-0\poppler-24.08.0\Library\bin"
            poppler_path=r"/usr/bin" 
        )
    except Exception as e:
        raise RuntimeError(f"PDF conversion failed: {e}") from e

    if not pages:
        raise ValueError("PDF file is empty or could not be processed")
    
    return "\n".join(pytesseract.image_to_string(page).strip() for page in pages)

def log_time(start_time, process_name):
    elapsed_time = time.time() - start_time
    print(f"{process_name} took {elapsed_time:.2f} seconds")

def convert_pdf_to_image(pdf_path):
    images = convert_from_path(pdf_path)
    image_path = "converted_page.jpg"
    images[0].save(image_path, "JPEG")
    return image_path

def send_to_llm_single_page(pdf_path, text):
    try:
        if pdf_path.lower().endswith(".pdf"):
            image_path = convert_pdf_to_image(pdf_path)
        else:
            image_path = pdf_path

        with open(image_path, "rb") as image_file:
            start_time = time.time()
            image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
            log_time(start_time, "image64")

        client = OpenAI(api_key=openai_api_key)

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
                    {"type": "text", "text": "Invoice Number (Extract exactly as shown donot interpret (MAY BE alphanumeric with possible special characters: /-.#) (only extract from these aliases for Invoice Number : Invoice Number, Invoice NO., INVOICE NO., INVOICE NO.)), Invoice numbers may contain special characters or alphanumeric codes like 'INV-123/AB45'. Ensure that all characters in the invoice number are preserved exactly as they appear, including any dashes, slashes, or other symbols)"
                    "For Mega Pack invoices take Invoice Number from below the LOGO there is Vendor Address Below vendor address there is a two cross two table and in left column name Invoice number is there and has its value just beside it in right (This is Only for Mega Pack)example  INVOICE NO. 68294 on the PDF only take the number 68294 , INVOICE NO. 68585 on the PDF only take the number 68585 , INVOICE NO. 68135 on the PDF only take the number 68135"},
                    {"type": "text", "text": "Date (Format: YYYY-MM-DD)"},
                    {"type": "text", "text": "CUIN (Extract as written (usually alphanumeric) (aliases : @ KRA Inv. No. , CUIN, CU INVOICE NUMBER, CU INVOICE N, KRA Receipt NO, Number  beneath the QR Code starting with NO))"},
                    {"type": "text", "text": "Vendor Name (This will never be PWANI or PWANI OIL PRODUCTS LTD or PWANI LTD or any other information related to PWANI details like address, Contact) (Extract the vendor name from the invoice, which is located in the header of the document, specifically under or near the company logo.)"},
                    {"type": "text", "text": "Vendor Address"},
                    {"type": "text", "text": "Vendor Contact (Phone/Email) (Extract the vendor name from the invoice, which is located in the header of the document, specifically under or near the company logo.)"},
                    {"type": "text", "text": "PO Number (first 8 alphanumeric digits), (aliases: LPO Number,L.P.O. No., PO No., Order Number, Purchase Order)(take only the first 8 numbers not anything else for example :24004078R7 PO number will be 24004078 )"},
                    {"type": "text", "text": "Delivery Note/Challan Number"},
                    {"type": "text", "text": "SubTotal (Numeric value, aliases: SUBTOTAL, Amount, Total Net Value, SUB-TOTAL) example (101,356.73 treat it as 101356.73 not as 1,01,573.73 ) "},
                    {"type": "text", "text": "Total Amount (Numeric value, aliases: TOTAL, TOTAL AMOUNT, Taxable Amount) its the sum of 'Total Tax Amount' and  SubTotal take 117,573.81 as 117573.81 not as 101573.73) "},
                    {"type": "text", "text": "Currency (3-letter code, default KES)"},
                    {"type": "text", "text": "Total Tax Amount (Numeric value, aliases: VAT Total, Total VAT Amount, VAT@ ,VAT Total, Total VAT Amount in KSH)"},
                    {"type": "text", "text": "Goods/Services Details: Extract item description(description will never be 0), quantity(Numeric value)(Donot confuse quantity with packaging any thing written like (240 x 25 pcs) is a packaging information  not quantity information  )(qunatity will inside provide aliases such as qty or QTY or Quantity example value 9568 or 12394 or 6,000 treat as 6000 or 4,930  treat as 4390 or 460.00 treat as 460)(if packaging details are not found do not treat quantity as 0 , for example you are taking 0 where the value is 12394 with unit price 0), and unit price(numeric value) (" 
                     "Do not treat 6.1100 as 61.1  in unit price this will be 6.11 only (Please treat decimal accurately) "
                     "Do not treat 36.08 as 36.03"
                    "Avoid confusion where similar-looking characters could lead to misinterpretation. For instance:"
                    "'6' must not be confused with '5'."
                    "'9' should not be read as '0'."
                    "'4' should not be interpreted as '1'."
                    "'3' should not be interpreted as '8'.(you are taking 36.08 as 36.03 which is wrong take it as 36.08 only)"
                    "Ensure the extracted value is precise, reflecting the true unit price as written.. ). Ensure correct formatting of quantities and unit prices (handle decimals properly)."},
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
                    {"type": "text", "text": "2. Ensure that numbers are extracted accurately, especially similar-looking digits (e.g., '6' vs '5', '9' vs '0', '3' vs '8')."},
                    {"type": "text", "text": "3. Always capture alphanumeric characters exactly as they appear on the invoice."},
                    {"type" : "text", "text": "4. Be cautious you are making mistake while retreiving quantity never look under packaging heading for quantity only look under QTY, quantity and Quantity"},
                    
                    {"type" : "text", "text" : '''"Avoid confusion where similar-looking characters could lead to misinterpretation. For instance:"
                    "'6' must not be confused with '5'."
                    "'9' should not be read as '0'."
                     "'3' should not be read as '8'."
                    "'4' should not be interpreted as '1'."
                    "Ensure the extracted value is precise, reflecting the true unit price as written.."},'''},
                    
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

        log_time(start_time, "openai")

        if not response or not response.choices or not response.choices[0].message.content:
            return {"error": "No content returned"}

        raw_content = response.choices[0].message.content.strip()
        print("Raw OpenAI Response:\n", raw_content)  # Optional debug log

        return clean_openai_json(raw_content)

    except Exception as e:
        return {"error": str(e)}

def process_file(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    ext = filepath.lower().split('.')[-1]
    try:
        if ext == 'pdf':
            text = ocr_from_pdf(filepath)
        elif ext in {'png', 'jpg', 'jpeg', 'tiff', 'bmp'}:
            text = ocr_from_image(filepath)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        print(f"OCR extracted {len(text)} characters")
        return send_to_llm_single_page(filepath, text)

    except Exception as e:
        print(f"Error processing {filepath}: {str(e)}")
        return {"error": str(e)}

# === Example Usage ===
# result = process_file("path_to_invoice.pdf")
# print(json.dumps(result, indent=2))
