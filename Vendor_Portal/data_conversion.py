import os
import json
import pandas as pd
from decimal import Decimal, InvalidOperation
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Load environment variables
load_dotenv()

# Get DB credentials
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME")

# Create SQLAlchemy engine
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)

def data_conversion_pipeline(invoice_number):
    print(invoice_number)
    # Read source CSVs
    invoice_data_query  =  f"SELECT * FROM invoice_data WHERE invoice_number = '{invoice_number}'"
    # destination structure only used to match schema
    invoice_data_collection_query =f"SELECT * FROM Invoice_data_collection WHERE invoice_number = '{invoice_number}'"

    invoice_data_df = pd.read_sql_query(invoice_data_query, engine)

    # Helper functions
    def safe_decimal(value):
        try:
            return float(Decimal(str(value))) if pd.notna(value) else None
        except InvalidOperation:
            return None

    def safe_date(value):
        try:
            return pd.to_datetime(value).date() if pd.notna(value) else None
        except Exception:
            return None

    def parse_goods_services(raw):
        """Parse the goods_services JSON into multiple rows."""
        if pd.isna(raw):
            return []
        try:
            items = json.loads(raw)
            if isinstance(items, list):
                rows = []
                for item in items:
                    description = item.get("description")
                    quantity = safe_decimal(item.get("quantity"))
                    price = safe_decimal(item.get("unitPrice"))
                    rows.append((description, quantity, price))
                return rows
        except Exception:
            pass
        return []

    # Transform data
    transformed = []
    for _, row in invoice_data_df.iterrows():
        goods_services_rows = parse_goods_services(row.get("goods_services"))

        # Create a new row for each item in the goods_services list
        for desc, qty, price in goods_services_rows:
            calculated_subtotal = qty * price if qty and price else None
            sub_total = safe_decimal(row.get("total_before_tax"))

            transformed.append({
                "invoice_number": row.get("invoice_number"),
                "date": safe_date(row.get("invoice_date")),
                "cuin": row.get("cuin"),
                "vendor_name": row.get("vendor_name"),
                "vendor_address": row.get("vendor_address"),
                "vendor_contact": row.get("vendor_contact"),
                "po_number": row.get("po_number"),
                "sub_total": sub_total,
                "total_amount": safe_decimal(row.get("total_amount")),
                "currency": row.get("currency"),
                "total_tax_amount": safe_decimal(row.get("total_tax_amount")),
                "tax_id": row.get("tax_id"),
                "vat_pin": row.get("vat_pin") or row.get("tax_details"),
                "description": desc,
                "quantity": qty,
                "unit_price": price,
                "subject": row.get("submission_type"),
                "received_on": safe_date(row.get("updated_at") or row.get("created_at")),
                "file_path": row.get("image_qr_path"),
                "OCR_Confidence_Score": row.get("ocr_confidence_score"),
                "calculated_subtotal": calculated_subtotal,
                "subtotal_match": "Y" if sub_total == calculated_subtotal else "N",
                "tax_amount_match": "Y" if safe_decimal(row.get("total_tax_amount")) == safe_decimal(row.get("total_tax_amount")) else "N"
            })

    # Convert to DataFrame
    result_df = pd.DataFrame(transformed)

    print(result_df)

    # Sum the calculated subtotals and check if it matches the sub_total
    calculated_subtotal_sum = result_df['calculated_subtotal'].sum()
    result_df['subtotal_match'] = calculated_subtotal_sum == result_df['sub_total']

    # Check if subtotal + tax amount matches the total amount
    result_df['tax_amount_match'] = (result_df['sub_total'] + result_df['total_tax_amount']) == result_df['total_amount']

    result_df['release_number'] = 1

    result_df.to_excel('ref.xlsx')
    
    # Insert into MySQL
    result_df.to_sql("Invoice_data_collection", engine, if_exists="replace", index=False)
 
    print("✅ Data migrated successfully to invoice_data_collection.")

    return result_df  # Returning the DataFrame for further inspection
