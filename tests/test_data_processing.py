"""Tests for utils/data_processing.py"""

import pytest
from utils.data_processing import (
    JSONProcessor,
    MetricsCalculator,
    DataValidator,
    DataAggregator,
    format_currency,
    format_percentage,
    format_number,
)


class TestJSONProcessor:
    def test_validate_schema_pass(self):
        data = {"name": "test", "age": 25}
        schema = {"name": str, "age": int}
        assert JSONProcessor.validate_schema(data, schema) is True

    def test_validate_schema_missing_key(self):
        assert JSONProcessor.validate_schema({}, {"name": str}) is False

    def test_validate_schema_wrong_type(self):
        assert JSONProcessor.validate_schema({"name": 123}, {"name": str}) is False

    def test_safe_get_nested(self):
        data = {"a": {"b": {"c": 42}}}
        assert JSONProcessor.safe_get(data, "a.b.c") == 42

    def test_safe_get_missing(self):
        assert JSONProcessor.safe_get({}, "a.b", "default") == "default"

    def test_clean_json(self):
        data = {"a": 1, "b": None, "c": [None, 2]}
        result = JSONProcessor.clean_json(data)
        assert result == {"a": 1, "c": [2]}


class TestMetricsCalculator:
    def test_calculate_ctr(self):
        assert MetricsCalculator.calculate_ctr(1000, 50) == 5.0

    def test_calculate_ctr_zero_impressions(self):
        assert MetricsCalculator.calculate_ctr(0, 0) == 0.0

    def test_calculate_cpc(self):
        assert MetricsCalculator.calculate_cpc(100.0, 50) == 2.0

    def test_calculate_cpc_zero_clicks(self):
        assert MetricsCalculator.calculate_cpc(100.0, 0) == 0.0

    def test_calculate_cpm(self):
        assert MetricsCalculator.calculate_cpm(10.0, 1000) == 10.0

    def test_calculate_conversion_rate(self):
        assert MetricsCalculator.calculate_conversion_rate(10, 100) == 10.0

    def test_calculate_cpa(self):
        assert MetricsCalculator.calculate_cpa(100.0, 10) == 10.0

    def test_calculate_roas(self):
        assert MetricsCalculator.calculate_roas(500.0, 100.0) == 5.0

    def test_process_metrics(self):
        raw = {"impressions": 10000, "clicks": 500, "spend": 100.0, "conversions": 50}
        result = MetricsCalculator.process_metrics(raw)
        assert result["ctr"] == 5.0
        assert result["cpc"] == 0.2
        assert result["conversion_rate"] == 10.0


class TestDataValidator:
    def test_valid_metrics(self):
        metrics = {"impressions": 1000, "clicks": 50, "spend": 10.0, "ctr": 5.0}
        result = DataValidator.validate_metrics(metrics)
        assert result["is_valid"] is True

    def test_invalid_ctr(self):
        metrics = {"impressions": 100, "clicks": 50, "spend": 10.0, "ctr": 150}
        result = DataValidator.validate_metrics(metrics)
        assert result["is_valid"] is False

    def test_negative_values(self):
        metrics = {"impressions": -1, "clicks": 50, "spend": 10.0}
        result = DataValidator.validate_metrics(metrics)
        assert not result["is_valid"]

    def test_check_data_freshness_recent(self):
        from datetime import datetime
        ts = datetime.now().isoformat()
        assert DataValidator.check_data_freshness(ts) is True

    def test_check_data_freshness_old(self):
        assert DataValidator.check_data_freshness("2020-01-01T00:00:00") is False


class TestDataAggregator:
    def test_aggregate_campaign_data(self):
        adsets = [
            {"impressions": 1000, "clicks": 50, "spend": 10.0, "conversions": 5},
            {"impressions": 2000, "clicks": 100, "spend": 20.0, "conversions": 10},
        ]
        result = DataAggregator.aggregate_campaign_data(adsets)
        assert result["impressions"] == 3000
        assert result["clicks"] == 150


class TestFormatFunctions:
    def test_format_currency(self):
        assert format_currency(99.99) == "$99.99"
        assert format_currency(99.99, "EUR") == "€99.99"

    def test_format_percentage(self):
        assert format_percentage(5.123) == "5.12%"

    def test_format_number(self):
        assert format_number(1000000) == "1,000,000"
