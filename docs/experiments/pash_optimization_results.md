# PASH Optimization Experiment Results

Config: N=512, S=64, M=32, p_max=0.15.

## Methods

- **Random**: uniform inclusion probability, no history awareness.
- **PASH-cap**: capped exponential heuristic (alpha=1.40, floor=0.20, cap=0.15).
- **PASH-opt**: projected subgradient descent solving min_p lambda * E[short-delay collision] + (1-lambda) * max_{|J|=S} sum_{k in J} p_k s.t. 0 <= p_k <= p_max, sum_k p_k = S.

## Structural results

| Method | short-delay | worst-lag | candidate | usage CV | max incl prob | top-S mass | min-entropy approx |
|---|---:|---:|---:|---:|---:|---:|---:|
| Random | 0.125 | 0.125 (d=11) | 0.125 | 0.0481 | 0.125 | 0.125 | 2.08 |
| PASH-cap (heuristic) | 0.099 | 0.130 (d=7) | 0.148 | 0.0395 | 0.150 | 0.150 | 1.90 |
| PASH-opt $\lambda=0.00$ | 0.104 | 0.129 (d=7) | 0.142 | 0.0412 | 0.143 | 0.143 | 1.95 |
| PASH-opt $\lambda=0.25$ | 0.096 | 0.131 (d=7) | 0.146 | 0.0400 | 0.148 | 0.148 | 1.91 |
| PASH-opt $\lambda=0.50$ | 0.091 | 0.131 (d=7) | 0.149 | 0.0392 | 0.150 | 0.150 | 1.90 |
| PASH-opt $\lambda=0.75$ | 0.087 | 0.131 (d=7) | 0.148 | 0.0385 | 0.150 | 0.150 | 1.90 |
| PASH-opt $\lambda=1.00$ | 0.083 | 0.131 (d=7) | 0.149 | 0.0392 | 0.150 | 0.150 | 1.90 |

## Acceptance criteria check

Best PASH-opt: PASH-opt $\lambda=0.00$
  risk = 0.1416 (cap risk = 0.1482)

| Criterion | Result | Detail |
|---|---|---|
| 1. Same short-delay, lower candidate | PASS | opt candidate=0.1416 vs cap=0.1482 |
| 2. Same candidate, lower short-delay | PASS | opt short=0.1037 vs cap=0.0995 |
| 3. Flatter lag spectrum | PASS | opt worst-lag=0.1289 vs cap=0.1304 |

**At least one criterion met — PASH-opt is worth including in the main paper.**

## Interpretation

- lambda=0: pure candidate-aware minimisation (minimise max jammer-capturable mass).
- lambda=1: pure short-delay follower avoidance.
- Intermediate lambda values trace the Pareto frontier between these two objectives.
- PASH-cap is a single heuristic point on this frontier.
- If PASH-opt achieves lower candidate-aware collision at the same short-delay cost,
  it demonstrates that the exponential heuristic is not Pareto-optimal.

## Outputs

- Data: `results/pash_opt/summary.csv`.
- Figure: `figures/paper/fig9_pash_optimization.pdf`.
- Smoke outputs use `tmp/smoke-pash-opt/`.
