#!/usr/bin/env python3
"""
Python Utility Scripts for Data Processing and Analysis

This module provides utilities for structured JSON processing
to avoid LLM hallucinations and ensure data integrity.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JSONProcessor:
    """Safe JSON processing utilities"""

    @staticmethod
    def validate_schema(data: Dict, schema: Dict) -> bool:
        """Validate JSON data against schema"""
        try:
            for key, expected_type in schema.items():
                if key not in data:
                    logger.error(f"Missing required key: {key}")
                    return False

                if not isinstance(data[key], expected_type):
                    logger.error(f"Invalid type for {key}: expected {expected_type}, got {type(data[key])}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Schema validation error: {str(e)}")
            return False

    @staticmethod
    def safe_get(data: Dict, path: str, default: Any = None) -> Any:
        """Safely get nested value from dict"""
        try:
            keys = path.split('.')
            value = data

            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return default

                if value is None:
                    return default

            return value

        except Exception:
            return default

    @staticmethod
    def clean_json(data: Any) -> Any:
        """Remove null values and clean JSON"""
        if isinstance(data, dict):
            return {k: JSONProcessor.clean_json(v) for k, v in data.items() if v is not None}
        elif isinstance(data, list):
            return [JSONProcessor.clean_json(item) for item in data if item is not None]
        else:
            return data

class MetricsCalculator:
    """Calculate derived metrics from raw data"""

    @staticmethod
    def calculate_ctr(impressions: int, clicks: int) -> float:
        """Calculate Click-Through Rate"""
        if impressions == 0:
            return 0.0
        return (clicks / impressions) * 100

    @staticmethod
    def calculate_cpc(spend: float, clicks: int) -> float:
        """Calculate Cost Per Click"""
        if clicks == 0:
            return 0.0
        return spend / clicks

    @staticmethod
    def calculate_cpm(spend: float, impressions: int) -> float:
        """Calculate Cost Per Mille (1000 impressions)"""
        if impressions == 0:
            return 0.0
        return (spend / impressions) * 1000

    @staticmethod
    def calculate_conversion_rate(conversions: int, clicks: int) -> float:
        """Calculate Conversion Rate"""
        if clicks == 0:
            return 0.0
        return (conversions / clicks) * 100

    @staticmethod
    def calculate_cpa(spend: float, conversions: int) -> float:
        """Calculate Cost Per Acquisition"""
        if conversions == 0:
            return 0.0
        return spend / conversions

    @staticmethod
    def calculate_roas(revenue: float, spend: float) -> float:
        """Calculate Return on Ad Spend"""
        if spend == 0:
            return 0.0
        return revenue / spend

    @staticmethod
    def process_metrics(raw_data: Dict) -> Dict:
        """Process raw data and calculate all metrics"""
        try:
            impressions = raw_data.get('impressions', 0)
            clicks = raw_data.get('clicks', 0)
            spend = float(raw_data.get('spend', 0))
            conversions = raw_data.get('conversions', 0)
            revenue = float(raw_data.get('revenue', 0))

            return {
                # Raw metrics
                'impressions': impressions,
                'clicks': clicks,
                'spend': spend,
                'conversions': conversions,
                'revenue': revenue,

                # Calculated metrics
                'ctr': MetricsCalculator.calculate_ctr(impressions, clicks),
                'cpc': MetricsCalculator.calculate_cpc(spend, clicks),
                'cpm': MetricsCalculator.calculate_cpm(spend, impressions),
                'conversion_rate': MetricsCalculator.calculate_conversion_rate(conversions, clicks),
                'cpa': MetricsCalculator.calculate_cpa(spend, conversions),
                'roas': MetricsCalculator.calculate_roas(revenue, spend),

                # 1-day metrics (if available)
                '1_day_clicks': raw_data.get('1_day_clicks', 0),
                '1_day_views': raw_data.get('1_day_views', 0),

                # Metadata
                'timestamp': raw_data.get('timestamp', datetime.now().isoformat()),
                'processed_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error processing metrics: {str(e)}")
            return {}

class DataValidator:
    """Validate data quality and integrity"""

    @staticmethod
    def validate_metrics(metrics: Dict) -> Dict:
        """Validate metrics and flag anomalies"""
        issues = []

        # Check for impossible values
        if metrics.get('ctr', 0) > 100:
            issues.append('CTR exceeds 100%')

        if metrics.get('conversion_rate', 0) > 100:
            issues.append('Conversion rate exceeds 100%')

        # Check for negative values
        for key in ['impressions', 'clicks', 'spend', 'conversions']:
            if metrics.get(key, 0) < 0:
                issues.append(f'Negative value for {key}')

        # Check for data completeness
        required_fields = ['impressions', 'clicks', 'spend']
        missing = [f for f in required_fields if f not in metrics]
        if missing:
            issues.append(f'Missing required fields: {", ".join(missing)}')

        # Check for suspiciously high CPC
        if metrics.get('cpc', 0) > 50:
            issues.append('Unusually high CPC (>$50)')

        # Check for suspiciously high frequency
        if metrics.get('frequency', 0) > 10:
            issues.append('Very high frequency (>10) - possible ad fatigue')

        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'severity': 'high' if len(issues) > 2 else 'low'
        }

    @staticmethod
    def check_data_freshness(timestamp_str: str, max_age_hours: int = 24) -> bool:
        """Check if data is fresh enough"""
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            age_hours = (datetime.now() - timestamp).total_seconds() / 3600

            return age_hours <= max_age_hours

        except Exception:
            return False

class DataAggregator:
    """Aggregate data from multiple sources"""

    @staticmethod
    def aggregate_campaign_data(adsets: List[Dict]) -> Dict:
        """Aggregate adset data to campaign level"""
        try:
            aggregated = {
                'impressions': 0,
                'clicks': 0,
                'spend': 0.0,
                'conversions': 0,
                '1_day_clicks': 0,
                '1_day_views': 0,
                'reach': 0,
                'adset_count': len(adsets)
            }

            for adset in adsets:
                for key in ['impressions', 'clicks', 'conversions', '1_day_clicks', '1_day_views', 'reach']:
                    aggregated[key] += adset.get(key, 0)

                aggregated['spend'] += float(adset.get('spend', 0))

            # Calculate derived metrics
            return MetricsCalculator.process_metrics(aggregated)

        except Exception as e:
            logger.error(f"Error aggregating campaign data: {str(e)}")
            return {}

    @staticmethod
    def aggregate_time_series(data_points: List[Dict], interval: str = 'daily') -> List[Dict]:
        """Aggregate time-series data by interval"""
        try:
            # Group by date
            grouped = {}

            for point in data_points:
                timestamp = point.get('timestamp', '')
                date_key = timestamp.split('T')[0]  # Get date part

                if date_key not in grouped:
                    grouped[date_key] = []

                grouped[date_key].append(point)

            # Aggregate each group
            result = []
            for date_key, points in sorted(grouped.items()):
                aggregated = DataAggregator.aggregate_campaign_data(points)
                aggregated['date'] = date_key
                result.append(aggregated)

            return result

        except Exception as e:
            logger.error(f"Error aggregating time series: {str(e)}")
            return []

def format_currency(amount: float, currency: str = 'USD') -> str:
    """Format currency for display"""
    symbols = {'USD': '$', 'EUR': '€', 'GBP': '£'}
    symbol = symbols.get(currency, currency)
    return f"{symbol}{amount:.2f}"

def format_percentage(value: float, decimals: int = 2) -> str:
    """Format percentage for display"""
    return f"{value:.{decimals}f}%"

def format_number(value: int) -> str:
    """Format large numbers with commas"""
    return f"{value:,}"

# Example usage
if __name__ == '__main__':
    # Test JSON processor
    test_data = {
        'impressions': 10000,
        'clicks': 500,
        'spend': 100.0,
        'conversions': 50
    }

    metrics = MetricsCalculator.process_metrics(test_data)
    validation = DataValidator.validate_metrics(metrics)

    print("✅ Utility scripts initialized")
    print(f"   Processed metrics: {len(metrics)} fields")
    print(f"   Data valid: {validation['is_valid']}")
    print(f"   CTR: {format_percentage(metrics['ctr'])}")
    print(f"   CPC: {format_currency(metrics['cpc'])}")
