# Receipt Scanner

A complete Python web application for scanning, extracting, and managing receipts. Built with Streamlit, Tesseract OCR, and SQLite.

## Features

- **Multiple Input Methods**: Upload images, paste from clipboard, or capture with phone camera
- **OCR Processing**: Uses Tesseract OCR with image preprocessing for accurate text extraction
- **Structured Extraction**: Identifies merchant info, transaction details, line items, and financial summaries
- **Philippine Receipt Support**: Recognizes VAT, VAT-exempt, zero-rated, SC/PWD discounts, and other local formats
- **Financial Validation**: Validates calculations, detects inconsistencies, flags duplicates
- **Review & Correction**: Edit extracted data before saving with full validation re-check
- **Persistent Storage**: SQLite database with receipt and line item tables
- **Receipt History**: Search, filter, sort, view, edit, and delete receipts
- **Excel Export**: Professional .xlsx exports with multiple worksheets
- **Mobile Friendly**: Works on desktop and mobile browsers

## Quick Start

### Prerequisites

1. **Python 3.12+**
2. **Tesseract OCR** (system dependency - not installable via pip)

### Install Tesseract OCR

**macOS:**
```bash
brew install tesseract
# For additional languages:
brew install tesseract-lang
```

**Windows:**
1. Download installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Run installer (default path: `C:\Program Files\Tesseract-OCR`)
3. Add to PATH or set `TESSERACT_PATH` environment variable

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install tesseract-ocr
sudo apt-get install tesseract-ocr-eng tesseract-ocr-fil  # English + Filipino
```

### Setup Python Environment

```bash
cd receipt-scanner
python -m venv .venv

# macOS/Linux:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate

pip install -r requirements.txt
```

### Run the Application

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`

### Access from Phone (Same Network)

1. Find your computer's LAN IP: `ifconfig` (macOS/Linux) or `ipconfig` (Windows)
2. On phone browser, navigate to: `http://YOUR_LAN_IP:8501`
3. Camera capture works on mobile browsers (requires HTTPS for non-localhost in production)

## Project Structure

```
receipt-scanner/
├── app.py              # Main Streamlit application
├── database.py         # SQLite database operations
├── image_processor.py  # Image preprocessing & OCR
├── receipt_extractor.py # Structured data extraction
├── validator.py        # Financial validation
├── excel_export.py     # Excel export functionality
├── requirements.txt    # Python dependencies
├── README.md           # This file
├── .gitignore
├── data/
│   └── receipts.db     # SQLite database (auto-created)
└── uploads/            # Stored receipt images (auto-created)
```

## Usage Guide

### Scanning a Receipt

1. Go to **Scan Receipt** page
2. Choose input method:
   - **Upload**: Click to select image file
   - **Paste**: Copy image (screenshot, browser) → click text area → Ctrl+V/Cmd+V
   - **Camera**: Tap "Take a picture" on mobile
3. Click **Scan Receipt**
4. Review extracted data on review screen
5. Correct any errors
6. Click **Save Receipt**

### Managing Receipts

- **Receipt History**: View all saved receipts with search/filter
- **View**: Click 👁️ to see full details and download original image
- **Edit**: Click ✏️ to modify extracted data
- **Delete**: Select checkboxes → Delete Selected

### Exporting Data

1. Go to **Export Data** page
2. Choose export type:
   - Selected receipts (from history checkboxes)
   - Date range
   - All receipts
3. Optionally include OCR text sheet
4. Click **Generate Excel Export** → Download

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TESSERACT_PATH` | Auto-detect | Full path to tesseract executable |
| `OCR_LANG` | `eng` | Tesseract language code(s) |

## Database Schema

### receipts table
- All merchant, transaction, and financial fields
- `image_hash` (SHA256) for duplicate detection
- `validation_status`: Verified / Needs Review / Incomplete / Reviewed with Warnings
- `review_status`: Unreviewed / Reviewed

### receipt_items table
- Linked to receipts via foreign key (CASCADE DELETE)
- Description, quantity, unit_price, discount, tax, line_total
- Extraction evidence for audit trail

## Financial Validation

The validator checks:
- Item quantity × unit_price ≈ line_total
- Sum of item totals ≈ subtotal
- Discounts sum correctly
- VAT calculations (12% Philippine rate)
- Grand total = components sum
- Amount paid - total = change
- Date reasonableness
- Duplicate detection (merchant + date + total)

## Excel Export Format

**Multiple Receipts:**
- Sheet 1: Receipts (one row per receipt, all fields)
- Sheet 2: Receipt Items (one row per line item)
- Sheet 3: Validation (warnings, missing fields, check results)
- Sheet 4: OCR Text (optional, raw OCR output)

**Single Receipt:**
- Sheet 1: Receipt (key-value pairs)
- Sheet 2: Items (table)

## Troubleshooting

### Tesseract not found
```
Error: Tesseract OCR is not installed or not in PATH
```
- Install Tesseract (see above)
- On Windows, set `TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe`
- Restart terminal after installation

### Poor OCR accuracy
- Use clear, well-lit photos
- Avoid rotated/skewed images
- Receipt should fill most of frame
- Try preprocessing: the app applies multiple techniques automatically

### Camera doesn't work on phone
- Requires HTTPS for non-localhost (browser security)
- For local testing: use `localhost` or LAN IP with HTTP
- For production: deploy with HTTPS (nginx + certbot, or cloud provider)

### Database locked
- Close other instances of the app
- SQLite doesn't handle high concurrency well
- For multi-user: migrate to PostgreSQL

### Large images / memory issues
- Default max upload: 10 MB
- Images are upscaled to max 1000px for OCR
- Originals stored separately

## Deployment

### Local Network (Phone → Computer)
```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```
Access via `http://YOUR_LAN_IP:8501`

### Production Deployment

**Requirements:**
- HTTPS (certbot/nginx or cloud provider)
- Persistent volume for `data/` and `uploads/`
- Process manager (systemd, supervisor, or Docker)
- Reverse proxy for HTTPS termination

**Example systemd service:**
```ini
[Unit]
Description=Receipt Scanner
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/receipt-scanner
Environment=TESSERACT_PATH=/usr/bin/tesseract
ExecStart=/opt/receipt-scanner/.venv/bin/streamlit run app.py --server.address 0.0.0.0 --server.port 8501
Restart=always

[Install]
WantedBy=multi-user.target
```

**Backup Strategy:**
```bash
# Backup database
cp data/receipts.db backups/receipts_$(date +%Y%m%d).db

# Backup images
tar -czf backups/uploads_$(date +%Y%m%d).tar.gz uploads/
```

## Limitations

- No built-in multi-user authentication
- SQLite not suitable for high-concurrency multi-user
- OCR accuracy depends on image quality
- Philippine-specific tax logic (12% VAT) - adjust for other countries
- HEIC support requires pillow-heif or system library
- Camera capture requires HTTPS in production

## License

MIT License - Feel free to use and modify.

## Contributing

Issues and PRs welcome. Please test thoroughly before submitting.

---

**Built with:** Streamlit, Tesseract OCR, OpenCV, Pillow, pandas, openpyxl, SQLite