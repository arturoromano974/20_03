"""Tests for models/bayesian_model.py"""

import pytest
from unittest.mock import patch, MagicMock

# Mock config before importing the module
MOCK_CONFIG = {
    "machine_learning": {
        "bayesian_model": {
            "prior_strength": 0.1,
            "sensitivity": "high",
            "focus_metric": "1_day_click_view",
        }
    }
}


@pytest.fixture(autouse=True)
def mock_config(monkeypatch):
    """Ensure config is mocked for all tests."""
    import utils.config_loader as cl
    cl._cached_config = MOCK_CONFIG
    yield
    cl._cached_config = None


def _make_optimizer():
    from models.bayesian_model import BayesianOptimizer
    return BayesianOptimizer()


class TestEstimateConversionProbability:
    def test_zero_trials_returns_insufficient_data(self):
        opt = _make_optimizer()
        result = opt.estimate_conversion_probability(0, 0)
        assert result["mean"] == 0.0
        assert result["insufficient_data"] is True

    def test_normal_data(self):
        opt = _make_optimizer()
        result = opt.estimate_conversion_probability(50, 1000)
        assert 0.0 < result["mean"] < 1.0
        assert result["ci_lower"] < result["mean"] < result["ci_upper"]
        assert result["insufficient_data"] is False

    def test_all_conversions(self):
        opt = _make_optimizer()
        result = opt.estimate_conversion_probability(100, 100)
        assert result["mean"] > 0.5

    def test_posterior_parameters(self):
        opt = _make_optimizer()
        result = opt.estimate_conversion_probability(10, 100, prior_alpha=2.0, prior_beta=98.0)
        assert result["posterior_alpha"] == 12.0
        assert result["posterior_beta"] == 188.0


class TestImprovementProbability:
    def test_clearly_better(self):
        opt = _make_optimizer()
        result = opt.calculate_improvement_probability(10, 1000, 50, 1000)
        assert result["prob_b_better"] > 0.9

    def test_clearly_worse(self):
        opt = _make_optimizer()
        result = opt.calculate_improvement_probability(50, 1000, 10, 1000)
        assert result["prob_b_better"] < 0.1

    def test_similar_performance(self):
        opt = _make_optimizer()
        result = opt.calculate_improvement_probability(50, 1000, 51, 1000)
        assert 0.3 < result["prob_b_better"] < 0.7


class TestMicroSensitivity:
    def test_insufficient_history(self):
        opt = _make_optimizer()
        result = opt.calculate_micro_sensitivity([{"1_day_clicks": 10}])
        assert result["sensitivity_score"] == 0.0
        assert result["responsiveness"] == "unknown"

    def test_stable_metrics(self):
        opt = _make_optimizer()
        history = [{"1_day_clicks": 100, "1_day_views": 200}] * 10
        result = opt.calculate_micro_sensitivity(history)
        assert result["sensitivity_score"] == 0.0
        assert result["responsiveness"] == "low"

    def test_volatile_metrics(self):
        opt = _make_optimizer()
        # Use alternating high/low values so diffs have non-zero std
        history = [
            {"1_day_clicks": 100 if i % 2 == 0 else 500,
             "1_day_views": 50 if i % 2 == 0 else 300}
            for i in range(10)
        ]
        result = opt.calculate_micro_sensitivity(history)
        assert result["sensitivity_score"] > 0


class TestPredictFuturePerformance:
    def test_insufficient_data(self):
        opt = _make_optimizer()
        result = opt.predict_future_performance([{"clicks": 10, "conversions": 1}])
        assert result["confidence"] == "low"

    def test_prediction_clamped(self):
        """Predicted conversion rate must stay within [0, 1]."""
        opt = _make_optimizer()
        history = [
            {"clicks": 100, "conversions": 99},
            {"clicks": 100, "conversions": 100},
            {"clicks": 100, "conversions": 100},
            {"clicks": 100, "conversions": 100},
        ]
        result = opt.predict_future_performance(history, periods_ahead=100)
        assert 0.0 <= result["predicted_conversion_rate"] <= 1.0
