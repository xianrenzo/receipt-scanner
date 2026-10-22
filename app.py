import streamlit as st
import os
import sys
import json
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from PIL import Image
import io
import base64

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import ReceiptDatabase, get_database
from image_processor import ImageProcessor, get_image_processor
from receipt_extractor import ReceiptExtractor, get_extractor, ReceiptData
from validator import FinancialValidator, get_validator
from excel_export import ExcelExporter, get_exporter

st.set_page_config(
    page_title="Receipt Scanner",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = "data/receipts.db"
UPLOAD_DIR = "uploads"
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
TESSERACT_PATH = os.environ.get("TESSERACT_PATH")
OCR_LANG = os.environ.get("OCR_LANG", "eng")

os.makedirs(UPLOAD_DIR, exist_ok=True)

@st.cache_resource
def init_database():
    return get_database(DB_PATH)

@st.cache_resource
def init_processor():
    try:
        return get_image_processor(TESSERACT_PATH, OCR_LANG)
    except RuntimeError as e:
        st.error(str(e))
        return None

@st.cache_resource
def init_extractor():
    return get_extractor()

@st.cache_resource
def init_validator():
    return get_validator()

@st.cache_resource
def init_exporter():
    return get_exporter()

db = init_database()
processor = init_processor()
extractor = init_extractor()
validator = init_validator()
exporter = init_exporter()

if 'page' not in st.session_state:
    st.session_state.page = "Dashboard"
if 'scan_image' not in st.session_state:
    st.session_state.scan_image = None
if 'scan_image_path' not in st.session_state:
    st.session_state.scan_image_path = None
if 'scan_result' not in st.session_state:
    st.session_state.scan_result = None
if 'review_data' not in st.session_state:
    st.session_state.review_data = None
if 'history_filters' not in st.session_state:
    st.session_state.history_filters = {
        'search': '', 'date_from': '', 'date_to': '', 
        'status': '', 'sort_by': 'created_at', 'sort_order': 'DESC'
    }
if 'selected_receipts' not in st.session_state:
    st.session_state.selected_receipts = set()

def save_uploaded_image(image_bytes: bytes) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"receipt_{timestamp}.jpg"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, 'wb') as f:
        f.write(image_bytes)
    return path

def process_image(image_bytes: bytes, image_path: str) -> Optional[ReceiptData]:
    if processor is None:
        st.error("OCR processor not available. Please install Tesseract OCR.")
        return None
    
    with st.spinner("Processing image with OCR..."):
        ocr_result = processor.process_receipt_bytes(image_bytes)
    
    if not ocr_result.get('text', '').strip():
        st.warning("No text detected in the image. Please try a clearer image.")
        return None
    
    with st.spinner("Extracting receipt information..."):
        receipt_data = extractor.extract(ocr_result)
        receipt_data.raw_ocr_text = ocr_result.get('text', '')
    
    existing = db.get_all_receipts(limit=1000)
    validation = validator.validate(receipt_data, existing)
    
    return receipt_data

def render_sidebar():
    with st.sidebar:
        st.title("🧾 Receipt Scanner")
        st.caption("Expense tracking made simple")
        
        pages = ["Dashboard", "Scan Receipt", "Receipt History", "Export Data", "Settings"]
        for page in pages:
            if st.button(page, use_container_width=True, 
                        type="primary" if st.session_state.page == page else "secondary"):
                st.session_state.page = page
                st.rerun()
        
        st.divider()
        
        stats = db.get_dashboard_stats()
        st.metric("Total Receipts", stats['total_receipts'])
        st.metric("Needs Review", stats['needs_review'])
        
        if stats['spending_by_currency']:
            st.caption("Spending by Currency")
            for curr, total in stats['spending_by_currency'].items():
                st.caption(f"{curr}: {total:,.2f}")

