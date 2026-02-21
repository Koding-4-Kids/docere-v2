"""Tests for Bayesian Knowledge Tracing (BKT) module."""

import pytest

from docere.core.knowledge_tracing import (
    BKTParams,
    bkt_predict_correct,
    bkt_update,
    confusion_to_correct,
)


# ── confusion_to_correct ──


class TestConfusionToCorrect:
    def test_low_confusion_is_correct(self):
        assert confusion_to_correct(0.0) is True
        assert confusion_to_correct(0.1) is True
        assert confusion_to_correct(0.39) is True

    def test_high_confusion_is_incorrect(self):
        assert confusion_to_correct(0.4) is False
        assert confusion_to_correct(0.7) is False
        assert confusion_to_correct(1.0) is False

    def test_boundary(self):
        # Exactly at threshold → incorrect (conservative)
        assert confusion_to_correct(0.4) is False
        assert confusion_to_correct(0.399) is True

    def test_custom_threshold(self):
        assert confusion_to_correct(0.5, threshold=0.6) is True
        assert confusion_to_correct(0.7, threshold=0.6) is False


# ── bkt_update ──


class TestBKTUpdate:
    def test_correct_observation_increases_learned(self):
        params = BKTParams()
        p_before = 0.3
        p_after = bkt_update(p_before, correct=True, params=params)
        assert p_after > p_before

    def test_incorrect_observation_can_decrease_learned(self):
        params = BKTParams()
        # Start with moderate knowledge — wrong answer should lower it
        # (but learning transition may partially offset)
        p_high = 0.8
        p_after = bkt_update(p_high, correct=False, params=params)
        # Even with learning transition, wrong answer from high P(L)
        # should net lower than starting point
        assert p_after < p_high

    def test_prior_with_correct_observation(self):
        params = BKTParams(p_l0=0.1)
        p_after = bkt_update(params.p_l0, correct=True, params=params)
        # Should jump significantly from 0.1
        assert p_after > 0.3

    def test_prior_with_incorrect_observation(self):
        params = BKTParams(p_l0=0.1)
        p_after = bkt_update(params.p_l0, correct=False, params=params)
        # Should stay low but not be zero (learning transition)
        assert 0.0 < p_after < 0.3

    def test_learning_sequence_converges(self):
        """6 observations: correct, correct, wrong, correct, correct, correct → high mastery."""
        params = BKTParams()
        p = params.p_l0

        observations = [True, True, False, True, True, True]
        for correct in observations:
            p = bkt_update(p, correct, params)

        # Should converge to high mastery
        assert p > 0.9

    def test_all_wrong_stays_low(self):
        """All incorrect observations → stays at low mastery."""
        params = BKTParams()
        p = params.p_l0

        for _ in range(6):
            p = bkt_update(p, correct=False, params=params)

        # Should stay low (learning transition adds some, but not much)
        assert p < 0.5

    def test_all_correct_converges_to_one(self):
        """Many correct observations → converges near 1.0."""
        params = BKTParams()
        p = params.p_l0

        for _ in range(10):
            p = bkt_update(p, correct=True, params=params)

        assert p > 0.99

    def test_slip_resilience(self):
        """One wrong answer after many correct shouldn't crash mastery."""
        params = BKTParams()
        p = params.p_l0

        # Build up mastery
        for _ in range(5):
            p = bkt_update(p, correct=True, params=params)
        p_before_slip = p

        # One slip
        p = bkt_update(p, correct=False, params=params)

        # Should dip but not crash
        assert p > 0.5
        assert p < p_before_slip

    def test_output_bounded_zero_one(self):
        """Result should always be in [0, 1]."""
        params = BKTParams()
        for p_start in [0.0, 0.001, 0.5, 0.999, 1.0]:
            for correct in [True, False]:
                result = bkt_update(p_start, correct, params)
                assert 0.0 <= result <= 1.0, f"Out of bounds: {result} for p={p_start}, correct={correct}"

    def test_custom_params(self):
        """Custom BKT parameters change behavior."""
        # High guess rate → correct observation is less informative
        high_guess = BKTParams(p_guess=0.4)
        default = BKTParams()

        p_high_guess = bkt_update(0.1, correct=True, params=high_guess)
        p_default = bkt_update(0.1, correct=True, params=default)

        # With higher guess rate, correct answer is less evidence of knowing
        assert p_high_guess < p_default

    def test_degenerate_zero_denominator(self):
        """Edge case: parameters that could cause division by zero."""
        # p_slip=0 and p_guess=0 with p_learned=0 and wrong → denominator is 0
        params = BKTParams(p_guess=0.0, p_slip=0.0)
        result = bkt_update(0.0, correct=False, params=params)
        # Should not crash, returns something in [0, 1]
        assert 0.0 <= result <= 1.0


# ── bkt_predict_correct ──


class TestBKTPredictCorrect:
    def test_high_mastery_predicts_correct(self):
        params = BKTParams()
        p = bkt_predict_correct(0.9, params)
        assert p > 0.8

    def test_low_mastery_predicts_low(self):
        params = BKTParams()
        p = bkt_predict_correct(0.1, params)
        # Even with low mastery, guess rate provides a floor
        assert p < 0.3
        assert p >= params.p_guess  # Floor is the guess rate

    def test_zero_mastery_equals_guess_rate(self):
        params = BKTParams()
        p = bkt_predict_correct(0.0, params)
        assert p == pytest.approx(params.p_guess)

    def test_full_mastery(self):
        params = BKTParams()
        p = bkt_predict_correct(1.0, params)
        assert p == pytest.approx(1.0 - params.p_slip)
