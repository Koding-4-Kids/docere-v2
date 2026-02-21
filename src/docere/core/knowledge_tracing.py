"""Bayesian Knowledge Tracing (BKT) for concept mastery estimation.

A Hidden Markov Model that tracks the probability a student has learned
a concept based on their sequence of correct/incorrect observations.

Pure math — no DB, no LLM, no async dependencies.
"""

from dataclasses import dataclass


@dataclass
class BKTParams:
    """Parameters for a single BKT concept model.

    p_l0:      Prior probability of knowing the concept before any practice.
    p_transit: Probability of learning on each practice opportunity.
    p_guess:   Probability of correct response despite not knowing.
    p_slip:    Probability of incorrect response despite knowing.
    """

    p_l0: float = 0.1
    p_transit: float = 0.2
    p_guess: float = 0.15
    p_slip: float = 0.1


def bkt_update(p_learned: float, correct: bool, params: BKTParams) -> float:
    """Single BKT update step. Returns new P(learned).

    1. Bayesian posterior update given the observation.
    2. Apply learning transition (student may have learned from the attempt).
    """
    if correct:
        # P(L | correct) via Bayes' rule
        p_correct_given_l = 1.0 - params.p_slip
        p_correct_given_not_l = params.p_guess
        numerator = p_learned * p_correct_given_l
        denominator = numerator + (1.0 - p_learned) * p_correct_given_not_l
    else:
        # P(L | wrong) via Bayes' rule
        p_wrong_given_l = params.p_slip
        p_wrong_given_not_l = 1.0 - params.p_guess
        numerator = p_learned * p_wrong_given_l
        denominator = numerator + (1.0 - p_learned) * p_wrong_given_not_l

    # Guard against division by zero (degenerate parameters)
    if denominator == 0:
        p_posterior = p_learned
    else:
        p_posterior = numerator / denominator

    # Learning transition: student may have learned from this attempt
    p_new = p_posterior + (1.0 - p_posterior) * params.p_transit

    return p_new


def bkt_predict_correct(p_learned: float, params: BKTParams) -> float:
    """Predict probability of correct response on next attempt."""
    return p_learned * (1.0 - params.p_slip) + (1.0 - p_learned) * params.p_guess


def confusion_to_correct(confusion_score: float, threshold: float = 0.4) -> bool:
    """Map continuous confusion score to binary observation for BKT.

    confusion < threshold  → student demonstrated understanding (correct)
    confusion >= threshold → student did NOT demonstrate understanding (incorrect)

    Threshold at 0.4 (not 0.5) is conservative — we require clear evidence
    of understanding before counting it as "correct".
    """
    return confusion_score < threshold
