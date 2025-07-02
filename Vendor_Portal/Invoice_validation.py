import pandas as pd
from Vendor_Portal.Invoice_processing import process_file
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv


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

def validate_and_convert_to_dataframe(fields_matching_result):
    # Extract common fields that will remain constant across all rows
    common_fields = { 
        'invoice_number': fields_matching_result['invoice_number'],
        'date': fields_matching_result['date'],
        'cuin': fields_matching_result['cuin'],
        'vendor_name': fields_matching_result['vendor_name'],
        'vendor_address': fields_matching_result['vendor_address'],
        'vendor_contact': fields_matching_result['vendor_contact'],
        'po_number': fields_matching_result['po_number'],
        'sub_total': fields_matching_result['sub_total'],
        'total_amount': fields_matching_result['total_amount'],
        'currency': fields_matching_result['currency'],
        'total_tax_amount': fields_matching_result['total_tax_amount'],
        'tax_id': fields_matching_result['tax_id'],
        'vat_pin' : fields_matching_result['vat_pin'],
    }
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
    df.drop_duplicates(subset=['description'],keep='first',inplace=True)
    # df['cuin'] = 123654789
    print("updating abcdf")
    df.to_excel("abcdf.xlsx")
    print(df)
    print("updated abcdf")
    print(rows)
    

    # Check if any value is None or 0 and save to the database immediately
    if any(val == '0' or val is None for val in row.values()):
        # df = pd.DataFrame([row])  # Create a DataFrame for this row
        df.to_sql('extracted_data', engine, if_exists='replace', index=False)
        print("Data with None or 0 found, saved to SQL.")
        return {"message" : "validation stopped at extraction stage"}  # Return the DataFrame immediately if saving

    # rows.append(row)
    
    # Convert list of rows into a DataFrame
    
    # Calculate the subtotal by multiplying unit_price and quantity
    df['calculated_subtotal'] = df['unit_price'] * df['quantity']
    
    # Sum the calculated subtotals and check if it matches the sub_total
    calculated_subtotal_sum = df['calculated_subtotal'].sum()
    df['subtotal_match'] = calculated_subtotal_sum == df['sub_total']

    
    
    # Check if subtotal + tax amount matches the total amount
    df['tax_amount_match'] = (df['sub_total'] + df['total_tax_amount']) == df['total_amount']

    df.drop_duplicates(subset=['description'],keep='first',inplace=True)

    df.to_excel('invoice_data.xlsx')

    if (df['subtotal_match'] == False).any() or (df['tax_amount_match'] == False).any():
        # Setup the SQL connection
        # engine = create_engine('your_database_connection_string')

        # Store the entire DataFrame into 'reconciliation_data' table if condition is met
        df['Error_state'] = "Tax_amount"
        df.to_sql('reconciliation_data', con=engine, if_exists='append', index=False)

        print("Message:", "Data Saved to Reconcillateion stage")
        return df
        # return {"Message" : "Data Saved to Reconcillateion stage mismatch in subtotal and tax amount"}

    return df
    


def fields_matching(file_path):
    """Main processing function with enhanced validation"""
    try:
        # Process the file
        result = process_file(file_path)
        
        print("fields_matching_result:", result)
        # Validate and convert to DataFrame
        df = validate_and_convert_to_dataframe(result)

        # df.to_excel('invoice_data.xlsx')
        
        lpo_number = df['po_number']
        
        print("Invoice data validation successful!")
        return lpo_number
        
    except Exception as e:
        return {"Message" : "Invoice data validation/reconcillation unsuccessful!"}
        
