import io
import re
from typing import List, Dict, Any
import pypdf
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

CATEGORY_KEYWORDS = {
    'Pepsi': ['pepsi'],
    '7up': ['7up', 'seven up'],
    'Miranda Orange': ['miranda', 'mirinda'],
    'Mountain Dew': ['mountain dew', 'dew'],
    'Sting': ['sting'],
    'Slice': ['slice', 'mango juice'],
    'Aquafina Water': ['aquafina', 'water', 'mineral water'],
    'Carbonated Drinks': ['soda', 'carbonated', 'pop', 'fizzy'],
    'Energy Drinks': ['energy'],
    'Juice Drinks': ['juice'],
    'Packaged Water': ['packaged water', 'drinking water']
}

CATEGORY_ICONS = {
    'Pepsi': '🥤',
    '7up': '🍋',
    'Miranda Orange': '🍊',
    'Mountain Dew': '⚡',
    'Sting': '⚡',
    'Slice': '🥭',
    'Aquafina Water': '💧',
    'Carbonated Drinks': '🥤',
    'Energy Drinks': '⚡',
    'Juice Drinks': '🥭',
    'Packaged Water': '💧',
    'Specialty': '🥤'
}

DRINK_SIZES = ['200ml', '250 ml', '400 ml', '500 ml', '600 ml', '1.25 l', '1.75l', '2250 ml']
WATER_SIZES = ['500 ml', '1000 ml', '1500ml']

DAY_MAP = {
    'sunday': 1,
    'monday': 2,
    'tuesday': 3,
    'wednesday': 4,
    'thursday': 5,
    'friday': 6,
    'saturday': 7
}

def guess_brand_icon(text: str) -> str:

    tl = text.lower()
    if 'aquafina' in tl or 'water' in tl:
        return '💧'
    if 'pepsi' in tl:
        return '🥤'
    if '7up' in tl or 'seven' in tl:
        return '🍋'
    if 'miranda' in tl or 'mirinda' in tl or 'orange' in tl:
        return '🍊'
    if 'mountain dew' in tl or 'dew' in tl:
        return '⚡'
    if 'sting' in tl:
        return '⚡'
    if 'slice' in tl:
        return '🥭'
    return '🥤'

def guess_category(text: str) -> str:
    text_lower = text.lower()
    if 'aquafina' in text_lower or 'water' in text_lower:
        return 'Aquafina Water'
    if 'pepsi' in text_lower:
        return 'Pepsi'
    if '7up' in text_lower:
        return '7up'
    if 'miranda' in text_lower or 'mirinda' in text_lower:
        return 'Miranda Orange'
    if 'mountain dew' in text_lower or 'dew' in text_lower:
        return 'Mountain Dew'
    if 'sting' in text_lower:
        return 'Sting'
    if 'slice' in text_lower:
        return 'Slice'
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(kw in text_lower for kw in kws):
            return cat
    return 'Carbonated Drinks'


BRANDS = [
    ('Aquafina Water', ['aquafina', 'mineral water', 'purified water', 'drinking water', 'water']),
    ('Pepsi', ['pepsi']),
    ('7up', ['7up', 'seven up', '7-up']),
    ('Miranda Orange', ['miranda orange', 'miranda', 'mirinda orange', 'mirinda']),
    ('Mountain Dew', ['mountain dew', 'mtn dew', 'dew']),
    ('Sting', ['sting']),
    ('Slice', ['slice', 'mango juice'])
]

DEFAULT_CATEGORIES = {
    'Pepsi': 'Carbonated Drinks',
    '7up': 'Carbonated Drinks',
    'Miranda Orange': 'Carbonated Drinks',
    'Mountain Dew': 'Carbonated Drinks',
    'Sting': 'Energy Drinks',
    'Slice': 'Juice Drinks',
    'Aquafina Water': 'Packaged Water'
}

def extract_brand(text: str) -> str:
    tl = text.lower()
    for brand_name, keywords in BRANDS:
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', tl):
                return brand_name
    return ""

