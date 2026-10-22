import pytest
from receipt_extractor import ReceiptExtractor, ReceiptData, ReceiptItem
from validator import FinancialValidator, ValidationResult


class TestReceiptExtractor:
    @pytest.fixture
    def extractor(self):
        return ReceiptExtractor()

    def test_currency_detection_php(self, extractor):
        text = "Total: ₱1,250.00"
        currency, symbol = extractor.detect_currency(text)
        assert currency == 'PHP'
        assert symbol == '₱'
        
        text = "Total: PHP 1,250.00"
        currency, symbol = extractor.detect_currency(text)
        assert currency == 'PHP'
        
        text = "Total: P 1,250.00"
        currency, symbol = extractor.detect_currency(text)
        assert currency == 'PHP'

    def test_currency_detection_usd(self, extractor):
        text = "Total: $100.00"
        currency, symbol = extractor.detect_currency(text)
        assert currency == 'USD'
        assert symbol == '$'

    def test_currency_detection_eur(self, extractor):
        text = "Total: €100.00"
        currency, symbol = extractor.detect_currency(text)
        assert currency == 'EUR'
        assert symbol == '€'

    def test_amount_parsing(self, extractor):
        assert extractor.parse_amount("1,250.00") == 1250.00
        assert extractor.parse_amount("₱1,250.00") == 1250.00
        assert extractor.parse_amount("PHP 1,250.00") == 1250.00
        assert extractor.parse_amount("1250.00") == 1250.00
        assert extractor.parse_amount("1.250,00") == 1250.00  # European format now supported
        assert extractor.parse_amount("invalid") is None
        assert extractor.parse_amount(None) is None

    def test_date_extraction(self, extractor):
        assert extractor.extract_date("Date: 2026-10-20") == "2026-10-20"
        assert extractor.extract_date("Date: 20/10/2026") == "2026-10-20"
        assert extractor.extract_date("Date: 10/20/2026") == "2026-10-20"
        assert extractor.extract_date("Date: Oct 20, 2026") == "2026-10-20"
        assert extractor.extract_date("Date: 20 Oct 2026") == "2026-10-20"
        assert extractor.extract_date("No date here") is None

    def test_time_extraction(self, extractor):
        assert extractor.extract_time("Time: 14:30:00") == "14:30:00"
        assert extractor.extract_time("Time: 2:30 PM") == "14:30:00"
        assert extractor.extract_time("Time: 14.30.00") == "14:30:00"
        assert extractor.extract_time("No time here") is None

    def test_merchant_extraction(self, extractor):
        lines = [
            "SAMPLE STORE",
            "123 Main Street",
            "Manila, Philippines",
            "Tel: +632-123-4567",
            "TIN: 123-456-789-000"
        ]
        result = extractor.extract_merchant_info(lines)
        assert result['merchant_name'] == 'SAMPLE STORE'
        assert result['address'] == '123 Main Street'
        assert 'Manila' in result.get('city', '')
        assert result['contact_number'] is not None
        assert result['merchant_tin'] == '123-456-789-000'

    def test_transaction_extraction(self, extractor):
        lines = [
            "OR No: 12345",
            "Invoice: INV-001",
            "Terminal: 01",
            "Cashier: John Doe",
            "Payment: Cash",
            "Card: ****1234"
        ]
        result = extractor.extract_transaction_info(lines)
        assert result['receipt_number'] == '12345'
        assert result['invoice_number'] == 'INV-001'
        assert result['terminal_number'] == '01'
        assert result['cashier_name'] == 'John Doe'
        assert result['payment_method'] == 'Cash'
        assert result['masked_card_number'] == '****1234'

    def test_financial_extraction(self, extractor):
        lines = [
            "Subtotal: 100.00",
            "VAT: 12.00",
            "Total: 112.00",
            "Cash: 200.00",
            "Change: 88.00"
        ]
        result = extractor.extract_financial_summary(lines)
        assert result['subtotal'] == 100.00
        assert result['vat_tax'] == 12.00
        assert result['grand_total'] == 112.00
        assert result['amount_paid'] == 200.00
        assert result['change_given'] == 88.00

    def test_full_extraction(self, extractor):
        ocr_result = {
            'text': 'SAMPLE STORE\n123 Main St\nManila\nDate: 2026-10-20\nTime: 14:30\nSubtotal: 120.00\nTax: 0.00\nTotal: 120.00\nCash: 150.00\nChange: 30.00\nNotebook 2 50.00 100.00\nPen 1 20.00 20.00',
            'lines': [
                'SAMPLE STORE',
                '123 Main St',
                'Manila',
                'Date: 2026-10-20',
                'Time: 14:30',
                'Subtotal: 120.00',
                'Tax: 0.00',
                'Total: 120.00',
                'Cash: 150.00',
                'Change: 30.00',
                'Notebook 2 50.00 100.00',
                'Pen 1 20.00 20.00'
            ]
        }
        
        receipt = extractor.extract(ocr_result)
        
        assert receipt.merchant_name == 'SAMPLE STORE'
        assert receipt.transaction_date == '2026-10-20'
        assert receipt.transaction_time == '14:30:00'
        assert receipt.currency == 'PHP'
        assert receipt.subtotal == 120.00
        assert receipt.vat_tax == 0.00
        assert receipt.grand_total == 120.00
        assert receipt.amount_paid == 150.00
        assert receipt.change_given == 30.00
        assert len(receipt.items) == 2
        assert receipt.items[0].description == 'Notebook'
        assert receipt.items[0].quantity == 2
        assert receipt.items[0].unit_price == 50.00
        assert receipt.items[0].line_total == 100.00


