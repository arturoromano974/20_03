"""
Bayesian Model for Campaign Optimization

This module implements a Bayesian model for:
1. Probability estimation for campaign success
2. Sensitivity to micro-changes in metrics
3. Focus on 1-day click/view conversions
4. Confidence intervals and statistical significance
"""

import json
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from scipy import stats
from scipy.stats import beta, norm
from utils.config_loader import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
config = load_config()

class BayesianOptimizer:
    """Bayesian model for campaign optimization"""

    def __init__(self):
        self.prior_strength = config['machine_learning']['bayesian_model']['prior_strength']
        self.sensitivity = config['machine_learning']['bayesian_model']['sensitivity']
        self.focus_metric = config['machine_learning']['bayesian_model']['focus_metric']

    def estimate_conversion_probability(self, conversions: int, trials: int,
                                       prior_alpha: float = 2.0,
                                       prior_beta: float = 98.0) -> Dict:
        """
        Estimate conversion probability using Bayesian inference

        Args:
            conversions: Number of successful conversions
            trials: Number of total trials (clicks)
            prior_alpha: Prior successes (beta distribution)
            prior_beta: Prior failures (beta distribution)

        Returns:
            Dictionary with probability estimates and confidence intervals
        """
        try:
            if trials == 0:
                return {
                    'mean': 0.0,
                    'median': 0.0,
                    'mode': 0.0,
                    'ci_lower': 0.0,
                    'ci_upper': 0.0,
                    'std': 0.0
                }

            # Update posterior parameters
            failures = trials - conversions
            posterior_alpha = prior_alpha + conversions
            posterior_beta = prior_beta + failures

            # Calculate statistics
            mean = posterior_alpha / (posterior_alpha + posterior_beta)
            mode = (posterior_alpha - 1) / (posterior_alpha + posterior_beta - 2) if posterior_alpha > 1 and posterior_beta > 1 else mean

            # 95% Credible interval
            ci_lower = beta.ppf(0.025, posterior_alpha, posterior_beta)
            ci_upper = beta.ppf(0.975, posterior_alpha, posterior_beta)

            # Standard deviation
            variance = (posterior_alpha * posterior_beta) / ((posterior_alpha + posterior_beta) ** 2 * (posterior_alpha + posterior_beta + 1))
            std = np.sqrt(variance)

            return {
                'mean': float(mean),
                'median': float(beta.median(posterior_alpha, posterior_beta)),
                'mode': float(mode),
                'ci_lower': float(ci_lower),
                'ci_upper': float(ci_upper),
                'std': float(std),
                'posterior_alpha': float(posterior_alpha),
                'posterior_beta': float(posterior_beta)
            }

        except Exception as e:
            logger.error(f"Error estimating conversion probability: {str(e)}")
            return {
                'mean': 0.0,
                'median': 0.0,
                'mode': 0.0,
                'ci_lower': 0.0,
                'ci_upper': 0.0,
                'std': 0.0
            }

    def calculate_improvement_probability(self, conversions_a: int, trials_a: int,
                                         conversions_b: int, trials_b: int) -> Dict:
        """
        Calculate probability that variant B is better than variant A

        Used for A/B testing and optimization decisions
        """
        try:
            # Get posterior distributions
            dist_a = self.estimate_conversion_probability(conversions_a, trials_a)
            dist_b = self.estimate_conversion_probability(conversions_b, trials_b)

            # Monte Carlo simulation to calculate P(B > A)
            n_samples = 10000
            samples_a = beta.rvs(
                dist_a['posterior_alpha'],
                dist_a['posterior_beta'],
                size=n_samples
            )
            samples_b = beta.rvs(
                dist_b['posterior_alpha'],
                dist_b['posterior_beta'],
                size=n_samples
            )

            prob_b_better = np.mean(samples_b > samples_a)

            # Expected lift
            expected_lift = (dist_b['mean'] - dist_a['mean']) / max(dist_a['mean'], 0.0001)

            # Is significant? (> 95% probability)
            is_significant = prob_b_better > 0.95 or prob_b_better < 0.05

            return {
                'prob_b_better': float(prob_b_better),
                'prob_a_better': float(1 - prob_b_better),
                'expected_lift': float(expected_lift),
                'is_significant': bool(is_significant),
                'confidence': 'high' if is_significant else 'low',
                'recommendation': self._get_recommendation(prob_b_better, expected_lift)
            }

        except Exception as e:
            logger.error(f"Error calculating improvement probability: {str(e)}")
            return {
                'prob_b_better': 0.5,
                'prob_a_better': 0.5,
                'expected_lift': 0.0,
                'is_significant': False,
                'confidence': 'low',
                'recommendation': 'continue_testing'
            }

    def calculate_micro_sensitivity(self, metrics_history: List[Dict]) -> Dict:
        """
        Calculate sensitivity to micro-changes in metrics

        Analyzes how responsive the campaign is to small changes
        Focus on 1-day metrics as per requirements
        """
        try:
            if len(metrics_history) < 2:
                return {
                    'sensitivity_score': 0.0,
                    'responsiveness': 'unknown',
                    'micro_changes_detected': 0
                }

            # Extract 1-day metrics
            one_day_clicks = [m.get('1_day_clicks', 0) for m in metrics_history]
            one_day_views = [m.get('1_day_views', 0) for m in metrics_history]

            # Calculate changes
            click_changes = np.diff(one_day_clicks)
            view_changes = np.diff(one_day_views)

            # Calculate coefficient of variation (normalized volatility)
            click_cv = np.std(click_changes) / max(np.mean(one_day_clicks), 1) if len(one_day_clicks) > 0 else 0
            view_cv = np.std(view_changes) / max(np.mean(one_day_views), 1) if len(one_day_views) > 0 else 0

            # Sensitivity score (0-1, higher = more sensitive)
            sensitivity_score = min((click_cv + view_cv) / 2, 1.0)

            # Count micro-changes (changes < 10%)
            micro_changes = sum(1 for c in click_changes if abs(c) / max(np.mean(one_day_clicks), 1) < 0.1)

            # Classify responsiveness
            if sensitivity_score > 0.7:
                responsiveness = 'high'
            elif sensitivity_score > 0.3:
                responsiveness = 'medium'
            else:
                responsiveness = 'low'

            return {
                'sensitivity_score': float(sensitivity_score),
                'responsiveness': responsiveness,
                'micro_changes_detected': int(micro_changes),
                'click_volatility': float(click_cv),
                'view_volatility': float(view_cv),
                'recommendation': self._get_sensitivity_recommendation(sensitivity_score)
            }

        except Exception as e:
            logger.error(f"Error calculating micro-sensitivity: {str(e)}")
            return {
                'sensitivity_score': 0.0,
                'responsiveness': 'unknown',
                'micro_changes_detected': 0
            }

    def predict_future_performance(self, metrics_history: List[Dict],
                                   periods_ahead: int = 1) -> Dict:
        """
        Predict future performance using Bayesian time series

        Args:
            metrics_history: Historical metrics
            periods_ahead: Number of periods to predict (default 1 = next period)
        """
        try:
            if len(metrics_history) < 3:
                return {
                    'predicted_conversions': 0,
                    'predicted_clicks': 0,
                    'ci_lower': 0,
                    'ci_upper': 0,
                    'confidence': 'low'
                }

            # Extract conversion rates
            conversion_rates = []
            for m in metrics_history:
                clicks = m.get('clicks', 0)
                conversions = m.get('conversions', 0)
                if clicks > 0:
                    conversion_rates.append(conversions / clicks)

            if not conversion_rates:
                return {
                    'predicted_conversions': 0,
                    'predicted_clicks': 0,
                    'ci_lower': 0,
                    'ci_upper': 0,
                    'confidence': 'low'
                }

            # Calculate trend
            x = np.arange(len(conversion_rates))
            coeffs = np.polyfit(x, conversion_rates, 1)  # Linear trend

            # Predict next period
            next_x = len(conversion_rates) + periods_ahead - 1
            predicted_rate = coeffs[0] * next_x + coeffs[1]

            # Calculate prediction interval
            residuals = conversion_rates - (coeffs[0] * x + coeffs[1])
            std_residual = np.std(residuals)

            # 95% prediction interval
            ci_lower = predicted_rate - 1.96 * std_residual
            ci_upper = predicted_rate + 1.96 * std_residual

            # Estimate clicks (use moving average)
            recent_clicks = [m.get('clicks', 0) for m in metrics_history[-5:]]
            predicted_clicks = int(np.mean(recent_clicks))

            # Calculate predicted conversions
            predicted_conversions = int(predicted_rate * predicted_clicks)

            return {
                'predicted_conversions': predicted_conversions,
                'predicted_clicks': predicted_clicks,
                'predicted_conversion_rate': float(predicted_rate),
                'ci_lower': float(ci_lower * predicted_clicks),
                'ci_upper': float(ci_upper * predicted_clicks),
                'confidence': 'high' if len(metrics_history) > 10 else 'medium',
                'trend': 'increasing' if coeffs[0] > 0 else 'decreasing'
            }

        except Exception as e:
            logger.error(f"Error predicting future performance: {str(e)}")
            return {
                'predicted_conversions': 0,
                'predicted_clicks': 0,
                'ci_lower': 0,
                'ci_upper': 0,
                'confidence': 'low'
            }

    def _get_recommendation(self, prob_b_better: float, expected_lift: float) -> str:
        """Get recommendation based on probability and lift"""
        if prob_b_better > 0.95:
            if expected_lift > 0.1:  # >10% lift
                return 'scale_variant_b'
            else:
                return 'implement_variant_b'
        elif prob_b_better < 0.05:
            return 'scale_variant_a'
        else:
            return 'continue_testing'

    def _get_sensitivity_recommendation(self, sensitivity_score: float) -> str:
        """Get recommendation based on sensitivity"""
        if sensitivity_score > 0.7:
            return 'optimize_for_stability'
        elif sensitivity_score < 0.3:
            return 'increase_experimentation'
        else:
            return 'continue_monitoring'

def create_bayesian_optimizer() -> BayesianOptimizer:
    """Factory function to create Bayesian optimizer"""
    return BayesianOptimizer()

if __name__ == '__main__':
    # Test the Bayesian optimizer
    optimizer = create_bayesian_optimizer()

    # Test conversion probability estimation
    result = optimizer.estimate_conversion_probability(
        conversions=50,
        trials=1000
    )

    print("✅ Bayesian optimizer initialized")
    print(f"   Test result: {result['mean']:.2%} conversion rate")
    print(f"   95% CI: [{result['ci_lower']:.2%}, {result['ci_upper']:.2%}]")