def extract_type(text: str) -> str:
    tl = text.lower()
    if re.search(r'\bzero\s*sugar\b|\bzero-sugar\b|\bno\s*sugar\b|\bsugar\s*free\b', tl):
        return 'Zero Sugar'
    if re.search(r'\bdiet\b|\blight\b', tl):
        return 'Diet'
    if re.search(r'\bnormal\b|\bregular\b|\bclassic\b|\boriginal\b', tl):
        return 'Normal'
    return ""

def extract_form(text: str) -> str:
    tl = text.lower()
    if re.search(r'\bglass\s*bottle\b|\bglass\b|\brgb\b', tl):
        return 'Glass bottle'
    if re.search(r'\bpet\s*bottle\b|\bplastic\s*bottle\b|\bbottle\b|\bpet\b', tl):
        return 'Bottle'
    if re.search(r'\bcan\b|\btin\b', tl):
        return 'Can'
    return ""

def extract_size(text: str) -> str:
    m = re.search(r'\b(200\s*ml|250\s*ml|400\s*ml|500\s*ml|600\s*ml|1\.25\s*l(?:iter)?|1\.75\s*l(?:iter)?|2250\s*ml|1000\s*ml|1500\s*ml|\d+(?:\.\d+)?\s*(?:ml|l|ltr|liter))\b', text, re.IGNORECASE)
    if m:
        val = m.group(1).lower().strip()
        val = re.sub(r'liter|ltr', 'l', val)
        num_match = re.match(r'^(\d+(?:\.\d+)?)\s*(ml|l)$', val)
        if num_match:
            return f"{num_match.group(1)} {num_match.group(2)}"
        return val
    return ""

def extract_price(text: str):
    m = re.search(r'(?:[\$€£]|USD\s*)?\s*(\d+(?:\.\d{1,2})?)\s*(?:[\$€£]|USD)?', text)
    if m:
        try:
            val = float(m.group(1))
            if 0.1 <= val <= 999.0:
                return val
        except ValueError:
            pass
    return None

