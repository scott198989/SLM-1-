"""Independent analytic cases for transplanted engineering functions."""

import math, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forge_tools import engineering as e


def q(value, unit):
    return {"value": value, "unit": unit}


class IndependentEngineeringTests(unittest.TestCase):
    def test_motor_energy_balance(self):
        r = e.dc_motor(
            torque_constant=q(0.1, "N*m/A"),
            current=q(2, "A"),
            angular_speed=q(100, "rad/s"),
            winding_resistance=q(3, "Ohm"),
        )
        self.assertAlmostEqual(r["torque"]["value"], 0.2)
        self.assertAlmostEqual(r["terminal_voltage"]["value"], 16)
        self.assertAlmostEqual(r["mechanical_power"]["value"], 20)
        self.assertAlmostEqual(r["copper_loss"]["value"], 12)
        self.assertAlmostEqual(r["efficiency"]["value"], 20 / 32)

    def test_thermal_difference_and_absolute_temperature(self):
        r = e.thermal_expansion(
            length=q(2, "m"),
            coefficient=q(12e-6, "1/K"),
            delta_temperature=q(50, "delta_degC"),
        )
        self.assertAlmostEqual(r["length_change"]["value"], 0.0012)
        self.assertAlmostEqual(r["final_length"]["value"], 2.0012)
        self.assertAlmostEqual(e.convert_units(0, "degC", "K"), 273.15)
        with self.assertRaises(e.EngineeringError):
            e.thermal_expansion(
                length=q(2, "m"),
                coefficient=q(12e-6, "1/K"),
                delta_temperature=q(50, "degC"),
            )

    def test_rlc_from_reactance_balance(self):
        r = e.series_rlc(
            resistance=q(20, "Ohm"), inductance=q(0.01, "H"), capacitance=q(1e-6, "F")
        )
        omega = r["natural_frequency"]["value"]
        self.assertAlmostEqual(omega, 10000)
        self.assertAlmostEqual(omega * 0.01, 1 / (omega * 1e-6))
        self.assertAlmostEqual(r["quality_factor"]["value"], 5)
        self.assertAlmostEqual(r["damping_ratio"]["value"], 0.1)

    def test_step_initial_peak_and_steady_state(self):
        args = {"natural_frequency": q(10, "rad/s"), "damping_ratio": 0.5}
        initial = e.second_order_step(**args, elapsed_time=q(0, "s"))
        peak_time = math.pi / (5 * math.sqrt(3))
        peak = e.second_order_step(**args, elapsed_time=q(peak_time, "s"))
        late = e.second_order_step(**args, elapsed_time=q(100, "s"))
        self.assertAlmostEqual(initial["response"]["value"], 0)
        self.assertAlmostEqual(
            peak["response"]["value"], 1 + math.exp(-math.pi / math.sqrt(3))
        )
        self.assertAlmostEqual(late["response"]["value"], 1)
        with self.assertRaises(e.EngineeringError):
            e.second_order_step(
                natural_frequency=q(10, "Hz"), damping_ratio=0.5, elapsed_time=q(1, "s")
            )

    def test_zero_load_and_nonphysical_inputs(self):
        r = e.axial_stress(
            force=q(0, "N"), area=q(1, "m^2"), allowable_strength=q(1, "MPa")
        )
        self.assertIsNone(r["factor_of_safety"])
        self.assertEqual(r["factor_of_safety_status"], "unbounded_zero_load")
        with self.assertRaises(e.EngineeringError):
            e.axial_stress(
                force=q(1, "N"), area=q(0, "m^2"), allowable_strength=q(1, "MPa")
            )


if __name__ == "__main__":
    unittest.main()
