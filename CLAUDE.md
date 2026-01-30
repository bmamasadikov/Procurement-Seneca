# CLAUDE.md - AI Assistant Guide for Procurement-Seneca

## Project Overview

**Procurement-Seneca** is a Streamlit-based hotel procurement management application (v2.0) for calculating FF&E (Furniture, Fixtures & Equipment) and OS&E (Operating Supplies & Equipment) requirements. It provides automated procurement calculations, supplier management, CAPEX tracking, and RFP generation for hotel projects.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run app.py --server.enableCORS false --server.enableXsrfProtection false
```

The application runs on port **8501** by default.

## Tech Stack

- **Python 3.11**
- **Streamlit 1.31.0** - Web application framework
- **Pandas 2.2.0** - Data manipulation
- **openpyxl 3.1.2** / **xlsxwriter 3.1.9** - Excel file handling
- **pdfplumber 0.11.4** / **pymupdf 1.24.9** - PDF processing

## Project Structure

```
Procurement-Seneca/
├── app.py              # Main Streamlit application (2000+ lines)
├── calculator.py       # Procurement calculation engine
├── data_loader.py      # Excel data import utilities
├── database.py         # JSON-based persistence layer
├── departments.py      # Hotel department structure definitions
├── requirements.txt    # Python dependencies
└── .devcontainer/      # Dev container configuration
    └── devcontainer.json
```

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| `app.py` | Main entry point, UI components, session management, file import/export |
| `calculator.py` | `ProcurementCalculator` class - calculates quantities for 14 procurement categories |
| `data_loader.py` | `ProcurementDataLoader` - imports from Excel; `BrandStandards` - hotel brand multipliers |
| `database.py` | `ProcurementDatabase` - JSON-based CRUD for projects, items, suppliers, catalogs |
| `departments.py` | `HotelDepartments` and `DepartmentItems` - organizational structure definitions |

## Data Storage

The application uses a JSON-based file database stored in `procurement_data/`:

```
procurement_data/
├── projects.json           # Project metadata and configurations
├── procurement_items.json  # Calculated procurement items per project
├── suppliers.json          # Registered supplier information
├── supplier_catalogs.json  # Supplier catalog items
└── catalog_images/         # Extracted images from catalogs
```

## Key Classes and Functions

### ProcurementCalculator (`calculator.py`)

```python
calc = ProcurementCalculator(config)
results = calc.calculate_all()  # Returns dict with 14 categories
```

**Categories calculated:** `guest_rooms`, `linen`, `bathroom`, `furniture`, `amenities`, `restaurant`, `kitchen`, `spa`, `pool`, `gym`, `public_areas`, `conference`, `back_of_house`, `summary`

### ProcurementDatabase (`database.py`)

```python
db = ProcurementDatabase(db_path='procurement_data')

# Core operations
project_id = db.save_project(project_data, results)
projects = db.get_all_projects()
project = db.get_project(project_id)
db.update_project_status(project_id, status)  # 'draft', 'active', 'archived'
db.delete_project(project_id)

# Supplier operations
db.save_supplier(supplier_data)
db.save_supplier_catalog(supplier_id, catalog_items, images)
```

### BrandStandards (`data_loader.py`)

Supported hotel brands with quality multipliers:
- Hilton, Marriott, IHG, Accor, Hyatt
- Four Seasons, Ritz-Carlton
- Boutique, Independent

```python
standards = BrandStandards.get_standard('Marriott')
```

## Application Features

### User Roles

1. **Hotel User** - Creates projects, configures rooms, calculates procurement
2. **Supplier User** - Uploads catalogs, manages product listings

### Main Workflows

1. **Hotel Procurement Calculation**
   - Configure hotel (brand, rooms, facilities)
   - Calculate FF&E/OS&E requirements
   - Export to Excel by department
   - Save project for tracking

2. **Supplier Catalog Management**
   - Upload Excel or PDF catalogs
   - Map columns for data extraction
   - Extract and store product images

3. **RFP Generation**
   - Match procurement items with supplier catalogs
   - Similarity scoring (threshold: 0.55)
   - Generate email RFPs

4. **CAPEX Dashboard**
   - Track budgets by department
   - Monitor FF&E, OS&E, OPEX separately
   - Approval workflow management

## Code Conventions

### Style Guidelines

- **Type hints** are used throughout (`typing.Dict`, `typing.List`, `typing.Any`)
- **Docstrings** follow Python convention with brief descriptions
- **Private methods** prefixed with underscore (`_calculate_guest_rooms`)
- **Constants** defined as class attributes (see `HotelDepartments.STRUCTURE`)

### Streamlit Patterns

- Session state for user data: `st.session_state['key']`
- Sidebar for navigation and role selection
- Tabs for multi-section views
- Custom CSS in `st.markdown()` for styling

### Error Handling

```python
try:
    # Operation
