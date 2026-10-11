"""Conservative operating envelope for the unchanged pinned float calculator.

This is gate policy, not a claim that the source itself enforces these limits.
Bounding all nonzero scalar inputs keeps the algebraic functions' product/ratio
chains away from binary64 underflow/overflow. It deliberately refuses many valid
extreme-scale problems instead of silently changing the authenticated source.
"""
import math

MIN_NONZERO = 1e-50
MAX_MAGNITUDE = 1e50


def description():
    return {
        'version': 1,
        'nonzero_input_absolute_min': MIN_NONZERO,
        'nonzero_input_absolute_max': MAX_MAGNITUDE,
        'zero': 'Allowed only where the source domain allows it.',
        'second_order_nonzero_normalized_time_min': 1e-6,
        'second_order_normalized_time_max': 1e6,
        'second_order_max_decay_or_overshoot_exponent': 700,
        'scope': 'Additional conservative gate limits, not source limits or a precision guarantee.',
        'limitations': 'Rounding, cancellation and ill-conditioning can still occur within this envelope; independent engineering validation is not established.',
        'conversion': 'Unit conversion is algebraic; physical plausibility such as absolute-temperature validity is not certified.',
    }


def range_issue(capability, arguments):
    numbers = {}
    for name, argument in arguments.items():
        value = argument.get('value') if isinstance(argument, dict) else argument
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue  # The original strict domain validator handles bad types.
        try:
            if not math.isfinite(value):
                continue
        except OverflowError:
            continue
        numbers[name] = value
        if value != 0 and not MIN_NONZERO <= abs(value) <= MAX_MAGNITUDE:
            return {'input': name, 'reason': 'Every nonzero numeric input must have absolute magnitude between 1e-50 and 1e50 under the current numerical policy.'}
    if capability == 'second_order_step' and {'natural_frequency', 'damping_ratio', 'elapsed_time'} <= numbers.keys():
        wn, zeta, time = (numbers[n] for n in ('natural_frequency', 'damping_ratio', 'elapsed_time'))
        if wn > 0 and 0 < zeta < 1 and time >= 0:
            phase = wn * time
            if (time > 0 and phase < 1e-6) or phase > 1e6:
                return {'input': 'natural_frequency * elapsed_time', 'reason': 'The current step-response policy requires normalized time 0 or between 1e-6 and 1e6 to limit initial subtraction loss and large-phase error.'}
            overshoot_exponent = math.pi * zeta / math.sqrt((1 - zeta) * (1 + zeta))
            if zeta * phase > 700 or overshoot_exponent > 700:
                return {'input': 'damping/time', 'reason': 'The exponential terms exceed the supported decay range; a nonzero term could silently collapse to zero.'}
    return None
