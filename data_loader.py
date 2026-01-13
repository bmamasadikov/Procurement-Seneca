"""
Data loader module to extract and process existing Excel procurement data
"""
import pandas as pd
import openpyxl
from typing import Dict, List, Any
import warnings
warnings.filterwarnings('ignore')

class ProcurementDataLoader:
    """Load and process procurement data from existing Excel files"""

    def __init__(self, excel_path: str):
        self.excel_path = excel_path
        self.workbook = None
        self.data = {}

    def load_all_data(self) -> Dict[str, Any]:
        """Load all procurement data from Excel"""
        try:
            self.workbook = pd.ExcelFile(self.excel_path)

            # Load different categories
            self.data = {
                'beds_linen': self.load_beds_and_linen(),
                'furniture': self.load_furniture(),
                'restaurant': self.load_restaurant(),
                'kitchen': self.load_kitchen(),
                'amenities': self.load_amenities(),
                'ff_and_e': self.load_ff_and_e_checklist()
            }

            return self.data
        except Exception as e:
            print(f"Error loading data: {str(e)}")
            return {}

    def load_beds_and_linen(self) -> List[Dict]:
        """Load beds, mattresses, and linen data"""
        items = []

        try:
            df = pd.read_excel(self.workbook, sheet_name='Beds, Mattress & Linen', header=None)

            # Extract bed configuration
            # Row 2: Headers - Units, Size, STD, DLX, SUITE, EXTRA, etc.
            # Row 3-5: Bed data

            # Beds
            if len(df) > 3:
                std_rooms = df.iloc[2, 1] if pd.notna(df.iloc[2, 1]) else 0
                dlx_rooms = df.iloc[3, 1] if pd.notna(df.iloc[3, 1]) else 0
                suite_rooms = df.iloc[4, 1] if pd.notna(df.iloc[4, 1]) else 0

                items.append({
                    'category': 'Room Configuration',
                    'std_rooms': int(std_rooms) if pd.notna(std_rooms) else 0,
                    'dlx_rooms': int(dlx_rooms) if pd.notna(dlx_rooms) else 0,
                    'suite_rooms': int(suite_rooms) if pd.notna(suite_rooms) else 0
                })

            # Linen items - parse the structure
            linen_categories = ['Bedsheets', 'Mattress Protector', 'Duvet Cover',
                              'Pillow Case', 'Pillows', 'Towels', 'Bathrobe']

            for category in linen_categories:
                items.append({
                    'category': 'Linen',
                    'item': category,
                    'par_level': 4  # Default par level
                })

        except Exception as e:
            print(f"Error loading beds and linen: {str(e)}")

        return items

    def load_furniture(self) -> List[Dict]:
        """Load furniture list"""
        items = []

        try:
            df = pd.read_excel(self.workbook, sheet_name='FURNITURELIST', header=None)

            # Skip header rows and process data
            for idx in range(3, len(df)):
                row = df.iloc[idx]

                # Extract furniture code, name, total count
                if pd.notna(row[0]) and pd.notna(row[1]):
                    items.append({
                        'code': str(row[0]),
                        'name': str(row[1]),
                        'total': row[2] if pd.notna(row[2]) else 0,
                        'category': 'Furniture'
                    })

        except Exception as e:
            print(f"Error loading furniture: {str(e)}")

        return items

    def load_restaurant(self) -> List[Dict]:
        """Load restaurant items"""
        items = []

        try:
            df = pd.read_excel(self.workbook, sheet_name='Restaurant', header=None)

            # Process restaurant items
            for idx in range(2, len(df)):
                row = df.iloc[idx]

                if pd.notna(row[1]) and pd.notna(row[2]):
                    items.append({
                        'item': str(row[1]),
                        'quantity': row[2] if pd.notna(row[2]) else 0,
                        'category': 'Restaurant'
                    })

        except Exception as e:
            print(f"Error loading restaurant: {str(e)}")

        return items

    def load_kitchen(self) -> List[Dict]:
        """Load kitchen equipment"""
        items = []

        try:
            df = pd.read_excel(self.workbook, sheet_name='Kitchen', header=None)

            # Process kitchen items starting from row 1 (after header)
            for idx in range(1, len(df)):
                row = df.iloc[idx]

                if pd.notna(row[3]):  # Item name is in column 3
                    items.append({
                        'item': str(row[3]),
                        'manufacturer': str(row[4]) if pd.notna(row[4]) else '',
                        'model': str(row[5]) if pd.notna(row[5]) else '',
                        'size': str(row[6]) if pd.notna(row[6]) else '',
                        'quantity': row[7] if pd.notna(row[7]) else 0,
                        'category': 'Kitchen'
                    })

        except Exception as e:
            print(f"Error loading kitchen: {str(e)}")

        return items

    def load_amenities(self) -> List[Dict]:
        """Load room amenities"""
        items = []

        try:
            if 'AMENITIES' in self.workbook.sheet_names:
                df = pd.read_excel(self.workbook, sheet_name='AMENITIES', header=None)

                for idx in range(1, len(df)):
                    row = df.iloc[idx]

                    if pd.notna(row[0]):
                        items.append({
                            'item': str(row[0]),
                            'category': 'Amenities'
                        })

        except Exception as e:
            print(f"Error loading amenities: {str(e)}")

        return items

    def load_ff_and_e_checklist(self) -> Dict[str, List[Dict]]:
        """Load FF&E checklist organized by area"""
        checklist = {
            'rooms': [],
            'lobby': [],
            'machinery': []
        }

        try:
            df = pd.read_excel(self.workbook, sheet_name='FF&E Checklist', header=None)

            # The checklist has multiple columns for different areas
            # Column structure: ROOMS | HALLS & LOBBY | MACHINERY

            for idx in range(1, len(df)):
                row = df.iloc[idx]

                # Rooms items (column 1)
                if pd.notna(row[1]):
                    checklist['rooms'].append({
                        'item': str(row[1]),
                        'status': str(row[3]) if pd.notna(row[3]) else ''
                    })

                # Lobby items (column 6)
                if pd.notna(row[6]):
                    checklist['lobby'].append({
                        'item': str(row[6]),
                        'status': str(row[8]) if pd.notna(row[8]) else ''
                    })

                # Machinery items (column 11)
                if pd.notna(row[11]):
                    checklist['machinery'].append({
                        'item': str(row[11]),
                        'status': str(row[13]) if pd.notna(row[13]) else ''
                    })

        except Exception as e:
            print(f"Error loading FF&E checklist: {str(e)}")

        return checklist

    def get_room_configuration(self) -> Dict[str, int]:
        """Extract room configuration from the data"""
        config = {
            'std_rooms': 25,
            'dlx_rooms': 21,
            'suite_rooms': 4,
            'total_rooms': 50
        }

        if 'beds_linen' in self.data and self.data['beds_linen']:
            for item in self.data['beds_linen']:
                if item.get('category') == 'Room Configuration':
                    config.update({
                        'std_rooms': item.get('std_rooms', 25),
                        'dlx_rooms': item.get('dlx_rooms', 21),
                        'suite_rooms': item.get('suite_rooms', 4)
                    })
                    config['total_rooms'] = (
                        config['std_rooms'] +
                        config['dlx_rooms'] +
                        config['suite_rooms']
                    )
                    break

        return config


