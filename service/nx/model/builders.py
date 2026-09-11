"""Fixed STAP1-11 construction order, without launchers or source-project state."""

from . import common, dimensions, patterns
from . import step1_revolve as step1
from . import step2_flange_holes as step2
from . import step3_flats as step3
from . import step4_flange_threads as step4
from . import step5_npt as step5
from . import step6_central_m8 as step6
from . import step7_spotface_m8 as step7
from . import step8_diagonal_holes as step8
from . import step9_side_holes as step9
from . import step10_finishing as step10
from . import step11_center_ports as step11


def revolve(part, threads):
    names = (
        "LEFT_FACE_LAND", "LEFT_FACE_TO_FLANGE", "LEFT_FLANGE_BODY",
        "LEFT_FLANGE_TO_DR", "LEFT_45_DEGREE_TRANSITION", "CENTER_BODY",
        "RIGHT_45_DEGREE_TRANSITION", "RIGHT_DR_TO_FLANGE", "RIGHT_FLANGE_BODY",
        "RIGHT_FLANGE_TO_FACE", "RIGHT_FACE_LAND", "RIGHT_FACE_TO_INLET",
        "RIGHT_7DEG_INLET", "BORE", "LEFT_7DEG_INLET", "LEFT_INLET_TO_FACE",
    )
    profile = {
        "points": [{"name": f"P{index:02d}"} for index in range(17)],
        "segments": [{"name": name} for name in names],
    }
    sketch = step1.create_sketch(part, "SKETCH_STAP1_REVOLVE_OUTLINE")
    curves = step1.create_profile(part, sketch, {"profile": profile})
    step1.create_revolve(part, sketch, curves)


def flange_holes(part, threads):
    body = common.solid_body(part)
    seeds = []
    for side in ("LEFT", "RIGHT"):
        seed = step2.create_general_hole(part, body, side)
        step2.create_circular_pattern(part, seed, side)
        seeds.append(seed)
    common.update(step2.STEP_NAME)
    step2.verify_chamfers(part, seeds, float(part.Expressions.FindObject("DS").Value))


def flats(part, threads):
    step3.build(part)


def flange_threads(part, threads):
    entry = threads["HB M12 x 1.75"]
    contract = {"radial_thread_holes": {"hb_standard": entry, "thread_callout": "M12"}}
    positions = [
        {
            "position_id": name, "angle_deg": angle,
            "angle_expression": "STEP4_THREAD_ANGLE_" + name,
            "y_expression": "STEP4_THREAD_" + name + "_Y",
            "z_expression": "STEP4_THREAD_" + name + "_Z",
        }
        for name, angle in (("RIGHT", 0), ("UPPER_LEFT", 150), ("LOWER_LEFT", 210))
    ]
    body = common.solid_body(part)
    features = [
        step4.create_threaded_hole(part, body, side, position, contract)
        for side in ("LEFT", "RIGHT") for position in positions
    ]
    common.update(step4.STEP_NAME)
    for feature in features:
        common.verify_thread(part, feature, entry, 24, 30, end_chamfer=True)


def npt_ports(part, threads):
    entry = threads["HB 1/2-NPT"]
    contract = {"npt_holes": {"hb_standard": entry}}
    positions = [
        {"position_id": side + "_NPT", "x_expression": "STEP5_" + side + "_NPT_X",
         "y_expression": "STEP5_NPT_Y", "z_expression": "STEP5_NPT_ENTRY_Z"}
        for side in ("LEFT", "RIGHT")
    ]
    body = common.solid_body(part)
    features = [step5.create_npt_hole(part, body, position, contract) for position in positions]
    for position in positions:
        step5.create_continuous_hole(part, body, position, contract)
    common.update(step5.STEP_NAME)
    for feature in features:
        common.verify_thread(part, feature, entry, 15, 22)


def central_m8(part, threads):
    entry = threads["HB M8 x 1.25"]
    contract = {"m8_holes": {"hb_standard": entry}}
    positions = [
        {"position_id": f"M8_{x}_X_{y}_Y", "x_expression": f"STEP6_M8_{x}_X",
         "y_expression": f"STEP6_M8_{y}_Y", "z_expression": "STEP6_M8_ENTRY_Z"}
        for y in ("NEG", "POS") for x in ("NEG", "POS")
    ]
    body = common.solid_body(part)
    created = [step6.create_m8_hole(part, body, position, contract) for position in positions]
    common.update(step6.STEP_NAME)
    for feature, _point in created:
        common.verify_thread(part, feature, entry, 13, 15)


