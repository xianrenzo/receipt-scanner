import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


@dataclass
class ReceiptItem:
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    discount: Optional[float] = None
    tax: Optional[float] = None
    line_total: Optional[float] = None
    extraction_evidence: str = ""
    raw_line: str = ""


@dataclass
class ReceiptData:
    merchant_name: Optional[str] = None
    branch_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    contact_number: Optional[str] = None
    website_email: Optional[str] = None
    merchant_tin: Optional[str] = None
    receipt_number: Optional[str] = None
    transaction_ref: Optional[str] = None
    invoice_number: Optional[str] = None
    order_number: Optional[str] = None
    terminal_number: Optional[str] = None
    transaction_date: Optional[str] = None
    transaction_time: Optional[str] = None
    currency: str = "PHP"
    currency_symbol: Optional[str] = None
    payment_method: Optional[str] = None
    card_brand: Optional[str] = None
    masked_card_number: Optional[str] = None
    transaction_status: Optional[str] = None
    cashier_name: Optional[str] = None
    subtotal: Optional[float] = None
    item_discounts: Optional[float] = None
    transaction_discounts: Optional[float] = None
    total_discounts: Optional[float] = None
    amount_before_tax: Optional[float] = None
    vat_tax: Optional[float] = None
    taxable_sales: Optional[float] = None
    vat_exempt_sales: Optional[float] = None
    zero_rated_sales: Optional[float] = None
    other_taxes_fees: Optional[float] = None
    service_charge: Optional[float] = None
    delivery_fee: Optional[float] = None
    packaging_fee: Optional[float] = None
    tips_gratuity: Optional[float] = None
    rounding_adjustment: Optional[float] = None
    grand_total: Optional[float] = None
    amount_paid: Optional[float] = None
    cash_received: Optional[float] = None
    change_given: Optional[float] = None
    outstanding_balance: Optional[float] = None
    items: List[ReceiptItem] = field(default_factory=list)
    raw_ocr_text: str = ""
    validation_status: str = "Needs Review"
    review_status: str = "Unreviewed"
    warnings: List[str] = field(default_factory=list)


