import pandas as pd
import re
import cx_Oracle
import pandas as pd  # Import pandas for DataFrame operations
from flask import Flask, jsonify, make_response
from rapidfuzz import fuzz, process

# @app.route('/ask', methods=['POST'])
def LPO(data):
       

# Simulating request.json (This will be the actual data received in a Flask API)
    data = data
    

    # Initialize empty DataFrame and lists
    df_delivery_notes = pd.DataFrame()
    deliveryNoteNumbers = []
    lpo_numbers = []
    lpo_df=pd.DataFrame()

    # Handle "delivery_notes" (Convert to DataFrame)
    if isinstance(data, dict):
        if "deliveryNoteItems" in data:
            delivery_notes_list = data["deliveryNoteItems"]
            
            if isinstance(delivery_notes_list, list):  # Ensure it's a list
                df_delivery_notes = pd.DataFrame(delivery_notes_list)

        # Handle "delivery_note_mappings" (Extract DN and LPO numbers into lists)
        if "deliveryNotes" in data:
                delivery_mappings = data["deliveryNotes"]
                
                if isinstance(delivery_mappings, list):  # Ensure it's a list
                    for item in delivery_mappings:
                        dn_value = item.get("deliveryNoteNumber", "")
                        lpo_value = item.get("lpoNumbers", "")

                        # Ensure values are always lists, even if they are single items
                        if not isinstance(dn_value, list):
                            dn_value = [dn_value]
                        if not isinstance(lpo_value, list):
                            lpo_value = [lpo_value]

                        # Extend lists with extracted values
                        deliveryNoteNumbers.extend(dn_value)
                        lpo_numbers.extend(lpo_value)

    # Print results
    print("Delivery Notes DataFrame:\n", "Done")
    print("Delivery Note Numbers List:", "Done")
    print("LPO Numbers List:", "Done")

    query_2 = '''SELECT

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

      and poh.PO_HEADER_ID = por.PO_HEADER_ID

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
                NVL (TO_NUMBER (:p_po_no), TO_NUMBER (a.segment1))'''
   

    dsn = "TEST"
    username = "Apps"
    password = "apps085"

    if lpo_numbers:
        try:
            connection = cx_Oracle.connect(username, password, dsn)
            cursor = connection.cursor()

            for lpo in lpo_numbers:
                cursor.execute(query_2, lpo_number=lpo)
                results = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
                df = pd.DataFrame(results, columns=columns)
                lpo_df = pd.concat([lpo_df, df], ignore_index=True)

     

            for lpo in lpo_numbers:
                cursor.execute(query_GRN__Details, lpo_number=lpo)
                results = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
                df = pd.DataFrame(results, columns=columns)
                grn_df = pd.concat([grn_df, df], ignore_index=True)

        except cx_Oracle.DatabaseError as e:
            print("Database error (GRN):", e)
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    

    lpo_#df.to_excel('lpo_df.xlsx')
    grn_#df.to_excel('grn_df.xlsx')

   

    return {
        "Lpo_details": lpo_df,
        "GRn_details": grn_df,
        
    }
