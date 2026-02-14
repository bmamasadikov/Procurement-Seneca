import streamlit as st
import pandas as pd
import openpyxl
from io import BytesIO
from datetime import datetime
import json
import os
import re
from difflib import SequenceMatcher
from typing import Dict, List
from urllib.parse import quote
import requests
import pdfplumber
from calculator import ProcurementCalculator
from data_loader import BrandStandards
from database import ProcurementDatabase
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
try:
    import avenue1936_loader as av
except ImportError:
    av = None

# Page config
st.set_page_config(
    page_title="Hotel Procurement Calculator",
    page_icon="📋",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    :root {
        --background-color: #F5F5DC;
        --secondary-background-color: #F5F5DC;
        --text-color: #000000;
    }

    * {
        color: #000000 !important;
    }

    html, body,
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > .main,
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    .stMain,
    .stMainBlockContainer,
    .block-container {
        background-color: #F5F5DC !important;
    }
    
    /* Header styling */
    [data-testid="stHeader"] {
        background-color: #F5F5DC !important;
    }
    
    header {
        background-color: #F5F5DC !important;
    }
    
    .stAppHeader {
        background-color: #F5F5DC !important;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #F5F5DC !important;
    }
    
    [data-testid="stSidebarNav"] {
        background-color: #F5F5DC !important;
    }
    
    .stSidebar {
        background-color: #F5F5DC !important;
    }
    
    [data-testid="stSidebar"] > div:first-child {
        background-color: #F5F5DC !important;
    }
    
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #000000;
        text-align: center;
        padding: 1rem 0;
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #000000;
        margin-top: 2rem;
        border-bottom: 2px solid #000000;
        padding-bottom: 0.5rem;
    }
    .metric-card {
        background-color: #F5F5DC;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #000000;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #000000 !important;
    }
    
    p, span, div, label {
        color: #000000 !important;
    }
    
    .stButton > button {
        color: #000000;
        background-color: #F5F5DC;
    }

    .stTabs [data-baseweb="tab-list"] {
        background-color: #F5F5DC !important;
    }

    .stTabs [data-baseweb="tab"] {
        color: #000000 !important;
    }
    
    .stSelectbox, .stTextInput, .stNumberInput {
        background-color: #F5F5DC;
    }
    
    /* Input field styling */
    .stTextInput input, .stNumberInput input {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 2px solid #000000 !important;
    }
    
    .stSelectbox > div > div {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 2px solid #000000 !important;
    }
    
    .stNumberInput input {
        background-color: #FFFFFF !important;
        color: #000000 !important;
    }
    
    input[type="text"], input[type="number"] {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 2px solid #000000 !important;
    }
    
    /* Select dropdown styling */
    [data-baseweb="select"] {
        background-color: #FFFFFF !important;
    }
    
    [data-baseweb="select"] button {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 2px solid #000000 !important;
    }
    
    [data-baseweb="select"] div {
        color: #000000 !important;
    }
    .stRadio {
        color: #000000 !important;
    }
    
    .stRadio > div {
        color: #000000 !important;
    }
    
    /* Checkbox styling */
    .stCheckbox {
        color: #000000 !important;
    }
    
    .stCheckbox > div {
        color: #000000 !important;
    }
    
    /* Info box styling */
    .stInfo {
        background-color: #F5F5DC;
        color: #000000;
    }
    
    /* Warning styling */
    .stWarning {
        background-color: #F5F5DC;
        color: #000000;
    }
    
    /* Success styling */
    .stSuccess {
        background-color: #F5F5DC;
        color: #000000;
    }
    
    /* Error styling */
    .stError {
        background-color: #F5F5DC;
        color: #000000;
    }
    
    /* Dropdown menu styling - white text */
    [data-baseweb="popover"] {
        background-color: #2c3e50 !important;
    }
    
    [data-baseweb="menu"] {
        background-color: #2c3e50 !important;
    }
    
    [data-baseweb="menu"] li {
        color: #FFFFFF !important;
        background-color: #2c3e50 !important;
    }
    
    [data-baseweb="menu"] li:hover {
        background-color: #1f77b4 !important;
        color: #FFFFFF !important;
    }
    
    [data-baseweb="menu"] button {
        color: #FFFFFF !important;
        background-color: #2c3e50 !important;
    }
    
    /* Dropdown option styling */
    .st-ex {
        background-color: #2c3e50 !important;
        color: #FFFFFF !important;
    }
    
    ul[data-testid="stSelectMultiOptions"] li {
        color: #FFFFFF !important;
        background-color: #2c3e50 !important;
    }
    
    ul[data-testid="stSelectMultiOptions"] li:hover {
        background-color: #1f77b4 !important;
        color: #FFFFFF !important;
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
if 'supplier_id' not in st.session_state:
    st.session_state.supplier_id = None

# Title
st.markdown('<div class="main-header">Hotel Procurement Calculator</div>', unsafe_allow_html=True)
st.markdown("### Automated FF&E and OS&E Calculation System")

# Initialize menu state
if 'menu_open' not in st.session_state:
    st.session_state.menu_open = False

# Hamburger Menu Button in Sidebar
with st.sidebar:
    # Add Seneca College Logo
    st.markdown("""
    <div style='text-align: center; padding: 1rem 0;'>
        <div style='font-size: 2rem; font-weight: bold; color: #000000;'>SENECA</div>
        <div style='font-size: 0.8rem; color: #000000;'>Procurement System</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")

    # Hamburger Menu (3 lines)
    col1, col2, col3 = st.columns([1, 4, 1])
    with col1:
        if st.button("☰", key="menu_toggle", help="Toggle Menu"):
            st.session_state.menu_open = not st.session_state.menu_open
    
    with col3:
        if st.session_state.menu_open:
            if st.button("✕", key="menu_close", help="Close Menu"):
                st.session_state.menu_open = False
    
    # Menu Items (shown only when menu is open)
    if st.session_state.menu_open:
        st.markdown("### Navigation Menu")
        
        menu_options = [
            ("New Project", "new_project"),
            ("Procurement List", "procurement_list"),
            ("Project History", "history"),
            ("Checklist", "checklist"),
            ("CAPEX Dashboard", "capex_dashboard"),
            ("Comparison", "comparison"),
            ("Supplier Comparison", "supplier_comparison"),
            ("Supplier Portal", "supplier_portal")
        ]
        
        for label, mode in menu_options:
            if st.button(label, use_container_width=True, key=f"nav_{mode}"):
                st.session_state.view_mode = mode
                st.session_state.menu_open = False
                st.rerun()
        
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
        st.caption("Version 2.1 | Updated")
        st.caption("Procurement Management System")
        st.caption("with Supplier Portal")
# ============================================================================
# CAPEX DASHBOARD - Avenue 1936 Hotel
# ============================================================================

def show_capex_dashboard():
    """CAPEX Management - Avenue 1936 Hotel Furniture Tracking"""
    if av is None:
        st.error("Avenue 1936 loader module not found. Please ensure avenue1936_loader.py is available.")
        return
    
    st.markdown('<div class="main-header">Avenue 1936 - CAPEX Management</div>', unsafe_allow_html=True)
    st.caption("B&B Hotel | 46 Rooms | Tashkent, Uzbekistan")

    # Auto-load hotel data
    if 'av_data' not in st.session_state:
        st.session_state.av_data = av.load_data()
    data = st.session_state.av_data

    # Main tabs
    tab_overview, tab_rooms, tab_common, tab_export = st.tabs([
        "Overview", "Room Furniture", "Common Areas", "Export"
    ])

    # ── OVERVIEW TAB ──
    with tab_overview:
        totals = av.get_grand_totals(data)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Rooms", totals["total_rooms"])
        with col2:
            st.metric("Room Furniture Pieces", totals["room_furniture_items"])
        with col3:
            st.metric("Common Area Pieces", totals["common_area_items"])
        with col4:
            st.metric("Grand Total Items", totals["grand_total_items"])

        if totals["grand_total_cost"] > 0:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Room Furniture Cost", f"${totals['room_furniture_cost']:,.0f}")
            with col2:
                st.metric("Common Area Cost", f"${totals['common_area_cost']:,.0f}")
            with col3:
                st.metric("Total CAPEX", f"${totals['grand_total_cost']:,.0f}")

        st.markdown("---")

        # Block comparison
        st.markdown("### Block Comparison")
        col1, col2 = st.columns(2)

        block_a = av.get_block_summary(data, "A")
        block_b = av.get_block_summary(data, "B")

        with col1:
            st.markdown("**Block A** (Floors 2-5)")
            st.write(f"Rooms: {block_a['rooms']} | Items: {block_a['items']}")
            if block_a['cost'] > 0:
                st.write(f"Cost: ${block_a['cost']:,.0f}")

        with col2:
            st.markdown("**Block B** (Floors 2-4)")
            st.write(f"Rooms: {block_b['rooms']} | Items: {block_b['items']}")
            if block_b['cost'] > 0:
                st.write(f"Cost: ${block_b['cost']:,.0f}")

        st.markdown("---")

        # Floor-by-floor breakdown
        st.markdown("### Floor Breakdown")
        floor_rows = []
        for block in ["A", "B"]:
            for floor in av.get_block_floors(block):
                fs = av.get_floor_summary(data, block, floor)
                rooms_on_floor = av.get_rooms_for_block_floor(data, block, floor)
                floor_rows.append({
                    "Block": block,
                    "Floor": floor,
                    "Rooms": fs["rooms"],
                    "Room Numbers": ", ".join(rooms_on_floor),
                    "Total Items": fs["total_items"],
                    "Total Cost": f"${fs['total_cost']:,.0f}" if fs['total_cost'] > 0 else "-",
                })
        st.dataframe(pd.DataFrame(floor_rows), use_container_width=True, hide_index=True)

        st.markdown("---")

        # Room type summary
        st.markdown("### Room Type Summary")
        type_counts = {}
        for room in data["rooms"].values():
            rt = room["room_type_name"]
            if rt not in type_counts:
                type_counts[rt] = {"count": 0, "items": 0, "cost": 0}
            type_counts[rt]["count"] += 1
            for item in room["furniture_items"]:
                type_counts[rt]["items"] += item["qty"]
                type_counts[rt]["cost"] += item["qty"] * item.get("unit_price", 0)

        type_rows = []
        for rt_name, info in sorted(type_counts.items(), key=lambda x: -x[1]["count"]):
            type_rows.append({
                "Room Type": rt_name,
                "Count": info["count"],
                "Items per Room": info["items"] // info["count"] if info["count"] > 0 else 0,
                "Total Items": info["items"],
                "Total Cost": f"${info['cost']:,.0f}" if info['cost'] > 0 else "-",
            })
        st.dataframe(pd.DataFrame(type_rows), use_container_width=True, hide_index=True)

    # ── ROOM FURNITURE TAB ──
    with tab_rooms:
        st.markdown("### Room Furniture Inventory")

        col1, col2, col3 = st.columns(3)

        with col1:
            block = st.selectbox("Block", ["A", "B"], key="capex_block")
        with col2:
            floors = av.get_block_floors(block)
            floor = st.selectbox("Floor", floors, key="capex_floor")
        with col3:
            rooms_list = av.get_rooms_for_block_floor(data, block, floor)
            if rooms_list:
                room_labels = []
                for r in rooms_list:
                    ri = data["rooms"][r]
                    label = f"{r} ({ri['room_type_name']})"
                    if ri.get("suite_group"):
                        label += f" [Suite {ri['suite_group']}]"
                    room_labels.append(label)
                selected_label = st.selectbox("Room", room_labels, key="capex_room")
                room_number = rooms_list[room_labels.index(selected_label)]
            else:
                st.warning("No rooms on this floor")
                room_number = None

        if room_number:
            room = data["rooms"][room_number]

            # Room info cards
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Room", room_number)
            with col2:
                st.metric("Type", room["room_type_name"])
            with col3:
                st.metric("Size", f"{room['size_sqm']} m\u00b2")
            with col4:
                st.metric("Items", sum(i["qty"] for i in room["furniture_items"]))

            if room.get("suite_group"):
                st.info(f"Part of Two Bedroom Suite: {room['suite_group']}")
            if room.get("note"):
                st.info(room["note"])

            st.markdown("---")

            # Build editable dataframe
            items_for_edit = []
            for item in room["furniture_items"]:
                items_for_edit.append({
                    "Item": item["item_name"],
                    "Category": item["category"],
                    "Qty": item["qty"],
                    "Unit": item["unit"],
                    "Unit Price ($)": item.get("unit_price", 0),
                    "Total ($)": item["qty"] * item.get("unit_price", 0),
                    "Supplier": item.get("supplier", ""),
                    "Status": item.get("status", "pending"),
                })

            df_items = pd.DataFrame(items_for_edit)

            edited_df = st.data_editor(
                df_items,
                use_container_width=True,
                num_rows="fixed",
                key=f"editor_{room_number}",
                column_config={
                    "Item": st.column_config.TextColumn("Item", disabled=True),
                    "Category": st.column_config.TextColumn("Category", disabled=True),
                    "Qty": st.column_config.NumberColumn("Qty", min_value=0, max_value=50),
                    "Unit": st.column_config.TextColumn("Unit", disabled=True),
                    "Unit Price ($)": st.column_config.NumberColumn("Unit Price ($)", min_value=0, format="%.0f"),
                    "Total ($)": st.column_config.NumberColumn("Total ($)", disabled=True, format="%.0f"),
                    "Supplier": st.column_config.TextColumn("Supplier"),
                    "Status": st.column_config.SelectboxColumn(
                        "Status",
                        options=["pending", "ordered", "received", "installed"],
                    ),
                },
            )

            # Room total
            room_total = sum(
                edited_df.iloc[i]["Qty"] * edited_df.iloc[i]["Unit Price ($)"]
                for i in range(len(edited_df))
            )
            st.markdown(f"**Room {room_number} Total: ${room_total:,.0f}**")

            # Save button
            if st.button(f"Save Room {room_number}", key=f"save_{room_number}", type="primary"):
                updated = []
                for i in range(len(edited_df)):
                    row = edited_df.iloc[i]
                    updated.append({
                        "qty": int(row["Qty"]),
                        "unit_price": float(row["Unit Price ($)"]),
                        "supplier": str(row["Supplier"]),
                        "status": str(row["Status"]),
                    })
                data = av.update_room_items(data, room_number, updated)
                st.session_state.av_data = data
                st.success(f"Room {room_number} saved!")

    # ── COMMON AREAS TAB ──
    with tab_common:
        st.markdown("### Common Areas Furniture")

        area_names = list(data.get("common_areas", {}).keys())
        if area_names:
            selected_area = st.selectbox("Select Area", area_names, key="capex_area")

            area_items = data["common_areas"][selected_area]

            items_for_edit = []
            for item in area_items:
                items_for_edit.append({
                    "Item": item["item_name"],
                    "Qty": item["qty"],
                    "Unit": item.get("unit", "pcs"),
                    "Unit Price ($)": item.get("unit_price", 0),
                    "Total ($)": item["qty"] * item.get("unit_price", 0),
                    "Status": item.get("status", "pending"),
                })

            df_area = pd.DataFrame(items_for_edit)

            edited_area = st.data_editor(
                df_area,
                use_container_width=True,
                num_rows="fixed",
                key=f"area_editor_{selected_area}",
                column_config={
                    "Item": st.column_config.TextColumn("Item", disabled=True),
                    "Qty": st.column_config.NumberColumn("Qty", min_value=0, max_value=200),
                    "Unit": st.column_config.TextColumn("Unit", disabled=True),
                    "Unit Price ($)": st.column_config.NumberColumn("Unit Price ($)", min_value=0, format="%.0f"),
                    "Total ($)": st.column_config.NumberColumn("Total ($)", disabled=True, format="%.0f"),
                    "Status": st.column_config.SelectboxColumn(
                        "Status",
                        options=["pending", "ordered", "received", "installed"],
                    ),
                },
            )

            area_total = sum(
                edited_area.iloc[i]["Qty"] * edited_area.iloc[i]["Unit Price ($)"]
                for i in range(len(edited_area))
            )
            st.markdown(f"**{selected_area} Total: ${area_total:,.0f}**")

            if st.button(f"Save {selected_area}", key=f"save_area_{selected_area}", type="primary"):
                updated = []
                for i in range(len(edited_area)):
                    row = edited_area.iloc[i]
                    updated.append({
                        "qty": int(row["Qty"]),
                        "unit_price": float(row["Unit Price ($)"]),
                        "status": str(row["Status"]),
                    })
                data = av.update_common_area_items(data, selected_area, updated)
                st.session_state.av_data = data
                st.success(f"{selected_area} saved!")
        else:
            st.warning("No common areas data found.")

    # ── EXPORT TAB ──
    with tab_export:
        st.markdown("### Export CAPEX Report")

        if st.button("Generate Excel Report", type="primary"):
            df_all = av.export_to_dataframe(data)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_all.to_excel(writer, sheet_name="All Rooms", index=False)

                for block_name in ["A", "B"]:
                    df_block = df_all[df_all["Block"] == block_name]
                    if not df_block.empty:
                        df_block.to_excel(writer, sheet_name=f"Block {block_name}", index=False)

                common_rows = []
                for area_name, items in data.get("common_areas", {}).items():
                    for item in items:
                        common_rows.append({
                            "Area": area_name,
                            "Item": item["item_name"],
                            "Qty": item["qty"],
                            "Unit": item.get("unit", "pcs"),
                            "Unit Price": item.get("unit_price", 0),
                            "Total": item["qty"] * item.get("unit_price", 0),
                            "Status": item.get("status", "pending"),
                        })
                if common_rows:
                    pd.DataFrame(common_rows).to_excel(writer, sheet_name="Common Areas", index=False)

                totals = av.get_grand_totals(data)
                summary_rows = [
                    {"Metric": "Total Rooms", "Value": totals["total_rooms"]},
                    {"Metric": "Room Furniture Items", "Value": totals["room_furniture_items"]},
                    {"Metric": "Room Furniture Cost", "Value": totals["room_furniture_cost"]},
                    {"Metric": "Common Area Items", "Value": totals["common_area_items"]},
                    {"Metric": "Common Area Cost", "Value": totals["common_area_cost"]},
                    {"Metric": "Grand Total Items", "Value": totals["grand_total_items"]},
                    {"Metric": "Grand Total Cost", "Value": totals["grand_total_cost"]},
                ]
                pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

            output.seek(0)
            st.download_button(
                label="Download Avenue 1936 CAPEX Report",
                data=output.getvalue(),
                file_name="Avenue1936_CAPEX_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


# ============================================================================
# EXISTING FUNCTIONS (from deployed version)
# ============================================================================

def display_results():
    """Display calculation results"""
    results = st.session_state.results

    # Summary metrics
    st.markdown("### Summary")
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
        linen_count = len(results.get('linen', []))
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

    # Detailed tables
    tabs = st.tabs([
        "Guest Rooms", "Linen", "Bathroom", "Furniture", "Amenities",
        "Restaurant", "Kitchen", "Spa", "Pool", "Gym",
        "Public Areas", "Conference", "Back of House"
    ])

    categories = [
        'guest_rooms', 'linen', 'bathroom', 'furniture', 'amenities',
        'restaurant', 'kitchen', 'spa', 'pool', 'gym',
        'public_areas', 'conference', 'back_of_house'
    ]

    for i, cat in enumerate(categories):
        with tabs[i]:
            if results.get(cat):
                df = pd.DataFrame(results[cat])
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Linen summary
                if cat == 'linen' and 'Final Qty' in df.columns:
                    st.markdown("#### Linen Summary by Item")
                    linen_summary = df.groupby('Item')['Final Qty'].sum().reset_index()
                    linen_summary.columns = ['Item', 'Total Quantity']
                    linen_summary = linen_summary.sort_values('Total Quantity', ascending=False)
                    st.dataframe(linen_summary, use_container_width=True, hide_index=True)
            else:
                st.info(f"No {cat.replace('_', ' ')} items calculated")

    # Export
    st.markdown("---")
    st.markdown("### Export Results")
    col1, col2 = st.columns(2)
    with col1:
        excel_file = generate_excel_export(results)
        st.download_button(
            label="Download Excel Report",
            data=excel_file,
            file_name=f"Procurement_List_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    with col2:
        st.button("New Calculation", on_click=reset_calculation, use_container_width=True)


def generate_excel_export(results):
    """Generate Excel file with all results"""
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_data = {
            'Metric': list(results['summary'].keys()),
            'Value': list(results['summary'].values())
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

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


def show_project_history():
    """Display project history"""
    st.markdown('<div class="main-header">Project History</div>', unsafe_allow_html=True)

    projects = db.get_all_projects()

    if not projects:
        st.info("No projects saved yet. Create your first project in the 'New Project' view.")
        return

    st.markdown(f"### Total Projects: {len(projects)}")

    for project in reversed(projects):
        with st.expander(f"{project['hotel_info']['property_name']} - {project['hotel_info']['city']} ({project['project_id']})"):
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

            col1, col2, col3 = st.columns(3)
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
                    label="Download",
                    data=excel_data,
                    file_name=f"{project['hotel_info']['property_name']}_{project['project_id']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_{project['project_id']}"
                )


def show_procurement_checklist():
    """Show procurement checklist"""
    st.markdown('<div class="main-header">Procurement Checklist</div>', unsafe_allow_html=True)

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

    project = db.get_project(project_id)
    items = db.get_project_items(project_id)
    summary = db.get_procurement_summary(project_id)

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

    col1, col2, col3 = st.columns(3)
    with col1:
        filter_dept = st.selectbox("Filter by Department", ["All"] + list(set(item['department'] for item in items)))
    with col2:
        filter_status = st.selectbox("Filter by Status", ["All", "Not Ordered", "Ordered", "Received", "Installed"])
    with col3:
        search_term = st.text_input("Search Items", "")

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

    for idx, item in enumerate(filtered_items):
        item_data = item['item_data']
        status = item['procurement_status']
        original_idx = items.index(item)

        status_badges = []
        if status['ordered']:
            status_badges.append("Ordered")
        if status['received']:
            status_badges.append("Received")
        if status['installed']:
            status_badges.append("Installed")
        status_text = " | ".join(status_badges) if status_badges else "Pending"

        with st.container():
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**{item_data.get('Item', item_data.get('item', 'N/A'))}**")
                st.caption(f"{item['department']} - {item['category']}")
                st.caption(f"Qty: {item_data.get('Total Qty', item_data.get('Total_Qty', 0))} {item_data.get('Unit', 'pcs')}")

            with col2:
                st.write(status_text)

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

            with st.expander("Details & Notes"):
                col1, col2 = st.columns(2)

                with col1:
                    supplier = st.text_input("Supplier", value=status['supplier'], key=f"supplier_{original_idx}")
                    po_number = st.text_input("PO Number", value=status['po_number'], key=f"po_{original_idx}")
                    unit_price = st.number_input("Unit Price", value=float(status['unit_price']), key=f"price_{original_idx}")

                with col2:
                    ordered_qty = st.number_input("Ordered Qty", value=status['ordered_qty'], key=f"oqty_{original_idx}")
                    received_qty = st.number_input("Received Qty", value=status['received_qty'], key=f"rqty_{original_idx}")

                notes = st.text_area("Notes", value=status['notes'], key=f"notes_{original_idx}")

                if st.button("Save Details", key=f"save_{original_idx}"):
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

            st.markdown("---")


def show_project_comparison():
    """Compare two projects"""
    st.markdown('<div class="main-header">Project Comparison</div>', unsafe_allow_html=True)

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

    comparison = db.compare_projects(project1_id, project2_id)

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

    st.markdown("### Detailed Comparison")
    items1 = db.get_project_items(project1_id)
    items2 = db.get_project_items(project2_id)

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
        with st.expander(f"{dept}"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{comparison['project1']['name']}**")
                st.write(f"Items: {len(depts1.get(dept, []))}")
            with col2:
                st.markdown(f"**{comparison['project2']['name']}**")
                st.write(f"Items: {len(depts2.get(dept, []))}")


def print_by_department(project_id):
    """Generate print-friendly view by department"""
    items = db.get_project_items(project_id)
    project = db.get_project(project_id)

    departments = {}
    for item in items:
        dept = item['department']
        if dept not in departments:
            departments[dept] = []
        departments[dept].append(item)

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
                    'Ordered': 'Y' if status['ordered'] else '',
                    'Received': 'Y' if status['received'] else '',
                    'Supplier': status['supplier'],
                    'PO#': status['po_number'],
                    'Unit Price': status['unit_price'],
                    'Total Price': status['total_price']
                }
                items_data.append(record)

            df = pd.DataFrame(items_data)
            sheet_name = dept.replace('/', '-')[:31]
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    output.seek(0)

    st.download_button(
        label="Download Department Reports",
        data=output.getvalue(),
        file_name=f"{project['hotel_info']['property_name']}_by_department.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def generate_procurement_pdf(project_info: dict, procurement_data: list) -> bytes:
    """Generate PDF report for procurement list"""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter, rightMargin=0.5*inch, leftMargin=0.5*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=6,
        alignment=1  # Center alignment
    )
    
    # Header style
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=4,
    )
    
    # Add title
    title = Paragraph(f"Procurement List Report", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.1*inch))
    
    # Add project info
    hotel_name = project_info.get('property_name', 'Unknown')
    brand = project_info.get('brand', 'N/A')
    rooms = project_info.get('total_rooms', 0)
    
    info_text = f"Hotel: {hotel_name} | Brand: {brand} | Total Rooms: {rooms} | Date: {datetime.now().strftime('%Y-%m-%d')}"
    info_para = Paragraph(info_text, styles['Normal'])
    elements.append(info_para)
    elements.append(Spacer(1, 0.15*inch))
    
    # Create table data
    if procurement_data:
        # Table headers
        table_data = [
            ['Item', 'Department', 'Category', 'Qty', 'Unit', 'Supplier', 'Unit Price', 'Total Price', 'Status']
        ]
        
        # Add rows
        for item in procurement_data:
            table_data.append([
                item.get('Item', ''),
                item.get('Department', ''),
                item.get('Category', ''),
                str(item.get('Qty', '')),
                item.get('Unit', ''),
                item.get('Supplier', ''),
                item.get('Unit Price', ''),
                item.get('Total Price', ''),
                item.get('Status', '')
            ])
        
        # Create table
        table = Table(table_data, colWidths=[1.2*inch, 0.9*inch, 0.8*inch, 0.5*inch, 0.4*inch, 0.9*inch, 0.7*inch, 0.9*inch, 0.6*inch])
        
        # Style table
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f2f6')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
    
    # Build PDF
    doc.build(elements)
    output.seek(0)
    return output.getvalue()


def show_procurement_list():
    """Show comprehensive procurement list from all projects"""
    st.markdown('<div class="main-header">Procurement List</div>', unsafe_allow_html=True)
    
    projects = db.get_all_projects()
    
    if not projects:
        st.info("No projects found. Create a new project first.")
        return
    
    # Project selector
    project_options = {
        f"{p['hotel_info']['property_name']} - {p['hotel_info']['city']} ({p['project_id']})": p['project_id']
        for p in projects
    }
    
    selected_project_name = st.selectbox("Select Project", list(project_options.keys()))
    project_id = project_options[selected_project_name]
    
    project = db.get_project(project_id)
    items = db.get_project_items(project_id)
    summary = db.get_procurement_summary(project_id)
    
    # Project Header Info
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Hotel", project['hotel_info']['property_name'])
    with col2:
        st.metric("Brand", project['hotel_info']['brand'])
    with col3:
        st.metric("Total Rooms", project['hotel_info']['total_rooms'])
    with col4:
        st.metric("Total Items", summary['total_items'])
    
    st.markdown("---")
    
    # Summary stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Ordered", f"{summary['ordered_count']} ({summary['ordered_percent']}%)")
    with col2:
        st.metric("Received", f"{summary['received_count']} ({summary['received_percent']}%)")
    with col3:
        st.metric("Installed", f"{summary['installed_count']} ({summary['installed_percent']}%)")
    with col4:
        st.metric("Pending", f"{summary['total_items'] - summary['ordered_count']} items")
    
    st.markdown("---")
    
    # Filter and search
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_dept = st.selectbox(
            "Filter by Department",
            ["All"] + sorted(list(set(item['department'] for item in items)))
        )
    with col2:
        filter_status = st.selectbox(
            "Filter by Status",
            ["All", "Not Ordered", "Ordered", "Received", "Installed"]
        )
    with col3:
        search_term = st.text_input("Search by Item Name", "")
    
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
    
    # Build procurement table
    procurement_data = []
    for item in filtered_items:
        item_data = item['item_data']
        status = item['procurement_status']
        
        procurement_data.append({
            'Item': item_data.get('Item', item_data.get('item', 'N/A')),
            'Department': item['department'],
            'Category': item['category'],
            'Qty': item_data.get('Total Qty', item_data.get('Total_Qty', 0)),
            'Unit': item_data.get('Unit', 'pcs'),
            'Supplier': status['supplier'],
            'PO Number': status['po_number'],
            'Unit Price': f"${status['unit_price']:.2f}",
            'Total Price': f"${status['total_price']:,.2f}",
            'Status': 'Ordered' if status['ordered'] else 'Pending',
            'Received': 'Yes' if status['received'] else 'No',
            'Installed': 'Yes' if status['installed'] else 'No',
        })
    
    st.markdown(f"### Showing {len(procurement_data)} items")
    
    if procurement_data:
        df = pd.DataFrame(procurement_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Export options
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Export to Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Procurement List', index=False)
                
                # Add summary sheet
                summary_data = {
                    'Metric': ['Total Items', 'Ordered', 'Received', 'Installed', 'Pending'],
                    'Count': [
                        summary['total_items'],
                        summary['ordered_count'],
                        summary['received_count'],
                        summary['installed_count'],
                        summary['total_items'] - summary['ordered_count']
                    ]
                }
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
            
            output.seek(0)
            st.download_button(
                label="Download Procurement List (Excel)",
                data=output.getvalue(),
                file_name=f"{project['hotel_info']['property_name']}_Procurement_List.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        with col2:
            # Export to PDF
            if PDF_AVAILABLE:
                pdf_data = generate_procurement_pdf(project['hotel_info'], procurement_data)
                st.download_button(
                    label="Download Procurement List (PDF)",
                    data=pdf_data,
                    file_name=f"{project['hotel_info']['property_name']}_Procurement_List.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.warning("PDF export not available. Please install reportlab: pip install reportlab")
        
        with col3:
            # Export by department
            if st.button("Export by Department", use_container_width=True):
                print_by_department(project_id)
        
        st.markdown("---")
        # Summary statistics
        st.write(f"**Total Value:** ${df['Total Price'].str.replace('$', '').str.replace(',', '').astype(float).sum():,.2f}")
    else:
        st.info("No items match the selected filters.")


# ============================================================================
# SUPPLIER HELPERS
# ============================================================================

def _normalize_text(value: str) -> str:
    """Normalize text for fuzzy matching and column detection."""
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _guess_column_map(df: pd.DataFrame) -> Dict[str, str]:
    """Guess likely column mapping for supplier catalog files."""
    mapping = {
        "item": "",
        "description": "",
        "specification": "",
        "unit": "",
        "price": "",
        "currency": "",
        "photo": "",
    }

    for col in df.columns:
        if str(col).startswith("_"):
            continue
        normalized = _normalize_text(col)
        if not mapping["item"] and any(k in normalized for k in ["item", "name", "product", "title", "sku", "code", "article"]):
            mapping["item"] = col
        elif not mapping["description"] and any(k in normalized for k in ["desc", "description", "details"]):
            mapping["description"] = col
        elif not mapping["specification"] and any(k in normalized for k in ["spec", "specification", "standard"]):
            mapping["specification"] = col
        elif not mapping["unit"] and any(k in normalized for k in ["unit", "uom", "measure"]):
            mapping["unit"] = col
        elif not mapping["price"] and any(k in normalized for k in ["price", "cost", "rate", "amount"]):
            mapping["price"] = col
        elif not mapping["currency"] and any(k in normalized for k in ["currency", "curr"]):
            mapping["currency"] = col
        elif not mapping["photo"] and any(k in normalized for k in ["photo", "image", "picture", "pic"]):
            mapping["photo"] = col

    return mapping


def _parse_price(value) -> float:
    """Parse price values from mixed text fields."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
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
    sheet_name: str = "",
) -> List[Dict]:
    """Build normalized catalog items from a mapped dataframe."""
    items = []
    item_col = column_map.get("item")
    if not item_col:
        return items

    for _, row in df.iterrows():
        item_name = str(row.get(item_col, "")).strip()
        if not item_name or item_name.lower() == "nan":
            continue

        price_value = _parse_price(row.get(column_map.get("price", ""), None)) if column_map.get("price") else None
        currency_value = row.get(column_map.get("currency", ""), default_currency) if column_map.get("currency") else default_currency

        source_row = row.get("_source_row")
        try:
            source_row = int(source_row) if source_row is not None else None
        except (TypeError, ValueError):
            source_row = None

        image_path = None
        if image_map and source_row:
            image_path = image_map.get((sheet_name, source_row))

        items.append({
            "item_name": item_name,
            "description": str(row.get(column_map.get("description", ""), "")).strip(),
            "specification": str(row.get(column_map.get("specification", ""), "")).strip(),
            "unit": str(row.get(column_map.get("unit", ""), "")).strip(),
            "price": price_value,
            "currency": str(currency_value).strip() if currency_value is not None else default_currency,
            "price_available": price_value is not None,
            "photo_ref": str(row.get(column_map.get("photo", ""), "")).strip(),
            "image_path": image_path or "",
            "source_row": source_row,
        })

    return items


def _detect_header_row(df: pd.DataFrame) -> int:
    """Detect likely header row based on common procurement labels."""
    for idx, row in df.iterrows():
        values = [str(v).strip() for v in row.tolist() if str(v).strip() and str(v).strip().lower() != "nan"]
        if len(values) < 3:
            continue
        joined = " ".join(values).lower()
        if any(key in joined for key in ["item", "description", "spec", "unit", "qty", "price", "vendor", "article", "photo"]):
            return idx
    return -1


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a dataframe by inferring headers and preserving source row."""
    if df.empty:
        return df

    uses_default_headers = all(isinstance(col, int) for col in df.columns) or any(str(col).startswith("Unnamed:") for col in df.columns)
    if not uses_default_headers:
        cleaned = df.dropna(axis=1, how="all").dropna(axis=0, how="all").copy()
        if "_source_row" not in cleaned.columns:
            cleaned["_source_row"] = cleaned.index + 1
        return cleaned

    header_idx = _detect_header_row(df)
    if header_idx == -1:
        cleaned = df.dropna(axis=1, how="all").dropna(axis=0, how="all").copy()
        cleaned.columns = [f"column_{i + 1}" for i in range(len(cleaned.columns))]
        cleaned["_source_row"] = cleaned.index + 1
        return cleaned

    header_row = df.iloc[header_idx].astype(str).tolist()
    cleaned = df.iloc[header_idx + 1:].copy()
    cleaned.columns = header_row
    cleaned = cleaned.dropna(axis=1, how="all").dropna(axis=0, how="all")
    cleaned["_source_row"] = cleaned.index + 1
    return cleaned


def _parse_pdf_tables(file_bytes: bytes) -> List[pd.DataFrame]:
    """Extract tabular content from a PDF file."""
    tables = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                if not table:
                    continue
                df = pd.DataFrame(table)
                if df.empty:
                    continue
                if df.shape[0] > 1:
                    df.columns = df.iloc[0]
                    df = df.iloc[1:]
                df = df.dropna(axis=1, how="all")
                prepared = _prepare_dataframe(df)
                if "_source_row" not in prepared.columns:
                    prepared["_source_row"] = prepared.index + 1
                tables.append(prepared)
    return tables


def _ensure_dir(path: str) -> None:
    """Ensure directory exists."""
    os.makedirs(path, exist_ok=True)


def _extract_excel_images(file_bytes: bytes, output_dir: str) -> Dict:
    """Extract embedded images from Excel and map by sheet+row."""
    mapping = {}
    _ensure_dir(output_dir)

    wb = openpyxl.load_workbook(BytesIO(file_bytes))
    for ws in wb.worksheets:
        for idx, image in enumerate(getattr(ws, "_images", [])):
            anchor = getattr(image, "anchor", None)
            row = None
            if hasattr(anchor, "_from"):
                row = anchor._from.row + 1
            if not row:
                continue

            img_bytes = None
            try:
                img_bytes = image._data()
            except Exception:
                img_bytes = None
            if not img_bytes and getattr(image, "image", None) is not None:
                try:
                    buffer = BytesIO()
                    image.image.save(buffer, format="PNG")
                    img_bytes = buffer.getvalue()
                except Exception:
                    img_bytes = None
            if not img_bytes:
                continue

            filename = f"{ws.title}_row{row}_{idx + 1}.png"
            image_path = os.path.join(output_dir, filename)
            with open(image_path, "wb") as handle:
                handle.write(img_bytes)
            mapping[(ws.title, row)] = image_path
    return mapping


def _extract_pdf_images(file_bytes: bytes, output_dir: str) -> List[str]:
    """Extract image assets from PDF."""
    _ensure_dir(output_dir)
    images = []
    try:
        import fitz
    except ImportError:
        return images

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page_index in range(len(doc)):
            page = doc[page_index]
            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                data = doc.extract_image(xref)
                img_bytes = data.get("image")
                if not img_bytes:
                    continue
                ext = data.get("ext", "png")
                filename = f"page{page_index + 1}_img{img_index + 1}.{ext}"
                image_path = os.path.join(output_dir, filename)
                with open(image_path, "wb") as handle:
                    handle.write(img_bytes)
                images.append(image_path)
    return images


def _load_catalog_from_file(uploaded_file) -> Dict:
    """Load catalog tables from uploaded file."""
    file_bytes = uploaded_file.read()
    filename = uploaded_file.name
    extension = filename.split(".")[-1].lower()

    if extension == "csv":
        df = pd.read_csv(BytesIO(file_bytes))
        df["_source_row"] = df.index + 1
        return {"dataframes": [df], "source_type": "csv", "source_name": filename}

    if extension in ["xlsx", "xls"]:
        xl = pd.ExcelFile(BytesIO(file_bytes))
        dataframes = []
        for sheet_name in xl.sheet_names:
            df_raw = pd.read_excel(xl, sheet_name=sheet_name, header=None)
            dataframes.append(_prepare_dataframe(df_raw))
        return {
            "dataframes": dataframes,
            "sheet_names": xl.sheet_names,
            "source_type": "excel",
            "source_name": filename,
            "file_bytes": file_bytes,
        }

    if extension == "pdf":
        tables = _parse_pdf_tables(file_bytes)
        return {
            "dataframes": tables,
            "source_type": "pdf",
            "source_name": filename,
            "file_bytes": file_bytes,
        }

    return {"dataframes": [], "source_type": extension, "source_name": filename}


def _load_catalog_from_url(url: str) -> Dict:
    """Load catalog tables from URL."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    filename = url.split("/")[-1].split("?")[0]
    extension = filename.split(".")[-1].lower()
    file_bytes = response.content

    if extension == "csv":
        df = pd.read_csv(BytesIO(file_bytes))
        df["_source_row"] = df.index + 1
        return {"dataframes": [df], "source_type": "csv", "source_name": filename, "source_url": url}

    if extension in ["xlsx", "xls"]:
        xl = pd.ExcelFile(BytesIO(file_bytes))
        dataframes = []
        for sheet_name in xl.sheet_names:
            df_raw = pd.read_excel(xl, sheet_name=sheet_name, header=None)
            dataframes.append(_prepare_dataframe(df_raw))
        return {
            "dataframes": dataframes,
            "sheet_names": xl.sheet_names,
            "source_type": "excel",
            "source_name": filename,
            "source_url": url,
            "file_bytes": file_bytes,
        }

    if extension == "pdf":
        tables = _parse_pdf_tables(file_bytes)
        return {
            "dataframes": tables,
            "source_type": "pdf",
            "source_name": filename,
            "source_url": url,
            "file_bytes": file_bytes,
        }

    return {"dataframes": [], "source_type": extension, "source_name": filename, "source_url": url}


def _similarity_score(a: str, b: str) -> float:
    """Name similarity score for item matching."""
    return SequenceMatcher(None, _normalize_text(a), _normalize_text(b)).ratio()


def _match_catalog_item(proc_name: str, catalog_items: List[Dict]) -> Dict:
    """Find best matching supplier catalog item for a procurement line."""
    best_match = None
    best_score = 0.0

    for item in catalog_items:
        candidate_name = item.get("item_name", "")
        score = _similarity_score(proc_name, candidate_name)
        if score > best_score:
            best_score = score
            best_match = item

    if best_match and best_score >= 0.55:
        return {**best_match, "match_score": best_score}
    return {}


def _compose_rfp_email(project: Dict, supplier: Dict, items: List[Dict]) -> Dict:
    """Create RFP email subject/body for selected supplier items."""
    hotel = project.get("hotel_info", {})
    subject = f"RFP: {hotel.get('property_name', 'Hotel')} - {project.get('project_id', '')}"

    lines = [
        f"Hello {supplier.get('contact_person') or supplier.get('name')},",
        "",
        "Please provide a quotation for the following items:",
        "",
    ]
    for item in items:
        line = f"- {item['item_name']} | Qty: {item['quantity']}"
        if item.get("specification"):
            line += f" | Spec: {item['specification']}"
        if item.get("price_available"):
            line += f" | Target Price: {item.get('price')} {item.get('currency', '')}".rstrip()
        lines.append(line)
    lines.extend([
        "",
        "Please confirm lead times, delivery terms, and any alternatives.",
        "",
        "Thank you,",
        hotel.get("project_name", "Procurement Team"),
    ])

    return {"subject": subject, "body": "\n".join(lines)}


def _send_email_smtp(smtp_config: Dict, to_email: str, subject: str, body: str) -> str:
    """Send an email via SMTP."""
    import smtplib
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_config.get("from_email")
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP(smtp_config.get("host"), smtp_config.get("port", 587)) as server:
        if smtp_config.get("use_tls", True):
            server.starttls()
        server.login(smtp_config.get("username"), smtp_config.get("password"))
        server.send_message(msg)

    return "sent"


# ============================================================================
# SUPPLIER PORTAL
# ============================================================================

def show_supplier_portal():
    """Supplier portal for profile management and catalog uploads."""
    st.markdown('<div class="main-header">Supplier Portal</div>', unsafe_allow_html=True)
    st.markdown("### Manage Suppliers and Product Catalogs")

    suppliers = db.get_all_suppliers()
    supplier_lookup = {f"{s.get('name', 'Unnamed')} ({s.get('email', 'no-email')})": s["supplier_id"] for s in suppliers}
    supplier_options = ["Create new supplier"] + list(supplier_lookup.keys())

    tab_profile, tab_upload, tab_library, tab_analytics = st.tabs([
        "Supplier Profile",
        "Catalog Upload",
        "Catalog Library",
        "Procurement Analytics",
    ])

    with tab_profile:
        selected_supplier = st.selectbox("Supplier Profile", supplier_options, key="supplier_profile_select")
        selected_supplier_id = supplier_lookup.get(selected_supplier) if selected_supplier != "Create new supplier" else None
        selected_data = db.get_supplier(selected_supplier_id) if selected_supplier_id else {}

        with st.form("supplier_profile_form"):
            st.markdown("### Supplier Details")
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Supplier Name", value=selected_data.get("name", ""))
                email = st.text_input("Email", value=selected_data.get("email", ""))
                phone = st.text_input("Phone", value=selected_data.get("phone", ""))
            with col2:
                website = st.text_input("Website", value=selected_data.get("website", ""))
                contact_person = st.text_input("Contact Person", value=selected_data.get("contact_person", ""))
                categories = st.text_input("Categories (comma-separated)", value=", ".join(selected_data.get("categories", [])))

            address = st.text_area("Address", value=selected_data.get("address", ""))
            notes = st.text_area("Notes", value=selected_data.get("notes", ""))

            submitted = st.form_submit_button("Save Supplier")
            if submitted:
                if not name or not email:
                    st.error("Supplier Name and Email are required.")
                else:
                    supplier_id = db.save_supplier({
                        "supplier_id": selected_data.get("supplier_id"),
                        "name": name,
                        "email": email,
                        "phone": phone,
                        "website": website,
                        "contact_person": contact_person,
                        "categories": [c.strip() for c in categories.split(",") if c.strip()],
                        "address": address,
                        "notes": notes,
                        "created_at": selected_data.get("created_at"),
                    })
                    st.session_state.supplier_id = supplier_id
                    st.success("Supplier profile saved.")

    active_supplier_id = st.session_state.supplier_id
    if not active_supplier_id and supplier_lookup:
        # Use selected profile when no explicit session supplier is set.
        selected_label = st.session_state.get("supplier_profile_select", "Create new supplier")
        active_supplier_id = supplier_lookup.get(selected_label)

    with tab_upload:
        st.markdown("### Catalog Upload")
        if not active_supplier_id:
            st.info("Save or select a supplier profile first.")
        else:
            catalog_name = st.text_input("Catalog Name", value="Main Catalog", key="catalog_name")
            default_currency = st.selectbox("Default Currency", ["USD", "EUR", "GBP", "AED", "SAR", "RUB"], index=0, key="catalog_currency")
            extract_images = st.checkbox("Extract embedded images (Excel/PDF)", help="Slower for large catalogs", key="catalog_extract_images")

            uploaded_file = st.file_uploader("Upload Catalog (CSV, XLSX, PDF)", type=["csv", "xlsx", "xls", "pdf"], key="catalog_upload")
            catalog_url = st.text_input("Or paste catalog URL (CSV/XLSX/PDF)", key="catalog_url")

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

            if catalog_data and catalog_data.get("dataframes"):
                st.markdown("#### Preview & Column Mapping")
                sheet_names = catalog_data.get("sheet_names", [])
                is_multi_sheet = catalog_data.get("source_type") == "excel" and len(sheet_names) > 1
                bulk_import_all = st.checkbox("Bulk import all sheets (auto-detect columns)", key="catalog_bulk_import") if is_multi_sheet else False

                if bulk_import_all:
                    summary_rows = []
                    image_map = {}
                    pdf_images = []
                    image_dir = ""

                    if extract_images and catalog_data.get("file_bytes"):
                        image_dir = os.path.join(db.db_path, "catalog_images", active_supplier_id, datetime.now().strftime("%Y%m%d_%H%M%S"))
                        if catalog_data.get("source_type") == "excel":
                            image_map = _extract_excel_images(catalog_data["file_bytes"], image_dir)
                        elif catalog_data.get("source_type") == "pdf":
                            pdf_images = _extract_pdf_images(catalog_data["file_bytes"], image_dir)

                    for index, sheet_label in enumerate(sheet_names):
                        sheet_df = catalog_data["dataframes"][index]
                        guessed = _guess_column_map(sheet_df)
                        summary_rows.append({
                            "Sheet": sheet_label,
                            "Rows": len(sheet_df),
                            "Item Column": guessed["item"] or "Missing",
                            "Price Column": guessed["price"] or "Missing",
                            "Photo Column": guessed["photo"] or "Missing",
                        })
                    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

                    if st.button("Bulk Save Catalogs", key="catalog_bulk_save"):
                        saved = 0
                        skipped = 0
                        total_items = 0

                        for index, sheet_label in enumerate(sheet_names):
                            sheet_df = catalog_data["dataframes"][index]
                            guessed = _guess_column_map(sheet_df)
                            if not guessed["item"]:
                                skipped += 1
                                continue
                            catalog_items = _build_catalog_items(sheet_df, guessed, default_currency, image_map, sheet_label)
                            if not catalog_items:
                                skipped += 1
                                continue
                            db.save_supplier_catalog(
                                active_supplier_id,
                                {
                                    "name": f"{catalog_name} - {sheet_label}",
                                    "source_type": catalog_data.get("source_type", ""),
                                    "source_name": catalog_data.get("source_name", ""),
                                    "source_url": catalog_data.get("source_url", ""),
                                    "image_dir": image_dir,
                                    "image_count": len(image_map) or len(pdf_images),
                                },
                                catalog_items,
                            )
                            saved += 1
                            total_items += len(catalog_items)

                        st.success(f"Saved {saved} catalogs ({total_items} items). Skipped {skipped} sheets.")
                else:
                    if sheet_names and len(sheet_names) > 1:
                        sheet_label = st.selectbox("Select Sheet", sheet_names, key="catalog_sheet_select")
                        sheet_index = sheet_names.index(sheet_label)
                        df = catalog_data["dataframes"][sheet_index]
                    else:
                        sheet_label = ""
                        df = catalog_data["dataframes"][0]

                    st.dataframe(df.drop(columns=["_source_row"], errors="ignore").head(20), use_container_width=True)
                    column_options = ["(none)"] + list(df.columns)
                    guessed = _guess_column_map(df)

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        item_col = st.selectbox(
                            "Item Name Column",
                            column_options,
                            index=column_options.index(guessed["item"]) if guessed["item"] in column_options else 0,
                            key="map_item_col",
                        )
                        desc_col = st.selectbox(
                            "Description Column",
                            column_options,
                            index=column_options.index(guessed["description"]) if guessed["description"] in column_options else 0,
                            key="map_desc_col",
                        )
                    with col2:
                        spec_col = st.selectbox(
                            "Specification Column",
                            column_options,
                            index=column_options.index(guessed["specification"]) if guessed["specification"] in column_options else 0,
                            key="map_spec_col",
                        )
                        unit_col = st.selectbox(
                            "Unit Column",
                            column_options,
                            index=column_options.index(guessed["unit"]) if guessed["unit"] in column_options else 0,
                            key="map_unit_col",
                        )
                    with col3:
                        price_col = st.selectbox(
                            "Price Column",
                            column_options,
                            index=column_options.index(guessed["price"]) if guessed["price"] in column_options else 0,
                            key="map_price_col",
                        )
                        currency_col = st.selectbox(
                            "Currency Column",
                            column_options,
                            index=column_options.index(guessed["currency"]) if guessed["currency"] in column_options else 0,
                            key="map_currency_col",
                        )
                    photo_col = st.selectbox(
                        "Photo Column",
                        column_options,
                        index=column_options.index(guessed["photo"]) if guessed["photo"] in column_options else 0,
                        key="map_photo_col",
                    )

                    if st.button("Save Catalog", key="catalog_save"):
                        image_map = {}
                        pdf_images = []
                        image_dir = ""
                        if extract_images and catalog_data.get("file_bytes"):
                            image_dir = os.path.join(db.db_path, "catalog_images", active_supplier_id, datetime.now().strftime("%Y%m%d_%H%M%S"))
                            if catalog_data.get("source_type") == "excel":
                                image_map = _extract_excel_images(catalog_data["file_bytes"], image_dir)
                            elif catalog_data.get("source_type") == "pdf":
                                pdf_images = _extract_pdf_images(catalog_data["file_bytes"], image_dir)

                        column_map = {
                            "item": "" if item_col == "(none)" else item_col,
                            "description": "" if desc_col == "(none)" else desc_col,
                            "specification": "" if spec_col == "(none)" else spec_col,
                            "unit": "" if unit_col == "(none)" else unit_col,
                            "price": "" if price_col == "(none)" else price_col,
                            "currency": "" if currency_col == "(none)" else currency_col,
                            "photo": "" if photo_col == "(none)" else photo_col,
                        }
                        catalog_items = _build_catalog_items(df, column_map, default_currency, image_map, sheet_label)
                        if not catalog_items:
                            st.error("No catalog items were created. Please confirm the Item Name column.")
                        else:
                            catalog_id = db.save_supplier_catalog(
                                active_supplier_id,
                                {
                                    "name": catalog_name,
                                    "source_type": catalog_data.get("source_type", ""),
                                    "source_name": catalog_data.get("source_name", ""),
                                    "source_url": catalog_data.get("source_url", ""),
                                    "image_dir": image_dir,
                                    "image_count": len(image_map) or len(pdf_images),
                                },
                                catalog_items,
                            )
                            st.success(f"Catalog saved ({len(catalog_items)} items). Catalog ID: {catalog_id}")

    with tab_library:
        st.markdown("### Existing Catalogs")
        supplier_for_library = st.selectbox("Supplier", list(supplier_lookup.keys()), key="catalog_library_supplier") if supplier_lookup else None
        if not supplier_for_library:
            st.info("No suppliers available.")
        else:
            supplier_id = supplier_lookup[supplier_for_library]
            catalogs = db.get_supplier_catalogs(supplier_id)
            if not catalogs:
                st.info("No catalogs uploaded yet.")
            else:
                for catalog in catalogs:
                    with st.expander(f"{catalog.get('name', 'Catalog')} ({len(catalog.get('items', []))} items)"):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Items", len(catalog.get("items", [])))
                        with col2:
                            st.metric("Images", catalog.get("image_count", 0))
                        with col3:
                            st.metric("Uploaded", str(catalog.get("uploaded_at", ""))[:10])
                        if catalog.get("source_url"):
                            st.markdown(f"**Source:** [{catalog['source_url']}]({catalog['source_url']})")
                catalog_names = {f"{c.get('name', 'Catalog')} ({len(c.get('items', []))} items)": c for c in catalogs}
                selected_catalog = st.selectbox("Preview Catalog Items", list(catalog_names.keys()), key="catalog_preview_select")
                selected_items = catalog_names[selected_catalog].get("items", [])
                preview_df = pd.DataFrame(selected_items).head(25)
                if not preview_df.empty:
                    st.dataframe(preview_df, use_container_width=True, hide_index=True)

    with tab_analytics:
        st.markdown('<div class="section-header">Procurement Analytics</div>', unsafe_allow_html=True)
        analytics = db.get_p2p_analytics()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total POs", analytics["total_pos"])
        with col2:
            st.metric("Total Invoices", analytics["total_invoices"])
        with col3:
            st.metric("Total Payments", analytics["total_payments"])
        with col4:
            st.metric("Outstanding Payables", f"${analytics['outstanding_payables']:,.0f}")

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### PO Status Breakdown")
            po_status = analytics["pos_by_status"]
            if po_status:
                st.bar_chart(po_status)
        with col2:
            st.markdown("### Invoice Status Breakdown")
            invoice_status = analytics["invoices_by_status"]
            if invoice_status:
                st.bar_chart(invoice_status)

        st.markdown("---")
        st.markdown("### Matching Statistics")
        col1, col2, col3, col4 = st.columns(4)
        matching = analytics["matching_stats"]
        with col1:
            st.metric("3-Way Matched", matching["3-Way"])
        with col2:
            st.metric("2-Way Matched", matching["2-Way"])
        with col3:
            st.metric("Unmatched", matching["Unmatched"])
        with col4:
            st.metric("Mismatched", matching["Mismatched"])


def show_supplier_comparison():
    """Compare project procurement list against supplier catalogs and prepare RFP emails."""
    st.markdown('<div class="main-header">Supplier Comparison & RFP</div>', unsafe_allow_html=True)

    projects = db.get_all_projects()
    if not projects:
        st.info("No saved projects found. Create and save a project first.")
        return

    project_options = {
        f"{p['hotel_info']['property_name']} - {p['hotel_info']['city']} ({p['project_id']})": p["project_id"]
        for p in projects
    }
    selected_project_name = st.selectbox("Select Project", list(project_options.keys()), key="supplier_cmp_project")
    project_id = project_options[selected_project_name]
    project = db.get_project(project_id)

    suppliers = db.get_all_suppliers()
    if not suppliers:
        st.info("No suppliers available. Add suppliers and upload catalogs first.")
        return

    supplier_choices = {f"{s.get('name')} ({s.get('email')})": s["supplier_id"] for s in suppliers}
    selected_suppliers = st.multiselect("Select Suppliers", list(supplier_choices.keys()), key="supplier_cmp_suppliers")
    if not selected_suppliers:
        st.info("Select at least one supplier to compare.")
        return

    selected_supplier_ids = [supplier_choices[name] for name in selected_suppliers]
    catalog_items = db.get_all_catalog_items(selected_supplier_ids)
    if not catalog_items:
        st.warning("No catalog items found for selected suppliers.")
        return

    catalog_by_supplier = {}
    for item in catalog_items:
        catalog_by_supplier.setdefault(item["supplier_id"], []).append(item)

    project_items = db.get_project_items(project_id)
    if not project_items:
        st.info("Selected project has no procurement items.")
        return

    comparison_rows = []
    match_map = {}

    for idx, proj_item in enumerate(project_items):
        item_data = proj_item.get("item_data", {})
        proc_name = item_data.get("Item") or item_data.get("item") or "Item"
        quantity = item_data.get("Total Qty", item_data.get("Total_Qty", 0))
        specification = item_data.get("Specification", item_data.get("specification", ""))

        row = {"Item": proc_name, "Qty": quantity, "Specification": specification, "Selected Supplier": ""}
        match_map[idx] = {}

        for supplier_name, supplier_id in supplier_choices.items():
            if supplier_id not in selected_supplier_ids:
                continue
            match = _match_catalog_item(proc_name, catalog_by_supplier.get(supplier_id, []))
            match_map[idx][supplier_id] = match
            if match:
                price_label = match["price"] if match.get("price_available") else "POR"
                row[f"{supplier_name} Price"] = price_label
                row[f"{supplier_name} Match"] = match.get("item_name", "")
            else:
                row[f"{supplier_name} Price"] = "No match"
                row[f"{supplier_name} Match"] = ""

        comparison_rows.append(row)

    df = pd.DataFrame(comparison_rows)
    supplier_options = [""] + selected_suppliers

    st.markdown("### Comparison Table")
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Selected Supplier": st.column_config.SelectboxColumn(
                "Selected Supplier",
                options=supplier_options,
            ),
        },
    )

    selected_items_by_supplier = {}
    for row_index, row in edited_df.iterrows():
        chosen_supplier_label = row.get("Selected Supplier")
        if not chosen_supplier_label:
            continue
        supplier_id = supplier_choices.get(chosen_supplier_label)
        match = match_map.get(row_index, {}).get(supplier_id, {})
        if not match:
            continue

        qty_value = row.get("Qty", 0)
        try:
            qty_value = float(qty_value)
        except (TypeError, ValueError):
            qty_value = 0

        selected_items_by_supplier.setdefault(supplier_id, []).append({
            "item_name": row.get("Item"),
            "quantity": qty_value,
            "specification": row.get("Specification", ""),
            "price": match.get("price"),
            "currency": match.get("currency"),
            "price_available": match.get("price_available", False),
        })

    if not selected_items_by_supplier:
        st.info("Select suppliers for items to generate RFP summary.")
        return

    st.markdown("### RFP Summary")
    for supplier_id, items in selected_items_by_supplier.items():
        supplier = db.get_supplier(supplier_id)
        total_items = len(items)
        total_value = sum((item["price"] or 0) * item["quantity"] for item in items if item.get("price_available"))
        st.write(f"- {supplier.get('name')}: {total_items} items | Estimated: {total_value:,.2f}")

    try:
        smtp_config = dict(st.secrets.get("smtp", {}))
    except Exception:
        smtp_config = {}

    if st.button("Send RFP Emails", key="rfp_send_btn"):
        for supplier_id, items in selected_items_by_supplier.items():
            supplier = db.get_supplier(supplier_id)
            email_content = _compose_rfp_email(project, supplier, items)
            to_email = supplier.get("email")
            if not to_email:
                st.warning(f"Skipping supplier without email: {supplier.get('name', supplier_id)}")
                continue

            if smtp_config and smtp_config.get("host"):
                try:
                    _send_email_smtp(smtp_config, to_email, email_content["subject"], email_content["body"])
                    st.success(f"Email sent to {supplier.get('name')}")
                except Exception as exc:
                    st.error(f"Failed to send to {supplier.get('name')}: {exc}")
            else:
                mailto = f"mailto:{to_email}?subject={quote(email_content['subject'])}&body={quote(email_content['body'])}"
                st.markdown(f"[Open email draft for {supplier.get('name')}]({mailto})")


