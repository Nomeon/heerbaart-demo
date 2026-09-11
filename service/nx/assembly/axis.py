"""Active builders extracted from heerbaart_poc/tools/axis.py."""

AXIS_VECTORS = {"XC": (1.0, 0.0, 0.0), "YC": (0.0, 1.0, 0.0), "ZC": (0.0, 0.0, 1.0)}

def axis_vector(axis_name):
    axis_name = str(axis_name).upper()

    if axis_name not in AXIS_VECTORS:
        supported = ", ".join(sorted(AXIS_VECTORS))
        raise ValueError(f"Unsupported centerline axis: {axis_name}. Use one of: {supported}")

    return AXIS_VECTORS[axis_name]



def axis_name(axis_name):
    axis_name = str(axis_name).upper()
    axis_vector(axis_name)
    return axis_name



def perpendicular_axis_vector(axis):
    if axis == AXIS_VECTORS["XC"]:
        return AXIS_VECTORS["ZC"]

    return AXIS_VECTORS["XC"]
