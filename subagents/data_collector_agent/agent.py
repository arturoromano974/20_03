"""
Data Collection Agent (GPT-5.4-Nano)

This agent is responsible for:
1. Collecting campaign insights at scheduled intervals (12h/24h)
2. Storing data in time-series format
3. Feeding data to RAG system for context
4. Processing Facebook API responses
"""

import os
import json
import logging
from typing import Dict, List, Optional
from flask import Flask, request, jsonify
from openai import OpenAI
import redis
import requests
from datetime import datetime, timedelta
from utils.config_loader import load_config

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
config = load_config()

# Initialize OpenAI client
_openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize Redis
redis_client = redis.Redis(
    host=config['redis']['host'],
    port=config['redis']['port'],
    db=config['redis']['db'],
    decode_responses=True
)

# Facebook API Configuration
FB_API_VERSION = config['facebook']['api_version']
FB_ACCESS_TOKEN = os.getenv('FACEBOOK_ACCESS_TOKEN')
FB_AD_ACCOUNT_ID = os.getenv('FACEBOOK_AD_ACCOUNT_ID')
FB_API_BASE = f"https://graph.facebook.com/{FB_API_VERSION}"

class DataCollectorAgent:
    def __init__(self):
        self.client = _openai_client
        self.model = config['subagents']['data_collector_agent']['model']
        self.temperature = config['subagents']['data_collector_agent']['temperature']
        self.max_tokens = config['subagents']['data_collector_agent']['max_tokens']

    def collect_data(self, task_data: Dict) -> Dict:
        """Collect data from Facebook API at scheduled intervals"""
        try:
            collection_type = task_data.get('collection_type', '24h')
            entity_ids = task_data.get('entity_ids', [])
            entity_type = task_data.get('entity_type', 'campaign')

            # Determine time range based on collection type
            time_range = self._get_time_range(collection_type)

            # Collect data for each entity
            collected_data = []

            for entity_id in entity_ids:
                data = self._fetch_insights(entity_id, entity_type, time_range)
                if data:
                    # Process and structure the data
                    processed = self._process_insights(data, entity_id, entity_type)

                    # Store in cache
                    self._store_data(processed, entity_id, entity_type)

                    # Store in time-series format
                    self._store_time_series(processed, entity_id, entity_type)

                    # Feed to RAG system
                    self._feed_to_rag(processed, entity_id, entity_type)

                    collected_data.append(processed)

            logger.info(f"Collected data for {len(collected_data)} entities")

            return {
                'status': 'success',
                'collection_type': collection_type,
                'entities_processed': len(collected_data),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error collecting data: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def _get_time_range(self, collection_type: str) -> Dict:
        """Get time range for data collection"""
        now = datetime.now()

        if collection_type == '12h':
            since = now - timedelta(hours=12)
        elif collection_type == '24h':
            since = now - timedelta(hours=24)
        elif collection_type == 'realtime':
            since = now - timedelta(hours=1)
        else:
            since = now - timedelta(hours=24)

        return {
            'since': since.strftime('%Y-%m-%d'),
            'until': now.strftime('%Y-%m-%d')
        }

    def _fetch_insights(self, entity_id: str, entity_type: str,
                       time_range: Dict) -> Optional[Dict]:
        """Fetch insights from Facebook API"""
        try:
            # Build API endpoint based on entity type
            if entity_type == 'campaign':
                endpoint = f"/{entity_id}/insights"
            elif entity_type == 'adset':
                endpoint = f"/{entity_id}/insights"
            elif entity_type == 'ad':
                endpoint = f"/{entity_id}/insights"
            else:
                raise ValueError(f"Unknown entity type: {entity_type}")

            # Build parameters
            params = {
                'access_token': FB_ACCESS_TOKEN,
                'time_range': json.dumps(time_range),
                'fields': ','.join(config['data_collection']['metrics']),
                'breakdowns': ','.join(config['data_collection']['breakdown']),
                'level': entity_type,
                'limit': 100
            }

            # Call Facebook API (simulated for this implementation)
            url = f"{FB_API_BASE}{endpoint}"
            logger.info(f"Fetching insights: {url}")

            # Simulate API response
            # In production, use actual API call:
            # response = requests.get(url, params=params)
            # return response.json()

            # Simulated response
            return self._generate_simulated_insights(entity_id, entity_type)

        except Exception as e:
            logger.error(f"Error fetching insights: {str(e)}")
            return None

    def _generate_simulated_insights(self, entity_id: str,
                                    entity_type: str) -> Dict:
        """Generate simulated insights for testing"""
        import random

        return {
            'data': [{
                'impressions': random.randint(1000, 10000),
                'clicks': random.randint(50, 500),
                'spend': round(random.uniform(10, 200), 2),
                'conversions': random.randint(5, 50),
                'actions': [
                    {
                        'action_type': '1_day_click',
                        'value': str(random.randint(5, 30))
                    },
                    {
                        'action_type': '1_day_view',
                        'value': str(random.randint(10, 40))
                    }
                ],
                'ctr': round(random.uniform(0.5, 5.0), 2),
                'cpc': round(random.uniform(0.2, 2.0), 2),
                'cpm': round(random.uniform(5, 25), 2),
                'frequency': round(random.uniform(1.0, 3.5), 2),
                'reach': random.randint(800, 8000),
                'date_start': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                'date_stop': datetime.now().strftime('%Y-%m-%d')
            }],
            'paging': {}
        }

    def _process_insights(self, data: Dict, entity_id: str,
                         entity_type: str) -> Dict:
        """Process insights using structured JSON (no raw analysis)"""
        try:
            # Extract data from API response
            insights = data.get('data', [])
            if not insights:
                return {}

            # Aggregate multiple data points
            aggregated = {
                'entity_id': entity_id,
                'entity_type': entity_type,
                'impressions': 0,
                'clicks': 0,
                'spend': 0.0,
                'conversions': 0,
                'ctr': 0.0,
                'cpc': 0.0,
                'cpm': 0.0,
                'frequency': 0.0,
                'reach': 0,
                '1_day_clicks': 0,
                '1_day_views': 0,
                'timestamp': datetime.now().isoformat()
            }

            for insight in insights:
                aggregated['impressions'] += insight.get('impressions', 0)
                aggregated['clicks'] += insight.get('clicks', 0)
                aggregated['spend'] += float(insight.get('spend', 0))
                aggregated['conversions'] += insight.get('conversions', 0)
                aggregated['reach'] += insight.get('reach', 0)

                # Extract 1-day metrics
                actions = insight.get('actions', [])
                for action in actions:
                    if action['action_type'] == '1_day_click':
                        aggregated['1_day_clicks'] += int(action['value'])
                    elif action['action_type'] == '1_day_view':
                        aggregated['1_day_views'] += int(action['value'])

            # Calculate averages
            count = len(insights)
            if count > 0:
                aggregated['frequency'] = sum(i.get('frequency', 0) for i in insights) / count

            # Calculate derived metrics
            if aggregated['impressions'] > 0:
                aggregated['ctr'] = (aggregated['clicks'] / aggregated['impressions']) * 100
                aggregated['cpm'] = (aggregated['spend'] / aggregated['impressions']) * 1000

            if aggregated['clicks'] > 0:
                aggregated['cpc'] = aggregated['spend'] / aggregated['clicks']
                aggregated['conversion_rate'] = (aggregated['conversions'] / aggregated['clicks']) * 100

            return aggregated

        except Exception as e:
            logger.error(f"Error processing insights: {str(e)}")
            return {}

    def _store_data(self, data: Dict, entity_id: str, entity_type: str):
        """Store data in Redis cache"""
        try:
            key = f'performance:{entity_type}:{entity_id}'
            redis_client.setex(
                key,
                config['redis']['ttl'],
                json.dumps(data)
            )
            logger.info(f"Stored data in cache: {key}")
        except Exception as e:
            logger.error(f"Error storing data: {str(e)}")

    def _store_time_series(self, data: Dict, entity_id: str, entity_type: str):
        """Store data in time-series format"""
        try:
            # Create time-series key with timestamp
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            key = f'timeseries:{entity_type}:{entity_id}:{timestamp}'

            redis_client.setex(
                key,
                config['redis']['ttl'] * 7,  # Keep time-series data longer
                json.dumps(data)
            )

            # Add to sorted set for easy time-range queries
            sorted_set_key = f'timeseries_index:{entity_type}:{entity_id}'
            redis_client.zadd(
                sorted_set_key,
                {key: datetime.now().timestamp()}
            )

            logger.info(f"Stored time-series data: {key}")
        except Exception as e:
            logger.error(f"Error storing time-series data: {str(e)}")

    def _feed_to_rag(self, data: Dict, entity_id: str, entity_type: str):
        """Feed data to RAG system for context"""
        try:
            # Create document for RAG
            document = {
                'id': f"{entity_type}_{entity_id}_{datetime.now().timestamp()}",
                'entity_id': entity_id,
                'entity_type': entity_type,
                'content': json.dumps(data),
                'metadata': {
                    'timestamp': data.get('timestamp'),
                    'performance_score': self._calculate_performance_score(data)
                },
                'embedding_ready': True
            }

            # Store in RAG index (simulated)
            # In production, use actual vector DB (Qdrant, Weaviate, etc.)
            rag_key = f'rag:{entity_type}:{entity_id}'
            redis_client.lpush(rag_key, json.dumps(document))
            redis_client.ltrim(rag_key, 0, 99)  # Keep last 100 entries

            logger.info(f"Fed data to RAG: {rag_key}")
        except Exception as e:
            logger.error(f"Error feeding to RAG: {str(e)}")

    def _calculate_performance_score(self, data: Dict) -> float:
        """Calculate simple performance score for RAG metadata"""
        try:
            # Simple scoring based on key metrics
            ctr = data.get('ctr', 0)
            conversion_rate = data.get('conversion_rate', 0)
            one_day_ratio = data.get('1_day_clicks', 0) / max(data.get('clicks', 1), 1)

            # Weighted score
            score = (ctr * 0.3 + conversion_rate * 0.4 + one_day_ratio * 100 * 0.3)

            return min(score / 10, 10.0)  # Normalize to 0-10
        except Exception as e:
            logger.error(f"Error calculating score: {str(e)}")
            return 0.0

agent = DataCollectorAgent()

@app.route('/collector-agent', methods=['POST'])
def handle_request():
    """Handle incoming requests from orchestrator"""
    try:
        task_data = request.json
        logger.info(f"Received task: {task_data}")

        task_type = task_data.get('task_type', 'collect_data')

        if task_type == 'collect_data':
            result = agent.collect_data(task_data)
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
        'agent': 'data_collector_agent',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = config['subagents']['data_collector_agent']['port']
    logger.info(f"Starting Data Collector Agent on port {port}")
    app.run(host='0.0.0.0', port=port)