# ============================================================================
# MAIN ROUTING
# ============================================================================

# Show the appropriate view based on selected mode
if st.session_state.view_mode == 'procurement_list':
    show_procurement_list()
elif st.session_state.view_mode == 'capex_dashboard':
    show_capex_dashboard()
elif st.session_state.view_mode == 'history':
    show_project_history()
elif st.session_state.view_mode == 'checklist':
    show_procurement_checklist()
elif st.session_state.view_mode == 'comparison':
    show_project_comparison()
elif st.session_state.view_mode == 'supplier_comparison':
    show_supplier_comparison()
elif st.session_state.view_mode == 'supplier_portal':
    show_supplier_portal()
else:
    # Default: New Project form
    tab1, tab2, tab3, tab4 = st.tabs(["Basic Info", "Room Configuration", "Facilities", "Results"])

    with tab1:
        st.markdown('<div class="section-header">Hotel Information</div>', unsafe_allow_html=True)

        # Simplified, streamlined Basic Info section
        col1, col2 = st.columns(2)

        with col1:
            hotel_brand = st.selectbox(
                "Hotel Brand *",
                BrandStandards.get_available_brands(),
                key="hotel_brand"
            )
            property_name = st.text_input(
                "Property Name *",
                placeholder="e.g., Hilton Garden Inn Downtown",
                help="Official hotel name",
                key="property_name"
            )
            city = st.text_input(
                "City *",
                placeholder="e.g., New York",
                key="city"
            )
            total_rooms = st.number_input(
                "Total Number of Rooms *",
                min_value=1,
                max_value=1000,
                value=50,
                key="total_rooms"
            )

        with col2:
            num_floors = st.number_input(
                "Number of Floors",
                min_value=1,
                max_value=100,
                value=5,
                key="num_floors"
            )
            num_restaurants = st.number_input(
                "Number of Restaurants/Outlets",
                min_value=0,
                max_value=20,
                value=1,
                key="num_restaurants"
            )
            num_kitchens = st.number_input(
                "Number of Kitchens",
                min_value=0,
                max_value=10,
                value=1,
                key="num_kitchens"
            )
            num_room_types = st.number_input(
                "How many room types?",
                min_value=1,
                max_value=10,
                value=3,
                key="num_room_types"
            )

        # Store hotel name for later use
        hotel_name = f"{hotel_brand} - {property_name}, {city}"
        country = ""
        project_name = ""
        developer = ""

    with tab2:
        st.markdown('<div class="section-header">Room Type Configuration</div>', unsafe_allow_html=True)
        st.info("Define your room categories. The system will calculate all FF&E and OS&E items based on these.")

        room_types = []
        total_configured_rooms = 0

        for i in range(num_room_types):
            st.markdown(f"#### Room Type {i+1}")
            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                room_name = st.text_input(
                    "Room Type Name",
                    value=f"Standard" if i == 0 else f"Type {i+1}",
                    key=f"room_name_{i}"
                )
            with col2:
                room_count = st.number_input(
                    "Number of Rooms",
                    min_value=0,
                    max_value=1000,
                    value=25 if i == 0 else 0,
                    key=f"room_count_{i}"
                )
            with col3:
                bed_type = st.selectbox(
                    "Bed Type",
                    ["King", "Twin", "Queen"],
                    key=f"bed_type_{i}"
                )
            with col4:
                bed_size = st.selectbox(
                    "Bed Size",
                    ["200x200 (King)", "100x200 (Twin - Convertible)"] if bed_type in ["King", "Twin"] else ["200x200", "180x200"],
                    key=f"bed_size_{i}",
                    help="Twin rooms: 100x200 with Zip & Link. King: 200x200 only"
                )
            with col5:
                num_beds = st.number_input(
                    "Beds per Room",
                    min_value=1,
                    max_value=5,
                    value=2 if bed_type == "Twin" else 1,
                    key=f"num_beds_{i}"
                )

            if room_count > 0:
                room_types.append({
                    "name": room_name,
                    "count": room_count,
                    "bed_type": bed_type,
                    "bed_size": bed_size,
                    "num_beds": num_beds
                })
                total_configured_rooms += room_count

        if total_configured_rooms != total_rooms:
            st.warning(f"Room count mismatch: Configured {total_configured_rooms} rooms, but total is {total_rooms}")
        else:
            st.success(f"All {total_rooms} rooms configured correctly")

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

        col1, col2 = st.columns([3, 1])
        with col1:
            calculate_btn = st.button("Calculate & Save Project", type="primary", use_container_width=True)
        with col2:
            preview_btn = st.button("Preview Only", use_container_width=True)

        if calculate_btn or preview_btn:
            if not property_name or not city:
                st.error("Please fill in all required fields in Basic Info tab (marked with *)")
            elif total_configured_rooms != total_rooms:
                st.error("Please configure all rooms in Room Configuration tab")
            else:
                with st.spinner("Calculating procurement requirements..."):
                    st.session_state.calculation_done = True

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

                    if calculate_btn:
                        project_id = db.save_project(config, results)
                        st.session_state.current_project_id = project_id
                        st.success(f"Project saved successfully! ID: {project_id}")
                    else:
                        st.info("Preview mode - Project not saved")

                    st.rerun()

        if st.session_state.calculation_done:
            output_mode = st.radio(
                "Output Mode",
                ["Procurement List", "Supplier Comparison"],
                horizontal=True,
                key="results_output_mode",
            )
            if output_mode == "Supplier Comparison":
                show_supplier_comparison()
            else:
                display_results()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #000000;'>
    <p>Hotel Procurement Calculator v2.1 | Built with Streamlit</p>
    <p>Avenue 1936 CAPEX Management Module</p>
</div>
""", unsafe_allow_html=True)
