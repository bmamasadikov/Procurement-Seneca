"""
Procurement calculation engine with industry standard multipliers
"""
from typing import Dict, List, Any
from data_loader import BrandStandards


class ProcurementCalculator:
    """Calculate procurement requirements based on hotel configuration"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.brand = config.get('hotel_brand', 'Independent')
        self.brand_standards = BrandStandards.get_standard(self.brand)
        self.results = {}

    def calculate_all(self) -> Dict[str, Any]:
        """Calculate all procurement categories"""

        self.results = {
            'summary': self._calculate_summary(),
            'guest_rooms': self._calculate_guest_rooms(),
            'linen': self._calculate_linen(),
            'bathroom': self._calculate_bathroom(),
            'furniture': self._calculate_furniture(),
            'amenities': self._calculate_amenities(),
            'restaurant': self._calculate_restaurant(),
            'kitchen': self._calculate_kitchen(),
            'spa': self._calculate_spa(),
            'pool': self._calculate_pool(),
            'gym': self._calculate_gym(),
            'public_areas': self._calculate_public_areas(),
            'conference': self._calculate_conference(),
            'back_of_house': self._calculate_back_of_house()
        }

        return self.results

    def _calculate_summary(self) -> Dict[str, Any]:
        """Calculate overall summary"""
        room_types = self.config.get('room_types', [])
        total_rooms = sum([rt['count'] for rt in room_types])
        total_beds = sum([rt['count'] * rt['num_beds'] for rt in room_types])

        return {
            'hotel_name': self.config.get('hotel_name', 'Unnamed Hotel'),
            'brand': self.brand,
            'total_rooms': total_rooms,
            'total_beds': total_beds,
            'num_floors': self.config.get('num_floors', 0),
            'room_types_count': len(room_types),
            'has_spa': self.config.get('has_spa', False),
            'has_pool': self.config.get('has_pool', False),
            'has_gym': self.config.get('has_gym', False),
            'num_restaurants': self.config.get('num_restaurants', 0),
            'num_kitchens': self.config.get('num_kitchens', 0),
            'num_conference': self.config.get('num_conference', 0)
        }

    def _calculate_guest_rooms(self) -> List[Dict]:
        """Calculate guest room FF&E"""
        items = []
        room_types = self.config.get('room_types', [])

        for room_type in room_types:
            room_count = room_type['count']
            num_beds = room_type['num_beds']
            bed_type = room_type['bed_type']
            room_name = room_type['name']

            # Bed bases
            items.append({
                'Category': 'Beds',
                'Item': f"Bed Base - {bed_type}",
                'Specification': self._get_bed_size(bed_type),
                'Room Type': room_name,
                'Qty per Room': num_beds,
                'Room Count': room_count,
                'Total Qty': num_beds * room_count,
                'Unit': 'pcs',
                'Notes': ''
            })

            # Mattresses
            items.append({
                'Category': 'Mattresses',
                'Item': f"Mattress - {bed_type}",
                'Specification': self._get_bed_size(bed_type),
                'Room Type': room_name,
                'Qty per Room': num_beds,
                'Room Count': room_count,
                'Total Qty': num_beds * room_count,
                'Unit': 'pcs',
                'Notes': f'{self.brand} standard quality'
            })

            # Mattress protectors
            items.append({
                'Category': 'Mattresses',
                'Item': f"Mattress Protector - Waterproof",
                'Specification': self._get_bed_size(bed_type),
                'Room Type': room_name,
                'Qty per Room': num_beds,
                'Room Count': room_count,
                'Total Qty': num_beds * room_count,
                'Unit': 'pcs',
                'Notes': 'Waterproof breathable fabric'
            })

        return items

    def _calculate_linen(self) -> List[Dict]:
        """Calculate linen requirements with par levels"""
        items = []
        room_types = self.config.get('room_types', [])
        par_level = self.config.get('par_level', self.brand_standards['linen_par_level'])
        towel_par = self.brand_standards['towel_par_level']
        reserve_pct = self.config.get('reserve_stock', self.brand_standards['reserve_stock'])

        # Linen items per bed
        linen_items = [
            {'name': 'Fitted Sheet', 'per_bed': 1, 'par': par_level},
            {'name': 'Flat Sheet', 'per_bed': 1, 'par': par_level},
            {'name': 'Duvet Cover', 'per_bed': 1, 'par': par_level},
            {'name': 'Duvet Insert', 'per_bed': 1, 'par': 2},  # Lower par for inserts
            {'name': 'Pillow Case', 'per_bed': 2, 'par': par_level},
            {'name': 'Pillow (Standard)', 'per_bed': 2, 'par': 2},
            {'name': 'Pillow (Extra)', 'per_bed': 2, 'par': 2},
            {'name': 'Bed Runner/Scarf', 'per_bed': 1, 'par': par_level},
        ]

        # Towel items per room
        towel_items = [
            {'name': 'Bath Towel', 'per_room': 2, 'par': towel_par},
            {'name': 'Hand Towel', 'per_room': 2, 'par': towel_par},
            {'name': 'Face Towel', 'per_room': 2, 'par': towel_par},
            {'name': 'Bath Mat', 'per_room': 1, 'par': towel_par},
            {'name': 'Bathrobe', 'per_room': 2, 'par': 2},
            {'name': 'Slippers (Pair)', 'per_room': 2, 'par': 3},
        ]

        for room_type in room_types:
            room_count = room_type['count']
            num_beds = room_type['num_beds']
            room_name = room_type['name']
            bed_type = room_type['bed_type']
            bed_size = self._get_bed_size(bed_type)

            # Calculate linen
            for item in linen_items:
                base_qty = room_count * num_beds * item['per_bed']
                with_par = base_qty * item['par']
                final_qty = int(with_par * (1 + reserve_pct / 100))

                items.append({
                    'Category': 'Bed Linen',
                    'Item': item['name'],
                    'Specification': bed_size,
                    'Room Type': room_name,
                    'Per Bed': item['per_bed'],
                    'Total Beds': room_count * num_beds,
                    'Base Qty': base_qty,
                    'Par Level': item['par'],
                    'Qty with Par': with_par,
                    'Reserve %': reserve_pct,
                    'Final Qty': final_qty,
                    'Unit': 'pcs'
                })

            # Calculate towels and bathrobes
            for item in towel_items:
                base_qty = room_count * item['per_room']
                with_par = base_qty * item['par']
                final_qty = int(with_par * (1 + reserve_pct / 100))

                items.append({
                    'Category': 'Bathroom Linen',
                    'Item': item['name'],
                    'Specification': 'Standard',
                    'Room Type': room_name,
                    'Per Room': item['per_room'],
                    'Room Count': room_count,
                    'Base Qty': base_qty,
                    'Par Level': item['par'],
                    'Qty with Par': with_par,
                    'Reserve %': reserve_pct,
                    'Final Qty': final_qty,
                    'Unit': 'pcs'
                })

        return items

    def _calculate_bathroom(self) -> List[Dict]:
        """Calculate bathroom fixtures and accessories"""
        items = []
        room_types = self.config.get('room_types', [])

        bathroom_items = [
            {'name': 'Toilet', 'qty': 1},
            {'name': 'Sink/Vanity', 'qty': 1},
            {'name': 'Shower/Bathtub', 'qty': 1},
            {'name': 'Mirror (Bathroom)', 'qty': 1},
            {'name': 'Towel Bar', 'qty': 2},
            {'name': 'Towel Ring', 'qty': 1},
            {'name': 'Robe Hook', 'qty': 2},
            {'name': 'Toilet Paper Holder', 'qty': 1},
            {'name': 'Waste Bin', 'qty': 1},
            {'name': 'Hairdryer', 'qty': 1},
            {'name': 'Magnifying Mirror', 'qty': 1},
            {'name': 'Shower Curtain/Door', 'qty': 1},
        ]

        for room_type in room_types:
            for item in bathroom_items:
                items.append({
                    'Category': 'Bathroom Fixtures',
                    'Item': item['name'],
                    'Room Type': room_type['name'],
                    'Qty per Room': item['qty'],
                    'Room Count': room_type['count'],
                    'Total Qty': item['qty'] * room_type['count'],
                    'Unit': 'pcs'
                })

        return items

    def _calculate_furniture(self) -> List[Dict]:
        """Calculate furniture based on brand standards"""
        items = []
        room_types = self.config.get('room_types', [])
        furniture_standard = self.brand_standards['room_furniture']

        for room_type in room_types:
            for furniture_item, qty in furniture_standard.items():
                items.append({
                    'Category': 'Guest Room Furniture',
                    'Item': furniture_item,
                    'Room Type': room_type['name'],
                    'Qty per Room': qty,
                    'Room Count': room_type['count'],
                    'Total Qty': qty * room_type['count'],
                    'Unit': 'pcs',
                    'Brand Standard': self.brand
                })

        return items

    def _calculate_amenities(self) -> List[Dict]:
        """Calculate room amenities based on brand standards"""
        items = []
        room_types = self.config.get('room_types', [])
        amenities_list = self.brand_standards['amenities']

        # Amenities are typically per room per day, with stock for multiple days
        stock_days = 5  # Keep 5 days of stock

        for room_type in room_types:
            room_count = room_type['count']

            for amenity in amenities_list:
                # Most amenities are 1-2 per room
                qty_per_room = 2 if amenity in ['Soap', 'Shampoo'] else 1
                daily_need = room_count * qty_per_room
                total_stock = daily_need * stock_days

                items.append({
                    'Category': 'Room Amenities',
                    'Item': amenity,
                    'Room Type': room_type['name'],
                    'Qty per Room': qty_per_room,
                    'Room Count': room_count,
                    'Daily Requirement': daily_need,
                    'Stock Days': stock_days,
                    'Total Stock': total_stock,
                    'Unit': 'pcs',
                    'Brand Standard': self.brand
                })

        # Additional amenities
        additional_amenities = [
            {'name': 'Coffee/Tea Set', 'per_room': 1},
            {'name': 'Water Bottles (per day)', 'per_room': 2},
            {'name': 'Notepad', 'per_room': 1},
            {'name': 'Pen', 'per_room': 2},
            {'name': 'Laundry Bag', 'per_room': 1},
            {'name': 'Shoe Shine Kit', 'per_room': 1},
        ]

        for room_type in room_types:
            for item in additional_amenities:
                items.append({
                    'Category': 'Room Amenities',
                    'Item': item['name'],
                    'Room Type': room_type['name'],
                    'Qty per Room': item['per_room'],
                    'Room Count': room_type['count'],
                    'Total Qty': item['per_room'] * room_type['count'],
                    'Unit': 'sets' if 'Set' in item['name'] else 'pcs'
                })

        return items

    def _calculate_restaurant(self) -> List[Dict]:
        """Calculate restaurant F&B items"""
        items = []
        num_restaurants = self.config.get('num_restaurants', 0)

        if num_restaurants == 0:
            return items

        total_rooms = self.config.get('total_rooms', 50)
        # Assume 60-70% seat coverage of total rooms
        seats_per_restaurant = int(total_rooms * 0.65)

        # Restaurant furniture
        furniture_items = [
            {'name': 'Dining Chair', 'qty': seats_per_restaurant},
            {'name': 'Dining Table (2-seater)', 'qty': seats_per_restaurant // 6},
            {'name': 'Dining Table (4-seater)', 'qty': seats_per_restaurant // 3},
            {'name': 'Dining Table (6-seater)', 'qty': seats_per_restaurant // 8},
            {'name': 'Buffet Table', 'qty': 3},
            {'name': 'Service Station', 'qty': 2},
            {'name': 'Host Stand', 'qty': 1},
            {'name': 'Highchair', 'qty': 4},
        ]

        # Tableware - 3x multiplier for rotation
        tableware_items = [
            {'name': 'Dinner Plate', 'qty': seats_per_restaurant * 3},
            {'name': 'Salad/Dessert Plate', 'qty': seats_per_restaurant * 3},
            {'name': 'Bread Plate', 'qty': seats_per_restaurant * 3},
            {'name': 'Soup Bowl', 'qty': seats_per_restaurant * 3},
            {'name': 'Cereal Bowl', 'qty': seats_per_restaurant * 3},
            {'name': 'Coffee Cup & Saucer', 'qty': seats_per_restaurant * 3},
            {'name': 'Tea Cup & Saucer', 'qty': seats_per_restaurant * 3},
            {'name': 'Water Glass', 'qty': seats_per_restaurant * 4},
            {'name': 'Wine Glass (Red)', 'qty': seats_per_restaurant * 2},
            {'name': 'Wine Glass (White)', 'qty': seats_per_restaurant * 2},
            {'name': 'Champagne Flute', 'qty': seats_per_restaurant * 2},
        ]

        # Cutlery - 4x multiplier
        cutlery_items = [
            {'name': 'Dinner Fork', 'qty': seats_per_restaurant * 4},
            {'name': 'Salad Fork', 'qty': seats_per_restaurant * 4},
            {'name': 'Dinner Knife', 'qty': seats_per_restaurant * 4},
            {'name': 'Steak Knife', 'qty': seats_per_restaurant * 3},
            {'name': 'Soup Spoon', 'qty': seats_per_restaurant * 4},
            {'name': 'Teaspoon', 'qty': seats_per_restaurant * 4},
            {'name': 'Dessert Spoon', 'qty': seats_per_restaurant * 4},
        ]

        # Linen - 5x multiplier for rotation
        linen_items = [
            {'name': 'Tablecloth', 'qty': (seats_per_restaurant // 4) * 5},
            {'name': 'Napkin (Cloth)', 'qty': seats_per_restaurant * 5},
        ]

        for item in furniture_items:
            items.append({
                'Category': 'Restaurant Furniture',
                'Item': item['name'],
                'Outlets': num_restaurants,
                'Qty per Outlet': item['qty'],
                'Total Qty': item['qty'] * num_restaurants,
                'Unit': 'pcs'
            })

        for item in tableware_items:
            items.append({
                'Category': 'Tableware',
                'Item': item['name'],
                'Outlets': num_restaurants,
                'Seats per Outlet': seats_per_restaurant,
                'Multiplier': '3x',
                'Qty per Outlet': item['qty'],
                'Total Qty': item['qty'] * num_restaurants,
                'Unit': 'pcs'
            })

        for item in cutlery_items:
            items.append({
                'Category': 'Cutlery',
                'Item': item['name'],
                'Outlets': num_restaurants,
                'Seats per Outlet': seats_per_restaurant,
                'Multiplier': '4x',
                'Qty per Outlet': item['qty'],
                'Total Qty': item['qty'] * num_restaurants,
                'Unit': 'pcs'
            })

        for item in linen_items:
            items.append({
                'Category': 'Restaurant Linen',
                'Item': item['name'],
                'Outlets': num_restaurants,
                'Multiplier': '5x Par',
                'Qty per Outlet': item['qty'],
                'Total Qty': item['qty'] * num_restaurants,
                'Unit': 'pcs'
            })

        return items

    def _calculate_kitchen(self) -> List[Dict]:
        """Calculate kitchen equipment"""
        items = []
        num_kitchens = self.config.get('num_kitchens', 0)

        if num_kitchens == 0:
            return items

        # Major equipment
        major_equipment = [
            {'name': 'Commercial Range (6-burner)', 'qty': 2},
            {'name': 'Convection Oven', 'qty': 2},
            {'name': 'Griddle', 'qty': 1},
            {'name': 'Fryer (Deep)', 'qty': 2},
            {'name': 'Steamer', 'qty': 1},
            {'name': 'Salamander/Broiler', 'qty': 1},
            {'name': 'Commercial Refrigerator', 'qty': 2},
            {'name': 'Walk-in Freezer', 'qty': 1},
            {'name': 'Prep Refrigerator', 'qty': 2},
            {'name': 'Ice Machine', 'qty': 1},
            {'name': 'Dishwasher (Commercial)', 'qty': 1},
            {'name': 'Food Processor', 'qty': 2},
            {'name': 'Stand Mixer', 'qty': 2},
            {'name': 'Blender', 'qty': 3},
            {'name': 'Microwave (Commercial)', 'qty': 2},
        ]

        # Work stations
        work_stations = [
            {'name': 'Work Table (Stainless Steel)', 'qty': 6},
            {'name': 'Prep Table', 'qty': 4},
            {'name': 'Sink (3-compartment)', 'qty': 2},
            {'name': 'Hand Wash Sink', 'qty': 3},
            {'name': 'Shelving Unit (Stainless)', 'qty': 8},
            {'name': 'Exhaust Hood', 'qty': 3},
        ]

        # Small equipment
        small_equipment = [
            {'name': 'Cutting Board Set', 'qty': 10},
            {'name': 'Chef Knife Set', 'qty': 5},
            {'name': 'Mixing Bowl Set', 'qty': 5},
            {'name': 'Stock Pot Set', 'qty': 4},
            {'name': 'Sauce Pan Set', 'qty': 4},
            {'name': 'Frying Pan Set', 'qty': 4},
            {'name': 'Baking Sheet Pan', 'qty': 20},
            {'name': 'Hotel Pan (Full Size)', 'qty': 30},
            {'name': 'Hotel Pan (Half Size)', 'qty': 30},
        ]

        for item in major_equipment:
            items.append({
                'Category': 'Major Kitchen Equipment',
                'Item': item['name'],
                'Kitchens': num_kitchens,
                'Qty per Kitchen': item['qty'],
                'Total Qty': item['qty'] * num_kitchens,
                'Unit': 'pcs'
            })

        for item in work_stations:
            items.append({
                'Category': 'Kitchen Work Stations',
                'Item': item['name'],
                'Kitchens': num_kitchens,
                'Qty per Kitchen': item['qty'],
                'Total Qty': item['qty'] * num_kitchens,
                'Unit': 'pcs'
            })

        for item in small_equipment:
            items.append({
                'Category': 'Small Kitchen Equipment',
                'Item': item['name'],
                'Kitchens': num_kitchens,
                'Qty per Kitchen': item['qty'],
                'Total Qty': item['qty'] * num_kitchens,
                'Unit': 'sets' if 'Set' in item['name'] else 'pcs'
            })

        return items

    def _calculate_spa(self) -> List[Dict]:
        """Calculate spa equipment and supplies"""
        items = []

        if not self.config.get('has_spa', False):
            return items

        spa_rooms = self.config.get('spa_rooms', 4)

        # Spa furniture and equipment per treatment room
        spa_items = [
            {'name': 'Treatment Bed/Table', 'per_room': 1},
            {'name': 'Stool (Therapist)', 'per_room': 1},
            {'name': 'Side Table/Trolley', 'per_room': 1},
            {'name': 'Storage Cabinet', 'per_room': 1},
            {'name': 'Towel Warmer', 'per_room': 1},
            {'name': 'Robe Hook', 'per_room': 2},
        ]

        # Spa linen - higher par level
        spa_linen = [
            {'name': 'Spa Towel', 'per_room': 10, 'par': 5},
            {'name': 'Face Towel (Spa)', 'per_room': 10, 'par': 5},
            {'name': 'Spa Robe', 'per_room': 4, 'par': 3},
            {'name': 'Spa Slipper (Pair)', 'per_room': 4, 'par': 3},
            {'name': 'Sheet (Treatment Bed)', 'per_room': 3, 'par': 5},
        ]

        for item in spa_items:
            items.append({
                'Category': 'Spa Equipment',
                'Item': item['name'],
                'Treatment Rooms': spa_rooms,
                'Qty per Room': item['per_room'],
                'Total Qty': item['per_room'] * spa_rooms,
                'Unit': 'pcs'
            })

        for item in spa_linen:
            base = item['per_room'] * spa_rooms
            total = base * item['par']

            items.append({
                'Category': 'Spa Linen',
                'Item': item['name'],
                'Treatment Rooms': spa_rooms,
                'Per Room': item['per_room'],
                'Base Qty': base,
                'Par Level': item['par'],
                'Total Qty': total,
                'Unit': 'pcs'
            })

        return items

    def _calculate_pool(self) -> List[Dict]:
        """Calculate pool equipment"""
        items = []

        if not self.config.get('has_pool', False):
            return items

        pool_type = self.config.get('pool_type', 'Outdoor')

        pool_items = [
            {'name': 'Pool Lounge Chair', 'qty': 20},
            {'name': 'Pool Umbrella', 'qty': 10},
            {'name': 'Pool Towel', 'qty': 100, 'par': 4},
            {'name': 'Life Ring', 'qty': 2},
            {'name': 'Pool Net/Skimmer', 'qty': 2},
            {'name': 'Pool Vacuum', 'qty': 1},
            {'name': 'Chemical Test Kit', 'qty': 2},
        ]

        for item in pool_items:
            qty = item['qty']
            if 'par' in item:
                qty = item['qty'] * item['par']

            items.append({
                'Category': 'Pool Equipment',
                'Item': item['name'],
                'Pool Type': pool_type,
                'Total Qty': qty,
                'Unit': 'pcs',
                'Notes': f"Par {item['par']}x" if 'par' in item else ''
            })

        return items

    def _calculate_gym(self) -> List[Dict]:
        """Calculate gym equipment"""
        items = []

        if not self.config.get('has_gym', False):
            return items

        gym_items = [
            {'name': 'Treadmill', 'qty': 4},
            {'name': 'Elliptical Trainer', 'qty': 3},
            {'name': 'Exercise Bike', 'qty': 3},
            {'name': 'Rowing Machine', 'qty': 2},
            {'name': 'Weight Bench', 'qty': 2},
            {'name': 'Dumbbell Set (5-50 lbs)', 'qty': 2},
            {'name': 'Kettlebell Set', 'qty': 1},
            {'name': 'Yoga Mat', 'qty': 10},
            {'name': 'Exercise Ball', 'qty': 5},
            {'name': 'Towel (Gym)', 'qty': 50},
            {'name': 'Water Cooler', 'qty': 1},
            {'name': 'Mirror (Wall)', 'qty': 3},
        ]

        for item in gym_items:
            items.append({
                'Category': 'Gym Equipment',
                'Item': item['name'],
                'Total Qty': item['qty'],
                'Unit': 'sets' if 'Set' in item['name'] else 'pcs'
            })

        return items

    def _calculate_public_areas(self) -> List[Dict]:
        """Calculate public area furniture"""
        items = []

        public_items = [
            {'name': 'Reception Desk', 'qty': 1},
            {'name': 'Reception Chair (Staff)', 'qty': 3},
            {'name': 'Lobby Sofa (3-seater)', 'qty': 5},
            {'name': 'Lobby Armchair', 'qty': 10},
            {'name': 'Coffee Table', 'qty': 5},
            {'name': 'Side Table', 'qty': 8},
            {'name': 'Console Table', 'qty': 2},
            {'name': 'Decorative Rug', 'qty': 3},
            {'name': 'Artwork/Painting', 'qty': 15},
            {'name': 'Plant/Planter', 'qty': 10},
            {'name': 'Luggage Cart', 'qty': 5},
            {'name': 'Waste Bin (Lobby)', 'qty': 6},
            {'name': 'Signage (Directional)', 'qty': 20},
            {'name': 'Concierge Desk', 'qty': 1},
            {'name': 'Bell Stand', 'qty': 1},
        ]

        for item in public_items:
            items.append({
                'Category': 'Public Areas',
                'Item': item['name'],
                'Total Qty': item['qty'],
                'Unit': 'pcs'
            })

        return items

    def _calculate_conference(self) -> List[Dict]:
        """Calculate conference room equipment"""
        items = []
        num_conference = self.config.get('num_conference', 0)

        if num_conference == 0:
            return items

        # Per conference room
        conference_items = [
            {'name': 'Conference Table (10-person)', 'qty': 1},
            {'name': 'Conference Chair', 'qty': 12},
            {'name': 'Projector', 'qty': 1},
            {'name': 'Projection Screen', 'qty': 1},
            {'name': 'Whiteboard', 'qty': 1},
            {'name': 'Flip Chart & Stand', 'qty': 1},
            {'name': 'Water Pitcher', 'qty': 3},
            {'name': 'Water Glass', 'qty': 30},
            {'name': 'Notepad', 'qty': 20},
            {'name': 'Pen', 'qty': 20},
        ]

        for item in conference_items:
            items.append({
                'Category': 'Conference Room',
                'Item': item['name'],
                'Rooms': num_conference,
                'Qty per Room': item['qty'],
                'Total Qty': item['qty'] * num_conference,
                'Unit': 'pcs'
            })

        return items

    def _calculate_back_of_house(self) -> List[Dict]:
        """Calculate back of house equipment"""
        items = []

        total_rooms = self.config.get('total_rooms', 50)

        # Office furniture - scales with hotel size
        staff_count = int(total_rooms * 0.5)  # Rough estimate

        boh_items = [
            {'name': 'Office Desk', 'qty': staff_count // 2},
            {'name': 'Office Chair', 'qty': staff_count // 2},
            {'name': 'Filing Cabinet', 'qty': 5},
            {'name': 'Staff Locker', 'qty': staff_count},
            {'name': 'Staff Uniform', 'qty': staff_count * 3},
            {'name': 'Housekeeping Cart', 'qty': total_rooms // 10},
            {'name': 'Vacuum Cleaner', 'qty': total_rooms // 15},
            {'name': 'Floor Polisher', 'qty': 2},
            {'name': 'Laundry Basket', 'qty': total_rooms // 5},
        ]

        for item in boh_items:
            items.append({
                'Category': 'Back of House',
                'Item': item['name'],
                'Total Qty': item['qty'],
                'Unit': 'pcs',
                'Notes': ''
            })

        return items

    def _get_bed_size(self, bed_type: str) -> str:
        """Get bed size based on type"""
        sizes = {
            'King': '180x200 cm',
            'Queen': '160x200 cm',
            'Twin': '100x200 cm (each)',
            'Double Twin': '100x200 cm (each)',
            'Single': '100x200 cm'
        }
        return sizes.get(bed_type, '100x200 cm')
