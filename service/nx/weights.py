"""Read per-piece masses from the saved product and revolved blank bodies."""

import json
from pathlib import Path

from nx.variant import _fresh_session, _load_status


def body_mass_kg(part, body):
    units = [part.UnitCollection.FindObject(name) for name in (
        "SquareMilliMeter", "CubicMilliMeter", "Kilogram", "MilliMeter", "Newton",
    )]
    measurement = part.MeasureManager.NewMassProperties(units, 0.999, [body])
    try:
        return measurement.Mass
    finally:
        measurement.Dispose()


def measure_article_weights(request):
    session = _fresh_session()
    item_dir = Path(request["item_dir"])
    weights = {}
    for suffix, field in (("PART", "product_kg"), ("BLANK", "stock_kg")):
        part, status = session.Parts.OpenBaseDisplay(str(item_dir / f"{request['name']}_{suffix}.prt"))
        _load_status(status, f"Open {suffix} for weight measurement")
        body = (next(body for body in part.Bodies if body.IsSolidBody) if suffix == "PART"
                else next(body for body in part.Bodies if body.Name == "BLANK_REVOLVE_OUTLINE_BODY"))
        weights[field] = body_mass_kg(part, body)
        print(f"Weight {suffix}: {weights[field]:.9f} kg per piece ({body.Name or 'product solid'})", flush=True)
    (item_dir / "weights.json").write_text(json.dumps(weights, indent=2), encoding="utf-8")
    return {"weights": weights}
