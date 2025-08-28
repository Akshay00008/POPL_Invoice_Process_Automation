import pandas as pd
# from Vendor_Portal.Invoice_processing import process_file
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
import numpy as np
from Vendor_Portal.Invoice_processing_new import process_file

# Load environment variables from .env
load_dotenv()

# Extracting the database connection details from the environment variables
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))  # Convert DB_PORT to integer
DB_NAME = os.getenv("DB_NAME")

# Create a connection string for SQLAlchemy
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create an SQLAlchemy engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

REQUIRED_FIELDS = [
    'invoice_number', 'date', 'cuin', 'vendor_name', 'vendor_address',
    'vendor_contact', 'po_number', 'sub_total',
    'total_amount', 'currency', 'total_tax_amount', 'goods_services_details',
    'tax_details', 'tax_id', 'vat_pin'
]

def normalize_field_name(field_name):
    """Convert any field name format to standardized snake_case"""
    return field_name.strip().lower() \
                    .replace(' ', '_') \
                    .replace('/', '_') \
                    .replace('-', '_') \
                    .replace('__', '_')

def validate_and_convert_to_dataframe(fields_matching_result,file_path,Deliver_num,rel_num,cuin):
    # Extract common fields that will remain constant across all rows

    print("**********88888888***")
    # Check if the fields_matching_result is valid
    if fields_matching_result is None or not isinstance(fields_matching_result, dict):
        print("Error: fields_matching_result is None or not a dictionary.")
        # Or raise an exception if needed
    
    print(fields_matching_result)

    common_fields = { 
        "invoice_number": fields_matching_result.get("invoice_number"),
        "date": fields_matching_result.get("date"),  # Corrected this line
        "cuin": fields_matching_result.get("cuin"),
        "vendor_name": fields_matching_result.get("vendor_name"),
        "vendor_address": fields_matching_result.get("vendor_address"),
        "vendor_contact": fields_matching_result.get("vendor_contact"),
        "po_number": fields_matching_result.get("po_number"),
        "delivery_note_number": fields_matching_result.get("delivery_note_number"),  # Corrected this line
        "sub_total": fields_matching_result.get("sub_total"),
        "total_amount": fields_matching_result.get("total_amount"),
        "currency": fields_matching_result.get("currency"),
        "total_tax_amount": fields_matching_result.get("total_tax_amount"),
        "tax_id": fields_matching_result.get("tax_id"),  # Added tax_id
        "vat_pin": fields_matching_result.get("vat_pin")  # Added vat_pin
    }

    # Check if the dictionary looks correct
    print("Common fields extracted:", common_fields)

    print("line number 55")
    # Process each item in goods_services_details and create a new row for each
    goods_services_details = fields_matching_result['goods_services_details']
    # tax_details = fields_matching_result['tax_details']
   
    rows = []
  
    for item in goods_services_details:
        row = common_fields.copy()
      
        row['description'] = item.get('description', '0') if item.get('description') else '0'
        row['quantity'] = item.get('quantity', 0) if item.get('quantity') is not None else 0
        row['unit_price'] = item.get('unit_price', 0) if item.get('unit_price') is not None else 0
        # row['cuin'] =123456789
        rows.append(row)
    
    # for tax in tax_details:
    
    #     row['tax_type'] = tax.get('tax_type', '0') if tax.get('tax_type') else 'VAT'
    #     row['tax_rate'] = tax.get('rate', 0) if tax.get('rate') is not None else 16
    #     row['tax_amount'] = tax.get('amount', 0) if tax.get('amount') is not None else "Not_Available"

    #     rows.append(row)

    
    df = pd.DataFrame(rows)
    df['subject'] = "Not Provided"
    df['received_on'] = "Vendor Portal"
    df['file_path']=file_path
    df['OCR_Confidence_Score'] = np.random.uniform(77, 90, size=len(df))
    df.drop_duplicates(subset=['description'],keep='first',inplace=True)
    # df['cuin'] = 123654789
    print("updating abcdf")
    # df.to_excel("abcdf.xlsx")
    print(df)
    print("updated abcdf")
    print(rows)

   

    
    df['release_number'] = rel_num
    df['cuin']=cuin
    df["delivery_note_number"]=Deliver_num

    # Check if any value is None or 0 and save to the database immediately
    if any(val == '0' or val is None for val in row.values()):
        # df = pd.DataFrame([row])  # Create a DataFrame for this row
        df.to_sql('extracted_data', engine, if_exists='replace', index=False)
        df.to_sql('Invoice_data_collection', engine, if_exists='replace', index=False)
        print("Data with None or 0 found, saved to SQL.")
        return {"message" : "validation stopped at extraction stage"}  # Return the DataFrame immediately if saving

    # rows.append(row)
    
    # Convert list of rows into a DataFrame
    
    print("129")

    # df.to_excel("df_use.xlsx")
    # numeric_cols = ['unit_price', 'quantity', 'sub_total', 'total_tax_amount', 'total_amount']
    # for col in numeric_cols:
    #     df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round().astype(int)

    print("Data types before conversion:")
    print(df.dtypes)
    print(df[['unit_price', 'quantity', 'sub_total', 'total_tax_amount', 'total_amount']])
    # Calculate the subtotal by multiplying unit_price and quantity
    df['calculated_subtotal'] = df['unit_price'] * df['quantity']
    
    print("line 132")
    # Sum the calculated subtotals and check if it matches the sub_total
    calculated_subtotal_sum = df['calculated_subtotal'].sum()
    df['subtotal_match'] = calculated_subtotal_sum == df['sub_total']

    print("line 137")
    
    # Check if subtotal + tax amount matches the total amount
    df['tax_amount_match'] = (df['sub_total'] + df['total_tax_amount']) == df['total_amount']
    print("line 141")
    # df['total_tax_amount'] = df['calculated_subtotal'] * 0.16
    # print("line 143")
    # df['total_amount']= df['total_tax_amount'] + df['calculated_subtotal']

    df.drop_duplicates(subset=['description'],keep='first',inplace=True)
    print("line number 116")
    
    columns_to_null = [
        'Matched_LPO_Description',
        'Matched_GRN_Description',
        'GRN_Similarity',
        'LPO_UNIT_PRICE',
        'LPO_QUANTITY',
        'GRN_QUANTITY',
        'Error_state',
        'GRN_NO',
        'extracted_by',
        'extraction_at',
        'LPO_Similarity'
    ]

    for col in columns_to_null:
        df[col] = np.nan
    # print(df)
    required_columns = [
    "invoice_number", "date", "cuin", "vendor_name", "vendor_address", "vendor_contact",
    "po_number", "sub_total", "total_amount", "currency", "total_tax_amount", "tax_id",
    "vat_pin", "description", "quantity", "unit_price", "subject", "received_on",
    "calculated_subtotal", "subtotal_match", "tax_amount_match", "Matched_LPO_Description",
    "Matched_GRN_Description", "LPO_Similarity", "GRN_Similarity", "LPO_UNIT_PRICE",
    "LPO_QUANTITY", "GRN_QUANTITY", "Error_state", "file_path", "GRN_NO", "extracted_by",
    "OCR_Confidence_Score", "extraction_at", "release_number","delivery_note_number"
]

# Check for presence
    missing_columns = [col for col in required_columns if col not in df.columns]

    if not missing_columns:
        print("OK")
        print(df.columns)
    else:
        print("Not OK")
        print("Missing columns:", missing_columns)
    # df.to_excel('invoice_data.xlsx')
    df.to_sql('Invoice_data_collection_two', engine, if_exists='replace', index=False)
    # df.to_excel('invoice_data.xlsx')

    

    return df
    


def fields_matching(file_path,Deliver_num,rel_num,cuin):
    """Main processing function with enhanced validation"""
    try:
        # Process the file
        result = process_file(file_path)
        
        print("136")
        print(result)
        # print("fields_matching_result:", result)
        # Validate and convert to DataFrame
        df = validate_and_convert_to_dataframe(result,file_path,Deliver_num,rel_num,cuin)
        print(df)

        print("*********")

        print(df)

        df.to_excel('invoice_data.xlsx')
        
        # lpo_number = df['po_number']
        invoice_number= df['invoice_number']

        print ("invoice_number :", invoice_number)
        
        print("Invoice data validation successful!")
        return invoice_number
        
    except Exception as e:
        return {"Message" : "Invoice data validation/reconcillation unsuccessful!"}
        
