"""Explicit destinations shared by the structure and workholding builders."""

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class BuildPaths:
    item_dir: Path
    name: str
    work_dir: Path
    custom_dir: Path

    def part(self, kind):
        if kind not in {"PART", "ASSY", "CAD4CAM", "BLANK", "SETUP"}:
            raise ValueError(f"Unknown part kind: {kind}")
        return self.item_dir / f"{self.name}_{kind}.prt"

    @property
    def template(self):
        return (
            self.custom_dir / "MACH" / "resource" / "template_part" / "metric"
            / "template_part_setup_NX2512.prt"
        )

    @property
    def device_root(self):
        return self.custom_dir / "MACH" / "resource" / "library" / "device" / "graphics"


def request_paths(request):
    if not isinstance(request, dict):
        raise TypeError("NX request must be a dictionary")
    name = request.get("name", "BASELINE")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", name):
        raise ValueError("name must be a plain item name without a path or extension")
    values = []
    for key in ("item_dir", "work_dir", "custom_dir"):
        value = request.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be an absolute directory path")
        path = Path(value)
        if not path.is_absolute():
            raise ValueError(f"{key} must be absolute: {value}")
        values = [*values, path.resolve()]
    item_dir, work_dir, custom_dir = values
    if not item_dir.is_dir() or not custom_dir.is_dir():
        raise FileNotFoundError("item_dir and custom_dir must already exist")
    if item_dir == work_dir:
        raise ValueError("work_dir must be a separate scratch directory")
    if item_dir.is_relative_to(custom_dir) or work_dir.is_relative_to(custom_dir):
        raise ValueError("Output and scratch directories must not be inside the NX library")
    work_dir.mkdir(parents=True, exist_ok=True)
    return BuildPaths(item_dir, name, work_dir, custom_dir)
