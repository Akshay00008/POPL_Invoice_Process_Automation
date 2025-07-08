from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from utility.logger_file import Logs
from Vendor_Portal.Invoice_validation import fields_matching
from Vendor_Portal.Reconcilation import Reconcillation_process
from Vendor_Portal.kra_portal import check_qr_code_in_pdf
from threading import Thread
from Vendor_Portal.test import process_invoice_ocr_kra_portal
import asyncio
from Vendor_Portal.ERP_Upload import InvoiceApiHandler
from Vendor_Portal.data_conversion import   data_conversion_pipeline

# Initialize logger
loggs = Logs()

# Initialize Flask app and configure middleware
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)
CORS(app)

# Helper function to process the invoice OCR
def process_invoice_ocr(file_path,rel_num):
    """Processes the invoice file using OCR and validates the fields."""
    try:
        # Extract invoice data and validate fields
        result = fields_matching(file_path)
        
        # Check if the result is an error message
        if isinstance(result, dict) and "message" in result:
            # Return the error message
            return result
        
        # Unpack the result into invoice_df and invoice_number
        invoice_df, invoice_number = result
        
        # Validate the extracted values (ensure they are not None)
        if invoice_df is None or invoice_number is None:
            raise ValueError("Extracted values for invoice data are None.")

        loggs.info(f"Validated Invoice Data: {invoice_df}")
        
        # Extract values
        lpo_numbers = invoice_df[0]
        invoice_number = invoice_number[0]
        
        print("26 lpo_numbers:", lpo_numbers)
        print("27 invoice_number:", invoice_number)
        
        return lpo_numbers, invoice_number

    except Exception as e:
        loggs.error(f"Invoice processing failed: {str(e)}")
        return {"message": "Data with None or 0 found, saved to SQL."}


# Helper function to handle the reconciliation process
def perform_reconciliation(lpo_number,invoice_number,rel_num,item_count):
    """Runs the reconciliation process with the provided LPO numbers."""
    try:
        result = Reconcillation_process(lpo_number,invoice_number,rel_num,item_count)
        loggs.info(f"Reconciliation result: {result}")
    except Exception as e:
        loggs.error(f"Reconciliation failed: {str(e)}")
        raise ValueError(f"Reconciliation failed: {str(e)}")

    return {"result": result}

# Function to manage the OCR and reconciliation steps asynchronously
def process_invoice_and_reconcile(file_path,rel_num):
    """Process the invoice OCR and then perform reconciliation in background."""
    lpo_invoice_number = process_invoice_ocr(file_path)
    
    print("lpo_invoice_number :",lpo_invoice_number)

    if isinstance(lpo_invoice_number, dict) and "message" in lpo_invoice_number:
            # Return the error message
            return lpo_invoice_number
    lpo_numbers=lpo_invoice_number[0]
    invoice_number=lpo_invoice_number[1]


    print("LPo numbers :",lpo_numbers )
    print("invoice_number :", invoice_number)
    reconciliation_result = perform_reconciliation(lpo_numbers,invoice_number,rel_num,item_count=0)
    return reconciliation_result

# Route to trigger the invoice processing and reconciliation
from flask import request

@app.route("/invoice_processing", methods=["POST"], strict_slashes=False)
def invoice_trigger():
    """Trigger the invoice processing and reconciliation via an API endpoint."""
    # Get the file path from the request body
    
    submission_type=request.json.get('submission_type')
    
    if submission_type == 'form' :
        invoice_number = request.json.get('invoice_number')
        lpo_number = request.json.get('lpo_number')
        rel_num=request.json.get('rel_num')
        item_count=0
        result = data_conversion_pipeline (invoice_number)
        thread = Thread(target=perform_reconciliation, args=(lpo_number,invoice_number,rel_num,item_count))
        thread.start()
        return jsonify({"message": "Invoice processing and reconciliation started"}), 202
    
    
    else :

        file_path = request.json.get('invoice_image')
        # Check if file_path is provided in the request
        if not file_path:
            return jsonify({"error": "File path is required."}), 400
        
        # Run the processing in a background thread
        thread = Thread(target=process_invoice_and_reconcile, args=(file_path,rel_num))
        thread.start()

        # Respond to the client immediately while the background process runs
        return jsonify({"message": "Invoice processing and reconciliation started."}), 202


@app.route("/extraction_page",methods=["POST"], strict_slashes=False)
def extraction_page():
    lpo_number=request.json.get('lpo_number')
    invoice_number=request.json.get('invoice_number')
    try:
        result = data_conversion_pipeline(invoice_number)
        rel_num=result['release_number']
        rel_num=rel_num[0]
        thread = Thread(target=perform_reconciliation, args=(lpo_number,invoice_number,rel_num,0))
        thread.start()
        return jsonify({"message": "Reconcillation processing started."}), 202
    except Exception as e:
        loggs.error(f"Reconciliation failed: {str(e)}")
        raise ValueError(f"Reconciliation failed: {str(e)}")
    
# @app.route("/kra_portal", methods=["POST"], strict_slashes=False)
# def kra_portal():
#     # Get the PDF path from the request body
#     pdf_path = request.json.get('invoice_image')

#     if not pdf_path:
#         return jsonify({"error": "No invoice_image provided"}), 400
    
#     # Call the function to process the PDF and get the result
#     result = check_qr_code_in_pdf(pdf_path)

#     # Return the result in the response
#     return {"message" :result }


# #Flask route for handling the request
@app.route("/kra_portal", methods=["POST"], strict_slashes=False)
def kra_portal():
    """Process the invoice image and store data in SQL."""
    # Get the PDF path from the request body
    pdf_path = request.json.get('invoice_image')

    if not pdf_path:
        return jsonify({"error": "No invoice_image provided"}), 400

    # Call the function to process the PDF and get the result
    result = asyncio.run(process_invoice_ocr_kra_portal(pdf_path))

    # Return the result in the response
    return jsonify(result)
# #Flask route for handling the request

@app.route("/erp_upload",methods=["POST"], strict_slashes=False)
def erp_upload():
    
    dsn = "TEST"
    username = "Apps"
    password = "apps085"
    data_list=request.get_json()
    handler=InvoiceApiHandler(dsn,username,password)
    print("handler")
    result=handler.insert_data_and_call_api(data_list)
    print("result:", result)
    # message =handler.grn_generation(result)

    return result