import pytest
from receipt_extractor import ReceiptItem


class TestDatabase:
    def test_create_receipt(self, temp_db, sample_receipt_data, sample_items):
        image_hash = "abc123"
        image_path = "/tmp/test.jpg"
        
        receipt_id = temp_db.save_receipt(sample_receipt_data, sample_items, image_path, image_hash)
        
        assert receipt_id is not None
        assert receipt_id > 0

    def test_retrieve_receipt(self, temp_db, sample_receipt_data, sample_items):
        image_hash = "abc123"
        image_path = "/tmp/test.jpg"
        
        receipt_id = temp_db.save_receipt(sample_receipt_data, sample_items, image_path, image_hash)
        receipt = temp_db.get_receipt(receipt_id)
        
        assert receipt is not None
        assert receipt['id'] == receipt_id
        assert receipt['merchant_name'] == 'SAMPLE STORE'
        assert receipt['grand_total'] == 120.00
        assert len(receipt['items']) == 2
        assert receipt['items'][0]['description'] == 'Notebook'
        assert receipt['items'][1]['description'] == 'Pen'

    def test_update_receipt(self, temp_db, sample_receipt_data, sample_items):
        image_hash = "abc123"
        image_path = "/tmp/test.jpg"
        
        receipt_id = temp_db.save_receipt(sample_receipt_data, sample_items, image_path, image_hash)
        
        updated_data = sample_receipt_data.copy()
        updated_data['merchant_name'] = 'UPDATED STORE'
        updated_data['grand_total'] = 200.00
        
        updated_items = sample_items.copy()
        updated_items[0]['line_total'] = 150.00
        
        result = temp_db.update_receipt(receipt_id, updated_data, updated_items)
        assert result is True
        
        receipt = temp_db.get_receipt(receipt_id)
        assert receipt['merchant_name'] == 'UPDATED STORE'
        assert receipt['grand_total'] == 200.00
        assert receipt['items'][0]['line_total'] == 150.00

    def test_delete_receipt(self, temp_db, sample_receipt_data, sample_items):
        image_hash = "abc123"
        image_path = "/tmp/test.jpg"
        
        receipt_id = temp_db.save_receipt(sample_receipt_data, sample_items, image_path, image_hash)
        
        result = temp_db.delete_receipt(receipt_id)
        assert result is True
        
        receipt = temp_db.get_receipt(receipt_id)
        assert receipt is None

    def test_delete_multiple_receipts(self, temp_db, sample_receipt_data, sample_items):
        ids = []
        for i in range(3):
            data = sample_receipt_data.copy()
            data['merchant_name'] = f'STORE {i}'
            image_hash = f"hash{i}"
            image_path = f"/tmp/test{i}.jpg"
            receipt_id = temp_db.save_receipt(data, sample_items, image_path, image_hash)
            ids.append(receipt_id)
        
        deleted = temp_db.delete_multiple_receipts(ids)
        assert deleted == 3
        
        for receipt_id in ids:
            assert temp_db.get_receipt(receipt_id) is None

    def test_duplicate_detection(self, temp_db, sample_receipt_data, sample_items):
        image_bytes = b"test image data"
        image_hash = temp_db.compute_image_hash(image_bytes)
        image_path = "/tmp/test.jpg"
        
        receipt_id1 = temp_db.save_receipt(sample_receipt_data, sample_items, image_path, image_hash)
        assert receipt_id1 is not None
        
        duplicate = temp_db.check_duplicate(image_hash)
        assert duplicate is not None
        assert duplicate['id'] == receipt_id1

    def test_search_and_filter(self, temp_db, sample_receipt_data, sample_items):
        for i in range(5):
            data = sample_receipt_data.copy()
            data['merchant_name'] = f'STORE {i}'
            data['transaction_date'] = f'2026-10-{20+i:02d}'
            data['grand_total'] = 100.00 + i * 10
            image_hash = f"hash{i}"
            image_path = f"/tmp/test{i}.jpg"
            temp_db.save_receipt(data, sample_items, image_path, image_hash)
        
        results = temp_db.get_all_receipts(search='STORE 2')
        assert len(results) == 1
        assert results[0]['merchant_name'] == 'STORE 2'
        
        results = temp_db.get_all_receipts(date_from='2026-10-22', date_to='2026-10-24')
        assert len(results) == 3
        
        results = temp_db.get_all_receipts(status_filter='Verified')
        assert len(results) == 5

    def test_persistence(self, temp_db, sample_receipt_data, sample_items):
        image_hash = "persist_hash"
        image_path = "/tmp/persist.jpg"
        
        receipt_id = temp_db.save_receipt(sample_receipt_data, sample_items, image_path, image_hash)
        
        new_db = temp_db.__class__(temp_db.db_path)
        receipt = new_db.get_receipt(receipt_id)
        
        assert receipt is not None
        assert receipt['merchant_name'] == 'SAMPLE STORE'

    def test_missing_optional_fields(self, temp_db, sample_items):
        minimal_data = {
            'merchant_name': 'MINIMAL STORE',
            'transaction_date': '2026-10-20',
            'currency': 'PHP',
            'grand_total': 50.00,
            'validation_status': 'Needs Review',
            'review_status': 'Unreviewed'
        }
        
        image_hash = "minimal_hash"
        image_path = "/tmp/minimal.jpg"
        
        receipt_id = temp_db.save_receipt(minimal_data, sample_items, image_path, image_hash)
        assert receipt_id is not None
        
        receipt = temp_db.get_receipt(receipt_id)
        assert receipt['merchant_name'] == 'MINIMAL STORE'
        assert receipt['subtotal'] is None
        assert receipt['vat_tax'] is None

    def test_dashboard_stats(self, temp_db, sample_receipt_data, sample_items):
        for i in range(3):
            data = sample_receipt_data.copy()
            data['merchant_name'] = f'STORE {i}'
            data['grand_total'] = 100.00 * (i + 1)
            data['currency'] = 'PHP'
            data['validation_status'] = 'Verified' if i < 2 else 'Needs Review'
            image_hash = f"stats_hash{i}"
            image_path = f"/tmp/stats{i}.jpg"
            temp_db.save_receipt(data, sample_items, image_path, image_hash)
        
        stats = temp_db.get_dashboard_stats()
        
        assert stats['total_receipts'] == 3
        assert stats['spending_by_currency']['PHP'] == 600.00
        assert stats['needs_review'] == 1