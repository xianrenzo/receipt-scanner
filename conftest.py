import pytest
import tempfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import ReceiptDatabase


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db = ReceiptDatabase(db_path)
    yield db
    
    os.unlink(db_path)


@pytest.fixture
def sample_receipt_data():
    return {
        'merchant_name': 'SAMPLE STORE',
        'branch_name': 'Main Branch',
        'address': '123 Main St',
        'city': 'Manila',
        'country': 'Philippines',
        'contact_number': '+632-123-4567',
        'website_email': 'sample@store.com',
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
        'raw_ocr_text': 'Sample OCR text',
        'validation_status': 'Verified',
        'review_status': 'Reviewed'
    }


@pytest.fixture
def sample_items():
    return [
        {
            'description': 'Notebook',
            'quantity': 2,
            'unit_price': 50.00,
            'discount': 0.00,
            'tax': 0.00,
            'line_total': 100.00,
            'extraction_evidence': 'Notebook 2 50.00 100.00'
        },
        {
            'description': 'Pen',
            'quantity': 1,
            'unit_price': 20.00,
            'discount': 0.00,
            'tax': 0.00,
            'line_total': 20.00,
            'extraction_evidence': 'Pen 1 20.00 20.00'
        }
    ]