import os
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import openai
import json
from pyzbar.pyzbar import decode  # For QR code scanning

# Configure paths (uncomment/modify if needed)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_qr_from_image(image):
    """Extract the first QR code content from a PIL image."""
    try:
        # Convert to RGB for pyzbar compatibility
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Detect and decode QR codes
        decoded_objects = decode(image)
        if decoded_objects:
            return decoded_objects[0].data.decode('utf-8')
    except Exception as e:
        print(f"QR extraction error: {str(e)}")
    return None

def ocr_from_image(image_path):
    """Extract text and QR code from an image file."""
    with Image.open(image_path) as img:
        text = pytesseract.image_to_string(img)
        qr_content = extract_qr_from_image(img)
    return text.strip(), qr_content  # Return both OCR text and QR content

def ocr_from_pdf(pdf_path):
    """Extract text and QR code from a PDF file."""
    try:
        pages = convert_from_path(
            pdf_path, 
            dpi=300,
            # poppler_path=r"C:\Users\hp\Downloads\Release-24.08.0-0\poppler-24.08.0\Library\bin"
            poppler_path=r"\home\bramhesh_srivastav\POPL_Invoice_Process_Automation\Release-24.08.0-0\poppler-24.08.0\Library\bin"
        )
    except Exception as e:
        raise RuntimeError(f"PDF conversion failed: {e}") from e
    
    if not pages:
        raise ValueError("PDF file is empty or could not be processed")
    
    full_text = []
    qr_content = None
    for page in pages:
        # Extract text from each page
        page_text = pytesseract.image_to_string(page).strip()
        full_text.append(page_text)
        
        # Extract QR code if not already found
        if qr_content is None:
            qr_content = extract_qr_from_image(page)
    
    return "\n".join(full_text), qr_content

def extract_invoice_data_with_llm(text):
    """Extract structured data from invoice text using LLM (unchanged)"""
    # ... [Your existing LLM processing code] ...

def process_file(filepath):
    """Process file and return extracted invoice data + QR content"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    
    ext = filepath.lower().split('.')[-1]
    try:
        if ext == 'pdf':
            text, qr_content = ocr_from_pdf(filepath)
        elif ext in {'png', 'jpg', 'jpeg', 'tiff', 'bmp'}:
            text, qr_content = ocr_from_image(filepath)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
        
        print(f"Extracted {len(text)} characters from OCR")
        invoice_data = extract_invoice_data_with_llm(text)
        
        return {
            "invoice_data": invoice_data,
            "qr_content": qr_content
        }
    
    except Exception as e:
        print(f"Error processing {filepath}: {str(e)}")
        raise

if __name__ == "__main__":
    FILE_PATH = "C:\\Users\\hp\\Desktop\\FINANCE_20-05-2025\\Invoices\\ALLPACK 266900.pdf"
    
    try:
        result = process_file(FILE_PATH)
        print("\nExtracted Invoice Data:")
        print(json.dumps(result["invoice_data"], indent=2))
        print("\nQR Code Content:")
        print(result["qr_content"] or "No QR code detected")
    except Exception as e:
        print(f"Processing failed: {str(e)}")






        