"""
Facebook Ads Manager Agent (GPT-5.4-Nano)

This agent is responsible for:
1. Creating and managing Facebook campaigns
2. Configuring adsets with optimal targeting
3. Creating ads with generated creatives
4. Managing budgets and bidding strategies
"""

import os
import json
import logging
from typing import Dict, List, Optional
from flask import Flask, request, jsonify
import openai
import redis
import requests
from datetime import datetime
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

# Facebook API Configuration
FB_API_VERSION = config['facebook']['api_version']
FB_ACCESS_TOKEN = os.getenv('FACEBOOK_ACCESS_TOKEN')
FB_AD_ACCOUNT_ID = os.getenv('FACEBOOK_AD_ACCOUNT_ID')
FB_API_BASE = f"https://graph.facebook.com/{FB_API_VERSION}"

class AdsManagerAgent:
    def __init__(self):
        self.model = config['subagents']['ads_manager_agent']['model']
        self.temperature = config['subagents']['ads_manager_agent']['temperature']
        self.max_tokens = config['subagents']['ads_manager_agent']['max_tokens']

    def create_campaign(self, task_data: Dict) -> Dict:
        """Create a Facebook campaign using MCP tools"""
        try:
            # Generate campaign strategy using LLM
            strategy = self._generate_campaign_strategy(task_data)

            # Create campaign via Facebook API
            campaign_params = {
                'name': task_data.get('campaign_name', f"Campaign_{datetime.now().timestamp()}"),
                'objective': strategy.get('objective', 'CONVERSIONS'),
                'status': 'PAUSED',  # Start paused for review
                'special_ad_categories': strategy.get('special_categories', []),
                'access_token': FB_ACCESS_TOKEN
            }

            # Simulate API call (would use actual MCP tool in production)
            campaign_response = self._call_facebook_api(
                f'/act_{FB_AD_ACCOUNT_ID}/campaigns',
                'POST',
                campaign_params
            )

            campaign_id = campaign_response.get('id', f"campaign_{datetime.now().timestamp()}")

            # Cache campaign data
            campaign_data = {
                'id': campaign_id,
                'params': campaign_params,
                'strategy': strategy,
                'task_data': task_data,
                'timestamp': datetime.now().isoformat()
            }

            redis_client.setex(
                f'campaign:{campaign_id}',
                config['redis']['ttl'],
                json.dumps(campaign_data)
            )

            logger.info(f"Created campaign: {campaign_id}")

            return {
                'status': 'success',
                'campaign_id': campaign_id,
                'strategy': strategy
            }

        except Exception as e:
            logger.error(f"Error creating campaign: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def create_adset(self, task_data: Dict) -> Dict:
        """Create an adset with optimal targeting"""
        try:
            campaign_id = task_data.get('campaign_id')
            if not campaign_id:
                raise ValueError("campaign_id is required")

            # Generate targeting strategy using LLM
            targeting = self._generate_targeting_strategy(task_data)

            # Create adset via Facebook API
            adset_params = {
                'name': task_data.get('adset_name', f"AdSet_{datetime.now().timestamp()}"),
                'campaign_id': campaign_id,
                'daily_budget': task_data.get('daily_budget', 5000),  # in cents
                'billing_event': 'IMPRESSIONS',
                'optimization_goal': 'LINK_CLICKS',
                'bid_strategy': 'LOWEST_COST_WITHOUT_CAP',
                'targeting': targeting,
                'status': 'PAUSED',
                'access_token': FB_ACCESS_TOKEN
            }

            adset_response = self._call_facebook_api(
                f'/act_{FB_AD_ACCOUNT_ID}/adsets',
                'POST',
                adset_params
            )

            adset_id = adset_response.get('id', f"adset_{datetime.now().timestamp()}")

            # Cache adset data
            adset_data = {
                'id': adset_id,
                'campaign_id': campaign_id,
                'params': adset_params,
                'targeting': targeting,
                'timestamp': datetime.now().isoformat()
            }

            redis_client.setex(
                f'adset:{adset_id}',
                config['redis']['ttl'],
                json.dumps(adset_data)
            )

            logger.info(f"Created adset: {adset_id}")

            return {
                'status': 'success',
                'adset_id': adset_id,
                'targeting': targeting
            }

        except Exception as e:
            logger.error(f"Error creating adset: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def create_ad(self, task_data: Dict) -> Dict:
        """Create an ad with creative"""
        try:
            adset_id = task_data.get('adset_id')
            creative_id = task_data.get('creative_id')

            if not adset_id or not creative_id:
                raise ValueError("adset_id and creative_id are required")

            # Get creative from cache
            creative_data = redis_client.get(f'creative:{creative_id}')
            if not creative_data:
                raise ValueError(f"Creative not found: {creative_id}")

            creative = json.loads(creative_data)

            # Create ad creative on Facebook
            creative_params = {
                'name': f"Creative_{creative_id}",
                'object_story_spec': {
                    'page_id': task_data.get('page_id'),
                    'link_data': {
                        'message': creative['copy'].get('primary_text', ''),
                        'link': task_data.get('link_url', ''),
                        'caption': task_data.get('caption', ''),
                        'name': creative['copy'].get('headline', ''),
                        'description': creative['copy'].get('description', ''),
                        'call_to_action': {
                            'type': creative['copy'].get('cta', 'LEARN_MORE')
                        }
                    }
                },
                'access_token': FB_ACCESS_TOKEN
            }

            creative_response = self._call_facebook_api(
                f'/act_{FB_AD_ACCOUNT_ID}/adcreatives',
                'POST',
                creative_params
            )

            fb_creative_id = creative_response.get('id', f"creative_{datetime.now().timestamp()}")

            # Create ad
            ad_params = {
                'name': task_data.get('ad_name', f"Ad_{datetime.now().timestamp()}"),
                'adset_id': adset_id,
                'creative': {'creative_id': fb_creative_id},
                'status': 'PAUSED',
                'access_token': FB_ACCESS_TOKEN
            }

            ad_response = self._call_facebook_api(
                f'/act_{FB_AD_ACCOUNT_ID}/ads',
                'POST',
                ad_params
            )

            ad_id = ad_response.get('id', f"ad_{datetime.now().timestamp()}")

            # Cache ad data
            ad_data = {
                'id': ad_id,
                'adset_id': adset_id,
                'creative_id': creative_id,
                'fb_creative_id': fb_creative_id,
                'params': ad_params,
                'timestamp': datetime.now().isoformat()
            }

            redis_client.setex(
                f'ad:{ad_id}',
                config['redis']['ttl'],
                json.dumps(ad_data)
            )

            logger.info(f"Created ad: {ad_id}")

            return {
                'status': 'success',
                'ad_id': ad_id,
                'creative_id': creative_id
            }

        except Exception as e:
            logger.error(f"Error creating ad: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def _generate_campaign_strategy(self, task_data: Dict) -> Dict:
        """Generate campaign strategy using GPT-5.4-Nano"""
        try:
            prompt = f"""Generate a Facebook campaign strategy.

Task Data:
{json.dumps(task_data, indent=2)}

Return a JSON object with:
- objective: Campaign objective (CONVERSIONS, LINK_CLICKS, etc.)
- special_categories: Array of special ad categories if applicable
- budget_strategy: Budget allocation strategy
- optimization_tips: Array of optimization recommendations

Focus on 1-day click/view conversions.
"""

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a Facebook Ads campaign strategist. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"Error generating strategy: {str(e)}")
            return {
                'objective': 'CONVERSIONS',
                'special_categories': [],
                'budget_strategy': 'even_distribution',
                'optimization_tips': []
            }

    def _generate_targeting_strategy(self, task_data: Dict) -> Dict:
        """Generate targeting strategy using GPT-5.4-Nano"""
        try:
            prompt = f"""Generate optimal Facebook Ad targeting.

Task Data:
{json.dumps(task_data, indent=2)}

Return a JSON object with Facebook targeting parameters:
- geo_locations: Geographic targeting
- age_min, age_max: Age range
- genders: Array of gender targeting
- interests: Array of interest IDs
- behaviors: Array of behavior IDs
- custom_audiences: Array of custom audience IDs if applicable

Optimize for 1-day conversions.
"""

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a Facebook Ads targeting expert. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"Error generating targeting: {str(e)}")
            return {
                'geo_locations': {'countries': ['US']},
                'age_min': 18,
                'age_max': 65,
                'genders': [1, 2]
            }

    def _call_facebook_api(self, endpoint: str, method: str, params: Dict) -> Dict:
        """Call Facebook Graph API (MCP tool simulation)"""
        try:
            url = f"{FB_API_BASE}{endpoint}"

            # In production, this would use actual MCP Facebook tools
            # For now, simulate the API call
            logger.info(f"Facebook API call: {method} {url}")
            logger.info(f"Params: {json.dumps(params, indent=2)}")

            # Simulate successful response
            return {
                'id': f"fb_{datetime.now().timestamp()}",
                'success': True
            }

        except Exception as e:
            logger.error(f"Facebook API error: {str(e)}")
            raise

agent = AdsManagerAgent()

@app.route('/ads-manager-agent', methods=['POST'])
def handle_request():
    """Handle incoming requests from orchestrator"""
    try:
        task_data = request.json
        logger.info(f"Received task: {task_data}")

        task_type = task_data.get('task_type', 'create_campaign')

        if task_type == 'create_campaign':
            result = agent.create_campaign(task_data)
        elif task_type == 'create_adset':
            result = agent.create_adset(task_data)
        elif task_type == 'create_ad':
            result = agent.create_ad(task_data)
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
        'agent': 'ads_manager_agent',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = config['subagents']['ads_manager_agent']['port']
    logger.info(f"Starting Ads Manager Agent on port {port}")
    app.run(host='0.0.0.0', port=port)
