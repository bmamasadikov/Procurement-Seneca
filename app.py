import streamlit as st
import pandas as pd
import openpyxl
from io import BytesIO
from datetime import datetime
import json
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
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2c3e50;
        margin-top: 2rem;
        border-bottom: 2px solid #1f77b4;
        padding-bottom: 0.5rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
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

# ============================================================================
# FUNCTION DEFINITIONS
# ============================================================================

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

    # View mode selector
    st.markdown("### 📁 Menu")
    view_mode = st.radio(
        "Select View",
        ["New Project", "Project History", "Checklist", "Comparison"],
        key="view_mode_radio"
    )

    if view_mode == "New Project":
        st.session_state.view_mode = 'new_project'
    elif view_mode == "Project History":
        st.session_state.view_mode = 'history'
    elif view_mode == "Checklist":
        st.session_state.view_mode = 'checklist'
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
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            room_name = st.text_input(f"Room Type Name", value=f"Standard" if i==0 else f"Type {i+1}", key=f"room_name_{i}")
        with col2:
            room_count = st.number_input(f"Number of Rooms", min_value=0, max_value=1000, value=25 if i==0 else 0, key=f"room_count_{i}")
        with col3:
            bed_type = st.selectbox(f"Bed Configuration", ["King", "Twin", "Queen", "Double Twin"], key=f"bed_type_{i}")
        with col4:
            num_beds = st.number_input(f"Beds per Room", min_value=1, max_value=5, value=2 if bed_type=="Twin" else 1, key=f"num_beds_{i}")

        if room_count > 0:
            room_types.append({
                "name": room_name,
                "count": room_count,
                "bed_type": bed_type,
                "num_beds": num_beds
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
        display_results()

# Additional Views based on mode
if st.session_state.view_mode == 'history':
    show_project_history()
elif st.session_state.view_mode == 'checklist':
    show_procurement_checklist()
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