def render_dashboard():
    st.header("Dashboard")
    
    stats = db.get_dashboard_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Receipts", stats['total_receipts'])
    with col2:
        total_spending = sum(stats['spending_by_currency'].values())
        st.metric("Total Spending", f"{total_spending:,.2f}")
    with col3:
        st.metric("Needs Review", stats['needs_review'])
    with col4:
        st.metric("Incomplete", stats['incomplete'])
    
    if stats['spending_by_currency']:
        st.subheader("Spending by Currency")
        for curr, total in stats['spending_by_currency'].items():
            st.write(f"**{curr}**: {total:,.2f}")
    
    if stats['recent_receipts']:
        st.subheader("Recent Receipts")
        for receipt in stats['recent_receipts']:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                with col1:
                    st.write(f"**{receipt.get('merchant_name', 'Unknown')}**")
                with col2:
                    st.write(receipt.get('transaction_date', 'N/A'))
                with col3:
                    total = receipt.get('grand_total', 0)
                    curr = receipt.get('currency', 'PHP')
                    st.write(f"{curr} {total:,.2f}" if total else "N/A")
                with col4:
                    status = receipt.get('validation_status', 'Unknown')
                    color = "🟢" if status == "Verified" else "🟡" if status == "Needs Review" else "🔴"
                    st.write(f"{color} {status}")

def render_scan_page():
    st.header("Scan Receipt")
    
    tab1, tab2, tab3 = st.tabs(["📁 Upload", "📋 Paste", "📷 Camera"])
    
    with tab1:
        st.markdown("**Upload a receipt image** (JPG, PNG, WEBP, HEIC)")
        uploaded = st.file_uploader(
            "Choose an image",
            type=['jpg', 'jpeg', 'png', 'webp', 'heic', 'heif'],
            label_visibility="collapsed"
        )
        if uploaded:
            if uploaded.size > MAX_UPLOAD_SIZE:
                st.error(f"File too large. Maximum size: {MAX_UPLOAD_SIZE / (1024*1024):.0f} MB")
            else:
                image_bytes = uploaded.read()
                st.session_state.scan_image = image_bytes
                st.session_state.scan_image_path = save_uploaded_image(image_bytes)
                st.session_state.scan_result = None
                st.rerun()
    
    with tab2:
        st.markdown("**Paste an image from clipboard**")
        st.info("💡 Copy an image (Ctrl+C / Cmd+C) then click in the area below and press Ctrl+V / Cmd+V")
        
        pasted_data = st.text_area(
            "Paste base64 image data here (or use the JavaScript paste handler below)",
            height=100,
            label_visibility="collapsed",
            placeholder="Paste base64 image data here..."
        )
        
        if pasted_data:
            try:
                if pasted_data.startswith('data:image'):
                    header, encoded = pasted_data.split(',', 1)
                    image_bytes = base64.b64decode(encoded)
                    st.session_state.scan_image = image_bytes
                    st.session_state.scan_image_path = save_uploaded_image(image_bytes)
                    st.session_state.scan_result = None
                    st.rerun()
            except Exception as e:
                st.error(f"Failed to decode pasted image: {e}")
        
        st.markdown("""
        <script>
        document.addEventListener('paste', function(e) {
            const items = e.clipboardData.items;
            for (let item of items) {
                if (item.type.indexOf('image') === 0) {
                    const file = item.getAsFile();
                    const reader = new FileReader();
                    reader.onload = function(event) {
                        const base64 = event.target.result;
                        const textarea = document.querySelector('textarea[data-testid="stTextArea"]');
                        if (textarea) {
                            textarea.value = base64;
                            textarea.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    };
                    reader.readAsDataURL(file);
                }
            }
        });
        </script>
        """, unsafe_allow_html=True)
    
    with tab3:
        st.markdown("**Take a photo with your camera**")
        st.info("📱 Works best on mobile devices. Tap the button below to open camera.")
        
        camera_image = st.camera_input("Take a picture", label_visibility="collapsed")
        if camera_image:
            image_bytes = camera_image.getvalue()
            st.session_state.scan_image = image_bytes
            st.session_state.scan_image_path = save_uploaded_image(image_bytes)
            st.session_state.scan_result = None
            st.rerun()
    
    if st.session_state.scan_image:
        st.divider()
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.image(st.session_state.scan_image, caption="Receipt Image", use_container_width=True)
            
            if st.button("🔍 Scan Receipt", type="primary", use_container_width=True):
                result = process_image(st.session_state.scan_image, st.session_state.scan_image_path)
                if result:
                    st.session_state.scan_result = result
                    st.session_state.review_data = result
                    st.rerun()
            
            if st.button("🗑️ Clear", use_container_width=True):
                st.session_state.scan_image = None
                st.session_state.scan_image_path = None
                st.session_state.scan_result = None
                st.rerun()
        
        with col2:
            if st.session_state.scan_result:
                st.success("✅ Scan complete! Review the extracted data below.")
                render_review_form(st.session_state.scan_result, is_new=True)

