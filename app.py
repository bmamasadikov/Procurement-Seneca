import streamlit as st
import pandas as pd
import openpyxl
from io import BytesIO
from datetime import datetime
import json
import re
import requests
import pdfplumber
import os
from difflib import SequenceMatcher
from urllib.parse import quote
from typing import Dict, List
from calculator import ProcurementCalculator
from data_loader import BrandStandards
from database import ProcurementDatabase

# Page config
st.set_page_config(
    page_title="Hotel Procurement Calculator",
    page_icon="🏨",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    :root {
        --bg-0: #f6f7f9;
        --bg-1: #ffffff;
        --text-0: #111827;
        --text-1: #4b5563;
        --line-0: #e5e7eb;
        --accent-0: #0a84ff;
        --accent-1: #0f6ef2;
        --card-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
        --radius-0: 16px;
        --radius-1: 12px;
    }

    html, body, [class*="css"]  {
        font-family: "SF Pro Display", "SF Pro Text", "Helvetica Neue", "Avenir", Arial, sans-serif;
        color: var(--text-0);
        background: radial-gradient(1200px 600px at 20% -10%, #e9eef7 0%, transparent 60%),
                    radial-gradient(1000px 500px at 90% -20%, #e8f2ff 0%, transparent 55%),
                    var(--bg-0);
    }

    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: var(--text-0);
        text-align: center;
        letter-spacing: -0.02em;
        padding: 0.5rem 0 0.25rem 0;
    }
    .section-header {
        font-size: 1.3rem;
        font-weight: 600;
        color: var(--text-0);
        margin-top: 1.75rem;
        padding-bottom: 0.35rem;
        border-bottom: 1px solid var(--line-0);
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    .stTabs [data-baseweb="tab-list"] {
        background: var(--bg-1);
        border: 1px solid var(--line-0);
        border-radius: var(--radius-0);
        padding: 0.3rem;
        box-shadow: var(--card-shadow);
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: var(--radius-1);
        padding: 0.4rem 0.9rem;
        font-weight: 600;
        color: var(--text-1);
    }
    .stTabs [aria-selected="true"] {
        background: #eaf2ff;
        color: var(--text-0);
    }

    .stButton>button {
        background: var(--accent-0);
        color: #ffffff;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        padding: 0.6rem 1rem;
        box-shadow: 0 10px 20px rgba(10, 132, 255, 0.2);
    }
    .stButton>button:hover {
        background: var(--accent-1);
    }

    .stTextInput>div>div>input,
    .stNumberInput>div>div>input,
    .stSelectbox>div>div>div,
    .stTextArea>div>textarea,
    .stFileUploader>div>div {
        background: var(--bg-1);
        border: 1px solid var(--line-0);
        border-radius: 10px;
    }

    .stDataFrame, .stDataEditor {
        border-radius: var(--radius-0);
        box-shadow: var(--card-shadow);
        border: 1px solid var(--line-0);
        overflow: hidden;
    }

    .stMetric {
        background: var(--bg-1);
        border: 1px solid var(--line-0);
        border-radius: var(--radius-1);
        padding: 0.75rem 1rem;
        box-shadow: var(--card-shadow);
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
        border-right: 1px solid var(--line-0);
    }
</style>
""", unsafe_allow_html=True)

# Initialize database
@st.cache_resource
def get_database():
    return ProcurementDatabase()

db = get_database()

# Initialize session state
if 'calculation_done' not in st.session_state:
    st.session_state.calculation_done = False
if 'results' not in st.session_state:
    st.session_state.results = {}
if 'current_project_id' not in st.session_state:
    st.session_state.current_project_id = None
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'new_project'
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'supplier_id' not in st.session_state:
    st.session_state.supplier_id = None

# ============================================================================
# FUNCTION DEFINITIONS
# ============================================================================

def _normalize_text(value: str) -> str:
    """Normalize text for matching and column guessing."""
    if value is None:
        return ''
    return re.sub(r'[^a-z0-9]+', '', str(value).lower())


def _guess_column_map(df: pd.DataFrame) -> Dict[str, str]:
    """Guess column mapping for supplier catalog files."""
    mapping = {
        'item': '',
        'description': '',
        'specification': '',
        'unit': '',
        'price': '',
        'currency': '',
        'photo': '',
    }

    for col in df.columns:
        if str(col).startswith('_'):
            continue
        normalized = _normalize_text(col)
        if not mapping['item'] and any(k in normalized for k in ['item', 'name', 'product', 'title', 'sku', 'code', 'article']):
            mapping['item'] = col
        elif not mapping['description'] and any(k in normalized for k in ['desc', 'description', 'details']):
            mapping['description'] = col
        elif not mapping['specification'] and any(k in normalized for k in ['spec', 'specification', 'standard']):
            mapping['specification'] = col
        elif not mapping['unit'] and any(k in normalized for k in ['unit', 'uom', 'measure']):
            mapping['unit'] = col
        elif not mapping['price'] and any(k in normalized for k in ['price', 'cost', 'rate', 'amount']):
            mapping['price'] = col
        elif not mapping['currency'] and any(k in normalized for k in ['currency', 'curr']):
            mapping['currency'] = col
        elif not mapping['photo'] and any(k in normalized for k in ['photo', 'image', 'picture', 'pic']):
            mapping['photo'] = col

    return mapping


def _parse_price(value) -> float:
    """Parse price values from catalog files."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    cleaned = re.sub(r'[^0-9.\-]', '', str(value))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _build_catalog_items(
    df: pd.DataFrame,
    column_map: Dict[str, str],
    default_currency: str,
    image_map: Dict = None,
    sheet_name: str = ''
) -> List[Dict]:
    """Build catalog items from a DataFrame using a column map."""
    items = []
    item_col = column_map.get('item')

    if not item_col:
        return items

    for _, row in df.iterrows():
        item_name = str(row.get(item_col, '')).strip()
        if not item_name or item_name.lower() == 'nan':
            continue

        price_value = _parse_price(row.get(column_map.get('price', ''), None)) if column_map.get('price') else None
        currency_value = row.get(column_map.get('currency', ''), default_currency) if column_map.get('currency') else default_currency

        source_row = row.get('_source_row')
        try:
            source_row = int(source_row) if source_row is not None else None
        except (TypeError, ValueError):
            source_row = None

        image_path = None
        if image_map and source_row:
            image_path = image_map.get((sheet_name, source_row))

        items.append({
            'item_name': item_name,
            'description': str(row.get(column_map.get('description', ''), '')).strip(),
            'specification': str(row.get(column_map.get('specification', ''), '')).strip(),
            'unit': str(row.get(column_map.get('unit', ''), '')).strip(),
            'price': price_value,
            'currency': currency_value,
            'price_available': price_value is not None,
            'photo_ref': str(row.get(column_map.get('photo', ''), '')).strip(),
            'image_path': image_path or '',
            'source_row': source_row,
        })

    return items


def _detect_header_row(df: pd.DataFrame) -> int:
    """Find header row index based on common column labels."""
    for idx, row in df.iterrows():
        values = [str(v).strip() for v in row.tolist() if str(v).strip() and str(v).strip().lower() != 'nan']
        if len(values) < 3:
            continue
        joined = ' '.join(values).lower()
        if any(key in joined for key in ['item', 'description', 'spec', 'unit', 'qty', 'price', 'vendor', 'article', 'photo']):
            return idx
    return -1


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a DataFrame by locating headers and dropping empty columns."""
    if not any(str(col).startswith('Unnamed:') for col in df.columns):
        return df.dropna(axis=1, how='all')

    header_idx = _detect_header_row(df)
    if header_idx == -1:
        return df.dropna(axis=1, how='all')

    header_row = df.iloc[header_idx].astype(str).tolist()
    cleaned = df.iloc[header_idx + 1:].copy()
    cleaned.columns = header_row
    cleaned = cleaned.dropna(axis=1, how='all')
    cleaned = cleaned.dropna(axis=0, how='all')
    cleaned['_source_row'] = cleaned.index + 1
    return cleaned


def _parse_pdf_tables(file_bytes: bytes) -> List[pd.DataFrame]:
    """Extract tables from a PDF file."""
    tables = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                if not table:
                    continue
                df = pd.DataFrame(table)
                if df.empty:
                    continue
                # Treat first row as header when possible
                if df.shape[0] > 1:
                    df.columns = df.iloc[0]
                    df = df.iloc[1:]
                df = df.dropna(axis=1, how='all')
                prepared = _prepare_dataframe(df)
                if '_source_row' not in prepared.columns:
                    prepared['_source_row'] = prepared.index + 1
                tables.append(prepared)
    return tables


def _ensure_dir(path: str) -> None:
    """Ensure a directory exists."""
    os.makedirs(path, exist_ok=True)


def _extract_excel_images(file_bytes: bytes, output_dir: str) -> Dict:
    """Extract Excel images and map them to (sheet_name, row)."""
    mapping = {}
    _ensure_dir(output_dir)

    wb = openpyxl.load_workbook(BytesIO(file_bytes))
    for ws in wb.worksheets:
        for idx, image in enumerate(getattr(ws, '_images', [])):
            anchor = getattr(image, 'anchor', None)
            row = None
            if hasattr(anchor, '_from'):
                row = anchor._from.row + 1  # 1-based row
            if not row:
                continue
            img_bytes = None
            try:
                img_bytes = image._data()
            except Exception:
                img_bytes = None
            if not img_bytes and getattr(image, 'image', None) is not None:
                try:
                    buffer = BytesIO()
                    image.image.save(buffer, format='PNG')
                    img_bytes = buffer.getvalue()
                except Exception:
                    img_bytes = None

            if not img_bytes:
                continue

            filename = f"{ws.title}_row{row}_{idx + 1}.png"
            image_path = os.path.join(output_dir, filename)
            with open(image_path, 'wb') as handle:
                handle.write(img_bytes)
            mapping[(ws.title, row)] = image_path

    return mapping


def _extract_pdf_images(file_bytes: bytes, output_dir: str) -> List[str]:
    """Extract images from a PDF file."""
    _ensure_dir(output_dir)
    images = []
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return images

    with fitz.open(stream=file_bytes, filetype='pdf') as doc:
        for page_index in range(len(doc)):
            page = doc[page_index]
            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                data = doc.extract_image(xref)
                img_bytes = data.get('image')
                ext = data.get('ext', 'png')
                filename = f"page{page_index + 1}_img{img_index + 1}.{ext}"
                image_path = os.path.join(output_dir, filename)
                with open(image_path, 'wb') as handle:
                    handle.write(img_bytes)
                images.append(image_path)

    return images


def _load_catalog_from_file(uploaded_file) -> Dict:
    """Load catalog content from an uploaded file."""
    file_bytes = uploaded_file.read()
    filename = uploaded_file.name
    extension = filename.split('.')[-1].lower()

    if extension in ['csv']:
        df = pd.read_csv(BytesIO(file_bytes))
        df['_source_row'] = df.index + 1
        return {'dataframes': [df], 'source_type': 'csv', 'source_name': filename}
    if extension in ['xlsx', 'xls']:
        xl = pd.ExcelFile(BytesIO(file_bytes))
        dataframes = []
        for sheet_name in xl.sheet_names:
            df_raw = pd.read_excel(xl, sheet_name=sheet_name, header=None)
            dataframes.append(_prepare_dataframe(df_raw))
        return {
            'dataframes': dataframes,
            'sheet_names': xl.sheet_names,
            'source_type': 'excel',
            'source_name': filename,
            'file_bytes': file_bytes,
        }
    if extension in ['pdf']:
        tables = _parse_pdf_tables(file_bytes)
        return {
            'dataframes': tables,
            'source_type': 'pdf',
            'source_name': filename,
            'file_bytes': file_bytes,
        }

    return {'dataframes': [], 'source_type': extension, 'source_name': filename}


def _load_catalog_from_url(url: str) -> Dict:
    """Load catalog content from a URL."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    filename = url.split('/')[-1]
    extension = filename.split('.')[-1].lower()
    file_bytes = response.content

    if extension == 'csv':
        df = pd.read_csv(BytesIO(file_bytes))
        df['_source_row'] = df.index + 1
        return {'dataframes': [df], 'source_type': 'csv', 'source_name': filename, 'source_url': url}
    if extension in ['xlsx', 'xls']:
        xl = pd.ExcelFile(BytesIO(file_bytes))
        dataframes = []
        for sheet_name in xl.sheet_names:
            df_raw = pd.read_excel(xl, sheet_name=sheet_name, header=None)
            dataframes.append(_prepare_dataframe(df_raw))
        return {
            'dataframes': dataframes,
            'sheet_names': xl.sheet_names,
            'source_type': 'excel',
            'source_name': filename,
            'source_url': url,
            'file_bytes': file_bytes,
        }
    if extension == 'pdf':
        tables = _parse_pdf_tables(file_bytes)
        return {
            'dataframes': tables,
            'source_type': 'pdf',
            'source_name': filename,
            'source_url': url,
            'file_bytes': file_bytes,
        }

    return {'dataframes': [], 'source_type': extension, 'source_name': filename, 'source_url': url}


def show_supplier_portal():
    """Supplier portal for profile management and catalog uploads."""
    st.markdown('<div class="main-header">🏷️ Supplier Portal</div>', unsafe_allow_html=True)

    suppliers = db.get_all_suppliers()
    supplier_lookup = {f"{s.get('name', 'Unnamed')} ({s.get('email', 'no-email')})": s['supplier_id'] for s in suppliers}
    supplier_options = ["Create new supplier"] + list(supplier_lookup.keys())

    selected_supplier = st.selectbox("Supplier Profile", supplier_options)
    selected_supplier_id = supplier_lookup.get(selected_supplier) if selected_supplier != "Create new supplier" else None
    selected_data = db.get_supplier(selected_supplier_id) if selected_supplier_id else {}

    with st.form("supplier_profile_form"):
        st.markdown("### Supplier Details")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Supplier Name", value=selected_data.get('name', ''))
            email = st.text_input("Email", value=selected_data.get('email', ''))
            phone = st.text_input("Phone", value=selected_data.get('phone', ''))
        with col2:
            website = st.text_input("Website", value=selected_data.get('website', ''))
            contact_person = st.text_input("Contact Person", value=selected_data.get('contact_person', ''))
            categories = st.text_input("Categories (comma-separated)", value=', '.join(selected_data.get('categories', [])))

        address = st.text_area("Address", value=selected_data.get('address', ''))
        notes = st.text_area("Notes", value=selected_data.get('notes', ''))

        submitted = st.form_submit_button("Save Supplier")
        if submitted:
            supplier_id = db.save_supplier({
                'supplier_id': selected_data.get('supplier_id'),
                'name': name,
                'email': email,
                'phone': phone,
                'website': website,
                'contact_person': contact_person,
                'categories': [c.strip() for c in categories.split(',') if c.strip()],
                'address': address,
                'notes': notes,
                'created_at': selected_data.get('created_at'),
            })
            st.session_state.supplier_id = supplier_id
            st.success("Supplier profile saved.")

    active_supplier_id = st.session_state.supplier_id or selected_supplier_id
    if not active_supplier_id:
        st.info("Save or select a supplier to upload catalogs.")
        return

    st.markdown("---")
    st.markdown("### Catalog Upload")
    catalog_name = st.text_input("Catalog Name", value="Main Catalog")
    default_currency = st.selectbox("Default Currency", ["USD", "EUR", "GBP", "AED", "SAR", "RUB"], index=0)
    extract_images = st.checkbox("Extract embedded images (Excel/PDF)", help="Slower for large catalogs")

    uploaded_file = st.file_uploader("Upload Catalog (CSV, XLSX, PDF)", type=["csv", "xlsx", "xls", "pdf"])
    catalog_url = st.text_input("Or paste catalog URL (CSV/XLSX/PDF)")

    catalog_data = None
    if uploaded_file:
        try:
            catalog_data = _load_catalog_from_file(uploaded_file)
        except Exception as exc:
            st.error(f"Failed to read file: {exc}")
    elif catalog_url:
        try:
            catalog_data = _load_catalog_from_url(catalog_url)
        except Exception as exc:
            st.error(f"Failed to fetch URL: {exc}")

    if catalog_data and catalog_data.get('dataframes'):
        st.markdown("#### Preview & Column Mapping")
        sheet_names = catalog_data.get('sheet_names', [])
        is_multi_sheet = catalog_data.get('source_type') == 'excel' and len(sheet_names) > 1
        bulk_import_all = False

        if is_multi_sheet:
            bulk_import_all = st.checkbox("Bulk import all sheets (auto-detect columns)")

        if bulk_import_all:
            summary_rows = []
            image_map = {}
            pdf_images = []
            image_dir = ''
            if extract_images and catalog_data.get('file_bytes'):
                image_dir = os.path.join(db.db_path, 'catalog_images', active_supplier_id, datetime.now().strftime('%Y%m%d_%H%M%S'))
                if catalog_data.get('source_type') == 'excel':
                    image_map = _extract_excel_images(catalog_data['file_bytes'], image_dir)
                elif catalog_data.get('source_type') == 'pdf':
                    pdf_images = _extract_pdf_images(catalog_data['file_bytes'], image_dir)
            for index, sheet_label in enumerate(sheet_names):
                sheet_df = catalog_data['dataframes'][index]
                guessed = _guess_column_map(sheet_df)
                summary_rows.append({
                    'Sheet': sheet_label,
                    'Rows': len(sheet_df),
                    'Item Column': guessed['item'] or 'Missing',
                    'Price Column': guessed['price'] or 'Missing',
                    'Photo Column': guessed['photo'] or 'Missing',
                })

            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

            if st.button("Bulk Save Catalogs"):
                saved = 0
                skipped = 0
                total_items = 0

                for index, sheet_label in enumerate(sheet_names):
                    sheet_df = catalog_data['dataframes'][index]
                    guessed = _guess_column_map(sheet_df)
                    if not guessed['item']:
                        skipped += 1
                        continue

                    catalog_items = _build_catalog_items(sheet_df, guessed, default_currency, image_map, sheet_label)
                    if not catalog_items:
                        skipped += 1
                        continue

                    db.save_supplier_catalog(
                        active_supplier_id,
                        {
                            'name': f"{catalog_name} - {sheet_label}",
                            'source_type': catalog_data.get('source_type', ''),
                            'source_name': catalog_data.get('source_name', ''),
                            'source_url': catalog_data.get('source_url', ''),
                            'image_dir': image_dir,
                            'image_count': len(image_map) or len(pdf_images),
                        },
                        catalog_items,
                    )
                    saved += 1
                    total_items += len(catalog_items)

                st.success(f"Saved {saved} catalogs ({total_items} items). Skipped {skipped} sheets.")
        else:
            if sheet_names and len(sheet_names) > 1:
                sheet_label = st.selectbox("Select Sheet", sheet_names)
                sheet_index = sheet_names.index(sheet_label)
                df = catalog_data['dataframes'][sheet_index]
            else:
                df = catalog_data['dataframes'][0]
            st.dataframe(df.drop(columns=['_source_row'], errors='ignore').head(10), use_container_width=True)

            column_options = ['(none)'] + list(df.columns)
            guessed = _guess_column_map(df)

            col1, col2, col3 = st.columns(3)
            with col1:
                item_col = st.selectbox("Item Name Column", column_options,
                                        index=column_options.index(guessed['item']) if guessed['item'] in column_options else 0)
                desc_col = st.selectbox("Description Column", column_options,
                                        index=column_options.index(guessed['description']) if guessed['description'] in column_options else 0)
            with col2:
                spec_col = st.selectbox("Specification Column", column_options,
                                        index=column_options.index(guessed['specification']) if guessed['specification'] in column_options else 0)
                unit_col = st.selectbox("Unit Column", column_options,
                                        index=column_options.index(guessed['unit']) if guessed['unit'] in column_options else 0)
            with col3:
                price_col = st.selectbox("Price Column", column_options,
                                         index=column_options.index(guessed['price']) if guessed['price'] in column_options else 0)
                currency_col = st.selectbox("Currency Column", column_options,
                                            index=column_options.index(guessed['currency']) if guessed['currency'] in column_options else 0)
            photo_col = st.selectbox("Photo Column", column_options,
                                     index=column_options.index(guessed['photo']) if guessed['photo'] in column_options else 0)

            if st.button("Save Catalog"):
                image_map = {}
                pdf_images = []
                image_dir = ''
                if extract_images and catalog_data.get('file_bytes'):
                    image_dir = os.path.join(db.db_path, 'catalog_images', active_supplier_id, datetime.now().strftime('%Y%m%d_%H%M%S'))
                    if catalog_data.get('source_type') == 'excel':
                        image_map = _extract_excel_images(catalog_data['file_bytes'], image_dir)
                    elif catalog_data.get('source_type') == 'pdf':
                        pdf_images = _extract_pdf_images(catalog_data['file_bytes'], image_dir)

                column_map = {
                    'item': '' if item_col == '(none)' else item_col,
                    'description': '' if desc_col == '(none)' else desc_col,
                    'specification': '' if spec_col == '(none)' else spec_col,
                    'unit': '' if unit_col == '(none)' else unit_col,
                    'price': '' if price_col == '(none)' else price_col,
                    'currency': '' if currency_col == '(none)' else currency_col,
                    'photo': '' if photo_col == '(none)' else photo_col,
                }
                catalog_items = _build_catalog_items(df, column_map, default_currency, image_map, sheet_label if sheet_names else '')
                if not catalog_items:
                    st.error("No catalog items were created. Please confirm the Item Name column.")
                else:
                    catalog_id = db.save_supplier_catalog(
                        active_supplier_id,
                        {
                            'name': catalog_name,
                            'source_type': catalog_data.get('source_type', ''),
                            'source_name': catalog_data.get('source_name', ''),
                            'source_url': catalog_data.get('source_url', ''),
                            'image_dir': image_dir,
                            'image_count': len(image_map) or len(pdf_images),
                        },
                        catalog_items,
                    )
                    st.success(f"Catalog saved ({len(catalog_items)} items). Catalog ID: {catalog_id}")

    st.markdown("---")
    st.markdown("### Existing Catalogs")
    catalogs = db.get_supplier_catalogs(active_supplier_id)
    if not catalogs:
        st.info("No catalogs uploaded yet.")
    else:
        for catalog in catalogs:
            st.write(f"- {catalog.get('name', 'Catalog')} ({len(catalog.get('items', []))} items)")

        catalog_names = {f"{c.get('name', 'Catalog')} ({len(c.get('items', []))} items)": c for c in catalogs}
        selected_catalog = st.selectbox("Preview Catalog Items", list(catalog_names.keys()))
        selected_items = catalog_names[selected_catalog].get('items', [])
        preview_df = pd.DataFrame(selected_items).head(25)
        if not preview_df.empty:
            st.dataframe(preview_df, use_container_width=True, hide_index=True)


def _similarity_score(a: str, b: str) -> float:
    """Similarity score for matching catalog items."""
    return SequenceMatcher(None, _normalize_text(a), _normalize_text(b)).ratio()


def _match_catalog_item(proc_name: str, catalog_items: List[Dict]) -> Dict:
    """Find the best catalog item match for a procurement item."""
    best_match = None
    best_score = 0.0

    for item in catalog_items:
        candidate_name = item.get('item_name', '')
        score = _similarity_score(proc_name, candidate_name)
        if score > best_score:
            best_score = score
            best_match = item

    if best_match and best_score >= 0.55:
        return {**best_match, 'match_score': best_score}
    return {}


def _compose_rfp_email(project: Dict, supplier: Dict, items: List[Dict]) -> Dict:
    """Create RFP email subject/body for a supplier."""
    hotel = project.get('hotel_info', {})
    subject = f"RFP: {hotel.get('property_name', 'Hotel')} - {project.get('project_id', '')}"

    lines = [
        f"Hello {supplier.get('contact_person') or supplier.get('name')},",
        "",
        "Please provide a quotation for the following items:",
        "",
    ]

    for item in items:
        line = f"- {item['item_name']} | Qty: {item['quantity']}"
        if item.get('specification'):
            line += f" | Spec: {item['specification']}"
        if item.get('price_available'):
            line += f" | Target Price: {item['price']} {item.get('currency', '')}".rstrip()
        lines.append(line)

    lines.extend([
        "",
        "Please confirm lead times, delivery terms, and any alternatives.",
        "",
        "Thank you,",
        hotel.get('project_name', 'Procurement Team')
    ])

    return {
        'subject': subject,
        'body': "\n".join(lines),
    }


def _send_email_smtp(smtp_config: Dict, to_email: str, subject: str, body: str) -> str:
    """Send an email via SMTP and return status."""
    import smtplib
    from email.message import EmailMessage

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = smtp_config.get('from_email')
    msg['To'] = to_email
    msg.set_content(body)

    with smtplib.SMTP(smtp_config.get('host'), smtp_config.get('port', 587)) as server:
        if smtp_config.get('use_tls', True):
            server.starttls()
        server.login(smtp_config.get('username'), smtp_config.get('password'))
        server.send_message(msg)

    return "sent"


def show_supplier_comparison():
    """Compare procurement list with supplier catalogs and send RFP."""
    st.markdown('<div class="main-header">🤝 Supplier Comparison & RFP</div>', unsafe_allow_html=True)

    projects = db.get_all_projects()
    if not projects:
        st.info("No saved projects found. Create and save a project first.")
        return

    project_options = {
        f"{p['hotel_info']['property_name']} - {p['hotel_info']['city']} ({p['project_id']})": p['project_id']
        for p in projects
    }
    selected_project_name = st.selectbox("Select Project", list(project_options.keys()))
    project_id = project_options[selected_project_name]
    project = db.get_project(project_id)

    suppliers = db.get_all_suppliers()
    if not suppliers:
        st.info("No suppliers available. Ask suppliers to upload catalogs first.")
        return

    supplier_choices = {f"{s.get('name')} ({s.get('email')})": s['supplier_id'] for s in suppliers}
    selected_suppliers = st.multiselect("Select Suppliers", list(supplier_choices.keys()))
    if not selected_suppliers:
        st.info("Select at least one supplier to compare.")
        return

    selected_supplier_ids = [supplier_choices[name] for name in selected_suppliers]
    catalog_items = db.get_all_catalog_items(selected_supplier_ids)
    if not catalog_items:
        st.warning("No catalog items found for selected suppliers.")
        return

    # Group catalog items by supplier
    catalog_by_supplier = {}
    for item in catalog_items:
        catalog_by_supplier.setdefault(item['supplier_id'], []).append(item)

    project_items = db.get_project_items(project_id)
    comparison_rows = []
    match_map = {}

    for idx, proj_item in enumerate(project_items):
        item_data = proj_item.get('item_data', {})
        proc_name = item_data.get('Item') or item_data.get('item') or 'Item'
        quantity = item_data.get('Total Qty', item_data.get('Total_Qty', 0))
        specification = item_data.get('Specification', item_data.get('specification', ''))

        row = {
            'Item': proc_name,
            'Qty': quantity,
            'Specification': specification,
            'Selected Supplier': ''
        }

        match_map[idx] = {}

        for supplier_name, supplier_id in supplier_choices.items():
            if supplier_id not in selected_supplier_ids:
                continue
            match = _match_catalog_item(proc_name, catalog_by_supplier.get(supplier_id, []))
            match_map[idx][supplier_id] = match
            if match:
                price_label = match['price'] if match.get('price_available') else 'POR'
                row[f"{supplier_name} Price"] = price_label
                row[f"{supplier_name} Match"] = match.get('item_name', '')
            else:
                row[f"{supplier_name} Price"] = 'No match'
                row[f"{supplier_name} Match"] = ''

        comparison_rows.append(row)

    df = pd.DataFrame(comparison_rows)
    supplier_options = [''] + selected_suppliers

    st.markdown("### Comparison Table")
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Selected Supplier': st.column_config.SelectboxColumn(
                "Selected Supplier",
                options=supplier_options
            )
        }
    )

    # Build RFP selections
    selected_items_by_supplier = {}
    for row_index, row in edited_df.iterrows():
        chosen_supplier_label = row.get('Selected Supplier')
        if not chosen_supplier_label:
            continue
        supplier_id = supplier_choices.get(chosen_supplier_label)
        match = match_map.get(row_index, {}).get(supplier_id, {})
        if not match:
            continue

        selected_items_by_supplier.setdefault(supplier_id, []).append({
            'item_name': row.get('Item'),
            'quantity': row.get('Qty', 0),
            'specification': row.get('Specification', ''),
            'price': match.get('price'),
            'currency': match.get('currency'),
            'price_available': match.get('price_available', False),
        })

    if selected_items_by_supplier:
        st.markdown("### RFP Summary")
        for supplier_id, items in selected_items_by_supplier.items():
            supplier = db.get_supplier(supplier_id)
            total_items = len(items)
            total_value = sum(
                (item['price'] or 0) * item['quantity']
                for item in items
                if item.get('price_available')
            )
            st.write(f"- {supplier.get('name')}: {total_items} items | Estimated: {total_value:,.2f}")

        smtp_config = st.secrets.get("smtp", {})
        if st.button("📧 Send RFP Emails"):
            for supplier_id, items in selected_items_by_supplier.items():
                supplier = db.get_supplier(supplier_id)
                email_content = _compose_rfp_email(project, supplier, items)
                if smtp_config:
                    try:
                        _send_email_smtp(smtp_config, supplier.get('email'), email_content['subject'], email_content['body'])
                        st.success(f"Email sent to {supplier.get('name')}")
                    except Exception as exc:
                        st.error(f"Failed to send to {supplier.get('name')}: {exc}")
                else:
                    mailto = f"mailto:{supplier.get('email')}?subject={quote(email_content['subject'])}&body={quote(email_content['body'])}"
                    st.markdown(f"[Open email draft for {supplier.get('name')}]({mailto})")
    else:
        st.info("Select suppliers for each item to generate RFPs.")

