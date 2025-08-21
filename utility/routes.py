from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from utility.logger_file import Logs
from Vendor_Portal.Invoice_validation import fields_matching
from Vendor_Portal.Reconcilation import Reconcillation_process
from Vendor_Portal.kra_portal import check_qr_code_in_pdf
from threading import Thread
# from Vendor_Portal.test import process_invoice_ocr_kra_portal
import asyncio
from queue import Queue
from Vendor_Portal.ERP_Upload import InvoiceApiHandler
from Vendor_Portal.data_conversion import   data_conversion_pipeline
from Vendor_Portal.validate_pipeline import Buyer_validation
from Vendor_Portal.validate_pipeline_2 import  visit_and_validate_invoice_number

# Initialize logger
loggs = Logs()

# Initialize Flask app and configure middleware
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)
CORS(app)


# Create a queue to manage tasks
task_queue = Queue()

# Function to process each task from the queue
def process_task_from_queue():
    while True:
        try:
            file_path, rel_num, lpo_number, cuin = task_queue.get()
            if file_path is None:  # Stop the worker thread if None is received
                break

            try:
                # Perform the processing
                process_invoice_and_reconcile(file_path, rel_num, lpo_number, cuin)
            except Exception as e:
                print(f"Error processing task {file_path}: {e}")  # Log the error but continue

            task_queue.task_done()

        except Exception as queue_error:
            print(f"Unexpected error in worker loop: {queue_error}")


# Initialize a worker thread to handle the queue
worker_thread = Thread(target=process_task_from_queue)
worker_thread.start()

# Function to manage the OCR and reconciliation steps asynchronously
def process_invoice_and_reconcile(file_path, rel_num, lpo_number,cuin):
    lpo_number=lpo_number
    cuin=cuin
    # Perform invoice processing and reconciliation
    lpo_invoice_number = process_invoice_ocr(file_path, rel_num,cuin)
    if isinstance(lpo_invoice_number, dict) and "message" in lpo_invoice_number:
        return lpo_invoice_number

    lpo_numbers = lpo_number
    invoice_number = lpo_invoice_number
    reconciliation_result = perform_reconciliation(lpo_numbers, invoice_number, rel_num, item_count=0)
    return reconciliation_result

# Helper function to process the invoice OCR
def process_invoice_ocr(file_path,rel_num,cuin):
    """Processes the invoice file using OCR and validates the fields."""
    try:
        # Extract invoice data and validate fields
        result = fields_matching(file_path,rel_num,cuin)
        
        print("**********")
        print(result )
        # Check if the result is an error message
        if isinstance(result, dict) and "message" in result:
            # Return the error message
            return result
        
        # Unpack the result into invoice_df and invoice_number
        invoice_number = result
        
        # Validate the extracted values (ensure they are not None)
        if invoice_number is None:
            raise ValueError("Extracted values for invoice data are None.")

        loggs.info(f"Validated Invoice Data: {invoice_number}")
        
        # Extract values
        # lpo_numbers = lpo_number
        invoice_number = invoice_number[0]
        
        # print("26 lpo_numbers:", lpo_numbers)
        print("27 invoice_number:", invoice_number)
        
        return invoice_number

    except Exception as e:
        loggs.error(f"Invoice processing failed at line 53 : {str(e)}")
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
# def process_invoice_and_reconcile(file_path,rel_num):
#     """Process the invoice OCR and then perform reconciliation in background."""
#     lpo_invoice_number = process_invoice_ocr(file_path,rel_num)
    
#     print("lpo_invoice_number :",lpo_invoice_number)

#     if isinstance(lpo_invoice_number, dict) and "message" in lpo_invoice_number:
#             # Return the error message
#             return lpo_invoice_number
#     lpo_numbers=lpo_invoice_number[0]
#     invoice_number=lpo_invoice_number[1]


#     print("LPo numbers :",lpo_numbers )
#     print("invoice_number :", invoice_number)
#     reconciliation_result = perform_reconciliation(lpo_numbers,invoice_number,rel_num,item_count=0)
#     return reconciliation_result

# Route to trigger the invoice processing and reconciliation
from flask import request

