"""
Machine Learning Models for Campaign Optimization

This module implements ML models for:
1. Performance prediction
2. Budget optimization
3. Feature importance analysis
4. Automated decision making
5. Focus on 1-day click/view metrics
"""

import json
import logging
import numpy as np
import pickle
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
with open('/home/runner/work/20_03/20_03/config/config.json', 'r') as f:
    config = json.load(f)

class MLOptimizer:
    """Machine Learning optimizer for campaign performance"""

    def __init__(self):
        self.algorithm = config['machine_learning']['ml_model']['algorithm']
        self.features = config['machine_learning']['ml_model']['features']
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False

    def prepare_features(self, metrics: Dict) -> np.ndarray:
        """Prepare feature vector from metrics"""
        try:
            feature_vector = []

            for feature_name in self.features:
                value = metrics.get(feature_name, 0)

                # Special handling for derived features
                if feature_name == '1_day_click':
                    value = metrics.get('1_day_clicks', 0)
                elif feature_name == '1_day_view':
                    value = metrics.get('1_day_views', 0)

                feature_vector.append(float(value))

            return np.array(feature_vector).reshape(1, -1)

        except Exception as e:
            logger.error(f"Error preparing features: {str(e)}")
            return np.zeros((1, len(self.features)))

    def train_model(self, training_data: List[Dict]) -> bool:
        """
        Train the ML model on historical data

        Args:
            training_data: List of dictionaries with metrics and target
        """
        try:
            if len(training_data) < 10:
                logger.warning("Insufficient training data (< 10 samples)")
                return False

            # Prepare features and targets
            X = []
            y = []

            for data in training_data:
                features = self.prepare_features(data)
                X.append(features.flatten())

                # Target: 1-day conversion rate
                clicks = data.get('clicks', 1)
                one_day_conversions = data.get('1_day_clicks', 0) + data.get('1_day_views', 0) * 0.3
                target = one_day_conversions / max(clicks, 1)
                y.append(target)

            X = np.array(X)
            y = np.array(y)

            # Scale features
            X_scaled = self.scaler.fit_transform(X)

            # Train model
            if self.algorithm == 'gradient_boosting':
                self.model = GradientBoostingRegressor(
                    n_estimators=100,
                    learning_rate=0.1,
                    max_depth=4,
                    random_state=42
                )
            else:
                self.model = GradientBoostingRegressor()

            self.model.fit(X_scaled, y)
            self.is_trained = True

            logger.info(f"Model trained on {len(training_data)} samples")
            return True

        except Exception as e:
            logger.error(f"Error training model: {str(e)}")
            return False

    def predict_performance(self, metrics: Dict) -> Dict:
        """
        Predict future performance based on current metrics

        Returns predictions for 1-day conversions
        """
        try:
            if not self.is_trained:
                logger.warning("Model not trained yet, using baseline predictions")
                return self._baseline_prediction(metrics)

            # Prepare features
            features = self.prepare_features(metrics)
            features_scaled = self.scaler.transform(features)

            # Make prediction
            predicted_rate = self.model.predict(features_scaled)[0]

            # Calculate confidence (based on feature importance)
            confidence = self._calculate_confidence(metrics)

            # Estimate future metrics
            current_clicks = metrics.get('clicks', 0)
            predicted_1day_conversions = int(predicted_rate * current_clicks)

            return {
                'predicted_1day_conversion_rate': float(predicted_rate),
                'predicted_1day_conversions': predicted_1day_conversions,
                'confidence': confidence,
                'model_score': float(self.model.score(features_scaled, [predicted_rate])) if hasattr(self.model, 'score') else 0.0
            }

        except Exception as e:
            logger.error(f"Error predicting performance: {str(e)}")
            return self._baseline_prediction(metrics)

    def recommend_budget(self, metrics: Dict, current_budget: float,
                        max_increase: float = 0.2) -> Dict:
        """
        Recommend budget adjustments based on performance

        Args:
            metrics: Current metrics
            current_budget: Current daily budget
            max_increase: Maximum allowed increase (default 20%)

        Returns:
            Budget recommendation with reasoning
        """
        try:
            # Get performance prediction
            prediction = self.predict_performance(metrics)

            # Calculate performance score
            performance_score = self._calculate_performance_score(metrics)

            # Determine budget adjustment
            if performance_score > 0.7 and prediction['confidence'] == 'high':
                # Scale up
                adjustment = max_increase
                action = 'increase'
                reason = 'High performance with high confidence'
            elif performance_score < 0.3:
                # Scale down
                adjustment = -0.3  # 30% decrease
                action = 'decrease'
                reason = 'Low performance'
            elif performance_score < 0.5:
                # Small decrease
                adjustment = -0.1  # 10% decrease
                action = 'decrease'
                reason = 'Below average performance'
            else:
                # Maintain
                adjustment = 0.0
                action = 'maintain'
                reason = 'Stable performance'

            new_budget = current_budget * (1 + adjustment)

            return {
                'current_budget': float(current_budget),
                'recommended_budget': float(new_budget),
                'adjustment_pct': float(adjustment * 100),
                'action': action,
                'reason': reason,
                'performance_score': float(performance_score),
                'confidence': prediction['confidence']
            }

        except Exception as e:
            logger.error(f"Error recommending budget: {str(e)}")
            return {
                'current_budget': float(current_budget),
                'recommended_budget': float(current_budget),
                'adjustment_pct': 0.0,
                'action': 'maintain',
                'reason': 'Error in calculation',
                'performance_score': 0.0,
                'confidence': 'low'
            }

    def get_feature_importance(self) -> Dict:
        """Get feature importance from trained model"""
        try:
            if not self.is_trained or not hasattr(self.model, 'feature_importances_'):
                return {}

            importances = self.model.feature_importances_

            # Create dictionary of feature: importance
            feature_importance = {}
            for i, feature_name in enumerate(self.features):
                feature_importance[feature_name] = float(importances[i])

            # Sort by importance
            sorted_features = sorted(
                feature_importance.items(),
                key=lambda x: x[1],
                reverse=True
            )

            return {
                'features': dict(sorted_features),
                'top_3': [f[0] for f in sorted_features[:3]]
            }

        except Exception as e:
            logger.error(f"Error getting feature importance: {str(e)}")
            return {}

    def should_pause_campaign(self, metrics: Dict, threshold: float = -0.5) -> Dict:
        """
        Determine if campaign should be paused

        Args:
            metrics: Current metrics
            threshold: Performance threshold for pausing (default -0.5 = 50% below target)

        Returns:
            Decision with reasoning
        """
        try:
            # Calculate performance score
            score = self._calculate_performance_score(metrics)

            # Get prediction
            prediction = self.predict_performance(metrics)

            # Decision logic
            should_pause = False
            reason = []

            if score < 0.2:
                should_pause = True
                reason.append('Very low performance score')

            if metrics.get('cpc', 0) > 5.0:  # High CPC
                should_pause = True
                reason.append('CPC too high')

            if metrics.get('frequency', 0) > 4.0:  # High frequency
                should_pause = True
                reason.append('Ad fatigue detected')

            # Check 1-day metrics
            one_day_ratio = metrics.get('1_day_clicks', 0) / max(metrics.get('clicks', 1), 1)
            if one_day_ratio < 0.3:
                should_pause = True
                reason.append('Low 1-day conversion ratio')

            return {
                'should_pause': bool(should_pause),
                'reasons': reason,
                'performance_score': float(score),
                'confidence': prediction['confidence'],
                'alternative_action': 'optimize_creative' if not should_pause else None
            }

        except Exception as e:
            logger.error(f"Error determining pause decision: {str(e)}")
            return {
                'should_pause': False,
                'reasons': ['Error in calculation'],
                'performance_score': 0.0,
                'confidence': 'low'
            }

    def _baseline_prediction(self, metrics: Dict) -> Dict:
        """Baseline prediction when model is not trained"""
        clicks = metrics.get('clicks', 0)
        one_day_clicks = metrics.get('1_day_clicks', 0)
        one_day_views = metrics.get('1_day_views', 0)

        # Simple average
        current_rate = (one_day_clicks + one_day_views * 0.3) / max(clicks, 1)

        return {
            'predicted_1day_conversion_rate': float(current_rate),
            'predicted_1day_conversions': int(current_rate * clicks),
            'confidence': 'low',
            'model_score': 0.0
        }

    def _calculate_performance_score(self, metrics: Dict) -> float:
        """Calculate overall performance score (0-1)"""
        try:
            # Normalize metrics
            ctr = min(metrics.get('ctr', 0) / 10.0, 1.0)  # 10% CTR = 1.0
            conversion_rate = min(metrics.get('conversion_rate', 0) / 10.0, 1.0)  # 10% CR = 1.0
            one_day_ratio = metrics.get('1_day_clicks', 0) / max(metrics.get('clicks', 1), 1)

            # Weighted score (emphasis on 1-day metrics)
            score = (
                ctr * 0.25 +
                conversion_rate * 0.30 +
                one_day_ratio * 0.35 +
                (1 - min(metrics.get('cpc', 5) / 10.0, 1.0)) * 0.10  # Lower CPC is better
            )

            return min(max(score, 0.0), 1.0)

        except Exception as e:
            logger.error(f"Error calculating performance score: {str(e)}")
            return 0.0

    def _calculate_confidence(self, metrics: Dict) -> str:
        """Calculate prediction confidence"""
        # Check data quality
        impressions = metrics.get('impressions', 0)
        clicks = metrics.get('clicks', 0)

        if impressions > 10000 and clicks > 100:
            return 'high'
        elif impressions > 1000 and clicks > 10:
            return 'medium'
        else:
            return 'low'

    def save_model(self, filepath: str) -> bool:
        """Save trained model to file"""
        try:
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'features': self.features,
                'is_trained': self.is_trained,
                'timestamp': datetime.now().isoformat()
            }

            with open(filepath, 'wb') as f:
                pickle.dump(model_data, f)

            logger.info(f"Model saved to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error saving model: {str(e)}")
            return False

    def load_model(self, filepath: str) -> bool:
        """Load trained model from file"""
        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)

            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.features = model_data['features']
            self.is_trained = model_data['is_trained']

            logger.info(f"Model loaded from {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            return False

def create_ml_optimizer() -> MLOptimizer:
    """Factory function to create ML optimizer"""
    return MLOptimizer()

if __name__ == '__main__':
    # Test the ML optimizer
    optimizer = create_ml_optimizer()

    # Test with sample metrics
    test_metrics = {
        'impressions': 10000,
        'clicks': 500,
        'spend': 100.0,
        'conversions': 50,
        'ctr': 5.0,
        'cpc': 0.2,
        'cpm': 10.0,
        '1_day_clicks': 30,
        '1_day_views': 40
    }

    prediction = optimizer.predict_performance(test_metrics)
    budget_rec = optimizer.recommend_budget(test_metrics, 100.0)

    print("✅ ML optimizer initialized")
    print(f"   Prediction confidence: {prediction['confidence']}")
    print(f"   Budget recommendation: {budget_rec['action']} by {budget_rec['adjustment_pct']:.1f}%")
