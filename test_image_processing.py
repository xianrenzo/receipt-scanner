import pytest
import os
import tempfile
from PIL import Image, ImageDraw, ImageFont
import numpy as np


class TestImageProcessing:
    @pytest.fixture
    def sample_image_bytes(self):
        img = Image.new('RGB', (800, 600), color='white')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.load_default()
        except:
            font = None
        
        draw.text((50, 50), "TEST STORE", fill='black', font=font)
        draw.text((50, 100), "123 Main St", fill='black', font=font)
        draw.text((50, 150), "Date: 2026-10-20", fill='black', font=font)
        draw.text((50, 200), "Subtotal: 100.00", fill='black', font=font)
        draw.text((50, 250), "Tax: 12.00", fill='black', font=font)
        draw.text((50, 300), "Total: 112.00", fill='black', font=font)
        draw.text((50, 350), "Item 1  2  50.00  100.00", fill='black', font=font)
        draw.text((50, 400), "Item 2  1  12.00  12.00", fill='black', font=font)
        
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        return buf.getvalue()

    def test_valid_image_upload(self, sample_image_bytes):
        from image_processor import ImageProcessor
        
        try:
            processor = ImageProcessor()
        except RuntimeError:
            pytest.skip("Tesseract not available")
        
        image = processor.load_image_from_bytes(sample_image_bytes)
        
        assert image is not None
        assert image.shape[0] == 600
        assert image.shape[1] == 800
        assert len(image.shape) == 3

    def test_invalid_image_rejection(self):
        from image_processor import ImageProcessor
        
        try:
            processor = ImageProcessor()
        except RuntimeError:
            pytest.skip("Tesseract not available")
        
        invalid_bytes = b"not an image"
        
        with pytest.raises(ValueError):
            processor.load_image_from_bytes(invalid_bytes)

    def test_corrupt_image_handling(self):
        from image_processor import ImageProcessor
        
        try:
            processor = ImageProcessor()
        except RuntimeError:
            pytest.skip("Tesseract not available")
        
        corrupt_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"corrupt" * 100
        
        with pytest.raises(ValueError):
            processor.load_image_from_bytes(corrupt_bytes)

    def test_preprocessing_pipeline(self, sample_image_bytes):
        from image_processor import ImageProcessor
        
        try:
            processor = ImageProcessor()
        except RuntimeError:
            pytest.skip("Tesseract not available")
        
        image = processor.load_image_from_bytes(sample_image_bytes)
        processed = processor.preprocess_for_ocr(image)
        
        assert len(processed) >= 5
        
        names = [name for name, _ in processed]
        assert 'grayscale' in names
        assert 'denoised' in names
        assert 'contrast_enhanced' in names
        assert 'otsu_binary' in names
        assert 'adaptive_binary' in names
        assert 'morphological' in names

    def test_duplicate_detection(self, sample_image_bytes):
        from database import ReceiptDatabase
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            db = ReceiptDatabase(db_path)
            
            hash1 = db.compute_image_hash(sample_image_bytes)
            hash2 = db.compute_image_hash(sample_image_bytes)
            
            assert hash1 == hash2
            assert len(hash1) == 64
            
            different_bytes = sample_image_bytes + b"different"
            hash3 = db.compute_image_hash(different_bytes)
            
            assert hash1 != hash3
        finally:
            os.unlink(db_path)

    def test_upscaling_small_image(self):
        from image_processor import ImageProcessor
        
        try:
            processor = ImageProcessor()
        except RuntimeError:
            pytest.skip("Tesseract not available")
        
        small_img = Image.new('RGB', (200, 150), color='white')
        draw = ImageDraw.Draw(small_img)
        draw.text((10, 10), "Small", fill='black')
        
        buf = io.BytesIO()
        small_img.save(buf, format='JPEG')
        small_bytes = buf.getvalue()
        
        image = processor.load_image_from_bytes(small_bytes)
        processed = processor.preprocess_for_ocr(image)
        
        upscaled = [img for name, img in processed if name == 'upscaled']
        assert len(upscaled) == 1
        assert upscaled[0].shape[0] >= 1000 or upscaled[0].shape[1] >= 1000


import io