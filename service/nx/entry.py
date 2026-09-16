"""Single journal entry; its request/result paths are supplied by nx_runner."""

import json
import os
from pathlib import Path
import sys
import traceback


# NX's journal runner does not necessarily add the project root to sys.path.
sys.path = [str(Path(__file__).resolve().parents[1]), *sys.path]


def dispatch(request):
    stage = request["stage"]
    if stage == "part":
        from nx.build_part import build_part
        return build_part(request)
    if stage == "structure":
        from nx.build_structure import build_structure
        return build_structure(request)
    if stage == "setup":
        from nx.build_setup import build_setup
        return build_setup(request)
    if stage == "clone":
        from nx.variant import clone_article
        return clone_article(request)
    if stage == "update":
        from nx.variant import update_article
        return update_article(request)
    if stage == "refresh":
        from nx.build_setup import refresh_setup
        return refresh_setup(request)
    if stage == "cam":
        from nx.cam import regenerate_toolpaths
        return regenerate_toolpaths(request)
    if stage == "post":
        from nx.post import post_article
        return post_article(request)
    if stage == "simulation":
        from nx.simulation import simulate_article
        return simulate_article(request)
    raise ValueError(f"Unknown NX stage: {stage}")


def main():
    result_file = Path(os.environ["HEERBAART_NX_RESULT"])
    try:
        request = json.loads(Path(os.environ["HEERBAART_NX_REQUEST"]).read_text(encoding="utf-8"))
        output = dispatch(request)
        result_file.write_text(json.dumps({"ok": True, "output": output}, indent=2), encoding="utf-8")
    except Exception as error:
        result_file.write_text(json.dumps({"ok": False, "error": str(error)}, indent=2), encoding="utf-8")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
