"""
Department and subdepartment structure for hotel procurement
"""

class HotelDepartments:
    """Define hotel department structure and subdepartments"""

    STRUCTURE = {
        'Front Office': {
            'subdepartments': [
                'Reception/Front Desk',
                'Concierge',
                'Bell Services',
                'Business Center',
                'Guest Relations'
            ],
            'icon': '🏢'
        },
        'Housekeeping': {
            'subdepartments': [
                'Guest Rooms',
                'Public Areas',
                'Laundry',
                'Linen Room',
                'Housekeeping Office'
            ],
            'icon': '🧹'
        },
        'Food & Beverage': {
            'subdepartments': [
                'Main Kitchen',
                'Restaurant - Breakfast',
                'Restaurant - A la Carte',
                'Room Service',
                'Banquet/Events',
                'Bar/Lounge',
                'Buffet Area',
                'Pastry/Bakery',
                'Stewarding'
            ],
            'icon': '🍽️'
        },
        'Rooms Division': {
            'subdepartments': [
                'Standard Rooms',
                'Deluxe Rooms',
                'Suites',
                'Accessible Rooms',
                'Connecting Rooms'
            ],
            'icon': '🛏️'
        },
        'Spa & Wellness': {
            'subdepartments': [
                'Treatment Rooms',
                'Spa Reception',
                'Relaxation Area',
                'Wet Area (Sauna/Steam)',
                'Spa Retail'
            ],
            'icon': '💆'
        },
        'Recreation': {
            'subdepartments': [
                'Swimming Pool',
                'Fitness Center/Gym',
                'Kids Club',
                'Sports Facilities',
                'Pool Bar'
            ],
            'icon': '🏊'
        },
        'Meeting & Events': {
            'subdepartments': [
                'Conference Rooms',
                'Ballroom',
                'Meeting Rooms (Small)',
                'Meeting Rooms (Medium)',
                'Pre-function Areas',
                'Business Center'
            ],
            'icon': '📊'
        },
        'Back of House': {
            'subdepartments': [
                'Staff Areas',
                'Staff Cafeteria',
                'Lockers & Changing Rooms',
                'Offices',
                'Storage',
                'Maintenance/Engineering',
                'Security',
                'IT/Communications'
            ],
            'icon': '🏢'
        },
        'Engineering & Maintenance': {
            'subdepartments': [
                'Workshop',
                'Electrical Room',
                'HVAC',
                'Plumbing',
                'General Maintenance',
                'Groundskeeping'
            ],
            'icon': '🔧'
        }
    }

    @classmethod
    def get_all_departments(cls):
        """Get list of all departments"""
        return list(cls.STRUCTURE.keys())

    @classmethod
    def get_subdepartments(cls, department):
        """Get subdepartments for a specific department"""
        return cls.STRUCTURE.get(department, {}).get('subdepartments', [])

    @classmethod
    def get_icon(cls, department):
        """Get icon for a department"""
        return cls.STRUCTURE.get(department, {}).get('icon', '📋')


