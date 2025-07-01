from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from utility.logger_file import Logs
from Vendor_Portal.Invoice_validation import fields_matching
from Vendor_Portal.Reconcilation import Reconcillation_process
from threading import Thread

# Initialize logger
loggs = Logs()

# Initialize Flask app and configure middleware
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)
CORS(app)

# Helper function to process the invoice OCR
def process_invoice_ocr(file_path):
    """Processes the invoice file using OCR and validates the fields."""
    try:
        # Extract invoice data and validate fields
        invoice_df = fields_matching(file_path)
        loggs.info(f"Validated Invoice Data: {invoice_df}")
        lpo_numbers = invoice_df[0]
    except Exception as e:
        loggs.error(f"Invoice processing failed: {str(e)}")
        raise ValueError(f"Invoice processing failed: {str(e)}")
    
    return lpo_numbers

# Helper function to handle the reconciliation process
def perform_reconciliation(lpo_numbers,item_count):
    """Runs the reconciliation process with the provided LPO numbers."""
    try:
        result = Reconcillation_process(lpo_numbers,item_count)
        loggs.info(f"Reconciliation result: {result}")
    except Exception as e:
        loggs.error(f"Reconciliation failed: {str(e)}")
        raise ValueError(f"Reconciliation failed: {str(e)}")

    return {"result": result}

# Function to manage the OCR and reconciliation steps asynchronously
def process_invoice_and_reconcile(file_path):
    """Process the invoice OCR and then perform reconciliation in background."""
    lpo_numbers = process_invoice_ocr(file_path)
    print("LPo numbers :",lpo_numbers )
    reconciliation_result = perform_reconciliation(lpo_numbers,item_count=0)
    return reconciliation_result

# Route to trigger the invoice processing and reconciliation
@app.route("/invoice_processing", methods=["POST"], strict_slashes=False)
def invoice_trigger():
    """Trigger the invoice processing and reconciliation via an API endpoint."""
    # The file path could be passed from the request, for simplicity I use a fixed file path
    file_path = r"C:\\Users\\hp\\Desktop\\FINANCE_20-05-2025\\Invoices\\SANPAC MA109305.pdf"
    
    # Run the processing in a background thread
    thread = Thread(target=process_invoice_and_reconcile, args=(file_path,))
    thread.start()

    # Respond to the client immediately while the background process runs
    return jsonify({"message": "Invoice processing and reconciliation started."}), 202

# @app.route("/extraction_page",methods=["POST"], strict_slashes=False)