def extract_stock(text: str):
    m = re.search(r'(?:stock|qty|quantity)?\s*:?\s*(\d+)\s*(?:bottles?|units?|pcs?|cases?|crates?)', text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None

def build_product_record(raw_name: str, brand: str = "", type_val: str = "", form_val: str = "", size_val: str = "", price: float = 0.0, stock = None, category: str = "", description: str = "") -> Dict[str, Any]:
    combined_text = f"{raw_name} {description}".strip()
    
    detected_brand = brand or extract_brand(combined_text) or "Pepsi"
    detected_type = type_val or extract_type(combined_text)
    detected_form = form_val or extract_form(combined_text) or "Bottle"
    detected_size = size_val or extract_size(combined_text)
    if not detected_size:
        detected_size = "500 ml" if detected_brand == "Aquafina Water" else "500 ml"

    if not detected_type and detected_brand in ['Pepsi', '7up']:
        detected_type = 'Normal'

    if raw_name and ('(' in raw_name and ')' in raw_name and any(b in raw_name for b in ['Pepsi', '7up', 'Miranda', 'Mountain', 'Sting', 'Slice', 'Aquafina'])):
        clean_title = raw_name.strip()
    else:
        parts = []
        if detected_type and detected_type != 'Normal' and detected_brand in ['Pepsi', '7up']:
            parts.append(f"{detected_brand} - {detected_type}")
        elif detected_type == 'Normal' and detected_brand in ['Pepsi', '7up']:
            parts.append(f"{detected_brand} - Normal")
        else:
            parts.append(detected_brand)

        specs = []
        if detected_form:
            specs.append(detected_form)
        if detected_size:
            specs.append(detected_size)

        if specs:
            clean_title = f"{parts[0]} ({', '.join(specs)})"
        else:
            clean_title = parts[0]

    final_cat = category or DEFAULT_CATEGORIES.get(detected_brand, 'Carbonated Drinks')
    
    final_desc = description.strip()
    if not final_desc:
        desc_parts = [f"Chilled {detected_brand}"]
        if detected_type:
            desc_parts.append(f"{detected_type} formula")
        if detected_form:
            desc_parts.append(f"in {detected_form.lower()}")
        if detected_size:
            desc_parts.append(f"({detected_size})")
        final_desc = " ".join(desc_parts)

    day_num = None
    for d_name, d_val in DAY_MAP.items():
        if re.search(r'\b' + d_name + r'\b', combined_text.lower()):
            day_num = d_val
            break

    icon = guess_brand_icon(clean_title)

    return {
        "name": clean_title,
        "brand": detected_brand,
        "type": detected_type,
        "form": detected_form,
        "size": detected_size,
        "category": final_cat,
        "price": price,
        "stock": stock,
        "unit": "bottles",
        "description": final_desc,
        "available_day_of_week": day_num,
        "image_url": icon
    }

def parse_products_pdf(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Extracts text from an uploaded PDF and parses items into a list of beverage products.
    Takes ALL details present in the PDF (Brand, Type, Form, Size, Price, Stock, Category, Description).
    Handles:
      1. Spatial layout tables across multiple columns (Brand, Type, Form, Size, Price, Qty)
      2. Delimiter separated lines (|, tabs, commas, semicolons)
      3. Sequential table cells from PDF text streams
      4. Single line structured product definitions
    """
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    
    # 1. Try Layout Mode Extraction (Preserves horizontal row alignment)
    layout_lines = []
    plain_lines = []
    for page in reader.pages:
        try:
            txt_layout = page.extract_text(extraction_mode="layout") or ""
            layout_lines.extend([l.strip() for l in txt_layout.splitlines() if l.strip()])
        except Exception:
            pass

        txt_plain = page.extract_text() or ""
        plain_lines.extend([l.strip() for l in txt_plain.splitlines() if l.strip()])

    parsed_items = []
    seen_names = set()

    # Step 1: Detect column headers from the top lines of layout text
    header_indices = {}
    lines_to_check = layout_lines[:20] if layout_lines else plain_lines[:20]
    for line in lines_to_check:
        cols = [c.strip() for c in re.split(r'\s{2,}|\t|\|', line) if c.strip()]
        if len(cols) >= 3:
            cols_lower = [c.lower() for c in cols]
            for idx, col in enumerate(cols_lower):
                if any(k in col for k in ['drink', 'product', 'item name', 'drink / water']):
                    header_indices['name'] = idx
                elif any(k in col for k in ['brand']):
                    header_indices['brand'] = idx
                elif any(k in col for k in ['type', 'formula', 'variant']):
                    header_indices['type'] = idx
                elif any(k in col for k in ['form', 'pack', 'container', 'bottle']):
                    header_indices['form'] = idx
                elif any(k in col for k in ['size', 'volume', 'ml', 'capacity']):
                    header_indices['size'] = idx
                elif any(k in col for k in ['price', 'cost', 'rate', 'mrp']):
                    header_indices['price'] = idx
                elif any(k in col for k in ['qty', 'stock', 'quantity', 'units']):
                    header_indices['stock'] = idx
                elif any(k in col for k in ['desc', 'detail', 'specification', 'notes']):
                    header_indices['desc'] = idx
            if 'price' in header_indices and ('name' in header_indices or 'brand' in header_indices):
                break

    # Step 2: Line-by-line parsing using layout text
    source_lines = layout_lines if layout_lines else plain_lines
    for line in source_lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        # Skip document headers/titles
        if any(h in line_clean.lower() for h in ['daily drop beverage shop', 'official pricing specification', 'drink / water item', 'master drinks']):
            if not any(b in line_clean.lower() for b in ['pepsi', '7up', 'miranda', 'dew', 'sting', 'slice', 'aquafina']):
                continue

        cols = [c.strip() for c in re.split(r'\s{2,}|\t|\|', line_clean) if c.strip()]

        if len(cols) >= 2:
            price = None
            price_col_idx = -1
            for idx, col in enumerate(cols):
                p = extract_price(col)
                if p is not None and re.search(r'^\$?\s*\d+(?:\.\d{1,2})?$', col):
                    price = p
                    price_col_idx = idx
                    break

            if price is not None:
                raw_name = ""
                brand = ""
                type_val = ""
                form_val = ""
                size_val = ""
                stock_val = None
                desc = ""

                if header_indices and 'price' in header_indices:
                    if 'name' in header_indices and header_indices['name'] < len(cols):
                        raw_name = cols[header_indices['name']]
                    if 'brand' in header_indices and header_indices['brand'] < len(cols):
                        brand = cols[header_indices['brand']]
                    if 'type' in header_indices and header_indices['type'] < len(cols):
                        type_val = extract_type(cols[header_indices['type']])
                    if 'form' in header_indices and header_indices['form'] < len(cols):
                        form_val = extract_form(cols[header_indices['form']])
                    if 'size' in header_indices and header_indices['size'] < len(cols):
                        size_val = extract_size(cols[header_indices['size']])
                    if 'stock' in header_indices and header_indices['stock'] < len(cols):
                        stock_val = extract_stock(cols[header_indices['stock']]) or extract_price(cols[header_indices['stock']])
                    if 'desc' in header_indices and header_indices['desc'] < len(cols):
                        desc = cols[header_indices['desc']]

                if not raw_name:
                    raw_name = cols[0]
                    rem = [c for idx, c in enumerate(cols) if idx != 0 and idx != price_col_idx]
                    for r in rem:
                        if not size_val:
                            s = extract_size(r)
                            if s: size_val = s
                        if not type_val:
                            t = extract_type(r)
                            if t: type_val = t
                        if not form_val:
                            f = extract_form(r)
                            if f: form_val = f
                        if stock_val is None:
                            stk = extract_stock(r)
                            if stk: stock_val = stk
                        if len(r) > 10 and not desc:
                            desc = r

                record = build_product_record(
                    raw_name=raw_name,
                    brand=brand,
                    type_val=type_val,
                    form_val=form_val,
                    size_val=size_val,
                    price=price,
                    stock=stock_val,
                    description=desc
                )

                if record['name'] not in seen_names:
                    seen_names.add(record['name'])
                    parsed_items.append(record)
                continue

        # Step 3: Single-line regex extraction (Price embedded inside text)
        price_match = re.search(r'(?:[\$€£]|USD\s*)?\s*(\d+\.\d{2})', line_clean)
        if price_match:
            price = float(price_match.group(1))
            brand = extract_brand(line_clean)
            if brand or any(kw in line_clean.lower() for kw in ['diet', 'zero sugar', 'bottle', 'water', 'drink']):
                size_val = extract_size(line_clean)
                type_val = extract_type(line_clean)
                form_val = extract_form(line_clean)
                stock_val = extract_stock(line_clean)
                
                before_price = line_clean[:price_match.start()].strip()
                after_price = line_clean[price_match.end():].strip()
                
                record = build_product_record(
                    raw_name=before_price or brand,
                    brand=brand,
                    type_val=type_val,
                    form_val=form_val,
                    size_val=size_val,
                    price=price,
                    stock=stock_val,
                    description=after_price
                )
                if record['name'] not in seen_names:
                    seen_names.add(record['name'])
                    parsed_items.append(record)

    # Step 4: Vertical sequential cells fallback (if layout extraction produced few results)
    if len(parsed_items) < 2 and plain_lines:
        i = 0
        while i < len(plain_lines):
            line = plain_lines[i]
            p_match = re.match(r'^\$?\s*(\d+(?:\.\d{1,2})?)$', line)
            if p_match:
                p_val = float(p_match.group(1))
                if i >= 1:
                    c1 = plain_lines[i-1]
                    c2 = plain_lines[i-2] if i >= 2 else None
                    
                    if c2 and c2.lower() not in ['drink / water item', 'item name', 'drink name']:
                        r_name = c2
                        r_cat = c1
                    else:
                        r_name = c1
                        r_cat = ""

                    r_desc = ""
                    if i + 1 < len(plain_lines):
                        nxt = plain_lines[i+1]
                        if not re.match(r'^\$?\s*\d', nxt) and len(nxt) > 3:
                            r_desc = nxt

                    rec = build_product_record(
                        raw_name=r_name,
                        price=p_val,
                        category=r_cat,
                        description=r_desc
                    )
                    if rec['name'] not in seen_names:
                        seen_names.add(rec['name'])
                        parsed_items.append(rec)
            i += 1

    return parsed_items


def generate_sample_pdf_bytes() -> bytes:
    """
    Generates a sample Products List PDF ready for upload testing, specifically covering
    Pepsi (Diet, Zero Sugar, Normal; Bottle, Glass bottle), 7up (Zero Sugar, Normal; Bottle, Glass bottle),
    Miranda Orange, Mountain Dew, Sting, Slice, and Aquafina Water across requested sizes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    elements = []

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#d97706'),
        alignment=1
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748b'),
        alignment=1
    )

    elements.append(Paragraph("Daily Drop Beverage Shop - Master Drinks & Water Catalog", title_style))
    elements.append(Paragraph("Official Pricing Specification for Pepsi, 7up, Miranda, Mountain Dew, Sting, Slice & Aquafina", subtitle_style))
    elements.append(Spacer(1, 16))

    data = [
        ["Drink / Water Item", "Category", "Price", "Form, Type & Size Details"]
    ]

    sample_products = [
        ("Pepsi - Diet (Bottle, 500 ml)", "Carbonated Drinks", "$1.50", "Chilled Diet Pepsi in 500 ml PET bottle"),
        ("Pepsi - Zero Sugar (Glass bottle, 250 ml)", "Carbonated Drinks", "$1.25", "Crispy Zero Sugar Pepsi in 250 ml glass bottle"),
        ("Pepsi - Normal (Bottle, 1.25 l)", "Carbonated Drinks", "$2.20", "Classic Pepsi in 1.25 l family bottle"),
        ("7up - Normal (Bottle, 600 ml)", "Carbonated Drinks", "$1.50", "Crisp lemon-lime 7up in 600 ml bottle"),
        ("7up - Zero Sugar (Glass bottle, 250 ml)", "Carbonated Drinks", "$1.25", "Guilt-free Zero Sugar 7up in 250 ml glass bottle"),
        ("Miranda Orange (Bottle, 500 ml)", "Carbonated Drinks", "$1.40", "Bold fizzy orange flavor in 500 ml bottle"),
        ("Mountain Dew (Bottle, 400 ml)", "Carbonated Drinks", "$1.35", "Citrus rush Mountain Dew in 400 ml bottle"),
        ("Sting (Bottle, 250 ml)", "Energy Drinks", "$1.00", "High energy berry kick in 250 ml bottle"),
        ("Slice (Bottle, 500 ml)", "Juice Drinks", "$1.60", "Rich mango juice drink in 500 ml bottle"),
        ("Aquafina Water (Bottle, 500 ml)", "Packaged Water", "$0.75", "Pure purified drinking water in 500 ml bottle"),
        ("Aquafina Water (Bottle, 1000 ml)", "Packaged Water", "$1.10", "Pure purified drinking water in 1000 ml bottle"),
        ("Aquafina Water (Bottle, 1500 ml)", "Packaged Water", "$1.50", "Pure purified drinking water in 1500 ml bottle")
    ]

    for name, cat, prc, desc in sample_products:
        data.append([name, cat, prc, desc])

    table = Table(data, colWidths=[175, 95, 55, 215])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#fbbf24')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1e293b')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5f9')])
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

