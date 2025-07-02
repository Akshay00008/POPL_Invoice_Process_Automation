import pandas as pd
import re
import cx_Oracle
from flask import Flask, jsonify, make_response
from sentence_transformers import SentenceTransformer, util
import torch
import os 
from sqlalchemy import create_engine
from dotenv import load_dotenv
from openai import OpenAI
import numpy as np


load_dotenv()  # This will load the .env file in your project directory

# Retrieve OpenAI API Key from environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")  # Use the key stored in .env

# Check if the API key is loaded correctly
if not openai_api_key:
    raise ValueError("OpenAI API key is not set. Please set it in the .env file.")

# Initialize OpenAI client
client = OpenAI(api_key=openai_api_key)


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

def Reconcillation_process(lpo_numbers,item_count):
    
    # lpo_numbers = []
   

   

   
    query_2 = ''' 
    SELECT
 
      poh.po_header_id, poh.CREATION_DATE,
 
      poh.type_lookup_code PO_TYPE,
 
      poh.authorization_status PO_STATUS,
 
      poh.segment1 PO_NUMBER,
 
      por.RELEASE_NUM,
 
      pov.vendor_name SUPPLIER_NAME,
 
      povs.vendor_site_code Location,
 
      hrls.location_code Ship_To,
 
      hrlb.location_code Bill_to,
 
      pol.line_num,
 
      msib.segment1 Item, msib.DESCRIPTION,
 
      pol.unit_price,
 
      pol.quantity,
 
      pod.amount_billed Amount,
 
      pod.destination_subinventory,
 
      ppf.full_name Buyer_Name,
 
      poh.closed_Code
 
    FROM
 
      PO_HEADERS_ALL poh,
 
      PO_LINES_ALL pol,
 
      mtl_system_items_b msib,
 
      PO_LINE_LOCATIONS_ALL poll,
 
      PO_DISTRIBUTIONS_ALL pod,
 
      po_vendors pov,
 
      po_vendor_sites_All povs,
 
      hr_locations_all hrls,
 
      hr_locations_all hrlb,
 
      per_all_people_f ppf,
 
      po_line_types polt,
 
      PO_RELEASES_ALL por
 
    WHERE
 
      1 = 1
 
      AND polt.line_type_id     = pol.line_type_id
 
      AND povs.vendor_site_id   = poh.vendor_site_id
 
      AND pov.vendor_id         = poh.vendor_id
 
      AND pol.item_id           = msib.inventory_item_id
 
      AND msib.organization_id  = 83
 
      AND poh.po_header_id      = pol.po_header_id
 
      AND pol.po_line_id        = pod.po_line_id
 
      AND poll.line_location_id = pod.line_location_id
 
      AND poh.ship_to_location_id = hrls.location_id
 
      AND poh.bill_to_location_id = hrlb.location_id
 
      AND poh.agent_id          = ppf.person_id
 
      and poh.PO_HEADER_ID = por.PO_HEADER_ID(+)
 
      AND poh.segment1          = :lpo_number

      '''
    
    query_3 = '''
SELECT
 
      poh.po_header_id, poh.CREATION_DATE,
 
      poh.type_lookup_code PO_TYPE,
 
      poh.authorization_status PO_STATUS,
 
      poh.segment1 PO_NUMBER,
 
      por.RELEASE_NUM,
 
      pov.vendor_name SUPPLIER_NAME,
 
      povs.vendor_site_code Location,
 
      hrls.location_code Ship_To,
 
      hrlb.location_code Bill_to,
 
      pol.line_num,
 
      msib.segment1 Item, msib.DESCRIPTION,
 
      pol.unit_price,
 
      pol.quantity,
 
      pod.amount_billed Amount,
 
      pod.destination_subinventory,
 
      ppf.full_name Buyer_Name,
 
      poh.closed_Code
 
    FROM
 
      PO_HEADERS_ALL poh,
 
      PO_LINES_ALL pol,
 
      mtl_system_items_b msib,
 
      PO_LINE_LOCATIONS_ALL poll,
 
      PO_DISTRIBUTIONS_ALL pod,
 
      po_vendors pov,
 
      po_vendor_sites_All povs,
 
      hr_locations_all hrls,
 
      hr_locations_all hrlb,
 
      per_all_people_f ppf,
 
      po_line_types polt,
 
      PO_RELEASES_ALL por
 
    WHERE
 
      1 = 1
 
      AND polt.line_type_id     = pol.line_type_id
 
      AND povs.vendor_site_id   = poh.vendor_site_id
 
      AND pov.vendor_id         = poh.vendor_id
 
      AND pol.item_id           = msib.inventory_item_id
 
      AND msib.organization_id  = 83
 
      AND poh.po_header_id      = pol.po_header_id
 
      AND pol.po_line_id        = pod.po_line_id
 
      AND poll.line_location_id = pod.line_location_id
 
      AND poh.ship_to_location_id = hrls.location_id
 
      AND poh.bill_to_location_id = hrlb.location_id
 
      AND poh.agent_id          = ppf.person_id
 
      and poh.PO_HEADER_ID = por.PO_HEADER_ID(+)
 
      AND poh.segment1          = :lpo_number
      '''
   
    query_GRN__Details = '''SELECT a.po_header_id,
         a.org_id,
         a.segment1 po_no,
         a.creation_date order_date,
         b.segment1 vendor_code,
         b.vendor_name,
         c.vendor_site_code,
         c.address_line1,
         c.address_line2,
         c.address_line3,
         c.city || ' ' || c.state || ' ' || c.zip || ' ' || c.country
            city_country,
         b.vendor_id,
         c.vendor_site_id,
         d.receipt_num grn_no,
         d.creation_date receipt_date,
         d.shipment_num || ' ' || d.shipped_date supplier_inv_date,
         d.num_of_containers container_id,
         d.comments remarks,
         d.shipment_header_id,
         f.shipment_line_id,
         g.segment1 item_code,
         f.item_id,
         g.description item_name,
         g.primary_uom_code uom,
         e.quantity,
         d.receipt_num,
         h.subinventory
    FROM po_headers_all a,
         po_vendors b,
         po_vendor_sites_all c,
         rcv_shipment_headers_v d,
         po_lines_all e,
         rcv_shipment_lines f,
         mtl_system_items g,
         rcv_transactions h
   WHERE     a.vendor_id = b.vendor_id
         AND a.vendor_site_id = c.vendor_site_id
         AND b.vendor_id = c.vendor_id
         AND a.vendor_id = d.vendor_id
         AND a.vendor_site_id = d.vendor_site_id
         AND a.po_header_id = e.po_header_id
         AND d.shipment_header_id = f.shipment_header_id
         AND f.po_header_id = e.po_header_id
         AND f.po_line_id = e.po_line_id
         AND f.item_id IS NOT NULL
         AND f.po_header_id = a.po_header_id
         AND f.item_id = g.inventory_item_id(+)
         AND f.to_organization_id = g.organization_id(+)
         AND f.shipment_header_id = h.shipment_header_id
         AND f.shipment_line_id = h.shipment_line_id
         AND UPPER (h.transaction_type) = 'DELIVER'
         AND H.INSPECTION_STATUS_CODE != 'REJECTED'
         AND TO_NUMBER (a.segment1) =
                NVL (TO_NUMBER (:p_lpo_numbers), TO_NUMBER (a.segment1))'''
    dsn = "TEST"
    username = "Apps"
    password = "apps085"
    
    lpo_df = pd.DataFrame()
    grn_df = pd.DataFrame()
    print(lpo_numbers)
    # Initialize connection and cursor outside the try block to prevent reference errors
    connection = None
    cursor = None
    
    try:
        if lpo_numbers:
            connection = cx_Oracle.connect(username, password, dsn)
            cursor = connection.cursor()

            
            cursor.execute(query_3, lpo_number=lpo_numbers)
            results = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            df = pd.DataFrame(results, columns=columns)
            lpo_df = pd.concat([lpo_df, df], ignore_index=True)
            lpo_df.to_excel('lpo_df.xlsx')

            
            print("lpo:", lpo_numbers)
            cursor.execute(query_GRN__Details, p_lpo_numbers=lpo_numbers)
            results = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            df = pd.DataFrame(results, columns=columns)
            grn_df = pd.concat([grn_df, df], ignore_index=True)
            grn_df.to_excel('grn_df.xlsx')

    except cx_Oracle.DatabaseError as e:
        print(f"Database error: {e}")
    finally:
        # Check if cursor and connection were initialized, and close them if they were
        if cursor:
            cursor.close()
        if connection:
            connection.close()



    if lpo_df.empty and grn_df.empty:
        return {"message": "LPO and GRN details not found"}
    elif lpo_df.empty:
        return {"message": "LPO details not found", "GRn_details": grn_df.to_dict(orient='records')}
    elif grn_df.empty:
        return {"Lpo_details": lpo_df.to_dict(orient='records'), "message": "GRN details not found"}
    else :

        

            # return {"Lpo_details": lpo_df.to_dict(orient='records'), "GRn_details": grn_df.to_dict(orient='records')}

            # Semantic matching for all invoice items with all LPO and GRN entries

            df_invoice = pd.read_excel('invoice_data.xlsx')
            df_invoice.drop(columns=['Unnamed: 0'],inplace=True)
            # model = SentenceTransformer('all-MiniLM-L6-v2')
            invoice_descriptions = df_invoice['description'].astype(str).tolist()
            print("invoice_descriptions:",invoice_descriptions)
            lpo_descriptions = lpo_df['DESCRIPTION'].astype(str).tolist()
            grn_descriptions = grn_df['ITEM_NAME'].astype(str).tolist()

            # invoice_emb = model.encode(invoice_descriptions, convert_to_tensor=True)
            # lpo_emb = model.encode(lpo_descriptions, convert_to_tensor=True)
            # grn_emb = model.encode(grn_descriptions, convert_to_tensor=True)

            # lpo_sim = util.cos_sim(grn_emb, lpo_emb)
            # grn_sim = util.cos_sim(lpo_emb, grn_emb)

            # lpo_top_matches = torch.argmax(lpo_sim, dim=1)
            # grn_top_matches = torch.argmax(grn_sim, dim=1)

            # Function to get embeddings from OpenAI
            def get_embeddings(texts):
              response = client.embeddings.create(
              model="text-embedding-ada-002",
              input=texts
          )
          
            # Serialize the response to a dictionary
              response_dict = response.model_dump()
              return [embedding['embedding'] for embedding in response_dict['data']]

                      # Get embeddings for each description set
            # Compute embeddings for all descriptions
            grn_emb = np.array(get_embeddings(grn_descriptions))
            lpo_emb = np.array(get_embeddings(lpo_descriptions))
            invoice_emb = np.array(get_embeddings(invoice_descriptions))

            # Helper function for matrix cosine similarity
            def cosine_similarity_matrix(emb1, emb2):
                norm1 = np.linalg.norm(emb1, axis=1, keepdims=True)
                norm2 = np.linalg.norm(emb2, axis=1, keepdims=True)
                norm1 = np.where(norm1 == 0, 1, norm1)
                norm2 = np.where(norm2 == 0, 1, norm2)
                emb1_norm = emb1 / norm1
                emb2_norm = emb2 / norm2
                return np.dot(emb1_norm, emb2_norm.T)

            # Compute similarity matrices
            grn_lpo_sim_matrix = cosine_similarity_matrix(grn_emb, lpo_emb)
            invoice_lpo_sim_matrix = cosine_similarity_matrix(invoice_emb, lpo_emb)
            invoice_grn_sim_matrix = cosine_similarity_matrix(invoice_emb, grn_emb)

            # Find best matches
            grn_to_lpo_indices = np.argmax(grn_lpo_sim_matrix, axis=1)
            lpo_to_grn_indices = np.argmax(grn_lpo_sim_matrix, axis=0)
            invoice_to_lpo_indices = np.argmax(invoice_lpo_sim_matrix, axis=1)
            invoice_to_grn_indices = np.argmax(invoice_grn_sim_matrix, axis=1)

            # Assign to dataframes
            grn_df['Matched_LPO_Description'] = [lpo_descriptions[i] for i in grn_to_lpo_indices]
            grn_df['LPO_Similarity'] = [round(float(grn_lpo_sim_matrix[j, i]), 2) for j, i in enumerate(grn_to_lpo_indices)]

            lpo_df['Matched_GRN_Description'] = [grn_descriptions[i] for i in lpo_to_grn_indices]
            lpo_df['GRN_Similarity'] = [round(float(grn_lpo_sim_matrix[i, j]), 2) for j, i in enumerate(lpo_to_grn_indices)]

            df_invoice['Matched_LPO_Description'] = [lpo_descriptions[i] for i in invoice_to_lpo_indices]
            df_invoice['Matched_GRN_Description'] = [grn_descriptions[i] for i in invoice_to_grn_indices]
            df_invoice['LPO_Similarity'] = [round(float(invoice_lpo_sim_matrix[j, i]), 2) for j, i in enumerate(invoice_to_lpo_indices)]
            df_invoice['GRN_Similarity'] = [round(float(invoice_grn_sim_matrix[j, i]), 2) for j, i in enumerate(invoice_to_grn_indices)]
            # df_invoice.drop(['Unnamed: 0'],inplace=True)
            df_invoice.to_excel("invoice_validation.xlsx")

            lpo_df = lpo_df[['DESCRIPTION', 'UNIT_PRICE', 'QUANTITY']]
            grn_df = grn_df[['ITEM_NAME', 'QUANTITY']]

            # Rename columns using the 'columns' keyword argument
            lpo_df.rename(columns={"DESCRIPTION": "Matched_LPO_Description", "UNIT_PRICE": "LPO_UNIT_PRICE", "QUANTITY": "LPO_QUANTITY"}, inplace=True)
            grn_df.rename(columns={"ITEM_NAME": "Matched_GRN_Description", "QUANTITY": "GRN_QUANTITY"}, inplace=True)

            # First, merge df_invoice with lpo_df on 'Matched_LPO_Description'
            merged_df = df_invoice.merge(lpo_df, on='Matched_LPO_Description', how='left')

            # Then, merge the resulting DataFrame with grn_df on 'Matched_GRN_Description'
            final_df = merged_df.merge(grn_df, on='Matched_GRN_Description', how='left')



            if (df_invoice['LPO_Similarity'] < 0.75).any() :
                  # Assuming 'invoice_df' is the DataFrame you want to store
              # Setup the SQL connection
              # engine = create_engine('your_database_connection_string')

              # Store the invoice_df into 'reconciliation_data' table if the condition is met
              final_df['Error_state'] = "Line_Item"
              final_df.to_sql('reconciliation_data', con=engine, if_exists='replace', index=False)

              return {"Message" : "Data Saved to Reconcillateion stage mismatch in subtotal and tax amount"}  
            else :
                final_df.to_sql('Saved_Data', con=engine, if_exists='replace', index=False)  
                return {"Message" : "Data Saved to saved page"}