"""Exact HB selections from elster_family/step4-9 and step11_center_ports."""

import hashlib
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def load_threads(custom_dir):
    path = Path(custom_dir) / "UGII" / "Modeling_standards" / "NX_Thread_Standard.xml"
    content = path.read_bytes()
    root = ET.fromstring(content)
    digest = hashlib.sha256(content).hexdigest()
    # Size, pitch, major/minor diameter, tap drill, and chamfer in native table units.
    reviewed = (
        ("HB M12 x 1.75", "Metric Coarse", "Metric", "0.75", "M Profile", "0", 1.75, 12.1, 10.072, 10.3, 140, 12.3),
        ("HB M8 x 1.25", "Metric Coarse", "Metric", "0.75", "M Profile", "0", 1.25, 8.1, 6.619, 6.9, 140, 8.3),
        ("HB 1/2-NPT", "Inch NPT", "Inch", "Standard", "NPT", "1", 0.0714, 0.77843, 0.7188, 0.7189, 118, 0.84),
        ("HB 1/4-NPT", "Inch NPT", "Inch", "Standard", "NPT", "1", 0.0556, 0.49163, 0.4375, 0.4376, 118, 0.54),
    )
    result = {}
    for size, standard, unit, engage, form, tapered, pitch, major, minor, tap, tip, chamfer in reviewed:
        matches = [entry for entry in root.findall("ThreadedHole") if entry.get("Size") == size]
        if len(matches) != 1:
            raise ValueError(f"HB table requires exactly one {size!r} entry; found {len(matches)}")
        entry = matches[0].attrib
        text_fields = {
            "Standard": standard, "Unit": unit, "RadialEngage": engage,
            "ThreadForm": form, "Tapered": tapered,
        }
        number_fields = {
            "Pitch": pitch, "MajorDiameter": major, "MinorDiameter": minor,
            "TapDrillDia": tap, "HoleTipAngle": tip, "Angle": 60,
            "StartChamferDiameter": chamfer, "EndChamferDiameter": chamfer,
            "StartChamferAngle": 45, "EndChamferAngle": 45,
        }
        for field, expected in text_fields.items():
            if entry.get(field) != expected:
                raise ValueError(f"{size}: HB field {field} differs from the reviewed entry")
        for field, expected in number_fields.items():
            try:
                actual = float(entry[field])
            except (KeyError, ValueError) as exc:
                raise ValueError(f"{size}: missing or invalid HB field {field}") from exc
            if not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-9):
                raise ValueError(f"{size}: HB field {field} is {actual}, expected {expected}")
        scale = 25.4 if unit == "Inch" else 1.0
        result = {**result, size: {
            "size": entry["Size"],
            "standard": entry["Standard"],
            "radial_engage": entry["RadialEngage"],
            "callout": entry.get("Callout", size),
            "tap_drill_diameter_mm": float(entry["TapDrillDia"]) * scale,
            "hole_tip_angle_deg": float(entry["HoleTipAngle"]),
            "start_chamfer_diameter_mm": float(entry["StartChamferDiameter"]) * scale,
            "end_chamfer_diameter_mm": float(entry["EndChamferDiameter"]) * scale,
            "start_chamfer_angle_deg": float(entry["StartChamferAngle"]),
            "end_chamfer_angle_deg": float(entry["EndChamferAngle"]),
            "thread_table": str(path),
            "table_sha256": digest,
        }}
    return result