class DepartmentItems:
    """Standard items for each department/subdepartment"""

    ITEMS = {
        'Front Office': {
            'Reception/Front Desk': [
                {'item': 'Reception Desk', 'unit': 'pcs', 'qty_formula': 'fixed:1'},
                {'item': 'Reception Chair (Staff)', 'unit': 'pcs', 'qty_formula': 'fixed:3'},
                {'item': 'Computer Workstation', 'unit': 'pcs', 'qty_formula': 'fixed:3'},
                {'item': 'Phone System', 'unit': 'sets', 'qty_formula': 'fixed:1'},
                {'item': 'Key Card System', 'unit': 'sets', 'qty_formula': 'fixed:1'},
                {'item': 'Safe Deposit Boxes', 'unit': 'pcs', 'qty_formula': 'rooms:0.5'},
                {'item': 'Guest Directory/Compendium', 'unit': 'pcs', 'qty_formula': 'rooms:1'},
            ],
            'Concierge': [
                {'item': 'Concierge Desk', 'unit': 'pcs', 'qty_formula': 'fixed:1'},
                {'item': 'Concierge Chair', 'unit': 'pcs', 'qty_formula': 'fixed:2'},
                {'item': 'Brochure Display Rack', 'unit': 'pcs', 'qty_formula': 'fixed:2'},
            ],
            'Bell Services': [
                {'item': 'Bell Stand', 'unit': 'pcs', 'qty_formula': 'fixed:1'},
                {'item': 'Luggage Cart', 'unit': 'pcs', 'qty_formula': 'rooms:0.1'},
                {'item': 'Luggage Storage Rack', 'unit': 'pcs', 'qty_formula': 'fixed:3'},
            ],
        },

        'Housekeeping': {
            'Guest Rooms': [
                {'item': 'Bed Base', 'unit': 'pcs', 'category': 'Furniture', 'qty_formula': 'beds:1'},
                {'item': 'Mattress', 'unit': 'pcs', 'category': 'Furniture', 'qty_formula': 'beds:1'},
                {'item': 'Bedside Table', 'unit': 'pcs', 'category': 'Furniture', 'qty_formula': 'rooms:2'},
                {'item': 'Desk', 'unit': 'pcs', 'category': 'Furniture', 'qty_formula': 'rooms:1'},
                {'item': 'Desk Chair', 'unit': 'pcs', 'category': 'Furniture', 'qty_formula': 'rooms:1'},
                {'item': 'Lounge Chair', 'unit': 'pcs', 'category': 'Furniture', 'qty_formula': 'rooms:1'},
                {'item': 'Wardrobe', 'unit': 'pcs', 'category': 'Furniture', 'qty_formula': 'rooms:1'},
                {'item': 'TV Unit', 'unit': 'pcs', 'category': 'Furniture', 'qty_formula': 'rooms:1'},
                {'item': 'Luggage Rack', 'unit': 'pcs', 'category': 'Furniture', 'qty_formula': 'rooms:1'},
                {'item': 'Safe', 'unit': 'pcs', 'category': 'Equipment', 'qty_formula': 'rooms:1'},
                {'item': 'Mirror', 'unit': 'pcs', 'category': 'Furniture', 'qty_formula': 'rooms:2'},
                {'item': 'Waste Bin', 'unit': 'pcs', 'category': 'Equipment', 'qty_formula': 'rooms:2'},
            ],
            'Laundry': [
                {'item': 'Commercial Washer', 'unit': 'pcs', 'qty_formula': 'rooms:0.02'},
                {'item': 'Commercial Dryer', 'unit': 'pcs', 'qty_formula': 'rooms:0.02'},
                {'item': 'Ironing Station', 'unit': 'pcs', 'qty_formula': 'rooms:0.01'},
                {'item': 'Laundry Cart', 'unit': 'pcs', 'qty_formula': 'rooms:0.05'},
                {'item': 'Folding Table', 'unit': 'pcs', 'qty_formula': 'fixed:3'},
            ],
            'Linen Room': [
                {'item': 'Linen Storage Shelving', 'unit': 'units', 'qty_formula': 'fixed:8'},
                {'item': 'Linen Cart', 'unit': 'pcs', 'qty_formula': 'rooms:0.1'},
            ],
            'Housekeeping Office': [
                {'item': 'Housekeeping Cart', 'unit': 'pcs', 'qty_formula': 'rooms:0.1'},
                {'item': 'Vacuum Cleaner', 'unit': 'pcs', 'qty_formula': 'rooms:0.067'},
                {'item': 'Floor Polisher', 'unit': 'pcs', 'qty_formula': 'fixed:2'},
                {'item': 'Mop & Bucket Set', 'unit': 'sets', 'qty_formula': 'rooms:0.1'},
            ],
        },

        'Food & Beverage': {
            'Main Kitchen': [
                {'item': 'Commercial Range (6-burner)', 'unit': 'pcs', 'qty_formula': 'kitchen:2'},
                {'item': 'Convection Oven', 'unit': 'pcs', 'qty_formula': 'kitchen:2'},
                {'item': 'Griddle', 'unit': 'pcs', 'qty_formula': 'kitchen:1'},
                {'item': 'Deep Fryer', 'unit': 'pcs', 'qty_formula': 'kitchen:2'},
                {'item': 'Steamer', 'unit': 'pcs', 'qty_formula': 'kitchen:1'},
                {'item': 'Salamander/Broiler', 'unit': 'pcs', 'qty_formula': 'kitchen:1'},
                {'item': 'Commercial Refrigerator', 'unit': 'pcs', 'qty_formula': 'kitchen:2'},
                {'item': 'Walk-in Freezer', 'unit': 'pcs', 'qty_formula': 'kitchen:1'},
                {'item': 'Prep Refrigerator', 'unit': 'pcs', 'qty_formula': 'kitchen:2'},
                {'item': 'Ice Machine', 'unit': 'pcs', 'qty_formula': 'kitchen:1'},
                {'item': 'Dishwasher (Commercial)', 'unit': 'pcs', 'qty_formula': 'kitchen:1'},
                {'item': 'Food Processor', 'unit': 'pcs', 'qty_formula': 'kitchen:2'},
                {'item': 'Stand Mixer', 'unit': 'pcs', 'qty_formula': 'kitchen:2'},
                {'item': 'Work Table (Stainless)', 'unit': 'pcs', 'qty_formula': 'kitchen:6'},
                {'item': 'Sink (3-compartment)', 'unit': 'pcs', 'qty_formula': 'kitchen:2'},
                {'item': 'Exhaust Hood', 'unit': 'pcs', 'qty_formula': 'kitchen:3'},
                {'item': 'Shelving Unit (Stainless)', 'unit': 'pcs', 'qty_formula': 'kitchen:8'},
            ],
            'Restaurant - Breakfast': [
                {'item': 'Dining Chair', 'unit': 'pcs', 'qty_formula': 'seats:1'},
                {'item': 'Dining Table (2-seater)', 'unit': 'pcs', 'qty_formula': 'seats:0.15'},
                {'item': 'Dining Table (4-seater)', 'unit': 'pcs', 'qty_formula': 'seats:0.25'},
                {'item': 'Service Station', 'unit': 'pcs', 'qty_formula': 'restaurant:2'},
                {'item': 'Host Stand', 'unit': 'pcs', 'qty_formula': 'restaurant:1'},
            ],
            'Restaurant - A la Carte': [
                {'item': 'Dining Chair', 'unit': 'pcs', 'qty_formula': 'seats:1'},
                {'item': 'Dining Table (2-seater)', 'unit': 'pcs', 'qty_formula': 'seats:0.2'},
                {'item': 'Dining Table (4-seater)', 'unit': 'pcs', 'qty_formula': 'seats:0.3'},
                {'item': 'Dining Table (6-seater)', 'unit': 'pcs', 'qty_formula': 'seats:0.125'},
                {'item': 'Bar Stool', 'unit': 'pcs', 'qty_formula': 'fixed:12'},
                {'item': 'Bar Counter', 'unit': 'pcs', 'qty_formula': 'restaurant:1'},
            ],
            'Buffet Area': [
                {'item': 'Buffet Table (Hot)', 'unit': 'pcs', 'qty_formula': 'restaurant:3'},
                {'item': 'Buffet Table (Cold)', 'unit': 'pcs', 'qty_formula': 'restaurant:3'},
                {'item': 'Chafing Dish', 'unit': 'pcs', 'qty_formula': 'restaurant:12'},
                {'item': 'Ice Display Unit', 'unit': 'pcs', 'qty_formula': 'restaurant:2'},
            ],
            'Bar/Lounge': [
                {'item': 'Bar Counter', 'unit': 'pcs', 'qty_formula': 'fixed:1'},
                {'item': 'Bar Stool', 'unit': 'pcs', 'qty_formula': 'fixed:12'},
                {'item': 'Lounge Sofa', 'unit': 'pcs', 'qty_formula': 'fixed:5'},
                {'item': 'Lounge Chair', 'unit': 'pcs', 'qty_formula': 'fixed:8'},
                {'item': 'Coffee Table', 'unit': 'pcs', 'qty_formula': 'fixed:5'},
                {'item': 'Back Bar Shelving', 'unit': 'units', 'qty_formula': 'fixed:1'},
                {'item': 'Glass Washer', 'unit': 'pcs', 'qty_formula': 'fixed:1'},
                {'item': 'Ice Maker', 'unit': 'pcs', 'qty_formula': 'fixed:1'},
                {'item': 'Blender', 'unit': 'pcs', 'qty_formula': 'fixed:2'},
            ],
            'Room Service': [
                {'item': 'Room Service Cart', 'unit': 'pcs', 'qty_formula': 'rooms:0.1'},
                {'item': 'Hot Box/Food Warmer', 'unit': 'pcs', 'qty_formula': 'fixed:3'},
                {'item': 'Tray Stand', 'unit': 'pcs', 'qty_formula': 'rooms:0.2'},
            ],
            'Pastry/Bakery': [
                {'item': 'Pastry Oven', 'unit': 'pcs', 'qty_formula': 'fixed:2'},
                {'item': 'Dough Mixer', 'unit': 'pcs', 'qty_formula': 'fixed:2'},
                {'item': 'Work Table (Marble Top)', 'unit': 'pcs', 'qty_formula': 'fixed:3'},
                {'item': 'Proof Box', 'unit': 'pcs', 'qty_formula': 'fixed:1'},
                {'item': 'Display Refrigerator', 'unit': 'pcs', 'qty_formula': 'fixed:2'},
            ],
        },

        'Spa & Wellness': {
            'Treatment Rooms': [
                {'item': 'Treatment Bed/Table', 'unit': 'pcs', 'qty_formula': 'spa_rooms:1'},
                {'item': 'Stool (Therapist)', 'unit': 'pcs', 'qty_formula': 'spa_rooms:1'},
                {'item': 'Side Table/Trolley', 'unit': 'pcs', 'qty_formula': 'spa_rooms:1'},
                {'item': 'Storage Cabinet', 'unit': 'pcs', 'qty_formula': 'spa_rooms:1'},
                {'item': 'Towel Warmer', 'unit': 'pcs', 'qty_formula': 'spa_rooms:1'},
                {'item': 'Robe Hook', 'unit': 'pcs', 'qty_formula': 'spa_rooms:2'},
            ],
            'Spa Reception': [
                {'item': 'Reception Desk', 'unit': 'pcs', 'qty_formula': 'fixed:1'},
                {'item': 'Reception Chair (Staff)', 'unit': 'pcs', 'qty_formula': 'fixed:2'},
                {'item': 'Waiting Area Sofa', 'unit': 'pcs', 'qty_formula': 'fixed:2'},
                {'item': 'Retail Display Shelving', 'unit': 'units', 'qty_formula': 'fixed:3'},
            ],
            'Relaxation Area': [
                {'item': 'Lounge Chair/Recliner', 'unit': 'pcs', 'qty_formula': 'spa_rooms:2'},
                {'item': 'Side Table', 'unit': 'pcs', 'qty_formula': 'spa_rooms:2'},
                {'item': 'Water Dispenser', 'unit': 'pcs', 'qty_formula': 'fixed:1'},
            ],
        },

        'Recreation': {
            'Swimming Pool': [
                {'item': 'Pool Lounge Chair', 'unit': 'pcs', 'qty_formula': 'rooms:0.4'},
                {'item': 'Pool Umbrella', 'unit': 'pcs', 'qty_formula': 'rooms:0.2'},
                {'item': 'Side Table (Pool)', 'unit': 'pcs', 'qty_formula': 'rooms:0.2'},
                {'item': 'Life Ring', 'unit': 'pcs', 'qty_formula': 'fixed:2'},
                {'item': 'Pool Net/Skimmer', 'unit': 'pcs', 'qty_formula': 'fixed:2'},
                {'item': 'Pool Vacuum', 'unit': 'pcs', 'qty_formula': 'fixed:1'},
            ],
            'Fitness Center/Gym': [
                {'item': 'Treadmill', 'unit': 'pcs', 'qty_formula': 'rooms:0.08'},
                {'item': 'Elliptical Trainer', 'unit': 'pcs', 'qty_formula': 'rooms:0.06'},
                {'item': 'Exercise Bike', 'unit': 'pcs', 'qty_formula': 'rooms:0.06'},
                {'item': 'Rowing Machine', 'unit': 'pcs', 'qty_formula': 'fixed:2'},
                {'item': 'Weight Bench', 'unit': 'pcs', 'qty_formula': 'fixed:2'},
                {'item': 'Dumbbell Set (5-50 lbs)', 'unit': 'sets', 'qty_formula': 'fixed:2'},
                {'item': 'Kettlebell Set', 'unit': 'sets', 'qty_formula': 'fixed:1'},
                {'item': 'Yoga Mat', 'unit': 'pcs', 'qty_formula': 'fixed:10'},
                {'item': 'Mirror (Wall)', 'unit': 'pcs', 'qty_formula': 'fixed:3'},
            ],
        },

        'Meeting & Events': {
            'Conference Rooms': [
                {'item': 'Conference Table (10-person)', 'unit': 'pcs', 'qty_formula': 'conference:1'},
                {'item': 'Conference Chair', 'unit': 'pcs', 'qty_formula': 'conference:12'},
                {'item': 'Projector', 'unit': 'pcs', 'qty_formula': 'conference:1'},
                {'item': 'Projection Screen', 'unit': 'pcs', 'qty_formula': 'conference:1'},
                {'item': 'Whiteboard', 'unit': 'pcs', 'qty_formula': 'conference:1'},
                {'item': 'Flip Chart & Stand', 'unit': 'sets', 'qty_formula': 'conference:1'},
            ],
            'Ballroom': [
                {'item': 'Banquet Chair', 'unit': 'pcs', 'qty_formula': 'rooms:3'},
                {'item': 'Banquet Table (Round)', 'unit': 'pcs', 'qty_formula': 'rooms:0.3'},
                {'item': 'Stage Platform', 'unit': 'sets', 'qty_formula': 'fixed:1'},
                {'item': 'Podium', 'unit': 'pcs', 'qty_formula': 'fixed:2'},
                {'item': 'Dance Floor (Portable)', 'unit': 'sqm', 'qty_formula': 'rooms:2'},
            ],
        },

        'Back of House': {
            'Staff Cafeteria': [
                {'item': 'Cafeteria Table', 'unit': 'pcs', 'qty_formula': 'rooms:0.2'},
                {'item': 'Cafeteria Chair', 'unit': 'pcs', 'qty_formula': 'rooms:0.8'},
                {'item': 'Microwave', 'unit': 'pcs', 'qty_formula': 'fixed:2'},
                {'item': 'Refrigerator', 'unit': 'pcs', 'qty_formula': 'fixed:2'},
                {'item': 'Water Cooler', 'unit': 'pcs', 'qty_formula': 'fixed:1'},
            ],
            'Lockers & Changing Rooms': [
                {'item': 'Staff Locker', 'unit': 'pcs', 'qty_formula': 'rooms:0.5'},
                {'item': 'Bench (Changing Room)', 'unit': 'pcs', 'qty_formula': 'rooms:0.1'},
                {'item': 'Mirror', 'unit': 'pcs', 'qty_formula': 'fixed:4'},
            ],
            'Offices': [
                {'item': 'Office Desk', 'unit': 'pcs', 'qty_formula': 'rooms:0.25'},
                {'item': 'Office Chair', 'unit': 'pcs', 'qty_formula': 'rooms:0.25'},
                {'item': 'Filing Cabinet', 'unit': 'pcs', 'qty_formula': 'fixed:5'},
                {'item': 'Bookshelf', 'unit': 'pcs', 'qty_formula': 'rooms:0.1'},
            ],
        },
    }

    @classmethod
    def get_items(cls, department, subdepartment):
        """Get items for a specific department and subdepartment"""
        return cls.ITEMS.get(department, {}).get(subdepartment, [])

    @classmethod
    def get_all_items_for_department(cls, department):
        """Get all items for a department across all subdepartments"""
        dept_data = cls.ITEMS.get(department, {})
        all_items = []

        for subdept, items in dept_data.items():
            for item in items:
                item_copy = item.copy()
                item_copy['subdepartment'] = subdept
                all_items.append(item_copy)

        return all_items
