from __future__ import annotations

import math
from typing import Any, Dict, List


ROOM_TYPE_OPTIONS = [
    "Conference Room",
    "Boardroom",
    "Meeting Room",
    "Training Room",
    "Ballroom Meeting Section",
    "Huddle Room",
]

SEATING_STYLE_OPTIONS = [
    "Executive Boardroom",
    "Standard Meeting",
    "Huddle / Small Room",
    "Training",
    "Theater",
]

AREA_PER_PERSON_RANGES = {
    "Executive Boardroom": (3.0, 3.5),
    "Standard Meeting": (2.3, 2.8),
    "Huddle / Small Room": (1.8, 2.2),
    "Training": (1.5, 2.0),
    "Theater": (0.9, 1.2),
}

DEFAULT_AREA_PER_PERSON = {
    "Executive Boardroom": 3.25,
    "Standard Meeting": 2.5,
    "Huddle / Small Room": 2.0,
    "Training": 1.75,
    "Theater": 1.05,
}

CHAIR_CLEARANCE_M = 0.95
ACCESSIBLE_ZONE_M = 1.50
TABLE_WIDTH_PER_PERSON_M = 0.75
TABLE_DEPTH_BY_STYLE_M = {
    "Executive Boardroom": 1.20,
    "Standard Meeting": 1.00,
    "Huddle / Small Room": 0.80,
}
TRAINING_ROW_PITCH_M = 1.50
THEATER_ROW_PITCH_M = 0.95
MIN_TABLE_WIDTH_RECOMMENDATION_M = 3.00


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _round_area(value: float) -> float:
    return round(max(value, 0.0), 2)


def _normalize_room_type(room_type: str) -> str:
    cleaned = _clean_text(room_type)
    if cleaned in ROOM_TYPE_OPTIONS:
        return cleaned
    return ""


def _normalize_seating_style(seating_style: str) -> str:
    cleaned = _clean_text(seating_style)
    if cleaned in SEATING_STYLE_OPTIONS:
        return cleaned
    return ""


def _infer_total_area(length_m: float, width_m: float, total_area_m2: float, total_area_override: bool) -> tuple[float, float]:
    auto_total_area = _round_area(length_m * width_m) if length_m > 0 and width_m > 0 else 0.0
    if total_area_override:
        return _round_area(total_area_m2), auto_total_area
    if auto_total_area > 0:
        return auto_total_area, auto_total_area
    return _round_area(total_area_m2), auto_total_area


def _calculate_table_based_limit(
    length_m: float,
    width_m: float,
    seating_style: str,
) -> int | None:
    if length_m <= 0 or width_m <= 0:
        return None

    table_depth = TABLE_DEPTH_BY_STYLE_M[seating_style]
    minimum_width = table_depth + (CHAIR_CLEARANCE_M * 2)
    if width_m < minimum_width or length_m < (1.8 + CHAIR_CLEARANCE_M * 2):
        return 0

    available_length = max(length_m - (CHAIR_CLEARANCE_M * 2), 0)
    side_seats = math.floor(available_length / TABLE_WIDTH_PER_PERSON_M) * 2
    end_seats = 2 if width_m >= minimum_width else 0
    capacity = max(side_seats + end_seats, 0)
    if seating_style == "Huddle / Small Room":
        capacity = min(capacity, 6)
    return capacity


def _calculate_training_limit(length_m: float, width_m: float) -> int | None:
    if length_m <= 0 or width_m <= 0:
        return None
    usable_length = max(length_m - ACCESSIBLE_ZONE_M, 0)
    usable_width = max(width_m - 1.0, 0)
    rows = math.floor(usable_length / TRAINING_ROW_PITCH_M)
    seats_per_row = math.floor(usable_width / TABLE_WIDTH_PER_PERSON_M)
    return max(rows * seats_per_row, 0)


def _calculate_theater_limit(length_m: float, width_m: float) -> int | None:
    if length_m <= 0 or width_m <= 0:
        return None
    usable_length = max(length_m - ACCESSIBLE_ZONE_M, 0)
    usable_width = max(width_m - 1.0, 0)
    rows = math.floor(usable_length / THEATER_ROW_PITCH_M)
    seats_per_row = math.floor(usable_width / TABLE_WIDTH_PER_PERSON_M)
    return max(rows * seats_per_row, 0)


def _calculate_practical_limit(length_m: float, width_m: float, seating_style: str) -> int | None:
    if seating_style in TABLE_DEPTH_BY_STYLE_M:
        return _calculate_table_based_limit(length_m, width_m, seating_style)
    if seating_style == "Training":
        return _calculate_training_limit(length_m, width_m)
    if seating_style == "Theater":
        return _calculate_theater_limit(length_m, width_m)
    return None


