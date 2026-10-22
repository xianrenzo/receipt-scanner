import pytest
import openpyxl
import io
from excel_export import ExcelExporter


class TestExcelExport:
    @pytest.fixture
    def exporter(self):
        return ExcelExporter()

    @pytest.fixture
    def sample_receipts(self):
        return [
            {
                'id': 1,
                'merchant_name': 'STORE A',
                'branch_name': 'Branch 1',
                'address': '123 Main St',
                'city': 'Manila',
                'country': 'Philippines',
                'contact_number': '+632-123-4567',
                'website_email': 'store@a.com',
                'merchant_tin': '123-456-789-000',
                'receipt_number': 'RCPT-001',
                'transaction_ref': 'TXN-001',
                'invoice_number': 'INV-001',
                'order_number': 'ORD-001',
                'terminal_number': 'TERM-01',
                'transaction_date': '2026-10-20',
                'transaction_time': '14:30:00',
                'currency': 'PHP',
                'currency_symbol': '₱',
                'payment_method': 'Cash',
                'card_brand': None,
                'masked_card_number': None,
                'transaction_status': 'Completed',
                'cashier_name': 'John Doe',
                'subtotal': 120.00,
                'item_discounts': 0.00,
                'transaction_discounts': 0.00,
                'total_discounts': 0.00,
                'amount_before_tax': 120.00,
                'vat_tax': 0.00,
                'taxable_sales': 120.00,
                'vat_exempt_sales': 0.00,
                'zero_rated_sales': 0.00,
                'other_taxes_fees': 0.00,
                'service_charge': 0.00,
                'delivery_fee': 0.00,
                'packaging_fee': 0.00,
                'tips_gratuity': 0.00,
                'rounding_adjustment': 0.00,
                'grand_total': 120.00,
                'amount_paid': 150.00,
                'cash_received': 150.00,
                'change_given': 30.00,
                'outstanding_balance': 0.00,
                'validation_status': 'Verified',
                'review_status': 'Reviewed',
                'created_at': '2026-10-20T14:30:00',
                'updated_at': '2026-10-20T14:30:00',
                'original_image_path': '/uploads/receipt_1.jpg',
                'items': [
                    {
                        'id': 1,
                        'description': 'Notebook',
                        'quantity': 2,
                        'unit_price': 50.00,
                        'discount': 0.00,
                        'tax': 0.00,
                        'line_total': 100.00,
                        'extraction_evidence': 'Notebook 2 50.00 100.00'
                    },
                    {
                        'id': 2,
                        'description': 'Pen',
                        'quantity': 1,
                        'unit_price': 20.00,
                        'discount': 0.00,
                        'tax': 0.00,
                        'line_total': 20.00,
                        'extraction_evidence': 'Pen 1 20.00 20.00'
                    }
                ],
                'warnings': [],
                'validation_checks': {'items': True, 'subtotal': True, 'discounts': True, 'tax': True, 'grand_total': True, 'payment': True, 'dates': True}
            },
            {
                'id': 2,
                'merchant_name': 'STORE B',
                'branch_name': None,
                'address': None,
                'city': None,
                'country': None,
                'contact_number': None,
                'website_email': None,
                'merchant_tin': None,
                'receipt_number': 'RCPT-002',
                'transaction_ref': None,
                'invoice_number': None,
                'order_number': None,
                'terminal_number': None,
                'transaction_date': '2026-10-21',
                'transaction_time': '10:00:00',
                'currency': 'USD',
                'currency_symbol': '$',
                'payment_method': 'Credit Card',
                'card_brand': 'Visa',
                'masked_card_number': '****1234',
                'transaction_status': 'Completed',
                'cashier_name': None,
                'subtotal': 50.00,
                'item_discounts': 5.00,
                'transaction_discounts': 0.00,
                'total_discounts': 5.00,
                'amount_before_tax': 45.00,
                'vat_tax': 4.50,
                'taxable_sales': 45.00,
                'vat_exempt_sales': 0.00,
                'zero_rated_sales': 0.00,
                'other_taxes_fees': 0.00,
                'service_charge': 0.00,
                'delivery_fee': 0.00,
                'packaging_fee': 0.00,
                'tips_gratuity': 0.00,
                'rounding_adjustment': 0.00,
                'grand_total': 49.50,
                'amount_paid': 49.50,
                'cash_received': None,
                'change_given': None,
                'outstanding_balance': 0.00,
                'validation_status': 'Needs Review',
                'review_status': 'Unreviewed',
                'created_at': '2026-10-21T10:00:00',
                'updated_at': '2026-10-21T10:00:00',
                'original_image_path': '/uploads/receipt_2.jpg',
                'items': [
                    {
                        'id': 3,
                        'description': 'Widget',
                        'quantity': 1,
                        'unit_price': 50.00,
                        'discount': 5.00,
                        'tax': 4.50,
                        'line_total': 49.50,
                        'extraction_evidence': 'Widget 1 50.00 49.50'
                    }
                ],
                'warnings': ['Sum of item totals (49.50) ≠ Stated subtotal (50.00)'],
                'validation_checks': {'items': False, 'subtotal': False, 'discounts': True, 'tax': True, 'grand_total': True, 'payment': True, 'dates': True}
            }
        ]

    def test_export_multiple_receipts(self, exporter, sample_receipts):
        excel_data = exporter.export_receipts(sample_receipts, include_ocr=False)
        
        assert len(excel_data) > 0
        
        wb = openpyxl.load_workbook(io.BytesIO(excel_data))
        
        assert 'Receipts' in wb.sheetnames
        assert 'Receipt Items' in wb.sheetnames
        assert 'Validation' in wb.sheetnames
        assert 'OCR Text' not in wb.sheetnames
        
        ws_receipts = wb['Receipts']
        assert ws_receipts.max_row == 3  # header + 2 receipts
        assert ws_receipts.max_column >= 45
        
        ws_items = wb['Receipt Items']
        assert ws_items.max_row == 4  # header + 3 items
        
        ws_validation = wb['Validation']
        assert ws_validation.max_row == 3  # header + 2 receipts

    def test_export_with_ocr(self, exporter, sample_receipts):
        sample_receipts[0]['raw_ocr_text'] = 'Sample OCR text for receipt 1'
        sample_receipts[1]['raw_ocr_text'] = 'Sample OCR text for receipt 2'
        
        excel_data = exporter.export_receipts(sample_receipts, include_ocr=True)
        
        wb = openpyxl.load_workbook(io.BytesIO(excel_data))
        assert 'OCR Text' in wb.sheetnames
        
        ws_ocr = wb['OCR Text']
        assert ws_ocr.max_row == 3

    def test_export_single_receipt(self, exporter, sample_receipts):
        excel_data = exporter.export_single_receipt(sample_receipts[0])
        
        assert len(excel_data) > 0
        
        wb = openpyxl.load_workbook(io.BytesIO(excel_data))
        
        assert 'Receipt' in wb.sheetnames
        assert 'Items' in wb.sheetnames
        
        ws_receipt = wb['Receipt']
        assert ws_receipt.max_row >= 40
        
        ws_items = wb['Items']
        assert ws_items.max_row == 3  # header + 2 items

    def test_currency_preservation(self, exporter, sample_receipts):
        excel_data = exporter.export_receipts(sample_receipts)
        
        wb = openpyxl.load_workbook(io.BytesIO(excel_data))
        ws_receipts = wb['Receipts']
        
        row1_currency = ws_receipts.cell(row=2, column=17).value  # Currency column
        row1_total = ws_receipts.cell(row=2, column=39).value  # Grand Total column
        
        row2_currency = ws_receipts.cell(row=3, column=17).value
        row2_total = ws_receipts.cell(row=3, column=39).value
        
        assert row1_currency == 'PHP'
        assert row1_total == 120.00
        assert row2_currency == 'USD'
        assert row2_total == 49.50

    def test_missing_values_handled(self, exporter, sample_receipts):
        excel_data = exporter.export_receipts(sample_receipts)
        
        wb = openpyxl.load_workbook(io.BytesIO(excel_data))
        ws_receipts = wb['Receipts']
        
        # Check that missing optional fields are handled (either empty string or None)
        branch_val = ws_receipts.cell(row=3, column=3).value
        addr_val = ws_receipts.cell(row=3, column=4).value
        assert branch_val in ('', None)
        assert addr_val in ('', None)

    def test_formula_injection_prevention(self, exporter):
        dangerous_receipts = [{
            'id': 1,
            'merchant_name': '=CMD|"/C calc"!A1',
            'transaction_date': '2026-10-20',
            'currency': 'PHP',
            'grand_total': 100.00,
            'validation_status': 'Verified',
            'review_status': 'Reviewed',
            'created_at': '2026-10-20',
            'updated_at': '2026-10-20',
            'original_image_path': '',
            'items': [],
            'warnings': [],
            'validation_checks': {}
        }]
        
        excel_data = exporter.export_receipts(dangerous_receipts)
        
        wb = openpyxl.load_workbook(io.BytesIO(excel_data))
        ws = wb['Receipts']
        
        cell_value = ws.cell(row=2, column=2).value
        assert cell_value.startswith("'")
        assert "=CMD" not in cell_value or cell_value.startswith("'")

    def test_number_formatting(self, exporter, sample_receipts):
        excel_data = exporter.export_receipts(sample_receipts)
        
        wb = openpyxl.load_workbook(io.BytesIO(excel_data))
        ws_receipts = wb['Receipts']
        
        cell = ws_receipts.cell(row=2, column=40)  # Grand Total
        assert cell.number_format == '#,##0.00'
        
        ws_items = wb['Receipt Items']
        cell = ws_items.cell(row=2, column=8)  # Line Total
        assert cell.number_format == '#,##0.00'

    def test_date_formatting(self, exporter, sample_receipts):
        excel_data = exporter.export_receipts(sample_receipts)
        
        wb = openpyxl.load_workbook(io.BytesIO(excel_data))
        ws_receipts = wb['Receipts']
        
        cell = ws_receipts.cell(row=2, column=15)  # Transaction Date
        assert cell.number_format == 'YYYY-MM-DD'

    def test_frozen_panes_and_filters(self, exporter, sample_receipts):
        excel_data = exporter.export_receipts(sample_receipts)
        
        wb = openpyxl.load_workbook(io.BytesIO(excel_data))
        ws_receipts = wb['Receipts']
        
        assert ws_receipts.freeze_panes == 'A2'
        assert ws_receipts.auto_filter.ref is not None

    def test_column_widths(self, exporter, sample_receipts):
        excel_data = exporter.export_receipts(sample_receipts)
        
        wb = openpyxl.load_workbook(io.BytesIO(excel_data))
        ws_receipts = wb['Receipts']
        
        for col_idx in range(1, ws_receipts.max_column + 1):
            width = ws_receipts.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width
            assert width >= 10
            assert width <= 55

    def test_validation_sheet_content(self, exporter, sample_receipts):
        excel_data = exporter.export_receipts(sample_receipts)
        
        wb = openpyxl.load_workbook(io.BytesIO(excel_data))
        ws = wb['Validation']
        
        row2_status = ws.cell(row=2, column=6).value
        row3_status = ws.cell(row=3, column=6).value
        
        assert row2_status == 'Verified'
        assert row3_status == 'Needs Review'
        
        row3_warnings = ws.cell(row=3, column=7).value
        assert 'Sum of item totals' in row3_warnings