import logging
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass
from receipt_extractor import ReceiptData, ReceiptItem

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    is_valid: bool
    status: str
    warnings: List[str]
    errors: List[str]
    checks: Dict[str, Any]


class FinancialValidator:
    TOLERANCE = 0.02
    VAT_RATE = Decimal('0.12')
    
    def __init__(self, tolerance: float = 0.02):
        self.tolerance = Decimal(str(tolerance))

    def _to_decimal(self, value: Optional[float]) -> Optional[Decimal]:
        if value is None:
            return None
        try:
            return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception:
            return None

    def _compare(self, a: Optional[Decimal], b: Optional[Decimal], tolerance: Optional[Decimal] = None) -> bool:
        if a is None or b is None:
            return False
        tol = tolerance or self.tolerance
        return abs(a - b) <= tol

    def validate_items(self, items: List[ReceiptItem]) -> Tuple[List[str], List[str]]:
        warnings = []
        errors = []
        
        for i, item in enumerate(items):
            if item.quantity is not None and item.quantity <= 0:
                warnings.append(f"Item {i+1}: Invalid quantity ({item.quantity})")
            
            if item.unit_price is not None and item.unit_price < 0:
                warnings.append(f"Item {i+1}: Negative unit price ({item.unit_price})")
            
            if item.line_total is not None and item.line_total < 0:
                warnings.append(f"Item {i+1}: Negative line total ({item.line_total})")
            
            if item.quantity is not None and item.unit_price is not None and item.line_total is not None:
                calculated = Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
                actual = Decimal(str(item.line_total))
                if not self._compare(calculated, actual):
                    warnings.append(
                        f"Item {i+1}: Quantity × Unit Price ({calculated:.2f}) ≠ Line Total ({actual:.2f})"
                    )
            
            if item.discount is not None and item.discount < 0:
                warnings.append(f"Item {i+1}: Negative discount ({item.discount})")
        
        return warnings, errors

    def validate_subtotal(self, receipt: ReceiptData) -> Tuple[List[str], List[str]]:
        warnings = []
        errors = []
        
        if not receipt.items:
            return warnings, errors
        
        item_subtotal = Decimal('0')
        for item in receipt.items:
            if item.line_total is not None:
                item_subtotal += Decimal(str(item.line_total))
        
        if receipt.subtotal is not None:
            receipt_subtotal = Decimal(str(receipt.subtotal))
            if not self._compare(item_subtotal, receipt_subtotal):
                warnings.append(
                    f"Sum of item totals ({item_subtotal:.2f}) ≠ Stated subtotal ({receipt_subtotal:.2f})"
                )
        
        return warnings, errors

    def validate_discounts(self, receipt: ReceiptData) -> Tuple[List[str], List[str]]:
        warnings = []
        errors = []
        
        total_discount = Decimal('0')
        if receipt.item_discounts is not None:
            total_discount += Decimal(str(receipt.item_discounts))
        if receipt.transaction_discounts is not None:
            total_discount += Decimal(str(receipt.transaction_discounts))
        
        if receipt.total_discounts is not None:
            stated_total = Decimal(str(receipt.total_discounts))
            if not self._compare(total_discount, stated_total):
                warnings.append(
                    f"Sum of discounts ({total_discount:.2f}) ≠ Stated total discount ({stated_total:.2f})"
                )
        
        return warnings, errors

    def validate_tax(self, receipt: ReceiptData) -> Tuple[List[str], List[str]]:
        warnings = []
        errors = []
        
        if receipt.vat_tax is not None:
            vat = Decimal(str(receipt.vat_tax))
            
            if receipt.taxable_sales is not None:
                taxable = Decimal(str(receipt.taxable_sales))
                calculated_vat = (taxable * self.VAT_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                if not self._compare(vat, calculated_vat, Decimal('0.05')):
                    warnings.append(
                        f"VAT amount ({vat:.2f}) ≠ Calculated VAT on taxable sales ({calculated_vat:.2f})"
                    )
            
            if receipt.amount_before_tax is not None:
                before_tax = Decimal(str(receipt.amount_before_tax))
                calculated_vat = (before_tax * self.VAT_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                if not self._compare(vat, calculated_vat, Decimal('0.05')):
                    warnings.append(
                        f"VAT amount ({vat:.2f}) ≠ Calculated VAT on amount before tax ({calculated_vat:.2f})"
                    )
        elif receipt.taxable_sales is not None and receipt.taxable_sales > 0:
            warnings.append("VAT/Tax amount is missing but taxable sales are present")
        elif receipt.subtotal is not None and receipt.subtotal > 0 and receipt.vat_exempt_sales is None and receipt.zero_rated_sales is None:
            warnings.append("VAT/Tax amount is missing but subtotal suggests taxable transaction")
        
        return warnings, errors

    def validate_grand_total(self, receipt: ReceiptData) -> Tuple[List[str], List[str]]:
        warnings = []
        errors = []
        
        if receipt.grand_total is None:
            return warnings, errors
        
        grand_total = Decimal(str(receipt.grand_total))
        
        components = Decimal('0')
        has_components = False
        
        if receipt.subtotal is not None:
            components += Decimal(str(receipt.subtotal))
            has_components = True
        
        if receipt.total_discounts is not None:
            components -= Decimal(str(receipt.total_discounts))
        
        if receipt.vat_tax is not None:
            components += Decimal(str(receipt.vat_tax))
        
        if receipt.service_charge is not None:
            components += Decimal(str(receipt.service_charge))
        
        if receipt.delivery_fee is not None:
            components += Decimal(str(receipt.delivery_fee))
        
        if receipt.packaging_fee is not None:
            components += Decimal(str(receipt.packaging_fee))
        
        if receipt.tips_gratuity is not None:
            components += Decimal(str(receipt.tips_gratuity))
        
        if receipt.rounding_adjustment is not None:
            components += Decimal(str(receipt.rounding_adjustment))
        
        if receipt.other_taxes_fees is not None:
            components += Decimal(str(receipt.other_taxes_fees))
        
        if has_components:
            if not self._compare(components, grand_total, Decimal('0.05')):
                warnings.append(
                    f"Sum of components ({components:.2f}) ≠ Grand total ({grand_total:.2f})"
                )
        
        return warnings, errors

    def validate_payment(self, receipt: ReceiptData) -> Tuple[List[str], List[str]]:
        warnings = []
        errors = []
        
        if receipt.amount_paid is not None and receipt.grand_total is not None:
            paid = Decimal(str(receipt.amount_paid))
            total = Decimal(str(receipt.grand_total))
            
            if receipt.change_given is not None:
                change = Decimal(str(receipt.change_given))
                if not self._compare(paid - total, change):
                    warnings.append(
                        f"Amount paid ({paid:.2f}) - Grand total ({total:.2f}) ≠ Change ({change:.2f})"
                    )
            elif paid < total:
                warnings.append(f"Amount paid ({paid:.2f}) < Grand total ({total:.2f}) but no change recorded")
        
        if receipt.cash_received is not None and receipt.amount_paid is not None:
            cash = Decimal(str(receipt.cash_received))
            paid = Decimal(str(receipt.amount_paid))
            if not self._compare(cash, paid):
                warnings.append(f"Cash received ({cash:.2f}) ≠ Amount paid ({paid:.2f})")
        
        return warnings, errors

    def validate_dates(self, receipt: ReceiptData) -> Tuple[List[str], List[str]]:
        warnings = []
        errors = []
        
        if receipt.transaction_date:
            try:
                from datetime import datetime
                date = datetime.strptime(receipt.transaction_date, '%Y-%m-%d')
                if date.year < 2000 or date.year > datetime.now().year + 1:
                    warnings.append(f"Suspicious transaction date: {receipt.transaction_date}")
            except ValueError:
                warnings.append(f"Invalid date format: {receipt.transaction_date}")
        
        return warnings, errors

    def validate_duplicate_detection(self, receipt: ReceiptData, existing_receipts: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
        warnings = []
        errors = []
        
        if receipt.merchant_name and receipt.transaction_date and receipt.grand_total:
            for existing in existing_receipts:
                if (existing.get('merchant_name') == receipt.merchant_name and
                    existing.get('transaction_date') == receipt.transaction_date and
                    existing.get('grand_total') == receipt.grand_total):
                    warnings.append("Possible duplicate receipt detected (same merchant, date, and total)")
                    break
        
        return warnings, errors

    def validate(self, receipt: ReceiptData, existing_receipts: List[Dict[str, Any]] = None) -> ValidationResult:
        all_warnings = []
        all_errors = []
        checks = {}
        
        item_warnings, item_errors = self.validate_items(receipt.items)
        all_warnings.extend(item_warnings)
        all_errors.extend(item_errors)
        checks['items'] = len(item_warnings) == 0 and len(item_errors) == 0
        
        subtotal_warnings, subtotal_errors = self.validate_subtotal(receipt)
        all_warnings.extend(subtotal_warnings)
        all_errors.extend(subtotal_errors)
        checks['subtotal'] = len(subtotal_warnings) == 0 and len(subtotal_errors) == 0
        
        discount_warnings, discount_errors = self.validate_discounts(receipt)
        all_warnings.extend(discount_warnings)
        all_errors.extend(discount_errors)
        checks['discounts'] = len(discount_warnings) == 0 and len(discount_errors) == 0
        
        tax_warnings, tax_errors = self.validate_tax(receipt)
        all_warnings.extend(tax_warnings)
        all_errors.extend(tax_errors)
        checks['tax'] = len(tax_warnings) == 0 and len(tax_errors) == 0
        
        total_warnings, total_errors = self.validate_grand_total(receipt)
        all_warnings.extend(total_warnings)
        all_errors.extend(total_errors)
        checks['grand_total'] = len(total_warnings) == 0 and len(total_errors) == 0
        
        payment_warnings, payment_errors = self.validate_payment(receipt)
        all_warnings.extend(payment_warnings)
        all_errors.extend(payment_errors)
        checks['payment'] = len(payment_warnings) == 0 and len(payment_errors) == 0
        
        date_warnings, date_errors = self.validate_dates(receipt)
        all_warnings.extend(date_warnings)
        all_errors.extend(date_errors)
        checks['dates'] = len(date_warnings) == 0 and len(date_errors) == 0
        
        if existing_receipts:
            dup_warnings, dup_errors = self.validate_duplicate_detection(receipt, existing_receipts)
            all_warnings.extend(dup_warnings)
            all_errors.extend(dup_errors)
            checks['duplicates'] = len(dup_warnings) == 0 and len(dup_errors) == 0
        
        critical_fields = [
            receipt.merchant_name, receipt.transaction_date, 
            receipt.currency, receipt.grand_total
        ]
        missing_critical = sum(1 for f in critical_fields if f is None)
        
        if all_errors:
            status = "Incomplete"
        elif missing_critical > 0:
            status = "Incomplete"
            all_warnings.append(f"Missing {missing_critical} critical field(s)")
        elif all_warnings:
            status = "Needs Review"
        else:
            status = "Verified"
        
        receipt.validation_status = status
        receipt.warnings = all_warnings
        
        return ValidationResult(
            is_valid=len(all_errors) == 0,
            status=status,
            warnings=all_warnings,
            errors=all_errors,
            checks=checks
        )


def get_validator(tolerance: float = 0.02) -> FinancialValidator:
    return FinancialValidator(tolerance)