@app.route("/invoice_processing", methods=["POST"], strict_slashes=False)
def invoice_trigger():
    invoices = request.json.get('invoice_objects')

    if not invoices:
        return jsonify({"error": "No invoice objects provided."}), 400

    for invoice in invoices:
        submission_type = invoice.get('submission_type')

        if submission_type == 'form':
            invoice_number = invoice.get('invoice_number')
            lpo_number = invoice.get('lpo_number')
            rel_num = invoice.get('REL_NUM')
            item_count = 0
            result = data_conversion_pipeline(invoice_number)

            # Start the task in the queue
            task_queue.put((lpo_number, invoice_number, rel_num, item_count))
            # Optionally, you can send a response after each task is added.
        elif submission_type == 'upload':
            file_path = invoice.get('invoice_image')
            rel_num = invoice.get('REL_NUM')
            lpo_number = invoice.get('lpo_number')
            cuin=invoice.get('cuin')

            # Check if file_path is provided in the request
            if not file_path:
                return jsonify({"error": "File path is required."}), 400

            # Add task to the queue for sequential processing
            task_queue.put((file_path, rel_num,lpo_number,cuin))
            # Optionally, you can send a response after each task is added.
        else:
            return jsonify({"error": f"Invalid submission type: {submission_type}"}), 400

    return jsonify({"message": "Invoice processing and reconciliation started for all invoices"}), 202


# @app.route("/invoice_processing", methods=["POST"], strict_slashes=False)
# def invoice_trigger():
#     submission_type = request.json.get('submission_type')

#     if submission_type == 'form':
#         invoice_number = request.json.get('invoice_number')
#         lpo_number = request.json.get('lpo_number')
#         rel_num = request.json.get('REL_NUM')
#         item_count = 0
#         result = data_conversion_pipeline(invoice_number)

#         # Start the task in the queue
#         task_queue.put((lpo_number, invoice_number, rel_num, item_count))
#         return jsonify({"message": "Invoice processing and reconciliation started"}), 202

#     else:
#         file_path = request.json.get('invoice_image')
#         rel_num = request.json.get('REL_NUM')
        
#         # Check if file_path is provided in the request
#         if not file_path:
#             return jsonify({"error": "File path is required."}), 400
        
#         # Add task to the queue for sequential processing
#         task_queue.put((file_path, rel_num))

#         return jsonify({"message": "Invoice processing and reconciliation started."}), 202




@app.route("/extraction_page",methods=["POST"], strict_slashes=False)
def extraction_page():
    lpo_number=request.json.get('lpo_number')
    invoice_number=request.json.get('invoice_number')
    try:
        result = data_conversion_pipeline(invoice_number)
        rel_num=result['release_number']
        rel_num=rel_num[0]
        print("1345")
        thread = Thread(target=perform_reconciliation, args=(lpo_number,invoice_number,rel_num,0))
        thread.start()
        return jsonify({"message": "Reconcillation processing started."}), 202
    except Exception as e:
        loggs.error(f"Reconciliation failed: {str(e)}")
        raise ValueError(f"Reconciliation failed: {str(e)}")
    



# #Flask route for handling the request
@app.route("/kra_portal", methods=["POST"], strict_slashes=False)
def kra_portal():

    try :
        """Process the invoice image and store data in SQL."""
        # Get the PDF path from the request body
        pdf_path = request.json.get('invoice_image')

        if not pdf_path:
            return jsonify({"error": "No invoice_image provided"}), 400

        # Call the function to process the PDF and get the result
        # result = asyncio.run(process_invoice_ocr_kra_portal(pdf_path))
        final_details=asyncio.run(process_invoice_ocr_kra_portal(pdf_path))
        print("******:")
        print(final_details)
        print("**********")

        for invoice_path, data in final_details.items():
            control_unit_invoice_number = data.get('invoice_data', {}).get('control_unit_invoice_number', 'Not Found')
            print(f"Control Unit Invoice Number: {control_unit_invoice_number}")

        # # Continue with the buyer validation process
        # result = asyncio.run(Buyer_validation(final_details))

        # control_unit_invoice_number = final_details.get(
        # '/apps/POPL_Invoice_Process_Automation/Invoices/KOBIAN 122076.pdf', {}
        #     ).get('invoice_data', {}).get('control_unit_invoice_number', 'Not Found')

        # print(control_unit_invoice_number)

        # Continue with the buyer validation process
        result = asyncio.run(Buyer_validation(final_details))
        return control_unit_invoice_number


        

        # Return the result in the response
    except Exception as e:
            loggs.error(f"KRA Validation failed: {str(e)}")
            raise ValueError(f"KRA Validation failed:: {str(e)}")
        

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

@app.route("/Ccuin_fif",methods=["POST"], strict_slashes=False)
async def main():
    CUIN=request.json.get('CUIN')
    results = await visit_and_validate_invoice_number(CUIN)
    for pdf_file, result in results.items():
        buyer = result.get("buyer_name", "").strip().upper()
        if buyer == "PWANI OIL PRODUCTS LTD":
            print(f"✅ Validated: {pdf_file}")
            return {"message" : "Sucess"}, 200
        else:
            print(f"❌ Not validated: {pdf_file} (Buyer: {buyer})")
            return {"message" : "Not Sucess"} , 500



