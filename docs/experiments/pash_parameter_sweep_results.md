# PASH Parameter Sweep Results

## Research question

Can the capped PASH parameters be selected by an auditable structural criterion rather than by a hand-tuned choice?

## Design

- Method: capped exponential PASH with memory 6.
- Parameters: alpha, probability floor, and inclusion-probability cap.
- Metrics: short-delay collision, worst-lag collision, candidate-aware collision, usage CV, and max inclusion probability.
- Feasibility rule: short-delay collision <= 0.105, usage CV <= 0.055, and measured max inclusion probability respecting the cap.
- Objective: minimize max(worst-lag collision, candidate-aware collision) among feasible candidates.
- Profile: `paper`.

## Best feasible setting

- alpha=1.40, floor=0.20, cap=0.14; short-delay=0.1048, worst-lag d=7 collision=0.1292, candidate-aware=0.1390, risk=0.1390, usage-CV=0.0492.

## Current paper setting located in the sweep

- alpha=1.40, floor=0.20, cap=0.15; short-delay=0.0997, worst-lag d=7 collision=0.1305, candidate-aware=0.1487, risk=0.1487, usage-CV=0.0465.

## Interpretation

This sweep turns the PASH-cap choice into a reproducible design point. If the best feasible point differs from the current paper setting, the next paper iteration should either update the PASH-cap parameterization or explicitly justify the more conservative choice.

## Outputs

- Data: `results/pash_sweep/summary.csv`.
- Figure: `figures/paper/fig8_pash_parameter_sweep.pdf`.
- Temporary smoke outputs use `tmp/smoke-pash-sweep/`.

## Limitations

The sweep is structural. It does not yet rerun coded BER/BLER for every candidate. The selected point should be validated in coded adversarial experiments before replacing the current paper setting.