def spotface_m8(part, threads):
    entry = threads["HB M8 x 1.25"]
    contract = {"m8_holes": {"hb_standard": entry}}
    body = common.solid_body(part)
    features = []
    for position in patterns.step7_positions():
        probe = step7.create_probe_point(part, position)
        step7.create_spotface(part, body, probe, position, contract)
        point = step7.create_entry_point(part, position)
        features.append(step7.create_m8_hole(part, body, point, position, contract))
    common.update(step7.STEP_NAME)
    for feature in features:
        common.verify_thread(part, feature, entry, 13, 15)


def diagonal_holes(part, threads):
    entry = threads["HB M8 x 1.25"]
    contract = {"diagonal_holes": {"m8": {"hb_standard": entry}}}
    positions = step8.create_coordinate_expressions(part, [
        {**position, "entry_formulas": patterns.diagonal_formulas(position, probe=False),
         "probe_formulas": patterns.diagonal_formulas(position, probe=True)}
        for position in patterns.step8_positions()
    ])
    body = common.solid_body(part)
    features = []
    for position in positions:
        probe = step8.create_point(part, position, probe=True)
        point = step8.create_point(part, position, probe=False)
        if position["hole_type"] == "H9":
            step8.create_h9_hole(part, body, probe, position, contract)
        else:
            features.append(step8.create_m8_hole(part, body, point, position, contract))
    common.update(step8.STEP_NAME)
    for feature in features:
        common.verify_thread(part, feature, entry, 13, 15)


def side_holes(part, threads):
    entry = threads["HB M8 x 1.25"]
    contract = {"side_holes": {"m8": {"hb_standard": entry}}}
    positions = step9.create_coordinate_expressions(part, [
        {**position,
         "entry_formulas": {
             "x": position["x_expression"], "z": position["tangent_offset_expression"],
             "y": "STEP3_SIDE_FLAT_OFFSET" if position["plane_side"] == "POS_Y" else "-STEP3_SIDE_FLAT_OFFSET",
         },
         "probe_formulas": {
             "x": position["x_expression"], "z": position["tangent_offset_expression"],
             "y": "STEP3_SIDE_FLAT_OFFSET + STEP9_SIDE_PROJECTION_MARGIN" if position["plane_side"] == "POS_Y" else "-STEP3_SIDE_FLAT_OFFSET - STEP9_SIDE_PROJECTION_MARGIN",
         }}
        for position in patterns.step9_positions()
    ])
    body = common.solid_body(part)
    features = []
    for position in positions:
        point = step9.create_point(part, position, probe=False)
        if position["hole_type"] == "H9":
            probe = step9.create_point(part, position, probe=True)
            step9.create_h9_hole(part, body, probe, position, contract)
        else:
            features.append(step9.create_m8_hole(part, body, point, position, contract))
    common.update(step9.STEP_NAME)
    for feature in features:
        common.verify_thread(part, feature, entry, 13, 15)


def finishing(part, threads):
    step10.build(part)
    common.update(step10.STEP_NAME)
    step10.verify(part)


def center_ports(part, threads):
    entries = {"M12": threads["HB M12 x 1.75"], "NPT": threads["HB 1/4-NPT"]}
    d4 = step11.create_d4(part)
    features = {port: step11.create_thread(part, port, entry) for port, entry in entries.items()}
    common.update(step11.STEP_NAME)
    common.verify_thread(part, features["M12"], entries["M12"], 9, 14)
    common.verify_thread(part, features["NPT"], entries["NPT"], 10, 15)
    step11.verify(part, features, d4, {"hb_table": {"entries": entries}})


STAGES = (
    (step1.STEP_NAME, revolve, ()),
    (step2.STEP_NAME, flange_holes, dimensions.STEP2_EXPRESSIONS),
    (step3.STEP_NAME, flats, dimensions.STEP3_EXPRESSIONS),
    (step4.STEP_NAME, flange_threads, dimensions.STEP4_EXPRESSIONS),
    (step5.STEP_NAME, npt_ports, dimensions.STEP5_EXPRESSIONS),
    (step6.STEP_NAME, central_m8, dimensions.STEP6_EXPRESSIONS),
    (step7.STEP_NAME, spotface_m8, dimensions.STEP7_EXPRESSIONS),
    (step8.STEP_NAME, diagonal_holes, dimensions.STEP8_EXPRESSIONS),
    (step9.STEP_NAME, side_holes, dimensions.STEP9_EXPRESSIONS),
    (step10.STEP_NAME, finishing, dimensions.STEP10_EXPRESSIONS),
    (step11.STEP_NAME, center_ports, dimensions.STEP11_EXPRESSIONS),
)
