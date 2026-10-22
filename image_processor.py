import os
import cv2
import numpy as np
from PIL import Image, ExifTags
import pytesseract
from typing import Optional, Tuple, List, Dict, Any
import tempfile
import logging

logger = logging.getLogger(__name__)


class ImageProcessor:
    def __init__(self, tesseract_path: Optional[str] = None, ocr_lang: str = 'eng'):
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        self.ocr_lang = ocr_lang
        self._verify_tesseract()

    def _verify_tesseract(self) -> bool:
        try:
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract version: {version}")
            return True
        except Exception as e:
            logger.error(f"Tesseract not found: {e}")
            raise RuntimeError(
                "Tesseract OCR is not installed or not in PATH. "
                "Please install Tesseract OCR and ensure it's accessible."
            )

    def load_image(self, image_path: str) -> np.ndarray:
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image from {image_path}")
        return image

    def load_image_from_bytes(self, image_bytes: bytes) -> np.ndarray:
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Could not decode image from bytes")
        return image

    def save_image(self, image: np.ndarray, path: str) -> bool:
        return cv2.imwrite(path, image)

    def correct_orientation(self, image: np.ndarray, image_path: str = None) -> np.ndarray:
        if image_path:
            try:
                pil_image = Image.open(image_path)
                exif = pil_image._getexif()
                if exif:
                    for tag, value in exif.items():
                        if ExifTags.TAGS.get(tag) == 'Orientation':
                            if value == 3:
                                image = cv2.rotate(image, cv2.ROTATE_180)
                            elif value == 6:
                                image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
                            elif value == 8:
                                image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
                            break
            except Exception as e:
                logger.warning(f"Could not read EXIF orientation: {e}")
        return image

    def preprocess_for_ocr(self, image: np.ndarray) -> List[np.ndarray]:
        processed_images = []
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        processed_images.append(('grayscale', gray))
        
        height, width = gray.shape
        if max(height, width) < 1000:
            scale = 1000 / max(height, width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            upscaled = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            processed_images.append(('upscaled', upscaled))
            gray = upscaled
        
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        processed_images.append(('denoised', denoised))
        
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)
        processed_images.append(('contrast_enhanced', enhanced))
        
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        processed_images.append(('otsu_binary', binary))
        
        adaptive = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        processed_images.append(('adaptive_binary', adaptive))
        
        kernel = np.ones((1, 1), np.uint8)
        morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        processed_images.append(('morphological', morph))
        
        return processed_images

    def extract_text(self, image: np.ndarray) -> Dict[str, Any]:
        try:
            config = f'--oem 3 --psm 6 -l {self.ocr_lang}'
            data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
            
            text_lines = []
            confidences = []
            
            for i in range(len(data['text'])):
                if data['text'][i].strip():
                    text_lines.append(data['text'][i])
                    confidences.append(data['conf'][i])
            
            full_text = ' '.join(text_lines)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            return {
                'text': full_text,
                'lines': text_lines,
                'confidences': confidences,
                'avg_confidence': avg_confidence,
                'raw_data': data
            }
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return {
                'text': '',
                'lines': [],
                'confidences': [],
                'avg_confidence': 0,
                'raw_data': {}
            }

    def process_receipt_image(self, image_path: str) -> Dict[str, Any]:
        image = self.load_image(image_path)
        image = self.correct_orientation(image, image_path)
        
        processed_versions = self.preprocess_for_ocr(image)
        
        best_result = None
        best_confidence = 0
        
        for name, processed in processed_versions:
            result = self.extract_text(processed)
            if result['avg_confidence'] > best_confidence:
                best_confidence = result['avg_confidence']
                best_result = result
                best_result['preprocessing_method'] = name
        
        if best_result is None:
            best_result = self.extract_text(image)
            best_result['preprocessing_method'] = 'original'
        
        return best_result

    def process_receipt_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        image = self.load_image_from_bytes(image_bytes)
        
        processed_versions = self.preprocess_for_ocr(image)
        
        best_result = None
        best_confidence = 0
        
        for name, processed in processed_versions:
            result = self.extract_text(processed)
            if result['avg_confidence'] > best_confidence:
                best_confidence = result['avg_confidence']
                best_result = result
                best_result['preprocessing_method'] = name
        
        if best_result is None:
            best_result = self.extract_text(image)
            best_result['preprocessing_method'] = 'original'
        
        return best_result


def get_image_processor(tesseract_path: Optional[str] = None, ocr_lang: str = 'eng') -> ImageProcessor:
    return ImageProcessor(tesseract_path, ocr_lang)