import cx_Oracle
from datetime import datetime


class InvoiceApiHandler:
    def __init__(self, dsn, username, password):
        self.dsn = dsn
        self.username = username
        self.password = password
        self.connection = None
        self.cursor = None

    def _parse_date(self, date_str):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    def _call_grn_api(self):
        self.connection = cx_Oracle.connect(self.username, self.password, self.dsn)
        self.cursor = self.connection.cursor()
        plsql = """
        DECLARE
            errbuf VARCHAR2(100);
            retcode VARCHAR2(100);
        BEGIN
            xxpw_ap_inv_intf_pkg.main(errbuf, retcode);
        END;
        """
        self.cursor.execute(plsql)

    def insert_data_and_call_api(self, data_list):
        insert_sql = """
        INSERT INTO xxpw_ap_invoices_stg (
            interface_header_id,
            ap_interface_line_id,
            invoice_number,
            invoice_date,
            invoice_type,
            description,
            invoice_amount,
            tax_amount,
            amount_wo_tax,
            amount_with_tax,
            supplier_number,
            supplier_name,
            supplier_site,
            cuin_number,
            invoice_currency,
            line_number,
            item_code,
            inventory_item_id,
            line_amount,
            quantity,
            unit_price,
            unit_of_measure,
            gl_account,
            grn_number,
            grn_line_number,
            po_number,
            po_line_number,
            invoice_received_date,
            interface_flag,
            error_message,
            conc_request_id,
            creation_date,
            created_by,
            last_update_date,
            last_updated_by,
            job_id
        ) VALUES (
            :interface_header_id,
            :ap_interface_line_id,
            :invoice_number,
            :invoice_date,
            :invoice_type,
            :description,
            :invoice_amount,
            :tax_amount,
            :amount_wo_tax,
            :amount_with_tax,
            :supplier_number,
            :supplier_name,
            :supplier_site,
            :cuin_number,
            :invoice_currency,
            :line_number,
            :item_code,
            :inventory_item_id,
            :line_amount,
            :quantity,
            :unit_price,
            :unit_of_measure,
            :gl_account,
            :grn_number,
            :grn_line_number,
            :po_number,
            :po_line_number,
            :invoice_received_date,
            :interface_flag,
            :error_message,
            :conc_request_id,
            :creation_date,
            :created_by,
            :last_update_date,
            :last_updated_by,
            :job_id
        )
        """

        try:
            self.connection = cx_Oracle.connect(self.username, self.password, self.dsn)
            self.cursor = self.connection.cursor()

            batch_data = []
            for row in data_list:
                batch_data.append({
                    "interface_header_id":  row.get("INTERFACE_HEADER_ID"),
                    "ap_interface_line_id": row.get("AP_INTERFACE_LINE_ID"),
                    "invoice_number":       row.get("INVOICE_NUMBER"),
                    "invoice_date":         self._parse_date(row.get("INVOICE_DATE")),
                    "invoice_type":         row.get("INVOICE_TYPE") or "STANDARD",
                    "description":          row.get("DESCRIPTION"),
                    "invoice_amount":       row.get("INVOICE_AMOUNT"),
                    "tax_amount":           row.get("TAX_AMOUNT"),
                    "amount_wo_tax":        row.get("AMOUNT_WO_TAX"),
                    "amount_with_tax":      row.get("AMOUNT_WITH_TAX"),
                    "supplier_number":      row.get("SUPPLIER_NUMBER"),
                    "supplier_name":        row.get("SUPPLIER_NAME"),
                    "supplier_site":        row.get("SUPPLIER_SITE"),
                    "cuin_number":          row.get("CUIN_NUMBER"),
                    "invoice_currency":     row.get("INVOICE_CURRENCY"),
                    "line_number":          row.get("LINE_NUMBER"),
                    "item_code":            row.get("ITEM_CODE"),
                    "inventory_item_id":    row.get("INVENTORY_ITEM_ID"),
                    "line_amount":          row.get("LINE_AMOUNT"),
                    "quantity":             row.get("QUANTITY"),
                    "unit_price":           row.get("UNIT_PRICE"),
                    "unit_of_measure":      row.get("UNIT_OF_MEASURE"),
                    "gl_account":           row.get("GL_ACCOUNT"),
                    "grn_number":           row.get("GRN_NUMBER"),
                    "grn_line_number":      row.get("GRN_LINE_NUMBER"),
                    "po_number":            row.get("PO_NUMBER"),
                    "po_line_number":       row.get("PO_LINE_NUMBER"),
                    "invoice_received_date": self._parse_date(row.get("INVOICE_RECEIVED_DATE")),
                    "interface_flag":        row.get("INTERFACE_FLAG") or "N",
                    "error_message":         row.get("ERROR_MESSAGE"),
                    "conc_request_id":       row.get("CONC_REQUEST_ID"),
                    "creation_date":         self._parse_date(row.get("CREATION_DATE")) or datetime.now(),
                    "created_by":            row.get("CREATED_BY"),
                    "last_update_date":      self._parse_date(row.get("LAST_UPDATE_DATE")) or datetime.now(),
                    "last_updated_by":       row.get("LAST_UPDATED_BY"),
                    "job_id":                row.get("JOB_ID")
                })

            self.cursor.executemany(insert_sql, batch_data)
            self.connection.commit()

            print("Data inserted into staging table")

            # # Call stored procedure twice
            self._call_grn_api()
            self._call_grn_api()

            print("ERP EXECUTION done")

            return "sucess"

        except cx_Oracle.Error as error:
            print("Oracle error:", error)
            return None

        finally:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
