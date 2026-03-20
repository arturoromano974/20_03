"""Tests for models/ml_optimizer.py"""

import os
import pytest
from unittest.mock import patch

MOCK_CONFIG = {
    "machine_learning": {
        "ml_model": {
            "algorithm": "gradient_boosting",
            "features": [
                "impressions", "clicks", "ctr", "cpc", "cpm",
                "conversions", "cost", "1_day_click", "1_day_view"
            ],
        }
    }
}


@pytest.fixture(autouse=True)
def mock_config(monkeypatch):
    import utils.config_loader as cl
    cl._cached_config = MOCK_CONFIG
    yield
    cl._cached_config = None


def _make_optimizer():
    from models.ml_optimizer import MLOptimizer
    return MLOptimizer()


def _sample_metrics():
    return {
        "impressions": 10000,
        "clicks": 500,
        "ctr": 5.0,
        "cpc": 0.2,
        "cpm": 10.0,
        "conversions": 50,
        "cost": 100.0,
        "1_day_clicks": 30,
        "1_day_views": 40,
        "spend": 100.0,
    }


class TestPrepareFeatures:
    def test_returns_correct_shape(self):
        opt = _make_optimizer()
        features = opt.prepare_features(_sample_metrics())
        assert features.shape == (1, 9)

    def test_1_day_click_alias(self):
        """Feature '1_day_click' should read from '1_day_clicks'."""
        opt = _make_optimizer()
        m = {"1_day_clicks": 42}
        features = opt.prepare_features(m)
        idx = MOCK_CONFIG["machine_learning"]["ml_model"]["features"].index("1_day_click")
        assert features[0, idx] == 42.0


class TestTrainModel:
    def test_insufficient_data(self):
        opt = _make_optimizer()
        assert opt.train_model([_sample_metrics()] * 5) is False

    def test_successful_training(self):
        opt = _make_optimizer()
        data = [_sample_metrics() for _ in range(20)]
        assert opt.train_model(data) is True
        assert opt.is_trained is True
        assert hasattr(opt, "training_score")


class TestPredictPerformance:
    def test_untrained_returns_baseline(self):
        opt = _make_optimizer()
        result = opt.predict_performance(_sample_metrics())
        assert result["confidence"] == "low"
        assert result["model_score"] == 0.0

    def test_trained_prediction(self):
        opt = _make_optimizer()
        opt.train_model([_sample_metrics() for _ in range(20)])
        result = opt.predict_performance(_sample_metrics())
        assert "predicted_1day_conversion_rate" in result


class TestBudgetRecommendation:
    def test_maintain_budget(self):
        opt = _make_optimizer()
        result = opt.recommend_budget(_sample_metrics(), 100.0)
        assert result["current_budget"] == 100.0
        assert result["action"] in ("increase", "decrease", "maintain")


class TestSaveLoadModel:
    def test_save_and_load(self, tmp_path):
        opt = _make_optimizer()
        opt.train_model([_sample_metrics() for _ in range(20)])

        filepath = str(tmp_path / "model.joblib")
        assert opt.save_model(filepath) is True
        assert os.path.isfile(filepath)

        opt2 = _make_optimizer()
        assert opt2.load_model(filepath) is True
        assert opt2.is_trained is True
