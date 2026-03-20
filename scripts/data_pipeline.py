"""
Data Collection Pipeline - 12h and 24h Cycles

This script orchestrates the data collection at scheduled intervals:
- 12-hour cycle: Quick optimization
- 24-hour cycle: Deep analysis and strategic decisions
"""

import os
import sys
import json
import logging
import schedule
import time
from datetime import datetime
from typing import Dict, List

# Add project root to path
sys.path.append('/home/runner/work/20_03/20_03')

from cache.redis_utils import create_cache
from models.rag_system import create_rag_system
from models.bayesian_model import create_bayesian_optimizer
from models.ml_optimizer import create_ml_optimizer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load configuration
with open('/home/runner/work/20_03/20_03/config/config.json', 'r') as f:
    config = json.load(f)

class DataCollectionPipeline:
    """Manages 12h and 24h data collection and learning cycles"""

    def __init__(self):
        self.cache = create_cache()
        self.rag = create_rag_system()
        self.bayesian = create_bayesian_optimizer()
        self.ml = create_ml_optimizer()

    def run_12h_cycle(self):
        """12-hour cycle: Quick optimization"""
        logger.info("=" * 60)
        logger.info("Starting 12-hour data collection cycle")
        logger.info("=" * 60)

        try:
            # Get active campaigns
            active_campaigns = self._get_active_campaigns()

            logger.info(f"Processing {len(active_campaigns)} active campaigns")

            for campaign_id in active_campaigns:
                self._process_campaign_quick(campaign_id)

            # Quick ML model update (partial fit)
            self._update_ml_model_quick()

            logger.info("12-hour cycle completed successfully")

        except Exception as e:
            logger.error(f"Error in 12-hour cycle: {str(e)}")

    def run_24h_cycle(self):
        """24-hour cycle: Deep analysis and learning"""
        logger.info("=" * 60)
        logger.info("Starting 24-hour data collection cycle")
        logger.info("=" * 60)

        try:
            # Get all campaigns (including paused)
            all_campaigns = self._get_all_campaigns()

            logger.info(f"Processing {len(all_campaigns)} campaigns for deep analysis")

            for campaign_id in all_campaigns:
                self._process_campaign_deep(campaign_id)

            # Full ML model retraining
            self._retrain_ml_model()

            # Clean up old data
            self._cleanup_old_data()

            logger.info("24-hour cycle completed successfully")

        except Exception as e:
            logger.error(f"Error in 24-hour cycle: {str(e)}")

    def _get_active_campaigns(self) -> List[str]:
        """Get list of active campaign IDs"""
        try:
            # Get from cache
            campaign_keys = self.cache.keys('campaign:*')

            active = []
            for key in campaign_keys:
                campaign_data = self.cache.get(key)
                if campaign_data and campaign_data.get('status') == 'ACTIVE':
                    active.append(campaign_data['id'])

            return active

        except Exception as e:
            logger.error(f"Error getting active campaigns: {str(e)}")
            return []

    def _get_all_campaigns(self) -> List[str]:
        """Get list of all campaign IDs"""
        try:
            campaign_keys = self.cache.keys('campaign:*')

            all_campaigns = []
            for key in campaign_keys:
                campaign_data = self.cache.get(key)
                if campaign_data:
                    all_campaigns.append(campaign_data['id'])

            return all_campaigns

        except Exception as e:
            logger.error(f"Error getting all campaigns: {str(e)}")
            return []

    def _process_campaign_quick(self, campaign_id: str):
        """Quick processing for 12h cycle"""
        try:
            logger.info(f"Processing campaign {campaign_id} (quick)")

            # Get latest performance data
            performance = self.cache.get(f'performance:campaign:{campaign_id}')

            if not performance:
                logger.warning(f"No performance data for campaign {campaign_id}")
                return

            # Quick Bayesian analysis
            conversions = performance.get('conversions', 0)
            clicks = performance.get('clicks', 1)

            bayesian_result = self.bayesian.estimate_conversion_probability(
                conversions, clicks
            )

            # Check for immediate actions needed
            if bayesian_result['mean'] < 0.01:  # < 1% conversion rate
                logger.warning(f"Campaign {campaign_id} has low conversion rate: {bayesian_result['mean']:.2%}")
                self._flag_for_review(campaign_id, 'low_conversion_rate')

            # Store quick analysis
            analysis = {
                'campaign_id': campaign_id,
                'type': '12h_quick',
                'bayesian': bayesian_result,
                'timestamp': datetime.now().isoformat()
            }

            self.cache.set(f'analysis:12h:{campaign_id}', analysis, ttl=43200)  # 12 hours

        except Exception as e:
            logger.error(f"Error processing campaign {campaign_id}: {str(e)}")

    def _process_campaign_deep(self, campaign_id: str):
        """Deep processing for 24h cycle"""
        try:
            logger.info(f"Processing campaign {campaign_id} (deep)")

            # Get historical data
            historical_data = self._get_historical_data(campaign_id)

            if not historical_data:
                logger.warning(f"No historical data for campaign {campaign_id}")
                return

            # Deep Bayesian analysis
            sensitivity_result = self.bayesian.calculate_micro_sensitivity(historical_data)

            # ML prediction
            latest_metrics = historical_data[-1] if historical_data else {}
            ml_prediction = self.ml.predict_performance(latest_metrics)

            # Budget recommendation
            current_budget = latest_metrics.get('daily_budget', 100.0)
            budget_rec = self.ml.recommend_budget(latest_metrics, current_budget)

            # Index in RAG for future reference
            self._index_in_rag(campaign_id, {
                'historical_data': historical_data,
                'sensitivity': sensitivity_result,
                'ml_prediction': ml_prediction,
                'budget_recommendation': budget_rec
            })

            # Store deep analysis
            analysis = {
                'campaign_id': campaign_id,
                'type': '24h_deep',
                'sensitivity': sensitivity_result,
                'ml_prediction': ml_prediction,
                'budget_recommendation': budget_rec,
                'timestamp': datetime.now().isoformat()
            }

            self.cache.set(f'analysis:24h:{campaign_id}', analysis, ttl=86400)  # 24 hours

            # Log insights
            logger.info(f"  Sensitivity: {sensitivity_result['responsiveness']}")
            logger.info(f"  ML Prediction: {ml_prediction['predicted_1day_conversion_rate']:.2%}")
            logger.info(f"  Budget Action: {budget_rec['action']}")

        except Exception as e:
            logger.error(f"Error in deep processing for campaign {campaign_id}: {str(e)}")

    def _get_historical_data(self, campaign_id: str) -> List[Dict]:
        """Get historical performance data"""
        try:
            # Get time-series data
            sorted_set_key = f'timeseries_index:campaign:{campaign_id}'
            entries = self.cache.redis_client.zrange(sorted_set_key, 0, -1)

            historical = []
            for entry in entries:
                if isinstance(entry, bytes):
                    entry = entry.decode('utf-8')

                data = self.cache.get(entry)
                if data:
                    historical.append(data)

            return historical

        except Exception as e:
            logger.error(f"Error getting historical data: {str(e)}")
            return []

    def _index_in_rag(self, campaign_id: str, analysis_data: Dict):
        """Index analysis data in RAG system"""
        try:
            document = {
                'id': f'analysis_{campaign_id}_{datetime.now().timestamp()}',
                'content': json.dumps(analysis_data),
                'metadata': {
                    'campaign_id': campaign_id,
                    'entity_type': 'campaign_analysis',
                    'timestamp': datetime.now().isoformat()
                }
            }

            self.rag.index_document(document)

        except Exception as e:
            logger.error(f"Error indexing in RAG: {str(e)}")

    def _flag_for_review(self, campaign_id: str, reason: str):
        """Flag campaign for manual review"""
        try:
            flag = {
                'campaign_id': campaign_id,
                'reason': reason,
                'timestamp': datetime.now().isoformat(),
                'status': 'pending_review'
            }

            self.cache.set(f'flag:{campaign_id}', flag, ttl=86400)
            logger.warning(f"Campaign {campaign_id} flagged for review: {reason}")

        except Exception as e:
            logger.error(f"Error flagging campaign: {str(e)}")

    def _update_ml_model_quick(self):
        """Quick ML model update (online learning)"""
        try:
            logger.info("Updating ML model (quick)")

            # Get recent data (last 12 hours)
            recent_analyses = self.cache.keys('analysis:12h:*')

            training_data = []
            for key in recent_analyses[:100]:  # Limit to 100 most recent
                data = self.cache.get(key)
                if data:
                    training_data.append(data)

            if len(training_data) >= 10:
                # Update model (would use partial_fit in production)
                logger.info(f"Quick model update with {len(training_data)} samples")

        except Exception as e:
            logger.error(f"Error updating ML model: {str(e)}")

    def _retrain_ml_model(self):
        """Full ML model retraining"""
        try:
            logger.info("Retraining ML model (full)")

            # Get all historical data
            all_analyses = self.cache.keys('analysis:*')

            training_data = []
            for key in all_analyses:
                data = self.cache.get(key)
                if data:
                    training_data.append(data)

            if len(training_data) >= 50:
                success = self.ml.train_model(training_data)
                if success:
                    # Save model
                    model_path = f'/home/runner/work/20_03/20_03/models/trained_model_{datetime.now().strftime("%Y%m%d")}.pkl'
                    self.ml.save_model(model_path)
                    logger.info(f"Model retrained and saved: {model_path}")
            else:
                logger.warning(f"Insufficient data for training ({len(training_data)} samples)")

        except Exception as e:
            logger.error(f"Error retraining ML model: {str(e)}")

    def _cleanup_old_data(self):
        """Clean up old cached data"""
        try:
            logger.info("Cleaning up old data")

            # Remove analyses older than 7 days
            cutoff = datetime.now().timestamp() - (7 * 86400)

            # Clean time-series indices
            indices = self.cache.keys('timeseries_index:*')
            for index_key in indices:
                removed = self.cache.redis_client.zremrangebyscore(
                    index_key, '-inf', cutoff
                )
                if removed > 0:
                    logger.info(f"Removed {removed} old entries from {index_key}")

        except Exception as e:
            logger.error(f"Error cleaning up old data: {str(e)}")

def main():
    """Main function to run the pipeline"""
    logger.info("Starting Data Collection Pipeline")

    pipeline = DataCollectionPipeline()

    # Schedule jobs
    schedule.every(12).hours.do(pipeline.run_12h_cycle)
    schedule.every(24).hours.do(pipeline.run_24h_cycle)

    # Run immediately on startup
    logger.info("Running initial 24h cycle")
    pipeline.run_24h_cycle()

    # Main loop
    logger.info("Pipeline scheduled. Running...")
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == '__main__':
    main()
