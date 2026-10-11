"""Regressions for schema, unit, sign and near-zero evaluator defects."""
import unittest
from .evaluate_answerability import _matches


class NumericOracleTests(unittest.TestCase):
    def test_units_and_quantity_schema_are_required(self):
        self.assertFalse(_matches({'value': 600, 'unit': 'banana'}, 600))
        self.assertFalse(_matches({'value': 600, 'unit': 'banana'}, {'value': 600, 'unit': 'Pa'}))
        self.assertFalse(_matches({'value': 600, 'unit': 'Pa', 'extra': 1}, {'value': 600, 'unit': 'Pa'}))
        self.assertFalse(_matches(600, {'value': 600, 'unit': 'Pa'}))
        self.assertTrue(_matches({'value': 600, 'unit': 'Pa'}, {'value': 600, 'unit': 'Pa'}))

    def test_tiny_nonzero_zero_sign_and_nonfinite(self):
        self.assertFalse(_matches({'value': 0, 'unit': 'm'}, {'value': 1e-200, 'unit': 'm'}))
        self.assertFalse(_matches(0, 1e-200))
        self.assertFalse(_matches(1e-200, 0))
        self.assertFalse(_matches(-1e-200, 1e-200))
        self.assertTrue(_matches(1e-200, 1e-200))
        self.assertTrue(_matches(5e-309, 5e-309))
        for value in [float('nan'), float('inf'), True]:
            self.assertFalse(_matches(value, 1))

    def test_recursive_lists_and_boolean_are_not_numbers(self):
        self.assertTrue(_matches([1.0, 2.0], [1, 2]))
        self.assertFalse(_matches([1, 2, 3], [1, 2]))
        self.assertFalse(_matches(True, 1))
        self.assertFalse(_matches(1, True))
        self.assertTrue(_matches(None, None))


if __name__ == '__main__':
    unittest.main(verbosity=2)
