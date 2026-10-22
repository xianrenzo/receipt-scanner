import sqlite3
import os
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
import json


class ReceiptDatabase:
    def __init__(self, db_path: str = "data/receipts.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS receipts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    merchant_name TEXT,
                    branch_name TEXT,
                    address TEXT,
                    city TEXT,
                    country TEXT,
                    contact_number TEXT,
                    website_email TEXT,
                    merchant_tin TEXT,
                    receipt_number TEXT,
                    transaction_ref TEXT,
                    invoice_number TEXT,
                    order_number TEXT,
                    terminal_number TEXT,
                    transaction_date TEXT,
                    transaction_time TEXT,
                    currency TEXT DEFAULT 'PHP',
                    currency_symbol TEXT,
                    payment_method TEXT,
                    card_brand TEXT,
                    masked_card_number TEXT,
                    transaction_status TEXT,
                    cashier_name TEXT,
                    subtotal REAL,
                    item_discounts REAL,
                    transaction_discounts REAL,
                    total_discounts REAL,
                    amount_before_tax REAL,
                    vat_tax REAL,
                    taxable_sales REAL,
                    vat_exempt_sales REAL,
                    zero_rated_sales REAL,
                    other_taxes_fees REAL,
                    service_charge REAL,
                    delivery_fee REAL,
                    packaging_fee REAL,
                    tips_gratuity REAL,
                    rounding_adjustment REAL,
                    grand_total REAL,
                    amount_paid REAL,
                    cash_received REAL,
                    change_given REAL,
                    outstanding_balance REAL,
                    raw_ocr_text TEXT,
                    original_image_path TEXT,
                    image_hash TEXT UNIQUE,
                    validation_status TEXT DEFAULT 'Needs Review',
                    review_status TEXT DEFAULT 'Unreviewed',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS receipt_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    receipt_id INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    quantity REAL,
                    unit_price REAL,
                    discount REAL,
                    tax REAL,
                    line_total REAL,
                    extraction_evidence TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (receipt_id) REFERENCES receipts(id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_date ON receipts(transaction_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_merchant ON receipts(merchant_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_status ON receipts(validation_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_hash ON receipts(image_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_receipt ON receipt_items(receipt_id)")
            
            conn.commit()

    def compute_image_hash(self, image_data: bytes) -> str:
        return hashlib.sha256(image_data).hexdigest()

    def check_duplicate(self, image_hash: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM receipts WHERE image_hash = ?", (image_hash,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def save_receipt(self, receipt_data: Dict[str, Any], items: List[Dict[str, Any]], 
                     image_path: str, image_hash: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            receipt_fields = [
                'merchant_name', 'branch_name', 'address', 'city', 'country',
                'contact_number', 'website_email', 'merchant_tin', 'receipt_number',
                'transaction_ref', 'invoice_number', 'order_number', 'terminal_number',
                'transaction_date', 'transaction_time', 'currency', 'currency_symbol',
                'payment_method', 'card_brand', 'masked_card_number', 'transaction_status',
                'cashier_name', 'subtotal', 'item_discounts', 'transaction_discounts',
                'total_discounts', 'amount_before_tax', 'vat_tax', 'taxable_sales',
                'vat_exempt_sales', 'zero_rated_sales', 'other_taxes_fees', 'service_charge',
                'delivery_fee', 'packaging_fee', 'tips_gratuity', 'rounding_adjustment',
                'grand_total', 'amount_paid', 'cash_received', 'change_given',
                'outstanding_balance', 'raw_ocr_text'
            ]
            
            values = [receipt_data.get(field) for field in receipt_fields]
            values.extend([image_path, image_hash, 
                          receipt_data.get('validation_status', 'Needs Review'),
                          receipt_data.get('review_status', 'Unreviewed'), now, now])
            
            placeholders = ', '.join(['?'] * len(values))
            columns = ', '.join(receipt_fields + ['original_image_path', 'image_hash', 
                                                  'validation_status', 'review_status',
                                                  'created_at', 'updated_at'])
            
            cursor.execute(f"INSERT INTO receipts ({columns}) VALUES ({placeholders})", values)
            receipt_id = cursor.lastrowid
            
            for item in items:
                cursor.execute("""
                    INSERT INTO receipt_items (receipt_id, description, quantity, unit_price,
                                               discount, tax, line_total, extraction_evidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    receipt_id,
                    item.get('description', ''),
                    item.get('quantity'),
                    item.get('unit_price'),
                    item.get('discount'),
                    item.get('tax'),
                    item.get('line_total'),
                    item.get('extraction_evidence'),
                    now
                ))
            
            conn.commit()
            return receipt_id

    def update_receipt(self, receipt_id: int, receipt_data: Dict[str, Any], 
                       items: List[Dict[str, Any]]) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            receipt_fields = [
                'merchant_name', 'branch_name', 'address', 'city', 'country',
                'contact_number', 'website_email', 'merchant_tin', 'receipt_number',
                'transaction_ref', 'invoice_number', 'order_number', 'terminal_number',
                'transaction_date', 'transaction_time', 'currency', 'currency_symbol',
                'payment_method', 'card_brand', 'masked_card_number', 'transaction_status',
                'cashier_name', 'subtotal', 'item_discounts', 'transaction_discounts',
                'total_discounts', 'amount_before_tax', 'vat_tax', 'taxable_sales',
                'vat_exempt_sales', 'zero_rated_sales', 'other_taxes_fees', 'service_charge',
                'delivery_fee', 'packaging_fee', 'tips_gratuity', 'rounding_adjustment',
                'grand_total', 'amount_paid', 'cash_received', 'change_given',
                'outstanding_balance', 'raw_ocr_text', 'validation_status', 'review_status'
            ]
            
            set_clause = ', '.join([f"{field} = ?" for field in receipt_fields])
            values = [receipt_data.get(field) for field in receipt_fields]
            values.append(now)
            values.append(receipt_id)
            
            cursor.execute(f"UPDATE receipts SET {set_clause}, updated_at = ? WHERE id = ?", values)
            
            cursor.execute("DELETE FROM receipt_items WHERE receipt_id = ?", (receipt_id,))
            
            for item in items:
                cursor.execute("""
                    INSERT INTO receipt_items (receipt_id, description, quantity, unit_price,
                                               discount, tax, line_total, extraction_evidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    receipt_id,
                    item.get('description', ''),
                    item.get('quantity'),
                    item.get('unit_price'),
                    item.get('discount'),
                    item.get('tax'),
                    item.get('line_total'),
                    item.get('extraction_evidence'),
                    now
                ))
            
            conn.commit()
            return cursor.rowcount > 0

    def get_receipt(self, receipt_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,))
            row = cursor.fetchone()
            if row:
                receipt = dict(row)
                cursor.execute("SELECT * FROM receipt_items WHERE receipt_id = ?", (receipt_id,))
                receipt['items'] = [dict(item) for item in cursor.fetchall()]
                return receipt
            return None

    def get_all_receipts(self, search: str = "", date_from: str = "", date_to: str = "",
                         status_filter: str = "", sort_by: str = "created_at", 
                         sort_order: str = "DESC", limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM receipts WHERE 1=1"
            params = []
            
            if search:
                query += " AND (merchant_name LIKE ? OR receipt_number LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%"])
            
            if date_from:
                query += " AND transaction_date >= ?"
                params.append(date_from)
            
            if date_to:
                query += " AND transaction_date <= ?"
                params.append(date_to)
            
            if status_filter:
                query += " AND validation_status = ?"
                params.append(status_filter)
            
            valid_sort_columns = ['created_at', 'transaction_date', 'grand_total', 'merchant_name']
            if sort_by not in valid_sort_columns:
                sort_by = 'created_at'
            
            if sort_order.upper() not in ['ASC', 'DESC']:
                sort_order = 'DESC'
            
            query += f" ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_receipts_count(self, search: str = "", date_from: str = "", date_to: str = "",
                           status_filter: str = "") -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT COUNT(*) FROM receipts WHERE 1=1"
            params = []
            
            if search:
                query += " AND (merchant_name LIKE ? OR receipt_number LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%"])
            
            if date_from:
                query += " AND transaction_date >= ?"
                params.append(date_from)
            
            if date_to:
                query += " AND transaction_date <= ?"
                params.append(date_to)
            
            if status_filter:
                query += " AND validation_status = ?"
                params.append(status_filter)
            
            cursor.execute(query, params)
            return cursor.fetchone()[0]

    def delete_receipt(self, receipt_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT original_image_path FROM receipts WHERE id = ?", (receipt_id,))
            row = cursor.fetchone()
            
            cursor.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))
            conn.commit()
            
            if row and row['original_image_path'] and os.path.exists(row['original_image_path']):
                try:
                    os.remove(row['original_image_path'])
                except OSError:
                    pass
            
            return cursor.rowcount > 0

    def delete_multiple_receipts(self, receipt_ids: List[int]) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ', '.join(['?'] * len(receipt_ids))
            cursor.execute(f"SELECT original_image_path FROM receipts WHERE id IN ({placeholders})", receipt_ids)
            rows = cursor.fetchall()
            
            cursor.execute(f"DELETE FROM receipts WHERE id IN ({placeholders})", receipt_ids)
            conn.commit()
            
            for row in rows:
                if row['original_image_path'] and os.path.exists(row['original_image_path']):
                    try:
                        os.remove(row['original_image_path'])
                    except OSError:
                        pass
            
            return cursor.rowcount

    def get_dashboard_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM receipts")
            total_receipts = cursor.fetchone()[0]
            
            cursor.execute("SELECT currency, SUM(grand_total) FROM receipts WHERE grand_total IS NOT NULL GROUP BY currency")
            spending_by_currency = {row[0]: row[1] for row in cursor.fetchall()}
            
            cursor.execute("SELECT COUNT(*) FROM receipts WHERE validation_status = 'Needs Review'")
            needs_review = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM receipts WHERE validation_status = 'Incomplete'")
            incomplete = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT * FROM receipts 
                ORDER BY created_at DESC LIMIT 5
            """)
            recent = [dict(row) for row in cursor.fetchall()]
            
            return {
                'total_receipts': total_receipts,
                'spending_by_currency': spending_by_currency,
                'needs_review': needs_review,
                'incomplete': incomplete,
                'recent_receipts': recent
            }

    def get_receipts_for_export(self, receipt_ids: Optional[List[int]] = None,
                                 date_from: str = "", date_to: str = "") -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM receipts WHERE 1=1"
            params = []
            
            if receipt_ids:
                placeholders = ', '.join(['?'] * len(receipt_ids))
                query += f" AND id IN ({placeholders})"
                params.extend(receipt_ids)
            
            if date_from:
                query += " AND transaction_date >= ?"
                params.append(date_from)
            
            if date_to:
                query += " AND transaction_date <= ?"
                params.append(date_to)
            
            query += " ORDER BY transaction_date DESC"
            
            cursor.execute(query, params)
            receipts = [dict(row) for row in cursor.fetchall()]
            
            for receipt in receipts:
                cursor.execute("SELECT * FROM receipt_items WHERE receipt_id = ?", (receipt['id'],))
                receipt['items'] = [dict(item) for item in cursor.fetchall()]
            
            return receipts


def get_database(db_path: str = "data/receipts.db") -> ReceiptDatabase:
    return ReceiptDatabase(db_path)