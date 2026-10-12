"""Independent analytic checks for the external numerical tools."""

import math
import unittest

from forge1.engineering import (
    EngineeringError, Quantity, axial_stress, check_dimensional_equation,
    convert_units, dc_motor, execute_tool, parse_unit, quadratic_roots,
    second_order_step, series_rlc, thermal_expansion, tool_catalog,
)


def q(value, unit):
    return {"value": value, "unit": unit}


class UnitTests(unittest.TestCase):
    def test_conversion_and_derived_dimensions(self):
        self.assertAlmostEqual(convert_units(2.5, "kN", "N"), 2500)
        self.assertAlmostEqual(convert_units(1, "MPa", "N/mm^2"), 1)
        self.assertAlmostEqual(convert_units(60, "rpm", "rad/s"), 2 * math.pi)
        self.assertAlmostEqual(convert_units(20, "degC", "K"), 293.15)
        self.assertAlmostEqual(convert_units(50, "%", "1"), 0.5)
        self.assertEqual(parse_unit("kg*m/s^2").dimensions, parse_unit("N").dimensions)
        self.assertAlmostEqual(Quantity.from_value(1, "in").to("mm"), 25.4)

    def test_dimensions_are_not_physical_proof(self):
        self.assertTrue(check_dimensional_equation("N", "kg*m/s^2")["consistent"])
        self.assertFalse(check_dimensional_equation("N", "kg*m/s")["consistent"])
        # Torque and energy share SI dimensions: caller must preserve semantics.
        self.assertTrue(check_dimensional_equation("N*m", "J")["consistent"])

    def test_rejects_invalid_and_nonfinite_inputs(self):
        for unit in ("__import__('os')", "m + m", "m//s", "m^13", "m**2", "", "degC/s", "N/(m*s)"):
            with self.subTest(unit=unit), self.assertRaises(EngineeringError):
                parse_unit(unit)
        for value in (True, "1", float("nan"), float("inf"), 10 ** 400):
            with self.subTest(value=type(value)), self.assertRaises(EngineeringError):
                convert_units(value, "m", "mm")
        with self.assertRaises(EngineeringError):
            convert_units(1, "m", "s")
        with self.assertRaises(EngineeringError):
            convert_units(1, "Hz", "rad/s")
        with self.assertRaises(EngineeringError):
            convert_units(20, "degC", "delta_K")


class CalculatorTests(unittest.TestCase):
    def test_stress_and_factor_of_safety(self):
        result = axial_stress(force=q(20, "kN"), area=q(100, "mm^2"), allowable_strength=q(400, "MPa"))
        self.assertAlmostEqual(result["stress"]["value"], 200e6)
        self.assertAlmostEqual(result["factor_of_safety"]["value"], 2)
        zero = axial_stress(force=q(0, "N"), area=q(1, "m^2"), allowable_strength=q(1, "Pa"))
        self.assertIsNone(zero["factor_of_safety"])
        self.assertEqual(zero["factor_of_safety_status"], "unbounded_zero_load")

    def test_dc_motor_energy_balance(self):
        result = dc_motor(torque_constant=q(0.1, "N*m/A"), current=q(5, "A"),
                          angular_speed=q(100, "rad/s"), winding_resistance=q(2, "Ohm"))
        self.assertAlmostEqual(result["torque"]["value"], 0.5)
        self.assertAlmostEqual(result["mechanical_power"]["value"], 50)
        self.assertAlmostEqual(result["copper_loss"]["value"], 50)
        self.assertAlmostEqual(result["terminal_voltage"]["value"], 20)
        self.assertAlmostEqual(result["efficiency"]["value"], 0.5)
        self.assertAlmostEqual(result["terminal_voltage"]["value"] * 5,
                               result["mechanical_power"]["value"] + result["copper_loss"]["value"])

    def test_free_thermal_expansion_signed_and_affine(self):
        result = thermal_expansion(length=q(2, "m"), coefficient=q(12e-6, "1/K"), delta_temperature=q(-50, "delta_degC"))
        self.assertAlmostEqual(result["length_change"]["value"], -0.0012)
        self.assertAlmostEqual(result["final_length"]["value"], 1.9988)
        with self.assertRaises(EngineeringError):
            thermal_expansion(length=q(2, "m"), coefficient=q(12e-6, "1/K"), delta_temperature=q(50, "degC"))

    def test_second_order_analytic_landmarks(self):
        initial = second_order_step(natural_frequency=q(10, "rad/s"), damping_ratio=0.5, elapsed_time=q(0, "s"))
        self.assertAlmostEqual(initial["response"]["value"], 0)
        self.assertAlmostEqual(initial["overshoot"]["value"], 16.303353482158048)
        self.assertAlmostEqual(initial["settling_time_2pct_approx"]["value"], 0.8)
        peak = second_order_step(natural_frequency=q(10, "rad/s"), damping_ratio=0.5,
                                 elapsed_time=initial["peak_time"])
        self.assertAlmostEqual(peak["response"]["value"], 1 + initial["overshoot"]["value"] / 100)
        with self.assertRaises(EngineeringError):
            second_order_step(natural_frequency=q(10, "rad/s"), damping_ratio=1, elapsed_time=q(0, "s"))
        with self.assertRaises(EngineeringError):
            second_order_step(natural_frequency=q(10, "Hz"), damping_ratio=0.5, elapsed_time=q(0, "s"))

    def test_rlc_frequency_and_damping(self):
        result = series_rlc(resistance=q(10, "Ohm"), inductance=q(10, "mH"), capacitance=q(10, "uF"))
        self.assertAlmostEqual(result["natural_frequency"]["value"], 3162.277660168379)
        self.assertAlmostEqual(result["resonance_frequency"]["value"], 503.2921210448704)
        self.assertAlmostEqual(result["quality_factor"]["value"] * result["damping_ratio"]["value"], 0.5)

    def test_quadratic_handles_cancellation_and_degeneracy(self):
        roots = quadratic_roots(a=1, b=-1e8, c=1)["real_roots"]
        self.assertAlmostEqual(roots[0], 1e-8, delta=1e-22)
        self.assertAlmostEqual(roots[0] * roots[1], 1)
        self.assertEqual(quadratic_roots(a=1, b=0, c=0)["real_roots"], [0])
        self.assertEqual(quadratic_roots(a=1, b=0, c=1)["real_roots"], [])
        with self.assertRaises(EngineeringError):
            quadratic_roots(a=0, b=0, c=0)

    def test_tool_boundary_refuses_missing_unknown_and_wrong_dimension(self):
        self.assertIn("dc_motor", tool_catalog())
        result = execute_tool("convert_units", {"value": 1, "from_unit": "m", "to_unit": "mm"})
        self.assertEqual(result["result"], 1000)
        self.assertEqual(result["provenance"], "external_deterministic_tool")
        for name, arguments in [
            ("axial_stress", {"force": q(1, "N")}),
            ("exec", {"code": "print('unsafe')"}),
            ("convert_units", {"value": 1, "from_unit": "m", "to_unit": "mm", "extra": 1}),
            ("axial_stress", {"force": q(1, "N"), "area": q(1, "m"), "allowable_strength": q(1, "Pa")}),
            ("axial_stress", {"force": q(1, "N"), "area": q(0, "m^2"), "allowable_strength": q(1, "Pa")}),
        ]:
            with self.subTest(name=name, arguments=arguments), self.assertRaises(EngineeringError):
                execute_tool(name, arguments)


if __name__ == "__main__":
    unittest.main()
