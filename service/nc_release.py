"""Release only the exact NC file that completed external simulation."""

import hashlib
import json


def nc_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invalidate_release(item_dir):
    (item_dir / "simulation.json").unlink(missing_ok=True)


def released_nc(item_dir, article_number):
    nc = item_dir / f"{article_number}-SETUP.min"
    try:
        result = json.loads((item_dir / "simulation.json").read_text(encoding="utf-8"))
        if (result.get("passed") is True and result.get("mode") == "external_nc"
                and result.get("completed") is True and result.get("nc_sha256") == nc_hash(nc)):
            return nc
    except (OSError, ValueError, TypeError):
        pass
    return None