def render_review_form(receipt: ReceiptData, is_new: bool = False):
    st.subheader("Review & Correct Extracted Data")
    
    with st.expander("📄 Raw OCR Text", expanded=False):
        st.text_area("OCR Output", receipt.raw_ocr_text, height=200, disabled=True)
    
    if receipt.warnings:
        st.warning("⚠️ **Validation Warnings:**")
        for warning in receipt.warnings:
            st.write(f"• {warning}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Merchant & Transaction")
        
        merchant_name = st.text_input("Merchant Name", value=receipt.merchant_name or "")
        branch_name = st.text_input("Branch", value=receipt.branch_name or "")
        address = st.text_area("Address", value=receipt.address or "")
        city = st.text_input("City", value=receipt.city or "")
        country = st.text_input("Country", value=receipt.country or "Philippines")
        contact = st.text_input("Contact Number", value=receipt.contact_number or "")
        website = st.text_input("Website/Email", value=receipt.website_email or "")
        tin = st.text_input("Merchant TIN", value=receipt.merchant_tin or "")
        
        receipt_number = st.text_input("Receipt Number", value=receipt.receipt_number or "")
        transaction_ref = st.text_input("Transaction Ref", value=receipt.transaction_ref or "")
        invoice_number = st.text_input("Invoice Number", value=receipt.invoice_number or "")
        order_number = st.text_input("Order Number", value=receipt.order_number or "")
        terminal = st.text_input("Terminal", value=receipt.terminal_number or "")
        
        trans_date = st.date_input(
            "Transaction Date", 
            value=datetime.strptime(receipt.transaction_date, '%Y-%m-%d').date() if receipt.transaction_date else date.today()
        )
        trans_time = st.time_input(
            "Transaction Time",
            value=datetime.strptime(receipt.transaction_time, '%H:%M:%S').time() if receipt.transaction_time else datetime.now().time()
        )
        
        currency = st.selectbox("Currency", ["PHP", "USD", "EUR", "JPY", "Other"], 
                               index=["PHP", "USD", "EUR", "JPY"].index(receipt.currency) if receipt.currency in ["PHP", "USD", "EUR", "JPY"] else 0)
        if currency == "Other":
            currency = st.text_input("Custom Currency Code", value=receipt.currency or "PHP")
        
        payment_method = st.selectbox("Payment Method", 
            ["", "Cash", "Credit Card", "Debit Card", "GCash", "Maya/PayMaya", "Bank Transfer", "Other"],
            index=["", "Cash", "Credit Card", "Debit Card", "GCash", "Maya/PayMaya", "Bank Transfer", "Other"].index(receipt.payment_method) if receipt.payment_method in ["", "Cash", "Credit Card", "Debit Card", "GCash", "Maya/PayMaya", "Bank Transfer", "Other"] else 0)
        
        card_brand = st.text_input("Card Brand", value=receipt.card_brand or "")
        masked_card = st.text_input("Masked Card Number", value=receipt.masked_card_number or "")
        cashier = st.text_input("Cashier", value=receipt.cashier_name or "")
    
    with col2:
        st.markdown("### Financial Summary")
        
        def money_input(label, value, key):
            return st.number_input(label, value=float(value) if value is not None else 0.0, 
                                 step=0.01, format="%.2f", key=key)
        
        subtotal = money_input("Subtotal", receipt.subtotal, "subtotal")
        item_discounts = money_input("Item Discounts", receipt.item_discounts, "item_discounts")
        trans_discounts = money_input("Transaction Discounts", receipt.transaction_discounts, "trans_discounts")
        total_discounts = money_input("Total Discounts", receipt.total_discounts, "total_discounts")
        amount_before_tax = money_input("Amount Before Tax", receipt.amount_before_tax, "amount_before_tax")
        vat_tax = money_input("VAT/Tax", receipt.vat_tax, "vat_tax")
        taxable_sales = money_input("Taxable Sales", receipt.taxable_sales, "taxable_sales")
        vat_exempt = money_input("VAT-Exempt Sales", receipt.vat_exempt_sales, "vat_exempt")
        zero_rated = money_input("Zero-Rated Sales", receipt.zero_rated_sales, "zero_rated")
        other_taxes = money_input("Other Taxes/Fees", receipt.other_taxes_fees, "other_taxes")
        service_charge = money_input("Service Charge", receipt.service_charge, "service_charge")
        delivery_fee = money_input("Delivery Fee", receipt.delivery_fee, "delivery_fee")
        packaging_fee = money_input("Packaging Fee", receipt.packaging_fee, "packaging_fee")
        tips = money_input("Tips/Gratuity", receipt.tips_gratuity, "tips")
        rounding = money_input("Rounding Adjustment", receipt.rounding_adjustment, "rounding")
        grand_total = money_input("Grand Total", receipt.grand_total, "grand_total")
        amount_paid = money_input("Amount Paid", receipt.amount_paid, "amount_paid")
        cash_received = money_input("Cash Received", receipt.cash_received, "cash_received")
        change_given = money_input("Change Given", receipt.change_given, "change_given")
        outstanding = money_input("Outstanding Balance", receipt.outstanding_balance, "outstanding")
    
    st.markdown("### Itemized Purchases")
    
    if 'edited_items' not in st.session_state:
        st.session_state.edited_items = []
        for item in receipt.items:
            st.session_state.edited_items.append({
                'description': item.description,
                'quantity': item.quantity or 1,
                'unit_price': item.unit_price or 0,
                'discount': item.discount or 0,
                'tax': item.tax or 0,
                'line_total': item.line_total or 0,
                'extraction_evidence': item.extraction_evidence
            })
    
    for i, item in enumerate(st.session_state.edited_items):
        with st.container():
            cols = st.columns([3, 1, 1, 1, 1, 1, 1])
            with cols[0]:
                item['description'] = st.text_input("Description", value=item['description'], key=f"desc_{i}", label_visibility="collapsed")
            with cols[1]:
                item['quantity'] = st.number_input("Qty", value=item['quantity'], step=1, key=f"qty_{i}", label_visibility="collapsed")
            with cols[2]:
                item['unit_price'] = st.number_input("Unit Price", value=item['unit_price'], step=0.01, format="%.2f", key=f"up_{i}", label_visibility="collapsed")
            with cols[3]:
                item['discount'] = st.number_input("Discount", value=item['discount'], step=0.01, format="%.2f", key=f"disc_{i}", label_visibility="collapsed")
            with cols[4]:
                item['tax'] = st.number_input("Tax", value=item['tax'], step=0.01, format="%.2f", key=f"tax_{i}", label_visibility="collapsed")
            with cols[5]:
                item['line_total'] = st.number_input("Line Total", value=item['line_total'], step=0.01, format="%.2f", key=f"lt_{i}", label_visibility="collapsed")
            with cols[6]:
                if st.button("🗑️", key=f"del_{i}"):
                    st.session_state.edited_items.pop(i)
                    st.rerun()
    
    if st.button("➕ Add Item"):
        st.session_state.edited_items.append({
            'description': '', 'quantity': 1, 'unit_price': 0, 'discount': 0, 'tax': 0, 'line_total': 0, 'extraction_evidence': ''
        })
        st.rerun()
    
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💾 Save Receipt", type="primary", use_container_width=True):
            save_receipt(receipt, is_new)
    with col2:
        if st.button("🔄 Re-scan", use_container_width=True):
            if st.session_state.scan_image:
                result = process_image(st.session_state.scan_image, st.session_state.scan_image_path)
                if result:
                    st.session_state.scan_result = result
                    st.session_state.review_data = result
                    st.session_state.edited_items = []
                    st.rerun()
    with col3:
        if st.button("❌ Cancel", use_container_width=True):
            clear_scan_state()
            st.rerun()