def display_results():
    """Display calculation results"""
    results = st.session_state.results

    # Summary metrics
    st.markdown("### 📊 Summary")
    summary = results.get('summary', {})

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Hotel", summary.get('hotel_name', 'N/A'))
    with col2:
        st.metric("Total Rooms", summary.get('total_rooms', 0))
    with col3:
        st.metric("Total Beds", summary.get('total_beds', 0))
    with col4:
        st.metric("Brand", summary.get('brand', 'N/A'))
    with col5:
        st.metric("Floors", summary.get('num_floors', 0))

    st.markdown("---")

    # Category counts
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        linen_count = sum([len(results.get('linen', []))])
        st.metric("Linen SKUs", linen_count)
    with col2:
        furniture_count = len(results.get('furniture', []))
        st.metric("Furniture Items", furniture_count)
    with col3:
        restaurant_count = len(results.get('restaurant', []))
        st.metric("Restaurant Items", restaurant_count)
    with col4:
        total_items = sum([
            len(results.get('guest_rooms', [])),
            len(results.get('linen', [])),
            len(results.get('furniture', [])),
            len(results.get('restaurant', [])),
            len(results.get('kitchen', [])),
            len(results.get('spa', [])),
            len(results.get('public_areas', []))
        ])
        st.metric("Total Line Items", total_items)

    st.markdown("---")

    # Detailed tables with more tabs
    tabs = st.tabs([
        "🛏️ Guest Rooms",
        "🧺 Linen",
        "🛁 Bathroom",
        "🪑 Furniture",
        "🧴 Amenities",
        "🍽️ Restaurant",
        "👨‍🍳 Kitchen",
        "💆 Spa",
        "🏊 Pool",
        "💪 Gym",
        "🏛️ Public Areas",
        "📊 Conference",
        "🏢 Back of House"
    ])

    # Guest Rooms
    with tabs[0]:
        if results.get('guest_rooms'):
            df = pd.DataFrame(results['guest_rooms'])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No guest room items calculated")

    # Linen
    with tabs[1]:
        if results.get('linen'):
            df = pd.DataFrame(results['linen'])
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Linen summary by item
            if 'Final Qty' in df.columns:
                st.markdown("#### Linen Summary by Item")
                linen_summary = df.groupby('Item')['Final Qty'].sum().reset_index()
                linen_summary.columns = ['Item', 'Total Quantity']
                linen_summary = linen_summary.sort_values('Total Quantity', ascending=False)
                st.dataframe(linen_summary, use_container_width=True, hide_index=True)
        else:
            st.info("No linen items calculated")

    # Bathroom
    with tabs[2]:
        if results.get('bathroom'):
            df = pd.DataFrame(results['bathroom'])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No bathroom items calculated")

    # Furniture
    with tabs[3]:
        if results.get('furniture'):
            df = pd.DataFrame(results['furniture'])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No furniture items calculated")

    # Amenities
    with tabs[4]:
        if results.get('amenities'):
            df = pd.DataFrame(results['amenities'])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No amenities calculated")

    # Restaurant
    with tabs[5]:
        if results.get('restaurant'):
            df = pd.DataFrame(results['restaurant'])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No restaurant configured")

    # Kitchen
    with tabs[6]:
        if results.get('kitchen'):
            df = pd.DataFrame(results['kitchen'])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No kitchen configured")

    # Spa
    with tabs[7]:
        if results.get('spa'):
            df = pd.DataFrame(results['spa'])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No spa configured")

    # Pool
    with tabs[8]:
        if results.get('pool'):
            df = pd.DataFrame(results['pool'])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No pool configured")

    # Gym
    with tabs[9]:
        if results.get('gym'):
            df = pd.DataFrame(results['gym'])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No gym configured")

    # Public Areas
    with tabs[10]:
        if results.get('public_areas'):
            df = pd.DataFrame(results['public_areas'])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No public area items")

    # Conference
    with tabs[11]:
        if results.get('conference'):
            df = pd.DataFrame(results['conference'])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No conference rooms configured")

    # Back of House
    with tabs[12]:
        if results.get('back_of_house'):
            df = pd.DataFrame(results['back_of_house'])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No back of house items calculated")

    # Export buttons
    st.markdown("---")
    st.markdown("### 📥 Export Results")
    col1, col2 = st.columns(2)

    with col1:
        excel_file = generate_excel_export(results)
        st.download_button(
            label="📊 Download Excel Report",
            data=excel_file,
            file_name=f"{st.session_state.hotel_name}_Procurement_List_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with col2:
        st.button("🔄 New Calculation", on_click=reset_calculation, use_container_width=True)

def generate_excel_export(results):
    """Generate Excel file with all results"""
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Summary sheet
        summary_data = {
            'Metric': list(results['summary'].keys()),
            'Value': list(results['summary'].values())
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

        # Individual category sheets
        categories = [
            ('guest_rooms', 'Guest Rooms'),
            ('linen', 'Linen'),
            ('bathroom', 'Bathroom'),
            ('furniture', 'Furniture'),
            ('amenities', 'Amenities'),
            ('restaurant', 'Restaurant'),
            ('kitchen', 'Kitchen'),
            ('spa', 'Spa'),
            ('pool', 'Pool'),
            ('gym', 'Gym'),
            ('public_areas', 'Public Areas'),
            ('conference', 'Conference'),
            ('back_of_house', 'Back of House')
        ]

        for key, sheet_name in categories:
            if results.get(key):
                df = pd.DataFrame(results[key])
                df.to_excel(writer, sheet_name=sheet_name, index=False)

                # Auto-adjust column widths
                worksheet = writer.sheets[sheet_name]
                for idx, col in enumerate(df.columns):
                    max_length = max(
                        df[col].astype(str).apply(len).max(),
                        len(str(col))
                    )
                    worksheet.column_dimensions[openpyxl.utils.get_column_letter(idx + 1)].width = min(max_length + 2, 50)

    output.seek(0)
    return output.getvalue()

def reset_calculation():
    """Reset calculation state"""
    st.session_state.calculation_done = False
    st.session_state.results = {}
    st.rerun()

def show_project_history():
    """Display project history"""
    st.markdown('<div class="main-header">📚 Project History</div>', unsafe_allow_html=True)

    projects = db.get_all_projects()

    if not projects:
        st.info("No projects saved yet. Create your first project in the 'New Project' view.")
        return

    st.markdown(f"### Total Projects: {len(projects)}")

    # Project list
    for project in reversed(projects):  # Show newest first
        with st.expander(f"🏨 {project['hotel_info']['property_name']} - {project['hotel_info']['city']} ({project['project_id']})"):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.write("**Brand:**", project['hotel_info']['brand'])
                st.write("**City:**", project['hotel_info']['city'])
                st.write("**Country:**", project['hotel_info']['country'])

            with col2:
                st.write("**Total Rooms:**", project['hotel_info']['total_rooms'])
                st.write("**Floors:**", project['hotel_info']['num_floors'])
                st.write("**Created:**", project['created_at'][:10])

            with col3:
                summary = db.get_procurement_summary(project['project_id'])
                st.metric("Total Items", summary['total_items'])
                st.metric("Ordered", f"{summary['ordered_percent']}%")

            # Action buttons
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("View Checklist", key=f"view_{project['project_id']}"):
                    st.session_state.current_project_id = project['project_id']
                    st.session_state.view_mode = 'checklist'
                    st.rerun()

            with col2:
                if st.button("Print by Dept", key=f"print_{project['project_id']}"):
                    print_by_department(project['project_id'])

            with col3:
                excel_data = db.export_project_to_excel(project['project_id'], '')
                st.download_button(
                    label="📥 Download",
                    data=excel_data,
                    file_name=f"{project['hotel_info']['property_name']}_{project['project_id']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_{project['project_id']}"
                )

            with col4:
                if st.button("🗑️ Delete", key=f"delete_{project['project_id']}"):
                    if st.confirm("Are you sure?"):
                        db.delete_project(project['project_id'])
                        st.success("Project deleted")
                        st.rerun()

def show_procurement_checklist():
    """Show mobile-friendly procurement checklist"""
    st.markdown('<div class="main-header">📋 Procurement Checklist</div>', unsafe_allow_html=True)

    # Project selector
    projects = db.get_all_projects()

    if not projects:
        st.warning("No projects found. Create a project first.")
        return

    project_options = {
        f"{p['hotel_info']['property_name']} - {p['hotel_info']['city']} ({p['project_id']})": p['project_id']
        for p in projects
    }

    selected_project_name = st.selectbox("Select Project", list(project_options.keys()))
    project_id = project_options[selected_project_name]

    st.session_state.current_project_id = project_id

    # Get project data
    project = db.get_project(project_id)
    items = db.get_project_items(project_id)
    summary = db.get_procurement_summary(project_id)

    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Items", summary['total_items'])
    with col2:
        st.metric("Ordered", f"{summary['ordered_count']} ({summary['ordered_percent']}%)")
    with col3:
        st.metric("Received", f"{summary['received_count']} ({summary['received_percent']}%)")
    with col4:
        st.metric("Installed", f"{summary['installed_count']} ({summary['installed_percent']}%)")

    st.markdown("---")

    # Filter options
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_dept = st.selectbox("Filter by Department", ["All"] + list(set(item['department'] for item in items)))
    with col2:
        filter_status = st.selectbox("Filter by Status", ["All", "Not Ordered", "Ordered", "Received", "Installed"])
    with col3:
        search_term = st.text_input("🔍 Search Items", "")

    # Apply filters
    filtered_items = items.copy()

    if filter_dept != "All":
        filtered_items = [item for item in filtered_items if item['department'] == filter_dept]

    if filter_status != "All":
        if filter_status == "Not Ordered":
            filtered_items = [item for item in filtered_items if not item['procurement_status']['ordered']]
        elif filter_status == "Ordered":
            filtered_items = [item for item in filtered_items if item['procurement_status']['ordered'] and not item['procurement_status']['received']]
        elif filter_status == "Received":
            filtered_items = [item for item in filtered_items if item['procurement_status']['received'] and not item['procurement_status']['installed']]
        elif filter_status == "Installed":
            filtered_items = [item for item in filtered_items if item['procurement_status']['installed']]

    if search_term:
        filtered_items = [
            item for item in filtered_items
            if search_term.lower() in str(item['item_data'].get('Item', item['item_data'].get('item', ''))).lower()
        ]

    st.markdown(f"### Showing {len(filtered_items)} items")

    # Display items as cards (mobile-friendly)
    for idx, item in enumerate(filtered_items):
        item_data = item['item_data']
        status = item['procurement_status']

        # Find original index
        original_idx = items.index(item)

        # Status badges
        status_badges = []
        if status['ordered']:
            status_badges.append("🛒 Ordered")
        if status['received']:
            status_badges.append("📦 Received")
        if status['installed']:
            status_badges.append("✅ Installed")

        status_text = " | ".join(status_badges) if status_badges else "⏸️ Pending"

        with st.container():
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**{item_data.get('Item', item_data.get('item', 'N/A'))}**")
                st.caption(f"{item['department']} • {item['category']}")
                st.caption(f"Qty: {item_data.get('Total Qty', item_data.get('Total_Qty', 0))} {item_data.get('Unit', 'pcs')}")

            with col2:
                st.markdown(f"<span style='font-size: 0.8em;'>{status_text}</span>", unsafe_allow_html=True)

                # Quick action buttons
                if not status['ordered']:
                    if st.button("Mark Ordered", key=f"order_{original_idx}"):
                        db.update_item_status(project_id, original_idx, {
                            'ordered': True,
                            'ordered_date': datetime.now().strftime('%Y-%m-%d')
                        })
                        st.rerun()
                elif not status['received']:
                    if st.button("Mark Received", key=f"receive_{original_idx}"):
                        db.update_item_status(project_id, original_idx, {
                            'received': True,
                            'received_date': datetime.now().strftime('%Y-%m-%d')
                        })
                        st.rerun()
                elif not status['installed']:
                    if st.button("Mark Installed", key=f"install_{original_idx}"):
                        db.update_item_status(project_id, original_idx, {
                            'installed': True,
                            'installed_date': datetime.now().strftime('%Y-%m-%d')
                        })
                        st.rerun()

            # Expandable details
            with st.expander("📦 Procurement Details"):
                col1, col2 = st.columns(2)

                with col1:
                    supplier = st.text_input("Supplier", value=status['supplier'], key=f"supplier_{original_idx}")
                    po_number = st.text_input("PO Number", value=status['po_number'], key=f"po_{original_idx}")
                    unit_price = st.number_input("Unit Price", value=float(status['unit_price']), key=f"price_{original_idx}")

                with col2:
                    ordered_qty = st.number_input("Ordered Qty", value=status['ordered_qty'], key=f"oqty_{original_idx}")
                    received_qty = st.number_input("Received Qty", value=status['received_qty'], key=f"rqty_{original_idx}")

                notes = st.text_area("Notes", value=status['notes'], key=f"notes_{original_idx}")

                if st.button("💾 Save Details", key=f"save_{original_idx}"):
                    db.update_item_status(project_id, original_idx, {
                        'supplier': supplier,
                        'po_number': po_number,
                        'unit_price': unit_price,
                        'ordered_qty': ordered_qty,
                        'received_qty': received_qty,
                        'total_price': unit_price * ordered_qty,
                        'notes': notes
                    })
                    st.success("Saved!")
                    st.rerun()

            # Installation Specifications
            with st.expander("🔧 Installation Specifications"):
                install_specs = status.get('installation_specs', {})

                col1, col2 = st.columns(2)

                with col1:
                    height_cm = st.number_input(
                        "Installation Height (cm from floor)",
                        value=int(install_specs.get('height_cm', 0)),
                        min_value=0,
                        max_value=300,
                        key=f"height_{original_idx}",
                        help="Default heights pre-filled from standards"
                    )
                    distance_fixture = st.text_input(
                        "Distance from Fixture",
                        value=install_specs.get('distance_from_fixture', ''),
                        key=f"dist_fix_{original_idx}",
                        placeholder="e.g., 20cm above sink"
                    )

                with col2:
                    installer = st.text_input(
                        "Installer Assigned",
                        value=install_specs.get('installer_assigned', ''),
                        key=f"installer_{original_idx}"
                    )

                install_notes = st.text_area(
                    "Installation Notes",
                    value=install_specs.get('installation_notes', ''),
                    key=f"install_notes_{original_idx}",
                    placeholder="Special instructions, tools needed, etc."
                )

                if st.button("💾 Save Installation Specs", key=f"save_install_{original_idx}"):
                    db.update_item_status(project_id, original_idx, {
                        'installation_specs': {
                            'height_cm': height_cm,
                            'distance_from_fixture': distance_fixture,
                            'installation_notes': install_notes,
                            'installer_assigned': installer
                        }
                    })
                    st.success("Installation specs saved!")
                    st.rerun()

            st.markdown("---")

def show_project_comparison():
    """Compare two projects"""
    st.markdown('<div class="main-header">📊 Project Comparison</div>', unsafe_allow_html=True)

    projects = db.get_all_projects()

    if len(projects) < 2:
        st.warning("Need at least 2 projects to compare.")
        return

    project_options = {
        f"{p['hotel_info']['property_name']} - {p['hotel_info']['city']}": p['project_id']
        for p in projects
    }

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Project 1")
        project1_name = st.selectbox("Select Project 1", list(project_options.keys()), key="p1")
        project1_id = project_options[project1_name]

    with col2:
        st.markdown("### Project 2")
        project2_name = st.selectbox("Select Project 2", list(project_options.keys()), key="p2")
        project2_id = project_options[project2_name]

    if project1_id == project2_id:
        st.warning("Please select different projects to compare.")
        return

    # Get comparison data
    comparison = db.compare_projects(project1_id, project2_id)

    # Display comparison
    st.markdown("### Comparison Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Rooms", comparison['project1']['rooms'],
                 delta=comparison['differences']['rooms_diff'])

    with col2:
        st.metric("Total Items", comparison['project1']['total_items'],
                 delta=comparison['differences']['items_diff'])

    with col3:
        st.metric("Total Budget", f"${comparison['project1']['total_budget']:,.0f}",
                 delta=f"${comparison['differences']['budget_diff']:,.0f}")

    # Detailed comparison table
    st.markdown("### Detailed Comparison")

    items1 = db.get_project_items(project1_id)
    items2 = db.get_project_items(project2_id)

    # Group by department
    depts1 = {}
    for item in items1:
        dept = item['department']
        if dept not in depts1:
            depts1[dept] = []
        depts1[dept].append(item)

    depts2 = {}
    for item in items2:
        dept = item['department']
        if dept not in depts2:
            depts2[dept] = []
        depts2[dept].append(item)

    all_depts = set(list(depts1.keys()) + list(depts2.keys()))

    for dept in sorted(all_depts):
        with st.expander(f"📂 {dept}"):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown(f"**{comparison['project1']['name']}**")
                st.write(f"Items: {len(depts1.get(dept, []))}")

            with col2:
                st.markdown(f"**{comparison['project2']['name']}**")
                st.write(f"Items: {len(depts2.get(dept, []))}")

def show_capex_dashboard():
    """CAPEX Management Dashboard with budget tracking and analytics"""
    st.markdown('<div class="main-header">💰 CAPEX Management Dashboard</div>', unsafe_allow_html=True)

    projects = db.get_all_projects()

    if not projects:
        st.warning("No projects found. Create a project first.")
        return

    # Project selector
    project_options = {
        f"{p['hotel_info']['property_name']} - {p['hotel_info']['city']} ({p['project_id']})": p['project_id']
        for p in projects
    }

    selected_project_name = st.selectbox("Select Project", list(project_options.keys()))
    project_id = project_options[selected_project_name]

    # Get budget summary
    budget_summary = db.get_budget_summary(project_id)
    items = db.get_project_items(project_id)

    # Overall CAPEX Summary
    st.markdown("### 📊 Overall CAPEX Summary")

    total_budget = sum(dept['budget_total'] for dept in budget_summary.values())
    total_actual = sum(dept['actual_total'] for dept in budget_summary.values())
    total_variance = total_budget - total_actual

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Budget", f"${total_budget:,.2f}")
    with col2:
        st.metric("Total Actual", f"${total_actual:,.2f}")
    with col3:
        variance_color = "normal" if total_variance >= 0 else "inverse"
        st.metric("Variance", f"${total_variance:,.2f}",
                 delta=f"{(total_variance/total_budget*100) if total_budget > 0 else 0:.1f}%")
    with col4:
        spent_pct = (total_actual / total_budget * 100) if total_budget > 0 else 0
        st.metric("Budget Used", f"{spent_pct:.1f}%")

    st.markdown("---")

    # FF&E vs OS&E vs OPEX Breakdown
    st.markdown("### 🏷️ Expense Type Breakdown")

    total_ffe = sum(dept['ffe_total'] for dept in budget_summary.values())
    total_ose = sum(dept['ose_total'] for dept in budget_summary.values())
    total_opex = sum(dept['opex_total'] for dept in budget_summary.values())

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("FF&E (7yr depreciation)", f"${total_ffe:,.2f}")
        st.caption("Furniture, Fixtures & Equipment")
    with col2:
        st.metric("OS&E (1yr depreciation)", f"${total_ose:,.2f}")
        st.caption("Operating Supplies & Equipment")
    with col3:
        st.metric("OPEX (Fully expensed)", f"${total_opex:,.2f}")
        st.caption("Operational Expenditure")

    st.markdown("---")

    # Department-level Budget Tracking
    st.markdown("### 🏢 Budget by Department")

    for dept, data in sorted(budget_summary.items()):
        with st.expander(f"📂 {dept} ({data['item_count']} items)"):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Budget", f"${data['budget_total']:,.2f}")
            with col2:
                st.metric("Actual", f"${data['actual_total']:,.2f}")
            with col3:
                variance = data['variance']
                status = "🟢 Under Budget" if variance >= 0 else "🔴 Over Budget"
                st.metric("Variance", f"${variance:,.2f}")
                st.caption(status)

            # Progress bar
            if data['budget_total'] > 0:
                progress = min(data['actual_total'] / data['budget_total'], 1.0)
                st.progress(progress)
                st.caption(f"{progress*100:.1f}% of budget spent")

    st.markdown("---")

    # Approval Status Overview
    st.markdown("### ✅ Approval Status")

    approval_counts = {'draft': 0, 'submitted': 0, 'dept_approved': 0, 'finance_approved': 0, 'rejected': 0}

    for item in items:
        capex_info = item.get('capex_info', {})
        status = capex_info.get('approval_status', 'draft')
        if status in approval_counts:
            approval_counts[status] += 1

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Draft", approval_counts['draft'])
    with col2:
        st.metric("Submitted", approval_counts['submitted'])
    with col3:
        st.metric("Dept Approved", approval_counts['dept_approved'])
    with col4:
        st.metric("Finance Approved", approval_counts['finance_approved'])
    with col5:
        st.metric("Rejected", approval_counts['rejected'])

    st.markdown("---")

    # Items requiring attention
    st.markdown("### ⚠️ Items Requiring Attention")

    # Items over budget
    over_budget_items = [
        item for item in items
        if item.get('capex_info', {}).get('variance', 0) < 0
    ]

    if over_budget_items:
        st.warning(f"**{len(over_budget_items)} items over budget**")
        for item in over_budget_items[:5]:  # Show first 5
            capex_info = item.get('capex_info', {})
            item_data = item['item_data']
            st.write(f"• {item_data.get('Item', 'N/A')} - Over by ${abs(capex_info.get('variance', 0)):,.2f}")
    else:
        st.success("✅ All items within budget")

    # Pending approvals
    pending_approval = [
        item for item in items
        if item.get('capex_info', {}).get('approval_status', 'draft') in ['submitted', 'draft']
    ]

    if pending_approval:
        st.info(f"**{len(pending_approval)} items pending approval**")

def print_by_department(project_id):
    """Generate print-friendly view by department"""
    items = db.get_project_items(project_id)
    project = db.get_project(project_id)

    # Group by department
    departments = {}
    for item in items:
        dept = item['department']
        if dept not in departments:
            departments[dept] = []
        departments[dept].append(item)

    # Create Excel with sheets per department
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for dept, dept_items in departments.items():
            items_data = []

            for item in dept_items:
                item_data = item['item_data']
                status = item['procurement_status']

                record = {
                    'Item': item_data.get('Item', item_data.get('item', 'N/A')),
                    'Category': item['category'],
                    'Qty': item_data.get('Total Qty', item_data.get('Total_Qty', 0)),
                    'Unit': item_data.get('Unit', 'pcs'),
                    'Ordered': '✓' if status['ordered'] else '',
                    'Received': '✓' if status['received'] else '',
                    'Supplier': status['supplier'],
                    'PO#': status['po_number'],
                    'Unit Price': status['unit_price'],
                    'Total Price': status['total_price']
                }
                items_data.append(record)

            df = pd.DataFrame(items_data)

            # Clean sheet name (max 31 chars, no special chars)
            sheet_name = dept.replace('/', '-')[:31]
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    output.seek(0)

    st.download_button(
        label=f"📄 Download Department Reports",
        data=output.getvalue(),
        file_name=f"{project['hotel_info']['property_name']}_by_department.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ============================================================================
# MAIN APPLICATION UI
# ============================================================================

# Title
st.markdown('<div class="main-header">🏨 Hotel Procurement Calculator</div>', unsafe_allow_html=True)
st.markdown("### Automated FF&E and OS&E Calculation System")

# Sidebar
with st.sidebar:
    st.image("https://via.placeholder.com/150x80/1f77b4/ffffff?text=Hotel+Logo", width=150)
    st.markdown("---")

    st.markdown("### 🔐 Access")
    role = st.radio("Select Role", ["Hotel", "Supplier"], key="role_selector")
    auth_config = st.secrets.get("auth", {})
    if auth_config:
        password = st.text_input("Password", type="password")
        required_password = auth_config.get(f"{role.lower()}_password")
        if required_password and password != required_password:
            st.warning("Invalid password for this role.")
            st.stop()

    st.session_state.user_role = role.lower()

    # View mode selector
    st.markdown("### 📁 Menu")
    if st.session_state.user_role == 'supplier':
        view_mode = st.radio(
            "Select View",
            ["Supplier Portal"],
            key="view_mode_radio"
        )
        st.session_state.view_mode = 'supplier_portal'
    else:
        view_mode = st.radio(
            "Select View",
            ["New Project", "Project History", "Checklist", "Supplier Comparison", "CAPEX Dashboard", "Comparison"],
            key="view_mode_radio"
        )

        if view_mode == "New Project":
            st.session_state.view_mode = 'new_project'
        elif view_mode == "Project History":
            st.session_state.view_mode = 'history'
        elif view_mode == "Checklist":
            st.session_state.view_mode = 'checklist'
        elif view_mode == "Supplier Comparison":
            st.session_state.view_mode = 'supplier_comparison'
        elif view_mode == "CAPEX Dashboard":
            st.session_state.view_mode = 'capex_dashboard'
        elif view_mode == "Comparison":
            st.session_state.view_mode = 'comparison'

    st.markdown("---")
    st.markdown("### Quick Guide")
    st.info("""
    1. Enter hotel details
    2. Configure room types
    3. Add facilities
    4. Click Calculate & Save
    5. Track procurement status
    6. Download reports
    """)

    st.markdown("---")
    st.markdown("### About")
    st.caption("Version 2.0")
    st.caption("Procurement Management System")

# Main form
if st.session_state.view_mode == 'supplier_portal':
    show_supplier_portal()
    st.stop()

tab1, tab2, tab3, tab4 = st.tabs(["📋 Basic Info", "🛏️ Room Configuration", "🏊 Facilities", "📊 Results"])

with tab1:
    st.markdown('<div class="section-header">Hotel Information</div>', unsafe_allow_html=True)

    # Detailed hotel identification
    st.markdown("#### Project Identification")
    col1, col2, col3 = st.columns(3)

    with col1:
        hotel_brand = st.selectbox(
            "Hotel Brand *",
            BrandStandards.get_available_brands()
        )
        project_name = st.text_input(
            "Project Name *",
            placeholder="e.g., Grand Opening 2024",
            help="Internal project identifier"
        )

    with col2:
        property_name = st.text_input(
            "Property Name *",
            placeholder="e.g., Hilton Garden Inn Downtown",
            help="Official hotel name"
        )
        city = st.text_input("City *", placeholder="e.g., New York")

    with col3:
        country = st.text_input("Country *", placeholder="e.g., USA")
        developer = st.text_input(
            "Developer/Owner",
            placeholder="e.g., ABC Hospitality Group"
        )

    # Combine for display name
    hotel_name = f"{hotel_brand} - {property_name}, {city}"

    st.markdown("---")

    st.markdown("#### Property Configuration")
    col1, col2 = st.columns(2)

    with col1:
        total_rooms = st.number_input("Total Number of Rooms *", min_value=1, max_value=1000, value=50)
        num_floors = st.number_input("Number of Floors", min_value=1, max_value=100, value=5)

    with col2:
        num_restaurants = st.number_input("Number of Restaurants/Outlets", min_value=0, max_value=20, value=1)
        num_kitchens = st.number_input("Number of Kitchens", min_value=0, max_value=10, value=1)

with tab2:
    st.markdown('<div class="section-header">Room Type Configuration</div>', unsafe_allow_html=True)

    st.info("Define your room categories. The system will calculate all FF&E and OS&E items based on these.")

    # Room types configuration
    num_room_types = st.number_input("How many room types?", min_value=1, max_value=10, value=3)

    room_types = []
    total_configured_rooms = 0

    for i in range(num_room_types):
        st.markdown(f"#### Room Type {i+1}")
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            room_name = st.text_input(f"Room Type Name", value=f"Standard" if i==0 else f"Type {i+1}", key=f"room_name_{i}")
        with col2:
            room_count = st.number_input(f"Number of Rooms", min_value=0, max_value=1000, value=25 if i==0 else 0, key=f"room_count_{i}")
        with col3:
            bed_type = st.selectbox(f"Bed Configuration", ["King", "Twin", "Queen", "Double Twin"], key=f"bed_type_{i}")
        with col4:
            num_beds = st.number_input(f"Beds per Room", min_value=1, max_value=5, value=2 if bed_type=="Twin" else 1, key=f"num_beds_{i}")
        with col5:
            num_bathrooms = st.number_input(f"Bathrooms per Room", min_value=1, max_value=3, value=1, key=f"num_bathrooms_{i}",
                                           help="Suites may have 2-3 bathrooms")

        if room_count > 0:
            room_types.append({
                "name": room_name,
                "count": room_count,
                "bed_type": bed_type,
                "num_beds": num_beds,
                "num_bathrooms": num_bathrooms
            })
            total_configured_rooms += room_count

    # Validation
    if total_configured_rooms != total_rooms:
        st.warning(f"⚠️ Room count mismatch: Configured {total_configured_rooms} rooms, but total is {total_rooms}")
    else:
        st.success(f"✅ All {total_rooms} rooms configured correctly")

with tab3:
    st.markdown('<div class="section-header">Facilities & Amenities</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Wellness & Recreation")
        has_spa = st.checkbox("Spa Facility")
        if has_spa:
            spa_rooms = st.number_input("Number of Treatment Rooms", min_value=1, max_value=50, value=4)
        else:
            spa_rooms = 0

        has_pool = st.checkbox("Swimming Pool")
        if has_pool:
            pool_type = st.selectbox("Pool Type", ["Indoor", "Outdoor", "Both"])
        else:
            pool_type = "None"

        has_gym = st.checkbox("Gym/Fitness Center", value=True)

    with col2:
        st.markdown("#### Business & Events")
        has_conference = st.checkbox("Conference Rooms")
        if has_conference:
            num_conference = st.number_input("Number of Conference Rooms", min_value=1, max_value=20, value=2)
        else:
            num_conference = 0

        has_business_center = st.checkbox("Business Center", value=True)

    st.markdown("#### Linen Standards")
    col1, col2, col3 = st.columns(3)
    with col1:
        linen_standard = st.selectbox("Linen Quality Standard", ["Economy", "Standard", "Premium", "Luxury"])
    with col2:
        par_level = st.number_input("Par Level (sets per bed)", min_value=2, max_value=10, value=4,
                                     help="How many complete sets of linen per bed (for rotation)")
    with col3:
        reserve_stock = st.slider("Reserve Stock %", min_value=0, max_value=50, value=10,
                                  help="Additional backup inventory percentage")

with tab4:
    st.markdown('<div class="section-header">Calculation Results</div>', unsafe_allow_html=True)

    # Calculate and Save button
    col1, col2 = st.columns([3, 1])
    with col1:
        calculate_btn = st.button("🔄 Calculate & Save Project", type="primary", use_container_width=True)
    with col2:
        preview_btn = st.button("👁️ Preview Only", use_container_width=True)

    if calculate_btn or preview_btn:
        if not property_name or not city or not project_name:
            st.error("Please fill in all required fields in Basic Info tab (marked with *)")
        elif total_configured_rooms != total_rooms:
            st.error("Please configure all rooms in Room Configuration tab")
        else:
            with st.spinner("Calculating procurement requirements..."):
                st.session_state.calculation_done = True

                # Generate calculations using the new calculator
                config = {
                    'hotel_name': hotel_name,
                    'hotel_brand': hotel_brand,
                    'property_name': property_name,
                    'city': city,
                    'country': country,
                    'project_name': project_name,
                    'developer': developer,
                    'room_types': room_types,
                    'total_rooms': total_rooms,
                    'num_floors': num_floors,
                    'par_level': par_level,
                    'reserve_stock': reserve_stock,
                    'has_spa': has_spa,
                    'spa_rooms': spa_rooms,
                    'has_pool': has_pool,
                    'pool_type': pool_type,
                    'has_gym': has_gym,
                    'num_restaurants': num_restaurants,
                    'num_kitchens': num_kitchens,
                    'num_conference': num_conference,
                    'linen_standard': linen_standard,
                    'has_business_center': has_business_center
                }

                calculator = ProcurementCalculator(config)
                results = calculator.calculate_all()
                st.session_state.results = results

                # Save to database if Calculate & Save was clicked
                if calculate_btn:
                    project_id = db.save_project(config, results)
                    st.session_state.current_project_id = project_id
                    st.success(f"✅ Project saved successfully! ID: {project_id}")
                else:
                    st.info("📋 Preview mode - Project not saved")

                st.rerun()

    # Display results if calculated
    if st.session_state.calculation_done:
        output_mode = st.radio(
            "Output Mode",
            ["Procurement list", "Supplier comparison"],
            horizontal=True
        )
        if output_mode == "Procurement list":
            display_results()
        else:
            show_supplier_comparison()

# Additional Views based on mode
if st.session_state.view_mode == 'supplier_portal':
    show_supplier_portal()
elif st.session_state.view_mode == 'history':
    show_project_history()
elif st.session_state.view_mode == 'checklist':
    show_procurement_checklist()
elif st.session_state.view_mode == 'supplier_comparison':
    show_supplier_comparison()
elif st.session_state.view_mode == 'capex_dashboard':
    show_capex_dashboard()
elif st.session_state.view_mode == 'comparison':
    show_project_comparison()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #7f8c8d;'>
    <p>Hotel Procurement Calculator v2.0 | Built with Streamlit</p>
    <p>© 2024 All Rights Reserved</p>
</div>
""", unsafe_allow_html=True)