def _table_length_for_capacity(final_capacity: int) -> float | None:
    if final_capacity <= 0:
        return None
    if final_capacity <= 6:
        return 1.8
    if final_capacity <= 8:
        return 2.4
    if final_capacity <= 10:
        return 3.0
    if final_capacity <= 12:
        return 3.6
    return 3.6


def _recommended_table_shape(width_m: float, seating_style: str) -> str:
    if seating_style == "Theater":
        return "No Main Table"
    if seating_style == "Training":
        return "Modular Training Tables"
    if width_m > 0 and width_m < MIN_TABLE_WIDTH_RECOMMENDATION_M:
        return "Oval / Boat-Shaped"
    return "Rectangular"


def _recommend_table_package(room: Dict[str, Any], warnings: List[str]) -> tuple[float | None, str]:
    seating_style = room.get("seating_style", "")
    width_m = _safe_float(room.get("width_m", 0))
    final_capacity = int(room.get("final_procurement_occupancy", 0) or 0)
    table_shape = _recommended_table_shape(width_m, seating_style)
    table_length = _table_length_for_capacity(final_capacity)

    if table_shape == "Oval / Boat-Shaped":
        warnings.append("Room width is below 3.0 m; oval or boat-shaped tables are recommended.")

    if seating_style in TABLE_DEPTH_BY_STYLE_M and width_m > 0:
        minimum_width = TABLE_DEPTH_BY_STYLE_M[seating_style] + (CHAIR_CLEARANCE_M * 2)
        if width_m < minimum_width:
            warnings.append("Recommended table size may not fit comfortably within the room width.")

    return table_length, table_shape


def _build_procurement_preview(room: Dict[str, Any]) -> List[Dict[str, Any]]:
    final_capacity = int(room.get("final_procurement_occupancy", 0) or 0)
    if final_capacity <= 0:
        return []

    room_name = room.get("room_name", "Conference Room")
    room_code = room.get("room_code", "")
    room_type = room.get("room_type", "")
    seating_style = room.get("seating_style", "")
    table_length = room.get("recommended_table_length_m")
    table_shape = room.get("recommended_table_shape", "")
    basis = f"Final practical occupancy: {final_capacity}"
    notes = room.get("notes", "")

    def item(category: str, name: str, qty: int, unit: str = "pcs", item_notes: str = "") -> Dict[str, Any]:
        return {
            "Category": category,
            "Item": name,
            "Conference Room": room_name,
            "Room Code": room_code,
            "Room Type": room_type,
            "Seating Style": seating_style,
            "Qty per Room": qty,
            "Total Qty": qty,
            "Unit": unit,
            "Calculation Basis": basis,
            "Notes": item_notes or notes,
        }

    items: List[Dict[str, Any]] = []

    if seating_style == "Executive Boardroom":
        items.append(item("Conference Seating", "Boardroom Chair", final_capacity))
    elif seating_style == "Training":
        items.append(item("Conference Seating", "Training Chair", final_capacity))
        items.append(item("Conference Tables", "Training Desk", final_capacity))
    else:
        items.append(item("Conference Seating", "Conference Chair", final_capacity))

    if seating_style in {"Executive Boardroom", "Standard Meeting", "Huddle / Small Room"}:
        if final_capacity <= 12:
            table_name = f"Meeting Table ({table_length:.1f} m)" if table_length else "Meeting Table"
            table_note = f"{table_shape} shape recommended." if table_shape else ""
            items.append(item("Conference Tables", table_name, 1, item_notes=table_note))
        else:
            modular_count = max(1, math.ceil(final_capacity / 6))
            table_note = f"{table_shape} modular layout recommended." if table_shape else ""
            items.append(item("Conference Tables", "Modular Meeting Table", modular_count, item_notes=table_note))

    if seating_style == "Training":
        items.append(item("Presentation Furniture", "Presentation Table", 1))
        items.append(item("Presentation Furniture", "Speaker Podium", 1))
        items.append(item("Presentation Furniture", "Side Table", 1))
    elif seating_style == "Theater":
        items.append(item("Presentation Furniture", "Presentation Table", 1))
        items.append(item("Presentation Furniture", "Speaker Podium", 1))
        items.append(item("Presentation Furniture", "Side Table", max(1, math.ceil(final_capacity / 20))))
    else:
        items.append(item("Presentation Furniture", "Presentation Table", 1))
        items.append(item("Presentation Furniture", "Side Table", max(1, math.ceil(final_capacity / 10))))
        if seating_style == "Standard Meeting" or room_type in {"Conference Room", "Training Room", "Ballroom Meeting Section"}:
            items.append(item("Presentation Furniture", "Speaker Podium", 1))

    if room_type in {"Conference Room", "Meeting Room", "Training Room", "Ballroom Meeting Section"}:
        items.append(item("Meeting Accessories", "Flip Chart & Stand", 1))

    return items


