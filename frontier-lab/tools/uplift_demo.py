#!/usr/bin/env python3
"""Simple, deterministic SYNTHETIC randomized experiment. No customer data."""
import json
import math
import random


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        raise ValueError("n must be a positive integer")
    if not isinstance(successes, int) or isinstance(successes, bool) or not 0 <= successes <= n:
        raise ValueError("invalid number of successes")
    if not math.isfinite(z) or z <= 0:
        raise ValueError("invalid z-score")
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def simulate(seed: int = 20261115, n_per_arm: int = 1500, p_control: float = 0.1, p_treatment: float = 0.13) -> dict:
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be integer")
    if not isinstance(n_per_arm, int) or isinstance(n_per_arm, bool) or n_per_arm < 2:
        raise ValueError("need at least two observations per arm")
    if not all(isinstance(p, (int, float)) and not isinstance(p, bool) and math.isfinite(p) and 0 <= p <= 1 for p in (p_control, p_treatment)):
        raise ValueError("probabilities must be finite in [0, 1]")
    rng = random.Random(seed)
    # Treatment assignment is synthetic, fixed by design. No observational confounding claim.
    control = sum(rng.random() < p_control for _ in range(n_per_arm))
    treatment = sum(rng.random() < p_treatment for _ in range(n_per_arm))
    rate_c, rate_t = control / n_per_arm, treatment / n_per_arm
    risk_diff = rate_t - rate_c
    standard_error = math.sqrt(rate_c * (1 - rate_c) / n_per_arm + rate_t * (1 - rate_t) / n_per_arm)
    return {
        "provenance": "synthetic_demo_only",
        "dataset": "random_generated_binary_outcomes",
        "seed": seed,
        "n_per_arm": n_per_arm,
        "control": {"successes": control, "rate": rate_c, "wilson_95": wilson_interval(control, n_per_arm)},
        "treatment": {"successes": treatment, "rate": rate_t, "wilson_95": wilson_interval(treatment, n_per_arm)},
        "risk_difference": risk_diff,
        "approx_risk_difference_95": [risk_diff - 1.96 * standard_error, risk_diff + 1.96 * standard_error],
        "interpretation": "Demonstration only. Asymptotic CIs; no claim of real conversion uplift, no clustered/randomization inference.",
    }


if __name__ == "__main__":
    print(json.dumps(simulate(), indent=2))