except Exception as e:
    print(f"Error description: {e}")
    return {}  # or appropriate default
```

### Data Structures

**Project Configuration:**
```python
config = {
    'hotel_name': str,
    'hotel_brand': str,  # One of BrandStandards supported brands
    'room_types': [
        {'name': str, 'count': int, 'num_beds': int, 'bed_type': str}
    ],
    'num_floors': int,
    'num_restaurants': int,
    'num_kitchens': int,
    'has_spa': bool,
    'spa_rooms': int,
    'has_pool': bool,
    'has_gym': bool,
    'num_conference': int,
    'par_level': int,      # Linen par level (default: 4)
    'reserve_stock': int   # Reserve stock days (default: 10)
}
```

**Procurement Item:**
```python
item = {
    'Category': str,
    'Item': str,
    'Specification': str,
    'Room Type': str,
    'Qty per Room': int,
    'Room Count': int,
    'Total Qty': int,
    'Unit': str,
    'Notes': str
}
```

## Development Notes

### Adding New Procurement Categories

1. Add calculation method in `calculator.py`:
   ```python
   def _calculate_new_category(self) -> List[Dict]:
       items = []
       # calculation logic
       return items
   ```

2. Include in `calculate_all()` results dict

3. Add display section in `app.py` `display_results()` function

### Adding New Hotel Brands

Update `BrandStandards` class in `data_loader.py`:
```python
STANDARDS = {
    'NewBrand': {
        'quality_multiplier': 1.0,
        'linen_par': 4,
        # ... other standards
    }
}
```

### Modifying Department Structure

Edit `departments.py` - update `HotelDepartments.STRUCTURE` dict

## Testing

No automated tests currently exist. Manual testing workflow:

1. Run the application
2. Test each user role (Hotel/Supplier)
3. Create test project with various configurations
4. Verify calculation accuracy
5. Test import/export functionality

## Configuration

### Streamlit Secrets (optional)

Create `.streamlit/secrets.toml` for:
```toml
[smtp]
server = "smtp.example.com"
port = 587
username = "user@example.com"
password = "password"

[auth]
supplier_password = "supplier_access"
```

### Environment

- Dev container uses Python 3.11 (Debian Bookworm)
- Port 8501 exposed for Streamlit
- CORS and XSRF protection disabled for development

## Common Tasks

### Resetting Database

Delete the `procurement_data/` directory - it will be recreated on next run.

### Exporting Project Data

Use the "Export to Excel" button in the UI, or programmatically:
```python
from database import ProcurementDatabase
db = ProcurementDatabase()
project = db.get_project(project_id)
items = db.get_project_items(project_id)
```

### Debugging Calculations

```python
from calculator import ProcurementCalculator
calc = ProcurementCalculator(config)
results = calc.calculate_all()
# Inspect results['category_name'] for specific category
```

## Known Limitations

1. **File-based database** - Not suitable for concurrent multi-user access
2. **No authentication** - Basic role selection only
3. **Hardcoded paths** - Database path not configurable via environment
4. **No test coverage** - Manual testing required
5. **CORS/XSRF disabled** - Security features disabled for development

## File Locations Reference

| What | Where |
|------|-------|
| Main app entry | `app.py:1` |
| Calculator class | `calculator.py:8` |
| Database class | `database.py:11` |
| Brand standards | `data_loader.py` (BrandStandards class) |
| Department structure | `departments.py:5` |
| Custom CSS styles | `app.py:26-200` |
| Session state init | `app.py` (look for `st.session_state`) |