class ReceiptExtractor:
    CURRENCY_PATTERNS = {
        'PHP': [r'₱', r'PHP', r'\bP\s*\d', r'Php', r'Peso'],
        'USD': [r'\$', r'USD', r'US\s*\$'],
        'EUR': [r'€', r'EUR'],
        'JPY': [r'¥', r'JPY'],
    }
    
    DATE_PATTERNS = [
        r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b',
        r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b',
        r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b',
        r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})\b',
    ]
    
    TIME_PATTERNS = [
        r'\b(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\b',
        r'\b(\d{1,2}\.\d{2}(?:\.\d{2})?)\b',
    ]
    
    AMOUNT_PATTERN = r'[\$₱€¥]?\s*(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?|\d+(?:\.\d{2})?|(?:\d{1,3}(?:\.\d{3})*(?:,\d{2})?))'
    
    PHILIPPINE_LABELS = {
        'vatable_sales': [r'VATable\s+Sales', r'VAT\s+Sales', r'Vatable'],
        'vat_exempt': [r'VAT[-\s]?Exempt\s+Sales', r'VAT\s+Exempt', r'Non[-\s]?VAT'],
        'zero_rated': [r'Zero[-\s]?Rated\s+Sales', r'Zero\s+Rated'],
        'vat_amount': [r'VAT\s+Amount', r'VAT\s*[:\-]', r'\bVAT\b'],
        'senior_pwd': [r'S[C/]\s*PWD', r'Senior\s+Citizen', r'PWD\s+Discount', r'SC/PWD'],
        'total_sales': [r'Total\s+Sales', r'Total\s+Amount\s+Due'],
        'amount_tendered': [r'Amount\s+Tendered', r'Cash\s+Received'],
        'change': [r'Change', r'Change\s+Given'],
        'or_number': [r'O\.?R\.?\s*No\.?', r'OR\s*#', r'Official\s+Receipt'],
        'tin': [r'TIN', r'Tax\s+Identification'],
    }

    def __init__(self):
        self.amount_regex = re.compile(self.AMOUNT_PATTERN)
        self.date_regexes = [re.compile(p, re.IGNORECASE) for p in self.DATE_PATTERNS]
        self.time_regexes = [re.compile(p, re.IGNORECASE) for p in self.TIME_PATTERNS]

    def parse_amount(self, text: str) -> Optional[float]:
        if not text:
            return None
        cleaned = text.replace(' ', '').replace('₱', '').replace('$', '').replace('PHP', '').replace('Php', '').replace('P', '')
        if ',' in cleaned and '.' in cleaned:
            if cleaned.rfind(',') > cleaned.rfind('.'):
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            parts = cleaned.split(',')
            if len(parts[-1]) == 2 and len(parts) > 1:
                cleaned = cleaned.replace(',', '.')
            else:
                cleaned = cleaned.replace(',', '')
        try:
            return float(cleaned)
        except ValueError:
            return None

    def extract_amounts_from_line(self, line: str) -> List[float]:
        amounts = []
        for match in self.amount_regex.finditer(line):
            val = self.parse_amount(match.group(1))
            if val is not None:
                amounts.append(val)
        return amounts

    def detect_currency(self, text: str) -> Tuple[str, Optional[str]]:
        text_upper = text.upper()
        for currency, patterns in self.CURRENCY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_upper):
                    symbol_map = {'PHP': '₱', 'USD': '$', 'EUR': '€', 'JPY': '¥'}
                    return currency, symbol_map.get(currency)
        return 'PHP', '₱'

    def extract_date(self, text: str) -> Optional[str]:
        for regex in self.date_regexes:
            match = regex.search(text)
            if match:
                date_str = match.group(1)
                for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y', '%m-%d-%Y', '%m/%d/%Y',
                           '%d %b %Y', '%d %B %Y', '%b %d, %Y', '%B %d, %Y']:
                    try:
                        parsed = datetime.strptime(date_str, fmt)
                        return parsed.strftime('%Y-%m-%d')
                    except ValueError:
                        continue
        return None

    def extract_time(self, text: str) -> Optional[str]:
        for regex in self.time_regexes:
            match = regex.search(text)
            if match:
                time_str = match.group(1)
                for fmt in ['%H:%M:%S', '%H:%M', '%I:%M:%S %p', '%I:%M %p', '%H.%M.%S', '%H.%M']:
                    try:
                        parsed = datetime.strptime(time_str, fmt)
                        return parsed.strftime('%H:%M:%S')
                    except ValueError:
                        continue
        return None

    def extract_merchant_info(self, lines: List[str]) -> Dict[str, Any]:
        result = {}
        
        if lines:
            result['merchant_name'] = lines[0].strip()[:200]
        
        for i, line in enumerate(lines[:10]):
            line_lower = line.lower()
            if any(kw in line_lower for kw in ['branch', 'store #', 'store no', 'outlet']):
                result['branch_name'] = line.strip()[:100]
            elif any(kw in line_lower for kw in ['address', 'addr', 'location']):
                result['address'] = line.strip()[:200]
            elif i == 1 and len(line.strip()) > 5 and not any(kw in line_lower for kw in ['date', 'time', 'total', 'subtotal', 'tax', 'vat', 'cash', 'change', 'receipt', 'invoice', 'or no']):
                result['address'] = line.strip()[:200]
            elif any(kw in line_lower for kw in ['city', 'manila', 'quezon', 'makati', 'pasig', 'taguig', 'cebu', 'davao']):
                result['city'] = line.strip()[:100]
            elif re.search(r'(?i)(tel|phone|contact)', line):
                result['contact_number'] = line.strip()[:50]
            elif re.search(r'(?i)(www\.|@|\.com|\.ph)', line):
                result['website_email'] = line.strip()[:100]
            elif re.search(r'(?i)tin', line):
                tin_match = re.search(r'\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{3}', line)
                if tin_match:
                    result['merchant_tin'] = tin_match.group(0)
        
        return result

    def extract_transaction_info(self, lines: List[str]) -> Dict[str, Any]:
        result = {}
        
        for line in lines:
            line_lower = line.lower()
            
            if not result.get('receipt_number'):
                for label in ['receipt', 'or no', 'or number', 'trans no', 'transaction no']:
                    if label in line_lower:
                        match = re.search(r'[#:]\s*([A-Z0-9\-]+)', line, re.IGNORECASE)
                        if match:
                            result['receipt_number'] = match.group(1)
                            break
            
            if not result.get('invoice_number') and 'invoice' in line_lower:
                match = re.search(r'[#:]\s*([A-Z0-9\-]+)', line, re.IGNORECASE)
                if match:
                    result['invoice_number'] = match.group(1)
            
            if not result.get('terminal_number') and 'terminal' in line_lower:
                match = re.search(r'\d+', line)
                if match:
                    result['terminal_number'] = match.group(0)
            
            if not result.get('payment_method'):
                for method in ['cash', 'credit', 'debit', 'gcash', 'maya', 'paymaya', 'card', 'visa', 'mastercard', 'amex']:
                    if method in line_lower:
                        result['payment_method'] = method.capitalize()
                        if method in ['visa', 'mastercard', 'amex']:
                            result['card_brand'] = method.capitalize()
                        break
            
            if not result.get('masked_card_number'):
                match = re.search(r'\*{4,}\d{4}', line)
                if match:
                    result['masked_card_number'] = match.group(0)
            
            if not result.get('cashier_name') and any(kw in line_lower for kw in ['cashier', 'attendant', 'server', 'clerk']):
                parts = re.split(r'[:#]\s*', line, 1)
                if len(parts) > 1:
                    result['cashier_name'] = parts[1].strip()[:50]
        
        return result

    def extract_financial_summary(self, lines: List[str]) -> Dict[str, Any]:
        result = {}
        
        financial_keywords = {
            'subtotal': ['subtotal', 'sub total', 'total sales', 'amount before tax'],
            'item_discounts': ['item discount', 'discount on items'],
            'transaction_discounts': ['transaction discount', 'total discount', 'less discount', 'discount total'],
            'vat_tax': ['vat', 'tax', 'vat amount', 'sales tax'],
            'taxable_sales': ['taxable', 'vatable sales', 'vatable'],
            'vat_exempt_sales': ['vat exempt', 'non-vat', 'exempt sales'],
            'zero_rated_sales': ['zero rated', 'zero-rated'],
            'service_charge': ['service charge', 'sc', 'service fee'],
            'delivery_fee': ['delivery', 'delivery fee', 'delivery charge'],
            'packaging_fee': ['packaging', 'packaging fee', 'pack fee'],
            'tips_gratuity': ['tip', 'gratuity', 'service tip'],
            'rounding_adjustment': ['rounding', 'round off', 'adjustment'],
            'grand_total': ['total', 'grand total', 'total amount', 'amount due', 'total payable'],
            'amount_paid': ['amount paid', 'cash', 'tendered', 'amount tendered', 'paid'],
            'cash_received': ['cash received', 'cash tendered'],
            'change_given': ['change', 'change given'],
            'outstanding_balance': ['balance', 'outstanding', 'amount due'],
        }
        
        for line in lines:
            line_lower = line.lower()
            amounts = self.extract_amounts_from_line(line)
            
            if not amounts:
                continue
            
            for field, keywords in financial_keywords.items():
                if field in result:
                    continue
                if any(kw in line_lower for kw in keywords):
                    if field in ['grand_total', 'amount_paid', 'cash_received'] and len(amounts) > 1:
                        result[field] = max(amounts)
                    else:
                        result[field] = amounts[-1]
                    break
        
        return result

    def extract_items(self, lines: List[str]) -> List[ReceiptItem]:
        items = []
        in_item_section = False
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            if any(kw in line_lower for kw in ['item', 'description', 'qty', 'quantity', 'price', 'amount', 'total']):
                if not in_item_section:
                    in_item_section = True
                    continue
            
            if in_item_section:
                if any(kw in line_lower for kw in ['subtotal', 'total', 'discount', 'tax', 'vat', 'payment', 'cash', 'change']):
                    in_item_section = False
                    continue
                
                amounts = self.extract_amounts_from_line(line)
                if len(amounts) >= 2:
                    words = line.split()
                    if len(words) >= 2:
                        desc = ' '.join(words[:-len(amounts)])
                        qty = amounts[0] if amounts[0] == int(amounts[0]) and amounts[0] < 100 else None
                        unit_price = amounts[-2] if len(amounts) >= 2 else None
                        line_total = amounts[-1]
                        
                        if desc and len(desc) > 1:
                            items.append(ReceiptItem(
                                description=desc[:200],
                                quantity=qty,
                                unit_price=unit_price,
                                line_total=line_total,
                                raw_line=line
                            ))
                elif len(amounts) == 1 and len(words) >= 2:
                    potential_items = [l for l in lines if self.extract_amounts_from_line(l) and len(self.extract_amounts_from_line(l)) >= 2]
                    if not potential_items:
                        pass
        
        if not items:
            for line in lines:
                amounts = self.extract_amounts_from_line(line)
                if len(amounts) >= 2:
                    words = line.split()
                    if len(words) >= 3:
                        desc = ' '.join(words[:-len(amounts)])
                        qty = amounts[0] if amounts[0] == int(amounts[0]) and amounts[0] < 100 else 1
                        unit_price = amounts[-2] if len(amounts) >= 2 else amounts[0]
                        line_total = amounts[-1]
                        
                        if desc and len(desc) > 1 and not any(kw in desc.lower() for kw in ['subtotal', 'total', 'tax', 'vat', 'cash', 'change', 'discount']):
                            items.append(ReceiptItem(
                                description=desc[:200],
                                quantity=qty,
                                unit_price=unit_price,
                                line_total=line_total,
                                raw_line=line
                            ))
        
        return items

    def extract(self, ocr_result: Dict[str, Any]) -> ReceiptData:
        lines = ocr_result.get('lines', [])
        raw_text = ocr_result.get('text', '')
        
        receipt = ReceiptData(raw_ocr_text=raw_text)
        
        currency, symbol = self.detect_currency(raw_text)
        receipt.currency = currency
        receipt.currency_symbol = symbol
        
        merchant_info = self.extract_merchant_info(lines)
        for k, v in merchant_info.items():
            setattr(receipt, k, v)
        
        transaction_info = self.extract_transaction_info(lines)
        for k, v in transaction_info.items():
            setattr(receipt, k, v)
        
        for line in lines:
            date = self.extract_date(line)
            if date and not receipt.transaction_date:
                receipt.transaction_date = date
            time = self.extract_time(line)
            if time and not receipt.transaction_time:
                receipt.transaction_time = time
        
        financial_info = self.extract_financial_summary(lines)
        for k, v in financial_info.items():
            setattr(receipt, k, v)
        
        receipt.items = self.extract_items(lines)
        
        return receipt


def get_extractor() -> ReceiptExtractor:
    return ReceiptExtractor()