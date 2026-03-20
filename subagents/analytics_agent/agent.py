"""
Analytics & Optimization Agent (GPT-5.4-Nano)

This agent is responsible for:
1. Fetching performance data every 12h/24h
2. Analyzing metrics using JSON processing (no raw analysis)
3. Applying Bayesian and ML models
4. Reallocating budget based on 1-day click/view performance
"""

import os
import json
import logging
from typing import Dict, List, Optional
from flask import Flask, request, jsonify
import openai
import redis
import numpy as np
from datetime import datetime, timedelta
from utils.config_loader import load_config

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
config = load_config()

# Initialize OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

# Initialize Redis
redis_client = redis.Redis(
    host=config['redis']['host'],
    port=config['redis']['port'],
    db=config['redis']['db'],
    decode_responses=True
)

class AnalyticsAgent:
    def __init__(self):
        self.model = config['subagents']['analytics_agent']['model']
        self.temperature = config['subagents']['analytics_agent']['temperature']
        self.max_tokens = config['subagents']['analytics_agent']['max_tokens']

    def analyze_performance(self, task_data: Dict) -> Dict:
        """Analyze campaign performance using structured JSON processing"""
        try:
            campaign_id = task_data.get('campaign_id')
            adset_ids = task_data.get('adset_ids', [])
            ad_ids = task_data.get('ad_ids', [])

            # Fetch performance data from cache
            performance_data = self._fetch_performance_data(
                campaign_id, adset_ids, ad_ids
            )

            if not performance_data:
                return {
                    'status': 'error',
                    'error': 'No performance data available'
                }

            # Process data with structured JSON (no raw LLM analysis)
            processed_metrics = self._process_metrics_json(performance_data)

            # Apply Bayesian model
            bayesian_predictions = self._apply_bayesian_model(processed_metrics)

            # Apply ML model
            ml_recommendations = self._apply_ml_model(processed_metrics)

            # Generate optimization recommendations
            optimization_plan = self._generate_optimization_plan(
                processed_metrics,
                bayesian_predictions,
                ml_recommendations
            )

            # Cache results
            result_id = f"analysis_{datetime.now().timestamp()}"
            result_data = {
                'id': result_id,
                'campaign_id': campaign_id,
                'metrics': processed_metrics,
                'bayesian': bayesian_predictions,
                'ml_recommendations': ml_recommendations,
                'optimization_plan': optimization_plan,
                'timestamp': datetime.now().isoformat()
            }

            redis_client.setex(
                f'analysis:{result_id}',
                config['redis']['ttl'],
                json.dumps(result_data)
            )

            logger.info(f"Completed analysis: {result_id}")

            return {
                'status': 'success',
                'analysis_id': result_id,
                'optimization_plan': optimization_plan,
                'key_insights': self._extract_key_insights(result_data)
            }

        except Exception as e:
            logger.error(f"Error analyzing performance: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def _fetch_performance_data(self, campaign_id: str,
                                adset_ids: List[str],
                                ad_ids: List[str]) -> Dict:
        """Fetch performance data from cache/storage"""
        try:
            data = {
                'campaign': {},
                'adsets': [],
                'ads': []
            }

            # Fetch campaign data
            if campaign_id:
                campaign_data = redis_client.get(f'performance:{campaign_id}')
                if campaign_data:
                    data['campaign'] = json.loads(campaign_data)

            # Fetch adset data
            for adset_id in adset_ids:
                adset_data = redis_client.get(f'performance:adset:{adset_id}')
                if adset_data:
                    data['adsets'].append(json.loads(adset_data))

            # Fetch ad data
            for ad_id in ad_ids:
                ad_data = redis_client.get(f'performance:ad:{ad_id}')
                if ad_data:
                    data['ads'].append(json.loads(ad_data))

            return data

        except Exception as e:
            logger.error(f"Error fetching performance data: {str(e)}")
            return {}

    def _process_metrics_json(self, performance_data: Dict) -> Dict:
        """Process metrics using structured JSON (no raw analysis)"""
        try:
            # Extract key metrics
            metrics = {
                'impressions': 0,
                'clicks': 0,
                'spend': 0.0,
                'conversions': 0,
                'ctr': 0.0,
                'cpc': 0.0,
                'cpm': 0.0,
                'conversion_rate': 0.0,
                '1_day_clicks': 0,
                '1_day_views': 0,
                'frequency': 0.0,
                'reach': 0
            }

            # Aggregate metrics from all levels
            for level in ['campaign', 'adsets', 'ads']:
                level_data = performance_data.get(level, {})
                if isinstance(level_data, list):
                    for item in level_data:
                        metrics = self._aggregate_metrics(metrics, item)
                elif isinstance(level_data, dict):
                    metrics = self._aggregate_metrics(metrics, level_data)

            # Calculate derived metrics
            if metrics['impressions'] > 0:
                metrics['ctr'] = (metrics['clicks'] / metrics['impressions']) * 100
                metrics['cpm'] = (metrics['spend'] / metrics['impressions']) * 1000

            if metrics['clicks'] > 0:
                metrics['cpc'] = metrics['spend'] / metrics['clicks']
                metrics['conversion_rate'] = (metrics['conversions'] / metrics['clicks']) * 100

            return metrics

        except Exception as e:
            logger.error(f"Error processing metrics: {str(e)}")
            return {}

    def _aggregate_metrics(self, current: Dict, new_data: Dict) -> Dict:
        """Aggregate metrics from different sources"""
        for key in ['impressions', 'clicks', 'spend', 'conversions',
                   '1_day_clicks', '1_day_views', 'reach']:
            if key in new_data:
                current[key] += new_data[key]

        # Update frequency (average)
        if 'frequency' in new_data and new_data['frequency'] > 0:
            current['frequency'] = (current['frequency'] + new_data['frequency']) / 2

        return current

    def _apply_bayesian_model(self, metrics: Dict) -> Dict:
        """Apply Bayesian model for probability estimation"""
        try:
            # Simple Bayesian inference for conversion probability
            # In production, use PyMC3 or similar

            # Prior parameters (from historical data)
            alpha_prior = 2.0  # successful conversions
            beta_prior = 98.0  # unsuccessful conversions

            # Update with current data
            successes = metrics.get('conversions', 0)
            trials = metrics.get('clicks', 0)
            failures = trials - successes

            # Posterior parameters
            alpha_posterior = alpha_prior + successes
            beta_posterior = beta_prior + failures

            # Expected conversion rate
            expected_conversion_rate = alpha_posterior / (alpha_posterior + beta_posterior)

            # Confidence interval (95%)
            # Using beta distribution properties
            from scipy import stats
            ci_lower = stats.beta.ppf(0.025, alpha_posterior, beta_posterior)
            ci_upper = stats.beta.ppf(0.975, alpha_posterior, beta_posterior)

            # Probability of improvement
            baseline_conversion_rate = alpha_prior / (alpha_prior + beta_prior)
            prob_improvement = 1 - stats.beta.cdf(
                baseline_conversion_rate,
                alpha_posterior,
                beta_posterior
            )

            return {
                'expected_conversion_rate': float(expected_conversion_rate),
                'confidence_interval': {
                    'lower': float(ci_lower),
                    'upper': float(ci_upper)
                },
                'probability_of_improvement': float(prob_improvement),
                'is_significant': prob_improvement > 0.95,
                'sensitivity_score': self._calculate_sensitivity(metrics)
            }

        except Exception as e:
            logger.error(f"Error in Bayesian model: {str(e)}")
            return {
                'expected_conversion_rate': 0.0,
                'confidence_interval': {'lower': 0.0, 'upper': 0.0},
                'probability_of_improvement': 0.0,
                'is_significant': False,
                'sensitivity_score': 0.0
            }

    def _calculate_sensitivity(self, metrics: Dict) -> float:
        """Calculate sensitivity to micro-changes (0-1 scale)"""
        try:
            # Focus on 1-day metrics as per requirements
            one_day_clicks = metrics.get('1_day_clicks', 0)
            one_day_views = metrics.get('1_day_views', 0)
            total_clicks = metrics.get('clicks', 1)  # Avoid division by zero

            # Calculate sensitivity score
            one_day_ratio = (one_day_clicks + one_day_views * 0.3) / max(total_clicks, 1)

            # Normalize to 0-1
            sensitivity = min(one_day_ratio * 2, 1.0)

            return float(sensitivity)

        except Exception as e:
            logger.error(f"Error calculating sensitivity: {str(e)}")
            return 0.0

    def _apply_ml_model(self, metrics: Dict) -> Dict:
        """Apply ML model for recommendations"""
        try:
            # In production, use trained ML model (scikit-learn, XGBoost, etc.)
            # For now, use rule-based system with ML-like scoring

            features = np.array([
                metrics.get('ctr', 0),
                metrics.get('cpc', 0),
                metrics.get('conversion_rate', 0),
                metrics.get('1_day_clicks', 0) / max(metrics.get('clicks', 1), 1),
                metrics.get('frequency', 0)
            ])

            # Normalize features (0-1)
            normalized = self._normalize_features(features)

            # Calculate performance score
            weights = np.array([0.25, 0.15, 0.30, 0.25, 0.05])  # Focus on conversions and 1-day metrics
            performance_score = float(np.dot(normalized, weights))

            # Generate recommendations based on score
            recommendations = []

            if performance_score < 0.3:
                recommendations.append({
                    'action': 'pause',
                    'reason': 'Low performance score',
                    'priority': 'high'
                })
            elif performance_score < 0.5:
                recommendations.append({
                    'action': 'optimize',
                    'reason': 'Below average performance',
                    'priority': 'medium'
                })
            elif performance_score > 0.7:
                recommendations.append({
                    'action': 'scale',
                    'reason': 'High performance',
                    'priority': 'high',
                    'suggested_budget_increase': 0.2  # 20% increase
                })

            # Check frequency
            if metrics.get('frequency', 0) > 3.0:
                recommendations.append({
                    'action': 'refresh_creative',
                    'reason': 'High frequency causing ad fatigue',
                    'priority': 'medium'
                })

            # Check 1-day metrics
            one_day_ratio = metrics.get('1_day_clicks', 0) / max(metrics.get('clicks', 1), 1)
            if one_day_ratio < 0.5:
                recommendations.append({
                    'action': 'optimize_for_immediate_action',
                    'reason': 'Low 1-day conversion ratio',
                    'priority': 'medium'
                })

            return {
                'performance_score': performance_score,
                'recommendations': recommendations,
                'predicted_cpa': self._predict_cpa(metrics),
                'predicted_roas': self._predict_roas(metrics)
            }

        except Exception as e:
            logger.error(f"Error in ML model: {str(e)}")
            return {
                'performance_score': 0.0,
                'recommendations': [],
                'predicted_cpa': 0.0,
                'predicted_roas': 0.0
            }

    def _normalize_features(self, features: np.ndarray) -> np.ndarray:
        """Normalize features to 0-1 range"""
        # Simple min-max normalization
        # In production, use fitted scaler
        max_vals = np.array([10.0, 5.0, 10.0, 1.0, 5.0])  # Expected max values
        return np.clip(features / max_vals, 0, 1)

    def _predict_cpa(self, metrics: Dict) -> float:
        """Predict Cost Per Acquisition"""
        conversions = metrics.get('conversions', 0)
        spend = metrics.get('spend', 0)

        if conversions > 0:
            return spend / conversions
        return 0.0

    def _predict_roas(self, metrics: Dict) -> float:
        """Predict Return on Ad Spend"""
        # Simplified ROAS calculation
        # In production, use actual revenue data
        conversions = metrics.get('conversions', 0)
        spend = metrics.get('spend', 0)

        if spend > 0:
            # Assume average order value (would be from actual data)
            avg_order_value = 50.0
            revenue = conversions * avg_order_value
            return revenue / spend
        return 0.0

    def _generate_optimization_plan(self, metrics: Dict,
                                   bayesian: Dict,
                                   ml_recommendations: Dict) -> Dict:
        """Generate comprehensive optimization plan using LLM"""
        try:
            # Prepare structured data for LLM
            context = {
                'metrics': metrics,
                'bayesian_analysis': bayesian,
                'ml_recommendations': ml_recommendations
            }

            prompt = f"""Generate an optimization plan based on analytics data.

Data (JSON structured):
{json.dumps(context, indent=2)}

Generate a comprehensive optimization plan with:
1. immediate_actions: Array of actions to take now
2. budget_adjustments: Specific budget changes
3. targeting_recommendations: Targeting optimizations
4. creative_recommendations: Creative refresh suggestions
5. timeline: When to implement each action

Focus on 1-day click/view optimization.
Return ONLY valid JSON.
"""

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a performance marketing optimization expert. Always return valid JSON based on structured data analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"Error generating optimization plan: {str(e)}")
            return {
                'immediate_actions': [],
                'budget_adjustments': {},
                'targeting_recommendations': [],
                'creative_recommendations': [],
                'timeline': '24h'
            }

    def _extract_key_insights(self, result_data: Dict) -> List[str]:
        """Extract key insights from analysis"""
        insights = []

        # Performance insights
        score = result_data.get('ml_recommendations', {}).get('performance_score', 0)
        if score > 0.7:
            insights.append("Campaign is performing well above average")
        elif score < 0.3:
            insights.append("Campaign performance is below expectations")

        # Bayesian insights
        bayesian = result_data.get('bayesian', {})
        if bayesian.get('is_significant'):
            insights.append("Performance improvement is statistically significant")

        # Sensitivity insights
        sensitivity = bayesian.get('sensitivity_score', 0)
        if sensitivity > 0.7:
            insights.append("Campaign is highly responsive to changes")

        return insights

agent = AnalyticsAgent()

@app.route('/analytics-agent', methods=['POST'])
def handle_request():
    """Handle incoming requests from orchestrator"""
    try:
        task_data = request.json
        logger.info(f"Received task: {task_data}")

        task_type = task_data.get('task_type', 'analyze_performance')

        if task_type == 'analyze_performance':
            result = agent.analyze_performance(task_data)
        else:
            result = {
                'status': 'error',
                'error': f'Unknown task type: {task_type}'
            }

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error handling request: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'agent': 'analytics_agent',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = config['subagents']['analytics_agent']['port']
    logger.info(f"Starting Analytics Agent on port {port}")
    app.run(host='0.0.0.0', port=port)
