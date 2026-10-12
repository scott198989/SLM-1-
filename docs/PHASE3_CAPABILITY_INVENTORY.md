# FORGE v0.1 deterministic capability inventory

The router exposes 13 named calculations. It accepts strict arguments and bounded finite JSON, records input SHA-256 and returns computations with assumptions and limitations. Results are evidence for a stated calculation, not proof that the physical system or supplied parameters are correct. The engineering source remains byte-identical to the pinned transplant.

| Tool | Delegated calculation | Scope and outstanding model/human responsibility |
|---|---|---|
| `convert_units` | Supported SI/unit products and affine absolute temperatures; temperature differences separately | Choose correct physical quantity and absolute-versus-interval semantics. Hz is not interchangeable with rad/s without an explicit relation. Not a calibration procedure. |
| `check_dimensional_equation` | Compare supported dimensional expressions | Matching dimensions do not prove equations, sign conventions or physical equality. |
| `axial_stress` | F/A and allowable-strength/stress; zero-load unbounded result | Uniform static axial tension only; no buckling, bending, fatigue, fracture, joint or design-code acceptance. |
| `dc_motor` | Ideal SI PM DC torque, shaft power, copper loss, voltage and efficiency | Steady state; Kt=Ke in SI; no iron/mechanical/inverter loss, transients, thermal rating, saturation or AC/VFD model. |
| `thermal_expansion` | Free one-dimensional constant-coefficient expansion/contraction | Uniform unconstrained temperature change; no gradients, phase changes or thermal stress. |
| `second_order_step` | Unit-step response, overshoot, peak and approximate 2% settling time | Zero initial conditions, stable underdamped LTI system, 0<zeta<1; no general tuning or exact settling-crossing promise. |
| `series_rlc` | Natural/zero-reactance frequency, Q and damping | Ideal passive series lumped RLC; not an arbitrary network or capacitor-voltage-peak analysis. |
| `quadratic_roots` | Cancellation-resistant distinct real roots | Nondegenerate real quadratic; double precision, not arbitrary precision or symbolic proof. No complex roots. |
| `welch_ttest` | Difference, Welch t, Satterthwaite df, two-sided p and CI | Independent suitable samples, finite nondegenerate standard error; distribution/experimental assumptions must be justified separately. |
| `anova_oneway` | Classical one-way F, p and degrees of freedom | 2–32 groups, nonzero within-group variance, independent samples/normal residuals/equal variances; no automatic assumption test. |
| `linear_regression` | Full-column OLS with intercept, SSE, R-squared and residual df | 1–32 predictors, sufficient rows and full-rank design; no causality, robust-inference, extrapolation or automatic variable selection. |
| `factorial_design` | Complete two-level coded matrix, 1–8 factors | Physical levels, blocking, replication, randomization and safe experiment execution remain external. |
| `spc_known_sigma` | Known-center/sigma three-sigma individual limits and strict out-of-limit indices | Known stable independent baseline; no estimated Xbar-R, WECO, specifications, Cp/Cpk or acceptance decision. |

The tests independently cover arithmetic/dimensions, motor energy balance, RLC reactance, step initial/peak/steady behavior, temperature intervals, quadratic residuals, Welch/ANOVA/OLS fixtures, DOE orthogonality and SPC boundaries. They also cover missing/extra arguments, invalid units, nonfinite and Boolean inputs, numerical overflow, rank deficiency and bounded requests. The complete current software suite has 56 passing tests; that total includes dataset, family, seal, citation, tokenizer and controller tests, not 56 engineering-proof tests.

`baseline_protocol` adds an offline injected-inference controller with whitelisted tools and a three-call ceiling. It is tested with software fixtures and has not been integrated with loaded Qwen weights. No arbitrary Python, shell, network execution or expression evaluation is exposed as a model tool. Native tool-role fine-tuning is not included in the released JSON calculator protocol pilot.

FORGE still relies on model reasoning or external qualified tools/humans for model selection, assumptions, diagram interpretation, troubleshooting evidence, PLC scan semantics, ladder programs, Siemens/TIA configuration, induction motors/VFDs, PID design, sensor calibration, beam/FEA analysis, tolerance/production planning and safety/code acceptance. The current Qwen Base target has no image encoder. A faithful image link plus reviewed caption/data enables citations; it does not confer general vision capability.