class TestFinancialValidator:
    @pytest.fixture
    def validator(self):
        return FinancialValidator(tolerance=0.02)

    def test_valid_receipt(self, validator):
        receipt = ReceiptData(
            merchant_name='TEST STORE',
            transaction_date='2026-10-20',
            currency='PHP',
            subtotal=120.00,
            vat_tax=0.00,
            grand_total=120.00,
            amount_paid=150.00,
            change_given=30.00,
            items=[
                ReceiptItem(description='Notebook', quantity=2, unit_price=50.00, line_total=100.00),
                ReceiptItem(description='Pen', quantity=1, unit_price=20.00, line_total=20.00)
            ]
        )
        
        result = validator.validate(receipt)
        
        assert result.is_valid is True
        assert result.status == 'Verified'
        assert len(result.errors) == 0

    def test_explicit_zero_tax_vs_missing_tax(self, validator):
        receipt_with_zero = ReceiptData(
            merchant_name='TEST',
            transaction_date='2026-10-20',
            currency='PHP',
            subtotal=100.00,
            vat_tax=0.00,
            grand_total=100.00,
            items=[ReceiptItem(description='Item', quantity=1, unit_price=100.00, line_total=100.00)]
        )
        
        receipt_missing_tax = ReceiptData(
            merchant_name='TEST',
            transaction_date='2026-10-20',
            currency='PHP',
            subtotal=100.00,
            vat_tax=None,
            grand_total=100.00,
            items=[ReceiptItem(description='Item', quantity=1, unit_price=100.00, line_total=100.00)]
        )
        
        result_zero = validator.validate(receipt_with_zero)
        result_missing = validator.validate(receipt_missing_tax)
        
        assert result_zero.status == 'Verified'
        assert result_missing.status == 'Needs Review'
        assert any('tax' in w.lower() or 'vat' in w.lower() for w in result_missing.warnings)

    def test_item_validation(self, validator):
        receipt = ReceiptData(
            merchant_name='TEST',
            transaction_date='2026-10-20',
            currency='PHP',
            subtotal=100.00,
            grand_total=100.00,
            items=[
                ReceiptItem(description='Item', quantity=2, unit_price=50.00, line_total=100.00),
                ReceiptItem(description='Bad Item', quantity=1, unit_price=10.00, line_total=50.00)
            ]
        )
        
        result = validator.validate(receipt)
        
        assert any('Quantity' in w and 'Unit Price' in w and 'Line Total' in w for w in result.warnings)

    def test_subtotal_validation(self, validator):
        receipt = ReceiptData(
            merchant_name='TEST',
            transaction_date='2026-10-20',
            currency='PHP',
            subtotal=140.00,  # Different from sum of items (150)
            grand_total=150.00,
            items=[
                ReceiptItem(description='Item 1', quantity=1, unit_price=100.00, line_total=100.00),
                ReceiptItem(description='Item 2', quantity=1, unit_price=50.00, line_total=50.00)
            ]
        )
        
        result = validator.validate(receipt)
        
        assert any('Sum of item totals' in w and 'Stated subtotal' in w for w in result.warnings)

    def test_grand_total_validation(self, validator):
        receipt = ReceiptData(
            merchant_name='TEST',
            transaction_date='2026-10-20',
            currency='PHP',
            subtotal=100.00,
            vat_tax=12.00,
            service_charge=10.00,
            grand_total=130.00,  # Different from sum of components (122)
            items=[ReceiptItem(description='Item', quantity=1, unit_price=100.00, line_total=100.00)]
        )
        
        result = validator.validate(receipt)
        
        assert any('Sum of components' in w and 'Grand total' in w for w in result.warnings)

    def test_payment_validation(self, validator):
        receipt = ReceiptData(
            merchant_name='TEST',
            transaction_date='2026-10-20',
            currency='PHP',
            grand_total=100.00,
            amount_paid=150.00,
            change_given=40.00,
            items=[ReceiptItem(description='Item', quantity=1, unit_price=100.00, line_total=100.00)]
        )
        
        result = validator.validate(receipt)
        
        assert any('Amount paid' in w and 'Grand total' in w and 'Change' in w for w in result.warnings)

    def test_philippine_vat_validation(self, validator):
        receipt = ReceiptData(
            merchant_name='TEST',
            transaction_date='2026-10-20',
            currency='PHP',
            taxable_sales=100.00,
            vat_tax=12.00,
            grand_total=112.00,
            items=[ReceiptItem(description='Item', quantity=1, unit_price=100.00, line_total=100.00)]
        )
        
        result = validator.validate(receipt)
        
        assert result.status == 'Verified'

    def test_philippine_vat_mismatch(self, validator):
        receipt = ReceiptData(
            merchant_name='TEST',
            transaction_date='2026-10-20',
            currency='PHP',
            taxable_sales=100.00,
            vat_tax=15.00,
            grand_total=115.00,
            items=[ReceiptItem(description='Item', quantity=1, unit_price=100.00, line_total=100.00)]
        )
        
        result = validator.validate(receipt)
        
        assert any('VAT amount' in w and 'Calculated VAT' in w for w in result.warnings)

    def test_missing_critical_fields(self, validator):
        receipt = ReceiptData(
            merchant_name=None,
            transaction_date=None,
            currency='PHP',
            grand_total=None,
            items=[]
        )
        
        result = validator.validate(receipt)
        
        assert result.status == 'Incomplete'
        assert any('critical' in w.lower() for w in result.warnings)

    def test_negative_values_warning(self, validator):
        receipt = ReceiptData(
            merchant_name='TEST',
            transaction_date='2026-10-20',
            currency='PHP',
            grand_total=100.00,
            items=[
                ReceiptItem(description='Item', quantity=-1, unit_price=100.00, line_total=-100.00)
            ]
        )
        
        result = validator.validate(receipt)
        
        assert any('Negative' in w or 'Invalid quantity' in w for w in result.warnings)

    def test_duplicate_detection(self, validator):
        receipt = ReceiptData(
            merchant_name='SAME STORE',
            transaction_date='2026-10-20',
            currency='PHP',
            grand_total=100.00,
            items=[ReceiptItem(description='Item', quantity=1, unit_price=100.00, line_total=100.00)]
        )
        
        existing = [{
            'merchant_name': 'SAME STORE',
            'transaction_date': '2026-10-20',
            'grand_total': 100.00
        }]
        
        result = validator.validate(receipt, existing)
        
        assert any('duplicate' in w.lower() for w in result.warnings)