def save_receipt(receipt: ReceiptData, is_new: bool):
    receipt.merchant_name = st.session_state.get('merchant_name', receipt.merchant_name)
    receipt.branch_name = st.session_state.get('branch_name', receipt.branch_name)
    receipt.address = st.session_state.get('address', receipt.address)
    receipt.city = st.session_state.get('city', receipt.city)
    receipt.country = st.session_state.get('country', receipt.country)
    receipt.contact_number = st.session_state.get('contact', receipt.contact_number)
    receipt.website_email = st.session_state.get('website', receipt.website_email)
    receipt.merchant_tin = st.session_state.get('tin', receipt.merchant_tin)
    receipt.receipt_number = st.session_state.get('receipt_number', receipt.receipt_number)
    receipt.transaction_ref = st.session_state.get('transaction_ref', receipt.transaction_ref)
    receipt.invoice_number = st.session_state.get('invoice_number', receipt.invoice_number)
    receipt.order_number = st.session_state.get('order_number', receipt.order_number)
    receipt.terminal_number = st.session_state.get('terminal', receipt.terminal_number)
    receipt.transaction_date = st.session_state.get('trans_date', receipt.transaction_date)
    receipt.transaction_time = st.session_state.get('trans_time', receipt.transaction_time)
    receipt.currency = st.session_state.get('currency', receipt.currency)
    receipt.payment_method = st.session_state.get('payment_method', receipt.payment_method)
    receipt.card_brand = st.session_state.get('card_brand', receipt.card_brand)
    receipt.masked_card_number = st.session_state.get('masked_card', receipt.masked_card_number)
    receipt.cashier_name = st.session_state.get('cashier', receipt.cashier_name)
    receipt.subtotal = st.session_state.get('subtotal', receipt.subtotal)
    receipt.item_discounts = st.session_state.get('item_discounts', receipt.item_discounts)
    receipt.transaction_discounts = st.session_state.get('trans_discounts', receipt.transaction_discounts)
    receipt.total_discounts = st.session_state.get('total_discounts', receipt.total_discounts)
    receipt.amount_before_tax = st.session_state.get('amount_before_tax', receipt.amount_before_tax)
    receipt.vat_tax = st.session_state.get('vat_tax', receipt.vat_tax)
    receipt.taxable_sales = st.session_state.get('taxable_sales', receipt.taxable_sales)
    receipt.vat_exempt_sales = st.session_state.get('vat_exempt', receipt.vat_exempt_sales)
    receipt.zero_rated_sales = st.session_state.get('zero_rated', receipt.zero_rated_sales)
    receipt.other_taxes_fees = st.session_state.get('other_taxes', receipt.other_taxes_fees)
    receipt.service_charge = st.session_state.get('service_charge', receipt.service_charge)
    receipt.delivery_fee = st.session_state.get('delivery_fee', receipt.delivery_fee)
    receipt.packaging_fee = st.session_state.get('packaging_fee', receipt.packaging_fee)
    receipt.tips_gratuity = st.session_state.get('tips', receipt.tips_gratuity)
    receipt.rounding_adjustment = st.session_state.get('rounding', receipt.rounding_adjustment)
    receipt.grand_total = st.session_state.get('grand_total', receipt.grand_total)
    receipt.amount_paid = st.session_state.get('amount_paid', receipt.amount_paid)
    receipt.cash_received = st.session_state.get('cash_received', receipt.cash_received)
    receipt.change_given = st.session_state.get('change_given', receipt.change_given)
    receipt.outstanding_balance = st.session_state.get('outstanding', receipt.outstanding_balance)
    receipt.review_status = "Reviewed"
    
    items = []
    for item in st.session_state.edited_items:
        if item['description'].strip():
            items.append({
                'description': item['description'],
                'quantity': item['quantity'],
                'unit_price': item['unit_price'],
                'discount': item['discount'],
                'tax': item['tax'],
                'line_total': item['line_total'],
                'extraction_evidence': item['extraction_evidence']
            })
    
    receipt.items = [ReceiptData(**{'items': [type('Item', (), item)() for item in items]})]
    
    if is_new:
        image_hash = db.compute_image_hash(st.session_state.scan_image)
        existing = db.check_duplicate(image_hash)
        if existing:
            st.warning("⚠️ This receipt appears to be a duplicate!")
            if not st.checkbox("Save anyway"):
                return
        receipt_id = db.save_receipt(
            {k: v for k, v in receipt.__dict__.items() if not k.startswith('_')},
            items,
            st.session_state.scan_image_path,
            image_hash
        )
        st.success(f"✅ Receipt saved with ID: {receipt_id}")
    else:
        db.update_receipt(receipt.id, 
            {k: v for k, v in receipt.__dict__.items() if not k.startswith('_')},
            items
        )
        st.success("✅ Receipt updated!")
    
    clear_scan_state()
    st.session_state.page = "Receipt History"
    st.rerun()

