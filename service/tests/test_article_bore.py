import unittest
from types import SimpleNamespace
from unittest.mock import patch

from nx.variant import _edit_parameters, _values


VALUES = dict(DT=193.7, FA=380.0, DR=260.0, FR=2.0, FB=39.7, DS=25.4, DL=330.2)


def model():
    unit = SimpleNamespace(Tag=1)
    part = SimpleNamespace(Tag=2, PartUnits="mm")
    expressions = {}

    class Expression:
        Type = "Number"
        Units = unit
        OwningPart = part
        IsInterpartExpression = False
        IsNoUpdate = False

        def __init__(self, formula):
            self.formula = formula

        @property
        def Value(self):
            # Only the fixed arithmetic formulas below are evaluated here.
            names = {"DT": float(expressions["DT"].formula)}
            return eval(self.formula, {"__builtins__": {}}, names)

        def SetFormula(self, formula):
            self.formula = formula

    expressions.update({key: Expression(repr(value)) for key, value in VALUES.items()})
    expressions["MODEL_X_P13"] = Expression("300 - (DT - 180) / (2 * 0.1227845609)")
    expressions["MODEL_X_P14"] = Expression("-300 + (DT - 180) / (2 * 0.1227845609)")
    part.Expressions = SimpleNamespace(FindObject=expressions.__getitem__)
    part.UnitCollection = SimpleNamespace(FindObject=lambda name: unit)
    return part, expressions


class ArticleBoreTests(unittest.TestCase):
    def setUp(self):
        nxopen = SimpleNamespace(BasePart=SimpleNamespace(Units=SimpleNamespace(Millimeters="mm")))
        self.patch = patch.dict("sys.modules", {"NXOpen": nxopen})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_straight_bore_has_exact_radius_and_nonzero_segments(self):
        part, expressions = model()
        _edit_parameters(part, {**VALUES, "DT": 180.0})
        radius = expressions["DT"].Value / 2
        points = [(300, radius), (expressions["MODEL_X_P13"].Value, 90),
                  (expressions["MODEL_X_P14"].Value, 90), (-300, radius)]
        self.assertTrue(all(y == 90 for x, y in points))
        lengths = [a[0] - b[0] for a, b in zip(points, points[1:])]
        self.assertTrue(all(length > 0 for length in lengths))
        self.assertAlmostEqual(sum(lengths), 600)

    def test_larger_bore_keeps_parametric_inlet_lengths(self):
        part, expressions = model()
        _edit_parameters(part, {**VALUES, "DT": 202.7})
        length = (202.7 - 180) / (2 * 0.1227845609)
        self.assertAlmostEqual(expressions["MODEL_X_P13"].Value, 300 - length)
        self.assertAlmostEqual(expressions["MODEL_X_P14"].Value, -300 + length)

    def test_article_range_includes_180_but_not_smaller_bores(self):
        self.assertEqual(_values({"expressions": {**VALUES, "DT": 180}})["DT"], 180)
        with self.assertRaisesRegex(ValueError, "at least 180"):
            _values({"expressions": {**VALUES, "DT": 179.9}})


if __name__ == "__main__":
    unittest.main()