class BrandStandards:
    """Hotel brand standards and multipliers"""

    STANDARDS = {
        'Hilton': {
            'linen_par_level': 4,
            'towel_par_level': 5,
            'reserve_stock': 15,
            'amenities': [
                'Shampoo', 'Conditioner', 'Body Wash', 'Lotion',
                'Soap', 'Dental Kit', 'Sewing Kit', 'Shower Cap'
            ],
            'room_furniture': {
                'Bedside Table': 2,
                'Desk': 1,
                'Desk Chair': 1,
                'Lounge Chair': 1,
                'Ottoman': 1,
                'Wardrobe': 1,
                'TV Unit': 1,
                'Luggage Rack': 1,
                'Full Length Mirror': 1,
                'Safe': 1
            }
        },
        'DoubleTree': {
            'linen_par_level': 4,
            'towel_par_level': 4,
            'reserve_stock': 12,
            'amenities': [
                'Shampoo', 'Conditioner', 'Body Wash', 'Lotion',
                'Soap', 'Dental Kit', 'Sewing Kit'
            ],
            'room_furniture': {
                'Bedside Table': 2,
                'Desk': 1,
                'Desk Chair': 1,
                'Lounge Chair': 1,
                'Wardrobe': 1,
                'TV Unit': 1,
                'Luggage Rack': 1,
                'Mirror': 1,
                'Safe': 1
            }
        },
        'Hilton Garden Inn': {
            'linen_par_level': 3,
            'towel_par_level': 4,
            'reserve_stock': 10,
            'amenities': [
                'Shampoo', 'Conditioner', 'Body Wash',
                'Soap', 'Lotion'
            ],
            'room_furniture': {
                'Bedside Table': 2,
                'Desk': 1,
                'Desk Chair': 1,
                'Lounge Chair': 1,
                'Wardrobe': 1,
                'TV Unit': 1,
                'Mirror': 1
            }
        },
        'Marriott': {
            'linen_par_level': 4,
            'towel_par_level': 5,
            'reserve_stock': 15,
            'amenities': [
                'Shampoo', 'Conditioner', 'Body Wash', 'Lotion',
                'Soap', 'Dental Kit', 'Sewing Kit', 'Shower Cap',
                'Nail File'
            ],
            'room_furniture': {
                'Bedside Table': 2,
                'Desk': 1,
                'Desk Chair': 1,
                'Lounge Chair': 1,
                'Ottoman': 1,
                'Wardrobe': 1,
                'TV Unit': 1,
                'Luggage Rack': 1,
                'Mirror': 2,
                'Safe': 1
            }
        },
        'Radisson': {
            'linen_par_level': 4,
            'towel_par_level': 4,
            'reserve_stock': 12,
            'amenities': [
                'Shampoo', 'Conditioner', 'Body Wash', 'Lotion',
                'Soap', 'Dental Kit'
            ],
            'room_furniture': {
                'Bedside Table': 2,
                'Desk': 1,
                'Desk Chair': 1,
                'Armchair': 1,
                'Wardrobe': 1,
                'TV Unit': 1,
                'Luggage Rack': 1,
                'Mirror': 1,
                'Safe': 1
            }
        },
        'Independent': {
            'linen_par_level': 3,
            'towel_par_level': 3,
            'reserve_stock': 10,
            'amenities': [
                'Shampoo', 'Soap', 'Body Wash'
            ],
            'room_furniture': {
                'Bedside Table': 2,
                'Desk': 1,
                'Desk Chair': 1,
                'Chair': 1,
                'Wardrobe': 1,
                'TV Unit': 1,
                'Mirror': 1
            }
        }
    }

    @classmethod
    def get_standard(cls, brand: str) -> Dict:
        """Get standards for a specific brand"""
        return cls.STANDARDS.get(brand, cls.STANDARDS['Independent'])

    @classmethod
    def get_available_brands(cls) -> List[str]:
        """Get list of available brand standards"""
        return list(cls.STANDARDS.keys())