def clear_scan_state():
    st.session_state.scan_image = None
    st.session_state.scan_image_path = None
    st.session_state.scan_result = None
    st.session_state.review_data = None
    st.session_state.edited_items = []

def render_history_page():
    st.header("Receipt History")
    
    with st.expander("🔍 Filters", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            search = st.text_input("Search", value=st.session_state.history_filters['search'], 
                                  placeholder="Merchant name, receipt #...")
            st.session_state.history_filters['search'] = search
        with col2:
            date_from = st.date_input("From Date", 
                value=datetime.strptime(st.session_state.history_filters['date_from'], '%Y-%m-%d').date() 
                if st.session_state.history_filters['date_from'] else None)
            st.session_state.history_filters['date_from'] = date_from.strftime('%Y-%m-%d') if date_from else ''
        with col3:
            date_to = st.date_input("To Date",
                value=datetime.strptime(st.session_state.history_filters['date_to'], '%Y-%m-%d').date() 
                if st.session_state.history_filters['date_to'] else None)
            st.session_state.history_filters['date_to'] = date_to.strftime('%Y-%m-%d') if date_to else ''
        with col4:
            status = st.selectbox("Status", ["", "Verified", "Needs Review", "Incomplete", "Reviewed with Warnings"],
                                index=["", "Verified", "Needs Review", "Incomplete", "Reviewed with Warnings"].index(st.session_state.history_filters['status']) 
                                if st.session_state.history_filters['status'] in ["", "Verified", "Needs Review", "Incomplete", "Reviewed with Warnings"] else 0)
            st.session_state.history_filters['status'] = status
    
    col1, col2, col3 = st.columns(3)
    with col1:
        sort_by = st.selectbox("Sort By", ["created_at", "transaction_date", "grand_total", "merchant_name"],
                              index=["created_at", "transaction_date", "grand_total", "merchant_name"].index(st.session_state.history_filters['sort_by']))
        st.session_state.history_filters['sort_by'] = sort_by
    with col2:
        sort_order = st.selectbox("Order", ["DESC", "ASC"], 
                                 index=["DESC", "ASC"].index(st.session_state.history_filters['sort_order']))
        st.session_state.history_filters['sort_order'] = sort_order
    with col3:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    receipts = db.get_all_receipts(
        search=st.session_state.history_filters['search'],
        date_from=st.session_state.history_filters['date_from'],
        date_to=st.session_state.history_filters['date_to'],
        status_filter=st.session_state.history_filters['status'],
        sort_by=st.session_state.history_filters['sort_by'],
        sort_order=st.session_state.history_filters['sort_order'],
        limit=100
    )
    
    if not receipts:
        st.info("No receipts found. Scan your first receipt!")
        return
    
    st.write(f"Showing {len(receipts)} receipts")
    
    for receipt in receipts:
        with st.container():
            cols = st.columns([0.5, 3, 2, 2, 1.5, 1.5, 1])
            
            with cols[0]:
                selected = st.checkbox("", key=f"sel_{receipt['id']}", label_visibility="collapsed")
                if selected:
                    st.session_state.selected_receipts.add(receipt['id'])
                else:
                    st.session_state.selected_receipts.discard(receipt['id'])
            
            with cols[1]:
                st.write(f"**{receipt.get('merchant_name', 'Unknown')}**")
                if receipt.get('branch_name'):
                    st.caption(receipt['branch_name'])
            
            with cols[2]:
                st.write(receipt.get('transaction_date', 'N/A'))
                st.caption(receipt.get('transaction_time', ''))
            
            with cols[3]:
                total = receipt.get('grand_total', 0)
                curr = receipt.get('currency', 'PHP')
                st.write(f"**{curr} {total:,.2f}**" if total else "N/A")
            
            with cols[4]:
                status = receipt.get('validation_status', 'Unknown')
                color = "🟢" if status == "Verified" else "🟡" if status == "Needs Review" else "🔴"
                st.write(f"{color} {status}")
            
            with cols[5]:
                if st.button("👁️ View", key=f"view_{receipt['id']}", use_container_width=True):
                    st.session_state.view_receipt_id = receipt['id']
                    st.rerun()
            
            with cols[6]:
                if st.button("✏️ Edit", key=f"edit_{receipt['id']}", use_container_width=True):
                    st.session_state.edit_receipt_id = receipt['id']
                    st.rerun()
        
        if receipt.get('id') == st.session_state.get('view_receipt_id'):
            render_receipt_detail(receipt)
            st.divider()
        
        if receipt.get('id') == st.session_state.get('edit_receipt_id'):
            full_receipt = db.get_receipt(receipt['id'])
            if full_receipt:
                receipt_obj = ReceiptData(**{k: v for k, v in full_receipt.items() if k != 'items'})
                receipt_obj.items = [ReceiptData(**item) for item in full_receipt.get('items', [])]
                st.session_state.edited_items = []
                for item in full_receipt.get('items', []):
                    st.session_state.edited_items.append({
                        'description': item['description'],
                        'quantity': item['quantity'] or 1,
                        'unit_price': item['unit_price'] or 0,
                        'discount': item['discount'] or 0,
                        'tax': item['tax'] or 0,
                        'line_total': item['line_total'] or 0,
                        'extraction_evidence': item['extraction_evidence'] or ''
                    })
                render_review_form(receipt_obj, is_new=False)
                st.divider()
    
    if st.session_state.selected_receipts:
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Export Selected", use_container_width=True):
                export_selected()
        with col2:
            if st.button("🗑️ Delete Selected", use_container_width=True, type="secondary"):
                if st.checkbox("Confirm deletion"):
                    deleted = db.delete_multiple_receipts(list(st.session_state.selected_receipts))
                    st.success(f"Deleted {deleted} receipts")
                    st.session_state.selected_receipts.clear()
                    st.rerun()

def render_receipt_detail(receipt: Dict[str, Any]):
    st.subheader(f"Receipt #{receipt['id']}: {receipt.get('merchant_name', 'Unknown')}")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        if receipt.get('original_image_path') and os.path.exists(receipt['original_image_path']):
            st.image(receipt['original_image_path'], use_container_width=True)
            with open(receipt['original_image_path'], 'rb') as f:
                st.download_button("📥 Download Image", f.read(), 
                                 file_name=os.path.basename(receipt['original_image_path']),
                                 use_container_width=True)
    
    with col2:
        st.write(f"**Date:** {receipt.get('transaction_date', 'N/A')} {receipt.get('transaction_time', '')}")
        st.write(f"**Total:** {receipt.get('currency', 'PHP')} {receipt.get('grand_total', 0):,.2f}")
        st.write(f"**Status:** {receipt.get('validation_status', 'Unknown')}")
        st.write(f"**Payment:** {receipt.get('payment_method', 'N/A')}")
        
        if receipt.get('items'):
            st.write("**Items:**")
            for item in receipt['items']:
                st.write(f"• {item['description']} - {item.get('quantity', 1)} × {item.get('unit_price', 0):,.2f} = {item.get('line_total', 0):,.2f}")

def render_export_page():
    st.header("Export Data")
    
    export_type = st.radio("Export Type", ["Selected Receipts", "Date Range", "All Receipts"], horizontal=True)
    
    receipt_ids = None
    date_from = date_to = None
    
    if export_type == "Selected Receipts":
        if st.session_state.selected_receipts:
            receipt_ids = list(st.session_state.selected_receipts)
            st.info(f"{len(receipt_ids)} receipts selected from history")
        else:
            st.warning("No receipts selected. Go to Receipt History to select receipts.")
            return
    elif export_type == "Date Range":
        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("From Date")
        with col2:
            date_to = st.date_input("To Date")
        date_from = date_from.strftime('%Y-%m-%d') if date_from else ''
        date_to = date_to.strftime('%Y-%m-%d') if date_to else ''
    
    include_ocr = st.checkbox("Include OCR Text Sheet", value=False)
    
    if st.button("📊 Generate Excel Export", type="primary", use_container_width=True):
        with st.spinner("Generating Excel file..."):
            receipts = db.get_receipts_for_export(receipt_ids, date_from, date_to)
            
            if not receipts:
                st.warning("No receipts to export")
                return
            
            excel_data = exporter.export_receipts(receipts, include_ocr)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"receipts_export_{timestamp}.xlsx"
            
            st.download_button(
                "📥 Download Excel File",
                excel_data,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            st.success(f"✅ Exported {len(receipts)} receipts")

def render_settings_page():
    st.header("Settings")
    
    st.subheader("Database")
    st.write(f"**Location:** {DB_PATH}")
    st.write(f"**Size:** {os.path.getsize(DB_PATH) / 1024:.1f} KB" if os.path.exists(DB_PATH) else "**Size:** Not created yet")
    
    st.subheader("Image Storage")
    st.write(f"**Upload Directory:** {UPLOAD_DIR}")
    upload_count = len([f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))])
    st.write(f"**Stored Images:** {upload_count}")
    
    st.subheader("OCR Settings")
    st.write(f"**Tesseract Path:** {TESSERACT_PATH or 'System PATH'}")
    st.write(f"**OCR Language:** {OCR_LANG}")
    
    st.subheader("Upload Limits")
    st.write(f"**Max File Size:** {MAX_UPLOAD_SIZE / (1024*1024):.0f} MB")
    
    st.subheader("Default Currency")
    default_currency = st.selectbox("Default Currency", ["PHP", "USD", "EUR", "JPY"], index=0)
    
    st.divider()
    st.subheader("⚠️ Important Notes")
    st.warning("""
    **Security & Privacy:**
    - This application has no built-in authentication
    - Do not expose publicly without adding access controls
    - Receipt data is stored locally in SQLite
    - Images are stored in the uploads/ directory
    - For production: use HTTPS, persistent volumes, and regular backups
    
    **Deployment:**
    - Run locally: `streamlit run app.py`
    - Access from phone: Use your computer's LAN IP (e.g., http://192.168.x.x:8501)
    - For HTTPS: Use a reverse proxy (nginx + certbot) or cloud deployment
    """)

def export_selected():
    receipts = db.get_receipts_for_export(list(st.session_state.selected_receipts))
    if receipts:
        excel_data = exporter.export_receipts(receipts, include_ocr=False)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            "📥 Download Selected",
            excel_data,
            file_name=f"receipts_selected_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

def main():
    render_sidebar()
    
    if st.session_state.page == "Dashboard":
        render_dashboard()
    elif st.session_state.page == "Scan Receipt":
        render_scan_page()
    elif st.session_state.page == "Receipt History":
        render_history_page()
    elif st.session_state.page == "Export Data":
        render_export_page()
    elif st.session_state.page == "Settings":
        render_settings_page()

if __name__ == "__main__":
    main()