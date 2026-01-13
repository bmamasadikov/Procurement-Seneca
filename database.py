"""
Database module for storing project history and procurement tracking
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Any
import pandas as pd


class ProcurementDatabase:
    """Simple JSON-based database for procurement projects"""

    def __init__(self, db_path='procurement_data'):
        self.db_path = db_path
        self.projects_file = os.path.join(db_path, 'projects.json')
        self.items_file = os.path.join(db_path, 'procurement_items.json')
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """Create database directory and files if they don't exist"""
        if not os.path.exists(self.db_path):
            os.makedirs(self.db_path)

        if not os.path.exists(self.projects_file):
            self._write_json(self.projects_file, {})

        if not os.path.exists(self.items_file):
            self._write_json(self.items_file, {})

    def _read_json(self, file_path):
        """Read JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return {}

    def _write_json(self, file_path, data):
        """Write JSON file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error writing {file_path}: {e}")

    def save_project(self, project_data: Dict, results: Dict) -> str:
        """Save a new project"""
        projects = self._read_json(self.projects_file)
        items = self._read_json(self.items_file)

        # Generate project ID
        project_id = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Prepare project metadata
        project_info = {
            'project_id': project_id,
            'created_at': datetime.now().isoformat(),
            'hotel_info': {
                'brand': project_data.get('hotel_brand', ''),
                'property_name': project_data.get('property_name', ''),
                'city': project_data.get('city', ''),
                'country': project_data.get('country', ''),
                'project_name': project_data.get('project_name', ''),
                'total_rooms': project_data.get('total_rooms', 0),
                'num_floors': project_data.get('num_floors', 0),
            },
            'configuration': {
                'room_types': project_data.get('room_types', []),
                'facilities': {
                    'restaurants': project_data.get('num_restaurants', 0),
                    'kitchens': project_data.get('num_kitchens', 0),
                    'spa': project_data.get('has_spa', False),
                    'spa_rooms': project_data.get('spa_rooms', 0),
                    'pool': project_data.get('has_pool', False),
                    'gym': project_data.get('has_gym', False),
                    'conference': project_data.get('num_conference', 0),
                },
                'linen_standards': {
                    'par_level': project_data.get('par_level', 4),
                    'reserve_stock': project_data.get('reserve_stock', 10),
                }
            },
            'status': 'active',
            'last_modified': datetime.now().isoformat()
        }

        # Save project
        projects[project_id] = project_info
        self._write_json(self.projects_file, projects)

        # Save procurement items
        project_items = []

        # Process all categories
        for category in ['guest_rooms', 'linen', 'bathroom', 'furniture', 'amenities',
                        'restaurant', 'kitchen', 'spa', 'pool', 'gym', 'public_areas',
                        'conference', 'back_of_house']:
            if results.get(category):
                for item in results[category]:
                    item_record = {
                        'project_id': project_id,
                        'category': category,
                        'department': self._get_department(category),
                        'item_data': item,
                        'procurement_status': {
                            'ordered': False,
                            'ordered_date': None,
                            'ordered_qty': 0,
                            'received': False,
                            'received_date': None,
                            'received_qty': 0,
                            'installed': False,
                            'installed_date': None,
                            'supplier': '',
                            'po_number': '',
                            'unit_price': 0,
                            'total_price': 0,
                            'notes': ''
                        }
                    }
                    project_items.append(item_record)

        items[project_id] = project_items
        self._write_json(self.items_file, items)

        return project_id

    def _get_department(self, category):
        """Map category to department"""
        mapping = {
            'guest_rooms': 'Rooms Division',
            'linen': 'Housekeeping',
            'bathroom': 'Housekeeping',
            'furniture': 'Rooms Division',
            'amenities': 'Rooms Division',
            'restaurant': 'Food & Beverage',
            'kitchen': 'Food & Beverage',
            'spa': 'Spa & Wellness',
            'pool': 'Recreation',
            'gym': 'Recreation',
            'public_areas': 'Front Office',
            'conference': 'Meeting & Events',
            'back_of_house': 'Back of House'
        }
        return mapping.get(category, 'General')

    def get_all_projects(self) -> List[Dict]:
        """Get all projects"""
        projects = self._read_json(self.projects_file)
        return [
            {
                'project_id': pid,
                **pdata
            }
            for pid, pdata in projects.items()
        ]

    def get_project(self, project_id: str) -> Dict:
        """Get a specific project"""
        projects = self._read_json(self.projects_file)
        return projects.get(project_id, {})

    def get_project_items(self, project_id: str) -> List[Dict]:
        """Get all items for a project"""
        items = self._read_json(self.items_file)
        return items.get(project_id, [])

    def update_item_status(self, project_id: str, item_index: int, status_update: Dict):
        """Update procurement status of an item"""
        items = self._read_json(self.items_file)

        if project_id in items and item_index < len(items[project_id]):
            items[project_id][item_index]['procurement_status'].update(status_update)
            items[project_id][item_index]['procurement_status']['last_updated'] = datetime.now().isoformat()
            self._write_json(self.items_file, items)
            return True
        return False

    def get_items_by_department(self, project_id: str, department: str) -> List[Dict]:
        """Get items filtered by department"""
        all_items = self.get_project_items(project_id)
        return [item for item in all_items if item['department'] == department]

    def get_procurement_summary(self, project_id: str) -> Dict:
        """Get procurement status summary"""
        items = self.get_project_items(project_id)

        total_items = len(items)
        ordered = sum(1 for item in items if item['procurement_status']['ordered'])
        received = sum(1 for item in items if item['procurement_status']['received'])
        installed = sum(1 for item in items if item['procurement_status']['installed'])

        total_budget = sum(item['procurement_status']['total_price'] for item in items)
        spent = sum(
            item['procurement_status']['total_price']
            for item in items
            if item['procurement_status']['ordered']
        )

        return {
            'total_items': total_items,
            'ordered_count': ordered,
            'received_count': received,
            'installed_count': installed,
            'ordered_percent': round(ordered / total_items * 100, 1) if total_items > 0 else 0,
            'received_percent': round(received / total_items * 100, 1) if total_items > 0 else 0,
            'installed_percent': round(installed / total_items * 100, 1) if total_items > 0 else 0,
            'total_budget': total_budget,
            'spent': spent,
            'remaining': total_budget - spent
        }

    def export_project_to_excel(self, project_id: str, output_path: str):
        """Export project with status to Excel"""
        from io import BytesIO

        project = self.get_project(project_id)
        items = self.get_project_items(project_id)

        output = BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Project info
            project_info_df = pd.DataFrame([{
                'Project ID': project_id,
                'Property Name': project['hotel_info'].get('property_name', ''),
                'Brand': project['hotel_info'].get('brand', ''),
                'City': project['hotel_info'].get('city', ''),
                'Total Rooms': project['hotel_info'].get('total_rooms', 0),
                'Created': project.get('created_at', ''),
                'Last Modified': project.get('last_modified', '')
            }])
            project_info_df.to_excel(writer, sheet_name='Project Info', index=False)

            # Procurement items
            items_data = []
            for idx, item in enumerate(items):
                item_data = item['item_data']
                status = item['procurement_status']

                record = {
                    'Index': idx,
                    'Department': item['department'],
                    'Category': item['category'],
                    'Item': item_data.get('Item', item_data.get('item', 'N/A')),
                    'Specification': item_data.get('Specification', ''),
                    'Total Qty': item_data.get('Total Qty', item_data.get('Total_Qty', 0)),
                    'Unit': item_data.get('Unit', 'pcs'),
                    'Ordered': '✓' if status['ordered'] else '',
                    'Ordered Date': status['ordered_date'] or '',
                    'Received': '✓' if status['received'] else '',
                    'Received Date': status['received_date'] or '',
                    'Installed': '✓' if status['installed'] else '',
                    'Supplier': status['supplier'],
                    'PO Number': status['po_number'],
                    'Unit Price': status['unit_price'],
                    'Total Price': status['total_price'],
                    'Notes': status['notes']
                }
                items_data.append(record)

            items_df = pd.DataFrame(items_data)
            items_df.to_excel(writer, sheet_name='Procurement Items', index=False)

            # Summary by department
            summary_data = []
            for dept in items_df['Department'].unique():
                dept_items = items_df[items_df['Department'] == dept]
                summary_data.append({
                    'Department': dept,
                    'Total Items': len(dept_items),
                    'Ordered': dept_items['Ordered'].str.contains('✓').sum(),
                    'Received': dept_items['Received'].str.contains('✓').sum(),
                    'Installed': dept_items['Installed'].str.contains('✓').sum(),
                    'Total Budget': dept_items['Total Price'].sum()
                })

            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary by Department', index=False)

        output.seek(0)
        return output.getvalue()

    def compare_projects(self, project_id_1: str, project_id_2: str) -> Dict:
        """Compare two projects"""
        project1 = self.get_project(project_id_1)
        project2 = self.get_project(project_id_2)

        items1 = self.get_project_items(project_id_1)
        items2 = self.get_project_items(project_id_2)

        comparison = {
            'project1': {
                'id': project_id_1,
                'name': project1['hotel_info'].get('property_name', 'Project 1'),
                'rooms': project1['hotel_info'].get('total_rooms', 0),
                'total_items': len(items1),
                'total_budget': sum(item['procurement_status']['total_price'] for item in items1)
            },
            'project2': {
                'id': project_id_2,
                'name': project2['hotel_info'].get('property_name', 'Project 2'),
                'rooms': project2['hotel_info'].get('total_rooms', 0),
                'total_items': len(items2),
                'total_budget': sum(item['procurement_status']['total_price'] for item in items2)
            },
            'differences': {
                'rooms_diff': project1['hotel_info'].get('total_rooms', 0) - project2['hotel_info'].get('total_rooms', 0),
                'items_diff': len(items1) - len(items2),
                'budget_diff': sum(item['procurement_status']['total_price'] for item in items1) -
                              sum(item['procurement_status']['total_price'] for item in items2)
            }
        }

        return comparison

    def delete_project(self, project_id: str) -> bool:
        """Delete a project"""
        projects = self._read_json(self.projects_file)
        items = self._read_json(self.items_file)

        if project_id in projects:
            del projects[project_id]
            self._write_json(self.projects_file, projects)

        if project_id in items:
            del items[project_id]
            self._write_json(self.items_file, items)

        return True
