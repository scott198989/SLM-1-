"""Small, auditable engineering calculators with explicit SI dimensions.

This module is an external tool boundary, not learned model capability.  It never
executes generated Python, evaluates expressions, or silently invents inputs.
All units are case-sensitive; the parser accepts only registered units combined
with ``*``, ``/`` and integer powers (for example ``kg*m/s^2``).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping


class EngineeringError(ValueError):
    """Invalid, incomplete, dimensionally inconsistent or unsupported input."""


# SI dimension order: mass, length, time, current, temperature, amount, luminosity.
Dimensions = tuple[int, int, int, int, int, int, int]
DIMENSIONLESS: Dimensions = (0, 0, 0, 0, 0, 0, 0)


@dataclass(frozen=True)
class Unit:
    scale: float
    dimensions: Dimensions
    offset: float = 0.0


@dataclass(frozen=True)
class Quantity:
    """Finite physical quantity stored in SI; values retain no display unit."""

    si_value: float
    dimensions: Dimensions

    def __post_init__(self) -> None:
        _number(self.si_value, "quantity")

    @classmethod
    def from_value(cls, value: float, unit: str) -> Quantity:
        parsed = parse_unit(unit)
        return cls(_finite(_number(value, "value") * parsed.scale + parsed.offset), parsed.dimensions)

    def to(self, unit: str) -> float:
        parsed = parse_unit(unit)
        if self.dimensions != parsed.dimensions:
            raise EngineeringError(f"Dimensional mismatch: quantity cannot be expressed in {unit!r}.")
        return _finite((self.si_value - parsed.offset) / parsed.scale)


def _dim(mass: int = 0, length: int = 0, time: int = 0, current: int = 0,
         temperature: int = 0, amount: int = 0, luminosity: int = 0) -> Dimensions:
    return mass, length, time, current, temperature, amount, luminosity


_UNITS: dict[str, Unit] = {
    "1": Unit(1.0, DIMENSIONLESS), "%": Unit(0.01, DIMENSIONLESS),
    "kg": Unit(1.0, _dim(mass=1)), "g": Unit(1e-3, _dim(mass=1)),
    "m": Unit(1.0, _dim(length=1)), "mm": Unit(1e-3, _dim(length=1)),
    "cm": Unit(1e-2, _dim(length=1)), "km": Unit(1e3, _dim(length=1)),
    "in": Unit(0.0254, _dim(length=1)), "ft": Unit(0.3048, _dim(length=1)),
    "s": Unit(1.0, _dim(time=1)), "ms": Unit(1e-3, _dim(time=1)),
    "min": Unit(60.0, _dim(time=1)), "h": Unit(3600.0, _dim(time=1)),
    "A": Unit(1.0, _dim(current=1)), "mA": Unit(1e-3, _dim(current=1)),
    "K": Unit(1.0, _dim(temperature=1)), "degC": Unit(1.0, _dim(temperature=1), 273.15),
    "delta_K": Unit(1.0, _dim(temperature=1)),
    "delta_degC": Unit(1.0, _dim(temperature=1)),
    "mol": Unit(1.0, _dim(amount=1)), "cd": Unit(1.0, _dim(luminosity=1)),
    "rad": Unit(1.0, DIMENSIONLESS), "deg": Unit(math.pi / 180, DIMENSIONLESS),
    "Hz": Unit(1.0, _dim(time=-1)), "rpm": Unit(2 * math.pi / 60, _dim(time=-1)),
    "N": Unit(1.0, _dim(mass=1, length=1, time=-2)),
    "kN": Unit(1e3, _dim(mass=1, length=1, time=-2)),
    "Pa": Unit(1.0, _dim(mass=1, length=-1, time=-2)),
    "kPa": Unit(1e3, _dim(mass=1, length=-1, time=-2)),
    "MPa": Unit(1e6, _dim(mass=1, length=-1, time=-2)),
    "GPa": Unit(1e9, _dim(mass=1, length=-1, time=-2)),
    "J": Unit(1.0, _dim(mass=1, length=2, time=-2)),
    "kJ": Unit(1e3, _dim(mass=1, length=2, time=-2)),
    "W": Unit(1.0, _dim(mass=1, length=2, time=-3)),
    "kW": Unit(1e3, _dim(mass=1, length=2, time=-3)),
    "V": Unit(1.0, _dim(mass=1, length=2, time=-3, current=-1)),
    "mV": Unit(1e-3, _dim(mass=1, length=2, time=-3, current=-1)),
    "Ohm": Unit(1.0, _dim(mass=1, length=2, time=-3, current=-2)),
    "ohm": Unit(1.0, _dim(mass=1, length=2, time=-3, current=-2)),
    "kohm": Unit(1e3, _dim(mass=1, length=2, time=-3, current=-2)),
    "H": Unit(1.0, _dim(mass=1, length=2, time=-2, current=-2)),
    "mH": Unit(1e-3, _dim(mass=1, length=2, time=-2, current=-2)),
    "uH": Unit(1e-6, _dim(mass=1, length=2, time=-2, current=-2)),
    "F": Unit(1.0, _dim(mass=-1, length=-2, time=4, current=2)),
    "uF": Unit(1e-6, _dim(mass=-1, length=-2, time=4, current=2)),
    "nF": Unit(1e-9, _dim(mass=-1, length=-2, time=4, current=2)),
    "C": Unit(1.0, _dim(time=1, current=1)),
}
_TERM = re.compile(r"([A-Za-z_%]+|1)(?:\^(-?\d+))?\Z")


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EngineeringError(f"{name} must be a finite number, not {type(value).__name__}.")
    try:
        return _finite(float(value))
    except (ValueError, OverflowError) as exc:
        raise EngineeringError(f"{name} must be a finite number.") from exc


def _finite(value: float) -> float:
    if not math.isfinite(value):
        raise EngineeringError("Input or computation is outside the finite numerical range.")
    return value


def parse_unit(expression: str) -> Unit:
    """Parse a restricted unit expression without evaluating arbitrary code.

    Operators associate left-to-right, so ``N/m*s`` means ``(N/m)*s``.
    Write ``N/m/s`` or ``N/(m*s)`` in mathematics; only the former is accepted
    here because parentheses are deliberately outside this tiny grammar.
    """
    if not isinstance(expression, str) or not expression or len(expression) > 128:
        raise EngineeringError("A nonempty unit string of at most 128 characters is required.")
    expression = expression.strip()
    if expression in _UNITS:
        return _UNITS[expression]
    if any(char.isspace() for char in expression):
        raise EngineeringError("Whitespace is not supported inside unit expressions.")
    pieces = re.split(r"([*/])", expression)
    scale = 1.0
    dimensions = [0] * 7
    for index in range(0, len(pieces), 2):
        term = _TERM.fullmatch(pieces[index])
        if not term or term.group(1) not in _UNITS:
            raise EngineeringError(f"Unsupported unit expression: {expression!r}.")
        unit = _UNITS[term.group(1)]
        if unit.offset:
            raise EngineeringError("Affine units such as degC may only appear alone; use delta_degC for differences.")
        power = int(term.group(2) or "1")
        if abs(power) > 12:
            raise EngineeringError("Unit powers must lie between -12 and 12.")
        if index and pieces[index - 1] == "/":
            power = -power
        try:
            scale *= unit.scale ** power
        except (OverflowError, ZeroDivisionError) as exc:
            raise EngineeringError("Unit scale is outside the finite numerical range.") from exc
        dimensions = [x + power * y for x, y in zip(dimensions, unit.dimensions)]
    if not math.isfinite(scale) or scale <= 0:
        raise EngineeringError("Unit scale is outside the finite numerical range.")
    return Unit(scale, tuple(dimensions))  # type: ignore[arg-type]


def convert_units(value: float, from_unit: str, to_unit: str) -> float:
    parse_unit(from_unit)
    parse_unit(to_unit)
    # Frequency and angular frequency share SI dimensions but differ physically.
    angular = {"rad/s", "rpm", "deg/s"}
    if ((from_unit == "Hz" and to_unit in angular)
            or (to_unit == "Hz" and from_unit in angular)):
        raise EngineeringError("Hz counts cycles; angular frequency requires an explicit 2*pi relationship, not a unit-only conversion.")
    intervals = {"delta_K", "delta_degC"}
    if ((from_unit == "degC" and to_unit in intervals)
            or (to_unit == "degC" and from_unit in intervals)):
        raise EngineeringError("Absolute temperature and temperature interval cannot be interconverted.")
    return Quantity.from_value(value, from_unit).to(to_unit)


def check_dimensional_equation(lhs_unit: str, rhs_unit: str) -> dict[str, Any]:
    """Check dimensional equivalence only, not algebra or physical validity."""
    lhs, rhs = parse_unit(lhs_unit), parse_unit(rhs_unit)
    return {"consistent": lhs.dimensions == rhs.dimensions,
            "lhs_dimensions": list(lhs.dimensions), "rhs_dimensions": list(rhs.dimensions),
            "limitation": "Equal dimensions do not establish a valid physical equation."}


def _quantity(value: Any, expected_unit: str, name: str, *, positive: bool = False,
              nonnegative: bool = False, difference: bool = False) -> float:
    if not isinstance(value, Mapping) or set(value) != {"value", "unit"}:
        raise EngineeringError(f"{name} requires exactly {{'value': number, 'unit': string}}.")
    unit = parse_unit(value["unit"])
    if expected_unit == "rad/s" and value["unit"] not in {"rad/s", "rpm", "deg/s"}:
        raise EngineeringError(f"{name} is angular speed/frequency; use rad/s, deg/s or rpm explicitly.")
    if difference and unit.offset:
        raise EngineeringError(f"{name} is a temperature difference; use delta_degC, delta_K or K.")
    result = Quantity.from_value(value["value"], value["unit"]).to(expected_unit)
    if positive and result <= 0:
        raise EngineeringError(f"{name} must be greater than zero.")
    if nonnegative and result < 0:
        raise EngineeringError(f"{name} must be nonnegative.")
    return result


def _result(value: float, unit: str) -> dict[str, Any]:
    return {"value": _finite(value), "unit": unit}


def axial_stress(*, force: Mapping[str, Any], area: Mapping[str, Any],
                 allowable_strength: Mapping[str, Any]) -> dict[str, Any]:
    """Uniform uniaxial tensile stress and strength/stress safety factor."""
    f = _quantity(force, "N", "force", nonnegative=True)
    a = _quantity(area, "m^2", "area", positive=True)
    strength = _quantity(allowable_strength, "Pa", "allowable_strength", positive=True)
    stress = _finite(f / a)
    if f != 0 and stress == 0:
        raise EngineeringError("Stress underflows floating-point precision; it cannot be treated as zero load.")
    return {"stress": _result(stress, "Pa"),
            "factor_of_safety": _result(strength / stress, "1") if stress else None,
            "factor_of_safety_status": "finite" if stress else "unbounded_zero_load",
            "assumptions": ["uniform_axial_tension", "static_loading", "no_stress_concentration"],
            "limitations": ["Does not assess buckling, fatigue, fracture, joints or regulatory acceptance."]}


def dc_motor(*, torque_constant: Mapping[str, Any], current: Mapping[str, Any],
             angular_speed: Mapping[str, Any], winding_resistance: Mapping[str, Any]) -> dict[str, Any]:
    """Ideal SI permanent-magnet DC motor, with winding copper loss only."""
    kt = _quantity(torque_constant, "N*m/A", "torque_constant", positive=True)
    i = _quantity(current, "A", "current", nonnegative=True)
    speed = _quantity(angular_speed, "rad/s", "angular_speed", nonnegative=True)
    resistance = _quantity(winding_resistance, "Ohm", "winding_resistance", nonnegative=True)
    torque = _finite(kt * i)
    power = _finite(torque * speed)
    loss = _finite(i * i * resistance)
    input_power = _finite(power + loss)
    return {"torque": _result(torque, "N*m"), "mechanical_power": _result(power, "W"),
            "copper_loss": _result(loss, "W"),
            "terminal_voltage": _result(kt * speed + i * resistance, "V"),
            "efficiency": _result(power / input_power, "1") if input_power else None,
            "assumptions": ["steady_state", "si_torque_constant_equals_back_emf_constant", "no_mechanical_or_iron_losses"],
            "limitations": ["Not a transient, thermal-limit, saturation or drive-inverter model."]}


def thermal_expansion(*, length: Mapping[str, Any], coefficient: Mapping[str, Any],
                      delta_temperature: Mapping[str, Any]) -> dict[str, Any]:
    """Free one-dimensional expansion with a constant linear coefficient."""
    initial = _quantity(length, "m", "length", positive=True)
    alpha = _quantity(coefficient, "1/K", "coefficient")
    delta_t = _quantity(delta_temperature, "K", "delta_temperature", difference=True)
    change = _finite(initial * alpha * delta_t)
    final = _finite(initial + change)
    if final <= 0:
        raise EngineeringError("Computed length is nonpositive; input is outside the linear expansion model.")
    return {"length_change": _result(change, "m"), "final_length": _result(final, "m"),
            "assumptions": ["uniform_temperature_change", "constant_linear_expansion_coefficient", "unconstrained_expansion"],
            "limitations": ["Does not model thermal stress, phase changes, gradients or temperature-dependent properties."]}


def second_order_step(*, natural_frequency: Mapping[str, Any], damping_ratio: float,
                      elapsed_time: Mapping[str, Any]) -> dict[str, Any]:
    """Unit-step response of wn² / (s² + 2*zeta*wn*s + wn²), 0<zeta<1."""
    wn = _quantity(natural_frequency, "rad/s", "natural_frequency", positive=True)
    zeta = _number(damping_ratio, "damping_ratio")
    time = _quantity(elapsed_time, "s", "elapsed_time", nonnegative=True)
    if not 0 < zeta < 1:
        raise EngineeringError("This tool covers only underdamped systems with 0 < damping_ratio < 1.")
    root = math.sqrt((1 - zeta) * (1 + zeta))
    wd = _finite(wn * root)
    angle = _finite(wd * time)
    envelope = math.exp(-_finite(zeta * wn * time))
    response = 1 - envelope * (math.cos(angle) + zeta / root * math.sin(angle))
    return {"response": _result(response, "1"),
            "overshoot": _result(100 * math.exp(-math.pi * zeta / root), "%"),
            "peak_time": _result(math.pi / wd, "s"),
            "settling_time_2pct_approx": _result(4 / (zeta * wn), "s"),
            "assumptions": ["linear_time_invariant", "zero_initial_conditions", "unit_step", "underdamped"],
            "limitations": ["Settling time is the common 4/(zeta*wn) approximation, not an exact crossing time."]}


def series_rlc(*, resistance: Mapping[str, Any], inductance: Mapping[str, Any],
               capacitance: Mapping[str, Any]) -> dict[str, Any]:
    """Natural frequency and damping for an ideal passive series RLC circuit."""
    resistance_ohm = _quantity(resistance, "Ohm", "resistance", positive=True)
    inductance_h = _quantity(inductance, "H", "inductance", positive=True)
    capacitance_f = _quantity(capacitance, "F", "capacitance", positive=True)
    # Separated square roots avoid underflow in the L*C product.
    omega = _finite(1 / math.sqrt(inductance_h) / math.sqrt(capacitance_f))
    q = _finite(math.sqrt(inductance_h) / math.sqrt(capacitance_f) / resistance_ohm)
    return {"natural_frequency": _result(omega, "rad/s"),
            "resonance_frequency": _result(omega / (2 * math.pi), "Hz"),
            "quality_factor": _result(q, "1"), "damping_ratio": _result(1 / (2 * q), "1"),
            "assumptions": ["ideal_lumped_components", "series_rlc", "linear_components"],
            "limitations": ["Resonance is zero net reactance, not necessarily the capacitor-voltage peak frequency."]}


def quadratic_roots(*, a: float, b: float, c: float) -> dict[str, Any]:
    """Real roots of a*x²+b*x+c=0 using a cancellation-resistant formula."""
    coefficients = [_number(x, name) for x, name in zip((a, b, c), ("a", "b", "c"))]
    if coefficients[0] == 0:
        raise EngineeringError("a must be nonzero; a degenerate equation is not a quadratic.")
    magnitude = max(abs(x) for x in coefficients)
    an, bn, cn = (x / magnitude for x in coefficients)
    if an == 0:
        raise EngineeringError("Coefficient scale separation exceeds this floating-point solver's range.")
    discriminant = bn * bn - 4 * an * cn
    if discriminant < 0:
        roots: list[float] = []
    elif discriminant == 0:
        roots = [_finite(-bn / (2 * an))]
    else:
        q = -0.5 * (bn + math.copysign(math.sqrt(discriminant), bn))
        roots = sorted([_finite(q / an), _finite(cn / q)])
    return {"real_roots": roots, "assumptions": ["real_coefficients", "dimensionless_variable"],
            "limitations": ["Double precision is not a symbolic or arbitrary-precision proof."]}


_TOOLS: dict[str, tuple[Callable[..., Any], set[str]]] = {
    "convert_units": (convert_units, {"value", "from_unit", "to_unit"}),
    "check_dimensional_equation": (check_dimensional_equation, {"lhs_unit", "rhs_unit"}),
    "axial_stress": (axial_stress, {"force", "area", "allowable_strength"}),
    "dc_motor": (dc_motor, {"torque_constant", "current", "angular_speed", "winding_resistance"}),
    "thermal_expansion": (thermal_expansion, {"length", "coefficient", "delta_temperature"}),
    "second_order_step": (second_order_step, {"natural_frequency", "damping_ratio", "elapsed_time"}),
    "series_rlc": (series_rlc, {"resistance", "inductance", "capacitance"}),
    "quadratic_roots": (quadratic_roots, {"a", "b", "c"}),
}


def tool_catalog() -> dict[str, list[str]]:
    """Return whitelisted tools and their required argument names."""
    return {name: sorted(fields) for name, (_, fields) in _TOOLS.items()}


def execute_tool(name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Dispatch a strictly validated tool request; no arbitrary code paths.

    Raises EngineeringError instead of filling missing inputs. Callers may report
    that exception as a structured refusal; they must not silently substitute 0.
    """
    if not isinstance(name, str) or name not in _TOOLS:
        raise EngineeringError(f"Unknown engineering tool: {name!r}.")
    if not isinstance(arguments, Mapping):
        raise EngineeringError("Tool arguments must be an object.")
    function, fields = _TOOLS[name]
    missing, unknown = fields - set(arguments), set(arguments) - fields
    if missing or unknown:
        raise EngineeringError(f"Tool arguments incomplete or invalid; missing={sorted(missing)}, unknown={sorted(map(str, unknown))}.")
    try:
        result = function(**arguments)
    except (OverflowError, ZeroDivisionError) as exc:
        raise EngineeringError("Inputs exceed the calculator's finite numerical range.") from exc
    return {"tool": name, "result": result, "provenance": "external_deterministic_tool"}