def calculate_conference_room_plan(room: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    errors: List[str] = []

    room_name = _clean_text(room.get("room_name"))
    room_code = _clean_text(room.get("room_code"))
    room_type = _normalize_room_type(room.get("room_type", ""))
    seating_style = _normalize_seating_style(room.get("seating_style", ""))
    length_m = _safe_float(room.get("length_m", 0))
    width_m = _safe_float(room.get("width_m", 0))
    total_area_input = _safe_float(room.get("total_area_m2", 0))
    total_area_override = bool(room.get("total_area_override", False))
    non_usable_area_m2 = _round_area(_safe_float(room.get("non_usable_area_m2", 0)))
    notes = _clean_text(room.get("notes"))

    total_area_m2, auto_total_area_m2 = _infer_total_area(length_m, width_m, total_area_input, total_area_override)
    usable_area_m2 = _round_area(total_area_m2 - non_usable_area_m2)

    if not room_name:
        errors.append("Room name is required.")
    if not seating_style:
        errors.append("Seating style is required.")
    if not room_type:
        errors.append("Room type is required.")
    if total_area_m2 <= 0:
        errors.append("Enter either total area or both length and width.")
    if non_usable_area_m2 > total_area_m2 > 0:
        errors.append("Non-usable area cannot exceed total area.")
    if total_area_m2 > 0 and usable_area_m2 <= 0:
        errors.append("Usable area must be greater than zero.")

    default_factor = DEFAULT_AREA_PER_PERSON.get(seating_style, 0)
    theoretical_occupancy = math.floor(usable_area_m2 / default_factor) if default_factor and usable_area_m2 > 0 else 0
    practical_limit = _calculate_practical_limit(length_m, width_m, seating_style) if seating_style else None
    practical_occupancy = theoretical_occupancy if practical_limit is None else min(theoretical_occupancy, max(practical_limit, 0))
    final_procurement_occupancy = max(practical_occupancy, 0)

    if length_m <= 0 or width_m <= 0:
        warnings.append("Practical layout validation is more accurate when both length and width are entered.")
    if min(length_m, width_m) > 0 and min(length_m, width_m) < ACCESSIBLE_ZONE_M:
        warnings.append("Accessibility turning clearance of 1.5 m cannot be maintained in the current room dimensions.")
    if theoretical_occupancy <= 0 and usable_area_m2 > 0 and not errors:
        warnings.append("Room is too small for the selected seating style.")
    if practical_limit is not None and practical_limit < theoretical_occupancy:
        warnings.append("Procurement quantity has been reduced because of layout limitations and clearance rules.")

    recommended_table_length_m, recommended_table_shape = _recommend_table_package(
        {
            "seating_style": seating_style,
            "width_m": width_m,
            "final_procurement_occupancy": final_procurement_occupancy,
        },
        warnings,
    )

    room_plan = {
        "room_name": room_name,
        "room_code": room_code,
        "room_type": room_type,
        "seating_style": seating_style,
        "length_m": _round_area(length_m),
        "width_m": _round_area(width_m),
        "total_area_override": total_area_override,
        "auto_total_area_m2": auto_total_area_m2,
        "total_area_m2": total_area_m2,
        "non_usable_area_m2": non_usable_area_m2,
        "usable_area_m2": usable_area_m2,
        "default_area_per_person_m2": default_factor,
        "theoretical_occupancy": max(theoretical_occupancy, 0),
        "practical_occupancy": max(practical_occupancy, 0),
        "final_procurement_occupancy": final_procurement_occupancy,
        "recommended_table_length_m": recommended_table_length_m,
        "recommended_table_shape": recommended_table_shape,
        "notes": notes,
        "warnings": warnings,
        "errors": errors,
    }
    room_plan["procurement_preview"] = _build_procurement_preview(room_plan)
    return room_plan


def build_conference_procurement_items(conference_rooms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for room in conference_rooms or []:
        plan = calculate_conference_room_plan(room)
        if plan.get("errors"):
            continue
        items.extend(plan.get("procurement_preview", []))
    return items
